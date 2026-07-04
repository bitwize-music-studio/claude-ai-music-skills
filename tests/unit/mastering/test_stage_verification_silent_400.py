"""_stage_verification (and the ceiling-guard recompute) must not let a
silent / corrupt mastered track's -inf LUFS poison its avg_lufs / lufs_range
aggregates or the album-range control flow.

Regression for issue #400 (residual after #371 fixed _stage_analysis): the
verification-stage aggregation still used unfiltered ``np.mean`` / ``max-min``
over LUFS values that can include -inf when a zeroed/corrupt mastered WAV is
globbed into ``ctx.mastered_files``. That leaves -inf/inf in
``ctx.stages["verification"]`` (the in-memory payload consumers read directly)
and makes ``album_range_fail = verify_range >= 1.0`` fire spuriously.

Heavy deps (analyze_track) are mocked — no real audio is read.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for _p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx

ANALYZE_TARGET = "tools.mastering.analyze_tracks.analyze_track"


def _track(name: str, lufs: float, peak_db: float) -> dict:
    """A minimally-complete analyze_track result for one mastered file."""
    return {
        "filename": name,
        "lufs": lufs,
        "peak_db": peak_db,
        "short_term_range": 6.0,
        "stl_95": 9.0,
        "low_rms": -30.0,
        "vocal_rms": -22.0,
    }


def _make_ctx(tmp_path: Path, names: list[str]) -> MasterAlbumCtx:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "mastered"
    source_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    ctx = MasterAlbumCtx(
        album_slug="test-album",
        genre="",
        target_lufs=-14.0,
        ceiling_db=-1.0,
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
    # analyze_track is mocked, so these paths need not exist on disk.
    ctx.mastered_files = [output_dir / n for n in names]
    ctx.targets = {
        "output_sample_rate": 48000,
        "output_bits": 24,
        "target_lufs": -14.0,
        "ceiling_db": -1.0,
    }
    ctx.settings = {}
    ctx.effective_lufs = -14.0
    ctx.effective_ceiling = -1.0
    ctx.effective_highmid = 0.0
    ctx.effective_highs = 0.0
    ctx.effective_compress = 2.5
    return ctx


def _run_verification(ctx: MasterAlbumCtx, fake_analyze) -> str | None:
    asyncio.set_event_loop(ctx.loop)
    try:
        with patch(ANALYZE_TARGET, fake_analyze):
            return ctx.loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        ctx.loop.close()


# ── new helpers ────────────────────────────────────────────────────────────

def test_finite_lufs_aggregates_filters_non_finite() -> None:
    results = [
        _track("01-ok.wav", -14.0, -2.0),
        _track("02-silent.wav", float("-inf"), float("-inf")),
        _track("03-ok.wav", -13.0, -2.0),
    ]
    avg, rng = _album_stages._finite_lufs_aggregates(results)
    assert avg is not None and math.isfinite(avg)
    assert rng is not None and math.isfinite(rng)
    # Aggregated over the two finite tracks only.
    assert avg == -13.5
    assert rng == 1.0


def test_finite_lufs_aggregates_all_non_finite_returns_none() -> None:
    results = [
        _track("01-silent.wav", float("-inf"), float("-inf")),
        _track("02-silent.wav", float("-inf"), float("-inf")),
    ]
    assert _album_stages._finite_lufs_aggregates(results) == (None, None)
    # Empty input is also None/None (no finite readings at all).
    assert _album_stages._finite_lufs_aggregates([]) == (None, None)


def test_round_or_none_passes_none_through() -> None:
    assert _album_stages._round_or_none(None, 1) is None
    assert _album_stages._round_or_none(-13.456, 1) == -13.5
    assert _album_stages._round_or_none(0.0, 2) == 0.0


# ── stage integration ───────────────────────────────────────────────────────

def test_verification_silent_track_keeps_aggregates_finite(tmp_path: Path) -> None:
    """One in-spec track + one silent (-inf) track. The stage still halts
    (a silent mastered track is genuinely out of spec), but the reported
    aggregates must be the finite metrics of the real track, not -inf/inf."""
    ctx = _make_ctx(tmp_path, ["01-ok.wav", "02-silent.wav"])

    def fake_analyze(path: str) -> dict:
        name = Path(path).name
        if "silent" in name:
            return _track(name, float("-inf"), float("-inf"))
        return _track(name, -14.0, -2.0)

    result = _run_verification(ctx, fake_analyze)

    stage = ctx.stages["verification"]
    # Core residual: no -inf/inf may reach the in-memory aggregates.
    assert stage["avg_lufs"] is not None and math.isfinite(stage["avg_lufs"])
    assert stage["lufs_range"] is not None and math.isfinite(stage["lufs_range"])
    # Metrics reflect the one measurable track, not the poisoned union.
    assert stage["avg_lufs"] == -14.0
    assert stage["lufs_range"] == 0.0

    # A single silent outlier must not spuriously trip the album-range gate
    # (range over the finite set is 0.0, well under the 1.0 dB limit).
    if result is not None:
        payload = json.loads(result)
        assert "album_lufs_range" not in payload.get("failure_detail", {})
        # And nothing serialized as a non-finite JS token.
        assert "Infinity" not in result and "NaN" not in result


def test_verification_all_silent_yields_none_without_crashing(
    tmp_path: Path,
) -> None:
    """Every mastered track silent → no finite readings. Aggregation must
    yield None (not -inf/nan) and the round() guards must not raise."""
    ctx = _make_ctx(tmp_path, ["01-silent.wav", "02-silent.wav"])

    def fake_analyze(path: str) -> dict:
        return _track(Path(path).name, float("-inf"), float("-inf"))

    result = _run_verification(ctx, fake_analyze)

    stage = ctx.stages["verification"]
    # None is the documented empty sentinel; -inf/nan is the bug.
    assert stage["avg_lufs"] is None or math.isfinite(stage["avg_lufs"])
    assert stage["lufs_range"] is None or math.isfinite(stage["lufs_range"])
    assert stage["avg_lufs"] is None
    assert stage["lufs_range"] is None
    if result is not None:
        assert "Infinity" not in result and "NaN" not in result
