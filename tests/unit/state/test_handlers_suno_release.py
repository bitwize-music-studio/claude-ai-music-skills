#!/usr/bin/env python3
"""Unit tests for handlers/suno_release.py — the album's playlist of approved takes.

    get_suno_release_plan(album)             — keepers in track order, what is missing
    set_album_playlist(album, id, name)      — record the playlist in the album README

Neither tool talks to Suno. The track-file builder and the album fixture come
from test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_suno_release.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: F401  (album is a fixture)
    CLIP_A,
    CLIP_B,
    LEGACY_KEEPER_ROW,
    README_WITH_BLOCK,
    README_WITHOUT_BLOCK,
    _row,
    _run,
    album,
    track_md,
)

from handlers import generation as _gen_mod  # noqa: E402
from handlers import suno_release as _release_mod  # noqa: E402

pytestmark = pytest.mark.unit

PLAYLIST_ID = "dfb303aa-74b1-41f3-9771-48a69bdd43ed"
CLIP_C = "71af26e1-7ca6-486b-8511-a5a93ddc10df"
CLIP_D = "ede52b0a-e021-4b7e-8954-bc7628a969f6"


def _plan(album_slug="test-album"):
    return json.loads(_run(_release_mod.get_suno_release_plan(album_slug)))


def _set(album_slug="test-album", playlist_id=PLAYLIST_ID, name="Test Album"):
    return json.loads(_run(_release_mod.set_album_playlist(album_slug, playlist_id, name)))


def _add_track(album, slug, title, **track):  # noqa: F811
    path = album.path.parent / f"{slug}.md"
    path.write_text(track_md(title=title, **track), encoding="utf-8")
    album.state["albums"]["test-album"]["tracks"][slug] = {
        "title": title, "status": "Final", "path": str(path),
    }
    return path


@pytest.fixture
def released(album):  # noqa: F811
    """Three tracks: 01 and 03 with a keeper, 02 without one. Drops the fixture's pathless track."""
    del album.state["albums"]["test-album"]["tracks"]["02-no-path"]
    album(
        log_rows=(_row(1, CLIP_A), _row(2, CLIP_B, rating="✓")),
        suno_link=f"[Listen](https://suno.com/song/{CLIP_B})", status="Final",
    )
    _add_track(album, "02-second", "Second", log_rows=(_row(1, CLIP_C),), status="Generated")
    _add_track(
        album, "03-third", "Third", log_rows=(_row(1, CLIP_D, rating="✓"),),
        suno_link=f"https://suno.com/song/{CLIP_D}", status="Final",
    )
    return album


# ===========================================================================
# get_suno_release_plan
# ===========================================================================


class TestGetSunoReleasePlan:
    def test_keepers_come_in_track_order(self, released):
        plan = _plan()
        assert plan["found"] is True
        assert plan["album_title"] == "Test Album"
        assert plan["suggested_name"] == "Test Album"
        assert plan["playlist"] is None
        assert plan["keepers"] == [
            {"track_slug": "01-first-track", "title": "First Track", "clip_id": CLIP_B,
             "url": f"https://suno.com/song/{CLIP_B}"},
            {"track_slug": "03-third", "title": "Third", "clip_id": CLIP_D,
             "url": f"https://suno.com/song/{CLIP_D}"},
        ]
        assert plan["clip_ids"] == [CLIP_B, CLIP_D]
        assert plan["batches"] == [[CLIP_B, CLIP_D]]

    def test_tracks_without_a_keeper_are_listed_with_the_reason(self, released):
        plan = _plan()
        assert plan["missing"] == [
            {"track_slug": "02-second", "title": "Second", "reason": "no_keeper"},
        ]
        assert plan["ready"] is False

    def test_ready_when_every_track_has_a_keeper(self, released):
        _add_track(
            released, "02-second", "Second", log_rows=(_row(1, CLIP_C, rating="✓"),),
            suno_link=f"https://suno.com/song/{CLIP_C}", status="Final",
        )
        plan = _plan()
        assert plan["missing"] == []
        assert plan["ready"] is True
        assert plan["clip_ids"] == [CLIP_B, CLIP_C, CLIP_D]

    def test_keeper_from_the_generation_log_when_the_suno_link_is_unset(self, released):
        released(log_rows=(_row(1, CLIP_A, rating="✓"), _row(2, CLIP_B)), status="Final")
        assert _plan()["keepers"][0]["clip_id"] == CLIP_A

    def test_ambiguous_and_legacy_keepers(self, released):
        released(log_rows=(_row(1, CLIP_A, rating="✓"), _row(2, CLIP_B, rating="✓")), status="Final")
        _add_track(released, "03-third", "Third", log_rows=(LEGACY_KEEPER_ROW,),
                   suno_link="https://suno.com/s/4hZKwZySCc8Lc63Q", status="Final")
        reasons = {m["track_slug"]: m["reason"] for m in _plan()["missing"]}
        assert reasons["01-first-track"] == "keeper_ambiguous"
        assert reasons["03-third"] == "legacy_link"

    def test_recorded_playlist(self, released):
        released.state["albums"]["test-album"]["suno_playlist"] = {"id": PLAYLIST_ID, "name": "Test Album"}
        assert _plan()["playlist"] == {
            "id": PLAYLIST_ID, "name": "Test Album",
            "url": f"https://suno.com/playlist/{PLAYLIST_ID}",
        }

    def test_placeholder_title_suggests_the_slug(self, released):
        released.state["albums"]["test-album"]["title"] = "[Album Title]"
        assert _plan()["suggested_name"] == "test-album"

    def test_batches_of_one_hundred(self, released):
        """playlists-add-clips takes 100 ids per call."""
        tracks = released.state["albums"]["test-album"]["tracks"]
        tracks.clear()
        for n in range(1, 206):
            clip = f"{n:08x}-0000-4000-8000-000000000000"
            _add_track(released, f"{n:03d}-t", f"T{n}", log_rows=(_row(1, clip, rating="✓"),),
                       suno_link=f"https://suno.com/song/{clip}", status="Final")
        plan = _plan()
        assert [len(b) for b in plan["batches"]] == [100, 100, 5]
        assert plan["clip_ids"][0] == "00000001-0000-4000-8000-000000000000"

    def test_unreadable_track_is_missing_not_fatal(self, released):
        released.state["albums"]["test-album"]["tracks"]["04-gone"] = {
            "title": "Gone", "status": "Final", "path": str(released.path.parent / "04-gone.md"),
        }
        missing = {m["track_slug"]: m["reason"] for m in _plan()["missing"]}
        assert missing["04-gone"] == "unreadable"

    def test_unknown_album(self, released):
        assert _plan("nope")["found"] is False


# ===========================================================================
# set_album_playlist
# ===========================================================================


def _readme(album, text=README_WITH_BLOCK):  # noqa: F811
    path = Path(album.state["albums"]["test-album"]["path"]) / "README.md"
    path.write_text(text, encoding="utf-8")
    return path


class TestSetAlbumPlaylist:
    def test_adds_the_block_and_keeps_everything_else(self, released):
        path = _readme(released)
        result = _set()
        assert result == {
            "updated": True, "path": str(path),
            "playlist": {"id": PLAYLIST_ID, "name": "Test Album",
                         "url": f"https://suno.com/playlist/{PLAYLIST_ID}"},
        }
        text = path.read_text(encoding="utf-8")
        assert "suno_playlist:  # Suno playlist of this album's approved takes" in text
        assert f'  id: "{PLAYLIST_ID}"\n  name: "Test Album"\n---\n' in text
        assert "# YYYY-MM-DD (fill in when releasing)" in text          # comments survive
        assert 'suno_workspace:  # Suno workspace' in text                # the other block is untouched
        from tools.state.parsers import parse_album_readme
        parsed = parse_album_readme(path)
        assert parsed["suno_playlist"] == {"id": PLAYLIST_ID, "name": "Test Album"}
        assert parsed["suno_workspace"] is None

    def test_replaces_an_earlier_playlist(self, released):
        path = _readme(released, README_WITHOUT_BLOCK)
        _set()
        other = "0f3c6c19-0c42-4d4f-9a37-7f5fd1bd2e01"
        assert _set(playlist_id=other, name="Second Try")["playlist"]["id"] == other
        text = path.read_text(encoding="utf-8")
        assert text.count("suno_playlist:") == 1
        assert PLAYLIST_ID not in text

    def test_refreshes_the_cache_entry(self, released):
        _readme(released)
        _set()
        assert released.state["albums"]["test-album"]["suno_playlist"] == {"id": PLAYLIST_ID, "name": "Test Album"}
        _gen_mod.write_state.assert_called_once()   # the album fixture replaced it with a mock

    @pytest.mark.parametrize("bad", ["", "not-a-uuid", "../../etc"])
    def test_rejects_a_bad_playlist_id_before_writing(self, released, bad):
        path = _readme(released)
        before = path.read_text(encoding="utf-8")
        assert "error" in _set(playlist_id=bad)
        assert path.read_text(encoding="utf-8") == before

    def test_name_is_required(self, released):
        _readme(released)
        assert "error" in _set(name=" ")

    def test_missing_readme(self, released):
        assert "README" in _set()["error"]

    def test_unknown_album(self, released):
        assert _set("nope")["found"] is False
