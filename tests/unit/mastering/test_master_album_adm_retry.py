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
    freq: float = 3500.0,
) -> Path:
    """Write a sine-wave fixture at a "bright" frequency (default 3500 Hz).

    3500 Hz is inside the high_mid band (2000-6000 Hz) so analyze_track
    sees is_dark=False. These fixtures exercise the ADM tightening path;
    dark-track exclusion is covered by test_master_album_dark_track_adm.py.
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
    album_slug: str = "adm-retry-album",
    adm_enabled: bool = True,
) -> dict:
    """Invoke master_album with ADM toggled on/off via config patching.

    ADM is opt-in (default false) as of the adm_validation_enabled
    config gate. These ADM-retry tests all test ADM-specific logic, so
    default to True and let new tests override when exercising the
    skip path.
    """
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
    _write_sine_wav(tmp_path / "02-track.wav", freq=4500.0)
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
# Test 2: Retry warn-falls-back after max cycles (was: halts) — #323 follow-up
# ---------------------------------------------------------------------------

def test_adm_retry_warn_fallback_after_max_cycles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """_adm_check_fn always returns clips → pipeline completes with WARN,
    does not halt.

    Per #323 follow-up: any album must complete rather than halting on
    pathological dense-transient content. The final ADM state is preserved
    as a warn on the stage plus a human-readable warning; the
    ADM_VALIDATION.md sidecar has per-track detail so operators can
    republish manually if the flag matters for distribution.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _always_clips(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        # Peak tracks the current ceiling so adaptive tightening advances
        # but never converges.
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 5,
            "peak_db_decoded": ceiling_db + 0.3,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _always_clips)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    # Warn-fallback: pipeline completes rather than halting.
    assert result.get("failed_stage") is None, (
        f"Expected pipeline to complete (warn-fallback), got failure: "
        f"{result.get('failure_detail')}"
    )
    adm_stage = result.get("stages", {}).get("adm_validation", {})
    assert adm_stage.get("status") == "warn", (
        f"Expected adm_validation stage status=warn, got: {adm_stage.get('status')}"
    )
    assert adm_stage.get("clip_failure_persisted") is True, (
        f"Expected clip_failure_persisted=True on warn-fallback, got: {adm_stage}"
    )
    warnings = result.get("warnings", [])
    assert any("ADM validation" in w and "clips persist on" in w for w in warnings), (
        f"Expected ADM warn-fallback warning, got warnings: {warnings}"
    )

    # Post-loop warn-fallback must populate the new per-track fields
    # on adm_validation stage so operators can inspect which tracks
    # were tightened vs skipped as dark casualties.
    stage = result.get("stages", {}).get("adm_validation")
    assert stage is not None
    assert "dark_casualties" in stage, (
        f"Expected dark_casualties key in adm_validation stage, got: {list(stage.keys())}"
    )
    assert "tightened_tracks" in stage, (
        f"Expected tightened_tracks key in adm_validation stage, got: {list(stage.keys())}"
    )
    assert "track_ceilings" in stage, (
        f"Expected track_ceilings key in adm_validation stage, got: {list(stage.keys())}"
    )
    assert isinstance(stage["dark_casualties"], list), (
        f"Expected dark_casualties to be a list, got: {type(stage['dark_casualties'])}"
    )
    assert isinstance(stage["tightened_tracks"], list), (
        f"Expected tightened_tracks to be a list, got: {type(stage['tightened_tracks'])}"
    )
    assert isinstance(stage["track_ceilings"], dict), (
        f"Expected track_ceilings to be a dict, got: {type(stage['track_ceilings'])}"
    )
    # This fixture has one bright (non-dark) track that clips every cycle.
    # The _always_clips stub returns peak = ceiling + 0.3, so adaptive
    # tightening does make progress each cycle (new_ceiling < current),
    # meaning the track ends up in tightened_tracks (not dark_casualties).
    assert len(stage["tightened_tracks"]) >= 1 or len(stage["dark_casualties"]) >= 1, (
        f"Expected at least one track in tightened_tracks or dark_casualties, "
        f"got tightened={stage['tightened_tracks']}, dark={stage['dark_casualties']}"
    )
    assert stage["tightened_tracks"] == ["01-track.wav"], (
        f"Expected tightened_tracks=['01-track.wav'], got: {stage['tightened_tracks']}"
    )


# ---------------------------------------------------------------------------
# Test 3: Adaptive tightening derives new ceiling from worst decoded peak
# ---------------------------------------------------------------------------

def test_adm_retry_adaptive_ceiling_from_worst_peak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cycle 1 ceiling must be set based on cycle 0's worst observed peak.

    With a peak of -0.71 dBTP at ceiling -1.0 dBTP (overshoot 0.29 dB),
    the adaptive formula picks ceiling - max(overshoot + 0.3 safety,
    0.5 min-step) = -1.0 - 0.59 = -1.59 dBTP.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    call_count = {"n": 0}

    def _fake_check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Cycle 0 first (only) file → worst peak -0.71
            return {
                "filename": Path(path).name,
                "encoder_used": encoder,
                "clip_count": 3,
                "peak_db_decoded": -0.71,
                "ceiling_db": ceiling_db,
                "clips_found": True,
            }
        # Subsequent cycles pass.
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 0,
            "peak_db_decoded": ceiling_db - 0.5,
            "ceiling_db": ceiling_db,
            "clips_found": False,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _fake_check)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    mastered_ceilings: list[float] = []
    import tools.mastering.master_tracks as _mt_mod
    _real_master_track = _mt_mod.master_track

    def _capture_master_track(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real_master_track(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture_master_track)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    assert result.get("failed_stage") is None, (
        f"Expected pipeline to succeed, got: {result.get('failure_detail')}"
    )
    # Cycle 1 (post-adaptive) ceilings: any call below -1.0 is cycle 1+.
    cycle1_ceilings = [c for c in mastered_ceilings if c < -1.0]
    assert cycle1_ceilings, (
        f"Expected cycle 1 ceiling < -1.0, got ceilings: {mastered_ceilings}"
    )
    # Target ~-1.59; accept [-1.65, -1.55] to cover float rounding.
    for c in cycle1_ceilings:
        assert -1.65 <= c <= -1.55, (
            f"Expected adaptive cycle-1 ceiling near -1.59, got {c:.3f}"
        )


# ---------------------------------------------------------------------------
# Test 4: Hard floor at -6 dBTP never exceeded
# ---------------------------------------------------------------------------

def test_adm_retry_respects_hard_floor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catastrophic peaks must not drive the ceiling below -6 dBTP.

    If every cycle reports a ridiculously high peak (e.g. +5 dBFS —
    impossible but worst-case robust) the adaptive formula would compute
    a ceiling far below -6 dBTP. The floor must clamp it, and the loop
    must warn-fallback rather than loop forever at the floor.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _catastrophic_peak(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 500,
            "peak_db_decoded": 5.0,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _catastrophic_peak)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    mastered_ceilings: list[float] = []
    import tools.mastering.master_tracks as _mt_mod
    _real_master_track = _mt_mod.master_track

    def _capture_master_track(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real_master_track(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture_master_track)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    assert result.get("failed_stage") is None, (
        f"Expected warn-fallback completion, got: {result.get('failure_detail')}"
    )
    assert all(c >= -6.0 for c in mastered_ceilings), (
        f"Ceiling breached floor at -6 dBTP, got ceilings: {mastered_ceilings}"
    )
    adm_stage = result.get("stages", {}).get("adm_validation", {})
    assert adm_stage.get("status") == "warn", (
        f"Expected warn status after floor exhaustion, got: {adm_stage}"
    )


# ---------------------------------------------------------------------------
# Test 5: Floor-then-cycle-again break path — ceiling can't decrease further
# ---------------------------------------------------------------------------

def test_adm_retry_breaks_when_ceiling_cannot_decrease(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When adaptive tightening proposes a ceiling that's not lower than
    the current per-track ceiling (already at floor from a prior cycle),
    the loop must break rather than repeating a no-progress re-master.

    Exercises the `if new_ceiling >= current` guard in the ADM cycle loop
    in audio.py, where `current = ctx.track_ceilings.get(fname,
    ctx.effective_ceiling)`.  Key contract details:

    - `ctx.effective_ceiling` is NOT updated by the ADM loop; it stays at
      its initial value (-1.0 dBTP) for the entire run.  Only
      `ctx.track_ceilings[fname]` is tightened per cycle.
    - After cycle 1 the single track's ceiling is pinned at the -6.0 dBTP
      floor (peak +5 dBFS forces the maximum step every time).
    - On the candidate cycle 2 pass, `_adm_adaptive_ceiling_per_track`
      would again propose -6.0, which is not < current (-6.0), so
      `new_ceiling >= current` is True → `any_floored` is set → the
      track is not added to `next_remaster` → `next_remaster` is empty
      → the loop breaks before issuing a third master_track call.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _catastrophic(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        # Peak is always +5 dBFS — any proposed tightening exceeds the
        # -6 dBTP floor, so cycle 1 pins at -6.0 and cycle 2 would
        # pin at -6.0 again → loop must break.
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 500,
            "peak_db_decoded": 5.0,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _catastrophic)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    mastered_ceilings: list[float] = []
    import tools.mastering.master_tracks as _mt_mod
    _real_master_track = _mt_mod.master_track

    def _capture(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real_master_track(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture)

    _run_master_album(tmp_path, album_slug=album_slug)

    # One master_track call per cycle-mastering pass, one track in this
    # fixture. Without the break guard this would be 3 (full budget).
    # With the guard: cycle 0 at -1.0, cycle 1 at -6.0, then break
    # before cycle 2 re-masters → exactly 2.
    assert len(mastered_ceilings) == 2, (
        f"Expected exactly 2 master_track calls (cycle 0 + cycle 1 at floor), "
        f"got {len(mastered_ceilings)} — loop may not be breaking on "
        f"no-decrease: ceilings={mastered_ceilings}"
    )


# ---------------------------------------------------------------------------
# Test 6: Three-cycle convergence — cycle 2 is reachable and can pass
# ---------------------------------------------------------------------------

def test_adm_retry_converges_on_third_cycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Content needing two retries (cycles 1 + 2) must complete.

    Before #329 `_ADM_MAX_CYCLES` was 2; content that only converged
    on cycle 2 halted. The bump to 3 must be actually exercised: this
    test forces clips on cycles 0 and 1, clean on cycle 2, and asserts
    success.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    cycle = {"n": 0}

    def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        cycle["n"] += 1
        # Clips on first two calls, clean on third+.
        # Under per-track tightening, ceiling_db kwarg is the GLOBAL
        # target (unchanged), so we model decreasing peaks explicitly
        # to avoid the slope-divergence detector misfiring.
        clips = cycle["n"] <= 2
        # Peaks decrease each call so slope detection sees improvement:
        # call 1: -0.5, call 2: -0.8. Both above ceiling_db (-1.0)
        # when the global ceiling is -1.0, but per-track the ceiling
        # has been tightened. The slope check passes because d_peak>0.
        peak_schedule = {1: -0.5, 2: -0.8}
        peak = peak_schedule.get(cycle["n"], ceiling_db - 0.5)
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 3 if clips else 0,
            "peak_db_decoded": peak,
            "ceiling_db": ceiling_db,
            "clips_found": clips,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    mastered_ceilings: list[float] = []
    import tools.mastering.master_tracks as _mt_mod
    _real_master_track = _mt_mod.master_track

    def _capture(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real_master_track(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    assert result.get("failed_stage") is None, (
        f"Expected 3-cycle convergence, got failure: {result.get('failure_detail')}"
    )
    # 3 cycles: initial + 2 retries. 3 master_track calls on a
    # single-track fixture (cycle 0: all tracks; cycles 1+2: selective
    # remaster of the clipping track only).
    assert len(mastered_ceilings) == 3, (
        f"Expected 3 master_track calls (cycle 0/1/2), got "
        f"{len(mastered_ceilings)}: {mastered_ceilings}"
    )


# ---------------------------------------------------------------------------
# Test 7: Warn-fallback writes ADM_VALIDATION.md sidecar
# ---------------------------------------------------------------------------

def test_adm_warn_fallback_writes_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Operators need the ADM_VALIDATION.md sidecar even when the loop
    warn-falls-back, so they can inspect per-track decoded peaks and
    decide whether to republish.

    The sidecar is written inside `_stage_adm_validation` regardless
    of outcome; this test pins that behavior against warn-fallback.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _always_clips(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 5,
            "peak_db_decoded": ceiling_db + 0.3,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _always_clips)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    _run_master_album(tmp_path, album_slug=album_slug)

    sidecar = tmp_path / "ADM_VALIDATION.md"
    assert sidecar.exists(), (
        f"Expected ADM_VALIDATION.md to exist after warn-fallback, "
        f"listing dir: {sorted(p.name for p in tmp_path.iterdir())}"
    )
    content = sidecar.read_text()
    assert "01-track.wav" in content, (
        f"Expected sidecar to reference track, got content head: "
        f"{content[:300]}"
    )


# ---------------------------------------------------------------------------
# Test 8: Warn-fallback still runs post-loop stages (metadata, etc.)
# ---------------------------------------------------------------------------

def test_adm_warn_fallback_runs_post_loop_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Warn-fallback must not short-circuit the pipeline's post-loop
    stages — the whole point is that the album still finishes.

    Asserts that metadata / layout / status_update ran by looking for
    their stage entries in the returned result. Before #329 a failing
    ADM stage halted the pipeline before these ran.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _always_clips(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 5,
            "peak_db_decoded": ceiling_db + 0.3,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _always_clips)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    stages = result.get("stages", {})
    for stage_name in ("metadata", "layout", "status_update"):
        assert stage_name in stages, (
            f"Expected post-loop stage {stage_name!r} to run after "
            f"warn-fallback, got stages: {sorted(stages.keys())}"
        )


# ---------------------------------------------------------------------------
# Gate tests: ADM validation is opt-in via mastering.adm_validation_enabled
# ---------------------------------------------------------------------------

def test_adm_skipped_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing `mastering.adm_validation_enabled` config key → ADM off.

    Each ADM cycle re-masters every track and AAC encode/decode adds
    ~10-12 min per cycle on a 10-track album. Default off keeps normal
    mastering runs fast; users opt in for ADM submission prep.
    """
    album_slug = "adm-gate-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    adm_called = {"n": 0}

    def _should_not_be_called(*args, **kwargs):
        adm_called["n"] += 1
        raise AssertionError(
            "_adm_check_fn should not be called when adm_validation_enabled=False"
        )

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _should_not_be_called)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    result = _run_master_album(tmp_path, album_slug=album_slug, adm_enabled=False)

    assert result.get("failed_stage") is None, (
        f"Expected pipeline to complete, got failure: {result.get('failure_detail')}"
    )
    assert adm_called["n"] == 0, (
        f"Expected 0 ADM calls when disabled, got {adm_called['n']}"
    )
    adm_stage = result.get("stages", {}).get("adm_validation", {})
    assert adm_stage.get("status") == "skipped", (
        f"Expected adm_validation.status=skipped, got: {adm_stage}"
    )
    assert adm_stage.get("reason") == "disabled_by_config", (
        f"Expected reason=disabled_by_config, got: {adm_stage}"
    )
    notices = result.get("notices", [])
    assert any(
        "ADM validation skipped" in n and "adm_validation_enabled" in n
        for n in notices
    ), f"Expected ADM-skipped notice, got notices: {notices}"


def test_adm_enabled_runs_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit `adm_validation_enabled: true` → ADM stage runs.

    Companion to the default-skip test. Pins the gate bidirectionally.
    """
    album_slug = "adm-gate-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    adm_called = {"n": 0}

    def _clean(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        adm_called["n"] += 1
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 0,
            "peak_db_decoded": ceiling_db - 0.5,
            "ceiling_db": ceiling_db,
            "clips_found": False,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _clean)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    result = _run_master_album(tmp_path, album_slug=album_slug, adm_enabled=True)

    assert result.get("failed_stage") is None
    assert adm_called["n"] >= 1, (
        f"Expected >= 1 ADM call when enabled, got {adm_called['n']}"
    )
    adm_stage = result.get("stages", {}).get("adm_validation", {})
    assert adm_stage.get("status") == "pass", (
        f"Expected adm_validation.status=pass with clean checks, got: {adm_stage}"
    )


def test_adm_failure_detail_suggests_dynamic_ceiling(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """failure_detail.suggestion must reflect the current ceiling, not a
    hardcoded -1.5.

    Bug reported: "the suggestion field says 'set mastering.
    true_peak_ceiling: -1.5 in config.yaml' — but the ceiling is
    already at -1.5". Pin the dynamic computation.

    Approach: set the starting ceiling to -2.5 via a genre override is
    involved, so we instead test by letting the retry loop tighten then
    inspecting the final halt suggestion. Since warn-fallback is the
    normal terminal state now, halt JSON isn't returned on clip failure
    — we test the suggestion string via the stage-level failure return
    by forcing clips on the last cycle only (cycle 3 with 2 prior
    tightenings). That last cycle's ceiling is well below -1.5, so the
    suggestion must reflect that.

    Simpler: we force a persistent clip on the first cycle and capture
    the notices pushed during tightening — the retry notice already
    shows the dynamic next ceiling (implemented in audio.py). What we
    pin here is the stage-level failure_detail.suggestion contents at
    the moment it's first generated.
    """
    album_slug = "adm-gate-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    # Force a single ADM failure on cycle 0, clean thereafter (so retry
    # is attempted once and the pipeline completes successfully).
    # We capture the failure_detail that would have been returned to
    # the retry driver before it moved on.
    captured_suggestions: list[str] = []
    captured_suggested_ceilings: list[float] = []
    original_stage = album_stages_mod._stage_adm_validation

    async def _wrap_stage(ctx):
        result = await original_stage(ctx)
        if result:
            payload = json.loads(result)
            fd = payload.get("failure_detail", {})
            if "suggestion" in fd:
                captured_suggestions.append(str(fd["suggestion"]))
            if "suggested_ceiling_db" in fd:
                captured_suggested_ceilings.append(float(fd["suggested_ceiling_db"]))
        return result

    monkeypatch.setattr(album_stages_mod, "_stage_adm_validation", _wrap_stage)

    call_count = {"n": 0}

    def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        call_count["n"] += 1
        clips = call_count["n"] == 1
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 5 if clips else 0,
            # Peak at -0.4 dBTP when ceiling -1.0 → overshoot 0.6
            "peak_db_decoded": -0.4 if clips else ceiling_db - 0.5,
            "ceiling_db": ceiling_db,
            "clips_found": clips,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    _run_master_album(tmp_path, album_slug=album_slug, adm_enabled=True)

    assert captured_suggestions, (
        f"Expected at least one suggestion to be generated on clip failure"
    )
    suggestion = captured_suggestions[0]
    suggested_ceiling = captured_suggested_ceilings[0]
    # Dynamic suggestion: worst_peak -0.4 at ceiling -1.0 → min(
    # ceiling - 0.5, peak - 0.3) = min(-1.5, -0.7) = -1.5. Acceptable
    # in a band around -1.5 given float precision.
    assert -1.55 <= suggested_ceiling <= -1.45, (
        f"Expected suggested_ceiling near -1.5 (computed from "
        f"peak=-0.4, ceiling=-1.0), got: {suggested_ceiling}"
    )
    # The string must name the actual computed value, not a hardcoded
    # one. For this fixture the computed value IS -1.5, but the string
    # must NOT use the literal hardcoded phrasing from the pre-fix
    # code: "set mastering.true_peak_ceiling: -1.5 in config.yaml"
    # without the "Worst decoded peak was ..." prefix.
    assert "Worst decoded peak" in suggestion, (
        f"Suggestion must reference observed worst peak (dynamic), got: "
        f"{suggestion}"
    )
    assert f"{suggested_ceiling:.2f}" in suggestion, (
        f"Suggestion must name the computed ceiling {suggested_ceiling:.2f}, got: "
        f"{suggestion}"
    )


# ---------------------------------------------------------------------------
# Slope-aware adaptive tightening — 0.6:1 ripple scaling converges
# ---------------------------------------------------------------------------

def test_adm_slope_aware_scales_tighten_on_sub_linear_ripple(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When AAC ripple shrinks at ~0.6 dB per 1 dB of ceiling tighten,
    the slope-aware formula must scale the tighten proportionally so
    convergence happens within the cycle budget.

    Reporter's real data: cycles 0→1→2 with ceiling going -1.5 →
    -2.33 → -3.49 and decoded peaks -0.97 → -1.47 → -2.80. The 1:1
    legacy formula proposed too-small tightens and never converged in
    3 cycles. The slope-aware formula observes d_peak / d_ceiling ≈
    0.6 after cycle 1 and multiplies subsequent tightens by ~1.67×.
    """
    album_slug = "adm-slope-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    # Model: decoded_peak(ceiling) = ceiling + base_overshoot - 0.6 *
    # tighten_from_start. Converges when overshoot ≤ 0.
    start_ceiling = -1.0
    base_overshoot = 1.0

    def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        tighten_from_start = start_ceiling - ceiling_db
        remaining_overshoot = base_overshoot - 0.6 * tighten_from_start
        clips_here = remaining_overshoot > 0
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 1 if clips_here else 0,
            "peak_db_decoded": ceiling_db + remaining_overshoot,
            "ceiling_db": ceiling_db,
            "clips_found": clips_here,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    mastered_ceilings: list[float] = []
    import tools.mastering.master_tracks as _mt_mod
    _real_master_track = _mt_mod.master_track

    def _capture(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real_master_track(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture)

    result = _run_master_album(tmp_path, album_slug=album_slug, adm_enabled=True)

    assert result.get("failed_stage") is None, (
        f"Expected pipeline completion, got: {result.get('failure_detail')}"
    )
    # On 0.6:1 material, slope-aware convergence fits inside the 5-
    # cycle budget. Pre-fix behavior (fixed 0.5 dB steps) would NOT
    # converge with base_overshoot=1.0. Upper bound: ≤4 re-masters.
    assert len(mastered_ceilings) <= 4, (
        f"Expected convergence in ≤4 re-masters with slope-aware formula, "
        f"got {len(mastered_ceilings)}: {mastered_ceilings}"
    )


# ---------------------------------------------------------------------------
# Divergence detection: ripple grows with tightening → warn-fallback
# ---------------------------------------------------------------------------

def test_adm_divergence_triggers_warn_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Material where tightening increases decoded ripple must
    terminate the loop early with a divergence notice, not burn all
    5 cycles. Mimics limiter pumping harder on tighter ceilings.
    """
    album_slug = "adm-divergent-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    # Pathological limiter: tightening the ceiling makes the decoded
    # peak GROW, not shrink. On cycle 0 at ceiling -1.0 the peak is
    # -0.5 dBTP; on cycle 1 at a tighter ceiling the peak rises to
    # -0.3 dBTP (higher = closer to 0 = worse). slope = Δpeak/Δceiling
    # = (-0.5 - (-0.3)) / (-1.0 - tightened) is negative — divergent.
    def _check(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        if ceiling_db >= -1.25:  # cycle 0 only
            peak = -0.5
        else:  # cycle 1 and beyond — peak actually worsened
            peak = -0.3
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 5,
            "peak_db_decoded": peak,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _check)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    mastered_ceilings: list[float] = []
    import tools.mastering.master_tracks as _mt_mod
    _real_master_track = _mt_mod.master_track

    def _capture(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real_master_track(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture)

    result = _run_master_album(tmp_path, album_slug=album_slug, adm_enabled=True)

    assert result.get("failed_stage") is None, (
        f"Expected warn-fallback completion on divergent material, "
        f"got: {result.get('failure_detail')}"
    )
    stage = result.get("stages", {}).get("adm_validation", {})
    assert stage.get("status") == "warn", (
        f"Expected warn status on divergent material, got: {stage}"
    )
    assert stage.get("diverging") is True, (
        f"Expected diverging=True on slope-≤-0 material, got: {stage}"
    )
    # Divergence detection must bail well before the 5-cycle budget —
    # cycle 0 + cycle 1 produce enough observations, cycle 2 detects.
    assert len(mastered_ceilings) <= 2, (
        f"Expected divergence bail after ≤2 re-masters, got "
        f"{len(mastered_ceilings)}: {mastered_ceilings}"
    )
    notices = result.get("notices", [])
    assert any(
        "adm loop terminated" in n.lower() for n in notices
    ), f"Expected ADM termination notice on divergent material, got notices: {notices}"


# ---------------------------------------------------------------------------
# Warn-fallback terminal notice appears in notices
# ---------------------------------------------------------------------------

def test_adm_warn_fallback_emits_terminal_notice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Operators reading the notice stream must see an explicit
    'ADM loop terminated without convergence' notice so they know the
    exit condition without scanning warnings. Previously only
    per-cycle tightening notices were emitted; no terminal notice
    named the warn-fallback exit.
    """
    album_slug = "adm-terminal-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _always_clips(path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 5,
            "peak_db_decoded": ceiling_db + 0.3,
            "ceiling_db": ceiling_db,
            "clips_found": True,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _always_clips)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    result = _run_master_album(tmp_path, album_slug=album_slug, adm_enabled=True)
    notices = result.get("notices", [])
    assert any(
        "adm loop terminated" in n.lower()
        for n in notices
    ), f"Expected terminal warn-fallback notice, got notices: {notices}"


# ---------------------------------------------------------------------------
# Step-cap test: cycle-to-cycle tighten must not exceed _ADM_MAX_TIGHTEN_DB
# ---------------------------------------------------------------------------

def test_adm_retry_caps_tighten_per_cycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A single retry must not drop the ceiling by more than 1.0 dB.

    Regression: when AAC ripple scales poorly with ceiling (peak drops
    only ~0.1 dB for every 1 dB of tightening), the slope-aware formula
    `(overshoot + 0.3) / max(slope, 0.4)` proposes ~4 dB one-shot
    tightens. The resulting ceiling is so low downstream limiting can't
    reach target LUFS and verification fails with -20-to-24 LUFS
    outputs. Cap each step at _ADM_MAX_TIGHTEN_DB.
    """
    album_slug = "adm-retry-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)

    def _shallow_slope(
        path, *, encoder="aac", ceiling_db=-1.0, bitrate_kbps=256,
    ):
        # Cycle 0 (ceiling -1.0): peak -0.4 → tighten 0.9 → ceiling -1.9
        # Cycle 1 (ceiling -1.9): peak -0.5 → slope 0.11, clamped to
        #   0.4 → uncapped tighten 4.25 dB (floored at -6.0). With cap:
        #   tighten 1.0 → ceiling -2.9.
        # Cycle 2+ (clean): exits the loop.
        if ceiling_db > -1.5:
            peak, clips = -0.4, True
        elif ceiling_db > -2.5:
            peak, clips = -0.5, True
        else:
            peak, clips = ceiling_db - 0.5, False
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 100 if clips else 0,
            "peak_db_decoded": peak,
            "ceiling_db": ceiling_db,
            "clips_found": clips,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _shallow_slope)
    monkeypatch.setattr(
        album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None,
    )

    mastered_ceilings: list[float] = []
    import tools.mastering.master_tracks as _mt_mod
    _real = _mt_mod.master_track

    def _capture(src, dst, *, ceiling_db=-1.0, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        return _real(src, dst, ceiling_db=ceiling_db, **kwargs)

    monkeypatch.setattr(_mt_mod, "master_track", _capture)

    _run_master_album(tmp_path, album_slug=album_slug)

    assert len(mastered_ceilings) >= 2, (
        f"Expected at least 2 cycles, got: {mastered_ceilings}"
    )
    for prev, curr in zip(mastered_ceilings, mastered_ceilings[1:]):
        step = prev - curr
        assert step <= 1.0 + 1e-3, (
            f"Cycle-to-cycle ceiling step {step:.3f} dB exceeds 1.0 dB "
            f"cap. Full ceiling history: {mastered_ceilings}"
        )
