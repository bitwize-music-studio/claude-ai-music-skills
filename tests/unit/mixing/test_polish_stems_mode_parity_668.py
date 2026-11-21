"""Analyze and polish choose stems vs. full mix by one rule (#668).

The layout import-audio writes is the keeper WAV beside ``stems/<track>/``.
The analyzer used stems only when there were no full-mix WAVs, while polish
used stems whenever ``stems/`` existed and looked up only stems-mode
analysis. So in that layout every analyzer recommendation (#336, e.g.
``already_dark`` → ``high_tame_db 0.0``) was dropped without a word.

Usage:
    python -m pytest tests/unit/mixing/test_polish_stems_mode_parity_668.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for _p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from handlers import _shared  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import mixing  # noqa: E402

pytestmark = pytest.mark.unit


def _dark_tone(path: Path, seconds: float = 1.0) -> None:
    """A low sine: no high-frequency energy, so the analyzer calls it dark."""
    t = np.arange(int(44100 * seconds)) / 44100
    mono = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.column_stack([mono, mono]), 44100, subtype="PCM_16")


class _FakeCache:
    def get_state(self) -> dict[str, Any]:
        return {"albums": {}}

    def get_state_ref(self) -> dict[str, Any]:
        return {"albums": {}}


@pytest.fixture
def album(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Stems for one track; tests add the full-mix WAV when they need it."""
    _dark_tone(tmp_path / "stems" / "01-dark" / "vocals.wav")
    _dark_tone(tmp_path / "stems" / "01-dark" / "synth.wav")
    monkeypatch.setattr(_shared, "cache", _FakeCache())
    monkeypatch.setattr(processing_helpers, "_resolve_audio_dir",
                        lambda *_a, **_k: (None, tmp_path))
    return tmp_path


def _analyze_then_polish(album: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    analysis = json.loads(asyncio.run(mixing.analyze_mix_issues("album", "electronic")))
    polish = json.loads(asyncio.run(mixing.polish_audio(
        album_slug="album", genre="electronic", use_stems=True,
        dry_run=True, analyzer_results=analysis,
    )))
    return analysis, polish


class TestStemsModeParity:
    def test_wav_beside_stems_analyzes_the_stems_polish_processes(self, album: Path) -> None:
        _dark_tone(album / "01-dark.wav")  # the keeper import-audio puts beside stems/

        analysis, polish = _analyze_then_polish(album)

        assert analysis["album_summary"]["source_mode"] == "stems"
        assert polish["summary"]["mode"] == "stems"
        applied = polish["summary"]["overrides_applied"]
        assert {(o["stem"], o["reason"]) for o in applied} >= {
            ("vocals", "already_dark"), ("synth", "already_dark"),
        }

    def test_stems_only_unchanged(self, album: Path) -> None:
        analysis, polish = _analyze_then_polish(album)

        assert analysis["album_summary"]["source_mode"] == "stems"
        assert polish["summary"]["mode"] == "stems"
        assert polish["summary"]["overrides_applied"]

    def test_full_mix_only_unchanged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _dark_tone(tmp_path / "01-dark.wav")
        monkeypatch.setattr(_shared, "cache", _FakeCache())
        monkeypatch.setattr(processing_helpers, "_resolve_audio_dir",
                            lambda *_a, **_k: (None, tmp_path))

        analysis, polish = _analyze_then_polish(tmp_path)

        assert analysis["album_summary"]["source_mode"] == "full_mix"
        assert polish["summary"]["mode"] == "full_mix"

    def test_polish_album_applies_the_recommendations(self, album: Path) -> None:
        _dark_tone(album / "01-dark.wav")

        result = json.loads(asyncio.run(mixing.polish_album("album", genre="electronic")))

        stage = result["stages"]["polish"]
        assert result["stages"]["pre_flight"]["mode"] == "stems"
        assert "already_dark" in {o["reason"] for o in stage["overrides_applied"]}
