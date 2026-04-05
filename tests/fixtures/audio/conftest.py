"""Pytest fixtures providing realistic audio WAV files on disk.

Import these fixtures by adding a conftest.py that imports from here,
or rely on pytest's automatic conftest discovery.
"""

from __future__ import annotations

import pytest

from tests.fixtures.audio import (
    DEFAULT_RATE,
    make_bass,
    make_bright,
    make_clipping,
    make_drums,
    make_full_mix,
    make_noisy,
    make_phase_problem,
    make_vocal,
    write_wav,
)


@pytest.fixture
def vocal_wav(tmp_path):
    """Formant-shaped vocal with sibilant bursts."""
    data, rate = make_vocal()
    return write_wav(str(tmp_path / "vocal.wav"), data, rate)


@pytest.fixture
def drums_wav(tmp_path):
    """Sharp transients with exponential decay."""
    data, rate = make_drums()
    return write_wav(str(tmp_path / "drums.wav"), data, rate)


@pytest.fixture
def bass_wav(tmp_path):
    """80 Hz fundamental + harmonics."""
    data, rate = make_bass()
    return write_wav(str(tmp_path / "bass.wav"), data, rate)


@pytest.fixture
def full_mix_wav(tmp_path):
    """Layered vocal + drums + bass mix."""
    data, rate = make_full_mix()
    return write_wav(str(tmp_path / "full_mix.wav"), data, rate)


@pytest.fixture
def clipping_wav(tmp_path):
    """Hard-clipped signal (should fail QC)."""
    data, rate = make_clipping()
    return write_wav(str(tmp_path / "clipping.wav"), data, rate)


@pytest.fixture
def phase_problem_wav(tmp_path):
    """Phase-inverted stereo (should fail mono compat)."""
    data, rate = make_phase_problem()
    return write_wav(str(tmp_path / "phase_problem.wav"), data, rate)


@pytest.fixture
def bright_wav(tmp_path):
    """Excessive high-frequency energy (should trigger tinniness)."""
    data, rate = make_bright()
    return write_wav(str(tmp_path / "bright.wav"), data, rate)


@pytest.fixture
def noisy_wav(tmp_path):
    """Signal with elevated noise floor."""
    data, rate = make_noisy()
    return write_wav(str(tmp_path / "noisy.wav"), data, rate)


@pytest.fixture
def stem_dir(tmp_path):
    """Directory with per-stem WAV files for mixing tests."""
    stems = tmp_path / "stems" / "01-test-track"
    stems.mkdir(parents=True)

    for name, generator in [
        ("vocals", make_vocal),
        ("drums", make_drums),
        ("bass", make_bass),
    ]:
        data, rate = generator(duration=1.5)
        write_wav(str(stems / f"{name}.wav"), data, rate)

    return str(stems)
