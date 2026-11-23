"""Delivery format and ceiling reach every master (#681, items 1-6).

Each test sets up a case where the wrong answer is distinguishable from the
right one: a config that differs from what the presets used to ship, a
ceiling tighter than the opus-safe one, a 16-bit target, frozen tolerances
that differ from the genre's.

Usage:
    python -m pytest tests/unit/mastering/test_delivery_format_681.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pyloudnorm as pyln
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as shared_mod  # noqa: E402
from handlers.processing import _album_stages as album_stages_mod  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from tools.mastering import config as mastering_config_mod  # noqa: E402
from tools.mastering.config import (  # noqa: E402
    DEFAULT_MASTERING_CONFIG,
    build_delivery_targets,
    build_effective_preset,
)
from tools.mastering.master_tracks import measure_true_peak  # noqa: E402

pytestmark = pytest.mark.unit

# A config that differs from everything the presets used to ship (24/96000).
LEGACY_CFG = {
    **DEFAULT_MASTERING_CONFIG,
    "delivery_bit_depth": 16,
    "delivery_sample_rate": 44100,
}


class _Cache:
    def __init__(self, album: dict | None = None) -> None:
        self._state = {"albums": {"test-album": {"tracks": {}, **(album or {})}}}

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _resolve_to(audio_dir: Path):
    return patch.object(
        processing_helpers, "_resolve_audio_dir",
        lambda slug, *_, **__: (None, audio_dir),
    )


def _cfg(values: dict):
    return patch.object(mastering_config_mod, "load_mastering_config", return_value=values)


def _tremolo(path: Path, *, seconds: float = 30.0, rate: int = 44100,
             freq: float = 440.0, amplitude: float = 0.3) -> Path:
    """Tremolo'd tone: enough loudness range for the LRA floor."""
    t = np.arange(int(seconds * rate)) / rate
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t)
    mono = amplitude * np.sin(2 * np.pi * freq * t) * env
    sf.write(str(path), np.column_stack([mono, mono]), rate, subtype="PCM_16")
    return path


def _dynamic(path: Path, *, seconds: float = 10.0, rate: int = 44100) -> Path:
    """Quiet verse, loud chorus, hot transients: a fix_dynamic candidate."""
    rng = np.random.default_rng(7)
    n = int(seconds * rate)
    t = np.arange(n) / rate
    env = np.where((t % 4.0) < 2.0, 0.05, 0.6)
    mono = env * np.sin(2 * np.pi * 220 * t) + 0.02 * rng.standard_normal(n)
    mono[:: rate // 2] = 0.99  # transients pinned near full scale
    sf.write(str(path), np.column_stack([mono, mono * 0.97]), rate, subtype="PCM_24")
    return path


def _true_peak_db(data: np.ndarray, rate: int) -> float:
    return float(20 * np.log10(measure_true_peak(data, rate)))


# ---------------------------------------------------------------------------
# Item 1 — the shipped presets do not clobber the configured delivery format
# ---------------------------------------------------------------------------


class TestPresetsHonourConfiguredFormat:
    @pytest.mark.parametrize("genre", ["pop", "metal", "electronic", "jazz"])
    def test_config_16_44100_survives_a_genre_preset(self, genre: str) -> None:
        with _cfg(LEGACY_CFG):
            bundle = build_effective_preset(
                genre=genre, target_lufs_arg=None, ceiling_db_arg=None,
            )
        assert bundle["targets"]["output_bits"] == 16
        assert bundle["targets"]["output_sample_rate"] == 44100
        # Dither follows the 16-bit target, not a 24-bit preset value.
        assert bundle["effective_preset"]["output_bits"] == 16
        assert bundle["effective_preset"]["dither_bits"] == 16
        assert bundle["effective_preset"]["output_sample_rate"] == 44100

    def test_shipped_presets_leave_the_format_unset(self) -> None:
        from tools.mastering.master_tracks import load_genre_presets

        for genre, preset in load_genre_presets().items():
            assert preset["output_bits"] == 0, genre
            assert preset["output_sample_rate"] == 0, genre
            assert preset["dither_bits"] == 0, genre

    def test_a_user_override_still_forces_one_genre(self, tmp_path, monkeypatch) -> None:
        from tests.unit.mixing._presets import point_overrides_at

        overrides = tmp_path / "overrides"
        overrides.mkdir()
        (overrides / "mastering-presets.yaml").write_text(
            "genres:\n  pop:\n    output_bits: 24\n    output_sample_rate: 48000\n",
        )
        point_overrides_at(monkeypatch, overrides)
        with _cfg(LEGACY_CFG):
            pop = build_effective_preset(genre="pop", target_lufs_arg=None, ceiling_db_arg=None)
            rock = build_effective_preset(genre="rock", target_lufs_arg=None, ceiling_db_arg=None)
        assert (pop["targets"]["output_bits"], pop["targets"]["output_sample_rate"]) == (24, 48000)
        assert pop["effective_preset"]["dither_bits"] == 24
        assert (rock["targets"]["output_bits"], rock["targets"]["output_sample_rate"]) == (16, 44100)

    def test_master_album_writes_the_configured_format(self, tmp_path: Path) -> None:
        for i, freq in enumerate([440.0, 660.0], start=1):
            _tremolo(tmp_path / f"0{i}-track.wav", freq=freq)
        with _resolve_to(tmp_path), patch.object(shared_mod, "cache", _Cache()), _cfg(LEGACY_CFG):
            result = json.loads(asyncio.run(
                audio_mod.master_album("test-album", genre="electronic"),
            ))
        assert result.get("failed_stage") is None, result
        assert result["settings"]["output_bits"] == 16
        assert result["settings"]["output_sample_rate"] == 44100
        for name in ("01-track.wav", "02-track.wav"):
            info = sf.info(str(tmp_path / "mastered" / name))
            assert (info.subtype, info.samplerate) == ("PCM_16", 44100)

    def test_master_track_treats_zero_as_unset(self, tmp_path: Path) -> None:
        from tools.mastering.master_tracks import load_genre_presets, master_track

        src = _tremolo(tmp_path / "in.wav", seconds=5.0)
        out = tmp_path / "out.wav"
        master_track(src, out, preset=dict(load_genre_presets()["pop"]))
        info = sf.info(str(out))
        # Not dithered at 0 bits (noise at full scale) nor written 16-bit.
        assert info.subtype == "PCM_24"
        data, rate = sf.read(str(out))
        assert pyln.Meter(rate).integrated_loudness(data) == pytest.approx(-14.0, abs=0.5)


# ---------------------------------------------------------------------------
# Item 2 — opus_safe never loosens a tighter ceiling
# ---------------------------------------------------------------------------


class TestOpusSafeOnlyTightens:
    @pytest.mark.parametrize("config_ceiling, expected", [
        (-2.0, -2.0),   # tighter than opus-safe: kept
        (-1.0, -1.5),   # looser: tightened
        (-0.5, -1.5),
    ])
    def test_min_of_config_and_opus_safe(self, config_ceiling, expected) -> None:
        targets = build_delivery_targets(
            {**DEFAULT_MASTERING_CONFIG, "true_peak_ceiling": config_ceiling},
            preset={"opus_safe": 1.0},
            target_lufs_arg=None, ceiling_db_arg=None,
        )
        assert targets["ceiling_db"] == expected

    def test_metal_with_a_minus_2_config(self) -> None:
        with _cfg({**DEFAULT_MASTERING_CONFIG, "true_peak_ceiling": -2.0}):
            bundle = build_effective_preset(genre="metal", target_lufs_arg=None, ceiling_db_arg=None)
        assert bundle["settings"]["ceiling_db"] == -2.0


# ---------------------------------------------------------------------------
# Item 3 — fix_dynamic_track writes the delivery format
# ---------------------------------------------------------------------------


class TestFixDynamicTrackDelivers:
    def _run(self, audio_dir: Path, cfg: dict, album: dict | None = None, **kw) -> dict:
        with _resolve_to(audio_dir), patch.object(shared_mod, "cache", _Cache(album)), _cfg(cfg):
            return json.loads(asyncio.run(
                audio_mod.fix_dynamic_track("test-album", "01-a.wav", **kw),
            ))

    def test_default_config_and_album_genre(self, tmp_path: Path) -> None:
        _dynamic(tmp_path / "01-a.wav")
        result = self._run(tmp_path, DEFAULT_MASTERING_CONFIG, album={"genre": "jazz"})
        assert "error" not in result, result
        out = tmp_path / "mastered" / "01-a.wav"
        info = sf.info(str(out))
        assert (info.subtype, info.samplerate) == ("PCM_24", 96000)
        data, rate = sf.read(str(out))
        # jazz targets -16 LUFS; the old tool always aimed at -14.
        assert pyln.Meter(rate).integrated_loudness(data) == pytest.approx(-16.0, abs=0.6)
        assert _true_peak_db(data, rate) <= -1.0 + 0.05
        assert result["settings"]["genre"] == "jazz"

    def test_configured_16_bit_48k_and_tight_ceiling(self, tmp_path: Path) -> None:
        _dynamic(tmp_path / "01-a.wav")
        cfg = {**DEFAULT_MASTERING_CONFIG, "delivery_bit_depth": 16,
               "delivery_sample_rate": 48000, "true_peak_ceiling": -2.0}
        result = self._run(tmp_path, cfg)
        assert "error" not in result, result
        out = tmp_path / "mastered" / "01-a.wav"
        info = sf.info(str(out))
        assert (info.subtype, info.samplerate) == ("PCM_16", 48000)
        data, rate = sf.read(str(out))
        assert _true_peak_db(data, rate) <= -2.0 + 0.05

    def test_unknown_explicit_genre_is_an_error(self, tmp_path: Path) -> None:
        _dynamic(tmp_path / "01-a.wav", seconds=2.0)
        result = self._run(tmp_path, DEFAULT_MASTERING_CONFIG, genre="not-a-genre")
        assert result["error"] == "Unknown genre: not-a-genre"
        assert not (tmp_path / "mastered" / "01-a.wav").exists()


# ---------------------------------------------------------------------------
# Item 4 — master_with_reference delivers the format and respects the ceiling
# ---------------------------------------------------------------------------


class TestReferenceMasterDelivers:
    @staticmethod
    def _matchering(rate: int = 44100):
        """Stand-in for matchering: renders a loud float file, overs included."""
        calls: dict = {}

        def _result(file, subtype, use_limiter=True, normalize=True):
            calls["result"] = {"subtype": subtype, "use_limiter": use_limiter,
                               "normalize": normalize}
            return SimpleNamespace(file=file)

        def _process(target, reference, results):
            t = np.arange(int(3.0 * rate)) / rate
            mono = 1.3 * np.sin(2 * np.pi * 440 * t)  # +2.3 dBFS: matchering, unlimited
            sf.write(results[0].file, np.column_stack([mono, mono]), rate, subtype="FLOAT")

        return SimpleNamespace(Result=_result, process=_process), calls

    def test_delivers_configured_format_under_the_ceiling(self, tmp_path: Path) -> None:
        from tools.mastering import reference_master as ref_mod

        mg, calls = self._matchering()
        out = tmp_path / "out.wav"
        with patch.object(ref_mod, "mg", mg):
            written = ref_mod.master_with_reference(
                tmp_path / "t.wav", tmp_path / "r.wav", out,
                output_bits=24, output_sample_rate=96000, ceiling_db=-1.0,
            )
        assert calls["result"] == {"subtype": "FLOAT", "use_limiter": False, "normalize": False}
        info = sf.info(str(out))
        assert (info.subtype, info.samplerate) == ("PCM_24", 96000)
        data, rate = sf.read(str(out))
        assert _true_peak_db(data, rate) <= -1.0 + 0.05
        assert written["output_bits"] == 24 and written["sample_rate"] == 96000
        assert not list(tmp_path.glob(".matchering_*")), "temp render left behind"

    def test_handler_uses_the_album_delivery_targets(self, tmp_path: Path) -> None:
        from tools.mastering import reference_master as ref_mod

        _tremolo(tmp_path / "ref.wav", seconds=3.0)
        _tremolo(tmp_path / "01-a.wav", seconds=3.0)
        mg, _ = self._matchering()
        cfg = {**DEFAULT_MASTERING_CONFIG, "delivery_bit_depth": 16,
               "delivery_sample_rate": 48000, "true_peak_ceiling": -2.0}
        with _resolve_to(tmp_path), patch.object(shared_mod, "cache", _Cache()), \
             patch.object(processing_helpers, "_check_matchering", return_value=None), \
             patch.object(ref_mod, "mg", mg), _cfg(cfg):
            result = json.loads(asyncio.run(
                audio_mod.master_with_reference("test-album", "ref.wav", "01-a.wav"),
            ))
        assert result["summary"]["success"] == 1, result
        assert result["settings"] == {"output_bits": 16, "output_sample_rate": 48000,
                                      "ceiling_db": -2.0}
        info = sf.info(str(tmp_path / "mastered" / "01-a.wav"))
        assert (info.subtype, info.samplerate) == ("PCM_16", 48000)
        data, rate = sf.read(str(tmp_path / "mastered" / "01-a.wav"))
        assert _true_peak_db(data, rate) <= -2.0 + 0.05


# ---------------------------------------------------------------------------
# Item 5 — a frozen re-master uses the tolerances it stored
# ---------------------------------------------------------------------------


def _ctx(loop) -> album_stages_mod.MasterAlbumCtx:
    return album_stages_mod.MasterAlbumCtx(
        album_slug="test-album", genre="pop", target_lufs=-14.0,
        ceiling_db=-1.0, cut_highmid=None, cut_highs=None,
        source_subfolder="", freeze_signature=True, new_anchor=False,
        loop=loop,
    )


def _verify(name: str, **overrides) -> dict:
    row = {"filename": name, "lufs": -14.0, "peak_db": -1.5, "stl_95": -12.0,
           "short_term_range": 9.0, "lra": 5.0, "low_rms": -20.0, "vocal_rms": -24.0,
           "band_energy": {}}
    row.update(overrides)
    return row


class TestFrozenTolerancesAreUsed:
    def test_coherence_check_uses_the_stored_band(self) -> None:
        async def _run():
            ctx = _ctx(asyncio.get_running_loop())
            ctx.preset_dict = {"coherence_low_rms_db": 2.0}
            # What stage 2b does with a signature's tolerances.
            ctx.effective_preset = {"coherence_low_rms_db": 0.5}
            ctx.anchor_result = {"selected_index": 1}
            ctx.verify_results = [_verify("01-a.wav"), _verify("02-b.wav", low_rms=-21.0)]
            await album_stages_mod._stage_coherence_check(ctx)
            return ctx

        ctx = asyncio.run(_run())
        # 1 dB off the anchor: within the genre's 2.0, outside the stored 0.5.
        assert ctx.stages["coherence_check"]["outlier_count"] == 1

    def test_post_qc_uses_the_stored_lra_floor(self, tmp_path: Path) -> None:
        wav = tmp_path / "01-a.wav"
        wav.touch()

        def _fake_qc(path, _preset=None, _genre=None, _ceiling=None):
            return {"filename": Path(path).name, "verdict": "PASS", "checks": {}}

        async def _run():
            ctx = _ctx(asyncio.get_running_loop())
            ctx.mastered_files = [wav]
            ctx.preset_dict = {"coherence_lra_floor_lu": 1.0}
            ctx.effective_preset = {"coherence_lra_floor_lu": 6.0}
            ctx.verify_results = [_verify("01-a.wav", short_term_range=3.0, lra=3.0)]
            return await album_stages_mod._stage_post_qc(ctx)

        with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
            result = asyncio.run(_run())
        assert result is not None, "the stored 6.0 LU floor should halt a 3.0 LU track"
        detail = json.loads(result)["failure_detail"]["lra_floor_violations"][0]
        assert detail["floor_lu"] == 6.0


# ---------------------------------------------------------------------------
# Item 6 — the archival copy is the pre-downconvert float
# ---------------------------------------------------------------------------


class TestArchivalIsPreDownconvert:
    def test_archival_float_is_not_the_16_bit_file(self, tmp_path: Path) -> None:
        for i, freq in enumerate([440.0, 660.0], start=1):
            _tremolo(tmp_path / f"0{i}-track.wav", seconds=4.0, freq=freq)
        cfg = {**LEGACY_CFG, "archival_enabled": True}
        with _resolve_to(tmp_path), patch.object(shared_mod, "cache", _Cache()), _cfg(cfg):
            result = json.loads(asyncio.run(audio_mod.master_album("test-album")))
        assert result.get("failed_stage") is None, result
        assert result["stages"]["archival"]["from_delivered"] is None
        assert not (tmp_path / ".archival_staging").exists()

        for name in ("01-track.wav", "02-track.wav"):
            arch, a_rate = sf.read(str(tmp_path / "archival" / name), dtype="float64")
            dlv, d_rate = sf.read(str(tmp_path / "mastered" / name), dtype="float64")
            assert sf.info(str(tmp_path / "archival" / name)).subtype == "FLOAT"
            assert a_rate == d_rate == 44100
            assert arch.shape == dlv.shape
            # Off the 16-bit grid: it was never truncated to 16 bits...
            steps = arch * 32768.0
            assert np.mean(np.abs(steps - np.round(steps)) > 1e-3) > 0.5
            # ...and it is the same master, before dither (TPDF: < 1 LSB each way).
            assert np.max(np.abs(arch - dlv)) < 2.0 / 32768.0
