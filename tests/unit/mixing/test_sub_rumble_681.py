"""The sub-rumble check hears an 808, not rumble, at C1 (#681, item 10).

The analyzer measured "< 30 Hz" on a PSD with ~11 Hz bins, so a C1 808
(32.7 Hz fundamental) read as rumble and drew a 35 Hz highpass, which the
polish merge applied over trap's own 25 Hz bass highpass and which cut the
808's fundamental. These tests use a generated 808 and generated rumble.

Usage:
    python -m pytest tests/unit/mixing/test_sub_rumble_681.py -v
"""

from __future__ import annotations

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

from handlers.processing.mixing import _build_analyzer  # noqa: E402
from tests.fixtures.audio.suno_like import make_808, make_rumble  # noqa: E402
from tools.mixing.mix_tracks import _get_stem_settings, apply_highpass  # noqa: E402

pytestmark = pytest.mark.unit


def _analyze(data: np.ndarray, rate: int, stem: str = "bass", genre: str = "trap") -> dict:
    return _build_analyzer()(data, rate, filename="01-track.wav", stem_name=stem, genre=genre)


def _fundamental_db(data: np.ndarray, rate: int, hz: float) -> float:
    spec = np.abs(np.fft.rfft(data[:, 0]))
    freqs = np.fft.rfftfreq(len(data), 1 / rate)
    band = (freqs > hz - 2) & (freqs < hz + 2)
    return float(20 * np.log10(np.max(spec[band])))


class TestRumbleDetector:
    @pytest.mark.parametrize("note_hz", [32.70, 27.50])  # C1, A0
    def test_an_808_is_not_rumble(self, note_hz: float) -> None:
        data, rate = make_808(note_hz=note_hz)
        result = _analyze(data, rate)
        assert "sub_rumble" not in result["issues"], result
        assert "highpass_cutoff" not in result["recommendations"]
        assert result["sub_ratio"] < 0.10  # flagged above 0.15

    def test_rumble_under_an_808_is_still_caught(self) -> None:
        boom, rate = make_808()
        rumble, _ = make_rumble(lo_hz=10.0, hi_hz=20.0, level=0.8)
        result = _analyze(boom + rumble, rate)
        assert "sub_rumble" in result["issues"], result
        assert result["recommendations"]["highpass_cutoff"] == 25

    def test_rumble_alone_is_caught(self) -> None:
        rumble, rate = make_rumble(lo_hz=8.0, hi_hz=18.0)
        result = _analyze(rumble, rate, stem="other", genre="")
        assert "sub_rumble" in result["issues"]
        assert result["sub_ratio"] > 0.5


class TestRecommendationMerge:
    def test_never_lowers_a_preset_highpass(self) -> None:
        # synth ships with an 80 Hz highpass; a rumble finding must not pull
        # it down to the analyzer's cutoff (the old 35 Hz one did).
        assert _get_stem_settings("synth", "trap")["highpass_cutoff"] == 80
        merged = _get_stem_settings("synth", "trap", analyzer_rec={"highpass_cutoff": 25})
        assert merged["highpass_cutoff"] == 80

    def test_never_raises_trap_bass_above_its_25_hz(self) -> None:
        assert _get_stem_settings("bass", "trap")["highpass_cutoff"] == 25
        merged = _get_stem_settings("bass", "trap", analyzer_rec={"highpass_cutoff": 25})
        assert merged["highpass_cutoff"] == 25

    def test_raises_a_lower_highpass(self) -> None:
        # A stem whose preset cut is below the analyzer's still gets the
        # protection the rumble finding asks for.
        merged = _get_stem_settings("bass", "trap", analyzer_rec={"highpass_cutoff": 40})
        assert merged["highpass_cutoff"] == 40

    def test_an_808_keeps_its_fundamental_through_polish(self) -> None:
        """End to end: analyzer finding → merged settings → the highpass applied."""
        data, rate = make_808()
        result = _analyze(data, rate)
        settings = _get_stem_settings("bass", "trap", analyzer_rec=result["recommendations"])
        cutoff = float(settings["highpass_cutoff"])
        assert cutoff == 25
        filtered = apply_highpass(data, rate, cutoff=cutoff)
        loss = _fundamental_db(data, rate, 32.70) - _fundamental_db(filtered, rate, 32.70)
        assert loss < 1.5, f"C1 fundamental lost {loss:.2f} dB at a {cutoff} Hz highpass"
