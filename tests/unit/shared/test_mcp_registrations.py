#!/usr/bin/env python3
"""Unit tests for tools/shared/mcp_registrations.py — where MCP servers are registered.

Every test runs against a fake home directory and a fake project directory, so
the developer's real ~/.claude.json, .mcp.json and Codex config are never read.

Usage:
    python -m pytest tests/unit/shared/test_mcp_registrations.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.shared import mcp_registrations as reg

pytestmark = pytest.mark.unit

HOST = "api.suno.com"
SUNO = "https://api.suno.com/mcp"
HTTP = {"type": "http", "url": SUNO}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A fake home, a fake project as the current directory, and no Claude env vars."""
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(reg, "managed_file", lambda: tmp_path / "managed" / "managed-mcp.json")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.chdir(project)
    return SimpleNamespace(home=home, project=project, tmp=tmp_path)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def claude_json(rig, *, user=None, projects=None) -> None:
    write_json(rig.home / ".claude.json", {"mcpServers": user or {}, "projects": projects or {}})


# ===========================================================================
# Locations
# ===========================================================================


class TestLocations:
    def test_claude_config_file_defaults_to_home(self, rig):
        assert reg.claude_config_file() == rig.home / ".claude.json"

    def test_claude_config_dir_moves_it(self, rig, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(rig.tmp / "elsewhere"))
        assert reg.claude_config_file() == rig.tmp / "elsewhere" / ".claude.json"

    def test_project_dir_is_the_current_directory(self, rig):
        assert reg.project_dir() == Path.cwd()

    def test_project_dir_env_beats_the_current_directory(self, rig, monkeypatch):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(rig.tmp / "other"))
        assert reg.project_dir() == rig.tmp / "other"

    def test_explicit_project_dir_beats_both(self, rig, monkeypatch):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(rig.tmp / "other"))
        assert reg.project_dir(rig.tmp / "given") == rig.tmp / "given"

    def test_codex_config_file(self, rig, monkeypatch):
        assert reg.codex_config_file() == rig.home / ".codex" / "config.toml"
        monkeypatch.setenv("CODEX_HOME", str(rig.tmp / "codex-home"))
        assert reg.codex_config_file() == rig.tmp / "codex-home" / "config.toml"

    @pytest.mark.parametrize("platform, expected", [
        ("darwin", Path("/Library/Application Support/ClaudeCode/managed-mcp.json")),
        ("linux", Path("/etc/claude-code/managed-mcp.json")),
    ])
    def test_managed_file_per_os(self, rig, monkeypatch, platform, expected):
        monkeypatch.undo()  # the rig replaced managed_file; test the real one
        monkeypatch.setattr(reg, "_is_windows", lambda: False)
        monkeypatch.setattr(reg.sys, "platform", platform)
        assert reg.managed_file() == expected

    def test_managed_file_on_windows(self, rig, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(reg, "_is_windows", lambda: True)
        monkeypatch.setenv("PROGRAMDATA", "ProgramDataDir")
        assert reg.managed_file() == Path("ProgramDataDir") / "ClaudeCode" / "managed-mcp.json"


# ===========================================================================
# find_servers
# ===========================================================================


class TestFindServers:
    def test_nothing_configured(self, rig):
        assert reg.find_servers(HOST) == []

    def test_user_scope(self, rig):
        claude_json(rig, user={"suno": HTTP})
        assert reg.find_servers(HOST) == [{"name": "suno", "scope": "user", "url": SUNO}]

    def test_local_scope_for_this_project(self, rig):
        claude_json(rig, projects={str(rig.project): {"mcpServers": {"suno": HTTP}}})
        assert reg.find_servers(HOST) == [{"name": "suno", "scope": "local", "url": SUNO}]

    def test_local_scope_for_another_project_does_not_count(self, rig):
        claude_json(rig, projects={str(rig.tmp / "other-project"): {"mcpServers": {"suno": HTTP}}})
        assert reg.find_servers(HOST) == []

    def test_local_scope_filed_under_the_resolved_path(self, rig, monkeypatch):
        link = rig.tmp / "link-to-project"
        link.symlink_to(rig.project)
        claude_json(rig, projects={str(rig.project.resolve()): {"mcpServers": {"suno": HTTP}}})
        assert reg.find_servers(HOST, project=link)[0]["scope"] == "local"

    def test_project_scope(self, rig):
        write_json(rig.project / ".mcp.json", {"mcpServers": {"suno": HTTP}})
        assert reg.find_servers(HOST) == [{"name": "suno", "scope": "project", "url": SUNO}]

    def test_managed_scope(self, rig):
        write_json(reg.managed_file(), {"mcpServers": {"suno": HTTP}})
        assert reg.find_servers(HOST) == [{"name": "suno", "scope": "managed", "url": SUNO}]

    def test_codex_scope(self, rig):
        codex = rig.home / ".codex" / "config.toml"
        codex.parent.mkdir(parents=True)
        codex.write_text(
            'model = "gpt-5"\n\n[mcp_servers.suno]\nurl = "https://api.suno.com/mcp"\n\n'
            '[mcp_servers.local-tool]\ncommand = "npx"\nargs = ["-y", "some-tool"]\n',
            encoding="utf-8",
        )
        assert reg.find_servers(HOST) == [{"name": "suno", "scope": "codex", "url": SUNO}]

    def test_any_name_matches_by_host(self, rig):
        claude_json(rig, user={"music-api": {"type": "http", "url": "HTTPS://API.SUNO.COM/mcp?x=1"}})
        found = reg.find_servers(HOST)
        assert [s["name"] for s in found] == ["music-api"]
        assert found[0]["url"] == "HTTPS://API.SUNO.COM/mcp?x=1"

    def test_other_hosts_and_stdio_servers_are_ignored(self, rig):
        claude_json(rig, user={
            "suno-lookalike": {"type": "http", "url": "https://api.suno.com.evil.example/mcp"},
            "burp": {"type": "sse", "url": "http://127.0.0.1:9876"},
            "pencil": {"type": "stdio", "command": "/Applications/Pencil.app/mcp"},
            "odd": "not a mapping",
            "no-url": {"type": "http"},
        })
        assert reg.find_servers(HOST) == []

    def test_results_come_in_scope_order(self, rig):
        claude_json(
            rig,
            user={"user-suno": HTTP},
            projects={str(rig.project): {"mcpServers": {"local-suno": HTTP}}},
        )
        write_json(rig.project / ".mcp.json", {"mcpServers": {"project-suno": HTTP}})
        write_json(reg.managed_file(), {"mcpServers": {"managed-suno": HTTP}})
        codex = rig.home / ".codex" / "config.toml"
        codex.parent.mkdir(parents=True)
        codex.write_text('[mcp_servers.codex-suno]\nurl = "https://api.suno.com/mcp"\n', encoding="utf-8")

        assert [(s["scope"], s["name"]) for s in reg.find_servers(HOST)] == [
            ("local", "local-suno"), ("project", "project-suno"), ("user", "user-suno"),
            ("managed", "managed-suno"), ("codex", "codex-suno"),
        ]

    def test_claude_config_dir_is_honoured(self, rig, monkeypatch):
        elsewhere = rig.tmp / "elsewhere"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(elsewhere))
        write_json(elsewhere / ".claude.json", {"mcpServers": {"suno": HTTP}})
        claude_json(rig, user={})  # the default location says nothing
        assert reg.find_servers(HOST)[0]["scope"] == "user"

    def test_project_dir_env_is_used_for_local_and_project_scope(self, rig, monkeypatch):
        other = rig.tmp / "other"
        other.mkdir()
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(other))
        claude_json(rig, projects={str(other): {"mcpServers": {"suno": HTTP}}})
        write_json(other / ".mcp.json", {"mcpServers": {"suno-too": HTTP}})
        assert [s["scope"] for s in reg.find_servers(HOST)] == ["local", "project"]

    def test_malformed_files_are_skipped(self, rig):
        (rig.home / ".claude.json").write_text("{not json", encoding="utf-8")
        (rig.project / ".mcp.json").write_text("[]", encoding="utf-8")  # a list, not a mapping
        write_json(reg.managed_file(), {"mcpServers": "nope"})
        codex = rig.home / ".codex" / "config.toml"
        codex.parent.mkdir(parents=True)
        codex.write_text("this is = = not toml", encoding="utf-8")
        assert reg.find_servers(HOST) == []

    def test_unreadable_file_is_skipped(self, rig, monkeypatch):
        claude_json(rig, user={"suno": HTTP})

        def boom(self, *args, **kwargs):
            raise PermissionError("no")

        monkeypatch.setattr(Path, "read_text", boom)
        assert reg.find_servers(HOST) == []
