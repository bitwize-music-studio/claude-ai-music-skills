"""Integration tests for Stage 5.5 (ADM validation) inside master_album (#290 step 9)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


def _write_sine_wav(path: Path, *, duration: float = 2.0,
                    sample_rate: int = 44100, amplitude: float = 0.3) -> Path:
    import soundfile as sf
    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    sf.write(str(path), np.column_stack([mono, mono]), sample_rate, subtype="PCM_24")
    return path


def test_adm_validation_pass_writes_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ADM stage writes ADM_VALIDATION.md on clean encode."""
    # Mock check fn to return clean result
    def _fake_check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 0,
            "peak_db_decoded": -1.8,
            "ceiling_db": ceiling_db,
            "clips_found": False,
        }
    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _fake_check)

    wav1 = _write_sine_wav(tmp_path / "01.wav")
    wav2 = _write_sine_wav(tmp_path / "02.wav")

    async def _run():
        ctx = album_stages_mod.MasterAlbumCtx(
            album_slug="my-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_event_loop(),
        )
        ctx.audio_dir = tmp_path
        ctx.mastered_files = [wav1, wav2]
        ctx.targets = {"ceiling_db": -1.0, "adm_aac_encoder": "aac"}
        return await album_stages_mod._stage_adm_validation(ctx), ctx

    result, ctx = asyncio.run(_run())

    assert result is None  # no halt
    assert ctx.stages["adm_validation"]["status"] == "pass"
    assert (tmp_path / "ADM_VALIDATION.md").exists()


def test_adm_validation_halt_on_clips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ADM stage halts and returns failure JSON when clips are found."""
    def _fake_check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 3,
            "peak_db_decoded": -0.5,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }
    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _fake_check)

    wav1 = _write_sine_wav(tmp_path / "01.wav")

    async def _run():
        ctx = album_stages_mod.MasterAlbumCtx(
            album_slug="my-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_event_loop(),
        )
        ctx.audio_dir = tmp_path
        ctx.mastered_files = [wav1]
        ctx.targets = {"ceiling_db": -1.0, "adm_aac_encoder": "aac"}
        return await album_stages_mod._stage_adm_validation(ctx), ctx

    result, ctx = asyncio.run(_run())

    assert result is not None  # halted
    payload = json.loads(result)
    assert payload["failed_stage"] == "adm_validation"
    assert "inter-sample" in payload["failure_detail"]["reason"].lower()
    assert (tmp_path / "ADM_VALIDATION.md").exists()
    assert ctx.stages["adm_validation"]["status"] == "fail"
    assert ctx.stages["adm_validation"]["clips_found"] is True


def test_adm_validation_encoder_error_warns_not_halts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ADM stage warns (never halts) when encoder subprocess fails."""
    from tools.mastering.adm_validation import ADMValidationError
    def _boom(path, **kwargs):
        raise ADMValidationError("ffmpeg not available")
    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _boom)

    wav1 = _write_sine_wav(tmp_path / "01.wav")

    async def _run():
        ctx = album_stages_mod.MasterAlbumCtx(
            album_slug="my-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_event_loop(),
        )
        ctx.audio_dir = tmp_path
        ctx.mastered_files = [wav1]
        ctx.targets = {"ceiling_db": -1.0, "adm_aac_encoder": "aac"}
        return await album_stages_mod._stage_adm_validation(ctx), ctx

    result, ctx = asyncio.run(_run())

    assert result is None  # not halted
    assert any("ADM" in n for n in ctx.notices)
    assert ctx.stages["adm_validation"]["status"] == "warn"
