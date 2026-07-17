#!/usr/bin/env python3
"""End-to-end MCP server boot checker (stdlib-only, no pytest, no repo imports).

Launches the bitwize-music MCP server as a real subprocess and drives a stdio
JSON-RPC handshake over its pipes: ``initialize`` -> ``notifications/initialized``
-> ``tools/list`` -> (optional) ``tools/call health_check``. Then closes stdin
and asserts the server shuts down cleanly on EOF.

With ``--scenario state-workflow`` it additionally proves the core state
workflow end-to-end: it seeds a temp content tree (1 album / 2 tracks, one
track title carrying a non-ASCII em dash for UTF-8 regression coverage),
points ``~/.bitwize-music/config.yaml`` at it, then drives ``rebuild_state``
-> ``list_albums`` -> ``find_album`` -> ``get_config`` -> ``list_tracks``
and asserts the real payloads. Any pre-existing ``config.yaml`` and
``cache/state.json`` are renamed aside first and restored in a ``finally``
no matter how the run ends, so the scenario is safe on a developer machine.

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
    --scenario NAME        Extra end-to-end scenario after the handshake.
                           Currently: state-workflow (seed config + content
                           tree, rebuild state, query albums/tracks/config,
                           assert a UTF-8 title round-trips).

Exit codes:
    0  server booted, responded, and shut down cleanly
    1  protocol / assertion failure (bad response, missing tool, dirty exit)
    2  deadline exceeded (boot or a response took too long)
    3  spawn problem or the child exited before/while handshaking

Local verification (Linux dev box) — drive the same launcher .mcp.json uses:
    CLAUDE_PLUGIN_ROOT="$PWD" python3 tests/e2e/mcp_boot_check.py \\
        --call-tool health_check --scenario state-workflow -- \\
        "$PWD/servers/bitwize-music-server/mcp-launch"
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
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

# --scenario state-workflow constants. The seeded markdown mirrors the shapes
# proven by tests/unit/state/test_indexer.py (_make_album_tree /
# _make_track_content) — README frontmatter + `| **Status** |` row, and the
# `## Track Details` table in track files.
BACKUP_SUFFIX = ".boot-check-bak"
SCENARIO_ARTIST = "ci-artist"
SCENARIO_GENRE = "electronic"
SCENARIO_ALBUM = "ci-test-album"
SCENARIO_ALBUM_TITLE = "Ci Test Album"
SCENARIO_TRACK1_SLUG = "01-first-track"
# The em dash is deliberate: end-to-end UTF-8 round-trip coverage (file on
# disk -> parser -> state cache -> JSON payload), especially on Windows.
SCENARIO_TRACK1_TITLE = "First Track — Reprise"
SCENARIO_TRACK2_SLUG = "02-second-track"
SCENARIO_TRACK2_TITLE = "Second Track"


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


def call_tool_json(
    server: ServerProc,
    req_id: int,
    name: str,
    arguments: dict[str, Any],
    deadline: float,
    phase: str = "tools/call",
) -> dict[str, Any]:
    """Call a tool and return its parsed JSON payload.

    MCP tool results carry the handler's JSON string as text content
    (``result["content"][0]["text"]``); a tool-level failure surfaces as
    ``result.isError == True`` (still a JSON-RPC success). Raises BootError
    on isError, a malformed content array, or a non-JSON payload.
    """
    server.send(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    result = server.recv_result(req_id, deadline)
    if result.get("isError") is True:
        raise BootError(
            phase,
            f"{name} returned isError=true: {result.get('content')!r}",
            EXIT_PROTOCOL,
        )
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise BootError(
            phase,
            f"{name}: expected a non-empty content array, got {content!r}",
            EXIT_PROTOCOL,
        )
    first = content[0]
    if (
        not isinstance(first, dict)
        or first.get("type") != "text"
        or not isinstance(first.get("text"), str)
    ):
        raise BootError(
            phase,
            f"{name}: expected a text content item, got {first!r}",
            EXIT_PROTOCOL,
        )
    try:
        payload = json.loads(first["text"])
    except json.JSONDecodeError as exc:
        raise BootError(
            phase,
            f"{name}: payload is not JSON ({exc}): {first['text'][:200]!r}",
            EXIT_PROTOCOL,
        ) from exc
    if not isinstance(payload, dict):
        raise BootError(
            phase,
            f"{name}: payload is not a JSON object: {payload!r}",
            EXIT_PROTOCOL,
        )
    return payload


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
        # health_check legitimately returns overall "warn" in CI (no plugin
        # cache), so assert only that the call did not error out and that the
        # payload is well-formed JSON.
        call_tool_json(server, 3, call_tool, {}, deadline)
        _ok("tools/call", f"{call_tool} responded without error")


def _yaml_sq(value: str) -> str:
    """Quote a string as a single-quoted YAML scalar.

    The only escape in single-quoted YAML is doubling the quote itself;
    Windows backslashes pass through literally, so temp paths are safe.
    """
    return "'" + value.replace("'", "''") + "'"


def _album_readme() -> str:
    """README.md matching test_indexer.py::_make_album_tree's default shape."""
    return f"""---
title: "{SCENARIO_ALBUM_TITLE}"
genres: ["{SCENARIO_GENRE}"]
explicit: false
---

# {SCENARIO_ALBUM_TITLE}

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 2 |
"""


def _track_md(title: str) -> str:
    """Track markdown matching test_indexer.py::_make_track_content's shape."""
    return f"""# {title}

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | {title} |
| **Status** | Not Started |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | N/A |
"""


class StateWorkflowEnv:
    """Isolated home state for ``--scenario state-workflow``.

    Renames any real ``~/.bitwize-music/config.yaml`` and
    ``~/.bitwize-music/cache/state.json`` aside (``*.boot-check-bak``), seeds
    a temp content tree plus a config pointing at it, and puts everything
    back in ``teardown()`` — which main() runs in a ``finally`` after the
    server is dead, so a crash anywhere still restores the user's files.
    ``Path.home()`` is used on purpose: on Windows it follows USERPROFILE,
    agreeing byte-for-byte with the server's own config discovery.
    """

    def __init__(self) -> None:
        base = Path.home() / ".bitwize-music"
        self._config_path = base / "config.yaml"
        self._state_path = base / "cache" / "state.json"
        # (target, backup-or-None) per file whose backup step completed;
        # teardown only ever touches processed targets, so a failure halfway
        # through setup can never delete a file that was not backed up.
        self._processed: list[tuple[Path, Path | None]] = []
        self.temp_root: Path | None = None
        self.content_root: Path | None = None

    def setup(self) -> None:
        for target in (self._config_path, self._state_path):
            backup = target.with_name(target.name + BACKUP_SUFFIX)
            if backup.exists():
                raise BootError(
                    "scenario",
                    f"stale backup {backup} exists (a previous run crashed "
                    f"mid-restore?) — restore or remove it manually, then retry",
                    EXIT_PROTOCOL,
                )
            if target.exists():
                target.rename(backup)
                self._processed.append((target, backup))
                _ok("scenario", f"backed up {target} -> {backup.name}")
            else:
                self._processed.append((target, None))

        self.temp_root = Path(tempfile.mkdtemp(prefix="bitwize-boot-check-"))
        content_root = self.temp_root / "content"
        audio_root = self.temp_root / "audio"
        documents_root = self.temp_root / "documents"
        tracks_dir = (
            content_root / "artists" / SCENARIO_ARTIST / "albums"
            / SCENARIO_GENRE / SCENARIO_ALBUM / "tracks"
        )
        tracks_dir.mkdir(parents=True)
        audio_root.mkdir()
        documents_root.mkdir()
        album_dir = tracks_dir.parent
        (album_dir / "README.md").write_text(_album_readme(), encoding="utf-8")
        (tracks_dir / f"{SCENARIO_TRACK1_SLUG}.md").write_text(
            _track_md(SCENARIO_TRACK1_TITLE), encoding="utf-8"
        )
        (tracks_dir / f"{SCENARIO_TRACK2_SLUG}.md").write_text(
            _track_md(SCENARIO_TRACK2_TITLE), encoding="utf-8"
        )
        # Resolve once, after creation, so the get_config comparison uses the
        # same symlink-free form the server computes (macOS /var -> /private/var).
        self.content_root = content_root.resolve()
        _ok("scenario", f"seeded temp content tree at {self.content_root}")

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        config_text = (
            "# Temporary config written by tests/e2e/mcp_boot_check.py"
            " --scenario state-workflow.\n"
            f"# If this file survived a run, restore config.yaml{BACKUP_SUFFIX}"
            " over it.\n"
            "artist:\n"
            f"  name: {_yaml_sq(SCENARIO_ARTIST)}\n"
            "paths:\n"
            f"  content_root: {_yaml_sq(str(self.content_root))}\n"
            f"  audio_root: {_yaml_sq(str(audio_root.resolve()))}\n"
            f"  documents_root: {_yaml_sq(str(documents_root.resolve()))}\n"
        )
        self._config_path.write_text(config_text, encoding="utf-8")
        _ok("scenario", f"wrote scenario config -> {self._config_path}")

    def teardown(self) -> None:
        """Restore the user's real files; best-effort but loud on failure."""
        for target, backup in reversed(self._processed):
            try:
                if target.exists():
                    target.unlink()
                if backup is not None:
                    backup.rename(target)
                    _ok("scenario", f"restored {target} from {backup.name}")
            except OSError as exc:
                print(
                    f"[WARN] scenario: could not restore {target}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        self._processed.clear()
        if self.temp_root is not None:
            shutil.rmtree(self.temp_root, ignore_errors=True)
            self.temp_root = None


def run_state_workflow(server: ServerProc, deadline: float, env: StateWorkflowEnv) -> None:
    """Drive config -> rebuild_state -> queries -> UTF-8 round-trip."""
    # 1. rebuild_state must index exactly the seeded tree: 1 album / 2 tracks.
    payload = call_tool_json(server, 4, "rebuild_state", {}, deadline, phase="scenario")
    if payload.get("success") is not True:
        raise BootError(
            "scenario",
            f"rebuild_state did not report success: {payload!r}",
            EXIT_PROTOCOL,
        )
    if payload.get("albums") != 1 or payload.get("tracks") != 2:
        raise BootError(
            "scenario",
            f"rebuild_state indexed albums={payload.get('albums')!r} "
            f"tracks={payload.get('tracks')!r}, expected 1 album / 2 tracks "
            f"from the seeded tree: {payload!r}",
            EXIT_PROTOCOL,
        )
    _ok("scenario", "rebuild_state indexed 1 album / 2 tracks from the seeded tree")

    # 2. list_albums must show exactly the seeded album.
    payload = call_tool_json(server, 5, "list_albums", {}, deadline, phase="scenario")
    albums = payload.get("albums")
    slugs = (
        [a.get("slug") for a in albums if isinstance(a, dict)]
        if isinstance(albums, list)
        else []
    )
    if slugs != [SCENARIO_ALBUM]:
        raise BootError(
            "scenario",
            f"list_albums returned slugs {slugs!r}, expected [{SCENARIO_ALBUM!r}]",
            EXIT_PROTOCOL,
        )
    _ok("scenario", f"list_albums shows {SCENARIO_ALBUM}")

    # 3. find_album fuzzy match: spaces normalize to the hyphenated slug.
    payload = call_tool_json(
        server, 6, "find_album", {"name": "ci test album"}, deadline, phase="scenario"
    )
    if payload.get("found") is not True or payload.get("slug") != SCENARIO_ALBUM:
        raise BootError(
            "scenario",
            f"find_album('ci test album') did not resolve to "
            f"{SCENARIO_ALBUM!r}: {payload!r}",
            EXIT_PROTOCOL,
        )
    _ok("scenario", f"find_album resolved 'ci test album' -> {SCENARIO_ALBUM}")

    # 4. get_config round-trips artist name and content_root. Compare paths
    # via pathlib (not raw strings) so Windows separator/case differences
    # cannot cause a false failure.
    payload = call_tool_json(server, 7, "get_config", {}, deadline, phase="scenario")
    config = payload.get("config")
    if not isinstance(config, dict):
        raise BootError(
            "scenario", f"get_config returned no config object: {payload!r}", EXIT_PROTOCOL
        )
    if config.get("artist_name") != SCENARIO_ARTIST:
        raise BootError(
            "scenario",
            f"get_config artist_name={config.get('artist_name')!r}, "
            f"expected {SCENARIO_ARTIST!r}",
            EXIT_PROTOCOL,
        )
    got_root = config.get("content_root")
    assert env.content_root is not None  # set by setup()
    if not isinstance(got_root, str) or Path(got_root) != env.content_root:
        raise BootError(
            "scenario",
            f"get_config content_root={got_root!r} != seeded {env.content_root}",
            EXIT_PROTOCOL,
        )
    _ok("scenario", "get_config round-trips artist_name and content_root")

    # 5. UTF-8 round-trip: the em-dash title must come back byte-identical.
    payload = call_tool_json(
        server, 8, "list_tracks", {"album_slug": SCENARIO_ALBUM}, deadline, phase="scenario"
    )
    tracks = payload.get("tracks")
    titles = (
        {t.get("slug"): t.get("title") for t in tracks if isinstance(t, dict)}
        if isinstance(tracks, list)
        else {}
    )
    got_title = titles.get(SCENARIO_TRACK1_SLUG)
    if got_title != SCENARIO_TRACK1_TITLE:
        raise BootError(
            "scenario",
            f"UTF-8 title did not round-trip: got {got_title!a}, "
            f"expected {SCENARIO_TRACK1_TITLE!a}",
            EXIT_PROTOCOL,
        )
    if titles.get(SCENARIO_TRACK2_SLUG) != SCENARIO_TRACK2_TITLE:
        raise BootError(
            "scenario",
            f"list_tracks track titles wrong: {titles!r}",
            EXIT_PROTOCOL,
        )
    # !a (ascii) keeps this line safe on non-UTF-8 Windows consoles.
    _ok("scenario", f"UTF-8 track title round-tripped intact ({got_title!a})")


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
    parser.add_argument("--scenario", choices=["state-workflow"], default=None)
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
    # Diagnostics may embed non-ASCII (the scenario's em-dash title); never
    # let a non-UTF-8 Windows console turn a report into a UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    deadline = time.monotonic() + args.timeout

    env: StateWorkflowEnv | None = None
    server: ServerProc | None = None
    try:
        if args.scenario == "state-workflow":
            # Back up the real config/state and seed the temp tree BEFORE
            # spawning: the server reads config.yaml at tool-call time.
            env = StateWorkflowEnv()
            env.setup()
        server = ServerProc(args.cmd)
        _ok("spawn", f"launched pid {server.proc.pid}: {' '.join(args.cmd)}")
        run_handshake(server, deadline, args.expect_tools, args.call_tool)
        if env is not None:
            run_state_workflow(server, deadline, env)
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
        # Order matters: the server must be dead before the backups go back,
        # so it cannot rewrite state.json after the restore. kill_tree does
        # not block, so reap briefly (no-op if it already exited cleanly).
        if server is not None:
            server.kill_tree()
            server.wait(timeout=5.0)
        if env is not None:
            env.teardown()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
