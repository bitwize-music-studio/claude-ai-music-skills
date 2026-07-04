"""Contract tests for the shared finite-LUFS aggregation helpers (#400).

``_finite_lufs_aggregates`` / ``_round_or_none`` were added by the #400 fix as
the single source of truth for "aggregate LUFS over finite readings only" and
are now consumed by ``_stage_analysis`` (the DRY consolidation of the #371
inline logic), ``_stage_verification`` and ``_stage_ceiling_guard``.

A silent / corrupt track reads -inf LUFS; feeding that into ``np.mean`` /
``max - min`` poisons the aggregate (avg -> -inf, range -> inf). These tests
pin the helper contract directly, so a regression in any one call site — or in
the helper itself — is caught at the source rather than only through a
stage-level integration test.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing._album_stages import (  # noqa: E402
    _finite_lufs_aggregates,
    _round_or_none,
)


def _rows(*lufs_values: float) -> list[dict]:
    """Build minimal analyze_track-shaped rows carrying the given LUFS values."""
    return [{"filename": f"{i:02d}.wav", "lufs": v} for i, v in enumerate(lufs_values)]


class TestFiniteLufsAggregates:
    def test_all_finite_matches_naive_mean_and_range(self):
        """With no silent tracks the helper equals the plain mean / max-min."""
        values = [-14.0, -13.2, -15.7, -12.9]
        avg, rng = _finite_lufs_aggregates(_rows(*values))
        assert avg == float(np.mean(values))
        assert rng == float(max(values) - min(values))

    def test_negative_inf_is_ignored(self):
        """A -inf silent track must not poison avg (-> -inf) or range (-> inf)."""
        avg, rng = _finite_lufs_aggregates(_rows(-14.0, float("-inf"), -13.0))
        assert avg == float(np.mean([-14.0, -13.0]))
        assert rng == pytest.approx(1.0)
        assert math.isfinite(avg) and math.isfinite(rng)

    def test_nan_is_ignored(self):
        avg, rng = _finite_lufs_aggregates(_rows(-14.0, float("nan"), -16.0))
        assert avg == float(np.mean([-14.0, -16.0]))
        assert rng == pytest.approx(2.0)

    def test_all_non_finite_returns_none_none(self):
        avg, rng = _finite_lufs_aggregates(_rows(float("-inf"), float("nan")))
        assert avg is None
        assert rng is None

    def test_empty_returns_none_none(self):
        assert _finite_lufs_aggregates([]) == (None, None)

    def test_single_finite_value_has_zero_range(self):
        avg, rng = _finite_lufs_aggregates(_rows(-14.0))
        assert avg == -14.0
        assert rng == 0.0


class TestRoundOrNone:
    def test_none_passes_through(self):
        assert _round_or_none(None, 1) is None
        assert _round_or_none(None, 2) is None

    def test_finite_rounds_like_builtin(self):
        assert _round_or_none(-14.037, 1) == round(-14.037, 1)
        assert _round_or_none(0.126, 2) == round(0.126, 2)
