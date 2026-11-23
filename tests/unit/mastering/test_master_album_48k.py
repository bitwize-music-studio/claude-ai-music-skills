"""master_album end to end on 48 kHz sources, the rate Suno delivers (#682).

Every other master_album flow test feeds it 44.1 kHz tones. These feed it
two Suno-like songs (``tests/fixtures/audio/suno_like.py``: 48 kHz stereo,
~-9 LUFS, brickwalled near 0 dBFS) and check what lands in ``mastered/``:
the delivery format, the audio's duration in seconds, that an upsampled
master holds nothing above the source's Nyquist (a relabelled file would),
the loudness on the written file and the true-peak ceiling.

Usage:
    python -m pytest tests/unit/mastering/test_master_album_48k.py -v
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

from handlers import _shared as shared_mod
from handlers.processing import _helpers as processing_helpers
from handlers.processing import audio as audio_mod
from tests.fixtures.audio.suno_like import make_suno_song
from tools.mastering import config as mastering_config_mod
from tools.mastering.config import DEFAULT_MASTERING_CONFIG
from tools.mastering.master_tracks import measure_true_peak

pytestmark = pytest.mark.unit

SOURCE_RATE = 48000
SECONDS = 30.0
NAMES = ("01-first.wav", "02-second.wav")


class _Cache:
    def __init__(self) -> None:
        self._state: dict = {"albums": {"suno-album": {"tracks": {}}}}

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _write_album(audio_dir: Path) -> None:
    for name, (seed, key) in zip(NAMES, [(1, 0), (2, 3)], strict=True):
        data, rate = make_suno_song(seconds=SECONDS, rate=SOURCE_RATE, seed=seed, key=key)
        assert rate == SOURCE_RATE
        sf.write(str(audio_dir / name), data, rate, subtype="PCM_16")


def _master_album(audio_dir: Path, config: dict) -> dict:
    with patch.object(processing_helpers, "_resolve_audio_dir",
                      lambda slug, *_, **__: (None, audio_dir)), \
         patch.object(shared_mod, "cache", _Cache()), \
         patch.object(mastering_config_mod, "load_mastering_config", return_value=config):
        return json.loads(asyncio.run(audio_mod.master_album("suno-album", genre="pop")))


def _check_delivered(audio_dir: Path, result: dict, *, rate: int, subtype: str) -> None:
    settings = result["settings"]
    target, ceiling = settings["target_lufs"], settings["ceiling_db"]
    for name in NAMES:
        path = audio_dir / "mastered" / name
        info = sf.info(str(path))
        assert (info.samplerate, info.subtype) == (rate, subtype), name
        data, out_rate = sf.read(str(path))
        # The same 30 s of audio, in seconds, whatever the rate.
        assert len(data) / out_rate == pytest.approx(SECONDS, abs=0.01), name
        # Upsampled, not relabelled: nothing above the 48 kHz source's Nyquist.
        if out_rate > SOURCE_RATE:
            mono = data.mean(axis=1)
            power = np.abs(np.fft.rfft(mono)) ** 2
            freqs = np.fft.rfftfreq(len(mono), 1 / out_rate)
            above = power[freqs > SOURCE_RATE / 2 + 500].sum() / power.sum()
            assert above < 1e-4, (name, above)  # dither / limiter residue: ~4e-6
        # The promise, measured on the file as written.
        lufs = pyln.Meter(out_rate).integrated_loudness(data)
        assert lufs == pytest.approx(target, abs=0.5), (name, lufs, target)
        true_peak = 20 * np.log10(measure_true_peak(data, out_rate))
        assert true_peak <= ceiling + 0.05, (name, true_peak, ceiling)


def test_default_config_upsamples_48k_suno_masters_to_96k(tmp_path: Path) -> None:
    _write_album(tmp_path)
    result = _master_album(tmp_path, dict(DEFAULT_MASTERING_CONFIG))
    assert result.get("failed_stage") is None, result.get("failure_detail")
    assert (result["settings"]["output_bits"], result["settings"]["output_sample_rate"]) == (24, 96000)
    _check_delivered(tmp_path, result, rate=96000, subtype="PCM_24")


def test_48k_delivery_keeps_suno_rate(tmp_path: Path) -> None:
    _write_album(tmp_path)
    config = {**DEFAULT_MASTERING_CONFIG, "delivery_bit_depth": 16, "delivery_sample_rate": 48000}
    result = _master_album(tmp_path, config)
    assert result.get("failed_stage") is None, result.get("failure_detail")
    assert (result["settings"]["output_bits"], result["settings"]["output_sample_rate"]) == (16, 48000)
    _check_delivered(tmp_path, result, rate=48000, subtype="PCM_16")
