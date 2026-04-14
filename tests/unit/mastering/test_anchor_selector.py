#!/usr/bin/env python3
"""Unit tests for the album-mastering anchor selector (#290 phase 2)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.anchor_selector import (
    _spectral_match_score,
)

from tools.mastering.anchor_selector import (
    _mix_quality_score,
    _representativeness_score,
    _ceiling_penalty_score,
    _album_medians,
)


REF = {
    "sub_bass": 8.0,
    "bass":     18.0,
    "low_mid":  20.0,
    "mid":      25.0,
    "high_mid": 14.0,
    "high":     10.0,
    "air":       5.0,
}


class TestSpectralMatchScore:
    def test_exact_match_scores_one(self):
        assert _spectral_match_score(REF, REF) == pytest.approx(1.0)

    def test_mismatched_curve_scores_below_match(self):
        off = {**REF, "mid": 5.0, "high": 30.0}  # large distance
        score_match = _spectral_match_score(REF, REF)
        score_off = _spectral_match_score(off, REF)
        assert score_off < score_match
        assert 0.0 < score_off < 1.0


def _track(**overrides) -> dict:
    base = {
        "filename": "01.wav",
        "stl_95": -14.0,
        "short_term_range": 8.0,
        "low_rms": -20.0,
        "vocal_rms": -18.0,
        "peak_db": -4.0,
        "band_energy": dict(REF),
    }
    base.update(overrides)
    return base


class TestMixQuality:
    def test_on_target_lra_and_spectral_match_scores_near_one(self):
        track = _track(short_term_range=8.0, band_energy=dict(REF))
        score = _mix_quality_score(track, REF, genre_ideal_lra=8.0)
        # LRA difference 0 → 1/(1+0)=1; spectral exact → 1; product = 1
        assert score == pytest.approx(1.0)

    def test_off_target_lra_drops_score(self):
        track = _track(short_term_range=14.0, band_energy=dict(REF))
        score = _mix_quality_score(track, REF, genre_ideal_lra=8.0)
        # |14 − 8| = 6 → 1/7 ≈ 0.143; spectral match = 1 → score ≈ 0.143
        assert score == pytest.approx(1.0 / 7.0, rel=1e-3)


class TestRepresentativeness:
    def test_track_at_median_scores_one(self):
        tracks = [
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
        ]
        medians = _album_medians(tracks)
        score = _representativeness_score(tracks[0], medians)
        assert score == pytest.approx(1.0)

    def test_distant_track_scores_below(self):
        tracks = [
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-10.0, short_term_range=3.0, low_rms=-12.0, vocal_rms=-10.0),
        ]
        medians = _album_medians(tracks)
        score_close = _representativeness_score(tracks[0], medians)
        score_far = _representativeness_score(tracks[2], medians)
        assert score_close > score_far
        assert 0.0 < score_far < 1.0


class TestCeilingPenalty:
    def test_peak_below_minus3_no_penalty(self):
        assert _ceiling_penalty_score(-6.0) == 0.0
        assert _ceiling_penalty_score(-3.0) == 0.0

    def test_peak_at_0dbfs_max_penalty(self):
        assert _ceiling_penalty_score(0.0) == pytest.approx(1.0)

    def test_peak_midway_scaled(self):
        assert _ceiling_penalty_score(-1.5) == pytest.approx(0.5)


from tools.mastering.anchor_selector import select_anchor


def _preset(ideal_lra: float = 8.0) -> dict:
    return {
        "genre_ideal_lra_lu": ideal_lra,
        "spectral_reference_energy": dict(REF),
    }


class TestSelectAnchorComposite:
    def test_picks_representative_track(self):
        # Track 1 matches album median exactly; track 2 is an outlier.
        t1 = _track(filename="01.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-5.0)
        t2 = _track(filename="02.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-5.0)
        t3 = _track(filename="03.wav", stl_95=-10.0, short_term_range=3.0,
                    low_rms=-12.0, vocal_rms=-10.0, peak_db=-2.0)
        result = select_anchor([t1, t2, t3], _preset())
        assert result["method"] == "tie_breaker"  # 01 and 02 identical
        assert result["selected_index"] == 1
        assert result["scores"][2]["score"] < result["scores"][0]["score"]

    def test_ceiling_penalty_demotes_hot_track(self):
        # Representative but near 0 dBFS → penalty beats representativeness.
        t1 = _track(filename="01.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-0.5)
        t2 = _track(filename="02.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-6.0)
        result = select_anchor([t1, t2], _preset())
        assert result["selected_index"] == 2  # cooler track wins
        assert result["scores"][0]["ceiling_penalty"] > 0
        assert result["scores"][1]["ceiling_penalty"] == 0.0


class TestSelectAnchorOverride:
    def test_valid_override_short_circuits_scoring(self):
        t1 = _track(filename="01.wav", peak_db=-5.0)
        t2 = _track(filename="02.wav", peak_db=-5.0)
        t3 = _track(filename="03.wav", peak_db=-5.0)
        result = select_anchor([t1, t2, t3], _preset(), override_index=2)
        assert result["method"] == "override"
        assert result["selected_index"] == 2
        assert result["override_index"] == 2
        assert result["override_reason"] is None

    def test_out_of_range_override_falls_through_to_scoring(self):
        t1 = _track(filename="01.wav", peak_db=-5.0)
        t2 = _track(filename="02.wav", peak_db=-5.0)
        result = select_anchor([t1, t2], _preset(), override_index=99)
        assert result["method"] in ("composite", "tie_breaker")
        assert result["override_index"] == 99
        assert "out of range" in (result["override_reason"] or "")

    def test_zero_override_treated_as_no_override(self):
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav")
        result = select_anchor([t1, t2], _preset(), override_index=0)
        assert result["method"] != "override"


class TestSelectAnchorTieBreaker:
    def test_ties_resolve_to_lowest_index(self):
        # Three identical tracks → lowest index wins.
        tracks = [_track(filename=f"0{i}.wav") for i in (1, 2, 3)]
        result = select_anchor(tracks, _preset())
        assert result["method"] == "tie_breaker"
        assert result["selected_index"] == 1

    def test_scores_outside_epsilon_use_composite(self):
        t1 = _track(filename="01.wav", short_term_range=8.0)   # on-target LRA
        t2 = _track(filename="02.wav", short_term_range=20.0)  # far-off LRA
        result = select_anchor([t1, t2], _preset())
        assert result["method"] == "composite"
        assert result["selected_index"] == 1


class TestSelectAnchorEligibility:
    def test_missing_signature_track_marked_ineligible(self):
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav", stl_95=None)  # missing
        result = select_anchor([t1, t2], _preset())
        assert result["selected_index"] == 1
        score_entry = next(s for s in result["scores"] if s["index"] == 2)
        assert score_entry["eligible"] is False
        assert "stl_95" in score_entry["reason"]

    def test_all_ineligible_returns_no_selection(self):
        t1 = _track(filename="01.wav", stl_95=None)
        t2 = _track(filename="02.wav", stl_95=None)
        result = select_anchor([t1, t2], _preset())
        assert result["selected_index"] is None
        assert result["method"] == "no_eligible_tracks"


class TestSelectAnchorInputHardening:
    def test_float_override_rejected_as_no_override(self):
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav")
        result = select_anchor([t1, t2], _preset(), override_index=1.5)
        assert result["method"] != "override"
        assert result["override_index"] == 1.5
        assert "non-integer" in (result["override_reason"] or "")

    def test_bool_override_rejected_as_no_override(self):
        # bool is an int subclass in Python; selector must still reject it.
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav")
        result = select_anchor([t1, t2], _preset(), override_index=True)
        assert result["method"] != "override"
        assert "non-integer" in (result["override_reason"] or "")

    def test_string_override_rejected_without_raising(self):
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav")
        # Must not raise TypeError from `> 0` comparison.
        result = select_anchor([t1, t2], _preset(), override_index="2")
        assert result["method"] != "override"
        assert "non-integer" in (result["override_reason"] or "")

    def test_band_energy_missing_a_band_marks_ineligible(self):
        bad = {k: v for k, v in REF.items() if k != "air"}
        t1 = _track(filename="01.wav", band_energy=bad)
        t2 = _track(filename="02.wav")
        result = select_anchor([t1, t2], _preset())
        assert result["selected_index"] == 2
        entry1 = next(s for s in result["scores"] if s["index"] == 1)
        assert entry1["eligible"] is False
        assert "air" in entry1["reason"]

    def test_malformed_spectral_reference_raises_valueerror(self):
        bad_preset = {
            "genre_ideal_lra_lu": 8.0,
            "spectral_reference_energy": {
                k: v for k, v in REF.items() if k != "air"
            },
        }
        t1 = _track(filename="01.wav")
        with pytest.raises(ValueError, match="missing bands"):
            select_anchor([t1], bad_preset)

    def test_empty_tracks_returns_no_selection(self):
        result = select_anchor([], _preset())
        assert result["selected_index"] is None
        assert result["method"] == "no_eligible_tracks"
        assert result["scores"] == []

    def test_track_missing_signature_key_entirely_handled_by_medians(self):
        # Latent I4: a track dict without the key at all (not None) must
        # not crash _album_medians when other tracks do have the key.
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav")
        t3 = dict(t1)
        del t3["stl_95"]  # key entirely absent, not just None
        t3["filename"] = "03.wav"
        result = select_anchor([t1, t2, t3], _preset())
        # t3 is ineligible (_is_eligible sees missing stl_95),
        # but t1 and t2 must still get scored without a KeyError.
        assert result["selected_index"] in (1, 2)
