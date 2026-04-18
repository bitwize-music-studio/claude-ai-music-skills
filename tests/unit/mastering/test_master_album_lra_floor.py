"""Tests for LRA floor hard-fail in _stage_post_qc (#290 step 10)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


def _make_qc_pass(filename: str) -> dict:
    """Return a minimal PASS result from qc_track for the given filename."""
    return {
        "filename": filename,
        "verdict": "PASS",
        "checks": {},
    }


def _make_verify_result(filename: str, short_term_range: float) -> dict:
    """Return a minimal analyze_track result with the given LRA."""
    return {
        "filename": filename,
        "lufs": -14.0,
        "peak_db": -1.5,
        "short_term_range": short_term_range,
    }


def test_lra_floor_fail_halts_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A track with LRA 3.0 LU below a floor of 6.0 LU must halt post_qc."""
    wav = tmp_path / "01-track.wav"
    wav.touch()

    def _fake_qc(path, _preset=None, _genre=None):
        return _make_qc_pass(Path(path).name)

    with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
        async def _run():
            ctx = album_stages_mod.MasterAlbumCtx(
                album_slug="lra-test", genre="", target_lufs=-14.0,
                ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
                source_subfolder="", freeze_signature=False, new_anchor=False,
                loop=asyncio.get_running_loop(),
            )
            ctx.mastered_files = [wav]
            ctx.preset_dict = {"coherence_lra_floor_lu": 6.0}
            ctx.verify_results = [_make_verify_result("01-track.wav", short_term_range=3.0)]
            return await album_stages_mod._stage_post_qc(ctx), ctx

        result, ctx = asyncio.run(_run())

    assert result is not None, "Expected halt JSON but got None"
    payload = json.loads(result)
    assert payload["failed_stage"] == "post_qc"
    assert ctx.stages["post_qc"]["status"] == "fail"
    details = payload["failure_detail"]["lra_floor_violations"]
    assert len(details) == 1
    assert details[0]["filename"] == "01-track.wav"
    assert details[0]["lra_lu"] == pytest.approx(3.0)
    assert details[0]["floor_lu"] == pytest.approx(6.0)


def test_lra_floor_pass_does_not_halt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A track with LRA 9.0 LU above a floor of 6.0 LU must not halt."""
    wav = tmp_path / "01-track.wav"
    wav.touch()

    def _fake_qc(path, _preset=None, _genre=None):
        return _make_qc_pass(Path(path).name)

    with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
        async def _run():
            ctx = album_stages_mod.MasterAlbumCtx(
                album_slug="lra-test", genre="", target_lufs=-14.0,
                ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
                source_subfolder="", freeze_signature=False, new_anchor=False,
                loop=asyncio.get_running_loop(),
            )
            ctx.mastered_files = [wav]
            ctx.preset_dict = {"coherence_lra_floor_lu": 6.0}
            ctx.verify_results = [_make_verify_result("01-track.wav", short_term_range=9.0)]
            return await album_stages_mod._stage_post_qc(ctx), ctx

        result, ctx = asyncio.run(_run())

    assert result is None, f"Expected no halt but got: {result}"
    assert ctx.stages["post_qc"]["status"] == "pass"


def test_lra_floor_skipped_when_no_preset(
    tmp_path: Path,
) -> None:
    """When preset_dict is None the LRA floor check is skipped entirely."""
    wav = tmp_path / "01-track.wav"
    wav.touch()

    def _fake_qc(path, _preset=None, _genre=None):
        return _make_qc_pass(Path(path).name)

    with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
        async def _run():
            ctx = album_stages_mod.MasterAlbumCtx(
                album_slug="lra-test", genre="", target_lufs=-14.0,
                ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
                source_subfolder="", freeze_signature=False, new_anchor=False,
                loop=asyncio.get_running_loop(),
            )
            ctx.mastered_files = [wav]
            ctx.preset_dict = None  # no preset loaded
            # Low LRA that would normally fail
            ctx.verify_results = [_make_verify_result("01-track.wav", short_term_range=1.0)]
            return await album_stages_mod._stage_post_qc(ctx), ctx

        result, ctx = asyncio.run(_run())

    assert result is None, f"Expected no halt but got: {result}"
    assert ctx.stages["post_qc"]["status"] == "pass"
