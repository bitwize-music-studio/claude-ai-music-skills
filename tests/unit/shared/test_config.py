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
        with open(config_path, 'w', encoding='utf-8') as f:
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


class TestLoadConfigNonMapping:
    """load_config() rejects valid YAML whose top level is not a mapping (#389)."""

    def test_top_level_list_returns_fallback_with_error(self, tmp_path, caplog):
        """Top-level YAML list returns fallback and logs an error naming path and type."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("- foo\n- bar\n")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            with caplog.at_level("ERROR", logger="tools.shared.config"):
                result = load_config(fallback={'default': True})
        assert result == {'default': True}
        assert any(
            str(config_path) in r.message and "list" in r.message
            for r in caplog.records
        )

    def test_top_level_scalar_returns_fallback(self, tmp_path):
        """Top-level YAML scalar returns fallback."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("42\n")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            result = load_config(fallback={'default': True})
            assert result == {'default': True}

    def test_non_mapping_returns_none_without_fallback(self, tmp_path):
        """Non-mapping YAML returns None when no fallback is given."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("just a string\n")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            assert load_config() is None

    def test_non_mapping_required_exits(self, tmp_path):
        """Non-mapping YAML exits when required=True."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("- foo\n")

        with mock.patch.object(config_module, 'CONFIG_PATH', config_path):
            with pytest.raises(SystemExit):
                load_config(required=True)


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


class TestParseYamlBool:
    """parse_yaml_bool() honors quoted YAML boolean strings (#388)."""

    def test_passes_through_bools(self):
        from tools.shared.config import parse_yaml_bool
        assert parse_yaml_bool(True) is True
        assert parse_yaml_bool(False) is False

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "yes", "Yes", "on", "1", " true "])
    def test_truthy_strings(self, value):
        from tools.shared.config import parse_yaml_bool
        assert parse_yaml_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "no", "No", "off", "0", " false "])
    def test_falsy_strings(self, value):
        from tools.shared.config import parse_yaml_bool
        assert parse_yaml_bool(value) is False

    def test_zero_one_ints(self):
        from tools.shared.config import parse_yaml_bool
        assert parse_yaml_bool(0) is False
        assert parse_yaml_bool(1) is True

    @pytest.mark.parametrize("value", ["maybe", "", "2", "truthy", 2, 2.5, [], {}, None, ["true"]])
    def test_unparseable_values_raise(self, value):
        from tools.shared.config import parse_yaml_bool
        with pytest.raises(ValueError):
            parse_yaml_bool(value)


class TestCoerceYamlBool:
    """coerce_yaml_bool() = parse_yaml_bool with warn-and-default fallback."""

    def test_parses_quoted_strings(self):
        from tools.shared.config import coerce_yaml_bool
        assert coerce_yaml_bool("false", default=True) is False
        assert coerce_yaml_bool("yes", default=False) is True

    def test_bool_passthrough(self):
        from tools.shared.config import coerce_yaml_bool
        assert coerce_yaml_bool(True, default=False) is True
        assert coerce_yaml_bool(False, default=True) is False

    def test_garbage_returns_default_with_warning(self, caplog):
        from tools.shared.config import coerce_yaml_bool
        with caplog.at_level("WARNING", logger="tools.shared.config"):
            assert coerce_yaml_bool("maybe", default=True, context="cloud.enabled") is True
            assert coerce_yaml_bool([], default=False, context="x") is False
        assert any("cloud.enabled" in r.message for r in caplog.records)


class TestParseYamlFloat:
    """parse_yaml_float() is the numeric sibling of parse_yaml_bool (#553).

    Numeric preset/config values were read with a bare `float(...)`, which
    raises on a quoted `"0.5"`-shaped mistake and takes the whole run down
    with a traceback. This helper gives numeric gates the same
    raise-then-warn-and-default contract the boolean gates already have.
    """

    @pytest.mark.parametrize("value", [0, 1, -2, 0.5, -3.5])
    def test_passes_through_real_numbers(self, value):
        from tools.shared.config import parse_yaml_float
        assert parse_yaml_float(value) == float(value)
        assert isinstance(parse_yaml_float(value), float)

    @pytest.mark.parametrize("value", [True, False])
    def test_bools_are_not_numbers(self, value):
        """`isinstance(True, int)` is True in Python — a boolean in a
        numeric slot is a mistake, not a 1.0."""
        from tools.shared.config import parse_yaml_float
        with pytest.raises(ValueError):
            parse_yaml_float(value)

    @pytest.mark.parametrize("value", ["0.5", "0", " 1 ", "abc", "", None, [], {}])
    def test_strings_and_junk_raise(self, value):
        """A quoted number is not silently accepted: an unreadable
        setting must fall back to its documented default, never be
        guessed into effect."""
        from tools.shared.config import parse_yaml_float
        with pytest.raises(ValueError):
            parse_yaml_float(value)

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_raises(self, value):
        from tools.shared.config import parse_yaml_float
        with pytest.raises(ValueError):
            parse_yaml_float(value)


class TestCoerceYamlFloat:
    """coerce_yaml_float() = parse_yaml_float with warn-and-default fallback."""

    def test_numbers_pass_through(self):
        from tools.shared.config import coerce_yaml_float
        assert coerce_yaml_float(0.5, default=0.0) == 0.5
        assert coerce_yaml_float(0, default=1.0) == 0.0

    def test_quoted_number_returns_default_with_warning(self, caplog):
        from tools.shared.config import coerce_yaml_float
        with caplog.at_level("WARNING", logger="tools.shared.config"):
            assert coerce_yaml_float("0.5", default=0.0, context="noise_reduction") == 0.0
        assert any("noise_reduction" in r.message for r in caplog.records)

    def test_garbage_returns_default_with_warning(self, caplog):
        from tools.shared.config import coerce_yaml_float
        with caplog.at_level("WARNING", logger="tools.shared.config"):
            assert coerce_yaml_float([], default=-2.0, context="high_tame_db") == -2.0
        assert any("high_tame_db" in r.message for r in caplog.records)
