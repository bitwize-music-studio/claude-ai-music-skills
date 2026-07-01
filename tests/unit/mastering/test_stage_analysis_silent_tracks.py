"""_stage_analysis (the master_album pre-flight analysis stage) must not let
a silent track's -inf LUFS poison its aggregates or hide the silent track
from the operator.

Parallel-site regression for issue #371: analyze_audio was fixed to filter
non-finite LUFS, but _stage_analysis in the master_album pipeline carried the
same unguarded ``np.mean`` / ``max-min`` aggregation.
"""

from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def _write_silent(path: Path, seconds: float = 3.0, rate: int = 48000) -> None:
    sf.write(str(path), np.zeros((int(seconds * rate), 2), dtype="float32"), rate)


def _write_normal(path: Path, seconds: float = 3.0, rate: int = 48000) -> None:
    rng = np.random.default_rng(7)
    n = int(seconds * rate)
    data = (rng.standard_normal((n, 2)) * 0.1).astype(np.float64)
    sf.write(str(path), data, rate, subtype="PCM_24")


def _run_stage(source_dir: Path):
    from handlers.processing._album_stages import MasterAlbumCtx, _stage_analysis

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = MasterAlbumCtx(
        album_slug="test", genre="pop", target_lufs=-14.0, ceiling_db=-1.0,
        cut_highmid=0.0, cut_highs=0.0, source_subfolder="",
        freeze_signature=False, new_anchor=False, loop=loop,
        source_dir=source_dir, wav_files=sorted(source_dir.glob("*.wav")),
    )
    try:
        loop.run_until_complete(_stage_analysis(ctx))
    finally:
        loop.close()
    return ctx


def test_silent_track_does_not_poison_analysis_aggregates(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _write_normal(source_dir / "01-normal.wav")
    _write_silent(source_dir / "02-silent.wav")

    ctx = _run_stage(source_dir)
    analysis = ctx.stages["analysis"]

    # Aggregates computed over the finite (non-silent) track only.
    assert analysis["avg_lufs"] is not None
    assert math.isfinite(analysis["avg_lufs"])
    assert analysis["lufs_range"] is not None
    assert math.isfinite(analysis["lufs_range"])
    # The silent track is surfaced to the operator, not hidden under "pass".
    assert "02-silent.wav" in analysis["silent_tracks"]
    assert any("02-silent.wav" in w for w in ctx.warnings)


def test_all_silent_analysis_yields_none_aggregates(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _write_silent(source_dir / "01-silent.wav")
    _write_silent(source_dir / "02-silent.wav")

    # Must not raise — None aggregates require a round() guard.
    ctx = _run_stage(source_dir)
    analysis = ctx.stages["analysis"]
    assert analysis["avg_lufs"] is None
    assert analysis["lufs_range"] is None
    assert len(analysis["silent_tracks"]) == 2
