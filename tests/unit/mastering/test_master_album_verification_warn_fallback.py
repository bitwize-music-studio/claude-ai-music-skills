"""Verification must warn-fallback (not halt) when recovery was attempted
but fix_dynamic reported converged=False. Regression for bug #4 — the
pipeline used to hard-halt at master:verification, skipping all stages
from coherence_check through status_update."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx


def _fake_analyze(target_lufs: float, off_by_lufs: float, peak_db: float):
    """Build a fake analyze_track result for a one-track album."""
    def _inner(path: str) -> dict:
        return {
            "filename":   Path(path).name,
            "lufs":       target_lufs + off_by_lufs,
            "peak_db":    peak_db,
            "short_term_range": 6.0,
            "stl_95":     9.0,
            "low_rms":    -30.0,
            "vocal_rms":  -22.0,
        }
    return _inner


def _fake_fix_dynamic_diverging(target_lufs: float):
    """fix_dynamic stub that always reports converged=False."""
    def _inner(data, rate, target_lufs=-14.0, eq_settings=None, ceiling_db=-1.0):
        # Pretend we did all the math and landed 9 dB under target.
        metrics = {
            "original_lufs":  target_lufs - 17.0,
            "final_lufs":     target_lufs - 9.0,
            "final_peak_db":  ceiling_db + 0.01,
            "converged":      False,
            "iterations_run": 3,
        }
        return data, metrics
    return _inner


def _make_ctx(tmp_path: Path, target_lufs: float = -14.0,
              ceiling: float = -1.5) -> MasterAlbumCtx:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "mastered"
    source_dir.mkdir()
    output_dir.mkdir()

    fname = "09-dark.wav"
    rng = np.random.default_rng(0)
    n = 48000 * 3
    data = rng.standard_normal((n, 2)).astype(np.float64) * 0.01
    sf.write(str(source_dir / fname), data, 48000, subtype="PCM_24")
    sf.write(str(output_dir / fname), data, 48000, subtype="PCM_24")

    ctx = MasterAlbumCtx(
        album_slug="test-album",
        genre="",
        target_lufs=target_lufs,
        ceiling_db=ceiling,
        cut_highmid=0.0,
        cut_highs=0.0,
        source_subfolder="",
        freeze_signature=False,
        new_anchor=False,
        loop=asyncio.new_event_loop(),
    )
    ctx.audio_dir = tmp_path
    ctx.source_dir = source_dir
    ctx.output_dir = output_dir
    ctx.wav_files = [source_dir / fname]
    ctx.mastered_files = [output_dir / fname]
    ctx.targets = {
        "output_sample_rate": 48000,
        "output_bits": 24,
        "target_lufs": target_lufs,
        "ceiling_db": ceiling,
    }
    ctx.settings = {}
    ctx.effective_lufs = target_lufs
    ctx.effective_ceiling = ceiling
    ctx.effective_highmid = 0.0
    ctx.effective_highs = 0.0
    ctx.effective_compress = 2.5
    return ctx


def test_verification_warn_fallback_on_unrecoverable(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)

    # Route 1 of 1 track as recoverable-but-non-convergent.
    fake_lufs = _fake_analyze(ctx.effective_lufs, off_by_lufs=-9.0,
                              peak_db=ctx.effective_ceiling - 0.05)
    fake_fix = _fake_fix_dynamic_diverging(ctx.effective_lufs)

    asyncio.set_event_loop(ctx.loop)
    try:
        with patch(
            "tools.mastering.analyze_tracks.analyze_track", fake_lufs,
        ), patch(
            "tools.mastering.fix_dynamic_track.fix_dynamic", fake_fix,
        ):
            result = ctx.loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        ctx.loop.close()

    # Key assertion: the stage returned None (warn-fallback), not a
    # failure JSON.
    assert result is None, (
        "verification halted when it should have warn-fallbacked "
        f"(returned: {result!r})"
    )
    stage = ctx.stages.get("verification")
    assert stage is not None
    assert stage["status"] == "warn"
    assert stage.get("unrecoverable_tracks") == ["09-dark.wav"]
    assert stage.get("all_within_spec") is False

    sidecar = ctx.output_dir / "VERIFICATION_WARNINGS.md"
    assert sidecar.exists(), "VERIFICATION_WARNINGS.md was not written"
    body = sidecar.read_text()
    assert "09-dark.wav" in body
    assert "-14.0" in body or "-14" in body

    # Notice + warning must be visible for operators.
    notices_blob = " ".join(ctx.notices)
    warnings_blob = " ".join(
        w if isinstance(w, str) else str(w) for w in ctx.warnings
    )
    assert "warn-fallback" in notices_blob.lower()
    assert "unrecoverable" in warnings_blob.lower() or \
           "VERIFICATION_WARNINGS" in warnings_blob


def test_verification_halts_when_recovery_not_attempted(tmp_path: Path) -> None:
    """If the failure isn't auto-recovery-eligible (e.g., peak issue
    alone), verification still halts as before."""
    ctx = _make_ctx(tmp_path)

    # Peak issue makes this NOT recoverable (has_peak_issue=True path).
    fake_lufs = _fake_analyze(ctx.effective_lufs, off_by_lufs=0.0,
                              peak_db=ctx.effective_ceiling + 0.5)

    asyncio.set_event_loop(ctx.loop)
    try:
        with patch(
            "tools.mastering.analyze_tracks.analyze_track", fake_lufs,
        ):
            result = ctx.loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        ctx.loop.close()

    # Not warn-fallback eligible → halt.
    assert result is not None
    import json
    payload = json.loads(result)
    assert payload["failed_stage"] == "verification"


def test_verification_halts_on_mixed_failure(tmp_path: Path) -> None:
    """Some tracks unrecoverable, others halt-eligible → halt overall.
    Warn-fallback only applies when ALL remaining out-of-spec tracks
    are auto-recovery casualties.

    Two-track album:
      - track A: recoverable-but-non-convergent (dark, fix_dynamic → converged=False)
      - track B: has peak issue (NOT recovery-eligible)
    Expected: verification halts (status="fail") because track B
    requires halt-eligible handling even though track A is a
    warn-fallback case.
    """
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "mastered"
    source_dir.mkdir()
    output_dir.mkdir()

    rng = np.random.default_rng(0)
    n = 48000 * 3
    data = rng.standard_normal((n, 2)).astype(np.float64) * 0.01
    for fname in ("01-a-unrecoverable.wav", "02-b-peak-issue.wav"):
        sf.write(str(source_dir / fname), data, 48000, subtype="PCM_24")
        sf.write(str(output_dir / fname), data, 48000, subtype="PCM_24")

    loop = asyncio.new_event_loop()
    ctx = MasterAlbumCtx(
        album_slug="test-album",
        genre="",
        target_lufs=-14.0,
        ceiling_db=-1.5,
        cut_highmid=0.0,
        cut_highs=0.0,
        source_subfolder="",
        freeze_signature=False,
        new_anchor=False,
        loop=loop,
    )
    ctx.audio_dir = tmp_path
    ctx.source_dir = source_dir
    ctx.output_dir = output_dir
    ctx.wav_files = [source_dir / "01-a-unrecoverable.wav",
                     source_dir / "02-b-peak-issue.wav"]
    ctx.mastered_files = [output_dir / "01-a-unrecoverable.wav",
                          output_dir / "02-b-peak-issue.wav"]
    ctx.targets = {"output_sample_rate": 48000, "output_bits": 24,
                   "target_lufs": -14.0, "ceiling_db": -1.5}
    ctx.settings = {}
    ctx.effective_lufs = -14.0
    ctx.effective_ceiling = -1.5
    ctx.effective_highmid = 0.0
    ctx.effective_highs = 0.0
    ctx.effective_compress = 2.5

    def _mixed_analyze(path: str) -> dict:
        name = Path(path).name
        if "unrecoverable" in name:
            return {
                "filename": name,
                "lufs": -23.0,  # way under target → lufs_too_low
                "peak_db": -1.55,  # at-ceiling → peak_at_ceiling triggers recovery
                "short_term_range": 6.0, "stl_95": 9.0,
                "low_rms": -30.0, "vocal_rms": -22.0,
            }
        else:
            return {
                "filename": name,
                "lufs": -14.0,
                "peak_db": -1.0,  # over ceiling -1.5 → has_peak_issue
                "short_term_range": 6.0, "stl_95": 9.0,
                "low_rms": -30.0, "vocal_rms": -22.0,
            }

    fake_fix = _fake_fix_dynamic_diverging(-14.0)

    asyncio.set_event_loop(loop)
    try:
        with patch(
            "tools.mastering.analyze_tracks.analyze_track", _mixed_analyze,
        ), patch(
            "tools.mastering.fix_dynamic_track.fix_dynamic", fake_fix,
        ):
            result = loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        loop.close()

    # Mixed case: halt-eligible track forces halt.
    assert result is not None
    import json
    payload = json.loads(result)
    assert payload["failed_stage"] == "verification"
    assert ctx.stages["verification"]["status"] == "fail"


def test_verification_halts_on_pure_range_failure(tmp_path: Path) -> None:
    """Album-range failure with no individually out-of-spec tracks
    must halt, not warn-fallback with an empty sidecar.

    Two tracks both landing within ±0.5 dB of target but with a
    >=1 dB spread between them — the album-range check fails
    but no track is individually out-of-spec, so recovery isn't
    triggered and warn-fallback doesn't apply.

    Values: -13.5 and -14.5 → both exactly 0.5 dB from target -14.0.
    The out-of-spec check is strict (> 0.5), so neither fires.
    Range = 1.0, which satisfies `>= 1.0`, so album_range_fail=True.
    """
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "mastered"
    source_dir.mkdir()
    output_dir.mkdir()

    rng = np.random.default_rng(0)
    n = 48000 * 3
    data = rng.standard_normal((n, 2)).astype(np.float64) * 0.01
    for fname in ("01-hot.wav", "02-mild.wav"):
        sf.write(str(source_dir / fname), data, 48000, subtype="PCM_24")
        sf.write(str(output_dir / fname), data, 48000, subtype="PCM_24")

    loop = asyncio.new_event_loop()
    ctx = MasterAlbumCtx(
        album_slug="test-album",
        genre="",
        target_lufs=-14.0,
        ceiling_db=-1.5,
        cut_highmid=0.0,
        cut_highs=0.0,
        source_subfolder="",
        freeze_signature=False,
        new_anchor=False,
        loop=loop,
    )
    ctx.audio_dir = tmp_path
    ctx.source_dir = source_dir
    ctx.output_dir = output_dir
    ctx.wav_files = [source_dir / "01-hot.wav", source_dir / "02-mild.wav"]
    ctx.mastered_files = [output_dir / "01-hot.wav", output_dir / "02-mild.wav"]
    ctx.targets = {
        "output_sample_rate": 48000,
        "output_bits": 24,
        "target_lufs": -14.0,
        "ceiling_db": -1.5,
    }
    ctx.settings = {}
    ctx.effective_lufs = -14.0
    ctx.effective_ceiling = -1.5
    ctx.effective_highmid = 0.0
    ctx.effective_highs = 0.0
    ctx.effective_compress = 2.5

    def _range_analyze(path: str) -> dict:
        name = Path(path).name
        # -13.5 and -14.5: both exactly 0.5 dB from target -14.0.
        # out-of-spec check is abs(diff) > 0.5 (strict), so neither fires.
        # Range = 1.0 satisfies >= 1.0, so album_range_fail=True.
        lufs = -13.5 if "hot" in name else -14.5
        return {
            "filename": name,
            "lufs": lufs,
            "peak_db": -2.0,
            "short_term_range": 6.0, "stl_95": 9.0,
            "low_rms": -30.0, "vocal_rms": -22.0,
        }

    asyncio.set_event_loop(loop)
    try:
        with patch("tools.mastering.analyze_tracks.analyze_track",
                   _range_analyze):
            result = loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        loop.close()

    # Pure range failure → halt.
    assert result is not None
    import json
    payload = json.loads(result)
    assert payload["failed_stage"] == "verification"
    assert payload["failure_detail"]["album_lufs_range"] >= 1.0
    assert ctx.stages["verification"]["status"] == "fail"

    # No sidecar should be written.
    sidecar = ctx.output_dir / "VERIFICATION_WARNINGS.md"
    assert not sidecar.exists(), (
        "sidecar written on pure range failure — should not happen "
        "(recovery was never attempted)"
    )
