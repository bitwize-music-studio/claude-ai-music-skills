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


def test_every_whitelisted_eq_key_is_overridden():
    """All EQ whitelist keys apply when present in analyzer_rec.

    `noise_reduction` used to be on this list and is deliberately not
    any more (#553) — see TestAnalyzerNeverAutoAppliesNoiseReduction.
    """
    from tools.mixing.mix_tracks import _get_stem_settings
    merged = _get_stem_settings(
        "vocals", genre="electronic",
        analyzer_rec={
            "mud_cut_db": -5.0,
            "high_tame_db": -3.0,
            "highpass_cutoff": 80,
            "excitation_db": 2.5,
        },
    )
    assert merged["mud_cut_db"] == pytest.approx(-5.0)
    assert merged["high_tame_db"] == pytest.approx(-3.0)
    assert merged["highpass_cutoff"] == 80
    assert merged["excitation_db"] == pytest.approx(2.5)


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


class TestAnalyzerNeverAutoAppliesNoiseReduction:
    """#553: `noise_reduction` was on the analyzer override whitelist, and

    that whitelist merges LAST in `_get_stem_settings`. The analyzer's
    `elevated_noise_floor` heuristic (quietest-10% mean > 0.005) fires on
    ordinary sustained content and recommends 0.5-0.8, and `polish_audio`
    auto-runs the analyzer — so the #553 default of `noise_reduction: 0`,
    *and* an explicit user `noise_reduction: 0`, were both overwritten on
    every polish run. The analyzer may still detect and report an
    elevated noise floor; applying noise reduction is the user's call.
    """

    def test_analyzer_noise_reduction_does_not_change_settings(self):
        from tools.mixing.mix_tracks import _get_stem_settings
        baseline = _get_stem_settings("vocals", genre="electronic")
        merged = _get_stem_settings(
            "vocals", genre="electronic",
            analyzer_rec={"noise_reduction": 0.8},
        )
        assert merged == baseline
        assert merged["noise_reduction"] == 0

    def test_analyzer_cannot_override_an_explicit_user_zero(self, tmp_path, monkeypatch):
        import tools.mixing.mix_tracks as mt

        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "mix-presets.yaml").write_text(
            "defaults:\n  vocals:\n    noise_reduction: 0\n"
        )
        monkeypatch.setattr(mt, "_get_overrides_path", lambda: override_dir)
        monkeypatch.setattr(mt, "MIX_PRESETS", mt.load_mix_presets())

        merged = mt._get_stem_settings(
            "vocals", genre="electronic", analyzer_rec={"noise_reduction": 0.8},
        )
        assert merged["noise_reduction"] == 0

    def test_explicit_user_noise_reduction_still_wins(self, tmp_path, monkeypatch):
        """The inverse direction — removing the analyzer key must not
        break the documented way to turn noise reduction back on."""
        import tools.mixing.mix_tracks as mt

        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "mix-presets.yaml").write_text(
            "defaults:\n  vocals:\n    noise_reduction: 0.5\n"
        )
        monkeypatch.setattr(mt, "_get_overrides_path", lambda: override_dir)
        monkeypatch.setattr(mt, "MIX_PRESETS", mt.load_mix_presets())

        merged = mt._get_stem_settings(
            "vocals", genre="electronic", analyzer_rec={"noise_reduction": 0.8},
        )
        assert merged["noise_reduction"] == pytest.approx(0.5)

    def test_noise_reduction_is_off_the_whitelist_and_the_reason_map(self):
        from tools.mixing.mix_tracks import (
            _ANALYZER_EQ_OVERRIDE_KEYS,
            _ANALYZER_PARAM_REASONS,
        )
        assert "noise_reduction" not in _ANALYZER_EQ_OVERRIDE_KEYS
        assert "noise_reduction" not in _ANALYZER_PARAM_REASONS


class TestBlockedAnalyzerRecommendationsAreSurfaced:
    """#553/#336: a recommendation the whitelist drops used to vanish

    silently — the analyzer keeps recommending it on every run and polish
    keeps never applying it, with nothing in the report to show the loop.
    Dropped recommendations are now reported alongside `overrides_applied`.
    """

    @staticmethod
    def _one_stem(tmp_path):
        import numpy as np
        import soundfile as sf

        rate = 44100
        t = np.linspace(0, 0.5, rate // 2, endpoint=False)
        mono = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        path = tmp_path / "vocals.wav"
        sf.write(str(path), np.column_stack([mono, mono]), rate, subtype="PCM_16")
        return path

    def test_blocked_noise_reduction_is_reported(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems

        stem = self._one_stem(tmp_path)
        result = mix_track_stems(
            {"vocals": str(stem)}, str(tmp_path / "out.wav"),
            analyzer_recs={"vocals": {
                "recommendations": {"noise_reduction": 0.8},
                "issues": ["elevated_noise_floor"],
            }},
        )

        assert not [e for e in result["overrides_applied"]
                    if e["parameter"] == "noise_reduction"]
        blocked = result["blocked"]
        assert [(e["stem"], e["parameter"]) for e in blocked] == [
            ("vocals", "noise_reduction"),
        ]
        assert blocked[0]["analyzer_rec"] == pytest.approx(0.8)
        assert blocked[0]["reason"]

    def test_blocked_click_removal_is_reported(self, tmp_path):
        """`click_removal` has always been off the whitelist — it is
        wired through `_resolve_analyzer_peak_ratio`, not merged."""
        from tools.mixing.mix_tracks import mix_track_stems

        stem = self._one_stem(tmp_path)
        result = mix_track_stems(
            {"vocals": str(stem)}, str(tmp_path / "out.wav"),
            analyzer_recs={"vocals": {
                "recommendations": {"click_removal": True},
                "issues": ["clicks_detected"],
            }},
        )
        assert [e["parameter"] for e in result["blocked"]] == ["click_removal"]

    def test_applied_recommendation_is_not_reported_as_blocked(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems

        stem = self._one_stem(tmp_path)
        result = mix_track_stems(
            {"vocals": str(stem)}, str(tmp_path / "out.wav"),
            analyzer_recs={"vocals": {
                "recommendations": {"high_tame_db": -3.0},
                "issues": ["harsh_highmids"],
            }},
        )
        assert [e["parameter"] for e in result["overrides_applied"]] == ["high_tame_db"]
        assert result["blocked"] == []

    def test_blocked_list_is_present_and_empty_without_recommendations(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems

        stem = self._one_stem(tmp_path)
        result = mix_track_stems({"vocals": str(stem)}, str(tmp_path / "out.wav"))
        assert result["blocked"] == []
