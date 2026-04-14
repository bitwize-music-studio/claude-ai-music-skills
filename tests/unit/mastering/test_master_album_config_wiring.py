"""Integration tests: master_album consumes mastering config for delivery.

Verifies that load_mastering_config() defaults propagate through the full
master_album pipeline (stages 1-7) to the mastered output file, and that
the response surfaces the resolved delivery settings plus an upsampling
notice when the output rate exceeds the source rate.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
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
    def __init__(self) -> None:
        self._state: dict = {}

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state

    def set_state(self, state: dict) -> None:  # pragma: no cover - not used in tests
        self._state = state


def _write_tone_wav(
    path: Path,
    sr: int = 44100,
    duration: float = 3.0,
    freq: float = 440.0,
) -> None:
    """Pure tone with matching L/R channels — mono-compat / phase-friendly."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone = 0.3 * np.sin(2 * np.pi * freq * t)
    stereo = np.column_stack([tone, tone])
    sf.write(str(path), stereo, sr, subtype="PCM_16")


@pytest.fixture
def three_track_audio_dir(tmp_path: Path) -> Path:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for i, freq in enumerate([440.0, 660.0, 880.0], start=1):
        _write_tone_wav(audio_dir / f"0{i}-track.wav", freq=freq)
    return audio_dir


def test_master_album_outputs_24bit_96khz_with_upsampling_notice(
    three_track_audio_dir: Path,
) -> None:
    """Default config: output is 24/96 WAV and response includes notices."""

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, three_track_audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()):
        result_json = asyncio.run(audio_mod.master_album("test-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, result

    settings = result["settings"]
    assert settings["output_bits"] == 24
    assert settings["output_sample_rate"] == 96000
    assert settings["source_sample_rate"] == 44100
    assert settings["upsampled_from_source"] is True

    # Notices list includes the upsampling caveat with honesty language
    notices = result.get("notices", [])
    assert any(
        "upsampled" in n.lower()
        and "44.1" in n
        and "96" in n
        and "no additional audio information" in n.lower()
        for n in notices
    ), f"Expected upsampling notice, got: {notices}"

    # Mastered output files exist at 24/96
    for i in range(1, 4):
        mastered = three_track_audio_dir / "mastered" / f"0{i}-track.wav"
        assert mastered.exists(), f"Missing: {mastered}"
        info = sf.info(str(mastered))
        assert info.samplerate == 96000
        assert info.subtype == "PCM_24"


def test_master_album_with_genre_preset_still_produces_24_96(
    three_track_audio_dir: Path,
) -> None:
    """Regression: genre argument must not silently downgrade to 16-bit.

    Before fixing the genre-preset YAML defaults, passing genre=electronic
    caused output to drop to 16-bit PCM because all genre presets
    inherited output_bits=16 from the defaults block.
    """

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, three_track_audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()):
        result_json = asyncio.run(
            audio_mod.master_album("test-album", genre="electronic")
        )

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, result

    assert result["settings"]["genre"] == "electronic"
    assert result["settings"]["output_bits"] == 24
    assert result["settings"]["output_sample_rate"] == 96000

    mastered = three_track_audio_dir / "mastered" / "01-track.wav"
    info = sf.info(str(mastered))
    assert info.samplerate == 96000
    assert info.subtype == "PCM_24"


def test_master_album_no_upsampling_notice_when_rates_match(
    three_track_audio_dir: Path,
) -> None:
    """delivery_sample_rate=44100 → no upsampling notice."""
    from tools.mastering import config as mastering_config_mod
    from tools.mastering.config import DEFAULT_MASTERING_CONFIG

    custom = {**DEFAULT_MASTERING_CONFIG, "delivery_sample_rate": 44100}

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, three_track_audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()), \
         patch.object(mastering_config_mod, "load_mastering_config", return_value=custom):
        result_json = asyncio.run(audio_mod.master_album("test-album"))

    result = json.loads(result_json)
    assert result["settings"]["output_sample_rate"] == 44100
    assert result["settings"]["upsampled_from_source"] is False

    notices = result.get("notices", [])
    assert not any("upsampled" in n.lower() for n in notices), (
        f"Did not expect upsampling notice at matched rates, got: {notices}"
    )

    mastered = three_track_audio_dir / "mastered" / "01-track.wav"
    info = sf.info(str(mastered))
    assert info.samplerate == 44100


@pytest.fixture
def two_track_long_audio_dir(tmp_path: Path) -> Path:
    """Two 30s stereo WAVs — long enough for analyze_track to produce
    signature metrics (STL-95 needs ≥20 short-term windows ≈ 23s).

    The two tracks differ in peak level and tonal center so the anchor
    selector has something meaningful to score.
    """
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    sr = 44100
    duration = 30.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Track 1: lower-peak, 440 Hz — moderate peak, pop-ish
    tone1 = 0.3 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(audio_dir / "01-track.wav"),
             np.column_stack([tone1, tone1]), sr, subtype="PCM_16")
    # Track 2: hotter-peak, 660 Hz — closer to ceiling
    tone2 = 0.7 * np.sin(2 * np.pi * 660.0 * t)
    sf.write(str(audio_dir / "02-track.wav"),
             np.column_stack([tone2, tone2]), sr, subtype="PCM_16")
    return audio_dir


def test_master_album_records_anchor_selection_stage(
    two_track_long_audio_dir: Path,
) -> None:
    """#290 phase 2: master_album runs anchor selector after analysis."""

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, two_track_long_audio_dir

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()):
        result_json = asyncio.run(
            audio_mod.master_album("test-album", genre="pop")
        )

    result = json.loads(result_json)
    stages = result["stages"]
    assert "anchor_selection" in stages
    anchor = stages["anchor_selection"]
    assert anchor["status"] in ("pass", "warn")
    selected = anchor["selected_index"]
    assert selected is None or 1 <= selected <= 2
    assert anchor["method"] in (
        "composite", "tie_breaker", "override", "no_eligible_tracks"
    )
    assert "scores" in anchor
    assert isinstance(anchor["scores"], list)
    assert len(anchor["scores"]) == 2


def test_master_album_honors_anchor_track_override(
    two_track_long_audio_dir: Path,
) -> None:
    """#290 phase 2: anchor_track frontmatter overrides composite scoring.

    Exercises the full override chain: state cache albums[slug].anchor_track
    → handler reads it via _shared.cache.get_state() → passes override_index
    to select_anchor → anchor_selection stage records method=="override".
    This is the end-to-end regression test for review finding C1.
    """

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, two_track_long_audio_dir

    # Pre-populate the mock state cache exactly as the indexer would
    # after parsing a README with `anchor_track: 2` in frontmatter.
    mock_cache = _MockCache()
    mock_cache._state = {
        "albums": {
            "test-album": {
                "anchor_track": 2,
                "tracks": {},
            },
        },
    }

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", mock_cache):
        result_json = asyncio.run(
            audio_mod.master_album("test-album", genre="pop")
        )

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, result
    anchor = result["stages"]["anchor_selection"]
    assert anchor["method"] == "override"
    assert anchor["selected_index"] == 2
    assert anchor["override_index"] == 2
    assert anchor["override_reason"] is None
