"""Tests for ADM retry loop (max 2 cycles, ceiling tightening) in master_album (#290 step 9)."""

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

from handlers import _shared  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _write_sine_wav(
    path: Path,
    *,
    duration: float = 30.0,
    sample_rate: int = 44100,
    amplitude: float = 0.3,
    freq: float = 440.0,
) -> Path:
    import soundfile as sf

    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    sf.write(str(path), np.column_stack([mono, mono]), sample_rate, subtype="PCM_24")
    return path


def _install_album(
    monkeypatch: pytest.MonkeyPatch,
    audio_path: Path,
    album_slug: str,
    status: str = "In Progress",
) -> None:
    fake_state = {
        "albums": {
            album_slug: {
                "path": str(audio_path),
                "status": status,
                "tracks": {},
            }
        }
    }

    class _FakeCache:
        def get_state(self):
            return fake_state

        def get_state_ref(self):
            return fake_state

    monkeypatch.setattr(_shared, "cache", _FakeCache())


def _run_master_album(tmp_path: Path, album_slug: str = "adm-retry-album") -> dict:
    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        return json.loads(asyncio.run(audio_mod.master_album(album_slug=album_slug)))


# ---------------------------------------------------------------------------
# Test 1: Retry tightens ceiling and succeeds on second ADM cycle
# ---------------------------------------------------------------------------

def test_adm_retry_tightens_ceiling_on_clips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """First ADM call returns clips; second returns clean → pipeline completes.

    Verifies:
    - failed_stage is None (pipeline completes)
    - _adm_check_fn was called at least twice (once per ADM cycle)
    - The retry notice appears in the result
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _write_sine_wav(tmp_path / "02-track.wav", freq=330.0)
    _install_album(monkeypatch, tmp_path, album_slug)

    call_count = {"n": 0}

    def _fake_check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        call_count["n"] += 1
        # First two calls (one per file, cycle 1) → clips found
        # Subsequent calls (cycle 2) → clean
        clips = call_count["n"] <= 2
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 1 if clips else 0,
            "peak_db_decoded": -0.5 if clips else -1.2,
            "ceiling_db": ceiling_db,
            "clips_found": clips,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _fake_check)
    # Bypass mutagen (not installed in test env) — no-op metadata embed
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    # Capture the ceiling_db passed to master_track on each call so we can
    # pin the retry contract (#323 comment — cycle 2 must re-master with
    # the tightened ceiling, not just re-check). Wrap the real function so
    # downstream verify/ADM still see properly mastered output.
    mastered_ceilings: list[float] = []

    import tools.mastering.master_tracks as _mt_mod
    _real_master_track = _mt_mod.master_track

    def _capture_master_track(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real_master_track(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture_master_track)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    assert result.get("failed_stage") is None, (
        f"Expected pipeline to succeed, got failure: {result.get('failure_detail')}"
    )
    assert call_count["n"] >= 2, (
        f"Expected _adm_check_fn to be called at least twice, got {call_count['n']}"
    )
    # ADM retry notice must be present
    notices = result.get("notices", [])
    assert any("ADM cycle" in n for n in notices), (
        f"Expected ADM retry notice, got notices: {notices}"
    )

    # #323 comment: cycle 2 must re-master with the tightened ceiling.
    # Default ceiling is -1.0 dBTP; tightened by 0.5 dB → -1.5 dBTP.
    assert mastered_ceilings, (
        f"Expected master_track to be called, got no calls"
    )
    tightened = [c for c in mastered_ceilings if c <= -1.4]
    assert tightened, (
        f"Expected at least one master_track call with ceiling <= -1.5 dBTP "
        f"on cycle 2, got ceilings: {mastered_ceilings}"
    )


# ---------------------------------------------------------------------------
# Test 2: Retry halts after max ADM cycles (2) when clips always present
# ---------------------------------------------------------------------------

def test_adm_retry_halts_after_max_cycles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """_adm_check_fn always returns clips → pipeline halts after 2 ADM cycles.

    Verifies:
    - failed_stage == "adm_validation"
    - failure_detail contains adm_cycles == 2
    - clips_retry_eligible is True in failure_detail
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _always_clips(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 5,
            "peak_db_decoded": -0.3,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _always_clips)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    assert result["failed_stage"] == "adm_validation", (
        f"Expected failed_stage=adm_validation, got: {result.get('failed_stage')}"
    )
    fd = result.get("failure_detail", {})
    assert fd.get("adm_cycles") == 2, (
        f"Expected adm_cycles=2 in failure_detail, got: {fd.get('adm_cycles')}"
    )
    assert fd.get("clips_retry_eligible") is True, (
        f"Expected clips_retry_eligible=True in failure_detail, got: {fd.get('clips_retry_eligible')}"
    )
