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
from pathlib import Path
from typing import Optional

# Derive plugin root from environment or file location
PLUGIN_ROOT = Path(
    os.environ.get("PLUGIN_ROOT", Path(__file__).resolve().parent.parent.parent)
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
    logger.error("MCP SDK not installed. Install with: pip install 'mcp[cli]'")
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
mcp = FastMCP("bitwize-music-state")


class StateCache:
    """In-memory cache for state data with lazy loading and staleness detection."""

    def __init__(self):
        self._state: Optional[dict] = None
        self._state_mtime: float = 0.0
        self._config_mtime: float = 0.0

    def get_state(self) -> dict:
        """Get state, loading from disk if needed or stale."""
        if self._is_stale() or self._state is None:
            self._load_from_disk()
        return self._state or {}

    def rebuild(self) -> dict:
        """Force full rebuild from markdown files."""
        config = read_config()
        if config is None:
            return {"error": f"Config not found at {CONFIG_FILE}"}

        # Preserve session from existing state
        existing = read_state()
        state = build_state(config)
        if existing and "session" in existing:
            state["session"] = existing["session"]

        write_state(state)
        self._state = state
        self._update_mtimes()
        return state

    def update_session(self, **kwargs) -> dict:
        """Update session fields and persist."""
        from datetime import datetime, timezone

        state = self.get_state()
        if not state:
            return {"error": "No state available"}

        session = state.get("session", {})

        if kwargs.get("clear"):
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
                    return True
            if CONFIG_FILE.exists():
                current_config_mtime = CONFIG_FILE.stat().st_mtime
                if current_config_mtime != self._config_mtime:
                    return True
        except OSError:
            return True
        return False

    def _load_from_disk(self):
        """Load state from disk into memory."""
        self._state = read_state()
        self._update_mtimes()
        if self._state is None:
            logger.warning("No state file found, will need rebuild")

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
        return json.dumps({"found": False, "error": "No albums in state cache"})

    normalized = _normalize_slug(name)

    # Exact match first
    if normalized in albums:
        return json.dumps({
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
        return json.dumps({
            "found": True,
            "slug": slug,
            "album": matches[slug],
        })
    elif len(matches) > 1:
        return json.dumps({
            "found": False,
            "multiple_matches": list(matches.keys()),
            "error": f"Multiple albums match '{name}': {', '.join(matches.keys())}",
        })
    else:
        return json.dumps({
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

    return json.dumps({"albums": result, "count": len(result)})


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
        return json.dumps({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    tracks = album.get("tracks", {})
    track = tracks.get(track_slug)
    if not track:
        return json.dumps({
            "found": False,
            "error": f"Track '{track_slug}' not found in album '{album_slug}'",
            "available_tracks": list(tracks.keys()),
        })

    return json.dumps({
        "found": True,
        "album_slug": album_slug,
        "track_slug": track_slug,
        "track": track,
    })


@mcp.tool()
async def get_session() -> str:
    """Get current session context.

    Returns:
        JSON with session data (last_album, last_track, last_phase, pending_actions)
    """
    state = cache.get_state()
    session = state.get("session", {})
    return json.dumps({"session": session})


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
    return json.dumps({"session": session})


@mcp.tool()
async def rebuild_state() -> str:
    """Force full rebuild of state cache from markdown files.

    Use when state seems stale or after manual file edits.

    Returns:
        JSON with rebuild result summary
    """
    state = cache.rebuild()

    if "error" in state:
        return json.dumps(state)

    album_count = len(state.get("albums", {}))
    track_count = sum(
        len(a.get("tracks", {})) for a in state.get("albums", {}).values()
    )
    ideas_count = len(state.get("ideas", {}).get("items", []))

    return json.dumps({
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
        return json.dumps({"error": "No config in state. Run rebuild_state first."})

    return json.dumps({"config": config})


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

    return json.dumps({
        "counts": counts,
        "items": items,
        "total": len(items),
    })


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

    return json.dumps({
        "albums_with_pending": pending,
        "total_pending_tracks": sum(len(a["tracks"]) for a in pending.values()),
    })


def main():
    """Start the MCP server."""
    logger.info("Starting bitwize-music-state MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
