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


class TestParityHoldsForUnreadableThresholds:
    """#553: polish reads `click_peak_ratio` through `_setting_float` —

    warn-and-default on anything it can't parse — while the analyzer
    still used a bare `float(raw)`. A quoted `click_peak_ratio: "20"`
    therefore split the two apart (analyzer 20.0, polish 15.0) and a
    non-numeric string raised ValueError out of the analyzer instead of
    warning. Both sides read the key the same way now.
    """

    @staticmethod
    def _resolved(monkeypatch, tmp_path, yaml_text, stem="keyboard", genre="electronic"):
        from tests.unit.mixing._presets import install_override

        install_override(tmp_path, monkeypatch, yaml_text)

        from handlers.processing.mixing import _resolve_analyzer_peak_ratio
        from tools.mixing.mix_tracks import _apply_click_removal, _get_stem_settings

        settings = _get_stem_settings(stem, genre)
        # Read the processor's effective value through the same path the
        # de-clicker takes, by capturing what it hands `remove_clicks`.
        seen: dict[str, float] = {}

        def _spy(data, rate, *, peak_ratio, repair="linear", detect_only=False, **kw):
            seen["peak_ratio"] = peak_ratio
            return data, 0

        import tools.mixing.mix_tracks as mt
        monkeypatch.setattr(mt, "remove_clicks", _spy)
        _apply_click_removal(
            object(), 44100, {**settings, "click_removal": True}, {},
        )
        return _resolve_analyzer_peak_ratio(stem, genre), seen["peak_ratio"]

    def test_quoted_threshold_resolves_the_same_on_both_sides(
        self, tmp_path, monkeypatch, caplog,
    ):
        import logging

        with caplog.at_level(logging.WARNING):
            analyzer, processor = self._resolved(monkeypatch, tmp_path, (
                'genres:\n'
                '  electronic:\n'
                '    keyboard:\n'
                '      click_peak_ratio: "20"\n'
            ))
        assert analyzer == pytest.approx(processor)
        assert analyzer == pytest.approx(15.0)
        assert any('click_peak_ratio' in r.message for r in caplog.records)

    def test_non_numeric_threshold_does_not_raise_in_the_analyzer(
        self, tmp_path, monkeypatch,
    ):
        analyzer, processor = self._resolved(monkeypatch, tmp_path, (
            'genres:\n'
            '  electronic:\n'
            '    keyboard:\n'
            '      click_peak_ratio: aggressive\n'
        ))
        assert analyzer == pytest.approx(processor) == pytest.approx(15.0)

    def test_real_numeric_threshold_still_reaches_both_sides(
        self, tmp_path, monkeypatch,
    ):
        analyzer, processor = self._resolved(monkeypatch, tmp_path, (
            'genres:\n'
            '  electronic:\n'
            '    keyboard:\n'
            '      click_peak_ratio: 22.5\n'
        ))
        assert analyzer == pytest.approx(processor) == pytest.approx(22.5)
