"""Integration test: master_audio / master_album consume mastering config.

End-to-end check that the resolved delivery targets (24-bit / 96 kHz by
default) flow from load_mastering_config() through the handler to the
mastered output file.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyloudnorm as pyln
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as shared_mod  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402


class _MockCache:
    """Minimal stand-in for the server's state cache."""

    def get_state(self) -> dict:
        return {}


TONE_HZ = 440.0
DURATION_S = 6.0


def _write_test_wav(path: Path, sr: int = 44100, duration: float = DURATION_S) -> None:
    """Write a test WAV at the given sample rate (default 44.1 kHz Suno-ish)."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    data = 0.3 * np.sin(2 * np.pi * TONE_HZ * t)
    stereo = np.column_stack([data, data])
    sf.write(str(path), stereo, sr, subtype="PCM_16")


def _assert_delivered_content(path: Path, target_lufs: float) -> None:
    """The master holds the source's audio at its rate, not just its header (#682).

    A 44.1 kHz file merely relabelled 96 kHz plays 2.18x fast: its duration
    shrinks and the tone moves up. Check both, and the promised loudness
    (±0.5 dB of the target) measured on the file as written.
    """
    data, rate = sf.read(str(path))
    assert len(data) / rate == pytest.approx(DURATION_S, abs=0.01)
    spectrum = np.abs(np.fft.rfft(data[:, 0] * np.hanning(len(data))))
    peak_hz = np.fft.rfftfreq(len(data), 1 / rate)[np.argmax(spectrum)]
    assert peak_hz == pytest.approx(TONE_HZ, abs=1.0)
    assert pyln.Meter(rate).integrated_loudness(data) == pytest.approx(target_lufs, abs=0.5)


@pytest.fixture
def one_track_audio_dir(tmp_path: Path) -> Path:
    """Create a minimal audio dir with a single 44.1 kHz WAV track."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    _write_test_wav(audio_dir / "01-test.wav")
    return audio_dir


def test_master_audio_produces_24bit_96khz_by_default(
    one_track_audio_dir: Path,
) -> None:
    """Default config → mastered output is 24-bit at 96 kHz."""

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, one_track_audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()):
        result_json = asyncio.run(audio_mod.master_audio("test-album"))

    result = json.loads(result_json)
    assert "error" not in result, result
    assert result["settings"]["output_bits"] == 24
    assert result["settings"]["output_sample_rate"] == 96000

    mastered = one_track_audio_dir / "mastered" / "01-test.wav"
    assert mastered.exists(), "mastered output was not written"
    info = sf.info(str(mastered))
    assert info.samplerate == 96000
    assert info.subtype == "PCM_24"
    _assert_delivered_content(mastered, result["settings"]["target_lufs"])
    for track in result["tracks"]:
        assert track["final_lufs"] == pytest.approx(result["settings"]["target_lufs"], abs=0.5)


def test_master_audio_honors_delivery_bit_depth_16(
    one_track_audio_dir: Path,
) -> None:
    """Setting delivery_bit_depth=16 in config produces 16-bit output."""
    from tools.mastering import config as mastering_config_mod
    from tools.mastering.config import DEFAULT_MASTERING_CONFIG

    custom = {**DEFAULT_MASTERING_CONFIG, "delivery_bit_depth": 16}

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, one_track_audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()), \
         patch.object(mastering_config_mod, "load_mastering_config", return_value=custom):
        result_json = asyncio.run(audio_mod.master_audio("test-album"))

    result = json.loads(result_json)
    assert "error" not in result, result
    assert result["settings"]["output_bits"] == 16

    mastered = one_track_audio_dir / "mastered" / "01-test.wav"
    info = sf.info(str(mastered))
    assert info.subtype == "PCM_16"


def test_master_audio_honors_legacy_source_rate(
    one_track_audio_dir: Path,
) -> None:
    """delivery_sample_rate=44100 matches Suno source → no upsampling."""
    from tools.mastering import config as mastering_config_mod
    from tools.mastering.config import DEFAULT_MASTERING_CONFIG

    custom = {**DEFAULT_MASTERING_CONFIG, "delivery_sample_rate": 44100}

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, one_track_audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()), \
         patch.object(mastering_config_mod, "load_mastering_config", return_value=custom):
        result_json = asyncio.run(audio_mod.master_audio("test-album"))

    result = json.loads(result_json)
    assert result["settings"]["output_sample_rate"] == 44100

    mastered = one_track_audio_dir / "mastered" / "01-test.wav"
    info = sf.info(str(mastered))
    assert info.samplerate == 44100
    _assert_delivered_content(mastered, result["settings"]["target_lufs"])
