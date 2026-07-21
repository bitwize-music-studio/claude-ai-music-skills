"""Real-Postgres integration test for the db_* MCP tools.

Drives the actual handler functions (imported from the server source, called
via ``asyncio.run`` — the same pattern the unit suite uses) end-to-end against
a live PostgreSQL server, asserting on the real returned JSON:

    db_init -> (seed album) -> db_create_tweet -> db_list_tweets ->
    db_update_tweet -> db_search_tweets -> db_get_tweet_stats ->
    db_delete_tweet -> (assert gone)

Gated behind the ``integration`` marker AND ``BITWIZE_INTEGRATION`` so the
normal suite / 3-OS matrix collect-and-skip (no Postgres present).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("BITWIZE_INTEGRATION"),
        reason="integration services not available (set BITWIZE_INTEGRATION=1)",
    ),
]


def _run(coro: Any) -> dict[str, Any]:
    """Run an async db_* tool synchronously and parse its JSON result."""
    return json.loads(asyncio.run(coro))


def _seed_album(conn: Any, slug: str) -> int:
    """Insert (or refresh) a minimal album row so db_create_tweet can resolve it.

    db_create_tweet resolves ``album_id`` from the ``albums`` table; the tweet
    tools don't create albums (that's db_sync_album, which needs full state
    cache setup). Seeding directly keeps this test focused on the tweet CRUD
    surface.
    """
    with conn.cursor() as cur:
        # Clear any stale row from an interrupted prior run (idempotent).
        cur.execute("DELETE FROM albums WHERE slug = %s", (slug,))
        cur.execute(
            """INSERT INTO albums (slug, title, genre, track_count)
               VALUES (%s, %s, %s, %s)
               RETURNING id""",
            (slug, "Integration Album", "electronic", 0),
        )
        return int(cur.fetchone()[0])


def test_tweet_lifecycle_against_real_postgres(
    seeded_config, plugin_root, pg_direct, album_slug
):
    from handlers import database as db

    # --- db_init: create schema + run migrations on a real DB ---------------
    init = _run(db.db_init())
    assert init.get("initialized") is True, init
    assert {"albums", "tracks", "tweets"}.issubset(set(init["tables"])), init

    # Seed the album the tweet references.
    _seed_album(pg_direct, album_slug)

    # --- db_create_tweet ----------------------------------------------------
    created = _run(
        db.db_create_tweet(
            album_slug,
            "Real Postgres round-trip for the integration album",
            platform="twitter",
            content_type="promo",
        )
    )
    assert created.get("created") is True, created
    tweet_id = created["tweet"]["id"]
    assert isinstance(tweet_id, int)

    # --- db_list_tweets: the row is really there ----------------------------
    listed = _run(db.db_list_tweets(album_slug=album_slug))
    assert listed["total"] >= 1, listed
    assert any(t["id"] == tweet_id for t in listed["tweets"]), listed

    # --- db_update_tweet: posted flag auto-sets posted_at -------------------
    updated = _run(db.db_update_tweet(tweet_id, posted="true", times_posted=2))
    assert updated.get("updated") is True, updated
    assert updated["tweet"]["posted"] is True
    assert updated["tweet"]["times_posted"] == 2
    assert updated["tweet"]["posted_at"] is not None

    # --- db_search_tweets: ILIKE substring match ----------------------------
    found = _run(db.db_search_tweets("round-trip", album_slug=album_slug))
    assert any(t["id"] == tweet_id for t in found["tweets"]), found

    # --- db_get_tweet_stats: aggregates reflect our row ---------------------
    stats = _run(db.db_get_tweet_stats(album_slug=album_slug))
    assert stats["total"] >= 1, stats
    assert stats["posted"] >= 1, stats
    assert any(p["platform"] == "twitter" for p in stats["per_platform"]), stats

    # --- db_delete_tweet: row is gone ---------------------------------------
    deleted = _run(db.db_delete_tweet(tweet_id))
    assert deleted.get("deleted") is True, deleted
    assert deleted["tweet_id"] == tweet_id

    after = _run(db.db_list_tweets(album_slug=album_slug))
    assert not any(t["id"] == tweet_id for t in after["tweets"]), after


def test_db_init_is_idempotent(seeded_config, plugin_root):
    """db_init uses IF NOT EXISTS patterns — running it twice must stay clean."""
    from handlers import database as db

    first = _run(db.db_init())
    second = _run(db.db_init())
    assert first.get("initialized") is True, first
    assert second.get("initialized") is True, second
    assert {"albums", "tracks", "tweets"}.issubset(set(second["tables"])), second
