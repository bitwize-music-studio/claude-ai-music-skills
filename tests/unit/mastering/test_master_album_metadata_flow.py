"""Integration tests for Stage 6.6 (metadata embedding) in master_album (#290)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

mutagen = pytest.importorskip("mutagen")

from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


def _write_wav(path: Path) -> Path:
    n = int(44100 * 1.0)
    data = (0.1 * np.sin(2 * np.pi * 440 * np.arange(n) / 44100)).astype(np.float32)
    sf.write(str(path), np.column_stack([data, data]), 44100, subtype="PCM_24")
    return path


def test_metadata_stage_embeds_artist_tag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Metadata stage embeds artist name from config into mastered WAVs."""
    from handlers import _shared
    fake_state = {"albums": {"my-album": {
        "path": str(tmp_path),
        "status": "In Progress",
        "tracks": {"01-track": {"title": "My Track", "status": "Generated"}},
    }}}
    class _FakeCache:
        def get_state(self): return fake_state
        def get_state_ref(self): return fake_state
    monkeypatch.setattr(_shared, "cache", _FakeCache())

    # Stub config to return artist name
    monkeypatch.setattr(
        "tools.shared.config.load_config",
        lambda: {
            "artist": {
                "name": "bitwize",
                "copyright_holder": "bitwize 2026",
                "label": "bitwize records",
            }
        },
    )

    wav = _write_wav(tmp_path / "01-track.wav")

    async def _run():
        ctx = album_stages_mod.MasterAlbumCtx(
            album_slug="my-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_event_loop(),
        )
        ctx.audio_dir = tmp_path
        ctx.mastered_files = [wav]
        ctx.targets = {}
        return await album_stages_mod._stage_metadata(ctx), ctx

    result, ctx = asyncio.run(_run())

    assert result is None
    assert ctx.stages["metadata"]["status"] == "pass"

    from mutagen.wave import WAVE
    tags = WAVE(str(wav)).tags
    assert tags is not None
    assert str(tags.get("TPE1")) == "bitwize"


def test_metadata_stage_warns_on_embed_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Metadata stage warns but never halts if embedding fails."""
    from handlers import _shared
    fake_state = {"albums": {"my-album": {
        "path": str(tmp_path), "status": "In Progress", "tracks": {},
    }}}
    class _FakeCache:
        def get_state(self): return fake_state
        def get_state_ref(self): return fake_state
    monkeypatch.setattr(_shared, "cache", _FakeCache())
    monkeypatch.setattr("tools.shared.config.load_config", lambda: {})

    from tools.mastering.metadata import MetadataEmbedError
    def _boom(path, **kwargs):
        raise MetadataEmbedError("write failed")
    monkeypatch.setattr(album_stages_mod, "_embed_wav_metadata_fn", _boom)

    wav = _write_wav(tmp_path / "01.wav")

    async def _run():
        ctx = album_stages_mod.MasterAlbumCtx(
            album_slug="my-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_event_loop(),
        )
        ctx.audio_dir = tmp_path
        ctx.mastered_files = [wav]
        ctx.targets = {}
        return await album_stages_mod._stage_metadata(ctx), ctx

    result, ctx = asyncio.run(_run())

    assert result is None  # never halts
    assert any("metadata" in w.lower() for w in ctx.warnings)
    assert ctx.stages["metadata"]["status"] == "warn"
