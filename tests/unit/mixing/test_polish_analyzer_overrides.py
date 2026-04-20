"""Unit tests for _get_stem_settings analyzer_rec merge behavior (#336)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_get_stem_settings_no_analyzer_rec_is_backward_compatible():
    """Without analyzer_rec, settings match previous behavior exactly."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    with_none = _get_stem_settings("synth", genre="electronic", analyzer_rec=None)
    assert baseline == with_none


def test_analyzer_rec_overrides_high_tame_db():
    """Analyzer high_tame_db=-2.0 overrides electronic's synth default (-1.5)."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    assert baseline.get("high_tame_db") == pytest.approx(-1.5), (
        f"precondition failed: expected electronic synth default -1.5, got {baseline.get('high_tame_db')}"
    )
    merged = _get_stem_settings(
        "synth", genre="electronic",
        analyzer_rec={"high_tame_db": -2.0},
    )
    assert merged["high_tame_db"] == pytest.approx(-2.0)


def test_sentinel_zero_overrides_negative_default():
    """analyzer_rec high_tame_db=0.0 overrides negative genre default (not silently dropped)."""
    from tools.mixing.mix_tracks import _get_stem_settings
    merged = _get_stem_settings(
        "synth", genre="electronic",
        analyzer_rec={"high_tame_db": 0.0},
    )
    assert merged["high_tame_db"] == pytest.approx(0.0)


def test_mud_cut_and_highpass_and_noise_reduction_also_overridden():
    """All four EQ whitelist keys apply when present in analyzer_rec."""
    from tools.mixing.mix_tracks import _get_stem_settings
    merged = _get_stem_settings(
        "vocals", genre="electronic",
        analyzer_rec={
            "mud_cut_db": -5.0,
            "high_tame_db": -3.0,
            "noise_reduction": 0.4,
            "highpass_cutoff": 80,
        },
    )
    assert merged["mud_cut_db"] == pytest.approx(-5.0)
    assert merged["high_tame_db"] == pytest.approx(-3.0)
    assert merged["noise_reduction"] == pytest.approx(0.4)
    assert merged["highpass_cutoff"] == 80


def test_non_eq_analyzer_rec_ignored():
    """click_removal and unknown keys do NOT leak into settings."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    merged = _get_stem_settings(
        "synth", genre="electronic",
        analyzer_rec={"click_removal": True, "random_junk_key": 99},
    )
    # click_removal is handled via _resolve_analyzer_peak_ratio, not merged here
    assert "click_removal" not in merged or merged.get("click_removal") == baseline.get("click_removal")
    assert "random_junk_key" not in merged


def test_empty_analyzer_rec_is_noop():
    """analyzer_rec={} produces identical output to analyzer_rec=None."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    empty = _get_stem_settings("synth", genre="electronic", analyzer_rec={})
    assert baseline == empty
