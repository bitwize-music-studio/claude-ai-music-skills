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
    resolve_path        - Resolve content/audio/documents path for an album
    resolve_track_file  - Find a track file path with metadata
    list_track_files    - List track files with status filtering
    extract_section     - Extract a section from a track markdown file
    update_track_field  - Update a metadata field in a track file
"""
import json
import logging
import os
import re
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
from tools.state.parsers import parse_track_file

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


@mcp.tool()
async def resolve_path(path_type: str, album_slug: str, genre: str = "") -> str:
    """Resolve the full filesystem path for an album's content, audio, or documents directory.

    Uses config and state cache to construct the correct mirrored path structure:
        content:   {content_root}/artists/{artist}/albums/{genre}/{album}/
        audio:     {audio_root}/{artist}/{album}/
        documents: {documents_root}/{artist}/{album}/
        tracks:    {content_root}/artists/{artist}/albums/{genre}/{album}/tracks/
        overrides: {overrides_path} or {content_root}/overrides/

    Args:
        path_type: One of "content", "audio", "documents", "tracks", "overrides"
        album_slug: Album slug (e.g., "my-album"). Ignored for "overrides".
        genre: Genre slug. Required for "content" and "tracks". If omitted, looked up from state cache.

    Returns:
        JSON with resolved path or error
    """
    if path_type not in ("content", "audio", "documents", "tracks", "overrides"):
        return _safe_json({
            "error": f"Invalid path_type '{path_type}'. Must be 'content', 'audio', 'documents', 'tracks', or 'overrides'.",
        })

    state = cache.get_state()
    config = state.get("config", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    # Overrides doesn't need album info
    if path_type == "overrides":
        overrides = config.get("overrides_dir", "")
        if overrides:
            return _safe_json({"path": overrides, "path_type": path_type})
        content_root = config.get("content_root", "")
        return _safe_json({
            "path": str(Path(content_root) / "overrides"),
            "path_type": path_type,
        })

    artist = config.get("artist_name", "")
    if not artist:
        return _safe_json({"error": "No artist_name in config."})

    normalized = _normalize_slug(album_slug)

    # For content/tracks, we need genre — try state cache if not provided
    if path_type in ("content", "tracks") and not genre:
        albums = state.get("albums", {})
        album_data = albums.get(normalized, {})
        genre = album_data.get("genre", "")
        if not genre:
            return _safe_json({
                "error": f"Genre required for '{path_type}' path. Provide genre parameter or ensure album '{album_slug}' exists in state.",
            })

    content_root = config.get("content_root", "")
    audio_root = config.get("audio_root", "")
    documents_root = config.get("documents_root", "")

    if path_type == "content":
        resolved = str(Path(content_root) / "artists" / artist / "albums" / genre / normalized)
    elif path_type == "tracks":
        resolved = str(Path(content_root) / "artists" / artist / "albums" / genre / normalized / "tracks")
    elif path_type == "audio":
        resolved = str(Path(audio_root) / artist / normalized)
    else:  # documents
        resolved = str(Path(documents_root) / artist / normalized)

    return _safe_json({
        "path": resolved,
        "path_type": path_type,
        "album_slug": normalized,
        "genre": genre,
    })


@mcp.tool()
async def resolve_track_file(album_slug: str, track_slug: str) -> str:
    """Find a track's file path and return its full metadata from state cache.

    More complete than get_track — includes the resolved file path and album context.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")

    Returns:
        JSON with track path, metadata, and album context
    """
    state = cache.get_state()
    albums = state.get("albums", {})

    normalized_album = _normalize_slug(album_slug)
    album = albums.get(normalized_album)
    if not album:
        return _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    tracks = album.get("tracks", {})
    normalized_track = _normalize_slug(track_slug)

    # Exact match first
    if normalized_track in tracks:
        track = tracks[normalized_track]
        return _safe_json({
            "found": True,
            "album_slug": normalized_album,
            "track_slug": normalized_track,
            "path": track.get("path", ""),
            "album_path": album.get("path", ""),
            "genre": album.get("genre", ""),
            "track": track,
        })

    # Prefix match — allow "01" to match "01-track-name"
    prefix_matches = {
        slug: data for slug, data in tracks.items()
        if slug.startswith(normalized_track)
    }

    if len(prefix_matches) == 1:
        slug = next(iter(prefix_matches))
        track = prefix_matches[slug]
        return _safe_json({
            "found": True,
            "album_slug": normalized_album,
            "track_slug": slug,
            "path": track.get("path", ""),
            "album_path": album.get("path", ""),
            "genre": album.get("genre", ""),
            "track": track,
        })
    elif len(prefix_matches) > 1:
        return _safe_json({
            "found": False,
            "error": f"Multiple tracks match '{track_slug}': {', '.join(prefix_matches.keys())}",
            "matches": list(prefix_matches.keys()),
        })

    return _safe_json({
        "found": False,
        "error": f"Track '{track_slug}' not found in album '{album_slug}'",
        "available_tracks": list(tracks.keys()),
    })


@mcp.tool()
async def list_track_files(album_slug: str, status_filter: str = "") -> str:
    """List all tracks for an album with file paths and optional status filtering.

    Unlike list_tracks, includes file paths and supports filtering by status.

    Args:
        album_slug: Album slug (e.g., "my-album")
        status_filter: Optional status filter (e.g., "Not Started", "In Progress", "Generated", "Final")

    Returns:
        JSON with track list including paths, or error if album not found
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
        status = track.get("status", "Unknown")

        if status_filter and status.lower() != status_filter.lower():
            continue

        track_list.append({
            "slug": slug,
            "title": track.get("title", slug),
            "status": status,
            "path": track.get("path", ""),
            "explicit": track.get("explicit", False),
            "has_suno_link": track.get("has_suno_link", False),
            "sources_verified": track.get("sources_verified", "N/A"),
        })

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "album_title": album.get("title", normalized),
        "album_path": album.get("path", ""),
        "genre": album.get("genre", ""),
        "tracks": track_list,
        "track_count": len(track_list),
        "total_tracks": len(tracks),
    })


# Pre-compiled patterns for section extraction
_RE_SECTION = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
_RE_CODE_BLOCK = re.compile(r'```\n?(.*?)```', re.DOTALL)

# Map user-friendly section names to markdown headings
_SECTION_NAMES = {
    "style": "Style Box",
    "style-box": "Style Box",
    "lyrics": "Lyrics Box",
    "lyrics-box": "Lyrics Box",
    "streaming": "Streaming Lyrics",
    "streaming-lyrics": "Streaming Lyrics",
    "pronunciation": "Pronunciation Notes",
    "pronunciation-notes": "Pronunciation Notes",
    "concept": "Concept",
    "source": "Source",
    "original-quote": "Original Quote",
    "musical-direction": "Musical Direction",
    "production-notes": "Production Notes",
    "generation-log": "Generation Log",
    "phonetic-review": "Phonetic Review Checklist",
}

# Fields that can be updated in the track details table
_UPDATABLE_FIELDS = {
    "status": "Status",
    "explicit": "Explicit",
    "suno-link": "Suno Link",
    "suno_link": "Suno Link",
    "sources-verified": "Sources Verified",
    "sources_verified": "Sources Verified",
    "stems": "Stems",
    "pov": "POV",
}


def _extract_markdown_section(text: str, heading: str) -> Optional[str]:
    """Extract content under a specific markdown heading.

    Returns the text between the target heading and the next heading
    of equal or higher level, or end of file.
    """
    matches = list(_RE_SECTION.finditer(text))
    target_idx = None
    target_level = None

    for i, m in enumerate(matches):
        level = len(m.group(1))  # number of # chars
        title = m.group(2).strip()
        if title.lower() == heading.lower():
            target_idx = i
            target_level = level
            break

    if target_idx is None:
        return None

    start = matches[target_idx].end()

    # Find next heading at same or higher level
    for m in matches[target_idx + 1:]:
        level = len(m.group(1))
        if level <= target_level:
            end = m.start()
            return text[start:end].strip()

    # No next heading — return rest of file
    return text[start:].strip()


def _extract_code_block(section_text: str) -> Optional[str]:
    """Extract the first code block from section text."""
    match = _RE_CODE_BLOCK.search(section_text)
    if match:
        return match.group(1).strip()
    return None


@mcp.tool()
async def extract_section(album_slug: str, track_slug: str, section: str) -> str:
    """Extract a specific section from a track's markdown file.

    Reads the track file from disk and returns the content under the
    specified heading. For sections with code blocks (lyrics, style, streaming),
    returns just the code block content.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        section: Section to extract. Options:
            "style" or "style-box" — Suno style prompt
            "lyrics" or "lyrics-box" — Suno lyrics
            "streaming" or "streaming-lyrics" — Streaming platform lyrics
            "pronunciation" or "pronunciation-notes" — Pronunciation table
            "concept" — Track concept description
            "source" — Source material
            "original-quote" — Original quote text
            "musical-direction" — Tempo, feel, instrumentation
            "production-notes" — Technical production notes
            "generation-log" — Generation attempt history
            "phonetic-review" — Phonetic review checklist

    Returns:
        JSON with section content or error
    """
    # Resolve the heading name
    section_key = section.lower().strip()
    heading = _SECTION_NAMES.get(section_key)
    if not heading:
        return _safe_json({
            "error": f"Unknown section '{section}'. Valid options: {', '.join(sorted(_SECTION_NAMES.keys()))}",
        })

    # Find the track file path via state cache
    state = cache.get_state()
    albums = state.get("albums", {})
    normalized_album = _normalize_slug(album_slug)
    album = albums.get(normalized_album)

    if not album:
        return _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    tracks = album.get("tracks", {})
    normalized_track = _normalize_slug(track_slug)

    # Exact or prefix match
    track_data = tracks.get(normalized_track)
    matched_slug = normalized_track
    if not track_data:
        prefix_matches = {s: d for s, d in tracks.items() if s.startswith(normalized_track)}
        if len(prefix_matches) == 1:
            matched_slug = next(iter(prefix_matches))
            track_data = prefix_matches[matched_slug]
        elif len(prefix_matches) > 1:
            return _safe_json({
                "found": False,
                "error": f"Multiple tracks match '{track_slug}': {', '.join(prefix_matches.keys())}",
            })
        else:
            return _safe_json({
                "found": False,
                "error": f"Track '{track_slug}' not found in album '{album_slug}'",
                "available_tracks": list(tracks.keys()),
            })

    track_path = track_data.get("path", "")
    if not track_path:
        return _safe_json({"error": f"No path stored for track '{matched_slug}'"})

    # Read the file
    path = Path(track_path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track file: {e}"})

    # Extract the section
    content = _extract_markdown_section(text, heading)
    if content is None:
        return _safe_json({
            "found": False,
            "error": f"Section '{heading}' not found in track file",
            "track_slug": matched_slug,
        })

    # For code-block sections, extract just the code block
    code_block_sections = {"Style Box", "Lyrics Box", "Streaming Lyrics", "Original Quote"}
    code_content = None
    if heading in code_block_sections:
        code_content = _extract_code_block(content)

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "track_slug": matched_slug,
        "section": heading,
        "content": code_content if code_content is not None else content,
        "raw_content": content if code_content is not None else None,
    })


# Pre-compiled pattern for table field updates
_RE_TABLE_ROW = None  # built dynamically per field


@mcp.tool()
async def update_track_field(
    album_slug: str,
    track_slug: str,
    field: str,
    value: str,
) -> str:
    """Update a metadata field in a track's markdown file.

    Modifies the track's details table (| **Key** | Value |) and rebuilds
    the state cache to reflect the change.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        field: Field to update. Options:
            "status" — Track status (Not Started, In Progress, Generated, Final)
            "explicit" — Explicit flag (Yes, No)
            "suno-link" or "suno_link" — Suno generation link
            "sources-verified" or "sources_verified" — Verification status
            "stems" — Stems available (Yes, No)
            "pov" — Point of view
        value: New value for the field

    Returns:
        JSON with update result or error
    """
    # Validate field
    field_key = field.lower().strip()
    table_key = _UPDATABLE_FIELDS.get(field_key)
    if not table_key:
        return _safe_json({
            "error": f"Unknown field '{field}'. Valid options: {', '.join(sorted(_UPDATABLE_FIELDS.keys()))}",
        })

    # Find track path via state cache
    state = cache.get_state()
    albums = state.get("albums", {})
    normalized_album = _normalize_slug(album_slug)
    album = albums.get(normalized_album)

    if not album:
        return _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
        })

    tracks = album.get("tracks", {})
    normalized_track = _normalize_slug(track_slug)

    # Exact or prefix match
    track_data = tracks.get(normalized_track)
    matched_slug = normalized_track
    if not track_data:
        prefix_matches = {s: d for s, d in tracks.items() if s.startswith(normalized_track)}
        if len(prefix_matches) == 1:
            matched_slug = next(iter(prefix_matches))
            track_data = prefix_matches[matched_slug]
        elif len(prefix_matches) > 1:
            return _safe_json({
                "found": False,
                "error": f"Multiple tracks match '{track_slug}': {', '.join(prefix_matches.keys())}",
            })
        else:
            return _safe_json({
                "found": False,
                "error": f"Track '{track_slug}' not found in album '{album_slug}'",
            })

    track_path = track_data.get("path", "")
    if not track_path:
        return _safe_json({"error": f"No path stored for track '{matched_slug}'"})

    # Read the file
    path = Path(track_path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track file: {e}"})

    # Find and replace the table row: | **Key** | old_value |
    pattern = re.compile(
        r'^(\|\s*\*\*' + re.escape(table_key) + r'\*\*\s*\|)\s*.*?\s*\|',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return _safe_json({
            "error": f"Field '{table_key}' not found in track file table",
            "track_slug": matched_slug,
        })

    old_value = text[match.start():match.end()]
    new_row = f"{match.group(1)} {value} |"
    updated_text = text[:match.start()] + new_row + text[match.end():]

    # Write back
    try:
        path.write_text(updated_text, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write track file: {e}"})

    logger.info("Updated %s.%s field '%s' to '%s'", normalized_album, matched_slug, table_key, value)

    # Re-parse the track to get updated metadata
    parsed = parse_track_file(path)

    # Update state cache in memory
    if matched_slug in tracks:
        tracks[matched_slug].update({
            "status": parsed.get("status", tracks[matched_slug].get("status")),
            "explicit": parsed.get("explicit", tracks[matched_slug].get("explicit")),
            "has_suno_link": parsed.get("has_suno_link", tracks[matched_slug].get("has_suno_link")),
            "sources_verified": parsed.get("sources_verified", tracks[matched_slug].get("sources_verified")),
            "mtime": path.stat().st_mtime,
        })
        write_state(state)

    return _safe_json({
        "success": True,
        "album_slug": normalized_album,
        "track_slug": matched_slug,
        "field": table_key,
        "value": value,
        "track": parsed,
    })


def main():
    """Start the MCP server."""
    logger.info("Starting bitwize-music-state MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
