#!/usr/bin/env python3
"""
MCP server for bitwize-music state cache.

Provides structured access to album, track, session, and config data
without shelling out to Python or reading JSON files manually.

Transport: stdio

Usage:
    python3 servers/state-server/server.py

Tools exposed:
    find_album          - Find album by name (fuzzy match)
    list_albums         - List all albums with summary
    get_track           - Get single track details
    list_tracks         - Get all tracks for an album (batch query)
    search              - Full-text search across albums/tracks/ideas
    get_session         - Get current session context
    update_session      - Update session context
    rebuild_state       - Force full rebuild
    get_config          - Get resolved config
    get_ideas           - Get ideas with counts
    get_pending_verifications - Get tracks needing verification
"""
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional, Any

# Derive plugin root from environment or file location
# Check CLAUDE_PLUGIN_ROOT first (standard env var), then PLUGIN_ROOT (legacy), then derive from file
PLUGIN_ROOT = Path(
    os.environ.get("CLAUDE_PLUGIN_ROOT") or
    os.environ.get("PLUGIN_ROOT") or
    Path(__file__).resolve().parent.parent.parent
)

# Add plugin root to sys.path for tools.* imports
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

# Configure logging to stderr (critical for stdio transport - never print to stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("bitwize-music-state")

# Try to import MCP SDK
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("=" * 70, file=sys.stderr)
    print("ERROR: MCP SDK not installed", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("", file=sys.stderr)
    print("The bitwize-music MCP server requires the MCP SDK.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Install with ONE of these methods:", file=sys.stderr)
    print("", file=sys.stderr)
    print("  1. User install (recommended):", file=sys.stderr)
    print("     pip install --user 'mcp[cli]>=1.2.0' pyyaml", file=sys.stderr)
    print("", file=sys.stderr)
    print("  2. Using pipx:", file=sys.stderr)
    print("     pipx install mcp", file=sys.stderr)
    print("", file=sys.stderr)
    print("  3. Virtual environment:", file=sys.stderr)
    print("     python3 -m venv ~/.bitwize-music/venv", file=sys.stderr)
    print("     ~/.bitwize-music/venv/bin/pip install 'mcp[cli]>=1.2.0' pyyaml", file=sys.stderr)
    print("", file=sys.stderr)
    print("After installing, restart Claude Code to reload the plugin.", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    sys.exit(1)

# Import from plugin's tools
from tools.state.indexer import (
    build_state,
    incremental_update,
    read_config,
    read_state,
    write_state,
    STATE_FILE,
    CONFIG_FILE,
)

# Initialize FastMCP server
mcp = FastMCP("bitwize-music-mcp")


class StateCache:
    """In-memory cache for state data with lazy loading and staleness detection.

    Thread-safe: all public methods acquire a lock before accessing state.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._state: Optional[dict] = None
        self._state_mtime: float = 0.0
        self._config_mtime: float = 0.0

    def get_state(self) -> dict:
        """Get state, loading from disk if needed or stale."""
        with self._lock:
            if self._is_stale() or self._state is None:
                logger.debug("State cache miss, loading from disk")
                self._load_from_disk()
            return self._state or {}

    def rebuild(self) -> dict:
        """Force full rebuild from markdown files."""
        logger.info("Starting full state rebuild")
        config = read_config()
        if config is None:
            logger.error("Config not found at %s", CONFIG_FILE)
            return {"error": f"Config not found at {CONFIG_FILE}"}

        # Preserve session from existing state
        existing = read_state()
        try:
            state = build_state(config)
        except Exception as e:
            logger.error("State build failed: %s", e)
            return {"error": f"State build failed: {e}"}

        if existing and "session" in existing:
            state["session"] = existing["session"]

        write_state(state)
        with self._lock:
            self._state = state
            self._update_mtimes()

        album_count = len(state.get("albums", {}))
        track_count = sum(
            len(a.get("tracks", {})) for a in state.get("albums", {}).values()
        )
        logger.info(
            "State rebuilt: %d albums, %d tracks", album_count, track_count
        )
        return state

    def update_session(self, **kwargs) -> dict:
        """Update session fields and persist.

        Note: get_state() acquires the lock, so we don't re-acquire here
        to avoid deadlock. Session updates are atomic via write_state's
        file locking.
        """
        from datetime import datetime, timezone

        state = self.get_state()
        if not state:
            logger.warning("Cannot update session: no state available")
            return {"error": "No state available"}
        if "error" in state:
            logger.warning("Cannot update session: state has error")
            return {"error": f"State has error: {state['error']}"}

        session = state.get("session", {})

        if kwargs.get("clear"):
            logger.info("Clearing session data")
            session = {
                "last_album": None,
                "last_track": None,
                "last_phase": None,
                "pending_actions": [],
                "updated_at": None,
            }
        else:
            if kwargs.get("album") is not None:
                session["last_album"] = kwargs["album"]
                logger.debug("Session album set to: %s", kwargs["album"])
            if kwargs.get("track") is not None:
                session["last_track"] = kwargs["track"]
            if kwargs.get("phase") is not None:
                session["last_phase"] = kwargs["phase"]
            if kwargs.get("action"):
                actions = session.get("pending_actions", [])
                actions.append(kwargs["action"])
                session["pending_actions"] = actions

        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["session"] = session
        write_state(state)
        self._state = state
        return session

    def _is_stale(self) -> bool:
        """Check if cached state is stale."""
        try:
            if STATE_FILE.exists():
                current_state_mtime = STATE_FILE.stat().st_mtime
                if current_state_mtime != self._state_mtime:
                    logger.debug("State file mtime changed, cache is stale")
                    return True
            if CONFIG_FILE.exists():
                current_config_mtime = CONFIG_FILE.stat().st_mtime
                if current_config_mtime != self._config_mtime:
                    logger.debug("Config file mtime changed, cache is stale")
                    return True
        except OSError as e:
            logger.debug("Staleness check OSError: %s", e)
            return True
        return False

    def _load_from_disk(self):
        """Load state from disk into memory."""
        self._state = read_state()
        self._update_mtimes()
        if self._state is None:
            logger.warning("No state file found, will need rebuild")
        else:
            album_count = len(self._state.get("albums", {}))
            logger.debug("Loaded state from disk: %d albums", album_count)

    def _update_mtimes(self):
        """Update cached mtime values."""
        try:
            if STATE_FILE.exists():
                self._state_mtime = STATE_FILE.stat().st_mtime
            if CONFIG_FILE.exists():
                self._config_mtime = CONFIG_FILE.stat().st_mtime
        except OSError:
            pass


# Global cache instance
cache = StateCache()


def _normalize_slug(name: str) -> str:
    """Normalize input to slug format."""
    return name.lower().replace(" ", "-").replace("_", "-")


def _safe_json(data: Any) -> str:
    """Serialize data to JSON with error fallback.

    If json.dumps() fails (e.g., circular references, non-serializable types),
    returns a JSON error object instead of crashing.
    """
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError, OverflowError) as e:
        return json.dumps({"error": f"JSON serialization failed: {e}"})


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
async def find_album(name: str) -> str:
    """Find an album by name with fuzzy matching.

    Args:
        name: Album name, slug, or partial match (e.g., "my-album", "my album", "My Album")

    Returns:
        JSON with found album data, or error with available albums
    """
    state = cache.get_state()
    albums = state.get("albums", {})

    if not albums:
        return _safe_json({"found": False, "error": "No albums in state cache"})

    normalized = _normalize_slug(name)

    # Exact match first
    if normalized in albums:
        return _safe_json({
            "found": True,
            "slug": normalized,
            "album": albums[normalized],
        })

    # Fuzzy match: check if input is substring of slug or vice versa
    matches = {
        slug: data
        for slug, data in albums.items()
        if normalized in slug or slug in normalized
    }

    if len(matches) == 1:
        slug = next(iter(matches))
        return _safe_json({
            "found": True,
            "slug": slug,
            "album": matches[slug],
        })
    elif len(matches) > 1:
        return _safe_json({
            "found": False,
            "multiple_matches": list(matches.keys()),
            "error": f"Multiple albums match '{name}': {', '.join(matches.keys())}",
        })
    else:
        return _safe_json({
            "found": False,
            "available_albums": list(albums.keys()),
            "error": f"No album found matching '{name}'",
        })


@mcp.tool()
async def list_albums(status_filter: str = "") -> str:
    """List all albums with summary info.

    Args:
        status_filter: Optional status to filter by (e.g., "In Progress", "Complete", "Released")

    Returns:
        JSON array of album summaries
    """
    state = cache.get_state()
    albums = state.get("albums", {})

    result = []
    for slug, album in albums.items():
        status = album.get("status", "Unknown")

        # Apply filter if provided
        if status_filter and status.lower() != status_filter.lower():
            continue

        result.append({
            "slug": slug,
            "title": album.get("title", slug),
            "genre": album.get("genre", ""),
            "status": status,
            "track_count": album.get("track_count", 0),
            "tracks_completed": album.get("tracks_completed", 0),
        })

    return _safe_json({"albums": result, "count": len(result)})


@mcp.tool()
async def get_track(album_slug: str, track_slug: str) -> str:
    """Get details for a specific track.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug (e.g., "01-track-name")

    Returns:
        JSON with track data or error
    """
    state = cache.get_state()
    albums = state.get("albums", {})

    # Normalize inputs
    album_slug = _normalize_slug(album_slug)
    track_slug = _normalize_slug(track_slug)

    album = albums.get(album_slug)
    if not album:
        return _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    tracks = album.get("tracks", {})
    track = tracks.get(track_slug)
    if not track:
        return _safe_json({
            "found": False,
            "error": f"Track '{track_slug}' not found in album '{album_slug}'",
            "available_tracks": list(tracks.keys()),
        })

    return _safe_json({
        "found": True,
        "album_slug": album_slug,
        "track_slug": track_slug,
        "track": track,
    })


@mcp.tool()
async def list_tracks(album_slug: str) -> str:
    """List all tracks for an album in one call (avoids N+1 queries).

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with all tracks for the album, or error if album not found
    """
    state = cache.get_state()
    albums = state.get("albums", {})

    normalized = _normalize_slug(album_slug)
    album = albums.get(normalized)
    if not album:
        return _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    tracks = album.get("tracks", {})
    track_list = []
    for slug, track in sorted(tracks.items()):
        track_list.append({
            "slug": slug,
            "title": track.get("title", slug),
            "status": track.get("status", "Unknown"),
            "explicit": track.get("explicit", False),
            "has_suno_link": track.get("has_suno_link", False),
            "sources_verified": track.get("sources_verified", "N/A"),
        })

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "album_title": album.get("title", normalized),
        "tracks": track_list,
        "track_count": len(track_list),
    })


@mcp.tool()
async def get_session() -> str:
    """Get current session context.

    Returns:
        JSON with session data (last_album, last_track, last_phase, pending_actions)
    """
    state = cache.get_state()
    session = state.get("session", {})
    return _safe_json({"session": session})


@mcp.tool()
async def update_session(
    album: str = "",
    track: str = "",
    phase: str = "",
    action: str = "",
    clear: bool = False,
) -> str:
    """Update session context.

    Args:
        album: Set last_album (album slug)
        track: Set last_track (track slug)
        phase: Set last_phase (e.g., "Writing", "Generating", "Mastering")
        action: Append a pending action
        clear: Clear all session data before applying updates

    Returns:
        JSON with updated session
    """
    session = cache.update_session(
        album=album or None,
        track=track or None,
        phase=phase or None,
        action=action or None,
        clear=clear,
    )
    return _safe_json({"session": session})


@mcp.tool()
async def rebuild_state() -> str:
    """Force full rebuild of state cache from markdown files.

    Use when state seems stale or after manual file edits.

    Returns:
        JSON with rebuild result summary
    """
    state = cache.rebuild()

    if "error" in state:
        return _safe_json(state)

    album_count = len(state.get("albums", {}))
    track_count = sum(
        len(a.get("tracks", {})) for a in state.get("albums", {}).values()
    )
    ideas_count = len(state.get("ideas", {}).get("items", []))

    return _safe_json({
        "success": True,
        "albums": album_count,
        "tracks": track_count,
        "ideas": ideas_count,
    })


@mcp.tool()
async def get_config() -> str:
    """Get resolved configuration (paths, artist name, settings).

    Returns:
        JSON with config section from state
    """
    state = cache.get_state()
    config = state.get("config", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    return _safe_json({"config": config})


@mcp.tool()
async def get_ideas(status_filter: str = "") -> str:
    """Get album ideas with status counts.

    Args:
        status_filter: Optional status to filter by (e.g., "Pending", "In Progress")

    Returns:
        JSON with ideas counts and items
    """
    state = cache.get_state()
    ideas = state.get("ideas", {})

    counts = ideas.get("counts", {})
    items = ideas.get("items", [])

    if status_filter:
        items = [i for i in items if i.get("status", "").lower() == status_filter.lower()]

    return _safe_json({
        "counts": counts,
        "items": items,
        "total": len(items),
    })


@mcp.tool()
async def search(query: str, scope: str = "all") -> str:
    """Full-text search across albums, tracks, and ideas.

    Args:
        query: Search query (case-insensitive substring match)
        scope: What to search - "albums", "tracks", "ideas", or "all" (default)

    Returns:
        JSON with matching results grouped by type
    """
    state = cache.get_state()
    query_lower = query.lower()
    results: dict = {"query": query, "scope": scope}

    if scope in ("all", "albums"):
        album_matches = []
        for slug, album in state.get("albums", {}).items():
            title = album.get("title", "")
            genre = album.get("genre", "")
            if (query_lower in slug.lower() or
                    query_lower in title.lower() or
                    query_lower in genre.lower()):
                album_matches.append({
                    "slug": slug,
                    "title": title,
                    "genre": genre,
                    "status": album.get("status", "Unknown"),
                })
        results["albums"] = album_matches

    if scope in ("all", "tracks"):
        track_matches = []
        for album_slug, album in state.get("albums", {}).items():
            for track_slug, track in album.get("tracks", {}).items():
                title = track.get("title", "")
                if (query_lower in track_slug.lower() or
                        query_lower in title.lower()):
                    track_matches.append({
                        "album_slug": album_slug,
                        "track_slug": track_slug,
                        "title": title,
                        "status": track.get("status", "Unknown"),
                    })
        results["tracks"] = track_matches

    if scope in ("all", "ideas"):
        idea_matches = []
        for idea in state.get("ideas", {}).get("items", []):
            title = idea.get("title", "")
            genre = idea.get("genre", "")
            if (query_lower in title.lower() or
                    query_lower in genre.lower()):
                idea_matches.append(idea)
        results["ideas"] = idea_matches

    total = sum(len(v) for k, v in results.items() if isinstance(v, list))
    results["total_matches"] = total

    return _safe_json(results)


@mcp.tool()
async def get_pending_verifications() -> str:
    """Get albums and tracks with pending source verification.

    Returns:
        JSON with tracks where sources_verified is 'Pending', grouped by album
    """
    state = cache.get_state()
    albums = state.get("albums", {})

    pending = {}
    for album_slug, album in albums.items():
        tracks = album.get("tracks", {})
        pending_tracks = [
            {"slug": t_slug, "title": t.get("title", t_slug)}
            for t_slug, t in tracks.items()
            if t.get("sources_verified", "").lower() == "pending"
        ]
        if pending_tracks:
            pending[album_slug] = {
                "album_title": album.get("title", album_slug),
                "tracks": pending_tracks,
            }

    return _safe_json({
        "albums_with_pending": pending,
        "total_pending_tracks": sum(len(a["tracks"]) for a in pending.values()),
    })


def main():
    """Start the MCP server."""
    logger.info("Starting bitwize-music-state MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
