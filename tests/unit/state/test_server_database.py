"""Tests for database handler pagination (db_list_tweets, db_search_tweets)."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro: Any) -> str:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_rows(n: int, album_slug: str = "test-album", platform: str = "twitter") -> list[dict]:
    """Generate N fake tweet rows matching the SELECT column layout."""
    rows = []
    for i in range(n):
        rows.append({
            "id": i + 1,
            "tweet_text": f"Post {i + 1} about the album",
            "platform": platform,
            "content_type": "promo",
            "media_path": None,
            "posted": False,
            "enabled": True,
            "times_posted": 0,
            "created_at": "2026-01-01T00:00:00",
            "posted_at": None,
            "album_slug": album_slug,
            "album_title": "Test Album",
            "track_number": None,
            "track_title": None,
        })
    return rows


class _FakeCursor:
    """Minimal psycopg2 RealDictCursor stand-in.

    The handler issues two queries per call: a COUNT(*) query first,
    then the data query with OFFSET/LIMIT appended.  We detect which
    is which via ``SELECT COUNT`` in the SQL text, then simulate
    OFFSET/LIMIT by slicing the rows list in-memory.
    """

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._results: list[dict] = []

    def execute(self, sql: str, params: list | None = None) -> None:
        sql_upper = sql.upper()
        if "SELECT COUNT" in sql_upper:
            self._results = [{"total": len(self._rows)}]
        else:
            # Figure out offset/limit from SQL keywords + trailing params.
            # The handler appends OFFSET %s and/or LIMIT %s *after* the
            # ORDER BY clause, so their param placeholders are always the
            # last entries in `params`.
            has_offset = "OFFSET" in sql_upper.split("ORDER")[-1]
            has_limit = "LIMIT" in sql_upper.split("ORDER")[-1]

            # Pop from the end: LIMIT is appended last in the handler
            p = list(params) if params else []
            limit = p.pop() if has_limit and p else None
            offset = p.pop() if has_offset and p else 0

            result = list(self._rows)[offset:]
            if limit is not None and limit > 0:
                result = result[:limit]
            self._results = result

    def fetchone(self) -> dict | None:
        return self._results[0] if self._results else None

    def fetchall(self) -> list[dict]:
        return self._results


def _patch_db(rows: list[dict]):
    """Context manager that patches DB deps and connection to return given rows."""
    fake_cursor = _FakeCursor(rows)
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor

    # Ensure psycopg2.extras is importable (may not be installed in test env)
    fake_extras = MagicMock()
    fake_extras.RealDictCursor = "RealDictCursor"

    fake_psycopg2 = MagicMock()
    fake_psycopg2.extras = fake_extras

    return _MultiPatch(fake_conn, fake_psycopg2)


class _MultiPatch:
    """Combines multiple patches into a single context manager."""

    def __init__(self, fake_conn: Any, fake_psycopg2: Any):
        self._fake_conn = fake_conn
        self._fake_psycopg2 = fake_psycopg2
        self._patches: list[Any] = []

    def __enter__(self) -> None:
        # Patch _check_db_deps to return None (no error)
        p1 = patch("handlers.database._check_db_deps", return_value=None)
        # Patch _get_db_connection to return our fake connection
        p2 = patch("handlers.database._get_db_connection",
                    return_value=(self._fake_conn, None))
        # Ensure psycopg2 and psycopg2.extras are importable
        p3 = patch.dict(sys.modules, {
            "psycopg2": self._fake_psycopg2,
            "psycopg2.extras": self._fake_psycopg2.extras,
        })
        self._patches = [p1, p2, p3]
        for p in self._patches:
            p.__enter__()

    def __exit__(self, *args: Any) -> None:
        for p in reversed(self._patches):
            p.__exit__(*args)


# ---------------------------------------------------------------------------
# Import handler module (after helpers so patches are available)
# ---------------------------------------------------------------------------

# Add server source to path
sys.path.insert(0, "servers/bitwize-music-server")
from handlers import database as server  # noqa: E402


# =============================================================================
# db_list_tweets pagination tests
# =============================================================================


@pytest.mark.unit
class TestDbListTweetsPagination:
    """Tests for limit/offset pagination in db_list_tweets."""

    def test_default_params_backward_compat(self):
        """Calling with no new params returns paginated response with defaults."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets()))
        assert result["total"] == 10
        assert result["offset"] == 0
        assert result["limit"] == 50
        assert result["has_more"] is False
        assert len(result["tweets"]) == 10

    def test_response_shape_has_pagination_fields(self):
        """Response includes total, offset, limit, has_more."""
        rows = _make_rows(3)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets()))
        expected_keys = {"tweets", "total", "offset", "limit", "has_more"}
        assert expected_keys == set(result.keys())

    def test_no_count_key(self):
        """Old 'count' key is replaced by 'total'."""
        rows = _make_rows(3)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets()))
        assert "count" not in result
        assert "total" in result

    def test_limit_zero_returns_all(self):
        """limit=0 returns all rows — backward compat."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets(limit=0)))
        assert result["total"] == 10
        assert len(result["tweets"]) == 10
        assert result["has_more"] is False
        # limit should reflect total when 0 means "all"
        assert result["limit"] == 10

    def test_limit_truncates(self):
        """limit=3 returns only 3 rows from a larger set."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets(limit=3)))
        assert result["total"] == 10
        assert len(result["tweets"]) == 3
        assert result["has_more"] is True
        assert result["limit"] == 3

    def test_offset_skips_rows(self):
        """offset=5 skips the first 5 rows."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets(limit=0, offset=5)))
        assert result["total"] == 10
        assert result["offset"] == 5
        assert len(result["tweets"]) == 5
        # First returned tweet should be post 6
        assert result["tweets"][0]["id"] == 6

    def test_offset_and_limit_combined(self):
        """offset + limit pages through results correctly."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets(limit=3, offset=2)))
        assert result["total"] == 10
        assert result["offset"] == 2
        assert result["limit"] == 3
        assert len(result["tweets"]) == 3
        assert result["has_more"] is True
        assert result["tweets"][0]["id"] == 3

    def test_offset_near_end(self):
        """offset near end returns remaining rows with has_more=False."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets(limit=5, offset=8)))
        assert result["total"] == 10
        assert len(result["tweets"]) == 2
        assert result["has_more"] is False

    def test_offset_beyond_total(self):
        """offset >= total returns empty tweets with has_more=False."""
        rows = _make_rows(5)
        with _patch_db(rows):
            result = json.loads(_run(server.db_list_tweets(limit=50, offset=100)))
        assert result["total"] == 5
        assert result["tweets"] == []
        assert result["has_more"] is False

    def test_empty_result_set(self):
        """No matching rows returns proper empty pagination."""
        with _patch_db([]):
            result = json.loads(_run(server.db_list_tweets()))
        assert result["total"] == 0
        assert result["tweets"] == []
        assert result["has_more"] is False


# =============================================================================
# db_search_tweets pagination tests
# =============================================================================


@pytest.mark.unit
class TestDbSearchTweetsPagination:
    """Tests for limit/offset pagination in db_search_tweets."""

    def test_default_params_backward_compat(self):
        """Calling with no new params returns paginated response with defaults."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("album")))
        assert result["total"] == 10
        assert result["offset"] == 0
        assert result["limit"] == 50
        assert result["has_more"] is False
        assert result["query"] == "album"
        assert len(result["tweets"]) == 10

    def test_response_shape_has_pagination_fields(self):
        """Response includes query, total, offset, limit, has_more."""
        rows = _make_rows(3)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("test")))
        expected_keys = {"query", "tweets", "total", "offset", "limit", "has_more"}
        assert expected_keys == set(result.keys())

    def test_no_count_key(self):
        """Old 'count' key is replaced by 'total'."""
        rows = _make_rows(3)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("test")))
        assert "count" not in result
        assert "total" in result

    def test_limit_zero_returns_all(self):
        """limit=0 returns all rows — backward compat."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("album", limit=0)))
        assert result["total"] == 10
        assert len(result["tweets"]) == 10
        assert result["has_more"] is False
        assert result["limit"] == 10

    def test_limit_truncates(self):
        """limit=3 returns only 3 rows from a larger set."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("album", limit=3)))
        assert result["total"] == 10
        assert len(result["tweets"]) == 3
        assert result["has_more"] is True

    def test_offset_skips_rows(self):
        """offset=5 skips the first 5 rows."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("album", limit=0, offset=5)))
        assert result["total"] == 10
        assert result["offset"] == 5
        assert len(result["tweets"]) == 5
        assert result["tweets"][0]["id"] == 6

    def test_offset_and_limit_combined(self):
        """offset + limit pages through results."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("album", limit=3, offset=2)))
        assert result["total"] == 10
        assert len(result["tweets"]) == 3
        assert result["has_more"] is True
        assert result["tweets"][0]["id"] == 3

    def test_offset_near_end(self):
        """offset near end returns remaining rows with has_more=False."""
        rows = _make_rows(10)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("album", limit=5, offset=8)))
        assert result["total"] == 10
        assert len(result["tweets"]) == 2
        assert result["has_more"] is False

    def test_offset_beyond_total(self):
        """offset >= total returns empty tweets."""
        rows = _make_rows(5)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("album", limit=50, offset=100)))
        assert result["total"] == 5
        assert result["tweets"] == []
        assert result["has_more"] is False

    def test_empty_query_rejected(self):
        """Empty query still returns error, pagination doesn't change that."""
        result = json.loads(_run(server.db_search_tweets("")))
        assert "error" in result

    def test_query_preserved_in_response(self):
        """The query field is always returned."""
        rows = _make_rows(3)
        with _patch_db(rows):
            result = json.loads(_run(server.db_search_tweets("hello world", limit=1)))
        assert result["query"] == "hello world"

    def test_empty_result_set(self):
        """No matching rows returns proper empty pagination."""
        with _patch_db([]):
            result = json.loads(_run(server.db_search_tweets("nonexistent")))
        assert result["total"] == 0
        assert result["tweets"] == []
        assert result["has_more"] is False
