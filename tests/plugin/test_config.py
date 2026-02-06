"""Tests for configuration files: config.example.yaml structure and docs."""

import pytest
import yaml

pytestmark = pytest.mark.plugin


class TestConfigExample:
    """config.example.yaml must exist and be valid."""

    def test_config_example_exists(self, config_dir):
        assert (config_dir / "config.example.yaml").exists(), "config.example.yaml missing"

    def test_config_example_valid_yaml(self, config_dir):
        config_example = config_dir / "config.example.yaml"
        if not config_example.exists():
            pytest.skip("config.example.yaml not found")

        with open(config_example) as f:
            data = yaml.safe_load(f)
        assert data is not None, "config.example.yaml is empty"

    @pytest.mark.parametrize("section", ['artist', 'paths', 'generation'])
    def test_config_required_section(self, config_dir, section):
        config_example = config_dir / "config.example.yaml"
        if not config_example.exists():
            pytest.skip("config.example.yaml not found")

        with open(config_example) as f:
            data = yaml.safe_load(f)
        assert section in data, f"Config missing section: {section}"

    @pytest.mark.parametrize("section,field", [
        ('artist', 'name'),
        ('paths', 'content_root'),
        ('paths', 'audio_root'),
    ])
    def test_config_required_field(self, config_dir, section, field):
        config_example = config_dir / "config.example.yaml"
        if not config_example.exists():
            pytest.skip("config.example.yaml not found")

        with open(config_example) as f:
            data = yaml.safe_load(f)
        assert section in data and field in data.get(section, {}), (
            f"Config missing: {section}.{field}"
        )


class TestConfigDocs:
    """Config documentation must exist."""

    def test_config_readme_exists(self, config_dir):
        assert (config_dir / "README.md").exists(), "config/README.md missing"

    def test_config_path_in_claude_md(self, claude_md_content):
        assert '~/.bitwize-music/config.yaml' in claude_md_content, (
            "CLAUDE.md should reference ~/.bitwize-music/config.yaml"
        )
