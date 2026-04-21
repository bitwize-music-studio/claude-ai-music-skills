"""Per-track ADM ceiling helper behaves like the legacy closure.

Also contains an integration test that exercises the full master_album
orchestrator to verify the per-track ADM ceiling isolation contract:
a clean neighbour's ceiling must never be tightened because its
neighbour clips ADM on cycle 0.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers import _shared  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from handlers.processing import _album_stages as album_stages_mod  # noqa: E402
from handlers.processing.audio import _adm_adaptive_ceiling_per_track  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers (mirrored from test_master_album_adm_retry.py pattern)
# ---------------------------------------------------------------------------

def _write_sine_wav(
    path: Path,
    *,
    duration: float = 30.0,
    sample_rate: int = 44100,
    amplitude: float = 0.3,
    freq: float = 3500.0,
) -> Path:
    """Write a bright-frequency sine wave (3500 Hz = high_mid band → is_dark=False)."""
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


def _run_master_album(
    tmp_path: Path,
    album_slug: str = "per-track-ceiling-album",
    adm_enabled: bool = True,
) -> dict:
    """Invoke master_album end-to-end with ADM toggled via config patching."""
    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    from tools.mastering import config as _master_config
    real_load = _master_config.load_mastering_config

    def _load_with_adm() -> dict:
        cfg = real_load()
        cfg["adm_validation_enabled"] = adm_enabled
        return cfg

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(_master_config, "load_mastering_config", _load_with_adm):
        return json.loads(asyncio.run(audio_mod.master_album(album_slug=album_slug)))


class TestAdmAdaptiveCeilingPerTrack:
    def test_first_cycle_tightens_by_overshoot_plus_safety(self):
        entry = {"filename": "a.wav", "peak_db_decoded": -0.5}
        new, floored, diverging = _adm_adaptive_ceiling_per_track(
            entry, current=-1.5, history=[],
        )
        # overshoot = -0.5 - (-1.5) = 1.0; plus safety 0.3 → 1.3, capped at 1.0.
        assert new == pytest.approx(-2.5, abs=0.01)
        assert floored is False
        assert diverging is False

    def test_floor_reached(self):
        entry = {"filename": "a.wav", "peak_db_decoded": -0.1}
        new, floored, _ = _adm_adaptive_ceiling_per_track(
            entry, current=-5.5, history=[],
        )
        # Proposed < -6 → clamp to -6, floored=True.
        assert new == pytest.approx(-6.0)
        assert floored is True

    def test_divergence_detected_when_peak_grows(self):
        # After appending {ceiling=-2.5, worst_peak=-0.1}, history becomes:
        #   [-2] = {ceiling=-2.0, worst_peak=-0.3}  (pre-existing last entry)
        #   [-1] = {ceiling=-2.5, worst_peak=-0.1}  (newly appended)
        # d_ceiling = -2.0 - (-2.5) = 0.5 > 1e-3
        # d_peak    = -0.3 - (-0.1) = -0.2  (peak got WORSE as we tightened)
        # slope = -0.2 / 0.5 = -0.4 <= 0  → diverging
        entry = {"filename": "a.wav", "peak_db_decoded": -0.1}
        history = [
            {"ceiling": -1.5, "worst_peak": -0.5},
            {"ceiling": -2.0, "worst_peak": -0.3},  # last pre-existing entry
        ]
        new, floored, diverging = _adm_adaptive_ceiling_per_track(
            entry, current=-2.5, history=history,
        )
        assert diverging is True
        assert new == pytest.approx(-2.5)  # unchanged


# ---------------------------------------------------------------------------
# Integration test: clean-track ceiling isolation across ADM cycles
# ---------------------------------------------------------------------------

def test_clean_tracks_keep_original_ceiling_when_neighbor_clips_adm(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Clean tracks must never have their ceiling tightened because a
    neighbouring track clips ADM.

    Regression guard for bug #3: per-track ADM isolation. Before the
    per-track ceiling machinery was introduced, the whole album was
    re-mastered with the tightened ceiling — even tracks that had no
    ADM clips. This test pins the correct behaviour:

    - Cycle 0: only 02-clipper.wav clips. _stage_mastering is called
      with ctx.remaster_filenames=None (master all files from scratch).
    - Cycle 1: only 02-clipper.wav is re-mastered (remaster_filenames=
      {"02-clipper.wav"}). 01-clean.wav is skipped entirely.
    - After convergence: adm_validation status is "pass"; only
      02-clipper.wav has an entry in ctx.track_ceilings (captured via
      the _stage_mastering spy).
    """
    album_slug = "per-track-ceiling-album"
    _write_sine_wav(tmp_path / "01-clean.wav", freq=3500.0)
    _write_sine_wav(tmp_path / "02-clipper.wav", freq=3500.0)
    _install_album(monkeypatch, tmp_path, album_slug)

    # Script _adm_check_fn:
    #   - cycle 0: only 02-clipper.wav clips
    #   - cycle 1+: everything clean
    call_count = {"n": 0}
    original_ceiling = -1.0

    def _scripted_check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        call_count["n"] += 1
        fname = Path(path).name
        # The first pass checks both files (cycle 0). Only 02-clipper clips.
        # Peak at -0.5 dBTP to trigger adaptive tightening by ~0.8 dB.
        # On all subsequent calls (cycle 1), return clean.
        clips_this_call = (call_count["n"] <= 2 and fname == "02-clipper.wav")
        return {
            "filename": fname,
            "encoder_used": encoder,
            "clip_count": 1 if clips_this_call else 0,
            "peak_db_decoded": -0.5 if clips_this_call else ceiling_db - 0.5,
            "ceiling_db": ceiling_db,
            "clips_found": clips_this_call,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _scripted_check)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    # Spy on _stage_mastering to capture ctx.remaster_filenames and
    # ctx.track_ceilings on each mastering call.
    real_stage_mastering = album_stages_mod._stage_mastering
    remaster_filenames_history: list[set[str] | None] = []
    track_ceilings_snapshots: list[dict[str, float]] = []

    async def _spy_stage_mastering(ctx: album_stages_mod.MasterAlbumCtx) -> str | None:
        remaster_filenames_history.append(
            frozenset(ctx.remaster_filenames) if ctx.remaster_filenames is not None else None,
        )
        track_ceilings_snapshots.append(dict(ctx.track_ceilings))
        return await real_stage_mastering(ctx)

    monkeypatch.setattr(album_stages_mod, "_stage_mastering", _spy_stage_mastering)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    # Pipeline must complete without failure.
    assert result.get("failed_stage") is None, (
        f"Expected pipeline to succeed, got failure: {result.get('failure_detail')}"
    )

    # ADM must converge (pass), not warn-fallback.
    adm_stage = result.get("stages", {}).get("adm_validation", {})
    assert adm_stage.get("status") == "pass", (
        f"Expected adm_validation status='pass' after convergence, got: {adm_stage}"
    )

    # Cycle 0: remaster all (remaster_filenames=None before ADM runs).
    assert remaster_filenames_history, "Expected at least one _stage_mastering call"
    assert remaster_filenames_history[0] is None, (
        f"Cycle 0 must master all tracks (remaster_filenames=None), "
        f"got: {remaster_filenames_history[0]}"
    )

    # Cycle 1: selective remaster of 02-clipper.wav only.
    assert len(remaster_filenames_history) >= 2, (
        f"Expected at least 2 _stage_mastering calls (cycle 0 + cycle 1), "
        f"got {len(remaster_filenames_history)}: {remaster_filenames_history}"
    )
    assert "02-clipper.wav" in remaster_filenames_history[1], (
        f"Cycle 1 must remaster 02-clipper.wav, got: {remaster_filenames_history[1]}"
    )
    assert "01-clean.wav" not in remaster_filenames_history[1], (
        f"Cycle 1 must NOT remaster 01-clean.wav (it was clean), "
        f"got: {remaster_filenames_history[1]}"
    )

    # ctx.track_ceilings must contain 02-clipper.wav with a tightened ceiling.
    # The tightened ceiling snapshot is captured on the cycle-1 mastering call.
    cycle1_ceilings = track_ceilings_snapshots[1]
    assert "02-clipper.wav" in cycle1_ceilings, (
        f"Expected 02-clipper.wav in track_ceilings on cycle 1, "
        f"got: {cycle1_ceilings}"
    )
    assert "01-clean.wav" not in cycle1_ceilings, (
        f"01-clean.wav must NOT be in track_ceilings (it never clipped), "
        f"got: {cycle1_ceilings}"
    )
    assert cycle1_ceilings["02-clipper.wav"] < original_ceiling, (
        f"02-clipper.wav ceiling must be tighter than original {original_ceiling} dBTP, "
        f"got: {cycle1_ceilings['02-clipper.wav']}"
    )
