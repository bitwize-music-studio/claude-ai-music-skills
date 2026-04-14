#!/usr/bin/env python3
"""Tests verifying coherence tolerance fields are present in genre defaults (#290 phase 3b)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.master_tracks import load_genre_presets


COHERENCE_FIELDS = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
}


class TestCoherenceTolerancesInDefaults:
    def test_all_four_fields_present_in_defaults_block(self):
        presets = load_genre_presets()
        # load_genre_presets merges defaults into every genre. Pick "pop" —
        # it's the canonical test genre and doesn't override these fields.
        pop = presets["pop"]
        for key, expected in COHERENCE_FIELDS.items():
            assert key in pop, f"{key} missing from merged pop preset"
            assert pop[key] == pytest.approx(expected), (
                f"{key} default = {pop[key]}, expected {expected}"
            )
