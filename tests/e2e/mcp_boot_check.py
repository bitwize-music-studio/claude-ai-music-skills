#!/usr/bin/env python3
"""End-to-end MCP server boot checker (stdlib-only, no pytest, no repo imports).

Launches the bitwize-music MCP server as a real subprocess and drives a stdio
JSON-RPC handshake over its pipes: ``initialize`` -> ``notifications/initialized``
-> ``tools/list`` -> (optional) ``tools/call health_check``. Then closes stdin
and asserts the server shuts down cleanly on EOF.

This exists because the unit suite imports ``server.py`` in-process with a mocked
FastMCP whose ``run()`` is a no-op, so it can never catch process-level startup
failures like issue #476 (``import fcntl`` crashing the server on Windows). This
checker boots the actual process and speaks the actual protocol.

It is deliberately stdlib-only and run by the *system* Python: the server runs
in the user-style venv (``~/.bitwize-music/venv``), exactly like a real install,
while this harness needs no dependencies. The filename has no ``test_`` prefix,
so pytest never collects it.

Usage:
    python tests/e2e/mcp_boot_check.py [options] -- CMD [ARG ...]

The command after ``--`` is the exact child argv (the workflow chooses the
launch shape per OS). ``CLAUDE_PLUGIN_ROOT`` is passed through the environment.

Options:
    --timeout SECS         Overall deadline for boot + handshake (default 120).
    --shutdown-grace SECS  Wait for clean exit after stdin EOF (default 20).
    --expect-tool NAME     Tool that must appear in tools/list (repeatable;
                           default: health_check).
    --call-tool NAME       Call this tool with {} arguments after tools/list.

Exit codes:
    0  server booted, responded, and shut down cleanly
    1  protocol / assertion failure (bad response, missing tool, dirty exit)
    2  deadline exceeded (boot or a response took too long)
    3  spawn problem or the child exited before/while handshaking

Local verification (Linux dev box) — drive the same launcher .mcp.json uses:
    CLAUDE_PLUGIN_ROOT="$PWD" python3 tests/e2e/mcp_boot_check.py \\
        --call-tool health_check -- \\
        "$PWD/servers/bitwize-music-server/mcp-launch"
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Any

SERVER_NAME = "bitwize-music-mcp"
# Any version in the SDK's supported list; the server negotiates down to its
# own latest if it doesn't recognise this, so the exact value is not load-bearing.
PROTOCOL_VERSION = "2025-06-18"

# Exit codes (see module docstring).
EXIT_OK = 0
EXIT_PROTOCOL = 1
EXIT_TIMEOUT = 2
EXIT_SPAWN = 3


class BootError(Exception):
    """A boot-check failure carrying the phase, message, and process exit code."""

    def __init__(self, phase: str, message: str, code: int) -> None:
        super().__init__(message)
        self.phase = phase
        self.message = message
        self.code = code


class ServerProc:
    """A spawned MCP server with line-framed JSON-RPC over binary stdio pipes.

    Binary pipes are deliberate: writing ``json.dumps(...).encode() + b"\\n"``
    means no text-mode newline translation can ever inject ``\\r\\n`` into the
    framing. The server itself emits ``\\r\\n`` line endings on Windows, so we
    strip a trailing ``\\r`` before parsing.
    """

    def __init__(self, cmd: list[str]) -> None:
        self._stdout_q: queue.Queue[bytes | None] = queue.Queue()
        self._stderr_tail: deque[str] = deque(maxlen=200)

        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        # Put the child (and its grandchild server.py, via run.py) in its own
        # process group / job so shutdown escalation can kill the whole tree.
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        try:
            self.proc = subprocess.Popen(cmd, **popen_kwargs)
        except OSError as exc:
            raise BootError("spawn", f"could not launch {cmd!r}: {exc}", EXIT_SPAWN) from exc

        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        assert self.proc.stderr is not None
        self._stdin = self.proc.stdin

        self._t_out = threading.Thread(target=self._pump_stdout, daemon=True)
        self._t_err = threading.Thread(target=self._pump_stderr, daemon=True)
        self._t_out.start()
        self._t_err.start()

    def _pump_stdout(self) -> None:
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            self._stdout_q.put(raw)
        self._stdout_q.put(None)  # sentinel: stdout closed (child exiting)

    def _pump_stderr(self) -> None:
        assert self.proc.stderr is not None
        for raw in self.proc.stderr:
            self._stderr_tail.append(raw.decode("utf-8", "replace").rstrip("\r\n"))

    def stderr_tail(self) -> str:
        return "\n".join(self._stderr_tail)

    def send(self, message: dict[str, Any]) -> None:
        data = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            self._stdin.write(data)
            self._stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise BootError(
                "send",
                f"child closed its stdin before we could write ({exc}); "
                f"exit code {self.proc.poll()}",
                EXIT_SPAWN,
            ) from exc

    def recv_result(self, expect_id: int, deadline: float) -> dict[str, Any]:
        """Return the ``result`` of the response with ``expect_id``.

        Skips notifications/log lines (no matching ``id``). Raises BootError on a
        JSON-RPC ``error``, a non-JSON stdout line (corrupted transport), child
        exit, or the deadline passing.
        """
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BootError(
                    "recv",
                    f"timed out waiting for response id={expect_id}",
                    EXIT_TIMEOUT,
                )
            try:
                raw = self._stdout_q.get(timeout=remaining)
            except queue.Empty:
                raise BootError(
                    "recv",
                    f"timed out waiting for response id={expect_id}",
                    EXIT_TIMEOUT,
                ) from None

            if raw is None:
                raise BootError(
                    "recv",
                    f"server stdout closed before response id={expect_id}; "
                    f"exit code {self.proc.poll()}",
                    EXIT_SPAWN,
                )

            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BootError(
                    "recv",
                    f"non-JSON line on stdout — stdio transport corrupted "
                    f"(a stray print?): {line!r} ({exc})",
                    EXIT_PROTOCOL,
                ) from exc

            if msg.get("id") != expect_id:
                # Server-initiated notification or a response to another id.
                continue
            if "error" in msg:
                raise BootError(
                    "recv",
                    f"JSON-RPC error for id={expect_id}: {msg['error']}",
                    EXIT_PROTOCOL,
                )
            result = msg.get("result")
            if not isinstance(result, dict):
                raise BootError(
                    "recv",
                    f"response id={expect_id} has no result object: {msg!r}",
                    EXIT_PROTOCOL,
                )
            return result

    def close_stdin(self) -> None:
        with contextlib.suppress(OSError):
            self._stdin.close()

    def wait(self, timeout: float) -> int | None:
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def kill_tree(self) -> None:
        """Best-effort kill of the child and any grandchild (run.py -> server.py)."""
        if self.proc.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        # Final fallback: direct kill of the immediate child.
        with contextlib.suppress(OSError):
            self.proc.kill()


def _ok(phase: str, detail: str) -> None:
    print(f"[OK] {phase}: {detail}", flush=True)


def run_handshake(
    server: ServerProc,
    deadline: float,
    expect_tools: list[str],
    call_tool: str | None,
) -> None:
    # 1. initialize
    server.send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "bitwize-music-boot-check", "version": "1.0.0"},
            },
        }
    )
    init = server.recv_result(1, deadline)
    server_info = init.get("serverInfo", {})
    got_name = server_info.get("name")
    if got_name != SERVER_NAME:
        raise BootError(
            "initialize",
            f"serverInfo.name={got_name!r}, expected {SERVER_NAME!r}",
            EXIT_PROTOCOL,
        )
    negotiated = init.get("protocolVersion")
    if not isinstance(negotiated, str) or not negotiated:
        raise BootError(
            "initialize", f"missing/blank protocolVersion: {init!r}", EXIT_PROTOCOL
        )
    _ok("initialize", f"serverInfo.name={got_name} protocolVersion={negotiated}")

    # 2. initialized notification (no response)
    server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # 3. tools/list
    server.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_result = server.recv_result(2, deadline)
    tools = tools_result.get("tools")
    if not isinstance(tools, list) or not tools:
        raise BootError(
            "tools/list", f"expected a non-empty tools array, got {tools!r}", EXIT_PROTOCOL
        )
    names = {
        t["name"]
        for t in tools
        if isinstance(t, dict) and isinstance(t.get("name"), str)
    }
    missing = [name for name in expect_tools if name not in names]
    if missing:
        raise BootError(
            "tools/list",
            f"missing expected tool(s) {missing}; present: {sorted(names)}",
            EXIT_PROTOCOL,
        )
    _ok("tools/list", f"{len(tools)} tools, present: {', '.join(expect_tools)}")

    # 4. optional tools/call
    if call_tool is not None:
        server.send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": call_tool, "arguments": {}},
            }
        )
        call_result = server.recv_result(3, deadline)
        # A tool-level failure surfaces as result.isError == True (JSON-RPC
        # success). health_check legitimately returns overall "warn" in CI
        # (no plugin cache), so assert only that the call did not error out.
        if call_result.get("isError") is True:
            content = call_result.get("content")
            raise BootError(
                "tools/call",
                f"{call_tool} returned isError=true: {content!r}",
                EXIT_PROTOCOL,
            )
        _ok("tools/call", f"{call_tool} responded without error")


def shutdown(server: ServerProc, grace: float) -> None:
    server.close_stdin()
    code = server.wait(timeout=grace)
    if code is None:
        server.kill_tree()
        raise BootError(
            "shutdown",
            f"server did not exit within {grace}s of stdin EOF — it would hang "
            f"real clients too (killed the process tree)",
            EXIT_PROTOCOL,
        )
    if code != 0:
        raise BootError(
            "shutdown",
            f"server exited {code} after a clean handshake (shutdown crash)",
            EXIT_PROTOCOL,
        )
    _ok("shutdown", "clean exit on stdin EOF (returncode 0)")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Boot the MCP server and drive a stdio JSON-RPC handshake.",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--shutdown-grace", type=float, default=20.0)
    parser.add_argument("--expect-tool", action="append", dest="expect_tools", default=None)
    parser.add_argument("--call-tool", default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        parser.error("missing server command after '--'")
    args.cmd = cmd
    if not args.expect_tools:
        args.expect_tools = ["health_check"]
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    deadline = time.monotonic() + args.timeout

    server: ServerProc | None = None
    try:
        server = ServerProc(args.cmd)
        _ok("spawn", f"launched pid {server.proc.pid}: {' '.join(args.cmd)}")
        run_handshake(server, deadline, args.expect_tools, args.call_tool)
        shutdown(server, args.shutdown_grace)
        print("[OK] MCP server booted, responded, and shut down cleanly", flush=True)
        return EXIT_OK
    except BootError as err:
        print(f"[FAIL] {err.phase}: {err.message}", file=sys.stderr, flush=True)
        if server is not None:
            code = server.proc.poll()
            if code is not None:
                print(f"       child exit code: {code}", file=sys.stderr, flush=True)
            tail = server.stderr_tail()
            if tail:
                print(
                    "---- server stderr (last 200 lines) ----",
                    file=sys.stderr,
                    flush=True,
                )
                print(tail, file=sys.stderr, flush=True)
        return err.code
    finally:
        if server is not None:
            server.kill_tree()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
