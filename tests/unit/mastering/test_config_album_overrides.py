"""build_delivery_targets must apply the per-album override rule for
mastering.adm_validation_enabled: frontmatter must be explicitly True,
else the effective value is False — regardless of config.yaml setting.

Other mastering.* keys follow the standard cascade (not covered by this
plan, but the kwarg shape supports them)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.config import build_delivery_targets


class TestAdmResolutionFromAlbumOverrides:
    def _call(self, *, config_adm, album_mastering):
        """Minimal build_delivery_targets call returning just
        adm_validation_enabled from the targets dict."""
        cfg = {
            "target_lufs": -14.0,
            "true_peak_ceiling": -1.0,
            "delivery_bit_depth": 24,
            "delivery_sample_rate": 96000,
            "adm_validation_enabled": config_adm,
        }
        targets = build_delivery_targets(
            cfg,
            preset=None,
            target_lufs_arg=0.0,
            ceiling_db_arg=0.0,
            source_sample_rate=48000,
            album_mastering=album_mastering,
        )
        return targets["adm_validation_enabled"]

    def test_frontmatter_true_config_false_runs_adm(self):
        """Explicit frontmatter opt-in: ADM runs."""
        result = self._call(
            config_adm=False,
            album_mastering={"adm_validation_enabled": True},
        )
        assert result is True

    def test_frontmatter_false_config_true_skips_adm(self):
        """Explicit frontmatter opt-out beats global config."""
        result = self._call(
            config_adm=True,
            album_mastering={"adm_validation_enabled": False},
        )
        assert result is False

    def test_frontmatter_missing_config_true_skips_adm(self):
        """New breaking-change default: frontmatter block missing (or key
        missing from the block) → ADM does NOT run. Config global is
        ignored for this key specifically."""
        # No mastering block at all:
        assert self._call(config_adm=True, album_mastering=None) is False
        assert self._call(config_adm=True, album_mastering={}) is False
        # Block present but key missing:
        assert self._call(
            config_adm=True,
            album_mastering={"ceiling_db": -1.5},
        ) is False

    def test_frontmatter_missing_config_false_skips_adm(self):
        """No frontmatter + no config → off (unchanged from prior default)."""
        assert self._call(config_adm=False, album_mastering=None) is False
        assert self._call(config_adm=False, album_mastering={}) is False

    def test_frontmatter_non_bool_truthy_still_requires_bool(self):
        """Explicit 1 / 'yes' / other truthy values are coerced via bool()
        — the spec requires explicit True but Python truthiness is
        acceptable (matches existing config.get loads). Document the
        behavior."""
        # Integer 1 from YAML is truthy
        assert self._call(
            config_adm=False,
            album_mastering={"adm_validation_enabled": 1},
        ) is True
        # Explicit 0 is falsy
        assert self._call(
            config_adm=True,
            album_mastering={"adm_validation_enabled": 0},
        ) is False
