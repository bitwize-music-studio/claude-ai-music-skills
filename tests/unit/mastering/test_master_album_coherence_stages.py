"""Unit tests for Stage 5.1 (coherence check) and Stage 5.2 (coherence correct)
inside the master_album pipeline (#290 steps 5-6)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _album_stages as album_stages_mod  # noqa: E402
from handlers.processing._album_stages import (  # noqa: E402
    MasterAlbumCtx,
    _stage_coherence_check,
    _stage_coherence_correct,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_verify_result(filename: str, lufs: float, **extra) -> dict:
    """Minimal analyze_track-style dict for verify_results."""
    return {
        "filename": filename,
        "lufs": lufs,
        "peak_db": -1.5,
        "stl_95": lufs + 4.0,
        "short_term_range": 6.5,
        "low_rms": lufs - 4.0,
        "vocal_rms": lufs - 2.0,
        **extra,
    }


def _write_sine_wav(path: Path, *, duration: float = 2.0,
                    sample_rate: int = 44100, amplitude: float = 0.3) -> Path:
    import soundfile as sf
    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    sf.write(str(path), np.column_stack([mono, mono]), sample_rate, subtype="PCM_24")
    return path


# ---------------------------------------------------------------------------
# Test 1: coherence check classifies tracks correctly (no outliers)
# ---------------------------------------------------------------------------

def test_coherence_check_classifies_tracks() -> None:
    """Two similar-LUFS tracks produce no outliers → stage status pass."""
    verify_results = [
        _make_verify_result("01-a.wav", lufs=-14.0),
        _make_verify_result("02-b.wav", lufs=-14.1),
    ]

    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": 1}
        ctx.verify_results = verify_results
        ctx.preset_dict = None
        result = await _stage_coherence_check(ctx)
        return result, ctx

    result, ctx = asyncio.run(_run())

    assert result is None, "Stage should not halt"
    assert ctx.coherence_classifications, "Classifications should be populated"
    assert len(ctx.coherence_classifications) == 2
    stage = ctx.stages["coherence_check"]
    assert stage["status"] == "pass"
    assert stage["outlier_count"] == 0
    assert stage["correctable_count"] == 0
    assert stage["anchor_index"] == 1


# ---------------------------------------------------------------------------
# Test 2: coherence check warns when anchor is missing
# ---------------------------------------------------------------------------

def test_coherence_check_warns_without_anchor() -> None:
    """No valid anchor → stage status warn with reason no_anchor."""
    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": None}
        ctx.verify_results = [_make_verify_result("01-a.wav", lufs=-14.0)]
        ctx.preset_dict = None
        result = await _stage_coherence_check(ctx)
        return result, ctx

    result, ctx = asyncio.run(_run())

    assert result is None
    stage = ctx.stages["coherence_check"]
    assert stage["status"] == "warn"
    assert stage["reason"] == "no_anchor"


# ---------------------------------------------------------------------------
# Test 3: coherence correct is a no-op when there are no outliers
# ---------------------------------------------------------------------------

def test_coherence_correct_no_op_when_no_outliers() -> None:
    """Empty classifications → status pass, iterations=0, no corrections."""
    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": 1}
        ctx.coherence_classifications = []
        ctx.preset_dict = None
        result = await _stage_coherence_correct(ctx)
        return result, ctx

    result, ctx = asyncio.run(_run())

    assert result is None
    stage = ctx.stages["coherence_correct"]
    assert stage["status"] == "pass"
    assert stage["iterations"] == 0
    assert stage["corrections"] == []


# ---------------------------------------------------------------------------
# Test 4: coherence correct clamps to 1.5 dB window
# ---------------------------------------------------------------------------

def test_coherence_correct_clamps_to_1_5_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Track 4 dB below anchor — build_correction_plan targets anchor (−14.0).
    That target is within the ±1.5 dB window, so no clamp fires.
    The test verifies the applied target equals the unclamped anchor_lufs.
    See test_coherence_correct_clamps_when_target_below_window for the clamp path."""
    anchor_lufs = -14.0
    track2_lufs = -18.0

    source_dir = tmp_path / "polished"
    source_dir.mkdir()
    output_dir = tmp_path / "mastered"
    output_dir.mkdir()

    _write_sine_wav(source_dir / "01-anchor.wav")
    _write_sine_wav(source_dir / "02-outlier.wav", amplitude=0.1)

    import shutil
    shutil.copy(source_dir / "01-anchor.wav", output_dir / "01-anchor.wav")
    shutil.copy(source_dir / "02-outlier.wav", output_dir / "02-outlier.wav")

    verify_results = [
        _make_verify_result("01-anchor.wav", lufs=anchor_lufs),
        _make_verify_result("02-outlier.wav", lufs=track2_lufs),
    ]

    from tools.mastering.album_signature import compute_anchor_deltas
    from tools.mastering.coherence import classify_outliers, load_tolerances
    tolerances = load_tolerances(None)
    deltas = compute_anchor_deltas(verify_results, anchor_index_1based=1)
    classifications = classify_outliers(
        deltas, verify_results, tolerances, anchor_index_1based=1
    )
    assert classifications[1]["is_outlier"], "Track 2 should be a LUFS outlier"

    captured_calls: list[dict] = []

    def _fake_master_track(src: str, dst: str, **kwargs) -> dict:
        captured_calls.append({"src": src, "dst": dst, **kwargs})
        shutil.copy(src, dst)
        return {"status": "ok"}

    monkeypatch.setattr(album_stages_mod, "_COHERENCE_MAX_ITERATIONS", 1)
    import tools.mastering.master_tracks as _mt_mod
    monkeypatch.setattr(_mt_mod, "master_track", _fake_master_track)

    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": 1}
        ctx.verify_results = verify_results
        ctx.coherence_classifications = classifications
        ctx.source_dir = source_dir
        ctx.output_dir = output_dir
        ctx.mastered_files = [
            output_dir / "01-anchor.wav",
            output_dir / "02-outlier.wav",
        ]
        ctx.effective_ceiling = -1.0
        ctx.effective_compress = 1.0
        ctx.effective_preset = {}
        ctx.preset_dict = None
        result = await _stage_coherence_correct(ctx)
        return result, ctx

    result, ctx = asyncio.run(_run())

    assert result is None
    assert len(captured_calls) == 1, f"Expected 1 call, got {len(captured_calls)}"
    applied = captured_calls[0]["target_lufs"]
    # build_correction_plan sets corrected_target_lufs = anchor_lufs = -14.0.
    # Clamp window: [-15.5, -12.5]. -14.0 is within, so no clamp fires.
    assert applied == pytest.approx(anchor_lufs, abs=1e-6), (
        f"Expected target_lufs={anchor_lufs}, got {applied}"
    )


# ---------------------------------------------------------------------------
# Test 5: clamping fires when outlier is far below window
# ---------------------------------------------------------------------------

def test_coherence_correct_clamps_when_target_below_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When build_correction_plan returns a target < anchor - 1.5, it gets clamped to -15.5."""
    anchor_lufs = -14.0
    fake_plan_target = -20.0  # way outside the ±1.5 window

    source_dir = tmp_path / "polished"
    source_dir.mkdir()
    output_dir = tmp_path / "mastered"
    output_dir.mkdir()
    _write_sine_wav(source_dir / "02-outlier.wav", amplitude=0.05)

    import shutil
    shutil.copy(source_dir / "02-outlier.wav", output_dir / "02-outlier.wav")
    _write_sine_wav(output_dir / "01-anchor.wav")

    captured_calls: list[dict] = []

    def _fake_master_track(src: str, dst: str, **kwargs) -> dict:
        captured_calls.append({"src": src, "dst": dst, **kwargs})
        shutil.copy(src, dst)
        return {"status": "ok"}

    import tools.mastering.master_tracks as _mt_mod
    monkeypatch.setattr(_mt_mod, "master_track", _fake_master_track)

    def _fake_plan(classifications, analysis_results, anchor_index_1based):
        return {
            "anchor_index": anchor_index_1based,
            "anchor_lufs": anchor_lufs,
            "corrections": [
                {
                    "index": 2,
                    "filename": "02-outlier.wav",
                    "correctable": True,
                    "corrected_target_lufs": fake_plan_target,
                    "reason": "LUFS outlier: delta=-6.00, tolerance=±0.50",
                }
            ],
            "skipped": [{"index": 1, "filename": "01-anchor.wav", "reason": "is_anchor"}],
        }

    monkeypatch.setattr(album_stages_mod, "_coherence_build_plan", _fake_plan)
    monkeypatch.setattr(album_stages_mod, "_COHERENCE_MAX_ITERATIONS", 1)

    verify_results = [
        _make_verify_result("01-anchor.wav", lufs=anchor_lufs),
        _make_verify_result("02-outlier.wav", lufs=-20.0),
    ]

    from tools.mastering.album_signature import compute_anchor_deltas
    from tools.mastering.coherence import classify_outliers, load_tolerances
    tolerances = load_tolerances(None)
    deltas = compute_anchor_deltas(verify_results, anchor_index_1based=1)
    classifications = classify_outliers(
        deltas, verify_results, tolerances, anchor_index_1based=1
    )

    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": 1}
        ctx.verify_results = verify_results
        ctx.coherence_classifications = classifications
        ctx.source_dir = source_dir
        ctx.output_dir = output_dir
        ctx.mastered_files = [
            output_dir / "01-anchor.wav",
            output_dir / "02-outlier.wav",
        ]
        ctx.effective_ceiling = -1.0
        ctx.effective_compress = 1.0
        ctx.effective_preset = {}
        ctx.preset_dict = None
        result = await _stage_coherence_correct(ctx)
        return result, ctx

    result, ctx = asyncio.run(_run())
    assert result is None

    # Clamped target = anchor_lufs - 1.5 = -15.5 (not the raw -20.0)
    assert len(captured_calls) == 1
    applied = captured_calls[0]["target_lufs"]
    expected_clamped = anchor_lufs - 1.5  # -15.5
    assert applied == pytest.approx(expected_clamped, abs=1e-6), (
        f"Expected clamped target {expected_clamped}, got {applied}"
    )
