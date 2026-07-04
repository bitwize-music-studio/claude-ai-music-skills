#!/usr/bin/env python3
"""Input-validation tests for handlers/database.py MCP tool handlers.

Malformed slugs (path separators, null bytes, traversal sequences) must
produce a structured JSON error via _safe_json — never an exception that
escapes the handler to the FastMCP layer.

Structured one class per tool so later issues can append their own classes.

Covers:
    - issue #379: db_sync_album crashed with an uncaught ValueError on
      malformed album_slug because _find_album_or_error ran outside the
      handler's try block.
    - issue #380: db_create_tweet silently dropped the track link (inserted
      track_id NULL) and falsely echoed the requested track_number when the
      track row was not found for the album.

Usage:
    python -m pytest tests/unit/state/test_handlers_database_validation.py -v
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure the MCP server source is importable as the `handlers` package
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import database as _database_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> str:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


SAMPLE_STATE: dict[str, Any] = {
    "albums": {
        "test-album": {
            "title": "Test Album",
            "genre": "electronic",
            "status": "In Progress",
            "track_count": 1,
            "explicit": False,
            "release_date": None,
            "streaming_urls": {},
            "tracks": {
                "01-first-track": {"title": "First Track"},
            },
        },
    },
}


class MockStateCache:
    """Minimal StateCache stand-in for _shared.cache."""

    def __init__(self, state: dict[str, Any] | None = None):
        self._state = state if state is not None else copy.deepcopy(SAMPLE_STATE)

    def get_state(self) -> dict[str, Any]:
        return self._state

    def get_state_ref(self) -> dict[str, Any]:
        return self._state


class _FakeSyncCursor:
    """Cursor stand-in for db_sync_album's INSERT ... RETURNING queries."""

    def execute(self, sql: str, params: Any = None) -> None:
        pass

    def fetchone(self) -> dict[str, Any]:
        return {"id": 1}


class _PatchedDb:
    """Patch DB deps, connection, and psycopg2 import for handler tests."""

    def __init__(self) -> None:
        self.conn = MagicMock()
        self.conn.cursor.return_value = _FakeSyncCursor()

        fake_extras = MagicMock()
        fake_extras.RealDictCursor = "RealDictCursor"
        fake_psycopg2 = MagicMock()
        fake_psycopg2.extras = fake_extras

        self._patches = [
            patch("handlers.database._check_db_deps", return_value=None),
            patch(
                "handlers.database._get_db_connection",
                return_value=(self.conn, None),
            ),
            patch.dict(sys.modules, {
                "psycopg2": fake_psycopg2,
                "psycopg2.extras": fake_extras,
            }),
        ]

    def __enter__(self) -> "_PatchedDb":
        for p in self._patches:
            p.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        for p in reversed(self._patches):
            p.__exit__(*args)


# =============================================================================
# db_sync_album — issue #379
# =============================================================================


@pytest.mark.unit
class TestDbSyncAlbumSlugValidation:
    """db_sync_album must return a JSON error on malformed album_slug (#379)."""

    def setup_method(self) -> None:
        self._orig_cache = _shared_mod.cache
        _shared_mod.cache = MockStateCache()

    def teardown_method(self) -> None:
        _shared_mod.cache = self._orig_cache

    @pytest.mark.parametrize("bad_slug", [
        "../etc",
        "a/b",
        "a\\b",
        "nul\0byte",
    ])
    def test_malformed_slug_returns_json_error(self, bad_slug: str) -> None:
        """Malformed slugs return a structured JSON error, not an exception."""
        with _PatchedDb():
            result = _run(_database_mod.db_sync_album(bad_slug))
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Invalid" in parsed["error"]
        assert "synced" not in parsed

    def test_valid_slug_not_found_returns_not_found_error(self) -> None:
        """Valid but unknown slug still returns the album-not-found JSON."""
        with _PatchedDb():
            result = _run(_database_mod.db_sync_album("no-such-album"))
        parsed = json.loads(result)
        assert parsed["found"] is False
        assert "not found" in parsed["error"]
        assert "available_albums" in parsed

    def test_valid_slug_syncs_album(self) -> None:
        """Valid existing slug syncs album and tracks (behavior unchanged)."""
        with _PatchedDb() as db:
            result = _run(_database_mod.db_sync_album("test-album"))
        parsed = json.loads(result)
        assert parsed == {
            "synced": True,
            "album_slug": "test-album",
            "album_id": 1,
            "tracks_synced": 1,
        }
        db.conn.commit.assert_called_once()
        db.conn.close.assert_called_once()


# =============================================================================
# db_create_tweet — issue #380
# =============================================================================


class _FakeTweetCursor:
    """Cursor stand-in for db_create_tweet's SELECT/INSERT queries.

    Dispatches fetchone() results based on the last executed SQL so a
    single cursor can serve the album lookup, the track lookup, and the
    INSERT ... RETURNING in sequence.
    """

    def __init__(self, track_exists: bool = True) -> None:
        self.track_exists = track_exists
        self.executed: list[str] = []
        self._last_sql = ""

    def execute(self, sql: str, params: Any = None) -> None:
        self._last_sql = sql
        self.executed.append(sql)

    def fetchone(self) -> dict[str, Any] | None:
        if "FROM albums" in self._last_sql:
            return {"id": 1}
        if "FROM tracks" in self._last_sql:
            return {"id": 42} if self.track_exists else None
        if "INSERT INTO tweets" in self._last_sql:
            return {
                "id": 7,
                "tweet_text": "check out this track",
                "platform": "twitter",
                "content_type": "promo",
                "media_path": None,
                "posted": False,
                "enabled": True,
                "times_posted": 0,
                "created_at": "2026-01-01T00:00:00",
            }
        return None

    @property
    def inserted(self) -> bool:
        return any("INSERT INTO tweets" in sql for sql in self.executed)


@pytest.mark.unit
class TestDbCreateTweetTrackLink:
    """db_create_tweet must not silently drop a requested track link (#380)."""

    def test_missing_track_returns_json_error(self) -> None:
        """track_number > 0 with no matching track row → structured error."""
        cursor = _FakeTweetCursor(track_exists=False)
        with _PatchedDb() as db:
            db.conn.cursor.return_value = cursor
            result = _run(_database_mod.db_create_tweet(
                "test-album", "check out this track", track_number=5,
            ))
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "error" in parsed
        assert "5" in parsed["error"]
        assert "created" not in parsed
        assert "track_number" not in parsed.get("tweet", {})

    def test_missing_track_does_not_insert_or_commit(self) -> None:
        """No tweet row is inserted or committed when the track is missing."""
        cursor = _FakeTweetCursor(track_exists=False)
        with _PatchedDb() as db:
            db.conn.cursor.return_value = cursor
            _run(_database_mod.db_create_tweet(
                "test-album", "check out this track", track_number=5,
            ))
        assert not cursor.inserted
        db.conn.commit.assert_not_called()
        db.conn.close.assert_called_once()

    def test_track_found_reports_track_number(self) -> None:
        """Existing track → tweet created with the correct track_number."""
        cursor = _FakeTweetCursor(track_exists=True)
        with _PatchedDb() as db:
            db.conn.cursor.return_value = cursor
            result = _run(_database_mod.db_create_tweet(
                "test-album", "check out this track", track_number=5,
            ))
        parsed = json.loads(result)
        assert parsed["created"] is True
        assert parsed["tweet"]["track_number"] == 5
        assert parsed["tweet"]["album_slug"] == "test-album"
        assert cursor.inserted
        db.conn.commit.assert_called_once()
        db.conn.close.assert_called_once()

    def test_album_level_tweet_skips_track_lookup(self) -> None:
        """track_number=0 → album-level tweet, track_number null (unchanged)."""
        cursor = _FakeTweetCursor(track_exists=False)
        with _PatchedDb() as db:
            db.conn.cursor.return_value = cursor
            result = _run(_database_mod.db_create_tweet(
                "test-album", "album announcement", track_number=0,
            ))
        parsed = json.loads(result)
        assert parsed["created"] is True
        assert parsed["tweet"]["track_number"] is None
        assert not any("FROM tracks" in sql for sql in cursor.executed)
        db.conn.commit.assert_called_once()
