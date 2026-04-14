"""Integration tests for Stage 5.4 (album-ceiling guard) inside
master_album (#290 phase 5, step 8)."""

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


def _run_master_album(tmp_path: Path, album_slug: str = "ceiling-album") -> dict:
    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        return json.loads(asyncio.run(
            audio_mod.master_album(album_slug=album_slug)
        ))


def test_ceiling_guard_passes_when_all_in_spec(tmp_path: Path, monkeypatch) -> None:
    # Three similar-amplitude sines → all within 2 LU of median after master.
    _write_sine_wav(tmp_path / "01-a.wav", amplitude=0.3, freq=220.0)
    _write_sine_wav(tmp_path / "02-b.wav", amplitude=0.3, freq=330.0)
    _write_sine_wav(tmp_path / "03-c.wav", amplitude=0.3, freq=440.0)
    _install_album(monkeypatch, tmp_path, "ceiling-album")

    result = _run_master_album(tmp_path)
    assert result.get("failed_stage") is None
    assert "ceiling_guard" in result["stages"]
    cg = result["stages"]["ceiling_guard"]
    assert cg["status"] == "pass"
    assert cg["action"] == "no_op"
    assert all(r["classification"] == "in_spec" for r in cg["tracks"])


def test_ceiling_guard_applies_pull_down_for_small_overshoot(
    tmp_path: Path, monkeypatch
) -> None:
    # Patch compute_overshoots to force one "correctable" row so we don't
    # depend on mastering producing exact LUFS deltas that bracket the
    # threshold. Verifies the integration path, not the math.
    _write_sine_wav(tmp_path / "01-a.wav", amplitude=0.3)
    _write_sine_wav(tmp_path / "02-b.wav", amplitude=0.3, freq=330.0)
    _install_album(monkeypatch, tmp_path, "ceiling-album")

    real_compute = audio_mod._ceiling_guard_compute_overshoots

    def _forced(tracks):
        r = real_compute(tracks)
        if r["tracks"]:
            r["tracks"][0] = {
                **r["tracks"][0],
                "overshoot_lu":   0.3,
                "classification": "correctable",
                "pull_down_db":   -0.3,
            }
        return r

    monkeypatch.setattr(
        audio_mod, "_ceiling_guard_compute_overshoots", _forced
    )

    result = _run_master_album(tmp_path)
    assert result.get("failed_stage") is None, result.get("failure_detail")
    cg = result["stages"]["ceiling_guard"]
    assert cg["status"] == "pass"
    assert cg["action"] == "pull_down"
    assert cg["pulled_down"] == ["01-a.wav"]
    # After pull-down, a re-verify happened — verification stage should
    # still show all_within_spec=true.
    assert result["stages"]["verification"]["all_within_spec"] is True


def test_ceiling_guard_halts_on_large_overshoot(tmp_path: Path, monkeypatch) -> None:
    _write_sine_wav(tmp_path / "01-a.wav", amplitude=0.3)
    _write_sine_wav(tmp_path / "02-b.wav", amplitude=0.3, freq=330.0)
    _install_album(monkeypatch, tmp_path, "ceiling-album")

    real_compute = audio_mod._ceiling_guard_compute_overshoots

    def _forced(tracks):
        r = real_compute(tracks)
        if r["tracks"]:
            r["tracks"][0] = {
                **r["tracks"][0],
                "overshoot_lu":   1.5,
                "classification": "halt",
                "pull_down_db":   None,
            }
        return r

    monkeypatch.setattr(
        audio_mod, "_ceiling_guard_compute_overshoots", _forced
    )

    result = _run_master_album(tmp_path)
    assert result["failed_stage"] == "ceiling_guard"
    assert result["stage_reached"] == "ceiling_guard"
    cg = result["stages"]["ceiling_guard"]
    assert cg["status"] == "fail"
    assert any(r["classification"] == "halt" for r in cg["tracks"])
    assert "overshoot" in result["failure_detail"]["reason"].lower()


def test_ceiling_guard_skipped_for_single_track_album(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sine_wav(tmp_path / "01-solo.wav", amplitude=0.3)
    _install_album(monkeypatch, tmp_path, "solo-album")

    result = _run_master_album(tmp_path, album_slug="solo-album")
    assert result.get("failed_stage") is None
    cg = result["stages"]["ceiling_guard"]
    # Single-track: median = track's own lufs, overshoot is always <= 0.
    assert cg["status"] == "pass"
    assert cg["action"] == "no_op"
