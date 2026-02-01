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
from tools.shared.config import load_config, validate_config


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


class TestValidateConfig:
    """Tests for validate_config()."""

    def _valid_config(self):
        return {
            'artist': {'name': 'bitwize'},
            'paths': {
                'content_root': '~/bitwize-music',
                'audio_root': '~/bitwize-music/audio',
            },
        }

    def test_valid_config_returns_empty(self):
        """Valid config produces no errors."""
        assert validate_config(self._valid_config()) == []

    def test_valid_config_with_optional_fields(self):
        """Config with all optional fields is valid."""
        config = self._valid_config()
        config['paths']['documents_root'] = '~/docs'
        config['generation'] = {'service': 'suno'}
        assert validate_config(config) == []

    def test_not_a_dict(self):
        """Non-dict input returns error."""
        errors = validate_config("not a dict")
        assert len(errors) == 1
        assert "not a dict" in errors[0]

    def test_missing_artist_section(self):
        """Missing artist section is an error."""
        config = self._valid_config()
        del config['artist']
        errors = validate_config(config)
        assert any("artist" in e for e in errors)

    def test_empty_artist_name(self):
        """Empty artist.name is an error."""
        config = self._valid_config()
        config['artist']['name'] = '  '
        errors = validate_config(config)
        assert any("artist.name" in e for e in errors)

    def test_missing_paths_section(self):
        """Missing paths section is an error."""
        config = self._valid_config()
        del config['paths']
        errors = validate_config(config)
        assert any("paths" in e for e in errors)

    def test_missing_content_root(self):
        """Missing paths.content_root is an error."""
        config = self._valid_config()
        del config['paths']['content_root']
        errors = validate_config(config)
        assert any("content_root" in e for e in errors)

    def test_missing_audio_root(self):
        """Missing paths.audio_root is an error."""
        config = self._valid_config()
        del config['paths']['audio_root']
        errors = validate_config(config)
        assert any("audio_root" in e for e in errors)

    def test_empty_content_root(self):
        """Empty paths.content_root is an error."""
        config = self._valid_config()
        config['paths']['content_root'] = ''
        errors = validate_config(config)
        assert any("content_root" in e for e in errors)

    def test_optional_documents_root_empty_is_error(self):
        """Empty documents_root (when present) is an error."""
        config = self._valid_config()
        config['paths']['documents_root'] = ''
        errors = validate_config(config)
        assert any("documents_root" in e for e in errors)

    def test_optional_documents_root_absent_is_ok(self):
        """Missing documents_root is fine (optional)."""
        config = self._valid_config()
        assert validate_config(config) == []

    def test_generation_not_dict(self):
        """Non-dict generation section is an error."""
        config = self._valid_config()
        config['generation'] = 'suno'
        errors = validate_config(config)
        assert any("generation" in e for e in errors)

    def test_generation_service_empty(self):
        """Empty generation.service is an error."""
        config = self._valid_config()
        config['generation'] = {'service': ''}
        errors = validate_config(config)
        assert any("generation.service" in e for e in errors)

    def test_generation_service_absent_is_ok(self):
        """Missing generation.service is fine (optional)."""
        config = self._valid_config()
        config['generation'] = {}
        assert validate_config(config) == []

    def test_artist_name_not_string(self):
        """Non-string artist.name is an error."""
        config = self._valid_config()
        config['artist']['name'] = 123
        errors = validate_config(config)
        assert any("artist.name" in e for e in errors)

    def test_multiple_errors_reported(self):
        """Multiple issues produce multiple errors."""
        errors = validate_config({})
        assert len(errors) >= 2  # Missing artist and paths at minimum


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
