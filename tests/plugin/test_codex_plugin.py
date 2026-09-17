"""Contract tests for the additive Codex plugin manifest."""

import json

import pytest

pytestmark = pytest.mark.plugin

EXPECTED_SKILL_COUNT = 53


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
        assert len(all_skill_frontmatter) == EXPECTED_SKILL_COUNT
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
