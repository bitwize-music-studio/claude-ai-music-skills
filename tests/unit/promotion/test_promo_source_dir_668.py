"""Promo videos are cut from mastered/, not the album folder's root (#668).

``generate_promo_videos`` (batch) and ``generate_album_sampler`` globbed only
the album's audio folder. After ``migrate_audio_layout`` the WAVs live in
``originals/`` and ``mastered/``, so the batch found nothing and returned
``{"tracks": [], "summary": {"success": 0, "failed": 0}}`` with no error,
and the sampler counted ``tracks_included`` from ``originals/`` whatever it
had been given.

Usage:
    python -m pytest tests/unit/promotion/test_promo_source_dir_668.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for _p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from handlers import _shared  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import video as video_mod  # noqa: E402

pytestmark = pytest.mark.unit


class _FakeCache:
    def get_state(self) -> dict[str, Any]:
        return {"config": {"artist_name": "bitwize"}, "albums": {}}


@pytest.fixture
def album(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An album in the migrated layout: originals/ and mastered/, artwork at the root."""
    (tmp_path / "album.png").write_bytes(b"png")
    monkeypatch.setattr(_shared, "cache", _FakeCache())
    monkeypatch.setattr(processing_helpers, "_check_ffmpeg", lambda: None)
    monkeypatch.setattr(processing_helpers, "_resolve_audio_dir",
                        lambda *_a, **_k: (None, tmp_path))
    return tmp_path


def _wavs(folder: Path, names: list[str]) -> None:
    folder.mkdir(exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"RIFF")


def _run_batch(album: Path) -> tuple[dict[str, Any], list[Path]]:
    seen: list[Path] = []

    def _fake_batch(**kwargs: Any) -> list[tuple[str, str, bool]]:
        seen.append(kwargs["album_dir"])
        return [(f.name, f"{f.stem}_promo.mp4", True)
                for f in sorted(kwargs["album_dir"].glob("*.wav"))]

    with patch("tools.promotion.generate_promo_video.batch_process_album",
               side_effect=_fake_batch), \
         patch("tools.shared.fonts.find_font", return_value=None):
        result = json.loads(asyncio.run(video_mod.generate_promo_videos("album")))
    return result, seen


def _run_sampler(album: Path) -> tuple[dict[str, Any], list[Path]]:
    seen: list[Path] = []

    def _fake_sampler(**kwargs: Any) -> bool:
        seen.append(kwargs["tracks_dir"])
        kwargs["output_path"].write_bytes(b"mp4")
        return True

    with patch("tools.promotion.generate_album_sampler.generate_album_sampler",
               side_effect=_fake_sampler):
        result = json.loads(asyncio.run(video_mod.generate_album_sampler("album")))
    return result, seen


class TestPromoReadsMastered:
    def test_batch_reads_mastered_after_migration(self, album: Path) -> None:
        _wavs(album / "originals", ["01-a.wav", "02-b.wav", "03-c.wav"])
        _wavs(album / "mastered", ["01-a.wav", "02-b.wav"])

        result, seen = _run_batch(album)

        assert seen == [album / "mastered"]
        assert result["summary"]["success"] == 2
        assert [t["filename"] for t in result["tracks"]] == ["01-a.wav", "02-b.wav"]

    def test_sampler_reads_and_counts_mastered(self, album: Path) -> None:
        _wavs(album / "originals", ["01-a.wav", "02-b.wav", "03-c.wav"])
        _wavs(album / "mastered", ["01-a.wav", "02-b.wav"])

        result, seen = _run_sampler(album)

        assert seen == [album / "mastered"]
        assert result["tracks_included"] == 2

    def test_not_mastered_yet_falls_back_to_originals(self, album: Path) -> None:
        _wavs(album / "originals", ["01-a.wav", "02-b.wav", "03-c.wav"])

        batch, batch_seen = _run_batch(album)
        sampler, sampler_seen = _run_sampler(album)

        assert batch_seen == [album / "originals"]
        assert batch["summary"]["success"] == 3
        assert sampler_seen == [album / "originals"]
        assert sampler["tracks_included"] == 3

    def test_flat_legacy_layout_unchanged(self, album: Path) -> None:
        _wavs(album, ["01-a.wav", "02-b.wav"])

        batch, batch_seen = _run_batch(album)
        sampler, sampler_seen = _run_sampler(album)

        assert batch_seen == [album]
        assert batch["summary"]["success"] == 2
        assert sampler_seen == [album]
        assert sampler["tracks_included"] == 2

    def test_single_track_prefers_the_master(self, album: Path) -> None:
        _wavs(album / "originals", ["01-a.wav"])
        _wavs(album / "mastered", ["01-a.wav"])
        used: list[Path] = []

        def _fake_video(**kwargs: Any) -> bool:
            used.append(kwargs["audio_path"])
            return True

        with patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   side_effect=_fake_video), \
             patch("tools.shared.fonts.find_font", return_value=None):
            result = json.loads(asyncio.run(video_mod.generate_promo_videos(
                "album", track_filename="01-a.wav",
            )))

        assert result["summary"]["success"] == 1
        assert used == [album / "mastered" / "01-a.wav"]
