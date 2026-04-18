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
    assert any("ADM validation" in w and "retain inter-sample" in w for w in warnings), (
        f"Expected ADM warn-fallback warning, got warnings: {warnings}"
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
    the current one (already at floor from a prior cycle), the loop
    must break rather than repeating a no-progress re-master.

    Exercises the `if new_ceiling >= ctx.effective_ceiling` guard in
    the ADM cycle loop in audio.py — the one that catches "we've
    already hit the floor, another iteration would just mean mastering
    with the same ceiling again".
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
        # Cycle 0 + cycle 1 report clips (one track each cycle so n<=2
        # is cycle 0, n==2-3 is cycle 1... wait, one track per cycle).
        # Clips on first two calls, clean on third+.
        clips = cycle["n"] <= 2
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 3 if clips else 0,
            "peak_db_decoded": ceiling_db + 0.3 if clips else ceiling_db - 0.5,
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
    # 3 cycles: initial + 2 retries. Exactly 3 master_track calls on a
    # single-track fixture.
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
