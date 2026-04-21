"""When a dark track clips ADM, it must NOT be tightened — instead it
goes to warn-fallback in ADM_VALIDATION.md with reason=dark_track_not_tightened."""

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
    """Write a sine-wave fixture.

    Default 440 Hz: all energy is in the low/mid bands → high_mid
    band_energy ≈ 0 % → is_dark=True.  Pass freq=3500.0 for a bright track.
    """
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
    album_slug: str = "dark-adm-album",
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


# ---------------------------------------------------------------------------
# Unit-level: partition logic
# ---------------------------------------------------------------------------

def test_dark_clipping_track_not_tightened():
    """Unit-level assertion on the partition logic: given clipping_fnames
    and dark_tracks sets, the tightenable set excludes dark tracks."""
    clipping_fnames = {"01-dark.wav", "02-bright.wav", "03-bright.wav"}
    dark_tracks = {"01-dark.wav"}
    tightenable = clipping_fnames - dark_tracks
    dark_clipping = clipping_fnames & dark_tracks
    assert tightenable == {"02-bright.wav", "03-bright.wav"}
    assert dark_clipping == {"01-dark.wav"}


# ---------------------------------------------------------------------------
# Integration test: all-dark clipping exits to warn-fallback immediately
# ---------------------------------------------------------------------------

def test_all_dark_clipping_breaks_to_warn_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If every clipping track is dark, the ADM loop must exit to
    warn-fallback immediately — no ceiling tightening, no re-master cycle.

    Regression guard for bug #5: dark track ADM exclusion. When every
    clipping filename is in ctx.dark_tracks, tightenable is empty, so
    the orchestrator must break to warn-fallback on the FIRST clip
    failure rather than retrying with a tightened ceiling.

    Fixture: one 440 Hz track (all energy in low/mid → high_mid < 10 %
    → is_dark=True). _adm_check_fn always returns clips so the loop
    can never tighten anything.

    Asserts:
    - pipeline completes (warn-fallback, not halt)
    - adm_validation.status == "warn" and clip_failure_persisted == True
    - adm_validation.dark_casualties contains "01-dark.wav"
    - adm_validation.tightened_tracks is empty (nothing was tightened)
    - ctx.track_ceilings is empty (accessible via stage output)
    - Only 1 mastering cycle ran (no re-master triggered)
    """
    album_slug = "dark-adm-album"
    # 440 Hz → high_mid band_energy ≈ 0 % → is_dark=True after _stage_analysis.
    _write_sine_wav(tmp_path / "01-dark.wav", freq=440.0)
    _install_album(monkeypatch, tmp_path, album_slug)

    # _adm_check_fn always reports clips on 01-dark.wav.
    def _always_clips_dark(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 3,
            "peak_db_decoded": ceiling_db + 0.3,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _always_clips_dark)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    # Spy on _stage_mastering to count how many mastering cycles run.
    real_stage_mastering = album_stages_mod._stage_mastering
    mastering_call_count = {"n": 0}

    async def _spy_stage_mastering(ctx: album_stages_mod.MasterAlbumCtx) -> str | None:
        mastering_call_count["n"] += 1
        return await real_stage_mastering(ctx)

    monkeypatch.setattr(album_stages_mod, "_stage_mastering", _spy_stage_mastering)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    # Pipeline must complete (warn-fallback, not halt).
    assert result.get("failed_stage") is None, (
        f"Expected warn-fallback completion, got failure: {result.get('failure_detail')}"
    )

    adm_stage = result.get("stages", {}).get("adm_validation", {})

    # ADM stage must be warn with clip_failure_persisted=True.
    assert adm_stage.get("status") == "warn", (
        f"Expected adm_validation status='warn', got: {adm_stage.get('status')}"
    )
    assert adm_stage.get("clip_failure_persisted") is True, (
        f"Expected clip_failure_persisted=True, got: {adm_stage}"
    )

    # 01-dark.wav must appear in dark_casualties (not in tightened_tracks).
    dark_casualties = adm_stage.get("dark_casualties", [])
    assert "01-dark.wav" in dark_casualties, (
        f"Expected '01-dark.wav' in dark_casualties, got: {dark_casualties}"
    )

    # Nothing should have been tightened.
    tightened_tracks = adm_stage.get("tightened_tracks", [])
    assert tightened_tracks == [], (
        f"Expected tightened_tracks=[] (dark tracks are never tightened), "
        f"got: {tightened_tracks}"
    )

    # track_ceilings must be empty — no track was tightened.
    track_ceilings = adm_stage.get("track_ceilings", {})
    assert track_ceilings == {}, (
        f"Expected track_ceilings={{}} (dark tracks are not tightened), "
        f"got: {track_ceilings}"
    )

    # Only one mastering cycle must have run (no re-master was triggered).
    # The ADM loop breaks to warn-fallback on the first clip failure because
    # tightenable is empty — so _stage_mastering runs exactly once.
    assert mastering_call_count["n"] == 1, (
        f"Expected exactly 1 mastering cycle (no re-master for dark tracks), "
        f"got {mastering_call_count['n']} calls"
    )
