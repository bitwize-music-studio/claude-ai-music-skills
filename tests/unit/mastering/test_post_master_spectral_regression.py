"""Post-QC emits tinniness-regression WARN when mastering pushes
high_mid/mid ratio up significantly from the polished input."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx


def _analysis_result(fname: str, tinniness: float) -> dict:
    """Minimal analyze_track result shape with just the fields that
    _stage_post_qc reads for the regression check."""
    return {
        "filename": fname,
        "lufs": -14.0,
        "peak_db": -1.5,
        "short_term_range": 6.0,
        "tinniness_ratio": tinniness,
    }


def _make_ctx(
    tmp_path: Path,
    pre_post: list[tuple[str, float, float]],
    preset: dict | None = None,
) -> MasterAlbumCtx:
    """Build a ctx populated with per-track pre/post tinniness.

    MasterAlbumCtx required fields (from dataclass introspection):
      album_slug, ceiling_db, cut_highmid, cut_highs, freeze_signature,
      genre, loop, new_anchor, source_subfolder, target_lufs

    analysis_results, verify_results, and effective_preset are optional
    dataclass fields (default_factory=list / default_factory=dict) so
    they can be passed as constructor kwargs OR set post-construction.
    We set them post-construction to match the pattern used by other
    mastering unit tests in this suite.
    """
    analysis = [_analysis_result(f, p) for f, p, _ in pre_post]
    verify = [_analysis_result(f, q) for f, _, q in pre_post]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mastered_dir = tmp_path / "mastered"
    mastered_dir.mkdir()

    # Real (tiny) audio files — qc_track will be mocked out anyway,
    # but the files must exist so MasterAlbumCtx doesn't complain.
    import numpy as np
    import soundfile as sf

    rng = np.random.default_rng(0)
    mastered_files = []
    for f, _, _ in pre_post:
        path = mastered_dir / f
        sf.write(
            str(path),
            (rng.standard_normal((48000, 2)) * 0.05).astype("float64"),
            48000,
            subtype="PCM_24",
        )
        mastered_files.append(path)

    ctx = MasterAlbumCtx(
        album_slug="test",
        genre="",
        target_lufs=-14.0,
        ceiling_db=-1.0,
        cut_highmid=0.0,
        cut_highs=0.0,
        source_subfolder="",
        freeze_signature=False,
        new_anchor=False,
        loop=loop,
    )
    ctx.mastered_files = mastered_files
    ctx.analysis_results = analysis
    ctx.verify_results = verify
    ctx.effective_preset = preset if preset is not None else {
        "post_qc_tinniness_warn_floor": 0.6,
        "post_qc_tinniness_warn_delta": 0.10,
    }
    return ctx


def _run_post_qc(ctx: MasterAlbumCtx) -> str | None:
    """Run _stage_post_qc with qc_track mocked to return a trivial PASS."""
    from unittest.mock import patch

    def _fake_qc(path, checks=None, genre=None):
        return {
            "filename": Path(path).name,
            "verdict": "PASS",
            "checks": {},
        }

    try:
        with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
            return ctx.loop.run_until_complete(
                _album_stages._stage_post_qc(ctx),
            )
    finally:
        ctx.loop.close()


class TestTinninessRegression:
    def test_regression_emits_warn(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path, [
            ("04-regressed.wav", 0.45, 0.82),  # floor=0.6, delta=+0.37
        ])
        result = _run_post_qc(ctx)
        assert result is None
        stage = ctx.stages["post_qc"]
        assert stage["status"] == "warn"
        regressions = stage["tinniness_regressions"]
        assert len(regressions) == 1
        assert regressions[0]["filename"] == "04-regressed.wav"
        assert regressions[0]["pre_tinniness"] == pytest.approx(0.45)
        assert regressions[0]["post_tinniness"] == pytest.approx(0.82)
        assert regressions[0]["delta"] == pytest.approx(0.37)
        assert any(
            "tinniness" in w.lower() and "04-regressed" in w
            for w in ctx.warnings
        )

    def test_no_regression_stays_pass(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path, [
            ("01-clean.wav", 0.30, 0.32),  # below floor, tiny delta
        ])
        result = _run_post_qc(ctx)
        assert result is None
        stage = ctx.stages["post_qc"]
        assert stage["status"] == "pass"
        assert stage.get("tinniness_regressions", []) == []

    def test_tinny_input_not_flagged_as_regression(self, tmp_path: Path) -> None:
        """Track that was already tinny pre-master shouldn't be flagged
        as a regression just because the post-master ratio is still
        tinny — the delta must also exceed threshold."""
        ctx = _make_ctx(tmp_path, [
            ("05-already-tinny.wav", 0.78, 0.80),  # above floor but delta=0.02
        ])
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        assert stage.get("tinniness_regressions", []) == []
        assert stage["status"] == "pass"

    def test_below_floor_not_flagged(self, tmp_path: Path) -> None:
        """Ratio that grew from 0.30 to 0.50 — large delta but below the
        absolute floor, so no WARN. (Taste-level judgement: moderate
        ratios aren't audible regressions.)"""
        ctx = _make_ctx(tmp_path, [
            ("06-growth-under-floor.wav", 0.30, 0.50),
        ])
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        assert stage.get("tinniness_regressions", []) == []
        assert stage["status"] == "pass"

    def test_preset_thresholds_are_respected(self, tmp_path: Path) -> None:
        """A loose preset with floor=0.9 should not flag a 0.82 post."""
        ctx = _make_ctx(
            tmp_path,
            [("04-regressed.wav", 0.45, 0.82)],
            preset={
                "post_qc_tinniness_warn_floor": 0.9,
                "post_qc_tinniness_warn_delta": 0.10,
            },
        )
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        assert stage.get("tinniness_regressions", []) == []
        assert stage["status"] == "pass"

    def test_multiple_regressions_all_reported(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path, [
            ("01-clean.wav",     0.30, 0.32),
            ("04-regressed.wav", 0.45, 0.82),
            ("07-regressed.wav", 0.50, 0.64),
        ])
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        regressions = stage["tinniness_regressions"]
        assert len(regressions) == 2
        names = sorted(r["filename"] for r in regressions)
        assert names == ["04-regressed.wav", "07-regressed.wav"]
        assert stage["status"] == "warn"
