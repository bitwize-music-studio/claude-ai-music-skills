"""Every path that re-masters a track from its source keeps the track's fade-out.

Coherence correction (the master_album stage and the album_coherence_correct
tool) and fix_dynamic_track write a mastered track from its source again. They
never passed a fade, which went unnoticed while master_album never faded at
all. They now take the same fade as the first master: the track file's Fade
Out row, or the default when it has none.

Usage:
    python -m pytest tests/unit/mastering/test_fade_out_paths.py -v
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as shared_mod
from handlers.processing import _album_stages as album_stages_mod
from handlers.processing import _helpers as processing_helpers
from handlers.processing import audio as audio_mod

pytestmark = pytest.mark.unit


class _FakeCache:
    def __init__(self, tracks: dict):
        self._state = {"albums": {"test-album": {"tracks": tracks}}}

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _sine(path: Path, *, seconds: float = 2.0, amplitude: float = 0.3,
          freq: float = 440.0) -> Path:
    rate = 44100
    t = np.arange(int(seconds * rate)) / rate
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(str(path), np.column_stack([mono, mono]), rate, subtype="PCM_24")
    return path


def _resolve_to(audio_dir: Path):
    def _fake_resolve(slug, *_, **__):
        return None, audio_dir
    return patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve)


# ===========================================================================
# The shared lookup
# ===========================================================================


class TestTrackFadeOut:
    @pytest.mark.parametrize("tracks, expected", [
        ({"02-outlier": {"fade_out": 8.0}}, 8.0),
        ({"02-outlier": {"fade_out": None}}, None),
        ({"02-outlier": {"title": "no row"}}, 3.0),
        ({}, 3.0),
    ])
    def test_reads_the_tracks_entry(self, monkeypatch, tracks, expected):
        monkeypatch.setattr(shared_mod, "cache", _FakeCache(tracks))
        assert processing_helpers._track_fade_out("test-album", "02-outlier.wav") == expected

    def test_matches_the_file_name_to_the_track_slug(self, monkeypatch):
        monkeypatch.setattr(shared_mod, "cache", _FakeCache({"02-outlier": {"fade_out": 8.0}}))
        assert processing_helpers._track_fade_out("Test-Album", "02-Outlier.WAV") == 8.0


# ===========================================================================
# Coherence correction inside master_album
# ===========================================================================


class TestCoherenceStage:
    def test_a_corrected_track_keeps_its_fade(self, tmp_path, monkeypatch):
        from tools.mastering.album_signature import compute_anchor_deltas
        from tools.mastering.coherence import classify_outliers, load_tolerances

        source_dir = tmp_path / "polished"
        output_dir = tmp_path / "mastered"
        source_dir.mkdir()
        output_dir.mkdir()
        for name, amplitude in (("01-anchor.wav", 0.3), ("02-outlier.wav", 0.1)):
            _sine(source_dir / name, amplitude=amplitude)
            shutil.copy(source_dir / name, output_dir / name)

        def verify(name, lufs):
            return {"filename": name, "lufs": lufs, "peak_db": -1.5, "stl_95": lufs + 4.0,
                    "short_term_range": 6.5, "low_rms": lufs - 4.0, "vocal_rms": lufs - 2.0}

        verify_results = [verify("01-anchor.wav", -14.0), verify("02-outlier.wav", -18.0)]
        classifications = classify_outliers(
            compute_anchor_deltas(verify_results, anchor_index_1based=1),
            verify_results, load_tolerances(None), anchor_index_1based=1,
        )
        calls: list[dict] = []

        def fake_master_track(src, dst, **kwargs):
            calls.append(kwargs)
            shutil.copy(src, dst)
            return {"status": "ok"}

        import tools.mastering.master_tracks as master_tracks_mod
        monkeypatch.setattr(master_tracks_mod, "master_track", fake_master_track)
        monkeypatch.setattr(album_stages_mod, "_COHERENCE_MAX_ITERATIONS", 1)
        monkeypatch.setattr(shared_mod, "cache", _FakeCache({"02-outlier": {"fade_out": 8.0}}))

        async def run():
            ctx = album_stages_mod.MasterAlbumCtx(
                album_slug="test-album", genre="", target_lufs=-14.0,
                ceiling_db=-1.0, cut_highmid=None, cut_highs=None,
                source_subfolder="", freeze_signature=False, new_anchor=False,
                loop=asyncio.get_running_loop(),
            )
            ctx.anchor_result = {"selected_index": 1}
            ctx.verify_results = verify_results
            ctx.coherence_classifications = classifications
            ctx.source_dir = source_dir
            ctx.output_dir = output_dir
            ctx.mastered_files = [output_dir / "01-anchor.wav", output_dir / "02-outlier.wav"]
            ctx.effective_ceiling = -1.0
            ctx.effective_compress = 1.0
            ctx.effective_preset = {}
            ctx.preset_dict = None
            return await album_stages_mod._stage_coherence_correct(ctx)

        asyncio.run(run())

        assert [call["fade_out"] for call in calls] == [8.0]


# ===========================================================================
# The album_coherence_correct tool
# ===========================================================================


class TestAlbumCoherenceCorrectTool:
    def test_a_corrected_track_keeps_its_fade(self, tmp_path, monkeypatch):
        for sub in ("polished", "mastered"):
            (tmp_path / sub).mkdir()
            for i, amplitude in enumerate((0.3, 0.6, 0.3), start=1):
                _sine(tmp_path / sub / f"{i:02d}-track.wav", seconds=60.0,
                      amplitude=amplitude, freq=200.0 + i * 30.0)
        fades: dict[str, object] = {}

        def fake_master_track(src, dst, **kwargs):
            fades[Path(src).name] = kwargs.get("fade_out", "not passed")
            shutil.copy(src, dst)
            return {}

        import tools.mastering.master_tracks as master_tracks_mod
        monkeypatch.setattr(master_tracks_mod, "master_track", fake_master_track)
        # Track 2 says no fade; the others have no entry, so they get the default.
        monkeypatch.setattr(shared_mod, "cache", _FakeCache({"02-track": {"fade_out": None}}))

        with _resolve_to(tmp_path):
            result = json.loads(asyncio.run(audio_mod.album_coherence_correct(
                album_slug="test-album", genre="pop", source_subfolder="polished",
                check_subfolder="mastered", anchor_track=1, dry_run=False,
            )))

        assert "error" not in result, result
        assert "02-track.wav" in fades, "track 2 is an outlier and should be re-mastered"
        assert fades["02-track.wav"] is None
        assert all(fade == 3.0 for name, fade in fades.items() if name != "02-track.wav")


# ===========================================================================
# The fix_dynamic_track tool
# ===========================================================================


class TestFixDynamicTrackTool:
    @pytest.mark.parametrize("tracks, expected", [
        ({"01-a": {"fade_out": 8.0}}, [8.0]),
        ({"01-a": {"title": "no row"}}, [3.0]),
        ({"01-a": {"fade_out": None}}, []),
    ])
    def test_the_fade_goes_on_before_the_fix(self, tmp_path, monkeypatch, tracks, expected):
        _sine(tmp_path / "01-a.wav", seconds=3.0)
        fades: list[float] = []
        import tools.mastering.master_tracks as master_tracks_mod
        real = master_tracks_mod.apply_fade_out

        def spy(data, rate, duration=5.0, curve="exponential"):
            fades.append(duration)
            return real(data, rate, duration=duration, curve=curve)

        monkeypatch.setattr(master_tracks_mod, "apply_fade_out", spy)
        monkeypatch.setattr(shared_mod, "cache", _FakeCache(tracks))

        with _resolve_to(tmp_path):
            result = json.loads(asyncio.run(audio_mod.fix_dynamic_track("test-album", "01-a.wav")))

        assert "error" not in result, result
        assert fades == expected
