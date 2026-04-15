"""Tests for MasterAlbumCtx dataclass and _build_notices (#290 D5)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing._album_stages import MasterAlbumCtx, _build_notices  # noqa: E402


def _make_ctx(**kwargs) -> MasterAlbumCtx:
    loop = asyncio.new_event_loop()
    defaults = dict(
        album_slug="test-album", genre="", target_lufs=-14.0,
        ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
        source_subfolder="", freeze_signature=False, new_anchor=False,
        loop=loop,
    )
    defaults.update(kwargs)
    return MasterAlbumCtx(**defaults)


def test_ctx_defaults_are_sane() -> None:
    ctx = _make_ctx()
    assert ctx.album_slug == "test-album"
    assert ctx.stages == {}
    assert ctx.warnings == []
    assert ctx.notices == []
    assert ctx.analysis_results == []
    assert ctx.wav_files == []
    assert ctx.freeze_mode == "fresh"
    assert ctx.frozen_signature is None
    assert ctx.audio_dir is None


def test_ctx_stages_accumulate() -> None:
    ctx = _make_ctx()
    ctx.stages["pre_flight"] = {"status": "pass"}
    ctx.stages["analysis"] = {"status": "pass"}
    assert len(ctx.stages) == 2


def test_ctx_warnings_accumulate() -> None:
    ctx = _make_ctx()
    ctx.warnings.append("warn 1")
    ctx.warnings.append("warn 2")
    assert len(ctx.warnings) == 2


def test_build_notices_no_upsample() -> None:
    ctx = _make_ctx()
    ctx.targets = {"upsampled_from_source": False}
    _build_notices(ctx)
    assert ctx.notices == []


def test_build_notices_upsample_appends_notice() -> None:
    ctx = _make_ctx()
    ctx.targets = {
        "upsampled_from_source": True,
        "source_sample_rate": 44100,
        "output_sample_rate": 96000,
    }
    _build_notices(ctx)
    assert len(ctx.notices) == 1
    assert "96 kHz" in ctx.notices[0]
    assert "44.1 kHz" in ctx.notices[0]
    assert "Hi-Res Lossless" in ctx.notices[0]


def test_build_notices_accumulates_on_repeated_call() -> None:
    # _build_notices is not idempotent — each call appends a notice.
    ctx = _make_ctx()
    ctx.targets = {
        "upsampled_from_source": True,
        "source_sample_rate": 44100,
        "output_sample_rate": 96000,
    }
    _build_notices(ctx)
    _build_notices(ctx)
    assert len(ctx.notices) == 2   # not idempotent by design — caller calls once


def test_build_notices_upsample_skips_when_rates_missing() -> None:
    ctx = _make_ctx()
    ctx.targets = {"upsampled_from_source": True}  # missing source_sample_rate
    _build_notices(ctx)
    assert ctx.notices == []


def test_ctx_independent_instances_dont_share_mutable_defaults() -> None:
    ctx_a = _make_ctx(album_slug="a")
    ctx_b = _make_ctx(album_slug="b")
    ctx_a.warnings.append("only for a")
    assert ctx_b.warnings == []
