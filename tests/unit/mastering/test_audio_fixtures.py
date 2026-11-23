"""The synthetic audio fixtures are what their docstrings say (#682).

Tests across mastering, mixing and QC lean on these generators; when one
quietly isn't stereo, or a "vocal" has no pitch, the tests built on it check
less than they claim.

Usage:
    python -m pytest tests/unit/mastering/test_audio_fixtures.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures import audio as fixtures

pytestmark = pytest.mark.unit

# Every generator that spreads a mono source with _to_stereo, at every width
# it uses (0.1 default, 0.05, 0.02).
SPREAD = ["make_vocal", "make_drums", "make_bass", "make_clipping", "make_bright",
          "make_noisy", "make_clicks_and_pops", "make_silent_gaps", "make_full_mix"]


@pytest.mark.parametrize("name", SPREAD)
def test_spread_generators_are_really_stereo(name: str) -> None:
    """L != R: a width that rounded to a 0-sample shift made dual mono."""
    data, _ = getattr(fixtures, name)()
    assert data.ndim == 2 and data.shape[1] == 2
    side = data[:, 0] - data[:, 1]
    assert np.sqrt(np.mean(side ** 2)) > 1e-4 * np.sqrt(np.mean(data[:, 0] ** 2))


def test_smaller_width_is_narrower() -> None:
    """The spread still scales with width: 0.02 is narrower than 0.1."""
    rng = np.random.default_rng(0)
    mono = rng.standard_normal(44100)
    side_rms = []
    for width in (0.02, 0.05, 0.1):
        st = fixtures._to_stereo(mono, width=width)
        side_rms.append(np.sqrt(np.mean((st[:, 0] - st[:, 1]) ** 2)))
    assert side_rms[0] < side_rms[1] < side_rms[2]


@pytest.mark.parametrize("rate", [44100, 48000])
def test_vocal_has_a_fundamental(rate: int) -> None:
    """make_vocal is pitched: its strongest component is the 220 Hz f0, with harmonics."""
    data, out_rate = fixtures.make_vocal(rate=rate)
    assert out_rate == rate
    mono = data[:, 0]
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    freqs = np.fft.rfftfreq(len(mono), 1 / rate)
    assert freqs[np.argmax(spectrum)] == pytest.approx(220.0, abs=5.0)

    def band(lo: float, hi: float) -> float:
        return float(np.sum(spectrum[(freqs >= lo) & (freqs < hi)] ** 2))

    # Harmonics at 440 / 660 Hz stand well above the gaps between them.
    for harmonic in (440.0, 660.0):
        assert band(harmonic - 10, harmonic + 10) > 20 * band(harmonic + 90, harmonic + 110)
    # Sibilance is still there for the de-esser tests.
    assert band(4000, 8000) > 0.01 * band(100, 4000)
