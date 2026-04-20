"""Tests for per-stem polished WAV output from mix_track_stems (#290)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def _write_stem(path: Path, amplitude: float = 0.1) -> Path:
    n = int(44100 * 1.0)
    data = (amplitude * np.sin(2 * np.pi * 440 * np.arange(n) / 44100)).astype(np.float32)
    sf.write(str(path), np.column_stack([data, data]), 44100, subtype="PCM_16")
    return path


def test_mix_track_stems_writes_vocals_to_stem_output_dir(tmp_path: Path) -> None:
    """When stem_output_dir is set, vocals.wav is written there."""
    from tools.mixing.mix_tracks import mix_track_stems

    stems_dir = tmp_path / "stems"
    stems_dir.mkdir()
    vocals_path = _write_stem(stems_dir / "vocals.wav")
    drums_path = _write_stem(stems_dir / "drums.wav")

    stem_output_dir = tmp_path / "polished" / "01-track"
    stem_output_dir.mkdir(parents=True)
    output_path = tmp_path / "polished" / "01-track.wav"

    result = mix_track_stems(
        {"vocals": str(vocals_path), "drums": str(drums_path)},
        output_path,
        stem_output_dir=stem_output_dir,
    )

    assert (stem_output_dir / "vocals.wav").exists()
    data, rate = sf.read(str(stem_output_dir / "vocals.wav"))
    assert data.size > 0


def test_mix_track_stems_no_stem_output_dir_unchanged(tmp_path: Path) -> None:
    """Without stem_output_dir, behavior is unchanged (no per-stem files written)."""
    from tools.mixing.mix_tracks import mix_track_stems

    stems_dir = tmp_path / "stems"
    stems_dir.mkdir()
    _write_stem(stems_dir / "vocals.wav")
    output_path = tmp_path / "polished" / "01-track.wav"
    output_path.parent.mkdir(parents=True)

    result = mix_track_stems(
        {"vocals": str(stems_dir / "vocals.wav")},
        output_path,
        # no stem_output_dir
    )

    # polished/ should only have the single output file, no subdirectory
    files = list((tmp_path / "polished").iterdir())
    assert len(files) == 1
    assert files[0].name == "01-track.wav"


def test_mix_track_stems_dry_run_does_not_write_stems(tmp_path: Path) -> None:
    """In dry_run mode, per-stem WAVs are not written even when dir is set."""
    from tools.mixing.mix_tracks import mix_track_stems

    stems_dir = tmp_path / "stems"
    stems_dir.mkdir()
    _write_stem(stems_dir / "vocals.wav")

    stem_output_dir = tmp_path / "polished" / "01-track"
    stem_output_dir.mkdir(parents=True)
    output_path = tmp_path / "polished" / "01-track.wav"

    mix_track_stems(
        {"vocals": str(stems_dir / "vocals.wav")},
        output_path,
        stem_output_dir=stem_output_dir,
        dry_run=True,
    )

    assert not (stem_output_dir / "vocals.wav").exists()


# ---------------------------------------------------------------------------
# Task 4 (#336): polish_audio analyzer_results coupling
# ---------------------------------------------------------------------------


def _make_dark_stem_dir(parent: Path, track_name: str) -> Path:
    """Create stems/{track_name}/ with a vocals.wav and synth.wav."""
    track_dir = parent / track_name
    track_dir.mkdir(parents=True)
    _write_stem(track_dir / "vocals.wav", amplitude=0.1)
    _write_stem(track_dir / "synth.wav", amplitude=0.1)
    return track_dir


class TestPolishAudioAnalyzerCoupling:
    """#336: polish_audio pipes analyzer recs into mix_track_stems."""

    def _setup_audio_dir(self, tmp_path: Path, monkeypatch) -> Path:
        """Build a minimal audio_dir with stems/ and patch _resolve_audio_dir."""
        audio_dir = tmp_path / "audio"
        stems_dir = audio_dir / "stems"
        stems_dir.mkdir(parents=True)
        _make_dark_stem_dir(stems_dir, "01-dark")

        # Patch _resolve_audio_dir to return our tmp audio dir
        from handlers.processing import _helpers
        def _fake_resolve(album_slug: str):
            return None, audio_dir
        monkeypatch.setattr(_helpers, "_resolve_audio_dir", _fake_resolve)

        # Bypass dependency check
        monkeypatch.setattr(_helpers, "_check_mixing_deps", lambda: None)

        return audio_dir

    def test_polish_audio_uses_provided_analyzer_results_without_rerun(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When analyzer_results is provided, polish_audio does NOT call analyze_mix_issues."""
        import asyncio
        import json

        self._setup_audio_dir(tmp_path, monkeypatch)

        from handlers.processing import mixing as mixing_mod

        call_count = {"n": 0}
        original = mixing_mod.analyze_mix_issues

        async def _tracking_analyzer(*args, **kwargs):
            call_count["n"] += 1
            return await original(*args, **kwargs)

        monkeypatch.setattr(mixing_mod, "analyze_mix_issues", _tracking_analyzer)

        # Provide pre-computed analyzer_results so polish should skip re-running
        pre_analyzed = {
            "tracks": [
                {
                    "track": "01-dark",
                    "stems": {
                        "synth": {
                            "filename": "synth.wav",
                            "issues": ["already_dark"],
                            "recommendations": {"high_tame_db": 0.0},
                        },
                        "vocals": {
                            "filename": "vocals.wav",
                            "issues": ["none_detected"],
                            "recommendations": {},
                        },
                    },
                    "issues": ["already_dark"],
                },
            ],
            "album_summary": {"tracks_analyzed": 1, "common_issues": ["already_dark"], "source_mode": "stems"},
        }

        result_json = asyncio.run(mixing_mod.polish_audio(
            album_slug="test-album", genre="electronic",
            use_stems=True, dry_run=True,
            analyzer_results=pre_analyzed,
        ))
        result = json.loads(result_json)

        assert call_count["n"] == 0, (
            f"polish_audio should NOT re-run analyzer when analyzer_results is passed, "
            f"but analyze_mix_issues was called {call_count['n']} time(s)"
        )

    def test_polish_audio_surfaces_overrides_from_provided_analyzer_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """polish_audio.summary.overrides_applied reflects per-track analyzer recs."""
        import asyncio
        import json

        self._setup_audio_dir(tmp_path, monkeypatch)
        from handlers.processing import mixing as mixing_mod

        pre_analyzed = {
            "tracks": [
                {
                    "track": "01-dark",
                    "stems": {
                        "synth": {
                            "filename": "synth.wav",
                            "issues": ["already_dark"],
                            "recommendations": {"high_tame_db": 0.0},
                        },
                        "vocals": {
                            "filename": "vocals.wav",
                            "issues": ["none_detected"],
                            "recommendations": {},
                        },
                    },
                    "issues": ["already_dark"],
                },
            ],
            "album_summary": {"tracks_analyzed": 1, "common_issues": ["already_dark"], "source_mode": "stems"},
        }

        result_json = asyncio.run(mixing_mod.polish_audio(
            album_slug="test-album", genre="electronic",
            use_stems=True, dry_run=True,
            analyzer_results=pre_analyzed,
        ))
        result = json.loads(result_json)

        overrides = result["summary"].get("overrides_applied", [])
        assert len(overrides) == 1, (
            f"expected 1 override (synth high_tame_db), got {overrides}"
        )
        entry = overrides[0]
        assert entry["track"] == "01-dark"
        assert entry["stem"] == "synth"
        assert entry["parameter"] == "high_tame_db"
        assert entry["applied"] == pytest.approx(0.0)
        assert entry["reason"] == "already_dark"

    def test_polish_album_surfaces_overrides_in_stage_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """polish_album's final JSON carries overrides_applied under stages.polish."""
        import asyncio
        import json

        audio_dir = self._setup_audio_dir(tmp_path, monkeypatch)
        # Create an empty polished/ directory so the verify stage finds it
        # (the verify stage needs polished_dir to exist but tolerates empty).
        (audio_dir / "polished").mkdir(exist_ok=True)

        from handlers.processing import mixing as mixing_mod

        # Patch analyze_mix_issues to return a pre-baked response with
        # one dark-synth track so polish_album can pipe it through.
        pre_analyzed = {
            "tracks": [
                {
                    "track": "01-dark",
                    "stems": {
                        "synth": {
                            "filename": "synth.wav",
                            "issues": ["already_dark"],
                            "recommendations": {"high_tame_db": 0.0},
                        },
                        "vocals": {
                            "filename": "vocals.wav",
                            "issues": ["none_detected"],
                            "recommendations": {},
                        },
                    },
                    "issues": ["already_dark"],
                },
            ],
            "album_summary": {
                "tracks_analyzed": 1,
                "common_issues": ["already_dark"],
                "source_mode": "stems",
            },
        }

        async def _fake_analyze(album_slug: str, genre: str = "") -> str:
            return json.dumps(pre_analyzed)

        monkeypatch.setattr(mixing_mod, "analyze_mix_issues", _fake_analyze)

        # qc_track runs on polished/ output during the verify stage.
        # Patch it to return a pass so the test doesn't require real WAVs.
        import tools.mastering.qc_tracks as qc_mod

        def _fake_qc(wav_path: str, checks: list, genre=None) -> dict:
            return {
                "filename": Path(wav_path).name,
                "verdict": "PASS",
                "checks": {},
            }

        monkeypatch.setattr(qc_mod, "qc_track", _fake_qc)

        result_json = asyncio.run(mixing_mod.polish_album(
            album_slug="test-album", genre="electronic",
        ))
        result = json.loads(result_json)

        assert "stages" in result, f"expected stages in polish_album result, got {list(result.keys())}"
        polish_stage = result["stages"].get("polish", {})
        assert "overrides_applied" in polish_stage, (
            f"polish_album stages.polish must expose overrides_applied; "
            f"got {list(polish_stage.keys())}"
        )
        # Exactly one override expected: synth.high_tame_db = 0.0 (already_dark)
        overrides = polish_stage["overrides_applied"]
        assert isinstance(overrides, list)
        assert len(overrides) == 1, (
            f"expected 1 override for dark synth stem, got {overrides}"
        )
        assert overrides[0]["track"] == "01-dark"
        assert overrides[0]["stem"] == "synth"
        assert overrides[0]["parameter"] == "high_tame_db"
        assert overrides[0]["reason"] == "already_dark"
