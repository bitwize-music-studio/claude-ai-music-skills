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


def test_measure_album_signature_with_genre_returns_anchor_block(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=3)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="mastered", genre="pop",
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["settings"]["genre"] == "pop"
    assert "anchor" in result
    # Short sine-wave fixtures typically satisfy stl_95 eligibility —
    # but if scoring can't converge (pathological synthetic audio), the
    # selector still returns a structured dict; assert on shape, not
    # specific index.
    anchor = result["anchor"]
    assert "selected_index" in anchor
    assert "method" in anchor
    assert "scores" in anchor
    assert isinstance(anchor["scores"], list)
    assert len(anchor["scores"]) == 3
    if anchor["selected_index"] is not None:
        assert anchor["deltas"]  # non-empty when a selection was made
        # Exactly one delta row should be flagged as the anchor.
        assert sum(1 for r in anchor["deltas"] if r["is_anchor"]) == 1


def test_measure_album_signature_with_explicit_anchor_track(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=4)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album",
                subfolder="mastered",
                anchor_track=2,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert "anchor" in result
    anchor = result["anchor"]
    assert anchor["selected_index"] == 2
    assert anchor["method"] == "override"
    assert anchor["override_index"] == 2
    assert len(anchor["deltas"]) == 4
    assert anchor["deltas"][1]["is_anchor"] is True  # track #2 (1-based)


def test_measure_album_signature_unknown_genre_returns_error(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=2)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="mastered",
                genre="not-a-real-genre",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "unknown genre" in result["error"].lower()
    # build_effective_preset surfaces the catalogue for fix-forward guidance.
    assert "available_genres" in result


def test_measure_album_signature_out_of_range_override_falls_through(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=3)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="mastered",
                anchor_track=99,  # out of range
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert "anchor" in result
    anchor = result["anchor"]
    # Override is rejected but still surfaces in the block for diagnostics.
    assert anchor["override_index"] == 99
    assert anchor["override_reason"] is not None
    assert "out of range" in anchor["override_reason"].lower()
    # method falls through to composite, tie_breaker, or no_eligible_tracks.
    assert anchor["method"] in ("composite", "tie_breaker", "no_eligible_tracks")
