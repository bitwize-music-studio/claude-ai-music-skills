#!/usr/bin/env python3
"""Check startup/resume through Codex from an unrelated music-project cwd.

HOME and CODEX_HOME are temporary. Only synthetic config, albums, and session
state are used. The default probe calls MCP through app-server without a model.
--model-check additionally exercises the four installed skills with real model
turns, using a temporary copy of existing Codex authentication when available.
It consumes model usage and is intentionally excluded from CI.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from codex_plugin_discovery_check import (
    EXPECTED_MCP_SERVER,
    EXPECTED_PLUGIN_ID,
    EXPECTED_SKILL_COUNT,
    AppServer,
    ProbeError,
    _canonical_skill_names,
    _check_skills,
    _install_local_plugin,
)

ALBUM = "probe-album"
ARTIST = "probeArtist"
MODEL_TOOLS = (
    "health_check", "get_config", "get_python_command", "get_pending_migrations",
    "get_session", "get_ideas", "get_pending_verifications", "rebuild_state",
    "list_albums", "find_album", "get_album_progress", "list_tracks",
    "list_skills", "get_skill", "update_session",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def initialize(app: AppServer) -> None:
    app.request(1, "initialize", {
        "clientInfo": {"name": "bitwize-session-probe", "version": "1"},
    })
    app.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})


class SessionProbe:
    def __init__(self, app: AppServer, workspace: Path) -> None:
        self.app = app
        self.request_id = 10
        result = app.request(2, "thread/start", {
            "cwd": str(workspace), "ephemeral": True,
            "approvalPolicy": "never", "sandbox": "read-only",
        })
        self.thread_id = result["thread"]["id"]
        try:
            status = app.request(3, "mcpServerStatus/list", {
                "threadId": self.thread_id, "detail": "full",
            })
        except ProbeError as exc:
            raise ProbeError(f"{exc}; MCP startup stderr: {app.stderr[-2000:]}") from exc
        server = next((s for s in status["data"] if s["name"] == EXPECTED_MCP_SERVER), None)
        require(server is not None, "Plugin MCP missing in foreign workspace")
        require(server["pluginId"] == EXPECTED_PLUGIN_ID, "Wrong MCP owner")

    def call(self, tool: str, **arguments: Any) -> dict[str, Any]:
        self.request_id += 1
        result = self.app.request(self.request_id, "mcpServer/tool/call", {
            "threadId": self.thread_id, "server": EXPECTED_MCP_SERVER,
            "tool": tool, "arguments": arguments,
        })
        require(not result.get("isError"), f"MCP {tool} returned an error")
        blocks = [c["text"] for c in result.get("content", []) if c.get("type") == "text"]
        require(bool(blocks), f"MCP {tool} returned no text")
        payload = json.loads(blocks[0])
        require(isinstance(payload, dict) and "error" not in payload, f"MCP {tool}: {payload}")
        return payload


def make_workspace(home: Path) -> tuple[Path, list[Path]]:
    workspace = home / "unrelated music project"
    workspace.mkdir()
    content = home / "creative content"
    config = {
        "artist": {"name": ARTIST},
        "paths": {
            "content_root": str(content), "audio_root": str(home / "audio"),
            "documents_root": str(home / "documents"),
            "overrides": str(content / "overrides"),
        },
        "generation": {"service": "suno"},
    }
    # JSON is valid YAML, keeping this host probe independent of Python packages.
    config_file = home / ".bitwize-music" / "config.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    album = content / "artists" / ARTIST / "albums" / "pop" / ALBUM
    tracks = album / "tracks"
    tracks.mkdir(parents=True)
    readme = album / "README.md"
    readme.write_text(
        '---\ntitle: "Probe Album"\n---\n\n# Probe Album\n\n'
        '## Album Details\n\n| Attribute | Detail |\n|---|---|\n'
        '| **Status** | Research Complete |\n| **Artist** | probeArtist |\n',
        encoding="utf-8",
    )
    files = [readme]
    for number, status, verified in [(1, "Sources Pending", "Pending"), (2, "Not Started", "N/A")]:
        track = tracks / f"{number:02d}-probe.md"
        track.write_text(
            f'---\ntitle: "Probe {number}"\ntrack_number: {number}\n---\n\n'
            f'# Probe {number}\n\n## Track Details\n\n| Attribute | Detail |\n|---|---|\n'
            f'| **Status** | {status} |\n| **Sources Verified** | {verified} |\n',
            encoding="utf-8",
        )
        files.append(track)
    return workspace, files


def check_workflow(probe: SessionProbe, home: Path) -> None:
    rebuilt = probe.call("rebuild_state")
    require(rebuilt["albums"] == 1 and rebuilt["tracks"] == 2, "Wrong fixture state")
    config = probe.call("get_config")["config"]
    require(config["artist_name"] == ARTIST, "Artist casing was lost")
    require(Path(config["content_root"]) == home / "creative content", "Wrong content root")
    health = probe.call("health_check", runtime="codex")
    require(health["status"] != "fail", f"Startup health failed: {health}")
    require(health["skills"]["source_count"] == EXPECTED_SKILL_COUNT, "Wrong source skill count")
    require(health["skills"]["status"] == "not_checked", "Overclaimed host registration")
    require("fix_message" not in health["skills"], "Codex was given a Claude cache repair")
    require(probe.call("get_pending_migrations")["count"] == 0, "Fresh state has pending migrations")
    album = probe.call("find_album", name="Probe Album")
    require(album.get("found") and album["slug"] == ALBUM, "Album lookup failed")
    progress = probe.call("get_album_progress", album_slug=ALBUM)
    require(progress["track_count"] == 2 and progress["sources_pending"] == 1, "Wrong progress")
    require(progress["phase"] == "Source Verification", f"Wrong phase: {progress['phase']}")
    tracks = probe.call("list_tracks", album_slug=ALBUM)
    require(tracks["track_count"] == 2, "Wrong track count")
    require(probe.call("get_pending_verifications")["total_pending_tracks"] == 1, "Source gate lost")
    updated = probe.call("update_session", album=ALBUM, phase=progress["phase"])
    require(updated["session"]["last_album"] == ALBUM, "Session update failed")
    session = probe.call("get_session")["session"]
    require(session["last_phase"] == "Source Verification", "Session phase was lost")
    saved = json.loads((home / ".bitwize-music/cache/state.json").read_text(encoding="utf-8"))
    require(saved["session"]["last_album"] == ALBUM, "Session was not persisted")


def check_model_turn(events: list[dict[str, Any]], *, resume: bool) -> int:
    """Require each turn to supply its own workflow evidence."""
    calls = [e["item"] for e in events if e.get("type") == "item.completed"
             and e.get("item", {}).get("type") == "mcp_tool_call"]
    failures = [{"tool": c.get("tool"), "status": c.get("status"), "error": c.get("error")}
                for c in calls if c.get("status") == "failed" or c.get("error")]
    require(not failures, f"Model workflow included failed MCP calls: {failures}")
    if not resume:
        require(any(c.get("tool") == "health_check" and c.get("arguments", {}).get("runtime") == "codex"
                    for c in calls), "Startup did not select Codex health diagnostics")
        return len(calls)

    tools = {c.get("tool") for c in calls}
    messages = [e["item"].get("text", "") for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "agent_message"]
    answer = "\n".join(messages)
    require({"get_session", "find_album", "get_album_progress", "list_tracks", "update_session"} <= tools,
            f"Resume missed workflow tools: {sorted(tools)}; answer: {answer[-2000:]}")
    require(any(c.get("tool") == "update_session"
                and c.get("arguments", {}).get("album") == ALBUM
                and c.get("arguments", {}).get("phase") == "Source Verification"
                and not c.get("arguments", {}).get("clear", False)
                for c in calls), "Resume did not update the expected album and phase")
    require("Probe Album" in answer and "verify-sources" in answer, "Resume missed album/source gate")
    require("$bitwize-music:verify-sources" in answer, "Resume used the wrong invocation syntax")
    return len(calls)


def read_saved_session(home: Path) -> dict[str, Any]:
    state = json.loads((home / ".bitwize-music/cache/state.json").read_text(encoding="utf-8"))
    session = state["session"]
    require(isinstance(session, dict), "Saved session is not an object")
    return session


def check_model(codex: str, workspace: Path, env: dict[str, str], auth_home: Path) -> None:
    """Exercise real skill loading and inspect structured tool events."""
    auth = auth_home / "auth.json"
    if auth.is_file():
        target = Path(env["CODEX_HOME"]) / "auth.json"
        shutil.copy2(auth, target)
        target.chmod(0o600)
    prompts = [(
        "This is an isolated synthetic music workspace. In order, use "
        "$bitwize-music:setup to check existing dependencies (do not install anything), "
        "$bitwize-music:configure show to inspect current settings, "
        "then $bitwize-music:session-start. Use the installed canonical instructions. "
        "Report actual startup state. Do not generate music or edit album/track files."
    ), (
        "Use $bitwize-music:resume without an album argument in this synthetic workspace. "
        "Follow the installed resume instructions, report actual album progress and "
        "exactly one next action using Codex skill syntax. Preserve the source "
        "verification gate. Do not generate music or edit album/track files. "
        "Complete the resume skill's session-context update."
    )]
    call_count = 0
    # The never policy makes unapproved MCP calls fail. Preapprove only fixture
    # queries/session updates, in this invocation's isolated plugin config.
    tool_policy = []
    for tool in MODEL_TOOLS:
        # CLI dotted keys are literal; TOML table-name quotes become part of
        # the key and would silently apply policy to a different plugin.
        key = (f"plugins.{EXPECTED_PLUGIN_ID}.mcp_servers."
               f"{EXPECTED_MCP_SERVER}.tools.{tool}.approval_mode")
        tool_policy.extend(["-c", f'{key}="approve"'])
    for number, prompt in enumerate(prompts, 1):
        resume = number == 2
        previous_session = read_saved_session(Path(env["HOME"])) if resume else None
        command = (
            [codex, "exec", "--json", "--ephemeral", "--skip-git-repo-check",
             "--sandbox", "workspace-write", "--add-dir", env["HOME"],
             "-c", 'approval_policy="never"', *tool_policy, prompt]
        )
        with subprocess.Popen(
            command, cwd=workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", start_new_session=sys.platform != "win32",
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=600)
            finally:
                # Reap MCP descendants as well, including after a timeout.
                if sys.platform != "win32":
                    with contextlib.suppress(OSError):
                        os.killpg(process.pid, signal.SIGKILL)
                elif process.poll() is None:
                    process.kill()
                process.wait()
        require(process.returncode == 0, f"Model probe failed (exit {process.returncode}): {stderr[-2000:]}")
        events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        call_count += check_model_turn(events, resume=resume)
        if resume:
            saved = read_saved_session(Path(env["HOME"]))
            require(saved.get("last_album") == ALBUM and saved.get("last_phase") == "Source Verification",
                    "Resume persisted the wrong album or phase")
            require(saved.get("updated_at") and saved["updated_at"] != previous_session.get("updated_at"),
                    "Resume session update was not persisted")
        print(f"Model workflow: phase {number}/{len(prompts)} completed", flush=True)
    print(f"Model workflow: {call_count} MCP calls; resume recommendation and saved session verified", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--venv", type=Path, default=Path.home() / ".bitwize-music/venv")
    parser.add_argument("--model-check", action="store_true", help="Start real model turns (uses account usage)")
    args = parser.parse_args()
    root = args.root.resolve()
    codex = shutil.which(args.codex)
    if codex is None or not args.venv.is_dir():
        print("A Codex executable and an installed dependency venv are required", file=sys.stderr)
        return 2
    original_auth_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    try:
        with tempfile.TemporaryDirectory(prefix="bitwize-session-", ignore_cleanup_errors=True) as tmp:
            home = Path(tmp).resolve()
            workspace, files = make_workspace(home)
            originals = {p: p.read_bytes() for p in files}
            (home / ".bitwize-music/venv").symlink_to(args.venv.resolve(), target_is_directory=True)
            env = os.environ.copy()
            env.update(HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / "codex"))
            Path(env["CODEX_HOME"]).mkdir()
            env.pop("CLAUDE_PLUGIN_ROOT", None)
            env.pop("PLUGIN_ROOT", None)
            version = _install_local_plugin(codex, root=root, env=env)
            app = AppServer(codex, root=workspace, env=env)
            try:
                initialize(app)
                _check_skills(app, root=workspace, expected_names=_canonical_skill_names(root))
                check_workflow(SessionProbe(app, workspace), home)
            finally:
                app.close()
            if args.model_check:
                try:
                    check_model(codex, workspace, env, original_auth_home)
                finally:
                    # Remove the credential even if directory teardown races
                    # with a host process writing other plugin files.
                    (Path(env["CODEX_HOME"]) / "auth.json").unlink(missing_ok=True)
            require(all(p.read_bytes() == data for p, data in originals.items()), "Creative fixtures were modified")
            print(f"Plugin {version}: Codex config, health, source gate, and persisted session passed from foreign cwd", flush=True)
        return 0
    except (ProbeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"Codex session/resume failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
