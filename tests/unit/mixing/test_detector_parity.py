"""Analyzer / processor click detector parity (#323 follow-up).

The `analyze_mix_issues` handler (used to report what needs fixing) and
the per-stem polish processors (used to actually fix clicks) must agree
on the `click_peak_ratio` threshold for every (stem, genre) pair. When
they disagree, the analyzer under-counts or over-counts clicks that the
processor removes (the reporter's case: 393 detected vs. 1,748 removed
on electronic keyboard because analyzer hardcoded 15.0 while processor
read the electronic preset's 10.0).

This test pins the invariant: for every supported (stem, genre), the
analyzer's resolved `peak_ratio` must equal the processor's. Achieved
by routing both sides through the same resolver.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


SUPPORTED_STEMS = [
    "vocals", "backing_vocals", "drums", "bass", "guitar",
    "keyboard", "strings", "brass", "woodwinds", "percussion",
    "synth", "other",
]

# Genres picked to cover the main click-threshold classes: tight/dense
# electronic (10.0), rock/pop (6.0), and the empty-string fallback
# which must produce the mix-preset default (15.0 unless the mix preset
# overrides it).
SAMPLE_GENRES = ["", "electronic", "rock", "pop", "ambient", "hip-hop"]


@pytest.mark.parametrize("stem", SUPPORTED_STEMS)
@pytest.mark.parametrize("genre", SAMPLE_GENRES)
def test_analyzer_matches_processor_peak_ratio(stem: str, genre: str) -> None:
    """Analyzer + processor must read the same peak_ratio per (stem, genre).

    Fails on the pre-fix code because the analyzer hardcodes
    `peak_ratio = 15.0` while the processor resolves through
    `_get_stem_settings(stem, genre)` → genre preset (e.g. electronic → 10.0).
    """
    from handlers.processing.mixing import _resolve_analyzer_peak_ratio
    from tools.mixing.mix_tracks import _get_stem_settings

    processor_settings = _get_stem_settings(stem, genre or None)
    processor_ratio = float(processor_settings.get("click_peak_ratio", 15.0))

    analyzer_ratio = _resolve_analyzer_peak_ratio(stem, genre or None)

    assert analyzer_ratio == pytest.approx(processor_ratio), (
        f"Analyzer/processor peak_ratio mismatch for stem={stem!r}, "
        f"genre={genre!r}: analyzer={analyzer_ratio}, "
        f"processor={processor_ratio}"
    )


@pytest.mark.parametrize("genre", SAMPLE_GENRES)
def test_analyzer_matches_full_mix_processor_peak_ratio(genre: str) -> None:
    """Full-mix path: analyzer + processor must read the same peak_ratio.

    When the analyzer handles a non-stems audio layout (or passes
    ``stem_name=None``), it delegates to `_get_full_mix_settings`. The
    processor's `mix_track_full` uses the same resolver. Pin parity on
    that branch too.
    """
    from handlers.processing.mixing import _resolve_analyzer_peak_ratio
    from tools.mixing.mix_tracks import _get_full_mix_settings

    processor_settings = _get_full_mix_settings(genre or None)
    processor_ratio = float(processor_settings.get("click_peak_ratio", 15.0))
    analyzer_ratio = _resolve_analyzer_peak_ratio(None, genre or None)

    assert analyzer_ratio == pytest.approx(processor_ratio), (
        f"Full-mix peak_ratio mismatch for genre={genre!r}: "
        f"analyzer={analyzer_ratio}, processor={processor_ratio}"
    )
