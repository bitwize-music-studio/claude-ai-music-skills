"""Album-mastering analysis measures the right thing on real-shaped audio (#681).

Items 7-9 of #681, on generated Suno-like masters (48 kHz / 16-bit stereo,
-12 to -8 LUFS, sample peaks within 1.5 dB of full scale, sections and a
fade; see ``tests/fixtures/audio/suno_like.py``):

- ``vocal_rms`` after polish describes the file analyzed, not the stem;
- the anchor's ceiling penalty is the limiting a track will get at the
  target, so it no longer picks a quiet ballad over every pop track, and
  still demotes a track the limiter would hit hard;
- ``lra`` is the EBU R128 loudness range, and the anchor and the LRA floor
  use it rather than ``short_term_range``.

Usage:
    python -m pytest tests/unit/mastering/test_analysis_681.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyloudnorm as pyln
import pytest
import soundfile as sf
from scipy.signal import butter, sosfilt

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tests.fixtures.audio.suno_like import make_suno_song  # noqa: E402
from tools.mastering.analyze_tracks import analyze_track  # noqa: E402
from tools.mastering.anchor_selector import select_anchor  # noqa: E402
from tools.mastering.master_tracks import load_genre_presets  # noqa: E402

pytestmark = pytest.mark.unit


def _write(path: Path, data: np.ndarray, rate: int, subtype: str = "PCM_16") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, rate, subtype=subtype)
    return path


def _vocal_stem(mix: np.ndarray, rate: int) -> np.ndarray:
    sos = butter(4, [300 / (rate / 2), 3500 / (rate / 2)], btype="band", output="sos")
    return 0.5 * np.asarray(sosfilt(sos, mix, axis=0))


# ---------------------------------------------------------------------------
# A realistic album, generated once per module
# ---------------------------------------------------------------------------

_ALBUM = {
    # name: (target LUFS, seed, key, sample-peak ceiling)
    "01-first-song.wav": (-9.0, 1, 0, 0.985),
    "02-second-song.wav": (-8.0, 2, 3, 0.985),
    "03-third-song.wav": (-11.0, 3, 5, 0.985),
    "04-ballad.wav": (-12.0, 9, 7, 0.70),  # lo-fi ballad, peaks at -4.3 dBFS
}


@pytest.fixture(scope="module")
def album(tmp_path_factory) -> list[dict]:
    """``analyze_track`` of a 4-track Suno-like album (60 s tracks)."""
    root = tmp_path_factory.mktemp("album681")
    results = []
    for name, (lufs, seed, key, peak) in _ALBUM.items():
        data, rate = make_suno_song(seconds=60.0, target_lufs=lufs, seed=seed, key=key, peak=peak)
        results.append(analyze_track(str(_write(root / name, data, rate))))
    return results


# ---------------------------------------------------------------------------
# Item 9 — lra is the EBU R128 loudness range
# ---------------------------------------------------------------------------


class TestLoudnessRange:
    def test_realistic_song_reads_a_song_lra(self, album) -> None:
        for track in album:
            # A mastered pop song reads 3-8 LU; the ungated max-min range
            # spans the intro and the fade and reads ~25.
            assert 3.0 <= track["lra"] <= 8.0, track["filename"]
            assert track["short_term_range"] > 15.0
            assert track["short_term_range"] - track["lra"] > 10.0

    def test_matches_the_tech_3342_reference(self, tmp_path: Path) -> None:
        data, rate = make_suno_song(seconds=40.0, seed=4)
        path = _write(tmp_path / "song.wav", data, rate)
        read, _ = sf.read(str(path))
        expected = pyln.Meter(rate).loudness_range(read)
        assert analyze_track(str(path))["lra"] == pytest.approx(expected, abs=1e-6)

    def test_over_compressed_song_reads_low(self, tmp_path: Path) -> None:
        """Brickwalled with no section dynamics, a 6 s fade: LRA ~2, not ~9."""
        data, rate = make_suno_song(seconds=150.0, target_lufs=-8.0, seed=4)
        block = 3 * rate
        for s in range(0, len(data) - 6 * rate - block, block):
            seg = data[s:s + block]
            data[s:s + block] = seg * (0.25 / (np.sqrt(np.mean(seg ** 2)) + 1e-12))
        path = _write(tmp_path / "squashed.wav", np.clip(data, -0.98, 0.98), rate)
        result = analyze_track(str(path))
        assert result["lra"] < 3.0
        assert result["short_term_range"] > 5.0

    def test_silence_has_no_lra(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "silent.wav", np.zeros((48000 * 5, 2)), 48000)
        assert analyze_track(str(path))["lra"] is None

    def test_coherence_floor_reads_lra(self) -> None:
        from tools.mastering.coherence import classify_outliers, load_tolerances

        tracks = [
            {"filename": "01.wav", "lra": 5.0, "short_term_range": 0.5},
            {"filename": "02.wav", "lra": 0.5, "short_term_range": 20.0},
        ]
        deltas = [{"index": 1}, {"index": 2}]
        rows = classify_outliers(deltas, tracks, load_tolerances({}), anchor_index_1based=1)
        floor = next(v for v in rows[1]["violations"] if v["metric"] == "lra_floor")
        assert floor["value"] == 0.5
        assert floor["severity"] == "outlier"

    def test_post_qc_floor_reads_lra(self, tmp_path: Path) -> None:
        from handlers.processing import _album_stages as stages

        wav = tmp_path / "01-a.wav"
        wav.touch()

        def _fake_qc(path, _preset=None, _genre=None):
            return {"filename": Path(path).name, "verdict": "PASS", "checks": {}}

        async def _run(row: dict):
            ctx = stages.MasterAlbumCtx(
                album_slug="t", genre="pop", target_lufs=-14.0, ceiling_db=-1.0,
                cut_highmid=None, cut_highs=None, source_subfolder="",
                freeze_signature=False, new_anchor=False, loop=asyncio.get_running_loop(),
            )
            ctx.mastered_files = [wav]
            ctx.preset_dict = {"coherence_lra_floor_lu": 1.0}
            ctx.verify_results = [{"filename": "01-a.wav", **row}]
            return await stages._stage_post_qc(ctx)

        with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
            # Squashed (LRA 0.6) behind a fade (short_term_range 9.3): halts.
            halted = asyncio.run(_run({"lra": 0.6, "short_term_range": 9.3}))
            # A song with LRA 4 that the old range called 0.5 (no fade): passes.
            passed = asyncio.run(_run({"lra": 4.0, "short_term_range": 0.5}))
        assert halted is not None
        assert json.loads(halted)["failure_detail"]["lra_floor_violations"][0]["lra_lu"] == 0.6
        assert passed is None


# ---------------------------------------------------------------------------
# Item 8 — the anchor's ceiling penalty on real Suno masters
# ---------------------------------------------------------------------------


class TestAnchorOnSunoMasters:
    def test_the_ballad_is_not_chosen_over_the_pop_tracks(self, album) -> None:
        peaks = [t["peak_db"] for t in album]
        assert max(peaks[:3]) > -1.6  # Suno-like: pinned near full scale
        # pop: -14 LUFS; the ceiling defaults to -1.0 dBTP.
        result = select_anchor(album, load_genre_presets()["pop"])
        assert result["selected_index"] != 4, result["scores"]
        # Every source is turned down to -14 LUFS: none will be limited.
        for entry in result["scores"]:
            assert entry["ceiling_penalty"] == 0.0
            assert entry["ceiling_penalty_basis"] == "limiting_at_target"

    def test_a_track_the_limiter_would_crush_is_still_demoted(self, album) -> None:
        # A dynamic, peaky track on the album median and the genre's ideal
        # LRA — the best mix and the most representative — whose peaks land
        # 2.5 dB over the ceiling once it is raised to -14 LUFS.
        medians = {k: float(np.median([t[k] for t in album]))
                   for k in ("stl_95", "lra", "low_rms", "vocal_rms")}
        hot = {**album[0], **medians, "filename": "05-hot.wav",
               "lufs": -16.0, "peak_db": -0.5, "lra": 8.0}
        tracks = [*album, hot]
        result = select_anchor(
            tracks, load_genre_presets()["pop"], target_lufs=-14.0, ceiling_db=-1.0,
        )
        hot_score = result["scores"][4]
        assert hot_score["ceiling_penalty"] == pytest.approx(2.5 / 3.0)
        assert hot_score["mix_quality"] == max(s["mix_quality"] for s in result["scores"])
        assert result["selected_index"] != 5

    def test_the_target_comes_from_the_preset_by_default(self, album) -> None:
        jazz = load_genre_presets()["jazz"]  # -16 LUFS
        result = select_anchor(album, jazz)
        assert all(s["ceiling_penalty_basis"] == "limiting_at_target" for s in result["scores"])

    def test_no_loudness_falls_back_to_the_source_peak(self) -> None:
        track = {"filename": "01.wav", "stl_95": -10.0, "lra": 6.0, "low_rms": -20.0,
                 "vocal_rms": -24.0, "peak_db": -1.5,
                 "band_energy": {b: 100 / 7 for b in ("sub_bass", "bass", "low_mid",
                                                     "mid", "high_mid", "high", "air")}}
        result = select_anchor([track], {}, target_lufs=-14.0)
        assert result["scores"][0]["ceiling_penalty_basis"] == "source_peak"
        assert result["scores"][0]["ceiling_penalty"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Item 7 — vocal_rms after polish describes the file analyzed
# ---------------------------------------------------------------------------


@pytest.fixture
def polished_track(tmp_path: Path) -> tuple[Path, np.ndarray, int]:
    """polished/01-song.wav and its polished/01-song/vocals.wav stem."""
    data, rate = make_suno_song(seconds=30.0, seed=1)
    _write(tmp_path / "polished" / "01-song.wav", data, rate, "PCM_24")
    _write(tmp_path / "polished" / "01-song" / "vocals.wav", _vocal_stem(data, rate), rate, "PCM_24")
    return tmp_path, data, rate


class TestVocalRmsFollowsTheMaster:
    def test_master_gain_moves_vocal_rms(self, polished_track) -> None:
        root, data, rate = polished_track
        readings = {}
        for gain_db in (0.0, -6.0):
            master = _write(root / "mastered" / "01-song.wav",
                            data * 10 ** (gain_db / 20), rate, "PCM_24")
            result = analyze_track(str(master))
            assert result["signature_meta"]["vocal_rms_source"] == "stem"
            readings[gain_db] = result["vocal_rms"]
        assert readings[0.0] - readings[-6.0] == pytest.approx(6.0, abs=0.05)

    def test_the_polished_mix_itself_reads_the_raw_stem(self, polished_track) -> None:
        root, _data, _rate = polished_track
        stem, _ = sf.read(str(root / "polished" / "01-song" / "vocals.wav"))
        raw = 20 * np.log10(np.sqrt(np.mean(np.mean(stem, axis=1) ** 2)))
        result = analyze_track(str(root / "polished" / "01-song.wav"))
        assert result["signature_meta"]["vocal_rms_offset_db"] == 0.0
        assert result["vocal_rms"] == pytest.approx(raw, abs=0.01)

    def test_a_stem_with_no_mix_to_relate_it_to_is_not_used(self, tmp_path: Path) -> None:
        # The album-root original next to an orphaned polished stem: nothing
        # says the stem is this render's vocal.
        data, rate = make_suno_song(seconds=30.0, seed=1)
        mix = _write(tmp_path / "01-song.wav", data, rate)
        _write(tmp_path / "polished" / "01-song" / "vocals.wav", _vocal_stem(data, rate), rate)
        result = analyze_track(str(mix))
        assert result["signature_meta"]["vocal_rms_source"] == "band_fallback"

    def test_coherence_after_polish_sees_no_vocal_outliers(self, tmp_path: Path) -> None:
        """The #681 report: three polished tracks, all mastered to -14 LUFS,
        one polished 6 dB quieter. Its stem is 6 dB quieter too, and read raw
        it made two vocal-RMS outliers and a clamped, unconvergent tilt."""
        from handlers import _shared as shared_mod
        from handlers.processing import _helpers as processing_helpers
        from handlers.processing import audio as audio_mod

        for i, (seed, key, gain_db) in enumerate([(1, 0, 0.0), (2, 3, 0.0), (3, 5, -6.0)], 1):
            data, rate = make_suno_song(seconds=30.0, seed=seed, key=key)
            data = data * 10 ** (gain_db / 20)
            name = f"0{i}-song"
            _write(tmp_path / "polished" / f"{name}.wav", data, rate, "PCM_24")
            _write(tmp_path / "polished" / name / "vocals.wav", _vocal_stem(data, rate), rate, "PCM_24")

        class _Cache:
            def __init__(self) -> None:
                self._state: dict = {"albums": {}}

            def get_state(self):
                return self._state

            def get_state_ref(self):
                return self._state

        with patch.object(processing_helpers, "_resolve_audio_dir",
                          lambda slug, *_, **__: (None, tmp_path)), \
             patch.object(shared_mod, "cache", _Cache()):
            result = json.loads(asyncio.run(audio_mod.master_album(
                "t", genre="pop", source_subfolder="polished",
            )))
        assert result.get("failed_stage") is None, result.get("failure_detail")
        corrections = result["stages"]["coherence_correct"].get("corrections", [])
        assert not [c for c in corrections if c.get("status") == "unconvergent"], corrections
        assert result["stages"]["coherence_check"]["outlier_count"] == 0, result["stages"]
