"""Integration tests for signature persistence inside master_album (#290 phase 4)."""

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
from tools.mastering.signature_persistence import (  # noqa: E402
    SIGNATURE_FILENAME,
    read_signature_file,
)


def _write_sine_wav(path: Path, *, duration: float = 30.0, sample_rate: int = 44100,
                    freq: float = 220.0, amplitude: float = 0.3) -> Path:
    import soundfile as sf
    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, sample_rate, subtype="PCM_24")
    return path


def _install_album(monkeypatch, audio_path: Path, album_slug: str,
                   status: str = "In Progress") -> None:
    from handlers import _shared
    fake_state = {"albums": {album_slug: {
        "path": str(audio_path),
        "status": status,
        "tracks": {},
    }}}
    class _FakeCache:
        def get_state(self): return fake_state
        def get_state_ref(self): return fake_state
    monkeypatch.setattr(_shared, "cache", _FakeCache())


def test_master_album_writes_signature_on_success(tmp_path: Path, monkeypatch) -> None:
    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _write_sine_wav(tmp_path / "02-track.wav", amplitude=0.32, freq=330.0)
    _install_album(monkeypatch, tmp_path, album_slug="sig-album")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="sig-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, f"master_album failed: {result.get('failure_detail')}"
    assert "signature_persist" in result["stages"]
    assert result["stages"]["signature_persist"]["status"] == "pass"

    # File exists and round-trips.
    sig = read_signature_file(tmp_path)
    assert sig is not None
    assert sig["album_slug"] == "sig-album"
    assert sig["anchor"]["index"] in (1, 2)
    assert sig["delivery_targets"]["tp_ceiling_db"] == -1.0
    assert sig["delivery_targets"]["target_lufs"] == -14.0

    # Verify numpy coercion produced native Python floats.
    anchor_sig = sig["anchor"]["signature"]
    assert anchor_sig is not None
    assert isinstance(anchor_sig["peak_db"], float)
    assert isinstance(anchor_sig["lufs"], float)

    # Verify method, pipeline, album_median, and plugin version fallback.
    assert sig["anchor"]["method"] in ("composite", "tie_breaker", "override")
    assert sig["pipeline"]["source_sample_rate"] == 44100
    assert sig["album_median"]["lufs"] is not None
    assert sig["plugin_version"] == "unknown"  # PLUGIN_ROOT=None in tests


def test_master_album_does_not_write_signature_on_stage_failure(tmp_path: Path, monkeypatch) -> None:
    # No WAV files → pre_flight fails.
    _install_album(monkeypatch, tmp_path, album_slug="empty-album")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="empty-album"))

    result = json.loads(result_json)
    assert result["failed_stage"] == "pre_flight"
    assert not (tmp_path / SIGNATURE_FILENAME).exists()


def test_master_album_signature_write_failure_is_nonfatal(tmp_path: Path, monkeypatch) -> None:
    """Stage 7.5 warnings when signature write fails — master_album still succeeds."""
    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _install_album(monkeypatch, tmp_path, album_slug="warn-album")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    def _raising_write(*_args, **_kw):
        from tools.mastering.signature_persistence import SignaturePersistenceError
        raise SignaturePersistenceError("simulated failure")

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(audio_mod, "write_signature_file", _raising_write):
        result_json = asyncio.run(audio_mod.master_album(album_slug="warn-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None
    assert result["stages"]["signature_persist"]["status"] == "warn"
    assert "simulated failure" in result["stages"]["signature_persist"]["error"]
