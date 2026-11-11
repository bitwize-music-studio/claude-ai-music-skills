#!/usr/bin/env python3
"""Unit tests for handlers/album_fields.py — album README upkeep.

    update_album_field(album, field, value)   — release date, explicit, tracks, concept, anchor track
    sync_album_tracklist(album, dry_run)      — rebuild the Tracklist table from the track files
    after_track_status_change(album, track)   — keep the README row and the album status in step

Usage:
    python -m pytest tests/unit/state/test_handlers_album_fields.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: F401
    MockStateCache,
    _run,
    _shared_mod,
    server,
    track_md,
)

from handlers import album_fields as _fields_mod  # noqa: E402
from handlers import core as _core_mod  # noqa: E402
from handlers import status as _status_mod  # noqa: E402
from tools.state.parsers import parse_album_readme  # noqa: E402

pytestmark = pytest.mark.unit

README = """---
title: "Test Album"
release_date: ""  # YYYY-MM-DD (fill in when releasing)
genres: ["folk"]
explicit: false  # true or false
# anchor_track: null  # Optional: 1-based track number to anchor album mastering
streaming:
  spotify: ""       # Fill in when released
---

# Test Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Artist** | test-artist |
| **Album** | Test Album |
| **Genre** | Folk |
| **Tracks** | 2 |
| **Status** | In Progress |
| **Explicit** | No |
| **Concept** | A quiet record |

## Soundtrack

| Attribute | Detail |
|-----------|--------|
| **Genre** | Platformer |
| **Concept** | Not this one |

## Tracklist

| # | Title | POV | Concept | Status |
|---|-------|-----|---------|--------|
| 01 | [Old Title](tracks/01-first.md) | First person | Kettle and boats | In Progress |
| 02 | [Second](tracks/02-second.md) | Narrator | The harbour | Not Started |
| 09 | [Deleted Track](tracks/09-gone.md) | — | Removed long ago | Not Started |

## Notes

Written by hand, must survive.
"""


@pytest.fixture
def album(tmp_path, monkeypatch):
    """An album on disk: README plus three track files, and a mock state cache."""
    album_dir = tmp_path / "content" / "test-album"
    tracks_dir = album_dir / "tracks"
    tracks_dir.mkdir(parents=True)
    readme = album_dir / "README.md"
    readme.write_text(README, encoding="utf-8")

    tracks = {}
    for slug, title, status in (
        ("01-first", "First", "Final"),
        ("02-second", "Second", "Generated"),
        ("03-third", "Third", "In Progress"),
    ):
        path = tracks_dir / f"{slug}.md"
        path.write_text(track_md(title=title, status=status), encoding="utf-8")
        tracks[slug] = {
            "title": title, "status": status, "path": str(path), "explicit": False,
            "has_suno_link": status == "Final", "sources_verified": "N/A", "mtime": 1.0,
        }
    state = {
        "config": {"content_root": str(tmp_path / "content"), "artist_name": "test-artist"},
        "albums": {
            "test-album": {
                "title": "Test Album", "genre": "folk", "status": "In Progress",
                "path": str(album_dir), "explicit": False, "release_date": None,
                "track_count": 2, "readme_mtime": 1.0, "tracks": tracks,
            },
        },
    }
    monkeypatch.setattr(_shared_mod, "cache", MockStateCache(state))
    for module in (_fields_mod, _core_mod):
        monkeypatch.setattr(module, "write_state", MagicMock())
    return type("Album", (), {"dir": album_dir, "readme": readme, "state": state, "tracks": tracks})


def _field(field, value, album_slug="test-album"):
    return json.loads(_run(_fields_mod.update_album_field(album_slug, field, value)))


def _sync(dry_run=False, album_slug="test-album"):
    return json.loads(_run(_fields_mod.sync_album_tracklist(album_slug, dry_run)))


def _tracklist(text):
    section = text.split("## Tracklist", 1)[1].split("\n## ", 1)[0]
    return [line for line in section.splitlines() if line.startswith("|")]


# ===========================================================================
# update_album_field
# ===========================================================================


class TestUpdateAlbumField:
    def test_release_date_keeps_the_line_comment(self, album):
        result = _field("release-date", "2026-12-01")
        assert result["success"] is True
        assert result["field"] == "release_date"
        text = album.readme.read_text(encoding="utf-8")
        assert 'release_date: "2026-12-01"  # YYYY-MM-DD (fill in when releasing)' in text
        assert parse_album_readme(album.readme)["release_date"] == "2026-12-01"
        assert album.state["albums"]["test-album"]["release_date"] == "2026-12-01"

    def test_release_date_can_be_cleared(self, album):
        _field("release_date", "2026-12-01")
        assert _field("release-date", "")["success"] is True
        assert 'release_date: ""  # YYYY-MM-DD' in album.readme.read_text(encoding="utf-8")

    @pytest.mark.parametrize("bad", ["December 1", "2026-13-01", "2026-02-30", "26-12-01"])
    def test_bad_release_date(self, album, bad):
        before = album.readme.read_text(encoding="utf-8")
        assert "error" in _field("release-date", bad)
        assert album.readme.read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("value,flag,cell", [("Yes", "true", "Yes"), ("true", "true", "Yes"), ("no", "false", "No")])
    def test_explicit_sets_frontmatter_and_the_details_row(self, album, value, flag, cell):
        assert _field("explicit", value)["success"] is True
        text = album.readme.read_text(encoding="utf-8")
        assert f"explicit: {flag}  # true or false" in text
        assert f"| **Explicit** | {cell} |" in text
        assert album.state["albums"]["test-album"]["explicit"] is (flag == "true")

    def test_bad_explicit(self, album):
        assert "error" in _field("explicit", "maybe")

    def test_tracks_and_concept_touch_only_album_details(self, album):
        assert _field("tracks", "3")["success"] is True
        assert _field("concept", "Slow mornings | harbour light")["success"] is True
        text = album.readme.read_text(encoding="utf-8")
        assert "| **Tracks** | 3 |" in text
        assert "| **Concept** | Slow mornings \\| harbour light |" in text
        assert "| **Concept** | Not this one |" in text       # the Soundtrack table is untouched
        assert "| **Genre** | Platformer |" in text
        assert album.state["albums"]["test-album"]["track_count"] == 3

    @pytest.mark.parametrize("bad", ["-1", "three", ""])
    def test_bad_tracks(self, album, bad):
        assert "error" in _field("tracks", bad)

    def test_anchor_track_replaces_the_commented_template_line(self, album):
        assert _field("anchor-track", "2")["success"] is True
        text = album.readme.read_text(encoding="utf-8")
        assert "anchor_track: 2  # Optional: 1-based track number to anchor album mastering" in text
        assert "# anchor_track:" not in text
        assert parse_album_readme(album.readme)["anchor_track"] == 2
        assert _field("anchor_track", "auto")["success"] is True
        assert "anchor_track: null  # Optional" in album.readme.read_text(encoding="utf-8")

    @pytest.mark.parametrize("bad", ["0", "-2", "second"])
    def test_bad_anchor_track(self, album, bad):
        assert "error" in _field("anchor-track", bad)

    def test_key_missing_from_frontmatter_is_added(self, album):
        album.readme.write_text(README.replace('release_date: ""  # YYYY-MM-DD (fill in when releasing)\n', ""), encoding="utf-8")
        assert _field("release-date", "2026-12-01")["success"] is True
        assert parse_album_readme(album.readme)["release_date"] == "2026-12-01"

    def test_the_rest_of_the_file_is_untouched(self, album):
        _field("release-date", "2026-12-01")
        text = album.readme.read_text(encoding="utf-8")
        assert text.replace('release_date: "2026-12-01"', 'release_date: ""') == README

    def test_status_is_not_edited_here(self, album):
        result = _field("status", "Complete")
        assert "update_album_status" in result["error"]

    def test_unknown_field(self, album):
        assert "Valid options" in _field("colour", "blue")["error"]

    def test_unknown_album_and_missing_readme(self, album):
        assert _field("tracks", "3", album_slug="nope")["found"] is False
        album.readme.unlink()
        assert "README" in _field("tracks", "3")["error"]


# ===========================================================================
# sync_album_tracklist
# ===========================================================================


class TestSyncAlbumTracklist:
    def test_rebuilds_the_table_from_the_track_files(self, album):
        result = _sync()
        assert result["changed"] is True
        assert result["rows"] == 3
        assert result["added"] == ["03-third"]
        assert result["removed"] == ["09"]
        assert result["updated"] == ["01-first", "02-second"]
        rows = _tracklist(album.readme.read_text(encoding="utf-8"))
        assert rows == [
            "| # | Title | POV | Concept | Status |",
            "|---|-------|-----|---------|--------|",
            "| 01 | [First](tracks/01-first.md) | First person | Kettle and boats | Final |",
            "| 02 | [Second](tracks/02-second.md) | Narrator | The harbour | Generated |",
            "| 03 | [Third](tracks/03-third.md) | — | — | In Progress |",
        ]

    def test_hand_written_columns_and_the_rest_of_the_file_survive(self, album):
        _sync()
        text = album.readme.read_text(encoding="utf-8")
        assert "Kettle and boats" in text and "The harbour" in text
        assert "## Notes\n\nWritten by hand, must survive.\n" in text
        assert "| **Concept** | A quiet record |" in text

    def test_track_count_row_follows(self, album):
        result = _sync()
        assert result["tracks_row"] == 3
        assert "| **Tracks** | 3 |" in album.readme.read_text(encoding="utf-8")
        assert album.state["albums"]["test-album"]["track_count"] == 3

    def test_dry_run_writes_nothing(self, album):
        before = album.readme.read_text(encoding="utf-8")
        result = _sync(dry_run=True)
        assert result["changed"] is True and result["dry_run"] is True
        assert album.readme.read_text(encoding="utf-8") == before

    def test_second_run_changes_nothing(self, album):
        _sync()
        again = _sync()
        assert again["changed"] is False
        assert again["added"] == again["removed"] == again["updated"] == []

    def test_three_column_table_with_unpadded_numbers(self, album):
        text = README.split("## Tracklist")[0] + (
            "## Tracklist\n\n| # | Title | Status |\n|---|-------|--------|\n"
            "| 1 | First | Final |\n| 2 | Second | In Progress |\n"
        )
        album.readme.write_text(text, encoding="utf-8")
        _sync()
        assert _tracklist(album.readme.read_text(encoding="utf-8"))[2:] == [
            "| 1 | [First](tracks/01-first.md) | Final |",
            "| 2 | [Second](tracks/02-second.md) | Generated |",
            "| 3 | [Third](tracks/03-third.md) | In Progress |",
        ]

    def test_no_tracklist_section(self, album):
        album.readme.write_text(README.split("## Tracklist")[0], encoding="utf-8")
        assert "Tracklist" in _sync()["error"]

    def test_unknown_album(self, album):
        assert _sync(album_slug="nope")["found"] is False


# ===========================================================================
# Following a track's status
# ===========================================================================


def _set_status(slug, status, force=False):
    return json.loads(_run(_core_mod.update_track_field("test-album", slug, "status", status, force)))


class TestTrackStatusFollowUp:
    def test_the_readme_row_follows_the_track(self, album):
        result = _set_status("02-second", "Final", force=True)
        assert result["success"] is True
        assert result["readme_tracklist"] == "updated"
        rows = _tracklist(album.readme.read_text(encoding="utf-8"))
        assert rows[3] == "| 02 | [Second](tracks/02-second.md) | Narrator | The harbour | Final |"
        assert rows[2].endswith("| In Progress |")          # other rows are left as they were

    def test_a_track_without_a_row_is_not_added(self, album):
        result = _set_status("03-third", "Generated", force=True)
        assert result["success"] is True
        assert "readme_tracklist" not in result
        assert "03-third" not in album.readme.read_text(encoding="utf-8")

    def test_album_completes_when_the_last_track_is_final(self, album, monkeypatch):
        monkeypatch.setattr(_status_mod, "write_state", MagicMock(), raising=False)
        _set_status("02-second", "Final", force=True)
        assert album.state["albums"]["test-album"]["status"] == "In Progress"   # 03 is not Final yet
        result = _set_status("03-third", "Final", force=True)
        assert result["album_status"] == {"from": "In Progress", "to": "Complete"}
        assert "| **Status** | Complete |" in album.readme.read_text(encoding="utf-8")
        assert album.state["albums"]["test-album"]["status"] == "Complete"

    def test_an_album_that_is_not_in_progress_is_left_alone(self, album):
        album.state["albums"]["test-album"]["status"] = "Concept"
        for slug in ("02-second", "03-third"):
            result = _set_status(slug, "Final", force=True)
        assert "album_status" not in result
        assert "| **Status** | In Progress |" in album.readme.read_text(encoding="utf-8")

    def test_other_fields_trigger_nothing(self, album):
        result = json.loads(_run(_core_mod.update_track_field("test-album", "02-second", "explicit", "Yes")))
        assert result["success"] is True
        assert "readme_tracklist" not in result and "album_status" not in result

    def test_a_missing_readme_does_not_fail_the_track_update(self, album):
        album.readme.unlink()
        result = _set_status("02-second", "Final", force=True)
        assert result["success"] is True
        assert "readme_tracklist" not in result


# ===========================================================================
# get_album_progress
# ===========================================================================


class TestProgressExtras:
    def test_takes_awaiting_a_decision_and_the_suno_references(self, album):
        clip_a = "4ef71736-b95e-489b-b5ac-1a41badceb08"
        clip_b = "6455b9ea-f786-4769-ac20-a2eb3eb49fee"
        row = "| {n} | 2026-06-15 | v6 | [Listen](https://suno.com/song/{clip}) | 0:52, via MCP, 10 credits | {rating} |"
        Path(album.tracks["02-second"]["path"]).write_text(track_md(
            title="Second", status="Generated",
            log_rows=(row.format(n=1, clip=clip_a, rating="—"), row.format(n=2, clip=clip_b, rating="—")),
        ), encoding="utf-8")
        album.state["albums"]["test-album"]["suno_workspace"] = {"id": "w", "name": "Test Album"}
        progress = json.loads(_run(_core_mod.get_album_progress("test-album")))
        assert progress["takes_pending_decision"] == [
            {"track_slug": "02-second", "title": "Second", "takes": 2},
        ]
        assert progress["suno_workspace"] == {"id": "w", "name": "Test Album"}
        assert progress["suno_playlist"] is None

    def test_a_track_with_a_keeper_is_not_pending(self, album):
        clip_a = "4ef71736-b95e-489b-b5ac-1a41badceb08"
        row = f"| 1 | 2026-06-15 | v6 | [Listen](https://suno.com/song/{clip_a}) | 0:52 | ✓ |"
        Path(album.tracks["02-second"]["path"]).write_text(
            track_md(title="Second", status="Generated", log_rows=(row,)), encoding="utf-8")
        progress = json.loads(_run(_core_mod.get_album_progress("test-album")))
        assert progress["takes_pending_decision"] == []
