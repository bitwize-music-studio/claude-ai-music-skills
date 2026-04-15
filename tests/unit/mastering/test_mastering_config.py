"""Unit tests for tools/mastering/config.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.mastering.config import (
    DEFAULT_MASTERING_CONFIG,
    load_mastering_config,
    resolve_mastering_targets,
)


class TestLoadMasteringConfig:
    def test_returns_defaults_when_config_missing(self):
        with patch("tools.mastering.config.load_config", return_value=None):
            result = load_mastering_config()
        assert result == DEFAULT_MASTERING_CONFIG

    def test_returns_defaults_when_mastering_key_absent(self):
        with patch(
            "tools.mastering.config.load_config",
            return_value={"artist": {"name": "x"}},
        ):
            result = load_mastering_config()
        assert result == DEFAULT_MASTERING_CONFIG

    def test_merges_user_values_over_defaults(self):
        user_config = {
            "mastering": {"delivery_bit_depth": 16, "archival_enabled": True}
        }
        with patch(
            "tools.mastering.config.load_config", return_value=user_config
        ):
            result = load_mastering_config()
        assert result["delivery_bit_depth"] == 16
        assert result["archival_enabled"] is True
        # Unmentioned keys keep defaults
        assert result["delivery_sample_rate"] == 96000
        assert result["target_lufs"] == -14.0

    def test_rejects_unknown_keys_silently(self):
        """Unknown keys are dropped with a log message; known keys still apply."""
        user_config = {
            "mastering": {"nonsense_key": 42, "target_lufs": -12.0}
        }
        with patch(
            "tools.mastering.config.load_config", return_value=user_config
        ):
            result = load_mastering_config()
        assert "nonsense_key" not in result
        assert result["target_lufs"] == -12.0

    def test_coerces_numeric_strings(self):
        """Users may quote numeric values in YAML; coerce to canonical types."""
        user_config = {
            "mastering": {
                "delivery_sample_rate": "48000",
                "target_lufs": "-14",
            }
        }
        with patch(
            "tools.mastering.config.load_config", return_value=user_config
        ):
            result = load_mastering_config()
        assert result["delivery_sample_rate"] == 48000
        assert isinstance(result["delivery_sample_rate"], int)
        assert result["target_lufs"] == -14.0
        assert isinstance(result["target_lufs"], float)

    def test_non_mapping_mastering_value_falls_back_to_defaults(self):
        """A malformed mastering: value (e.g. list) should not crash."""
        user_config = {"mastering": ["this", "is", "wrong"]}
        with patch(
            "tools.mastering.config.load_config", return_value=user_config
        ):
            result = load_mastering_config()
        assert result == DEFAULT_MASTERING_CONFIG


class TestResolveMasteringTargets:
    def _base_cfg(self) -> dict:
        return {
            "delivery_format": "wav",
            "delivery_bit_depth": 24,
            "delivery_sample_rate": 96000,
            "target_lufs": -14.0,
            "true_peak_ceiling": -1.0,
            "archival_enabled": False,
            "adm_aac_encoder": "aac",
        }

    def test_config_supplies_defaults_when_no_genre_no_explicit(self):
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=None,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert targets["target_lufs"] == -14.0
        assert targets["ceiling_db"] == -1.0
        assert targets["output_bits"] == 24
        assert targets["output_sample_rate"] == 96000

    def test_preset_overrides_config_for_target_lufs(self):
        preset = {"target_lufs": -9.0}  # e.g. metal preset
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=preset,
            target_lufs_arg=-14.0,  # default -> preset wins
            ceiling_db_arg=-1.0,
        )
        assert targets["target_lufs"] == -9.0

    def test_explicit_arg_overrides_preset_and_config(self):
        preset = {"target_lufs": -9.0}
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=preset,
            target_lufs_arg=-16.0,  # explicit override
            ceiling_db_arg=-1.0,
        )
        assert targets["target_lufs"] == -16.0

    def test_preset_output_bits_overrides_config(self):
        preset = {"output_bits": 16}
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=preset,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert targets["output_bits"] == 16

    def test_preset_output_sample_rate_overrides_config(self):
        preset = {"output_sample_rate": 48000}
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=preset,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert targets["output_sample_rate"] == 48000

    def test_preset_zero_sample_rate_falls_back_to_config(self):
        """Preset output_sample_rate=0 means 'preserve input'; config wins."""
        preset = {"output_sample_rate": 0}
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=preset,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert targets["output_sample_rate"] == 96000

    def test_upsampling_flag_set_when_output_exceeds_source(self):
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=None,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
            source_sample_rate=44100,
        )
        assert targets["upsampled_from_source"] is True
        assert targets["source_sample_rate"] == 44100

    def test_upsampling_flag_unset_when_output_matches_source(self):
        targets = resolve_mastering_targets(
            config=self._base_cfg(),
            preset=None,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
            source_sample_rate=96000,
        )
        assert targets["upsampled_from_source"] is False

    def test_genre_preset_defaults_do_not_force_legacy_16bit(self):
        """Regression: every shipped genre preset should honor the config
        delivery_bit_depth / delivery_sample_rate. Before the fix, all
        genres inherited output_bits=16 from YAML defaults and every
        genre-driven master silently dropped to 16-bit output, ignoring
        the config's 24/96 delivery target."""
        from tools.mastering.master_tracks import load_genre_presets

        cfg = {
            "delivery_format": "wav",
            "delivery_bit_depth": 24,
            "delivery_sample_rate": 96000,
            "target_lufs": -14.0,
            "true_peak_ceiling": -1.0,
            "archival_enabled": False,
            "adm_aac_encoder": "aac",
        }
        for genre in ("electronic", "hip-hop", "metal", "folk", "pop"):
            preset = load_genre_presets().get(genre)
            assert preset is not None, f"Missing built-in genre: {genre}"
            targets = resolve_mastering_targets(
                config=cfg,
                preset=preset,
                target_lufs_arg=-14.0,
                ceiling_db_arg=-1.0,
            )
            assert targets["output_bits"] == 24, (
                f"{genre} preset forces 16-bit output; check "
                f"tools/mastering/genre-presets.yaml defaults"
            )
            assert targets["output_sample_rate"] == 96000, (
                f"{genre} preset forces non-96kHz output; check "
                f"tools/mastering/genre-presets.yaml defaults"
            )

    def test_archival_flag_flows_through(self):
        cfg = {**self._base_cfg(), "archival_enabled": True}
        targets = resolve_mastering_targets(
            config=cfg,
            preset=None,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert targets["archival_enabled"] is True


def test_opus_safe_preset_applies_1_5_ceiling() -> None:
    """opus_safe: true tightens ceiling from -1.0 to -1.5 when caller uses default."""
    from tools.mastering.config import resolve_mastering_targets
    config = {"true_peak_ceiling": -1.0, "delivery_bit_depth": 24,
              "delivery_sample_rate": 96000, "target_lufs": -14.0,
              "archival_enabled": False, "adm_aac_encoder": "aac"}
    preset = {"opus_safe": True}
    result = resolve_mastering_targets(
        config, preset, target_lufs_arg=-14.0, ceiling_db_arg=-1.0
    )
    assert result["ceiling_db"] == -1.5


def test_opus_safe_does_not_override_explicit_ceiling() -> None:
    """Explicit ceiling_db_arg always wins over opus_safe."""
    from tools.mastering.config import resolve_mastering_targets
    config = {"true_peak_ceiling": -1.0, "delivery_bit_depth": 24,
              "delivery_sample_rate": 96000, "target_lufs": -14.0,
              "archival_enabled": False, "adm_aac_encoder": "aac"}
    preset = {"opus_safe": True}
    result = resolve_mastering_targets(
        config, preset, target_lufs_arg=-14.0, ceiling_db_arg=-2.0
    )
    assert result["ceiling_db"] == -2.0


def test_opus_safe_does_not_override_preset_true_peak_ceiling() -> None:
    """explicit true_peak_ceiling in preset wins over opus_safe."""
    from tools.mastering.config import resolve_mastering_targets
    config = {"true_peak_ceiling": -1.0, "delivery_bit_depth": 24,
              "delivery_sample_rate": 96000, "target_lufs": -14.0,
              "archival_enabled": False, "adm_aac_encoder": "aac"}
    preset = {"opus_safe": True, "true_peak_ceiling": -1.2}
    result = resolve_mastering_targets(
        config, preset, target_lufs_arg=-14.0, ceiling_db_arg=-1.0
    )
    assert result["ceiling_db"] == -1.2


def test_build_effective_preset_edm_gets_opus_safe_ceiling() -> None:
    """EDM genre preset (opus_safe: true) resolves to -1.5 dBTP ceiling."""
    from tools.mastering.config import build_effective_preset
    bundle = build_effective_preset(
        genre="edm",
        cut_highmid_arg=0.0, cut_highs_arg=0.0,
        target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
    )
    assert bundle["error"] is None
    assert bundle["targets"]["ceiling_db"] == -1.5
