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
        assert config_example.exists(), "Required file missing: config/config.example.yaml"

        with open(config_example, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None, "config.example.yaml is empty"

    @pytest.mark.parametrize("section", ['artist', 'paths', 'generation'])
    def test_config_required_section(self, config_dir, section):
        config_example = config_dir / "config.example.yaml"
        assert config_example.exists(), "Required file missing: config/config.example.yaml"

        with open(config_example, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert section in data, f"Config missing section: {section}"

    @pytest.mark.parametrize("section,field", [
        ('artist', 'name'),
        ('paths', 'content_root'),
        ('paths', 'audio_root'),
    ])
    def test_config_required_field(self, config_dir, section, field):
        config_example = config_dir / "config.example.yaml"
        assert config_example.exists(), "Required file missing: config/config.example.yaml"

        with open(config_example, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert section in data and field in data.get(section, {}), (
            f"Config missing: {section}.{field}"
        )


class TestConfigDocs:
    """Config documentation must exist."""

    def test_config_readme_exists(self, config_dir):
        assert (config_dir / "README.md").exists(), "config/README.md missing"

    def test_example_settings_have_reference_entries(self, config_dir):
        def leaf_keys(settings, prefix=""):
            for key, value in settings.items():
                name = f"{prefix}{key}"
                if isinstance(value, dict):
                    yield from leaf_keys(value, f"{name}.")
                else:
                    yield name

        example = yaml.safe_load((config_dir / "config.example.yaml").read_text(encoding="utf-8"))
        readme = (config_dir / "README.md").read_text(encoding="utf-8")
        _, _, settings = readme.partition("## Settings Reference\n")
        reference, _, _ = settings.partition("\n## ")
        missing = [key for key in leaf_keys(example) if f"| `{key}` |" not in reference]

        assert not missing, f"Undocumented example settings: {', '.join(missing)}"

    def test_config_path_in_plugin_rules(self, claude_md_content):
        assert '~/.bitwize-music/config.yaml' in claude_md_content, (
            "reference/plugin-rules.md should reference ~/.bitwize-music/config.yaml"
        )
