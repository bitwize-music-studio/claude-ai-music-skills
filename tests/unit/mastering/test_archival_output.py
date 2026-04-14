"""Tests for master_album's archival output path.

When mastering.archival_enabled is true, master_album writes a 32-bit
float copy of each mastered track to {audio_dir}/archival/. Default is
off.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
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
    def __init__(self) -> None:
        self._state: dict = {}

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _write_tone(path: Path, freq: float, sr: int = 44100, duration: float = 3.0) -> None:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone = 0.3 * np.sin(2 * np.pi * freq * t)
    stereo = np.column_stack([tone, tone])
    sf.write(str(path), stereo, sr, subtype="PCM_16")


def _three_track_dir(tmp_path: Path) -> Path:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for i, freq in enumerate([440.0, 660.0, 880.0], start=1):
        _write_tone(audio_dir / f"0{i}-track.wav", freq)
    return audio_dir


def test_archival_disabled_by_default(tmp_path: Path) -> None:
    """With default config, no archival/ directory is created."""
    audio_dir = _three_track_dir(tmp_path)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()):
        result_json = asyncio.run(audio_mod.master_album("test-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, result

    archival_dir = audio_dir / "archival"
    assert not archival_dir.exists(), "archival/ should not be created when disabled"


def test_archival_enabled_writes_32bit_float(tmp_path: Path) -> None:
    """With archival_enabled=true, archival/ contains 32-bit float copies."""
    from tools.mastering import config as mastering_config_mod
    from tools.mastering.config import DEFAULT_MASTERING_CONFIG

    audio_dir = _three_track_dir(tmp_path)
    custom = {**DEFAULT_MASTERING_CONFIG, "archival_enabled": True}

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()), \
         patch.object(mastering_config_mod, "load_mastering_config", return_value=custom):
        result_json = asyncio.run(audio_mod.master_album("test-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, result
    assert result["settings"]["archival_enabled"] is True

    archival_dir = audio_dir / "archival"
    assert archival_dir.is_dir(), "archival/ directory missing"

    for i in range(1, 4):
        arch = archival_dir / f"0{i}-track.wav"
        assert arch.exists(), f"Missing archival file: {arch.name}"
        info = sf.info(str(arch))
        assert info.subtype == "FLOAT", f"Expected FLOAT subtype, got {info.subtype}"
        # Sample rate matches the mastered delivery rate (96 kHz default)
        assert info.samplerate == 96000


def test_archival_stage_recorded_in_stages(tmp_path: Path) -> None:
    """stages dict records archival step when enabled."""
    from tools.mastering import config as mastering_config_mod
    from tools.mastering.config import DEFAULT_MASTERING_CONFIG

    audio_dir = _three_track_dir(tmp_path)
    custom = {**DEFAULT_MASTERING_CONFIG, "archival_enabled": True}

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()), \
         patch.object(mastering_config_mod, "load_mastering_config", return_value=custom):
        result_json = asyncio.run(audio_mod.master_album("test-album"))

    result = json.loads(result_json)
    stages = result["stages"]
    assert "archival" in stages
    assert stages["archival"]["status"] == "pass"
    assert stages["archival"]["count"] == 3
