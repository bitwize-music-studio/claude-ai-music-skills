"""Integration tests for the measure_album_signature MCP handler (#290 phase 3a)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402


def _write_sine_wav(path: Path, *, duration: float = 60.0, sample_rate: int = 44100,
                    freq: float = 220.0, amplitude: float = 0.3) -> Path:
    """Write a simple stereo sine-wave WAV long enough for stl_95 to be defined."""
    import soundfile as sf

    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, sample_rate, subtype="PCM_24")
    return path


def _setup_album(tmp_path: Path, track_count: int = 3) -> Path:
    mastered = tmp_path / "mastered"
    mastered.mkdir()
    for i in range(1, track_count + 1):
        # Vary frequency across tracks so analyzer produces non-identical
        # signatures even on synthetic sines.
        _write_sine_wav(mastered / f"{i:02d}-track.wav", freq=200.0 + i * 30.0)
    return tmp_path


def test_measure_album_signature_no_anchor_returns_tracks_and_album(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=3)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(album_slug="test-album", subfolder="mastered")
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["album_slug"] == "test-album"
    assert result["settings"]["subfolder"] == "mastered"
    assert result["settings"]["genre"] is None
    assert "anchor" not in result     # omitted when no genre + no override

    assert len(result["tracks"]) == 3
    assert result["album"]["track_count"] == 3
    assert result["album"]["median"]["lufs"] is not None
    assert result["tracks"][0]["index"] == 1
    assert result["tracks"][0]["filename"] == "01-track.wav"


def test_measure_album_signature_missing_subfolder_returns_error(tmp_path: Path) -> None:
    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="nonexistent",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_measure_album_signature_subfolder_escape_blocked(tmp_path: Path) -> None:
    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="../../../etc",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "escape" in result["error"].lower() or "invalid" in result["error"].lower()


def test_measure_album_signature_no_wavs_returns_error(tmp_path: Path) -> None:
    (tmp_path / "mastered").mkdir()
    # No WAV files.

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(album_slug="test-album", subfolder="mastered")
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "no wav" in result["error"].lower()
