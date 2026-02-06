#!/usr/bin/env python3
"""
Unit tests for config loading utility.

Usage:
    python -m pytest tools/shared/tests/test_config.py -v
"""

import sys
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import yaml
import tools.shared.config as config_module
from tools.shared.config import load_config


class TestLoadConfig:
    """Tests for load_config()."""

    def test_missing_config_returns_none(self, tmp_path):
        """Missing config file returns None when not required."""
        with mock.patch.object(config_module, 'CONFIG_PATH', tmp_path / "nonexistent.yaml"):
            result = load_config()
            assert result is None

    def test_missing_config_returns_fallback(self, tmp_path):
        """Missing config file returns fallback dict."""
        fallback = {'default': True}
        with mock.patch.object(config_module, 'CONFIG_PATH', tmp_path / "nonexistent.yaml"):
            result = load_config(fallback=fallback)
            assert result == fallback

    def test_missing_config_required_exits(self, tmp_path):
        """Missing config file exits when required=True."""
        with mock.patch.object(config_module, 'CONFIG_PATH', tmp_path / "nonexistent.yaml"):
            with pytest.raises(SystemExit):
                load_config(required=True)

    def test_valid_config_loads(self, tmp_path):
        """Valid YAML config file is loaded correctly."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': '/tmp/content'},
        }
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            result = load_config()
            assert result['artist']['name'] == 'testartist'
            assert result['paths']['content_root'] == '/tmp/content'

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        """Empty YAML file returns empty dict."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            result = load_config()
            assert result == {}

    def test_invalid_yaml_returns_fallback(self, tmp_path):
        """Invalid YAML returns fallback."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("{{invalid: yaml: content::")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            result = load_config(fallback={'default': True})
            assert result == {'default': True}

    def test_invalid_yaml_required_exits(self, tmp_path):
        """Invalid YAML exits when required=True."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("{{invalid: yaml: content::")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            with pytest.raises(SystemExit):
                load_config(required=True)

    def test_config_path_is_in_home_dir(self):
        """CONFIG_PATH points to ~/.bitwize-music/config.yaml."""
        expected = Path.home() / ".bitwize-music" / "config.yaml"
        assert config_module.CONFIG_PATH == expected


class TestLoadConfigYamlMissing:
    """Tests for config loading when PyYAML is not available."""

    def test_no_yaml_returns_fallback(self, tmp_path):
        """When yaml module is None, returns fallback."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("artist:\n  name: test\n")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            with mock.patch.object(config_module, 'yaml', None):
                result = load_config(fallback={'default': True})
                assert result == {'default': True}
