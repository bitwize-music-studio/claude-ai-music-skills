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


def _delta(**overrides) -> dict:
    """Minimal delta dict matching compute_anchor_deltas output."""
    base = {
        "index": 1,
        "filename": "01.wav",
        "is_anchor": False,
        "delta_lufs": 0.0,
        "delta_peak_db": 0.0,
        "delta_stl_95": 0.0,
        "delta_short_term_range": 0.0,
        "delta_low_rms": 0.0,
        "delta_vocal_rms": 0.0,
    }
    base.update(overrides)
    return base


def _analysis(**overrides) -> dict:
    """Minimal analyze_track dict — only fields the classifier needs."""
    base = {
        "filename": "01.wav",
        "lufs": -14.0,
        "short_term_range": 6.5,
        "stl_95": -10.5,
        "low_rms": -18.0,
        "vocal_rms": -16.0,
    }
    base.update(overrides)
    return base


TOLERANCES = dict(DEFAULTS)


class TestClassifyOutliers:
    def test_anchor_row_has_no_violations(self):
        deltas = [_delta(index=1, is_anchor=True)]
        analyses = [_analysis()]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=1)
        assert len(result) == 1
        assert result[0]["is_anchor"] is True
        assert result[0]["is_outlier"] is False
        assert result[0]["violations"] == []

    def test_lufs_outlier_flagged_and_marked_correctable(self):
        deltas = [
            _delta(index=1, delta_lufs=1.3),  # well beyond tolerance 0.5
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        track1 = result[0]
        assert track1["is_outlier"] is True
        lufs_violations = [v for v in track1["violations"] if v["metric"] == "lufs"]
        assert len(lufs_violations) == 1
        v = lufs_violations[0]
        assert v["delta"] == pytest.approx(1.3)
        assert v["tolerance"] == pytest.approx(0.5)
        assert v["severity"] == "outlier"
        assert v["correctable"] is True

    def test_lufs_within_tolerance_is_ok(self):
        deltas = [
            _delta(index=1, delta_lufs=0.3),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        track1 = result[0]
        assert track1["is_outlier"] is False
        lufs_violations = [v for v in track1["violations"] if v["metric"] == "lufs"]
        assert len(lufs_violations) == 1
        assert lufs_violations[0]["severity"] == "ok"

    def test_stl_95_outlier_flagged_and_not_correctable(self):
        deltas = [
            _delta(index=1, delta_stl_95=0.9),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        stl_violations = [
            v for v in result[0]["violations"] if v["metric"] == "stl_95"
        ]
        assert len(stl_violations) == 1
        assert stl_violations[0]["severity"] == "outlier"
        assert stl_violations[0]["correctable"] is False

    def test_lra_floor_violation_uses_absolute_threshold(self):
        deltas = [
            _delta(index=1),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [
            _analysis(filename="01.wav", short_term_range=0.7),   # below floor
            _analysis(filename="02.wav", short_term_range=6.5),
        ]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        floor_violations = [
            v for v in result[0]["violations"] if v["metric"] == "lra_floor"
        ]
        assert len(floor_violations) == 1
        assert floor_violations[0]["value"] == pytest.approx(0.7)
        assert floor_violations[0]["floor"] == pytest.approx(1.0)
        assert floor_violations[0]["severity"] == "outlier"
        assert floor_violations[0]["correctable"] is False

    def test_low_rms_outlier_flagged(self):
        deltas = [
            _delta(index=1, delta_low_rms=2.5),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        lr_violations = [
            v for v in result[0]["violations"] if v["metric"] == "low_rms"
        ]
        assert len(lr_violations) == 1
        assert lr_violations[0]["severity"] == "outlier"
        assert lr_violations[0]["correctable"] is False

    def test_vocal_rms_outlier_flagged(self):
        deltas = [
            _delta(index=1, delta_vocal_rms=-2.8),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        vr = [v for v in result[0]["violations"] if v["metric"] == "vocal_rms"]
        assert vr[0]["severity"] == "outlier"

    def test_missing_metric_produces_missing_severity(self):
        deltas = [
            _delta(index=1, delta_low_rms=None),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [
            _analysis(filename="01.wav", low_rms=None),
            _analysis(filename="02.wav"),
        ]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        lr = [v for v in result[0]["violations"] if v["metric"] == "low_rms"]
        assert len(lr) == 1
        assert lr[0]["severity"] == "missing"

    def test_multiple_violations_on_one_track(self):
        deltas = [
            _delta(index=1, delta_lufs=1.3, delta_stl_95=0.9, delta_vocal_rms=2.5),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        track1 = result[0]
        assert track1["is_outlier"] is True
        outlier_metrics = {
            v["metric"] for v in track1["violations"] if v["severity"] == "outlier"
        }
        assert outlier_metrics == {"lufs", "stl_95", "vocal_rms"}

    def test_missing_alone_does_not_flag_outlier(self):
        deltas = [
            _delta(index=1, delta_low_rms=None),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [
            _analysis(filename="01.wav", low_rms=None),
            _analysis(filename="02.wav"),
        ]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        assert result[0]["is_outlier"] is False


class TestBuildCorrectionPlan:
    def test_anchor_is_in_skipped(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": False, "violations": []},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.1),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)
        skipped_indices = {s["index"] for s in plan["skipped"]}
        assert 2 in skipped_indices
        anchor_entry = next(s for s in plan["skipped"] if s["index"] == 2)
        assert anchor_entry["reason"] == "is_anchor"

    def test_clean_tracks_are_skipped(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": False, "violations": [
                 {"metric": "lufs", "delta": 0.1, "tolerance": 0.5,
                  "severity": "ok", "correctable": False},
             ]},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.1),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)
        skipped_reasons = {s["index"]: s["reason"] for s in plan["skipped"]}
        assert skipped_reasons.get(1) == "no_violations"

    def test_lufs_outlier_is_correctable_with_anchor_lufs(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": True, "violations": [
                 {"metric": "lufs", "delta": 1.3, "tolerance": 0.5,
                  "severity": "outlier", "correctable": True},
             ]},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-12.8),   # outlier
            _analysis(filename="02.wav", lufs=-14.1),   # anchor, measured
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)

        assert plan["anchor_index"] == 2
        assert plan["anchor_lufs"] == pytest.approx(-14.1)
        correctable = [c for c in plan["corrections"] if c["correctable"]]
        assert len(correctable) == 1
        entry = correctable[0]
        assert entry["index"] == 1
        assert entry["corrected_target_lufs"] == pytest.approx(-14.1)
        assert "LUFS outlier" in entry["reason"]

    def test_non_lufs_only_outlier_is_not_correctable(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": True, "violations": [
                 {"metric": "lufs", "delta": 0.2, "tolerance": 0.5,
                  "severity": "ok", "correctable": False},
                 {"metric": "stl_95", "delta": 0.9, "tolerance": 0.5,
                  "severity": "outlier", "correctable": False},
             ]},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.1),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)

        uncorrectable = [c for c in plan["corrections"] if not c["correctable"]]
        assert len(uncorrectable) == 1
        assert "MVP scope" in uncorrectable[0]["reason"]
