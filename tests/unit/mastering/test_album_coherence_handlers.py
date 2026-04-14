"""Integration tests for album_coherence_check / album_coherence_correct (#290 phase 3b)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

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
    import soundfile as sf

    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, sample_rate, subtype="PCM_24")
    return path


def _setup_mastered_album(tmp_path: Path, loudness_amplitudes: list[float]) -> Path:
    """Create mastered/ subdir with N tracks at given amplitudes (→ varying LUFS)."""
    mastered = tmp_path / "mastered"
    mastered.mkdir()
    for i, amp in enumerate(loudness_amplitudes, start=1):
        _write_sine_wav(
            mastered / f"{i:02d}-track.wav",
            freq=200.0 + i * 30.0,
            amplitude=amp,
        )
    return tmp_path


def test_album_coherence_check_flags_lufs_outlier(tmp_path: Path) -> None:
    # Track 2 is ~2-3 LU louder than 1 and 3 → LUFS outlier.
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.6, 0.3])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_check(
                album_slug="test-album", subfolder="mastered",
                genre="pop", anchor_track=1,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert "summary" in result
    assert result["summary"]["track_count"] == 3
    # At least one outlier (track 2)
    assert result["summary"]["outlier_count"] >= 1
    # classifications should reveal which track is the outlier
    outliers = [c for c in result["classifications"] if c["is_outlier"]]
    assert any(c["index"] == 2 for c in outliers)


def test_album_coherence_check_errors_without_genre_and_anchor(tmp_path: Path) -> None:
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.3])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_check(
                album_slug="test-album", subfolder="mastered",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "genre" in result["error"].lower() or "anchor" in result["error"].lower()


def test_album_coherence_check_falls_back_to_defaults_when_genre_empty_with_anchor(tmp_path: Path) -> None:
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.35])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_check(
                album_slug="test-album", subfolder="mastered",
                anchor_track=1,  # no genre — should use hardcoded defaults
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["settings"]["tolerances"]["coherence_stl_95_lu"] == pytest.approx(0.5)


def _setup_full_album(tmp_path: Path, amplitudes: list[float]) -> Path:
    """Create polished/ + mastered/ subdirs with matching WAV names."""
    polished = tmp_path / "polished"
    polished.mkdir()
    mastered = tmp_path / "mastered"
    mastered.mkdir()
    for i, amp in enumerate(amplitudes, start=1):
        name = f"{i:02d}-track.wav"
        _write_sine_wav(polished / name, freq=200.0 + i * 30.0, amplitude=amp)
        _write_sine_wav(mastered / name, freq=200.0 + i * 30.0, amplitude=amp)
    return tmp_path


def test_album_coherence_correct_dry_run_does_not_write(tmp_path: Path) -> None:
    _setup_full_album(tmp_path, amplitudes=[0.3, 0.6, 0.3])
    mastered_bytes_before = (tmp_path / "mastered" / "02-track.wav").read_bytes()

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                check_subfolder="mastered",
                anchor_track=1,
                dry_run=True,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["dry_run"] is True
    assert "plan" in result
    # Mastered file unchanged
    assert (tmp_path / "mastered" / "02-track.wav").read_bytes() == mastered_bytes_before


def test_album_coherence_correct_errors_when_polished_missing(tmp_path: Path) -> None:
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.6])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                anchor_track=1,
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "polished" in result["error"].lower() or "not found" in result["error"].lower()


def test_album_coherence_correct_errors_when_polished_missing_a_track(tmp_path: Path) -> None:
    _setup_full_album(tmp_path, amplitudes=[0.3, 0.6])
    (tmp_path / "polished" / "02-track.wav").unlink()

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                anchor_track=1,
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "missing" in result["error"].lower() or "02-track" in result["error"]


def test_album_coherence_correct_remasters_lufs_outlier(tmp_path: Path) -> None:
    # Track 2 starts much louder (amplitude 0.6 → ~-7 LUFS vs -14 LUFS).
    # After correction it should land within 1 dB of track 1 (anchor).
    _setup_full_album(tmp_path, amplitudes=[0.3, 0.6, 0.3])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                check_subfolder="mastered",
                anchor_track=1,
                dry_run=False,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["dry_run"] is False
    assert result["summary"]["corrected"] >= 1
    assert result["summary"]["outliers_after"] <= result["summary"]["outliers_before"]
    correction = next(c for c in result["corrections"] if c["filename"] == "02-track.wav")
    assert correction["status"] == "ok"
    assert abs(correction["delta_from_anchor"]) < 1.0
