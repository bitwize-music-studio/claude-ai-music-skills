"""Contract tests for the additive Codex plugin manifest."""

import json

import pytest

pytestmark = pytest.mark.plugin

# Servers deliberately left out of the Codex manifest. Keep this empty unless a
# server genuinely cannot run under Codex, and record why next to its name.
CLAUDE_ONLY_MCP_SERVERS: frozenset[str] = frozenset()


class TestCodexPluginManifest:
    """The Codex adapter must point at the canonical upstream components."""

    def test_manifest_exists_and_is_valid(self, project_root):
        manifest_path = project_root / ".codex-plugin" / "plugin.json"
        assert manifest_path.exists(), "Required file missing: .codex-plugin/plugin.json"
        with manifest_path.open(encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["name"] == "bitwize-music"
        assert manifest["version"]
        assert manifest["description"]
        assert manifest["skills"] == "./skills/"
        servers = manifest["mcpServers"]
        assert isinstance(servers, dict)
        server = servers["bitwize-music-mcp"]
        assert server["type"] == "stdio"
        assert server["command"] == "./servers/bitwize-music-server/mcp-launch"
        assert server["cwd"] == "."

    def test_manifest_identity_and_version_match_claude_manifest(self, project_root):
        with (project_root / ".claude-plugin" / "plugin.json").open(encoding="utf-8") as f:
            claude_manifest = json.load(f)
        with (project_root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            codex_manifest = json.load(f)

        assert codex_manifest["name"] == claude_manifest["name"]
        assert codex_manifest["version"] == claude_manifest["version"]

    def test_manifest_has_required_codex_interface(self, project_root):
        with (project_root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            interface = json.load(f)["interface"]

        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "capabilities",
            "websiteURL",
            "defaultPrompt",
            "brandColor",
        ):
            assert interface.get(field), f"Codex interface missing {field}"
        assert len(interface["defaultPrompt"]) <= 3
        assert all(len(prompt) <= 128 for prompt in interface["defaultPrompt"])

    def test_all_canonical_skills_are_present(self, skills_dir, all_skill_frontmatter):
        # One entry per skill directory (with `_error` for a missing SKILL.md),
        # so completeness needs no hard-coded count that every new skill breaks.
        assert all_skill_frontmatter
        missing = [
            skill_dir.name
            for skill_dir in sorted(skills_dir.iterdir())
            if skill_dir.is_dir() and not (skill_dir / "SKILL.md").is_file()
        ]
        assert not missing, f"Canonical skills missing SKILL.md: {missing}"
        assert all("_error" not in frontmatter for frontmatter in all_skill_frontmatter.values())

    def test_claude_mcp_config_uses_plugin_root_interpolation(self, project_root):
        with (project_root / ".mcp.json").open(encoding="utf-8") as f:
            config = json.load(f)

        server = config["mcpServers"]["bitwize-music-mcp"]
        assert server["type"] == "stdio"
        command = server["command"]
        assert command == (
            "${CLAUDE_PLUGIN_ROOT}/servers/bitwize-music-server/mcp-launch"
        )
        assert "cwd" not in server
        launcher = project_root / "servers" / "bitwize-music-server" / "mcp-launch"
        assert launcher.is_file()

    def test_codex_mcp_config_uses_plugin_relative_launcher(self, project_root):
        with (project_root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            server = json.load(f)["mcpServers"]["bitwize-music-mcp"]

        command = server["command"]
        assert command == "./servers/bitwize-music-server/mcp-launch"
        assert server["cwd"] == "."
        assert "${" not in command
        launcher = project_root / command.removeprefix("./")
        assert launcher.is_file()

    def test_codex_mcp_servers_mirror_claude_mcp_json(self, project_root):
        """The MCP spawn is defined twice on purpose; this keeps the copies in step.

        Claude needs ``${CLAUDE_PLUGIN_ROOT}`` (it resolves a relative command
        against the session cwd); Codex expands no variables, so it needs a
        relative ``./`` command plus ``"cwd": "."``, which it joins onto the plugin
        root. So every server Claude launches must also be declared for Codex,
        with the same launcher, arguments and environment.
        """
        with (project_root / ".mcp.json").open(encoding="utf-8") as f:
            claude_servers = json.load(f)["mcpServers"]
        with (project_root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            codex_servers = json.load(f)["mcpServers"]

        assert set(codex_servers) == set(claude_servers) - CLAUDE_ONLY_MCP_SERVERS
        prefix = "${CLAUDE_PLUGIN_ROOT}/"
        for name, codex in codex_servers.items():
            claude = claude_servers[name]
            assert claude["command"].startswith(prefix), name
            assert codex["command"] == "./" + claude["command"].removeprefix(prefix), name
            # Without it the relative command only resolves when Codex happens to
            # run from the plugin root; from a project directory it is ENOENT.
            assert codex.get("cwd") == ".", name
            assert codex.get("type") == claude.get("type"), name
            assert codex.get("args", []) == claude.get("args", []), name
            assert codex.get("env", {}) == claude.get("env", {}), name

    def test_codex_mcp_timeout_covers_long_mastering_runs(self, project_root):
        """Codex cuts a tool call off at 300 s unless the server sets a timeout.

        master_album documents 3-5 min per track, plus 10-12 min per ADM retry
        cycle. At the default, a two-track album times out while the server keeps
        writing masters, and a retry can start a second run on the same album.
        """
        with (project_root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            server = json.load(f)["mcpServers"]["bitwize-music-mcp"]

        assert server.get("tool_timeout_sec", 0) >= 4 * 60 * 60

    def test_codex_manifest_opts_out_of_claude_hooks(self, project_root):
        """Without a ``hooks`` key Codex falls back to the Claude-format hooks.json.

        Every Codex user would then be asked to trust two PostToolUse hooks that
        cannot work there: Codex edit payloads carry no ``file_path``.
        """
        with (project_root / ".codex-plugin" / "plugin.json").open(encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest.get("hooks") == {}
