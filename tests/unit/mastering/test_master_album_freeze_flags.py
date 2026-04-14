"""Tests for --freeze-signature / --new-anchor MCP params (#290 phase 4)."""

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


def _write_sine_wav(path: Path, *, amplitude: float = 0.3) -> Path:
    import soundfile as sf
    rate = 44100
    n = int(2.0 * rate)
    t = np.arange(n) / rate
    mono = amplitude * np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, rate, subtype="PCM_24")
    return path


def _install_album(monkeypatch, audio_path: Path, slug: str, status: str = "In Progress"):
    from handlers import _shared
    fake = {"albums": {slug: {"path": str(audio_path), "status": status, "tracks": {}}}}
    class _FC:
        def get_state(self): return fake
        def get_state_ref(self): return fake
    monkeypatch.setattr(_shared, "cache", _FC())


def test_freeze_and_new_anchor_mutually_exclusive(tmp_path, monkeypatch):
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, "dual-album")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(
            album_slug="dual-album",
            freeze_signature=True,
            new_anchor=True,
        ))

    result = json.loads(result_json)
    assert result["failed_stage"] == "pre_flight"
    assert "mutually exclusive" in result["failure_detail"]["reason"].lower()


def test_released_album_missing_signature_halts(tmp_path, monkeypatch):
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, "released-no-sig", status="Released")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="released-no-sig"))

    result = json.loads(result_json)
    assert result["failed_stage"] == "freeze_decision"
    assert "released" in result["failure_detail"]["reason"].lower()
    assert "album_signature.yaml" in result["failure_detail"]["reason"].lower()


def test_freeze_signature_flag_without_file_errors(tmp_path, monkeypatch):
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, "freeze-no-sig")  # In Progress

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(
            album_slug="freeze-no-sig", freeze_signature=True,
        ))

    result = json.loads(result_json)
    assert result["failed_stage"] == "freeze_decision"
    assert "requested" in result["failure_detail"]["reason"].lower()
