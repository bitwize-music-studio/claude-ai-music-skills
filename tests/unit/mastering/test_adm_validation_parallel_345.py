"""Tests for parallel ADM validation (issue #345).

_stage_adm_validation used to encode+decode each mastered track serially
(two ffmpeg subprocesses per track with a tempdir round-trip), which dominated
mastering wall-clock time. The stage now runs the per-track ADM checks
concurrently (bounded to CPU count), while preserving:
  - result ORDER (results line up with ctx.mastered_files),
  - error partitioning (ADMValidationError → encoder_errors, warn not halt),
  - the clip → halt verdict,
  - propagation of non-ADMValidationError exceptions.

Usage:
    python -m pytest tests/unit/mastering/test_adm_validation_parallel_345.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _album_stages as album_stages_mod  # noqa: E402
from tools.mastering.adm_validation import ADMValidationError  # noqa: E402


def _clean_result(path, encoder="aac", ceiling_db=-1.0):
    return {
        "filename": Path(path).name,
        "encoder_used": encoder,
        "clip_count": 0,
        "peak_db_decoded": -1.8,
        "ceiling_db": ceiling_db,
        "clips_found": False,
    }


def _make_ctx(tmp_path: Path, wavs: list[Path]):
    ctx = album_stages_mod.MasterAlbumCtx(
        album_slug="my-album", genre="", target_lufs=-14.0,
        ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
        source_subfolder="", freeze_signature=False, new_anchor=False,
        loop=asyncio.get_running_loop(),
    )
    ctx.audio_dir = tmp_path
    ctx.mastered_files = wavs
    ctx.targets = {"ceiling_db": -1.0, "adm_aac_encoder": "aac"}
    return ctx


@pytest.mark.unit
class TestParallelExecution:
    def test_checks_run_concurrently(self, tmp_path, monkeypatch):
        """The per-track ADM checks overlap — serial code caps concurrency at 1.

        This is the #345 regression pin: on the old serial loop max observed
        concurrency is 1; the parallel stage reaches >1.
        """
        # Pin the concurrency bound so the test is deterministic on any host.
        monkeypatch.setattr(album_stages_mod.os, "cpu_count", lambda: 4)

        lock = threading.Lock()
        state = {"current": 0, "max": 0}

        def _slow_check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
            with lock:
                state["current"] += 1
                state["max"] = max(state["max"], state["current"])
            time.sleep(0.05)
            with lock:
                state["current"] -= 1
            return _clean_result(path, encoder, ceiling_db)

        monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _slow_check)
        wavs = [tmp_path / f"{i:02d}.wav" for i in range(1, 5)]
        for w in wavs:
            w.write_bytes(b"\x00")

        async def _run():
            ctx = _make_ctx(tmp_path, wavs)
            return await album_stages_mod._stage_adm_validation(ctx), ctx

        result, ctx = asyncio.run(_run())

        assert result is None
        assert state["max"] >= 2, "ADM checks did not run concurrently"
        assert len(ctx.adm_validation_results) == 4

    def test_results_preserve_input_order(self, tmp_path, monkeypatch):
        """results line up with ctx.mastered_files regardless of finish order."""
        monkeypatch.setattr(album_stages_mod.os, "cpu_count", lambda: 4)

        # Make later files finish FIRST, so order can only be right if the
        # stage preserves input order rather than completion order.
        delays = {"01.wav": 0.06, "02.wav": 0.04, "03.wav": 0.02, "04.wav": 0.0}

        def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
            time.sleep(delays[Path(path).name])
            return _clean_result(path, encoder, ceiling_db)

        monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
        wavs = [tmp_path / f"{i:02d}.wav" for i in range(1, 5)]
        for w in wavs:
            w.write_bytes(b"\x00")

        async def _run():
            ctx = _make_ctx(tmp_path, wavs)
            await album_stages_mod._stage_adm_validation(ctx)
            return ctx

        ctx = asyncio.run(_run())
        assert [r["filename"] for r in ctx.adm_validation_results] == [
            "01.wav", "02.wav", "03.wav", "04.wav",
        ]


@pytest.mark.unit
class TestBehaviorPreserved:
    def test_encoder_error_warns_not_halts_and_partitions(self, tmp_path, monkeypatch):
        """A track raising ADMValidationError → warn (return None), partitioned."""
        def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
            if Path(path).name == "02.wav":
                raise ADMValidationError("ffmpeg boom")
            return _clean_result(path, encoder, ceiling_db)

        monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
        wavs = [tmp_path / f"{i:02d}.wav" for i in range(1, 4)]
        for w in wavs:
            w.write_bytes(b"\x00")

        async def _run():
            ctx = _make_ctx(tmp_path, wavs)
            return await album_stages_mod._stage_adm_validation(ctx), ctx

        result, ctx = asyncio.run(_run())

        assert result is None  # encoder error warns, never halts
        assert ctx.stages["adm_validation"]["status"] == "warn"
        # Good tracks kept, in order; the failed one is not in results.
        assert [r["filename"] for r in ctx.adm_validation_results] == [
            "01.wav", "03.wav",
        ]
        assert any("02.wav" in e for e in ctx.stages["adm_validation"]["errors"])

    def test_clipping_track_halts(self, tmp_path, monkeypatch):
        """A clipping track still halts with failure JSON (verdict unchanged)."""
        def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
            r = _clean_result(path, encoder, ceiling_db)
            if Path(path).name == "02.wav":
                r["clips_found"] = True
                r["clip_count"] = 5
                r["peak_db_decoded"] = -0.2
            return r

        monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
        wavs = [tmp_path / f"{i:02d}.wav" for i in range(1, 4)]
        for w in wavs:
            w.write_bytes(b"\x00")

        async def _run():
            ctx = _make_ctx(tmp_path, wavs)
            return await album_stages_mod._stage_adm_validation(ctx), ctx

        result, ctx = asyncio.run(_run())

        assert result is not None
        parsed = json.loads(result)
        assert parsed["stages"]["adm_validation"]["status"] == "fail"
        assert parsed["stages"]["adm_validation"]["tracks_with_clips"] == 1

    def test_non_adm_exception_propagates(self, tmp_path, monkeypatch):
        """A non-ADMValidationError is not swallowed — it escapes the stage."""
        def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
        wav = tmp_path / "01.wav"
        wav.write_bytes(b"\x00")

        async def _run():
            ctx = _make_ctx(tmp_path, [wav])
            return await album_stages_mod._stage_adm_validation(ctx)

        with pytest.raises(RuntimeError, match="unexpected"):
            asyncio.run(_run())
