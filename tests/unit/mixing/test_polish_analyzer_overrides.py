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


class TestMixTrackStemsAnalyzerRecs:
    """#336: mix_track_stems accepts per-stem analyzer recs and records overrides_applied."""

    def _make_dummy_stem(self, tmp_path, name: str, amplitude: float = 0.2):
        """Write a 1-second 100 Hz sine as a stem WAV; return the path."""
        import numpy as np
        import soundfile as sf
        rate = 48000
        t = np.linspace(0.0, 1.0, rate, endpoint=False)
        mono = amplitude * np.sin(2 * np.pi * 100 * t).astype("float64")
        stereo = np.column_stack([mono, mono])
        p = tmp_path / f"{name}.wav"
        sf.write(str(p), stereo, rate)
        return str(p)

    def test_mix_track_stems_records_overrides_applied_when_recs_present(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {
            "vocals": self._make_dummy_stem(tmp_path, "vocals"),
            "synth":  self._make_dummy_stem(tmp_path, "synth"),
        }
        out = tmp_path / "mix.wav"
        analyzer_recs = {
            "synth": {
                "recommendations": {"high_tame_db": 0.0},
                "issues": ["already_dark"],
            }
        }
        result = mix_track_stems(
            stem_paths, str(out),
            genre="electronic", dry_run=True,
            analyzer_recs=analyzer_recs,
        )
        assert "overrides_applied" in result
        assert len(result["overrides_applied"]) == 1
        entry = result["overrides_applied"][0]
        assert entry["stem"] == "synth"
        assert entry["parameter"] == "high_tame_db"
        assert entry["analyzer_rec"] == pytest.approx(0.0)
        assert entry["applied"] == pytest.approx(0.0)
        assert entry["genre_default"] == pytest.approx(-1.5)
        assert entry["reason"] == "already_dark"

    def test_mix_track_stems_no_recs_yields_empty_overrides_list(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {"vocals": self._make_dummy_stem(tmp_path, "vocals")}
        out = tmp_path / "mix.wav"
        result = mix_track_stems(stem_paths, str(out), genre="electronic", dry_run=True)
        assert result.get("overrides_applied", []) == []

    def test_mix_track_stems_non_eq_rec_does_not_produce_override(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {"synth": self._make_dummy_stem(tmp_path, "synth")}
        out = tmp_path / "mix.wav"
        # Only click_removal (non-EQ whitelist) in recommendations
        analyzer_recs = {
            "synth": {
                "recommendations": {"click_removal": True},
                "issues": ["clicks_detected"],
            }
        }
        result = mix_track_stems(
            stem_paths, str(out), genre="electronic", dry_run=True,
            analyzer_recs=analyzer_recs,
        )
        assert result.get("overrides_applied", []) == []

    def test_mix_track_stems_missing_stem_in_recs_falls_through(self, tmp_path):
        """When analyzer_recs has no entry for a stem, that stem uses genre default."""
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {
            "synth": self._make_dummy_stem(tmp_path, "synth"),
            "vocals": self._make_dummy_stem(tmp_path, "vocals"),
        }
        out = tmp_path / "mix.wav"
        # Only synth has a rec; vocals should fall through without producing an override
        analyzer_recs = {
            "synth": {"recommendations": {"high_tame_db": -2.5}, "issues": ["harsh_highmids"]}
        }
        result = mix_track_stems(
            stem_paths, str(out), genre="electronic", dry_run=True,
            analyzer_recs=analyzer_recs,
        )
        stems_in_overrides = {e["stem"] for e in result.get("overrides_applied", [])}
        assert stems_in_overrides == {"synth"}

    def test_mix_track_stems_reason_is_per_parameter(self, tmp_path):
        """#336: a stem with multiple issues gets the correct reason per override entry."""
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {"vocals": self._make_dummy_stem(tmp_path, "vocals")}
        out = tmp_path / "mix.wav"
        # Stem has BOTH muddy_low_mids AND harsh_highmids — each parameter
        # should pick its own justifying tag, not the first-in-list one.
        analyzer_recs = {
            "vocals": {
                "recommendations": {
                    "mud_cut_db":   -4.0,
                    "high_tame_db": -2.5,
                },
                "issues": ["muddy_low_mids", "harsh_highmids"],
            }
        }
        result = mix_track_stems(
            stem_paths, str(out), genre="electronic", dry_run=True,
            analyzer_recs=analyzer_recs,
        )
        by_param = {e["parameter"]: e for e in result["overrides_applied"]}
        assert by_param["mud_cut_db"]["reason"] == "muddy_low_mids"
        assert by_param["high_tame_db"]["reason"] == "harsh_highmids"
