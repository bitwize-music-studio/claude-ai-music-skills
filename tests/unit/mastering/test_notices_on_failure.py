"""Test that notices appear in early-exit failure JSON (A4 — #290)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


def _install_album(monkeypatch, audio_path: Path, album_slug: str) -> None:
    from handlers import _shared
    fake_state = {"albums": {album_slug: {
        "path": str(audio_path), "status": "In Progress", "tracks": {},
    }}}
    class _FakeCache:
        def get_state(self): return fake_state
        def get_state_ref(self): return fake_state
    monkeypatch.setattr(_shared, "cache", _FakeCache())


def test_failure_json_includes_notices_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Failure JSON always has a 'notices' key (may be empty list)."""
    _install_album(monkeypatch, tmp_path, "my-album")
    monkeypatch.setattr(processing_helpers, "_resolve_audio_dir",
                        lambda slug, subfolder="": (None, tmp_path))
    monkeypatch.setattr(processing_helpers, "_check_mastering_deps", lambda: None)

    # Stage that always halts: inject a bad pre_flight result
    async def _bad_pre_flight(ctx):
        ctx.stages["pre_flight"] = {"status": "fail", "detail": "injected failure"}
        return json.dumps({
            "album_slug": ctx.album_slug,
            "stage_reached": "pre_flight",
            "stages": ctx.stages,
            "settings": ctx.settings,
            "warnings": ctx.warnings,
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": "injected"},
        })
    monkeypatch.setattr(album_stages_mod, "_stage_pre_flight", _bad_pre_flight)

    result_str = asyncio.run(audio_mod.master_album("my-album"))
    payload = json.loads(result_str)

    # Notices key must be present even in failure path
    assert "notices" in payload
    assert isinstance(payload["notices"], list)


def test_failure_json_includes_upsampling_notice_when_targets_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If targets indicate upsampling and a later stage fails, notices appear."""
    import numpy as np
    import soundfile as sf

    _install_album(monkeypatch, tmp_path, "my-album")
    monkeypatch.setattr(processing_helpers, "_resolve_audio_dir",
                        lambda slug, subfolder="": (None, tmp_path))
    monkeypatch.setattr(processing_helpers, "_check_mastering_deps", lambda: None)

    # Write a WAV so pre_flight passes
    n = 44100
    wav = tmp_path / "01.wav"
    sf.write(str(wav), np.zeros((n, 2), dtype=np.float32), 44100, subtype="PCM_16")

    # After pre_flight, inject an upsampling target signal
    original_pre_flight = album_stages_mod._stage_pre_flight
    async def _patched_pre_flight(ctx):
        result = await original_pre_flight(ctx)
        ctx.targets["upsampled_from_source"] = True
        ctx.targets["source_sample_rate"] = 44100
        ctx.targets["output_sample_rate"] = 96000
        return result
    monkeypatch.setattr(album_stages_mod, "_stage_pre_flight", _patched_pre_flight)

    # Make analysis fail immediately after
    async def _boom_analysis(ctx):
        ctx.stages["analysis"] = {"status": "fail", "detail": "injected"}
        return json.dumps({
            "album_slug": ctx.album_slug,
            "stage_reached": "analysis",
            "stages": ctx.stages,
            "settings": ctx.settings,
            "warnings": ctx.warnings,
            "failed_stage": "analysis",
            "failure_detail": {"reason": "injected"},
        })
    monkeypatch.setattr(album_stages_mod, "_stage_analysis", _boom_analysis)

    result_str = asyncio.run(audio_mod.master_album("my-album"))
    payload = json.loads(result_str)

    assert "notices" in payload
    assert any("96" in n or "upsample" in n.lower() for n in payload["notices"])
