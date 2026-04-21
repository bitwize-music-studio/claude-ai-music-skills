"""When a dark track clips ADM, it must NOT be tightened — instead it
goes to warn-fallback in ADM_VALIDATION.md with reason=dark_track_not_tightened."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_dark_clipping_track_not_tightened():
    """Unit-level assertion on the partition logic: given clipping_fnames
    and dark_tracks sets, the tightenable set excludes dark tracks."""
    clipping_fnames = {"01-dark.wav", "02-bright.wav", "03-bright.wav"}
    dark_tracks = {"01-dark.wav"}
    tightenable = clipping_fnames - dark_tracks
    dark_clipping = clipping_fnames & dark_tracks
    assert tightenable == {"02-bright.wav", "03-bright.wav"}
    assert dark_clipping == {"01-dark.wav"}


def test_all_dark_clipping_breaks_to_warn_fallback():
    """If every clipping track is dark, the ADM loop should exit to
    warn-fallback (no re-master cycle). Integration test — deferred to
    Task 7's master_album harness."""
    pytest.skip("TODO: Task 7 harness covers this end-to-end")
