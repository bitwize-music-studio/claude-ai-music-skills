"""Unit tests for analyze_mix_issues dark-track condition + threshold resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def test_resolve_analyzer_thresholds_defaults(monkeypatch):
    """With no preset overrides, resolver returns (0.10, 0.25, False)."""
    import tools.mixing.mix_tracks as mix_tracks
    from handlers.processing.mixing import _resolve_analyzer_thresholds

    # Stub load_mix_presets so the test doesn't read the host's
    # ~/bitwize-music/overrides/mix-presets.yaml — see #360.
    monkeypatch.setattr(mix_tracks, "load_mix_presets", lambda: {"defaults": {}})

    dark, harsh, adm_aware = _resolve_analyzer_thresholds()
    assert dark == pytest.approx(0.10)
    assert harsh == pytest.approx(0.25)
    assert adm_aware is False


def test_dark_condition_emits_high_tame_zero_and_already_dark_issue():
    """A track with high_mid_ratio < 0.10 gets recommendation high_tame_db=0.0."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = 0.3 * np.sin(2 * np.pi * 100 * t).astype(np.float64)
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="dark-track.wav", stem_name="synth", genre="electronic")

    assert "already_dark" in result["issues"], f"expected already_dark, got {result['issues']}"
    assert result["recommendations"]["high_tame_db"] == pytest.approx(0.0)
    assert result["high_mid_ratio"] < 0.10


def test_harsh_condition_still_fires_above_0_25():
    """A track with high_mid_ratio > 0.25 gets recommendation high_tame_db=-2.0 and harsh_highmids issue."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 3000 * t) + 0.3 * np.sin(2 * np.pi * 4000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="harsh-track.wav", stem_name="synth", genre="electronic")

    assert "harsh_highmids" in result["issues"], f"expected harsh_highmids, got {result['issues']}"
    assert result["recommendations"]["high_tame_db"] == pytest.approx(-2.0)


def test_middle_band_triggers_neither_condition():
    """high_mid_ratio in [0.10, 0.25] produces neither issue tag.

    Signal: 500 Hz at 0.8 + 3 kHz at 0.3 → high_mid_ratio ≈ 0.123, which
    sits between 0.10 and 0.25 so neither branch fires.
    """
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    # lo=0.8 @ 500 Hz + hi=0.3 @ 3 kHz → high_mid_ratio ≈ 0.123 (in-band)
    mono = (0.8 * np.sin(2 * np.pi * 500 * t) + 0.3 * np.sin(2 * np.pi * 3000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="middle-track.wav", stem_name="synth", genre="electronic")

    assert "already_dark" not in result["issues"]
    assert "harsh_highmids" not in result["issues"]
    assert "high_tame_db" not in result["recommendations"]
    assert result["high_mid_ratio"] > 0.10
    assert result["high_mid_ratio"] < 0.25


def test_preset_override_of_dark_threshold_changes_trigger():
    """Raising the dark threshold to 0.15 makes a ~0.138-ratio track fire already_dark.

    Signal: 500 Hz at 0.75 + 3 kHz at 0.3 → high_mid_ratio ≈ 0.138.
    Default threshold (0.10) does not fire; raised threshold (0.15) fires.
    """
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    # lo=0.75 @ 500 Hz + hi=0.3 @ 3 kHz → high_mid_ratio ≈ 0.138
    mono = (0.75 * np.sin(2 * np.pi * 500 * t) + 0.3 * np.sin(2 * np.pi * 3000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_default = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result_default = analyze_default(data, rate, filename="mid.wav", stem_name="synth", genre="electronic")
    assert "already_dark" not in result_default["issues"]
    assert result_default["high_mid_ratio"] > 0.10  # above default floor

    analyze_raised = _build_analyzer(dark_ratio=0.15, harsh_ratio=0.25)
    result_raised = analyze_raised(data, rate, filename="mid.wav", stem_name="synth", genre="electronic")
    assert "already_dark" in result_raised["issues"]
    assert result_raised["recommendations"]["high_tame_db"] == pytest.approx(0.0)


class TestAnalyzerMirrorsThePolishSilenceGate:
    """#553 follow-up: polish skips a stem whose peak falls under the

    silence gate, but the analyzer happily measured the same noise floor
    and emitted click counts and recommendations for it — so the two
    halves of the pipeline disagreed about whether the stem existed, and
    an operator reading `analyze_mix_issues` saw "600 clicks" on a stem
    polish would never touch. Both sides now read the same threshold.
    """

    @staticmethod
    def _noise_at(peak_dbfs, rate=44100, seed=7):
        import numpy as np

        rng = np.random.default_rng(seed)
        noise = rng.standard_normal(rate)
        noise = noise / np.max(np.abs(noise))
        mono = (noise * (10 ** (peak_dbfs / 20))).astype("float64")
        return np.column_stack([mono, mono]), rate

    def test_stem_below_the_gate_reports_as_skipped(self):
        from handlers.processing.mixing import _build_analyzer

        data, rate = self._noise_at(-60.0)
        analyze_one = _build_analyzer()
        result = analyze_one(
            data, rate, filename="percussion.wav",
            stem_name="percussion", genre="electronic",
        )

        assert result["skipped_empty"] is True
        assert result["issues"] == ["skipped_empty"]
        assert result["recommendations"] == {}
        assert "click_count" not in result
        assert result["peak_dbfs"] == pytest.approx(-60.0, abs=2.0)

    def test_stem_above_the_gate_is_analyzed_normally(self):
        from handlers.processing.mixing import _build_analyzer

        data, rate = self._noise_at(-6.0)
        analyze_one = _build_analyzer()
        result = analyze_one(
            data, rate, filename="percussion.wav",
            stem_name="percussion", genre="electronic",
        )

        assert result.get("skipped_empty") is not True
        assert "click_count" in result

    def test_full_mix_analysis_is_not_gated(self):
        """The gate lives in `mix_track_stems`; the full-mix fallback has
        no such skip, so full-mix analysis must not grow one either."""
        from handlers.processing.mixing import _build_analyzer

        data, rate = self._noise_at(-60.0)
        analyze_one = _build_analyzer()
        result = analyze_one(data, rate, filename="01-quiet.wav")

        assert result.get("skipped_empty") is not True
        assert "click_count" in result

    def test_analyzer_honors_a_lowered_gate_override(self, monkeypatch):
        """The threshold comes from the same per-stem setting polish
        reads, so an override moves both sides together."""
        import tools.mixing.mix_tracks as mt
        from handlers.processing.mixing import _build_analyzer

        real = mt._get_stem_settings

        def _lowered(stem_name, genre=None, analyzer_rec=None):
            return {**real(stem_name, genre, analyzer_rec),
                    "silence_gate_dbfs": -80.0}

        monkeypatch.setattr(mt, "_get_stem_settings", _lowered)

        data, rate = self._noise_at(-60.0)
        result = _build_analyzer()(
            data, rate, filename="percussion.wav",
            stem_name="percussion", genre="electronic",
        )
        assert result.get("skipped_empty") is not True


def _stems_album(tmp_path, peak_dbfs=-60.0):
    """An album dir whose only stem is a percussion WAV at `peak_dbfs` —
    under the default silence gate at -60, well above it at -6."""
    import numpy as np
    import soundfile as sf

    audio_dir = tmp_path / "audio"
    track_dir = audio_dir / "stems" / "01-track"
    track_dir.mkdir(parents=True)
    rate = 44100
    t = np.linspace(0, 1.0, rate, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t).astype("float64")
    mono *= (10 ** (peak_dbfs / 20)) / np.max(np.abs(mono))
    sf.write(str(track_dir / "percussion.wav"),
             np.column_stack([mono, mono]), rate, subtype="PCM_16")
    return audio_dir


def _run_analyze(audio_dir):
    """Run `analyze_mix_issues` against a prepared album dir."""
    import asyncio
    import json
    from unittest.mock import patch

    from handlers.processing import _helpers as helpers_mod
    from handlers.processing import mixing as mixing_mod

    with patch.object(helpers_mod, "_check_mixing_deps", return_value=None), \
         patch.object(helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
        raw = asyncio.run(mixing_mod.analyze_mix_issues("test-album"))
    return json.loads(raw)


class TestGatedStemsAreNotReportedAsAnAlbumIssue:
    """#553: a stem skipped by the silence gate is a routing fact, not a

    mix problem. Tagging it into the per-track `issues` list bubbled
    `skipped_empty` up into `album_summary.common_issues`, which reads as
    "every track on this album has something wrong with it" — the empty
    stem categories Suno's Auto Split returns are normal. The per-stem
    entry still carries `skipped_empty` and its own issue tag, so nothing
    is hidden; it just stops counting as an album-level issue.
    """

    def test_skipped_stem_does_not_reach_track_or_album_issues(self, tmp_path):
        result = _run_analyze(_stems_album(tmp_path))

        track = result["tracks"][0]
        assert track["stems"]["percussion"]["skipped_empty"] is True
        assert track["stems"]["percussion"]["issues"] == ["skipped_empty"]
        assert track["issues"] == ["none_detected"]
        assert "skipped_empty" not in result["album_summary"]["common_issues"]

    def test_real_issues_still_reach_the_album_summary(self, tmp_path):
        result = _run_analyze(_stems_album(tmp_path, peak_dbfs=-6.0))

        track = result["tracks"][0]
        assert track["stems"]["percussion"].get("skipped_empty") is not True
        assert track["issues"] != []
        assert result["album_summary"]["common_issues"] == sorted(
            set(track["issues"]) - {"none_detected"}
        )


class TestAnalyzerRefreshesPresetsAtRunEntry:
    """#553: polish re-reads `{overrides}/mix-presets.yaml` at every run

    entry, but the analyzer's resolvers read the module-global
    `MIX_PRESETS` snapshot. Inside one `polish_album` call — which
    analyzes and then polishes — a mid-session override edit was
    therefore visible to polish and invisible to analyze, so the two
    halves disagreed about which stems are empty and what click
    threshold applies. The analyzer refreshes the same way now.
    """

    @staticmethod
    def _stale_override(tmp_path, monkeypatch, yaml_text):
        """Point the overrides path at a file written AFTER import,
        deliberately *without* refreshing `MIX_PRESETS` — the stale
        snapshot this test exists to catch."""
        import tools.mixing.mix_tracks as mt

        override_dir = tmp_path / "overrides"
        override_dir.mkdir(exist_ok=True)
        (override_dir / "mix-presets.yaml").write_text(yaml_text)
        monkeypatch.setattr(mt, "_get_overrides_path", lambda: override_dir)
        return override_dir

    def _analyze(self, tmp_path, monkeypatch):
        result = _run_analyze(_stems_album(tmp_path))
        return result["tracks"][0]["stems"]["percussion"]

    def test_analyzer_sees_a_gate_override_written_after_import(
        self, tmp_path, monkeypatch,
    ):
        self._stale_override(tmp_path, monkeypatch, (
            "defaults:\n"
            "  percussion:\n"
            "    silence_gate_dbfs: -80\n"
        ))
        assert self._analyze(tmp_path, monkeypatch).get("skipped_empty") is not True

    def test_analyzer_still_gates_without_the_override(self, tmp_path, monkeypatch):
        self._stale_override(tmp_path, monkeypatch, "defaults: {}\n")
        assert self._analyze(tmp_path, monkeypatch)["skipped_empty"] is True

    def test_analyzer_sees_a_threshold_override_written_after_import(
        self, tmp_path, monkeypatch,
    ):
        from handlers.processing.mixing import _resolve_analyzer_peak_ratio

        self._stale_override(tmp_path, monkeypatch, (
            "defaults:\n"
            "  percussion:\n"
            "    silence_gate_dbfs: -80\n"
            "    click_peak_ratio: 22.5\n"
        ))
        self._analyze(tmp_path, monkeypatch)
        assert _resolve_analyzer_peak_ratio("percussion", "") == pytest.approx(22.5)
