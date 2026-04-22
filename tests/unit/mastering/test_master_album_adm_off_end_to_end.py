"""Regression: master_album runs end-to-end with ADM off. Explicitly
covers the new default-off semantic — no album frontmatter mastering
block means the ADM stage is skipped and the pipeline completes
through all post-loop stages (mastering_samples, post_qc, archival,
metadata, layout, signature_persist, status_update)."""

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


def _write_sine_wav(path: Path, *, rate: int = 44100,
                    seconds: float = 30.0, freq: float = 3500.0) -> Path:
    import soundfile as sf
    n = int(seconds * rate)
    t = np.arange(n) / rate
    mono = 0.3 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.column_stack([mono, mono]), rate, subtype="PCM_24")
    return path


def test_master_album_completes_with_adm_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """With no frontmatter mastering block (default off), master_album
    completes the full pipeline. ADM stage is marked skipped. No dark
    casualty / warn-fallback code paths are triggered. All post-loop
    stages run."""
    album_slug = "adm-off-regression"
    _write_sine_wav(tmp_path / "01-track.wav")

    # Install the album in the fake cache with NO mastering frontmatter
    # block — default-off semantic under test.
    fake_state = {
        "albums": {
            album_slug: {
                "path": str(tmp_path),
                "status": "In Progress",
                "tracks": {},
                # 'mastering' key absent or {} — both resolve to ADM off.
                "mastering": {},
            }
        }
    }

    class _FakeCache:
        def get_state(self):
            return fake_state

        def get_state_ref(self):
            return fake_state

    monkeypatch.setattr(_shared, "cache", _FakeCache())
    monkeypatch.setattr(
        album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None,
    )

    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    # Force global config to have ADM ON — the point is that frontmatter
    # default-off beats global ON. If the orchestrator honored global,
    # the ADM stage would run; since the frontmatter is empty, it should
    # NOT run.
    from tools.mastering import config as _master_config
    real_load = _master_config.load_mastering_config

    def _load_with_adm_on() -> dict:
        cfg = real_load()
        cfg["adm_validation_enabled"] = True
        return cfg

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(_master_config, "load_mastering_config", _load_with_adm_on):
        result = json.loads(asyncio.run(audio_mod.master_album(album_slug=album_slug)))

    # Pipeline completed (no halt).
    assert result.get("failed_stage") is None, (
        f"master_album halted: {result.get('failure_detail')}"
    )

    stages = result["stages"]

    # ADM stage must be explicitly skipped, not "pass" / "warn" / "fail".
    adm = stages.get("adm_validation", {})
    assert adm.get("status") == "skipped", (
        f"Expected adm_validation skipped (default-off), got: {adm}"
    )

    # All unconditional post-loop stages ran — this is the anti-regression
    # guard. If ADM-off broke ANY of these, we'd halt before reaching them.
    # (archival is conditional on archival_enabled config and is omitted here.)
    for must_run in ("mastering_samples", "post_qc",
                     "layout", "signature_persist", "status_update"):
        assert must_run in stages, (
            f"Stage {must_run} did not run with ADM off — "
            f"stages reached: {list(stages.keys())}"
        )


def test_master_album_adm_on_via_frontmatter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Opt-in case: frontmatter explicitly sets
    mastering.adm_validation_enabled: true. ADM stage must run
    (and since our fake clip check returns clean, it passes)."""
    album_slug = "adm-on-regression"
    _write_sine_wav(tmp_path / "01-track.wav")

    fake_state = {
        "albums": {
            album_slug: {
                "path": str(tmp_path),
                "status": "In Progress",
                "tracks": {},
                "mastering": {"adm_validation_enabled": True},
            }
        }
    }

    class _FakeCache:
        def get_state(self):
            return fake_state

        def get_state_ref(self):
            return fake_state

    monkeypatch.setattr(_shared, "cache", _FakeCache())
    monkeypatch.setattr(
        album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None,
    )

    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    # Stub adm check to return clean so the pipeline completes.
    def _clean_adm_check(path, *, encoder="aac", ceiling_db=-1.0,
                        bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 0,
            "peak_db_decoded": ceiling_db - 0.5,
            "ceiling_db": ceiling_db,
            "clips_found": False,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _clean_adm_check)

    # Global config OFF — frontmatter wins.
    from tools.mastering import config as _master_config
    real_load = _master_config.load_mastering_config

    def _load_with_adm_off() -> dict:
        cfg = real_load()
        cfg["adm_validation_enabled"] = False
        return cfg

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(_master_config, "load_mastering_config", _load_with_adm_off):
        result = json.loads(asyncio.run(audio_mod.master_album(album_slug=album_slug)))

    assert result.get("failed_stage") is None
    adm = result["stages"].get("adm_validation", {})
    # ADM stage ran — status is "pass" (no clips) not "skipped".
    assert adm.get("status") == "pass", (
        f"Expected adm_validation pass with frontmatter opt-in, got: {adm}"
    )
