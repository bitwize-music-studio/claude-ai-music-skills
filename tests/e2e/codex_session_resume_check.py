#!/usr/bin/env python3
"""Check Codex MCP session state from an unrelated music-project cwd.

HOME and CODEX_HOME are temporary. Only synthetic config, albums, and session
state are used. The probe calls MCP through app-server without a model.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from codex_plugin_discovery_check import (
    EXPECTED_MCP_SERVER,
    EXPECTED_PLUGIN_ID,
    AppServer,
    ProbeError,
    _canonical_skill_names,
    _check_skills,
    _install_local_plugin,
    _is_under,
)

if sys.platform == "win32":
    import _winapi

ALBUM = "probe-album"
ARTIST = "probeArtist"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def initialize(app: AppServer) -> None:
    app.request(1, "initialize", {
        "clientInfo": {"name": "bitwize-session-probe", "version": "1"},
    })
    app.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})


class SessionProbe:
    def __init__(self, app: AppServer, workspace: Path, *, codex_home: Path) -> None:
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
        if server is None:
            raise ProbeError("Plugin MCP missing in foreign workspace")
        require(server["pluginId"] == EXPECTED_PLUGIN_ID, "Wrong MCP owner")
        tools = server.get("tools")
        require(isinstance(tools, dict) and "health_check" in tools,
                f"Plugin MCP did not start: runtimeStatus={server.get('runtimeStatus')!r}, "
                f"toolsError={server.get('toolsError')!r}")
        plugin_root = self.call("get_plugin_version").get("plugin_root")
        require(_is_under(plugin_root, codex_home),
                f"MCP server runs from {plugin_root!r}, not the copy installed under {codex_home}")
        runtime_guide = Path(plugin_root) / "reference" / "runtime-compatibility.md"
        require(runtime_guide.is_file(), f"Installed plugin is missing runtime guide: {runtime_guide}")

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
        if not isinstance(payload, dict) or "error" in payload:
            raise ProbeError(f"MCP {tool}: {payload}")
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


def check_workflow(probe: SessionProbe, home: Path, *, expected_skill_count: int) -> None:
    rebuilt = probe.call("rebuild_state")
    require(rebuilt["albums"] == 1 and rebuilt["tracks"] == 2, "Wrong fixture state")
    config = probe.call("get_config")["config"]
    require(config["artist_name"] == ARTIST, "Artist casing was lost")
    require(Path(config["content_root"]) == home / "creative content", "Wrong content root")
    health = probe.call("health_check", runtime="codex")
    require(health["status"] != "fail", f"Startup health failed: {health}")
    require(health["skills"]["source_count"] == expected_skill_count, "Wrong source skill count")
    require(health["skills"]["status"] == "not_checked", "Overclaimed host registration")
    require("fix_message" not in health["skills"], "Codex was given a Claude cache repair")
    require(probe.call("get_pending_migrations")["count"] == 0, "Fresh state has pending migrations")
    album = probe.call("find_album", name="Probe Album")
    require(bool(album.get("found")) and album["slug"] == ALBUM, "Album lookup failed")
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
    saved = json.loads((home / ".bitwize-music/cache/state.json").read_text(encoding="utf-8"))["session"]
    require(saved["last_album"] == ALBUM and saved["last_phase"] == "Source Verification",
            "Album and phase were not persisted")


def link_venv(source: Path, target: Path) -> None:
    """Reuse dependencies without requiring Windows symlink privileges."""
    source = source.resolve()
    if sys.platform == "win32":
        # Keep '&', '%' and '^' literal instead of passing paths through cmd.
        _winapi.CreateJunction(str(source), str(target))
    else:
        target.symlink_to(source, target_is_directory=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--venv", type=Path, default=Path.home() / ".bitwize-music/venv")
    args = parser.parse_args()
    root = args.root.resolve()
    found = shutil.which(args.codex) or (args.codex if Path(args.codex).is_file() else None)
    if found is None or not args.venv.is_dir():
        print("A Codex executable and an installed dependency venv are required", file=sys.stderr)
        return 2
    codex = os.path.abspath(found)
    try:
        expected_names = _canonical_skill_names(root)
        with tempfile.TemporaryDirectory(prefix="bitwize-session-", ignore_cleanup_errors=True) as tmp:
            home = Path(tmp).resolve()
            workspace, files = make_workspace(home)
            originals = {p: p.read_bytes() for p in files}
            link_venv(args.venv, home / ".bitwize-music/venv")
            env = os.environ.copy()
            env.update(HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / "codex"))
            Path(env["CODEX_HOME"]).mkdir()
            env.pop("CLAUDE_PLUGIN_ROOT", None)
            env.pop("PLUGIN_ROOT", None)
            codex_home = Path(env["CODEX_HOME"])
            version = _install_local_plugin(codex, root=root, cwd=workspace, env=env)
            app = AppServer(codex, cwd=workspace, env=env)
            try:
                initialize(app)
                _check_skills(app, cwd=workspace, codex_home=codex_home, expected_names=expected_names)
                check_workflow(SessionProbe(app, workspace, codex_home=codex_home), home,
                               expected_skill_count=len(expected_names))
            finally:
                app.close()
            require(all(p.read_bytes() == data for p, data in originals.items()), "Creative fixtures were modified")
            print(f"Plugin {version}: Codex config, health, source gate, and persisted session passed from foreign cwd", flush=True)
        return 0
    except (ProbeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"Codex session/resume failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
