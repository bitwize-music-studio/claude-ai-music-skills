"""MASTERING_PROGRESS.log sidecar emitted during master_album runs.

Pin the behavior operators rely on:
- Log file exists at the album's audio_dir after any run.
- Each stage appears with ENTER + EXIT/HALT events.
- Timestamps are ISO8601 UTC so `tail -f` output is sortable.
- File persists after halt / warn-fallback (forensic value).

Motivation: master_album takes ~10-30 min with ADM enabled. MCP
clients can disconnect mid-call and operators have no visibility
into where the pipeline got to. The sidecar lets them
`tail -f MASTERING_PROGRESS.log` to see live stage progress.
"""

from __future__ import annotations

import asyncio
import json
import re
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


def _write_sine_wav(
    path: Path, *, duration: float = 30.0, sample_rate: int = 44100,
    amplitude: float = 0.3, freq: float = 440.0,
) -> Path:
    import soundfile as sf

    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    sf.write(str(path), np.column_stack([mono, mono]), sample_rate, subtype="PCM_24")
    return path


def _install_album(
    monkeypatch: pytest.MonkeyPatch, audio_path: Path, album_slug: str,
) -> None:
    fake_state = {
        "albums": {
            album_slug: {
                "path": str(audio_path), "status": "In Progress", "tracks": {},
            }
        }
    }

    class _FakeCache:
        def get_state(self):
            return fake_state

        def get_state_ref(self):
            return fake_state

    monkeypatch.setattr(_shared, "cache", _FakeCache())


def _run_master_album(tmp_path: Path, album_slug: str = "progress-album") -> dict:
    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        return json.loads(asyncio.run(audio_mod.master_album(album_slug=album_slug)))


def test_progress_log_written_on_successful_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """After a clean master_album run, the sidecar must exist and contain
    ENTER + EXIT events for pre-loop and post-loop stages."""
    album_slug = "progress-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    _run_master_album(tmp_path, album_slug=album_slug)

    log_path = tmp_path / "MASTERING_PROGRESS.log"
    assert log_path.exists(), (
        f"Expected MASTERING_PROGRESS.log at {log_path}, listing: "
        f"{sorted(p.name for p in tmp_path.iterdir())}"
    )
    content = log_path.read_text()

    # Run header
    assert "RUN START" in content, (
        f"Expected RUN START header in log, head: {content[:200]}"
    )
    assert f"album={album_slug}" in content

    # A representative subset of stages that always run
    for stage in (
        "pre_flight", "analysis", "pre_qc",
        "mastering", "verification", "post_qc",
        "signature_persist", "status_update",
    ):
        assert f"ENTER | {stage}" in content, (
            f"Missing ENTER for stage {stage!r}. Content:\n{content}"
        )
        assert f"EXIT | {stage}" in content, (
            f"Missing EXIT for stage {stage!r}. Content:\n{content}"
        )

    # Terminal COMPLETE event on successful pipeline
    assert "COMPLETE | pipeline" in content

    # ISO8601 UTC timestamps — one sample line must parse.
    ts_pattern = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z")
    assert ts_pattern.search(content), (
        f"Expected ISO8601 UTC timestamps, got:\n{content[:500]}"
    )


def test_progress_log_survives_halt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When the pipeline halts mid-run, the sidecar must still exist with
    the events up to and including the HALT."""
    album_slug = "progress-halt-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    # Force post_qc to halt by making qc_track return a FAIL verdict
    # on the clicks check.
    def _fake_qc(path, _checks=None, _genre=None):
        return {
            "filename": Path(path).name,
            "verdict": "FAIL",
            "checks": {
                "clicks": {
                    "status": "FAIL",
                    "detail": "forced failure for halt test",
                },
            },
        }

    monkeypatch.setattr("tools.mastering.qc_tracks.qc_track", _fake_qc)

    result = _run_master_album(tmp_path, album_slug=album_slug)

    # Pipeline halted somewhere; sidecar should have the HALT record.
    assert result.get("failed_stage") is not None, (
        f"Expected halt but pipeline completed: {result.get('stage_reached')}"
    )
    log_path = tmp_path / "MASTERING_PROGRESS.log"
    assert log_path.exists()
    content = log_path.read_text()
    assert "HALT | " in content, (
        f"Expected HALT record on halted pipeline, got:\n{content}"
    )


def test_progress_log_appends_across_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Two runs in the same audio_dir must append, not clobber — cross-run
    history is forensic value. Each run separated by its own RUN START
    header.
    """
    album_slug = "progress-append-album"
    _write_sine_wav(tmp_path / "01-track.wav")
    _install_album(monkeypatch, tmp_path, album_slug)
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None)

    _run_master_album(tmp_path, album_slug=album_slug)
    first_content = (tmp_path / "MASTERING_PROGRESS.log").read_text()
    first_headers = first_content.count("RUN START")

    _run_master_album(tmp_path, album_slug=album_slug)
    second_content = (tmp_path / "MASTERING_PROGRESS.log").read_text()
    second_headers = second_content.count("RUN START")

    assert second_headers == first_headers + 1, (
        f"Expected one additional RUN START header after 2nd run "
        f"(had {first_headers}, now {second_headers})"
    )
    # Second run's content must include all of the first.
    assert second_content.startswith(first_content), (
        "2nd run should append to (not rewrite) existing log — got "
        "divergent prefix."
    )
