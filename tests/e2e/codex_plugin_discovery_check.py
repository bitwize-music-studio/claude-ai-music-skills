#!/usr/bin/env python3
"""Exercise the local plugin through the Codex app-server.

The check uses a temporary ``CODEX_HOME`` so a developer's installed plugins
cannot shadow the checkout under test.  It installs the local plugin into that
isolated home, asks Codex to enumerate the skills, verifies the MCP server is
attributed to the same plugin, and calls ``health_check`` through Codex's MCP
bridge.  No model turn is started and no user configuration is changed.

This is deliberately stdlib-only.  The CI job installs the pinned Codex CLI;
the script itself only needs the CLI and the Python standard library.

Usage:
    python tests/e2e/codex_plugin_discovery_check.py [--root PATH]
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

EXPECTED_NAME = "bitwize-music"
EXPECTED_MARKETPLACE = "bitwize-music"
EXPECTED_PLUGIN_ID = f"{EXPECTED_NAME}@{EXPECTED_MARKETPLACE}"
EXPECTED_MCP_SERVER = "bitwize-music-mcp"
EXPECTED_TOOL = "health_check"
EXPECTED_SKILL_COUNT = 53

CLI_TIMEOUT_SECONDS = 60
APP_SERVER_TIMEOUT_SECONDS = 30
APP_SERVER_CLOSE_SECONDS = 15


class ProbeError(RuntimeError):
    """A user-facing failure from the Codex host probe."""


def _tail(value: str, limit: int = 4000) -> str:
    """Keep diagnostics bounded when a CLI emits a large response."""

    value = value.strip()
    return value if len(value) <= limit else value[-limit:]


def _run_cli(
    codex: str,
    args: list[str],
    *,
    root: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run a Codex CLI command and convert spawn/time failures to ProbeError."""

    try:
        return subprocess.run(
            [codex, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=root,
            env=env,
            timeout=CLI_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(f"Codex CLI command failed: {args!r}: {exc}") from exc


def _json_stdout(result: subprocess.CompletedProcess[str], description: str) -> dict[str, Any]:
    """Parse a successful Codex JSON response with useful diagnostics."""

    if result.returncode != 0:
        detail = _tail(result.stderr or result.stdout)
        raise ProbeError(f"{description} failed ({result.returncode}): {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(
            f"{description} returned invalid JSON: {exc}; output: {_tail(result.stdout)}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProbeError(f"{description} returned a non-object JSON payload")
    return payload


class AppServer:
    """Small line-framed JSON-RPC client for ``codex app-server``.

    The app-server emits notifications while requests are being handled, so a
    reader thread drains stdout and stderr continuously.  This also works on
    Windows, where ``select`` cannot wait on anonymous pipe handles.
    """

    def __init__(self, codex: str, *, root: Path, env: dict[str, str]) -> None:
        self._stdout: queue.Queue[str | None] = queue.Queue()
        self._stderr_tail: deque[str] = deque(maxlen=100)
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
            "cwd": root,
            "env": env,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        try:
            self._process = subprocess.Popen([codex, "app-server"], **popen_kwargs)
        except OSError as exc:
            raise ProbeError(f"Could not start Codex app-server: {exc}") from exc

        assert self._process.stdin is not None
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        self._stdin = self._process.stdin
        self._stdout_thread = threading.Thread(
            target=self._pump_stdout, name="codex-app-server-stdout", daemon=True
        )
        self._stderr_thread = threading.Thread(
            target=self._pump_stderr, name="codex-app-server-stderr", daemon=True
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _pump_stdout(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            self._stdout.put(line)
        self._stdout.put(None)

    def _pump_stderr(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr_tail.append(line.rstrip("\r\n"))

    def send(self, message: dict[str, Any]) -> None:
        try:
            self._stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self._stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise ProbeError(
                f"Codex app-server closed stdin while sending {message.get('method')!r}: {exc}"
            ) from exc

    def request(self, request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send one JSON-RPC request and return its result object."""

        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + APP_SERVER_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError(f"Timed out waiting for Codex app-server method {method!r}")
            try:
                line = self._stdout.get(timeout=remaining)
            except queue.Empty as exc:
                raise ProbeError(
                    f"Timed out waiting for Codex app-server method {method!r}"
                ) from exc
            if line is None:
                raise ProbeError(
                    f"Codex app-server exited before responding to {method!r}; "
                    f"stderr: {_tail(self.stderr)}"
                )
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProbeError(
                    f"Codex app-server emitted non-JSON stdout during {method!r}: "
                    f"{line.strip()!r} ({exc})"
                ) from exc
            if not isinstance(message, dict):
                raise ProbeError(
                    f"Codex app-server emitted a non-object message during {method!r}: {message!r}"
                )
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise ProbeError(
                    f"Codex app-server method {method!r} failed: {message['error']}"
                )
            result = message.get("result")
            if not isinstance(result, dict):
                raise ProbeError(
                    f"Codex app-server method {method!r} returned no result object: {message!r}"
                )
            return result

    @property
    def stderr(self) -> str:
        return "\n".join(self._stderr_tail)

    def close(self) -> None:
        """Close the app-server and escalate only if it ignores EOF."""

        with contextlib.suppress(OSError):
            self._stdin.close()
        try:
            self._process.wait(timeout=APP_SERVER_CLOSE_SECONDS)
        except subprocess.TimeoutExpired:
            self._signal_process_group(signal.SIGTERM)
            try:
                self._process.wait(timeout=APP_SERVER_CLOSE_SECONDS)
            except subprocess.TimeoutExpired:
                self._signal_process_group(signal.SIGKILL)
                self._process.wait(timeout=APP_SERVER_CLOSE_SECONDS)
        # MCP children can outlive the app-server and keep writing under
        # CODEX_HOME/plugins, which then fails TemporaryDirectory cleanup.
        self._signal_process_group(signal.SIGKILL)
        self._stdout_thread.join(timeout=1)
        self._stderr_thread.join(timeout=1)

    def _signal_process_group(self, posix_signal: int) -> None:
        if sys.platform == "win32":
            with contextlib.suppress(OSError):
                if posix_signal == signal.SIGTERM:
                    self._process.terminate()
                else:
                    self._process.kill()
            return
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(self._process.pid, posix_signal)


def _canonical_skill_names(root: Path) -> set[str]:
    """Return the expected Codex names from the one canonical skills tree."""

    skills_root = root / "skills"
    if not skills_root.is_dir():
        raise ProbeError(f"Canonical skills directory is missing: {skills_root}")
    skill_dirs = sorted(
        path for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    missing = [path.name for path in skill_dirs if not (path / "SKILL.md").is_file()]
    if missing or len(skill_dirs) != EXPECTED_SKILL_COUNT:
        raise ProbeError(
            f"Canonical skill tree is invalid: {len(skill_dirs)} directories, missing {missing}"
        )
    return {f"{EXPECTED_NAME}:{path.name}" for path in skill_dirs}


def _install_local_plugin(codex: str, *, root: Path, env: dict[str, str]) -> str:
    """Register and install only the current checkout in the isolated home."""

    marketplace = _json_stdout(
        _run_cli(
            codex,
            ["plugin", "marketplace", "add", str(root), "--json"],
            root=root,
            env=env,
        ),
        "Codex marketplace add",
    )
    marketplace_name = marketplace.get("marketplaceName")
    if marketplace_name != EXPECTED_MARKETPLACE:
        raise ProbeError(
            f"Codex registered unexpected marketplace {marketplace_name!r}; "
            f"expected {EXPECTED_MARKETPLACE!r}"
        )

    manifest_path = root / ".codex-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProbeError(f"Could not read Codex plugin manifest {manifest_path}: {exc}") from exc
    expected_version = manifest.get("version")
    if not isinstance(expected_version, str) or not expected_version:
        raise ProbeError(f"Codex plugin manifest has no valid version: {manifest_path}")

    installed = _json_stdout(
        _run_cli(
            codex,
            ["plugin", "add", EXPECTED_PLUGIN_ID, "--json"],
            root=root,
            env=env,
        ),
        "Codex plugin add",
    )
    if installed.get("pluginId") != EXPECTED_PLUGIN_ID:
        raise ProbeError(
            f"Codex installed unexpected plugin {installed.get('pluginId')!r}; "
            f"expected {EXPECTED_PLUGIN_ID!r}"
        )
    if installed.get("version") != expected_version:
        raise ProbeError(
            f"Codex installed version {installed.get('version')!r}; expected {expected_version!r}"
        )
    return str(expected_version)


def _path_for_cwd(value: Any) -> Path | None:
    if not isinstance(value, str):
        return None
    try:
        return Path(value).resolve()
    except OSError:
        return None


def _check_skills(app: AppServer, *, root: Path, expected_names: set[str]) -> int:
    result = app.request(
        3,
        "skills/list",
        {"cwds": [str(root)], "forceReload": True},
    )
    entries = result.get("data")
    if not isinstance(entries, list):
        raise ProbeError(f"Codex skills/list returned invalid data: {result!r}")

    entry = next(
        (
            candidate
            for candidate in entries
            if isinstance(candidate, dict) and _path_for_cwd(candidate.get("cwd")) == root
        ),
        None,
    )
    if entry is None:
        raise ProbeError(f"Codex skills/list returned no entry for checkout {root}")
    errors = entry.get("errors")
    if errors:
        raise ProbeError(f"Codex reported skill loading errors: {errors}")
    skills = entry.get("skills")
    if not isinstance(skills, list):
        raise ProbeError(f"Codex skills/list returned invalid skills data: {entry!r}")

    prefix = f"{EXPECTED_NAME}:"
    target_skills = [
        skill
        for skill in skills
        if isinstance(skill, dict) and str(skill.get("name", "")).startswith(prefix)
    ]
    actual_names = {skill["name"] for skill in target_skills}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ProbeError(f"Codex skill set mismatch: missing={missing}, extra={extra}")

    invalid = []
    for skill in target_skills:
        path_value = skill.get("path")
        path = Path(path_value) if isinstance(path_value, str) else None
        if not skill.get("enabled") or path is None or not path.is_file():
            invalid.append(
                {"name": skill.get("name"), "enabled": skill.get("enabled"), "path": path_value}
            )
    if invalid:
        raise ProbeError(f"Codex returned unloaded skill metadata: {invalid}")
    return len(target_skills)


def _check_mcp(app: AppServer, *, root: Path) -> None:
    thread_result = app.request(
        2,
        "thread/start",
        {
            "cwd": str(root),
            "ephemeral": True,
            "approvalPolicy": "never",
            "sandbox": "read-only",
        },
    )
    thread = thread_result.get("thread")
    thread_id = thread.get("id") if isinstance(thread, dict) else None
    if not isinstance(thread_id, str) or not thread_id:
        raise ProbeError(f"Codex thread/start returned no thread id: {thread_result!r}")

    status = app.request(
        4,
        "mcpServerStatus/list",
        {"detail": "full", "threadId": thread_id},
    )
    servers = status.get("data")
    if not isinstance(servers, list):
        raise ProbeError(f"Codex MCP status returned invalid data: {status!r}")
    server = next(
        (
            candidate
            for candidate in servers
            if isinstance(candidate, dict) and candidate.get("name") == EXPECTED_MCP_SERVER
        ),
        None,
    )
    if server is None:
        raise ProbeError(f"Codex did not discover MCP server {EXPECTED_MCP_SERVER!r}")
    if server.get("pluginId") != EXPECTED_PLUGIN_ID:
        raise ProbeError(
            f"MCP server {EXPECTED_MCP_SERVER!r} belongs to {server.get('pluginId')!r}, "
            f"not {EXPECTED_PLUGIN_ID!r}"
        )
    tools = server.get("tools")
    if not isinstance(tools, dict) or EXPECTED_TOOL not in tools:
        raise ProbeError(f"MCP server {EXPECTED_MCP_SERVER!r} has no {EXPECTED_TOOL!r} tool")

    call = app.request(
        5,
        "mcpServer/tool/call",
        {
            "server": EXPECTED_MCP_SERVER,
            "threadId": thread_id,
            "tool": EXPECTED_TOOL,
            "arguments": {},
        },
    )
    if call.get("isError") is True:
        raise ProbeError(f"Codex MCP tool call returned an error: {call!r}")
    content = call.get("content")
    if not isinstance(content, list):
        raise ProbeError(f"Codex MCP tool call returned no content: {call!r}")
    text_payload: str | None = None
    for block in content:
        if not isinstance(block, dict):
            continue
        block_text = block.get("text")
        if block.get("type") == "text" and isinstance(block_text, str):
            text_payload = block_text
            break
    if text_payload is None:
        raise ProbeError(f"Codex MCP tool call returned no text payload: {call!r}")
    try:
        health = json.loads(text_payload)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"health_check returned invalid JSON: {exc}") from exc
    health_skills = health.get("skills") if isinstance(health, dict) else None
    source_count = health_skills.get("source_count") if isinstance(health_skills, dict) else None
    if source_count != EXPECTED_SKILL_COUNT:
        raise ProbeError(
            f"health_check reported source_count={source_count!r}; "
            f"expected {EXPECTED_SKILL_COUNT}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository checkout containing .codex-plugin/plugin.json",
    )
    parser.add_argument(
        "--codex",
        default="codex",
        help="Codex executable or PATH name (default: codex)",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    codex = shutil.which(args.codex) or (
        args.codex if Path(args.codex).is_file() else None
    )
    if codex is None:
        print("codex CLI not found", file=sys.stderr)
        return 2
    if not (root / ".codex-plugin" / "plugin.json").is_file():
        print(f"Codex plugin manifest not found under {root}", file=sys.stderr)
        return 1

    try:
        expected_names = _canonical_skill_names(root)
        # ignore_cleanup_errors: Codex may still be writing under plugins/ after
        # app-server EOF, which otherwise turns a passing probe into
        # OSError: [Errno 39] Directory not empty.
        with tempfile.TemporaryDirectory(
            prefix="bitwize-music-codex-",
            ignore_cleanup_errors=True,
        ) as codex_home:
            env = os.environ.copy()
            env["CODEX_HOME"] = codex_home
            version = _install_local_plugin(codex, root=root, env=env)
            app = AppServer(codex, root=root, env=env)
            try:
                app.request(
                    1,
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "bitwize-music-codex-e2e",
                            "title": "bitwize-music Codex E2E",
                            "version": "1",
                        }
                    },
                )
                app.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
                loaded_count = _check_skills(app, root=root, expected_names=expected_names)
                _check_mcp(app, root=root)
            finally:
                app.close()
            print(
                f"Codex {version} loaded {loaded_count} canonical skills and called "
                f"{EXPECTED_MCP_SERVER}/{EXPECTED_TOOL} successfully",
                flush=True,
            )
        return 0
    except ProbeError as exc:
        print(f"Codex plugin E2E failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
