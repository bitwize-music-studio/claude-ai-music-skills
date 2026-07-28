"""Companion to test_symlinked_audio_dir_passes, for the audio funnel.

test_symlinked_audio_dir_passes pins that an album audio directory may be a
symlink pointing outside audio_root — but only exercises
validate_album_structure. _resolve_audio_dir is the funnel every audio tool
goes through (master, polish, qc, transcribe, promo video, sheet music), and
it must accept the same layout.

The rest of this module covers the other half of the same problem: _album_dir
raises, and each call site's contract says how a failure is reported. A raise
that escapes skips the structured error path the callers were built around.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for p in (PROJECT_ROOT, PROJECT_ROOT / "servers" / "bitwize-music-server"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from handlers import _shared  # noqa: E402
from handlers import maintenance  # noqa: E402


class _FakeCache:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state


@pytest.fixture
def symlinked_album(tmp_path, monkeypatch):
    """audio_root holding an album dir symlinked to a real dir outside it."""
    real = tmp_path / "external-drive" / "test-album"
    real.mkdir(parents=True)
    (real / "01-track.wav").write_bytes(b"RIFF")

    audio_root = tmp_path / "audio"
    parent = audio_root / "artists" / "test-artist" / "albums" / "electronic"
    parent.mkdir(parents=True)
    (parent / "test-album").symlink_to(real)

    monkeypatch.setattr(_shared, "cache", _FakeCache({
        "config": {"audio_root": str(audio_root), "artist_name": "test-artist"},
        "albums": {"test-album": {"genre": "electronic"}},
    }))
    return parent / "test-album"


def test_resolve_audio_dir_accepts_symlinked_album(symlinked_album):
    """The layout validate_album_structure passes must also resolve."""
    err, audio_dir = _shared._resolve_audio_dir("test-album")
    assert err is None, err
    assert audio_dir == symlinked_album
    assert [p.name for p in audio_dir.glob("*.wav")] == ["01-track.wav"]


def test_resolve_audio_dir_never_raises(symlinked_album):
    """Its contract is (error_json_or_None, Path_or_None) — not an exception.

    Every `err, d = _resolve_audio_dir(...)` call site branches on `err`;
    a raise skips all of those error paths.
    """
    try:
        _shared._resolve_audio_dir("test-album")
    except ValueError as exc:
        pytest.fail(f"_resolve_audio_dir raised instead of returning an error: {exc}")


def test_resolve_audio_dir_reports_a_bad_path_as_an_error_tuple(tmp_path, monkeypatch):
    """A genre that cannot be joined must arrive as `err`, not as a traceback."""
    monkeypatch.setattr(_shared, "cache", _FakeCache({
        "config": {"audio_root": str(tmp_path), "artist_name": "test-artist"},
        "albums": {"test-album": {"genre": "../../etc"}},
    }))
    err, audio_dir = _shared._resolve_audio_dir("test-album")
    assert audio_dir is None
    assert json.loads(err)["error"] == _shared.PATH_ESCAPES_ROOT


class TestMigrateAudioLayoutKeepsItsReport:
    """A bad album late in the loop must not erase the moves already made.

    migrate_audio_layout physically moves WAV files into originals/ as it goes.
    The results list is the only record of what moved, so an exception raised on
    album N discards the report for albums 1..N-1 *after* their files have been
    relocated — the user is left with a traceback and a changed filesystem.
    """

    @pytest.fixture
    def two_albums_one_bad(self, tmp_path, monkeypatch):
        audio_root = tmp_path / "audio"
        good = audio_root / "artists" / "a" / "albums" / "electronic" / "good-album"
        good.mkdir(parents=True)
        (good / "01-track.wav").write_bytes(b"RIFF")

        monkeypatch.setattr(_shared, "cache", _FakeCache({
            "config": {"audio_root": str(audio_root), "artist_name": "a"},
            # dict order is the loop order: the good album is migrated first,
            # then the bad one fails to resolve.
            "albums": {
                "good-album": {"genre": "electronic"},
                "bad-album": {"genre": "../../etc"},
            },
        }))
        return good

    def test_a_bad_album_is_reported_not_raised(self, two_albums_one_bad):
        result = json.loads(asyncio.run(
            maintenance.migrate_audio_layout(dry_run=False)
        ))
        by_slug = {a["slug"]: a for a in result["albums"]}

        assert by_slug["good-album"]["status"] == "migrated"
        assert by_slug["good-album"]["files_moved"] == ["01-track.wav"]
        assert by_slug["bad-album"]["status"] == "skipped"
        assert _shared.PATH_ESCAPES_ROOT in by_slug["bad-album"]["skip_reason"]
        assert result["summary"]["migrated"] == 1

    def test_the_files_it_reports_as_moved_really_moved(self, two_albums_one_bad):
        asyncio.run(maintenance.migrate_audio_layout(dry_run=False))
        assert (two_albums_one_bad / "originals" / "01-track.wav").is_file()
