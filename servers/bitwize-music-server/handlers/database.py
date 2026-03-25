"""Database tools — tweet/promo management via PostgreSQL."""

import logging
from typing import Optional

from handlers._shared import _normalize_slug, _safe_json, _find_album_or_error
from handlers import _shared

logger = logging.getLogger("bitwize-music-state")

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _check_db_deps() -> Optional[str]:
    """Return error message if database deps missing, else None."""
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        return (
            "Missing database dependency: psycopg2. "
            "Install: pip install psycopg2-binary"
        )
    return None


def _get_db_connection():
    """Get a psycopg2 connection using config credentials.

    Returns:
        (connection, None) on success, (None, error_json) on failure.
    """
    from tools.database.connection import get_db_config, get_connection

    db_config = get_db_config()
    if db_config is None:
        return None, _safe_json({
            "error": "Database not configured or not enabled. "
                     "Add a 'database:' section to ~/.bitwize-music/config.yaml"
        })

    try:
        conn = get_connection(db_config)
        return conn, None
    except Exception as e:
        return None, _safe_json({"error": f"Database connection failed: {e}"})


def _get_schema_sql() -> str:
    """Read the schema.sql file from tools/database/."""
    schema_path = _shared.PLUGIN_ROOT / "tools" / "database" / "schema.sql"
    if not schema_path.exists():
        return ""
    return schema_path.read_text(encoding="utf-8")


def _get_migration_files() -> list:
    """Get sorted list of migration SQL files."""
    migrations_dir = _shared.PLUGIN_ROOT / "tools" / "database" / "migrations"
    if not migrations_dir.exists():
        return []
    return sorted(migrations_dir.glob("*.sql"))


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


async def db_init(run_migrations: str = "true") -> str:
    """Initialize the database and run migrations.

    Creates tables if they don't exist (tools/database/schema.sql), then
    runs any migration files from tools/database/migrations/. Safe to run
    multiple times — all statements use IF NOT EXISTS / IF EXISTS patterns.

    Args:
        run_migrations: Also run migration files ("true" or "false", default: "true")

    Returns:
        JSON with initialization result (tables, migrations applied)
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    schema_sql = _get_schema_sql()
    if not schema_sql:
        return _safe_json({
            "error": "Schema file not found at tools/database/schema.sql"
        })

    conn, err = _get_db_connection()
    if err:
        return err

    try:
        cur = conn.cursor()

        # Run base schema
        cur.execute(schema_sql)
        conn.commit()

        # Run migrations
        migrations_applied = []
        if run_migrations.lower() != "false":
            for migration_file in _get_migration_files():
                try:
                    migration_sql = migration_file.read_text(encoding="utf-8")
                    cur.execute(migration_sql)
                    conn.commit()
                    migrations_applied.append(migration_file.name)
                except Exception as e:
                    conn.rollback()
                    migrations_applied.append(
                        f"{migration_file.name} (FAILED: {e})"
                    )

        # Check what tables exist now
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('albums', 'tracks', 'tweets')
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

        return _safe_json({
            "initialized": True,
            "tables": tables,
            "migrations_applied": migrations_applied,
            "schema_file": "tools/database/schema.sql",
        })
    except Exception as e:
        conn.rollback()
        return _safe_json({"error": f"Schema execution failed: {e}"})
    finally:
        conn.close()


async def db_list_tweets(
    album_slug: str = "",
    posted: str = "",
    enabled: str = "",
    platform: str = "",
) -> str:
    """List tweets with optional filtering by album, posted/enabled status, or platform.

    Args:
        album_slug: Filter by album slug (empty = all albums)
        posted: Filter by posted status ("true", "false", or empty for all)
        enabled: Filter by enabled status ("true", "false", or empty for all)
        platform: Filter by platform ("twitter", "instagram", "tiktok",
                  "facebook", "youtube", or empty for all)

    Returns:
        JSON with tweets list and count
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    conn, err = _get_db_connection()
    if err:
        return err

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            SELECT t.id, t.tweet_text, t.platform, t.content_type,
                   t.media_path, t.posted, t.enabled, t.times_posted,
                   t.created_at, t.posted_at,
                   a.slug as album_slug, a.title as album_title,
                   tr.track_number, tr.title as track_title
            FROM tweets t
            JOIN albums a ON t.album_id = a.id
            LEFT JOIN tracks tr ON t.track_id = tr.id
            WHERE 1=1
        """
        params = []

        if album_slug:
            query += " AND a.slug = %s"
            params.append(_normalize_slug(album_slug))

        if posted.lower() in ("true", "false"):
            query += " AND t.posted = %s"
            params.append(posted.lower() == "true")

        if enabled.lower() in ("true", "false"):
            query += " AND t.enabled = %s"
            params.append(enabled.lower() == "true")

        if platform:
            query += " AND t.platform = %s"
            params.append(platform.lower())

        query += " ORDER BY a.slug, t.id"

        cur.execute(query, params)
        rows = cur.fetchall()

        tweets = []
        for row in rows:
            tweets.append({
                "id": row["id"],
                "tweet_text": row["tweet_text"],
                "platform": row["platform"],
                "content_type": row["content_type"],
                "media_path": row["media_path"],
                "posted": row["posted"],
                "enabled": row["enabled"],
                "times_posted": row["times_posted"],
                "created_at": row["created_at"],
                "posted_at": row["posted_at"],
                "album_slug": row["album_slug"],
                "album_title": row["album_title"],
                "track_number": row["track_number"],
                "track_title": row["track_title"],
            })

        return _safe_json({"tweets": tweets, "count": len(tweets)})
    except Exception as e:
        return _safe_json({"error": f"Query failed: {e}"})
    finally:
        conn.close()


async def db_create_tweet(
    album_slug: str,
    tweet_text: str,
    track_number: int = 0,
    platform: str = "twitter",
    content_type: str = "promo",
    media_path: str = "",
) -> str:
    """Insert a new post linked to an album and optionally a track.

    Auto-resolves album_id and track_id from the album slug and track number.

    Args:
        album_slug: Album slug (e.g., "my-album")
        tweet_text: The post text content
        track_number: Track number to link (0 = album-level post, no track link)
        platform: Target platform ("twitter", "instagram", "tiktok",
                  "facebook", "youtube"). Default: "twitter"
        content_type: Post type ("promo", "announcement", "engagement",
                      "behind_the_scenes"). Default: "promo"
        media_path: Path to media file (empty = no media)

    Returns:
        JSON with created post data or error
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    if not tweet_text.strip():
        return _safe_json({"error": "tweet_text cannot be empty"})

    conn, err = _get_db_connection()
    if err:
        return err

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        slug = _normalize_slug(album_slug)

        # Resolve album_id
        cur.execute("SELECT id FROM albums WHERE slug = %s", (slug,))
        album_row = cur.fetchone()
        if not album_row:
            return _safe_json({
                "error": f"Album '{album_slug}' not found in database. "
                         "Use db_sync_album to sync it first.",
            })
        album_id = album_row["id"]

        # Resolve track_id if track_number provided
        track_id = None
        if track_number > 0:
            cur.execute(
                "SELECT id FROM tracks WHERE album_id = %s AND track_number = %s",
                (album_id, track_number),
            )
            track_row = cur.fetchone()
            if track_row:
                track_id = track_row["id"]

        cur.execute(
            """INSERT INTO tweets
                   (album_id, track_id, tweet_text, platform, content_type, media_path)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING id, tweet_text, platform, content_type, media_path,
                         posted, enabled, times_posted, created_at""",
            (album_id, track_id, tweet_text, platform.lower(),
             content_type, media_path or None),
        )
        row = cur.fetchone()
        conn.commit()

        return _safe_json({
            "created": True,
            "tweet": {
                "id": row["id"],
                "album_slug": slug,
                "track_number": track_number if track_number > 0 else None,
                "tweet_text": row["tweet_text"],
                "platform": row["platform"],
                "content_type": row["content_type"],
                "media_path": row["media_path"],
                "posted": row["posted"],
                "enabled": row["enabled"],
                "times_posted": row["times_posted"],
                "created_at": row["created_at"],
            },
        })
    except Exception as e:
        conn.rollback()
        return _safe_json({"error": f"Insert failed: {e}"})
    finally:
        conn.close()


async def db_update_tweet(
    tweet_id: int,
    tweet_text: str = "",
    posted: str = "",
    enabled: str = "",
    platform: str = "",
    content_type: str = "",
    media_path: str = "",
    times_posted: int = -1,
) -> str:
    """Update fields on an existing post. Only provided fields are changed.

    When posted is set to "true", posted_at is automatically set to now().

    Args:
        tweet_id: Post ID to update
        tweet_text: New post text (empty = don't change)
        posted: Set posted status ("true" or "false", empty = don't change)
        enabled: Set enabled status ("true" or "false", empty = don't change)
        platform: Change platform (empty = don't change)
        content_type: Change content type (empty = don't change)
        media_path: New media path (empty = don't change)
        times_posted: New times_posted count (-1 = don't change)

    Returns:
        JSON with updated post data or error
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    conn, err = _get_db_connection()
    if err:
        return err

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Build dynamic SET clause
        updates = []
        params = []

        if tweet_text:
            updates.append("tweet_text = %s")
            params.append(tweet_text)
        if posted.lower() in ("true", "false"):
            is_posted = posted.lower() == "true"
            updates.append("posted = %s")
            params.append(is_posted)
            # Auto-set posted_at when marking as posted
            if is_posted:
                updates.append("posted_at = now()")
        if enabled.lower() in ("true", "false"):
            updates.append("enabled = %s")
            params.append(enabled.lower() == "true")
        if platform:
            updates.append("platform = %s")
            params.append(platform.lower())
        if content_type:
            updates.append("content_type = %s")
            params.append(content_type)
        if media_path:
            updates.append("media_path = %s")
            params.append(media_path)
        if times_posted >= 0:
            updates.append("times_posted = %s")
            params.append(times_posted)

        if not updates:
            return _safe_json({"error": "No fields to update"})

        params.append(tweet_id)
        query = f"""
            UPDATE tweets SET {', '.join(updates)}
            WHERE id = %s
            RETURNING id, tweet_text, platform, content_type, media_path,
                      posted, enabled, times_posted, created_at, posted_at
        """  # nosec B608 — column names from hardcoded allowlist, not user input

        cur.execute(query, params)
        row = cur.fetchone()
        if not row:
            return _safe_json({"error": f"Tweet {tweet_id} not found"})

        conn.commit()

        return _safe_json({
            "updated": True,
            "tweet": {
                "id": row["id"],
                "tweet_text": row["tweet_text"],
                "platform": row["platform"],
                "content_type": row["content_type"],
                "media_path": row["media_path"],
                "posted": row["posted"],
                "enabled": row["enabled"],
                "times_posted": row["times_posted"],
                "created_at": row["created_at"],
                "posted_at": row["posted_at"],
            },
        })
    except Exception as e:
        conn.rollback()
        return _safe_json({"error": f"Update failed: {e}"})
    finally:
        conn.close()


async def db_delete_tweet(tweet_id: int) -> str:
    """Delete a tweet by ID.

    Args:
        tweet_id: Tweet ID to delete

    Returns:
        JSON with deletion result or error
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    conn, err = _get_db_connection()
    if err:
        return err

    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tweets WHERE id = %s RETURNING id", (tweet_id,))
        row = cur.fetchone()
        if not row:
            return _safe_json({"error": f"Tweet {tweet_id} not found"})

        conn.commit()
        return _safe_json({"deleted": True, "tweet_id": tweet_id})
    except Exception as e:
        conn.rollback()
        return _safe_json({"error": f"Delete failed: {e}"})
    finally:
        conn.close()


async def db_search_tweets(
    query: str,
    album_slug: str = "",
    platform: str = "",
) -> str:
    """Search post text with optional album and platform filters.

    Uses case-insensitive substring matching.

    Args:
        query: Search text (case-insensitive)
        album_slug: Optional album slug to narrow search
        platform: Optional platform filter ("twitter", "instagram", etc.)

    Returns:
        JSON with matching posts and count
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    if not query.strip():
        return _safe_json({"error": "Search query cannot be empty"})

    conn, err = _get_db_connection()
    if err:
        return err

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        sql = """
            SELECT t.id, t.tweet_text, t.platform, t.content_type,
                   t.posted, t.enabled, t.times_posted,
                   t.created_at, t.posted_at,
                   a.slug as album_slug, a.title as album_title,
                   tr.track_number, tr.title as track_title
            FROM tweets t
            JOIN albums a ON t.album_id = a.id
            LEFT JOIN tracks tr ON t.track_id = tr.id
            WHERE t.tweet_text ILIKE %s
        """
        params = [f"%{query}%"]

        if album_slug:
            sql += " AND a.slug = %s"
            params.append(_normalize_slug(album_slug))

        if platform:
            sql += " AND t.platform = %s"
            params.append(platform.lower())

        sql += " ORDER BY a.slug, t.id"

        cur.execute(sql, params)
        rows = cur.fetchall()

        tweets = []
        for row in rows:
            tweets.append({
                "id": row["id"],
                "tweet_text": row["tweet_text"],
                "platform": row["platform"],
                "content_type": row["content_type"],
                "posted": row["posted"],
                "enabled": row["enabled"],
                "times_posted": row["times_posted"],
                "created_at": row["created_at"],
                "posted_at": row["posted_at"],
                "album_slug": row["album_slug"],
                "album_title": row["album_title"],
                "track_number": row["track_number"],
                "track_title": row["track_title"],
            })

        return _safe_json({"query": query, "tweets": tweets, "count": len(tweets)})
    except Exception as e:
        return _safe_json({"error": f"Search failed: {e}"})
    finally:
        conn.close()


async def db_sync_album(album_slug: str) -> str:
    """Sync an album and its tracks from plugin markdown state to the database.

    Upserts the album row (by slug) and all track rows (by album_id + track_number).
    Uses the MCP state cache as the data source — no extra file reads needed.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with sync result (album upserted, tracks upserted counts)
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    # Get album from plugin state cache
    slug, album_data, err = _find_album_or_error(album_slug)
    if err:
        return err

    conn, conn_err = _get_db_connection()
    if conn_err:
        return conn_err

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Upsert album
        genre = album_data.get("genre", "")
        title = album_data.get("title", slug)
        track_count = album_data.get("track_count", 0)
        explicit = album_data.get("explicit", False)
        release_date = album_data.get("release_date")
        status = album_data.get("status", _shared.STATUS_UNKNOWN)

        # Extract streaming URLs from state cache
        streaming = album_data.get("streaming_urls", {})
        soundcloud_url = streaming.get("soundcloud", "")
        spotify_url = streaming.get("spotify", "")
        apple_music_url = streaming.get("apple_music", "")
        youtube_url = streaming.get("youtube_music", "")
        amazon_music_url = streaming.get("amazon_music", "")

        cur.execute(
            """INSERT INTO albums (slug, title, genre, track_count, explicit,
                                   release_date, status, concept,
                                   soundcloud_url, spotify_url, apple_music_url,
                                   youtube_url, amazon_music_url, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, now())
               ON CONFLICT (slug) DO UPDATE SET
                   title = EXCLUDED.title,
                   genre = EXCLUDED.genre,
                   track_count = EXCLUDED.track_count,
                   explicit = EXCLUDED.explicit,
                   release_date = EXCLUDED.release_date,
                   status = EXCLUDED.status,
                   soundcloud_url = EXCLUDED.soundcloud_url,
                   spotify_url = EXCLUDED.spotify_url,
                   apple_music_url = EXCLUDED.apple_music_url,
                   youtube_url = EXCLUDED.youtube_url,
                   amazon_music_url = EXCLUDED.amazon_music_url,
                   updated_at = now()
               RETURNING id""",
            (slug, title, genre, track_count, explicit, release_date, status, "",
             soundcloud_url, spotify_url, apple_music_url, youtube_url,
             amazon_music_url),
        )
        album_row = cur.fetchone()
        album_id = album_row["id"]

        # Upsert tracks
        tracks = album_data.get("tracks", {})
        tracks_synced = 0
        for track_slug, track_info in tracks.items():
            # Extract track number from slug (e.g., "01-track-name" -> 1)
            parts = track_slug.split("-", 1)
            try:
                track_number = int(parts[0])
            except (ValueError, IndexError):
                continue

            track_title = track_info.get("title", track_slug)

            cur.execute(
                """INSERT INTO tracks (album_id, track_number, slug, title,
                                       concept, updated_at)
                   VALUES (%s, %s, %s, %s, %s, now())
                   ON CONFLICT (album_id, track_number) DO UPDATE SET
                       slug = EXCLUDED.slug,
                       title = EXCLUDED.title,
                       updated_at = now()
                   RETURNING id""",
                (album_id, track_number, track_slug, track_title, ""),
            )
            tracks_synced += 1

        conn.commit()

        return _safe_json({
            "synced": True,
            "album_slug": slug,
            "album_id": album_id,
            "tracks_synced": tracks_synced,
        })
    except Exception as e:
        conn.rollback()
        return _safe_json({"error": f"Sync failed: {e}"})
    finally:
        conn.close()


async def db_get_tweet_stats(album_slug: str = "") -> str:
    """Get tweet counts by status for an album or globally.

    Returns posted/unposted, enabled/disabled breakdowns and total counts.

    Args:
        album_slug: Album slug (empty = global stats across all albums)

    Returns:
        JSON with tweet statistics
    """
    dep_err = _check_db_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    conn, err = _get_db_connection()
    if err:
        return err

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if album_slug:
            slug = _normalize_slug(album_slug)
            cur.execute(
                """SELECT
                       count(*) as total,
                       count(*) FILTER (WHERE t.posted = true) as posted,
                       count(*) FILTER (WHERE t.posted = false) as unposted,
                       count(*) FILTER (WHERE t.enabled = true) as enabled,
                       count(*) FILTER (WHERE t.enabled = false) as disabled,
                       coalesce(sum(t.times_posted), 0) as total_times_posted
                   FROM tweets t
                   JOIN albums a ON t.album_id = a.id
                   WHERE a.slug = %s""",
                (slug,),
            )
        else:
            cur.execute(
                """SELECT
                       count(*) as total,
                       count(*) FILTER (WHERE posted = true) as posted,
                       count(*) FILTER (WHERE posted = false) as unposted,
                       count(*) FILTER (WHERE enabled = true) as enabled,
                       count(*) FILTER (WHERE enabled = false) as disabled,
                       coalesce(sum(times_posted), 0) as total_times_posted
                   FROM tweets"""
            )

        row = cur.fetchone()

        # Per-platform breakdown
        platform_query = """
            SELECT platform, count(*) as count,
                   count(*) FILTER (WHERE posted = true) as posted
            FROM tweets
        """
        platform_params = []
        if album_slug:
            platform_query += " WHERE album_id IN (SELECT id FROM albums WHERE slug = %s)"
            platform_params.append(slug)
        platform_query += " GROUP BY platform ORDER BY platform"

        cur.execute(platform_query, platform_params)
        platforms_breakdown = []
        for prow in cur.fetchall():
            platforms_breakdown.append({
                "platform": prow["platform"],
                "count": prow["count"],
                "posted": prow["posted"],
            })

        # Per-album breakdown if global
        albums_breakdown = []
        if not album_slug:
            cur.execute(
                """SELECT a.slug, a.title, count(*) as tweet_count,
                          count(*) FILTER (WHERE t.posted = true) as posted,
                          count(*) FILTER (WHERE t.enabled = true) as enabled
                   FROM tweets t
                   JOIN albums a ON t.album_id = a.id
                   GROUP BY a.slug, a.title
                   ORDER BY a.slug"""
            )
            for arow in cur.fetchall():
                albums_breakdown.append({
                    "album_slug": arow["slug"],
                    "album_title": arow["title"],
                    "tweet_count": arow["tweet_count"],
                    "posted": arow["posted"],
                    "enabled": arow["enabled"],
                })

        result = {
            "album_slug": album_slug or "(all)",
            "total": row["total"],
            "posted": row["posted"],
            "unposted": row["unposted"],
            "enabled": row["enabled"],
            "disabled": row["disabled"],
            "total_times_posted": row["total_times_posted"],
            "per_platform": platforms_breakdown,
        }

        if albums_breakdown:
            result["per_album"] = albums_breakdown

        return _safe_json(result)
    except Exception as e:
        return _safe_json({"error": f"Stats query failed: {e}"})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(mcp):
    mcp.tool()(db_init)
    mcp.tool()(db_list_tweets)
    mcp.tool()(db_create_tweet)
    mcp.tool()(db_update_tweet)
    mcp.tool()(db_delete_tweet)
    mcp.tool()(db_search_tweets)
    mcp.tool()(db_sync_album)
    mcp.tool()(db_get_tweet_stats)
