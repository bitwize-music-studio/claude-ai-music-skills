"""The album's listening playlist: ``<album slug>.m3u8`` beside ``mastered/``.

Every tool that writes into ``mastered/`` rebuilds it from what is there, in
track order, so the mastered album can be played straight through in any
player. It never goes inside ``mastered/``, which is what the distributor
gets and stays WAV-only.

Usage:
    python -m pytest tests/unit/mastering/test_album_playlist.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as shared_mod
from handlers.processing import _album_stages as album_stages_mod
from handlers.processing import _helpers as processing_helpers
from handlers.processing import audio as audio_mod
from tools.mastering.playlist import PlaylistEntry, playlist_path, render_m3u8

pytestmark = pytest.mark.unit


def _silence(path: Path, seconds: float, rate: int = 8000) -> Path:
    sf.write(str(path), np.zeros((int(seconds * rate), 2), dtype=np.float32), rate,
             subtype="PCM_16")
    return path


def _sine(path: Path, seconds: float = 30.0, freq: float = 220.0) -> Path:
    rate = 44100
    t = np.arange(int(seconds * rate)) / rate
    mono = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(str(path), np.column_stack([mono, mono]), rate, subtype="PCM_24")
    return path


class _FakeCache:
    def __init__(self, state: dict):
        self._state = state

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _install_album(monkeypatch, slug: str, *, name: str = "", titles: dict | None = None,
                   audio_dir: Path | None = None) -> None:
    album: dict = {"status": "In Progress", "tracks": {}}
    if name:
        album["name"] = name
    if audio_dir is not None:
        album["path"] = str(audio_dir)
    for stem, title in (titles or {}).items():
        album["tracks"][stem] = {"title": title}
    monkeypatch.setattr(shared_mod, "cache", _FakeCache({"albums": {slug: album}}))


def _artist(monkeypatch, name: str | None) -> None:
    import tools.shared.config as config_mod
    config = {"artist": {"name": name}} if name else {}
    monkeypatch.setattr(config_mod, "load_config", lambda *a, **k: config)


def _resolve_to(audio_dir: Path):
    def _fake_resolve(slug, *_, **__):
        return None, audio_dir
    return patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve)


# ===========================================================================
# The text
# ===========================================================================


class TestRenderM3u8:
    def test_each_track_with_its_length_and_title_in_order(self):
        text = render_m3u8("Paper Boats", [
            PlaylistEntry("mastered/01-harbor.wav", 214, "bitwize - Harbor"),
            PlaylistEntry("mastered/02-tide.wav", 187, "bitwize - Tide"),
        ])
        assert text == (
            "#EXTM3U\n"
            "#PLAYLIST:Paper Boats\n"
            "#EXTINF:214,bitwize - Harbor\n"
            "mastered/01-harbor.wav\n"
            "#EXTINF:187,bitwize - Tide\n"
            "mastered/02-tide.wav\n"
        )

    def test_a_line_break_in_a_name_cannot_start_another_entry(self):
        text = render_m3u8("Two\nLines", [
            PlaylistEntry("mastered/01-a.wav", 10, "Evil\r\nhttp://example.org/x.mp3"),
        ])
        assert text.splitlines() == [
            "#EXTM3U",
            "#PLAYLIST:Two Lines",
            "#EXTINF:10,Evil http://example.org/x.mp3",
            "mastered/01-a.wav",
        ]

    def test_an_unknown_length_is_written_as_minus_one(self):
        text = render_m3u8("Album", [PlaylistEntry("mastered/01-a.wav", -1, "A")])
        assert "#EXTINF:-1,A\n" in text

    def test_no_album_name_means_no_playlist_line(self):
        text = render_m3u8("  ", [PlaylistEntry("mastered/01-a.wav", 3, "A")])
        assert text.splitlines()[:2] == ["#EXTM3U", "#EXTINF:3,A"]

    def test_names_keep_their_own_script(self):
        text = render_m3u8("Café del Mar", [PlaylistEntry("mastered/01-a.wav", 3, "봄날")])
        assert "#PLAYLIST:Café del Mar\n#EXTINF:3,봄날\n" in text

    def test_the_playlist_sits_beside_mastered_named_for_the_album(self, tmp_path):
        assert playlist_path(tmp_path, "paper-boats") == tmp_path / "paper-boats.m3u8"


# ===========================================================================
# Building it from mastered/
# ===========================================================================


class TestWriteAlbumPlaylist:
    def test_the_mastered_tracks_in_order_with_titles_and_lengths(self, tmp_path, monkeypatch):
        mastered = tmp_path / "mastered"
        mastered.mkdir()
        _silence(mastered / "02-tide.wav", 2.6)
        _silence(mastered / "01-harbor.wav", 1.4)
        (mastered / "notes.txt").write_text("not audio", encoding="utf-8")
        _install_album(monkeypatch, "paper-boats", name="Paper Boats",
                       titles={"01-harbor": "Harbor", "02-tide": "Tide"})
        _artist(monkeypatch, "bitwize")

        result = album_stages_mod.write_album_playlist("paper-boats", tmp_path)

        target = tmp_path / "paper-boats.m3u8"
        assert result == {"status": "pass", "path": str(target), "tracks": 2}
        assert target.read_text(encoding="utf-8") == (
            "#EXTM3U\n"
            "#PLAYLIST:Paper Boats\n"
            "#EXTINF:1,bitwize - Harbor\n"
            "mastered/01-harbor.wav\n"
            "#EXTINF:3,bitwize - Tide\n"
            "mastered/02-tide.wav\n"
        )

    def test_without_a_title_or_an_artist_the_file_name_is_shown(self, tmp_path, monkeypatch):
        (tmp_path / "mastered").mkdir()
        _silence(tmp_path / "mastered" / "01-harbor.wav", 1.0)
        _install_album(monkeypatch, "paper-boats")
        _artist(monkeypatch, None)

        album_stages_mod.write_album_playlist("paper-boats", tmp_path)

        lines = (tmp_path / "paper-boats.m3u8").read_text(encoding="utf-8").splitlines()
        assert lines == ["#EXTM3U", "#PLAYLIST:paper-boats", "#EXTINF:1,01-harbor",
                         "mastered/01-harbor.wav"]

    def test_an_unreadable_wav_is_listed_with_an_unknown_length(self, tmp_path, monkeypatch):
        (tmp_path / "mastered").mkdir()
        (tmp_path / "mastered" / "01-broken.wav").write_bytes(b"not a wav")
        _install_album(monkeypatch, "paper-boats")
        _artist(monkeypatch, None)

        result = album_stages_mod.write_album_playlist("paper-boats", tmp_path)

        assert result["tracks"] == 1
        assert "#EXTINF:-1,01-broken\n" in (tmp_path / "paper-boats.m3u8").read_text(encoding="utf-8")

    def test_mastered_stays_wav_only(self, tmp_path, monkeypatch):
        (tmp_path / "mastered").mkdir()
        _silence(tmp_path / "mastered" / "01-harbor.wav", 1.0)
        _install_album(monkeypatch, "paper-boats")
        _artist(monkeypatch, None)

        album_stages_mod.write_album_playlist("paper-boats", tmp_path)

        assert [p.name for p in (tmp_path / "mastered").iterdir()] == ["01-harbor.wav"]

    def test_nothing_mastered_removes_a_stale_playlist(self, tmp_path, monkeypatch):
        (tmp_path / "mastered").mkdir()
        stale = tmp_path / "paper-boats.m3u8"
        stale.write_text("#EXTM3U\nmastered/01-gone.wav\n", encoding="utf-8")
        _install_album(monkeypatch, "paper-boats")

        result = album_stages_mod.write_album_playlist("paper-boats", tmp_path)

        assert result["status"] == "skipped"
        assert not stale.exists()

    def test_a_write_failure_is_a_warning_not_an_error(self, tmp_path, monkeypatch):
        (tmp_path / "mastered").mkdir()
        _silence(tmp_path / "mastered" / "01-harbor.wav", 1.0)
        (tmp_path / "paper-boats.m3u8").mkdir()  # something in the way
        _install_album(monkeypatch, "paper-boats")
        _artist(monkeypatch, None)

        result = album_stages_mod.write_album_playlist("paper-boats", tmp_path)

        assert result["status"] == "warn"
        assert result["error"]


# ===========================================================================
# Every tool that writes mastered/
# ===========================================================================


class TestMasterAlbum:
    def test_the_pipeline_writes_the_playlist(self, tmp_path, monkeypatch):
        _sine(tmp_path / "01-a.wav")
        _sine(tmp_path / "02-b.wav", freq=330.0)
        _install_album(monkeypatch, "playlist-album", name="Playlist Album",
                       audio_dir=tmp_path)

        with _resolve_to(tmp_path):
            result = json.loads(asyncio.run(audio_mod.master_album(album_slug="playlist-album")))

        assert result.get("failed_stage") is None, result.get("failure_detail")
        assert result["stages"]["playlist"] == {
            "status": "pass", "path": str(tmp_path / "playlist-album.m3u8"), "tracks": 2,
        }
        lines = (tmp_path / "playlist-album.m3u8").read_text(encoding="utf-8").splitlines()
        assert lines[:2] == ["#EXTM3U", "#PLAYLIST:Playlist Album"]
        assert [line for line in lines if not line.startswith("#")] == [
            "mastered/01-a.wav", "mastered/02-b.wav",
        ]


def _run_master_audio(audio_dir: Path, **kwargs) -> dict:
    import tools.mastering.master_tracks as master_tracks_mod
    with _resolve_to(audio_dir), \
         patch.object(shared_mod, "cache", _FakeCache({})), \
         patch.object(master_tracks_mod, "_get_overrides_path", lambda: None):
        return json.loads(asyncio.run(audio_mod.master_audio("test-album", **kwargs)))


class TestMasterAudio:
    def test_mastering_writes_the_playlist(self, tmp_path):
        _sine(tmp_path / "01-a.wav", seconds=3.0)

        result = _run_master_audio(tmp_path)

        assert result["playlist"] == str(tmp_path / "test-album.m3u8")
        text = (tmp_path / "test-album.m3u8").read_text(encoding="utf-8")
        assert "mastered/01-a.wav\n" in text

    def test_a_dry_run_writes_none(self, tmp_path):
        _sine(tmp_path / "01-a.wav", seconds=3.0)

        result = _run_master_audio(tmp_path, dry_run=True)

        assert result["playlist"] is None
        assert not (tmp_path / "test-album.m3u8").exists()


class TestFixDynamicTrack:
    def test_the_fixed_track_is_in_the_playlist(self, tmp_path):
        _sine(tmp_path / "01-a.wav", seconds=3.0)

        with _resolve_to(tmp_path), patch.object(shared_mod, "cache", _FakeCache({})):
            result = json.loads(asyncio.run(audio_mod.fix_dynamic_track("test-album", "01-a.wav")))

        assert result["playlist"] == str(tmp_path / "test-album.m3u8")
        assert "mastered/01-a.wav\n" in (tmp_path / "test-album.m3u8").read_text(encoding="utf-8")


class TestMasterWithReference:
    @staticmethod
    def _matchering_stand_in():
        """matchering is heavy and optional: write the output the way it would."""
        def _master(target, reference, output):
            _silence(Path(output), 1.0)

        module = types.ModuleType("tools.mastering.reference_master")
        module.master_with_reference = MagicMock(side_effect=_master)
        return patch.dict("sys.modules", {"tools.mastering.reference_master": module})

    def _run(self, audio_dir: Path, *args) -> dict:
        with _resolve_to(audio_dir), \
             patch.object(shared_mod, "cache", _FakeCache({})), \
             patch.object(processing_helpers, "_check_matchering", return_value=None), \
             self._matchering_stand_in():
            return json.loads(asyncio.run(audio_mod.master_with_reference("test-album", *args)))

    def test_a_batch_writes_the_playlist(self, tmp_path):
        _silence(tmp_path / "ref.wav", 1.0)
        _silence(tmp_path / "01-a.wav", 1.0)
        _silence(tmp_path / "02-b.wav", 1.0)

        result = self._run(tmp_path, "ref.wav")

        assert result["playlist"] == str(tmp_path / "test-album.m3u8")
        text = (tmp_path / "test-album.m3u8").read_text(encoding="utf-8")
        assert [line for line in text.splitlines() if not line.startswith("#")] == [
            "mastered/01-a.wav", "mastered/02-b.wav",
        ]

    def test_one_track_refreshes_it_too(self, tmp_path):
        _silence(tmp_path / "ref.wav", 1.0)
        _silence(tmp_path / "01-a.wav", 1.0)

        result = self._run(tmp_path, "ref.wav", "01-a.wav")

        assert result["playlist"] == str(tmp_path / "test-album.m3u8")
