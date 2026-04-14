#!/usr/bin/env python3
"""Unit tests for album coherence classification + correction planning (#290 phase 3b)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.coherence import (
    DEFAULTS,
    classify_outliers,
    build_correction_plan,
    load_tolerances,
)


class TestLoadTolerances:
    def test_none_preset_returns_defaults(self):
        tolerances = load_tolerances(None)
        assert tolerances["coherence_stl_95_lu"] == pytest.approx(0.5)
        assert tolerances["coherence_lra_floor_lu"] == pytest.approx(1.0)
        assert tolerances["coherence_low_rms_db"] == pytest.approx(2.0)
        assert tolerances["coherence_vocal_rms_db"] == pytest.approx(2.0)
        assert tolerances["lufs_tolerance_lu"] == pytest.approx(0.5)

    def test_empty_preset_returns_defaults(self):
        assert load_tolerances({}) == DEFAULTS

    def test_partial_preset_merges_with_defaults(self):
        preset = {"coherence_stl_95_lu": 0.8}  # only override one
        tolerances = load_tolerances(preset)
        assert tolerances["coherence_stl_95_lu"] == pytest.approx(0.8)
        # Other fields fall back to defaults
        assert tolerances["coherence_lra_floor_lu"] == pytest.approx(1.0)

    def test_lufs_tolerance_not_overridable_from_preset(self):
        # lufs_tolerance_lu is hardcoded — presets can't change it
        preset = {"lufs_tolerance_lu": 99.0}
        tolerances = load_tolerances(preset)
        assert tolerances["lufs_tolerance_lu"] == pytest.approx(0.5)
