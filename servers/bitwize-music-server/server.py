#!/usr/bin/env python3
"""
MCP server for bitwize-music plugin.

Provides structured access to albums, tracks, sessions, config, paths,
and track content without shelling out to Python or reading files manually.

Transport: stdio

Usage:
    python3 servers/bitwize-music-server/server.py

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
    get_album_progress  - Get album progress breakdown with phase detection
    load_override       - Load user override file by name
    get_reference       - Read plugin reference file
    format_for_clipboard - Extract and format track content for clipboard
    check_homographs    - Scan text for homograph pronunciation risks
    scan_artist_names   - Check text against artist name blocklist
    check_pronunciation_enforcement - Verify pronunciation notes applied in lyrics
    get_album_full      - Combined album + track sections query
    validate_album_structure - Structural validation of album directories
    create_album_structure - Create album directory with templates
    run_pre_generation_gates - Run all 6 pre-generation validation gates
"""
import json
import logging
import os
import re
import shutil
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

    Auto-rebuilds state cache if empty or missing, so callers never need
    fallback glob logic.

    Args:
        name: Album name, slug, or partial match (e.g., "my-album", "my album", "My Album")

    Returns:
        JSON with found album data, or error with available albums
    """
    state = cache.get_state()
    albums = state.get("albums", {})

    # Auto-rebuild if state is empty or missing albums
    if not albums:
        logger.info("find_album: no albums in cache, attempting auto-rebuild")
        rebuilt = cache.rebuild()
        if "error" not in rebuilt:
            state = rebuilt
            albums = state.get("albums", {})
        if not albums:
            return _safe_json({
                "found": False,
                "error": "No albums found (state rebuilt but still empty)",
                "rebuilt": True,
            })

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


# Phase detection logic matching resume skill's decision tree
_PHASE_RULES = [
    # (condition_fn, phase_name)
    # Evaluated top-to-bottom, first match wins
]


def _detect_phase(album: dict) -> str:
    """Detect the current workflow phase for an album.

    Matches the decision tree from the resume skill.
    """
    status = album.get("status", "Unknown")
    tracks = album.get("tracks", {})

    if status == "Released":
        return "Released"
    if status == "Complete":
        return "Ready to Release"

    track_statuses = [t.get("status", "Unknown") for t in tracks.values()]
    sources = [t.get("sources_verified", "N/A") for t in tracks.values()]

    if status == "Concept" or not track_statuses:
        return "Planning"

    # Count by status
    not_started = sum(1 for s in track_statuses if s == "Not Started")
    in_progress = sum(1 for s in track_statuses if s == "In Progress")
    generated = sum(1 for s in track_statuses if s == "Generated")
    final = sum(1 for s in track_statuses if s == "Final")
    total = len(track_statuses)
    sources_pending = sum(1 for s in sources if s.lower() == "pending")

    if sources_pending > 0:
        return "Source Verification"
    if not_started > 0 or in_progress > 0:
        return "Writing"
    if generated == 0 and final == 0:
        return "Ready to Generate"
    if generated > 0 and (generated + final) < total:
        return "Generating"
    if generated > 0 and final == 0:
        return "Mastering"
    if final == total:
        return "Ready to Release"

    return "In Progress"


@mcp.tool()
async def get_album_progress(album_slug: str) -> str:
    """Get album progress breakdown with completion stats and phase detection.

    Provides a single-call summary of album state: track counts by status,
    completion percentage, and detected workflow phase. Eliminates duplicate
    progress calculation in album-dashboard and resume skills.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with progress data or error
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
    track_count = len(tracks)

    # Count by status
    status_counts = {}
    for track in tracks.values():
        s = track.get("status", "Unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    completed_statuses = {"Final", "Generated"}
    tracks_completed = sum(
        count for s, count in status_counts.items() if s in completed_statuses
    )

    completion_pct = round((tracks_completed / track_count * 100), 1) if track_count > 0 else 0.0

    # Detect phase
    phase = _detect_phase(album)

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "album_title": album.get("title", normalized),
        "album_status": album.get("status", "Unknown"),
        "genre": album.get("genre", ""),
        "phase": phase,
        "track_count": track_count,
        "tracks_completed": tracks_completed,
        "completion_percentage": completion_pct,
        "tracks_by_status": status_counts,
        "sources_pending": sum(
            1 for t in tracks.values()
            if t.get("sources_verified", "").lower() == "pending"
        ),
    })


# =============================================================================
# Content & Override Tools
# =============================================================================


@mcp.tool()
async def load_override(override_name: str) -> str:
    """Load a user override file by name from the overrides directory.

    Override files customize skill behavior per-user. This tool resolves the
    overrides directory from config and reads the named file if it exists.

    Args:
        override_name: Override filename (e.g., "pronunciation-guide.md",
                       "lyric-writing-guide.md", "CLAUDE.md",
                       "suno-preferences.md", "mastering-presets.yaml")

    Returns:
        JSON with {found: bool, content: str, path: str} or {found: false}
    """
    state = cache.get_state()
    config = state.get("config", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    # Resolve overrides directory
    overrides_dir = config.get("overrides_dir", "")
    if not overrides_dir:
        content_root = config.get("content_root", "")
        overrides_dir = str(Path(content_root) / "overrides")

    override_path = Path(overrides_dir) / override_name
    if not override_path.exists():
        return _safe_json({
            "found": False,
            "override_name": override_name,
            "overrides_dir": overrides_dir,
        })

    try:
        content = override_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read override file: {e}"})

    return _safe_json({
        "found": True,
        "override_name": override_name,
        "path": str(override_path),
        "content": content,
        "size": len(content),
    })


@mcp.tool()
async def get_reference(name: str, section: str = "") -> str:
    """Read a plugin reference file with optional section extraction.

    Reference files contain shared knowledge (pronunciation guide, artist
    blocklist, genre list, etc.). This keeps large reference files out of
    the LLM context when only a section is needed.

    Args:
        name: Reference path relative to plugin root's reference/ directory
              (e.g., "suno/pronunciation-guide", "suno/artist-blocklist",
               "suno/genre-list", "suno/v5-best-practices")
              Extension .md is added automatically if missing.
        section: Optional heading to extract (returns full file if empty)

    Returns:
        JSON with {content: str, path: str, section?: str}
    """
    # Normalize name
    ref_name = name.strip()
    if not ref_name.endswith(".md"):
        ref_name += ".md"

    ref_path = PLUGIN_ROOT / "reference" / ref_name
    if not ref_path.exists():
        return _safe_json({
            "error": f"Reference file not found: reference/{ref_name}",
            "path": str(ref_path),
        })

    try:
        content = ref_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read reference file: {e}"})

    # Extract section if requested
    if section:
        extracted = _extract_markdown_section(content, section)
        if extracted is None:
            return _safe_json({
                "error": f"Section '{section}' not found in reference/{ref_name}",
                "path": str(ref_path),
            })
        return _safe_json({
            "found": True,
            "path": str(ref_path),
            "section": section,
            "content": extracted,
        })

    return _safe_json({
        "found": True,
        "path": str(ref_path),
        "content": content,
        "size": len(content),
    })


@mcp.tool()
async def format_for_clipboard(
    album_slug: str,
    track_slug: str,
    content_type: str,
) -> str:
    """Extract and format track content ready for clipboard copy.

    Combines find-track + extract-section + format into one call.
    The skill still handles the actual clipboard command (pbcopy/xclip).

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        content_type: What to extract:
            "lyrics" — Suno Lyrics Box content
            "style" — Suno Style Box content
            "streaming" or "streaming-lyrics" — Streaming platform lyrics
            "all" — Style Box + separator + Lyrics Box

    Returns:
        JSON with {content: str, content_type: str, track_slug: str}
    """
    valid_types = {"lyrics", "style", "streaming", "streaming-lyrics", "all"}
    if content_type not in valid_types:
        return _safe_json({
            "error": f"Invalid content_type '{content_type}'. Options: {', '.join(sorted(valid_types))}",
        })

    # Resolve track file
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

    try:
        text = Path(track_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track file: {e}"})

    def _get_section_content(heading_name):
        """Extract code block content from a section."""
        section_text = _extract_markdown_section(text, heading_name)
        if section_text is None:
            return None
        code = _extract_code_block(section_text)
        return code if code is not None else section_text

    if content_type == "style":
        content = _get_section_content("Style Box")
    elif content_type == "lyrics":
        content = _get_section_content("Lyrics Box")
    elif content_type in ("streaming", "streaming-lyrics"):
        content = _get_section_content("Streaming Lyrics")
    elif content_type == "all":
        style = _get_section_content("Style Box")
        lyrics = _get_section_content("Lyrics Box")
        if style is None and lyrics is None:
            content = None
        else:
            parts = []
            if style:
                parts.append(style)
            if lyrics:
                parts.append(lyrics)
            content = "\n\n---\n\n".join(parts)
    else:
        content = None

    if content is None:
        return _safe_json({
            "found": False,
            "error": f"Content type '{content_type}' not found in track",
            "track_slug": matched_slug,
        })

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "track_slug": matched_slug,
        "content_type": content_type,
        "content": content,
    })


# =============================================================================
# Text Analysis Tools
# =============================================================================

# High-risk homographs that always require user clarification.
# Loaded from the pronunciation guide but kept as a compiled set for fast scanning.
_HIGH_RISK_HOMOGRAPHS = {
    "live": [
        {"pron_a": "LIV (live performance)", "pron_b": "LYVE (alive, living)"},
    ],
    "read": [
        {"pron_a": "REED (present tense)", "pron_b": "RED (past tense)"},
    ],
    "lead": [
        {"pron_a": "LEED (guide)", "pron_b": "LED (the metal)"},
    ],
    "wind": [
        {"pron_a": "WIND (breeze)", "pron_b": "WYND (turn, coil)"},
    ],
    "close": [
        {"pron_a": "KLOHS (near)", "pron_b": "KLOHZ (shut)"},
    ],
    "tear": [
        {"pron_a": "TEER (from crying)", "pron_b": "TAIR (rip)"},
    ],
    "bow": [
        {"pron_a": "BOH (ribbon, weapon)", "pron_b": "BOW (bend, ship front)"},
    ],
    "bass": [
        {"pron_a": "BAYSS (instrument)", "pron_b": "BASS (the fish)"},
    ],
    "row": [
        {"pron_a": "ROH (line, propel boat)", "pron_b": "ROW (argument)"},
    ],
    "sow": [
        {"pron_a": "SOH (plant seeds)", "pron_b": "SOW (female pig)"},
    ],
    "wound": [
        {"pron_a": "WOOND (injury)", "pron_b": "WOWND (coiled)"},
    ],
    "minute": [
        {"pron_a": "MIN-it (60 seconds)", "pron_b": "my-NOOT (tiny)"},
    ],
    "resume": [
        {"pron_a": "ri-ZOOM (continue)", "pron_b": "REZ-oo-may (CV)"},
    ],
    "object": [
        {"pron_a": "OB-jekt (thing)", "pron_b": "ob-JEKT (protest)"},
    ],
    "project": [
        {"pron_a": "PROJ-ekt (plan)", "pron_b": "pro-JEKT (throw)"},
    ],
    "record": [
        {"pron_a": "REK-ord (noun)", "pron_b": "ri-KORD (verb)"},
    ],
    "present": [
        {"pron_a": "PREZ-ent (gift, here)", "pron_b": "pri-ZENT (give)"},
    ],
    "content": [
        {"pron_a": "KON-tent (stuff)", "pron_b": "kon-TENT (satisfied)"},
    ],
    "desert": [
        {"pron_a": "DEZ-ert (sandy place)", "pron_b": "di-ZURT (abandon)"},
    ],
    "refuse": [
        {"pron_a": "REF-yoos (garbage)", "pron_b": "ri-FYOOZ (decline)"},
    ],
}

# Pre-compiled word boundary patterns for homograph scanning
_HOMOGRAPH_PATTERNS = {
    word: re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
    for word in _HIGH_RISK_HOMOGRAPHS
}


@mcp.tool()
async def check_homographs(text: str) -> str:
    """Scan text for homograph words that Suno cannot disambiguate.

    Checks against the high-risk homograph list from the pronunciation guide.
    Returns found words with line numbers and pronunciation options.

    Args:
        text: Lyrics text to scan

    Returns:
        JSON with {found: [{word, line, line_number, options}], count: int}
    """
    if not text.strip():
        return _safe_json({"found": [], "count": 0})

    results = []
    lines = text.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Skip section tags like [Verse 1], [Chorus], etc.
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            continue

        for word, pattern in _HOMOGRAPH_PATTERNS.items():
            for match in pattern.finditer(line):
                results.append({
                    "word": match.group(0),
                    "canonical": word,
                    "line": stripped,
                    "line_number": line_num,
                    "column": match.start(),
                    "options": _HIGH_RISK_HOMOGRAPHS[word],
                })

    return _safe_json({"found": results, "count": len(results)})


# Artist blocklist cache — loaded lazily from reference file
_artist_blocklist_cache: Optional[list] = None
_artist_blocklist_lock = threading.Lock()


def _load_artist_blocklist() -> list:
    """Load and parse the artist blocklist from the reference file.

    Returns a list of dicts: [{name: str, alternative: str, genre: str}]
    """
    global _artist_blocklist_cache
    with _artist_blocklist_lock:
        if _artist_blocklist_cache is not None:
            return _artist_blocklist_cache

        blocklist_path = PLUGIN_ROOT / "reference" / "suno" / "artist-blocklist.md"
        entries = []

        if not blocklist_path.exists():
            logger.warning("Artist blocklist not found at %s", blocklist_path)
            _artist_blocklist_cache = entries
            return entries

        try:
            text = blocklist_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.error("Cannot read artist blocklist: %s", e)
            _artist_blocklist_cache = entries
            return entries

        current_genre = ""
        # Parse table rows: | Don't Say | Say Instead |
        for line in text.split("\n"):
            # Detect genre headings
            heading_match = re.match(r'^###\s+(.+)', line)
            if heading_match:
                current_genre = heading_match.group(1).strip()
                continue

            # Parse table rows (skip header/separator rows)
            if line.startswith("|") and "---" not in line and "Don't Say" not in line:
                parts = [p.strip() for p in line.split("|")]
                # parts[0] is empty (before first |), parts[-1] is empty (after last |)
                if len(parts) >= 4:
                    name = parts[1].strip()
                    alternative = parts[2].strip()
                    if name and name != "Don't Say":
                        entries.append({
                            "name": name,
                            "alternative": alternative,
                            "genre": current_genre,
                        })

        _artist_blocklist_cache = entries
        logger.info("Loaded artist blocklist: %d entries", len(entries))
        return entries


@mcp.tool()
async def scan_artist_names(text: str) -> str:
    """Scan text for real artist/band names from the blocklist.

    Checks style prompts or lyrics against the artist blocklist. Found names
    should be replaced with sonic descriptions.

    Args:
        text: Style prompt or lyrics to scan

    Returns:
        JSON with {clean: bool, found: [{name, alternative, genre}], count: int}
    """
    if not text.strip():
        return _safe_json({"clean": True, "found": [], "count": 0})

    blocklist = _load_artist_blocklist()
    text_lower = text.lower()
    found = []

    for entry in blocklist:
        name = entry["name"]
        # Case-insensitive whole-word search
        pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
        if pattern.search(text_lower):
            found.append({
                "name": name,
                "alternative": entry["alternative"],
                "genre": entry["genre"],
            })

    return _safe_json({
        "clean": len(found) == 0,
        "found": found,
        "count": len(found),
    })


@mcp.tool()
async def check_pronunciation_enforcement(
    album_slug: str,
    track_slug: str,
) -> str:
    """Verify that all Pronunciation Notes entries are applied in the Suno lyrics.

    Reads the track's Pronunciation Notes table and Lyrics Box, then checks
    that each phonetic entry appears in the lyrics.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")

    Returns:
        JSON with {entries: [{word, phonetic, applied, occurrences}],
                   all_applied: bool, unapplied_count: int}
    """
    # Resolve track file
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

    try:
        text = Path(track_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track file: {e}"})

    # Extract Pronunciation Notes table
    pron_section = _extract_markdown_section(text, "Pronunciation Notes")
    if pron_section is None:
        return _safe_json({
            "found": True,
            "track_slug": matched_slug,
            "entries": [],
            "all_applied": True,
            "unapplied_count": 0,
            "note": "No Pronunciation Notes section found",
        })

    # Parse the pronunciation table: | Word/Phrase | Pronunciation | Reason |
    entries = []
    for line in pron_section.split("\n"):
        if not line.startswith("|") or "---" in line or "Word" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            word = parts[1].strip()
            phonetic = parts[2].strip()
            if word and word != "—" and phonetic and phonetic != "—":
                entries.append({"word": word, "phonetic": phonetic})

    if not entries:
        return _safe_json({
            "found": True,
            "track_slug": matched_slug,
            "entries": [],
            "all_applied": True,
            "unapplied_count": 0,
            "note": "Pronunciation table is empty",
        })

    # Extract Lyrics Box content
    lyrics_section = _extract_markdown_section(text, "Lyrics Box")
    lyrics_content = ""
    if lyrics_section:
        code = _extract_code_block(lyrics_section)
        lyrics_content = code if code else lyrics_section

    # Check each pronunciation entry
    results = []
    unapplied = 0
    for entry in entries:
        phonetic = entry["phonetic"]
        # Check if the phonetic version appears in lyrics (case-insensitive)
        occurrences = len(re.findall(
            re.escape(phonetic), lyrics_content, re.IGNORECASE
        ))
        applied = occurrences > 0
        if not applied:
            unapplied += 1
        results.append({
            "word": entry["word"],
            "phonetic": phonetic,
            "applied": applied,
            "occurrences": occurrences,
        })

    return _safe_json({
        "found": True,
        "track_slug": matched_slug,
        "entries": results,
        "all_applied": unapplied == 0,
        "unapplied_count": unapplied,
    })


# --- Explicit content scanning ---

# Base explicit words from explicit-checker skill.  Override via
# {overrides}/explicit-words.md (sections: "Additional Explicit Words",
# "Not Explicit (Override Base)").
_BASE_EXPLICIT_WORDS = {
    "fuck", "fucking", "fucked", "fucker", "motherfuck", "motherfucker",
    "shit", "shitting", "shitty", "bullshit",
    "bitch", "bitches",
    "cunt", "cock", "cocks",
    "dick", "dicks",
    "pussy", "pussies",
    "asshole", "assholes",
    "whore", "slut",
    "goddamn", "goddammit",
}

_explicit_word_cache: Optional[set] = None
_explicit_word_lock = threading.Lock()


def _load_explicit_words() -> set:
    """Load the explicit word set, merging base list with user overrides."""
    global _explicit_word_cache
    with _explicit_word_lock:
        if _explicit_word_cache is not None:
            return _explicit_word_cache

        words = set(_BASE_EXPLICIT_WORDS)

        # Try loading user overrides
        try:
            state = cache.get_state()
            config = state.get("config", {})
            overrides_dir = config.get("overrides_dir", "")
            if not overrides_dir:
                content_root = config.get("content_root", "")
                overrides_dir = str(Path(content_root) / "overrides")

            override_path = Path(overrides_dir) / "explicit-words.md"
            if override_path.exists():
                text = override_path.read_text(encoding="utf-8")

                # Parse "Additional Explicit Words" section
                add_section = _extract_markdown_section(text, "Additional Explicit Words")
                if add_section:
                    for line in add_section.split("\n"):
                        line = line.strip()
                        if line.startswith("- ") and line[2:].strip():
                            word = line[2:].split("(")[0].strip().lower()
                            if word:
                                words.add(word)

                # Parse "Not Explicit (Override Base)" section
                remove_section = _extract_markdown_section(text, "Not Explicit (Override Base)")
                if remove_section:
                    for line in remove_section.split("\n"):
                        line = line.strip()
                        if line.startswith("- ") and line[2:].strip():
                            word = line[2:].split("(")[0].strip().lower()
                            words.discard(word)
        except Exception:
            pass  # Fall back to base list

        _explicit_word_cache = words
        return words


@mcp.tool()
async def check_explicit_content(text: str) -> str:
    """Scan lyrics for explicit/profane words.

    Uses the base explicit word list merged with user overrides from
    {overrides}/explicit-words.md. Returns found words with line numbers
    and occurrence counts.

    Args:
        text: Lyrics text to scan

    Returns:
        JSON with {has_explicit: bool, found: [{word, line, line_number, count}],
                   total_count: int, unique_words: int}
    """
    if not text.strip():
        return _safe_json({
            "has_explicit": False, "found": [], "total_count": 0, "unique_words": 0,
        })

    words = _load_explicit_words()

    # Build compiled patterns for each word
    patterns = {
        w: re.compile(r'\b' + re.escape(w) + r'\b', re.IGNORECASE)
        for w in words
    }

    # Scan line by line
    hits: dict = {}  # word -> {count, lines: [{line, line_number}]}
    for line_num, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        # Skip section tags
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        for word, pattern in patterns.items():
            matches = pattern.findall(line)
            if matches:
                if word not in hits:
                    hits[word] = {"count": 0, "lines": []}
                hits[word]["count"] += len(matches)
                hits[word]["lines"].append({
                    "line": stripped,
                    "line_number": line_num,
                })

    found = []
    total = 0
    for word, data in sorted(hits.items()):
        total += data["count"]
        found.append({
            "word": word,
            "count": data["count"],
            "lines": data["lines"],
        })

    return _safe_json({
        "has_explicit": len(found) > 0,
        "found": found,
        "total_count": total,
        "unique_words": len(found),
    })


# --- Link extraction ---

_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


@mcp.tool()
async def extract_links(
    album_slug: str,
    file_name: str = "SOURCES.md",
) -> str:
    """Extract markdown links from an album file.

    Scans SOURCES.md, RESEARCH.md, or a track file for [text](url) links.
    Useful for source verification workflows.

    Args:
        album_slug: Album slug (e.g., "my-album")
        file_name: File to scan — "SOURCES.md", "RESEARCH.md", "README.md",
                   or a track slug like "01-track-name" (resolves to track file)

    Returns:
        JSON with {links: [{text, url, line_number}], count: int}
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

    album_path = album.get("path", "")

    # Determine file path
    file_path = None
    normalized_file = _normalize_slug(file_name)

    # Check if it's a track slug
    tracks = album.get("tracks", {})
    track = tracks.get(normalized_file)
    if not track:
        # Try prefix match
        prefix_matches = {s: d for s, d in tracks.items()
                         if s.startswith(normalized_file)}
        if len(prefix_matches) == 1:
            track = next(iter(prefix_matches.values()))

    if track:
        file_path = track.get("path", "")
    else:
        # It's a file name in the album directory
        candidate = Path(album_path) / file_name
        if candidate.exists():
            file_path = str(candidate)

    if not file_path:
        return _safe_json({
            "found": False,
            "error": f"File '{file_name}' not found in album '{album_slug}'",
        })

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read file: {e}"})

    links = []
    for line_num, line in enumerate(text.split("\n"), 1):
        for match in _MARKDOWN_LINK_RE.finditer(line):
            links.append({
                "text": match.group(1),
                "url": match.group(2),
                "line_number": line_num,
            })

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "file_name": file_name,
        "file_path": file_path,
        "links": links,
        "count": len(links),
    })


# --- Lyrics stats ---

# Genre word-count targets from craft-reference.md
_GENRE_WORD_TARGETS = {
    "pop":        {"min": 150, "max": 250},
    "dance-pop":  {"min": 150, "max": 250},
    "synth-pop":  {"min": 150, "max": 250},
    "punk":       {"min": 150, "max": 250},
    "pop-punk":   {"min": 150, "max": 250},
    "rock":       {"min": 200, "max": 350},
    "alt-rock":   {"min": 200, "max": 350},
    "folk":       {"min": 200, "max": 350},
    "country":    {"min": 200, "max": 350},
    "americana":  {"min": 200, "max": 350},
    "hip-hop":    {"min": 300, "max": 500},
    "rap":        {"min": 300, "max": 500},
    "ballad":     {"min": 200, "max": 300},
    "electronic": {"min": 100, "max": 200},
    "edm":        {"min": 100, "max": 200},
    "ambient":    {"min": 50,  "max": 150},
    "lo-fi":      {"min": 50,  "max": 150},
}

# Section tag pattern — these aren't "words" for counting
_SECTION_TAG_RE = re.compile(r'^\[.*\]$')


@mcp.tool()
async def get_lyrics_stats(
    album_slug: str,
    track_slug: str = "",
) -> str:
    """Get word count, character count, and genre target comparison for lyrics.

    Counts lyrics excluding section tags. Compares against genre-appropriate
    word count targets from the craft reference. Flags tracks that are over
    the 800-word danger zone (Suno rushes/compresses).

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Specific track slug/number (empty = all tracks)

    Returns:
        JSON with per-track stats and genre targets
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

    genre = album.get("genre", "").lower()
    all_tracks = album.get("tracks", {})

    # Determine which tracks
    if track_slug:
        normalized_track = _normalize_slug(track_slug)
        track_data = all_tracks.get(normalized_track)
        matched_slug = normalized_track

        if not track_data:
            prefix_matches = {s: d for s, d in all_tracks.items()
                             if s.startswith(normalized_track)}
            if len(prefix_matches) == 1:
                matched_slug = next(iter(prefix_matches))
                track_data = prefix_matches[matched_slug]
            elif len(prefix_matches) > 1:
                return _safe_json({
                    "found": False,
                    "error": f"Multiple tracks match '{track_slug}': "
                             f"{', '.join(prefix_matches.keys())}",
                })
            else:
                return _safe_json({
                    "found": False,
                    "error": f"Track '{track_slug}' not found in album '{album_slug}'",
                })
        tracks_to_check = {matched_slug: track_data}
    else:
        tracks_to_check = all_tracks

    # Get genre target
    target = _GENRE_WORD_TARGETS.get(genre, {"min": 150, "max": 350})

    track_results = []
    for t_slug, t_data in sorted(tracks_to_check.items()):
        track_path = t_data.get("path", "")
        if not track_path:
            track_results.append({
                "track_slug": t_slug,
                "title": t_data.get("title", t_slug),
                "error": "No file path",
            })
            continue

        try:
            text = Path(track_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            track_results.append({
                "track_slug": t_slug,
                "title": t_data.get("title", t_slug),
                "error": "Cannot read file",
            })
            continue

        # Extract Lyrics Box
        lyrics_section = _extract_markdown_section(text, "Lyrics Box")
        lyrics = ""
        if lyrics_section:
            code = _extract_code_block(lyrics_section)
            lyrics = code if code else lyrics_section

        if not lyrics.strip():
            track_results.append({
                "track_slug": t_slug,
                "title": t_data.get("title", t_slug),
                "word_count": 0,
                "char_count": 0,
                "line_count": 0,
                "section_count": 0,
                "status": "EMPTY",
            })
            continue

        # Count words excluding section tags
        words = []
        section_count = 0
        content_lines = 0
        for line in lyrics.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if _SECTION_TAG_RE.match(stripped):
                section_count += 1
                continue
            content_lines += 1
            words.extend(stripped.split())

        word_count = len(words)
        char_count = len(lyrics.strip())

        # Determine status
        if word_count > 800:
            status = "DANGER"
            note = "Over 800 words — Suno will rush/compress/skip sections"
        elif word_count > target["max"]:
            status = "OVER"
            note = f"Over target ({target['max']} max for {genre})"
        elif word_count < target["min"]:
            status = "UNDER"
            note = f"Under target ({target['min']} min for {genre})"
        else:
            status = "OK"
            note = f"Within target ({target['min']}–{target['max']} for {genre})"

        track_results.append({
            "track_slug": t_slug,
            "title": t_data.get("title", t_slug),
            "word_count": word_count,
            "char_count": char_count,
            "line_count": content_lines,
            "section_count": section_count,
            "status": status,
            "note": note,
        })

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "genre": genre,
        "target": target,
        "tracks": track_results,
    })


# =============================================================================
# Album Operation Tools
# =============================================================================


@mcp.tool()
async def get_album_full(
    album_slug: str,
    include_sections: str = "",
) -> str:
    """Get full album data including track content sections in one call.

    Combines find_album + extract_section for all tracks, eliminating N+1
    queries. Without include_sections, returns the same as find_album.

    Args:
        album_slug: Album slug (e.g., "my-album")
        include_sections: Comma-separated section names to extract from each track
                         (e.g., "lyrics,style,pronunciation,streaming")
                         Empty = metadata only (no file reads)

    Returns:
        JSON with album data + embedded track sections
    """
    state = cache.get_state()
    albums = state.get("albums", {})
    normalized = _normalize_slug(album_slug)

    # Try exact then fuzzy match
    album = albums.get(normalized)
    matched_slug = normalized
    if not album:
        matches = {s: d for s, d in albums.items() if normalized in s or s in normalized}
        if len(matches) == 1:
            matched_slug = next(iter(matches))
            album = matches[matched_slug]
        elif len(matches) > 1:
            return _safe_json({
                "found": False,
                "error": f"Multiple albums match '{album_slug}': {', '.join(matches.keys())}",
            })
        else:
            return _safe_json({
                "found": False,
                "error": f"Album '{album_slug}' not found",
                "available_albums": list(albums.keys()),
            })

    result = {
        "found": True,
        "slug": matched_slug,
        "album": {
            "title": album.get("title", matched_slug),
            "status": album.get("status", "Unknown"),
            "genre": album.get("genre", ""),
            "path": album.get("path", ""),
            "track_count": album.get("track_count", 0),
            "tracks_completed": album.get("tracks_completed", 0),
        },
        "tracks": {},
    }

    # Parse requested sections
    sections = []
    if include_sections:
        sections = [s.strip().lower() for s in include_sections.split(",") if s.strip()]

    tracks = album.get("tracks", {})
    for track_slug_key, track in sorted(tracks.items()):
        track_entry = {
            "title": track.get("title", track_slug_key),
            "status": track.get("status", "Unknown"),
            "explicit": track.get("explicit", False),
            "has_suno_link": track.get("has_suno_link", False),
            "sources_verified": track.get("sources_verified", "N/A"),
            "path": track.get("path", ""),
        }

        # Read sections from disk if requested
        if sections and track.get("path"):
            try:
                file_text = Path(track["path"]).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                file_text = None

            if file_text:
                track_entry["sections"] = {}
                for sec in sections:
                    heading = _SECTION_NAMES.get(sec)
                    if not heading:
                        continue
                    sec_content = _extract_markdown_section(file_text, heading)
                    if sec_content is not None:
                        # For code-block sections, extract just the code block
                        code_block_sections = {"Style Box", "Lyrics Box", "Streaming Lyrics", "Original Quote"}
                        if heading in code_block_sections:
                            code = _extract_code_block(sec_content)
                            if code is not None:
                                sec_content = code
                        track_entry["sections"][sec] = sec_content

        result["tracks"][track_slug_key] = track_entry

    return _safe_json(result)


@mcp.tool()
async def validate_album_structure(
    album_slug: str,
    checks: str = "all",
) -> str:
    """Run structural validation on an album's files and directories.

    Checks directory structure, required files, audio placement, and track
    content integrity. Returns structured results with actionable fix commands.

    Args:
        album_slug: Album slug (e.g., "my-album")
        checks: Comma-separated checks to run: "structure", "audio", "art",
                "tracks", "all" (default)

    Returns:
        JSON with {passed, failed, warnings, skipped, issues[], checks[]}
    """
    state = cache.get_state()
    config = state.get("config", {})
    albums = state.get("albums", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    normalized = _normalize_slug(album_slug)
    album = albums.get(normalized)
    if not album:
        return _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    # Parse check types
    check_set = set()
    for c in checks.split(","):
        c = c.strip().lower()
        if c == "all":
            check_set = {"structure", "audio", "art", "tracks"}
            break
        if c in ("structure", "audio", "art", "tracks"):
            check_set.add(c)
    if not check_set:
        check_set = {"structure", "audio", "art", "tracks"}

    content_root = config.get("content_root", "")
    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")
    genre = album.get("genre", "")
    album_path = album.get("path", "")
    audio_path = str(Path(audio_root) / artist / normalized)

    passed = 0
    failed = 0
    warnings = 0
    skipped = 0
    results = []
    issues = []

    def _pass(category, msg):
        nonlocal passed
        passed += 1
        results.append({"status": "PASS", "category": category, "message": msg})

    def _fail(category, msg, fix=""):
        nonlocal failed
        failed += 1
        results.append({"status": "FAIL", "category": category, "message": msg})
        if fix:
            issues.append({"message": msg, "fix": fix})

    def _warn(category, msg):
        nonlocal warnings
        warnings += 1
        results.append({"status": "WARN", "category": category, "message": msg})

    def _skip(category, msg):
        nonlocal skipped
        skipped += 1
        results.append({"status": "SKIP", "category": category, "message": msg})

    # --- Structure checks ---
    if "structure" in check_set:
        ap = Path(album_path)
        if ap.is_dir():
            _pass("structure", f"Album directory exists: {album_path}")
        else:
            _fail("structure", f"Album directory missing: {album_path}")

        readme = ap / "README.md"
        if readme.exists():
            _pass("structure", "README.md exists")
        else:
            _fail("structure", "README.md missing")

        tracks_dir = ap / "tracks"
        if tracks_dir.is_dir():
            _pass("structure", "tracks/ directory exists")
            track_files = list(tracks_dir.glob("*.md"))
            if track_files:
                _pass("structure", f"{len(track_files)} track files found")
            else:
                _warn("structure", "No track files found in tracks/")
        else:
            _fail("structure", "tracks/ directory missing",
                  fix=f"mkdir -p {album_path}/tracks")

    # --- Audio checks ---
    if "audio" in check_set:
        audio_p = Path(audio_path)
        wrong_path = Path(audio_root) / normalized  # missing artist folder

        if audio_p.is_dir():
            _pass("audio", f"Audio directory exists: {audio_path}")
            wav_files = list(audio_p.glob("*.wav"))
            if wav_files:
                _pass("audio", f"{len(wav_files)} WAV files found")
            else:
                _skip("audio", "No audio files yet")

            mastered = audio_p / "mastered"
            if mastered.is_dir():
                _pass("audio", "mastered/ directory exists")
            else:
                _skip("audio", "Not mastered yet")
        elif wrong_path.is_dir():
            _fail("audio", "Audio in wrong location (missing artist folder)",
                  fix=f"mv {wrong_path} {audio_path}")
        else:
            _skip("audio", "No audio directory yet")

    # --- Art checks ---
    if "art" in check_set:
        audio_p = Path(audio_path)
        ap = Path(album_path)

        if (audio_p / "album.png").exists():
            _pass("art", "album.png in audio folder")
        else:
            _skip("art", "No album art in audio folder yet")

        art_files = list(ap.glob("album-art.*"))
        if art_files:
            _pass("art", f"Album art in content folder: {art_files[0].name}")
        else:
            _skip("art", "No album art in content folder yet")

    # --- Track content checks ---
    if "tracks" in check_set:
        tracks = album.get("tracks", {})
        for t_slug, t_data in sorted(tracks.items()):
            status = t_data.get("status", "Unknown")
            has_link = t_data.get("has_suno_link", False)
            sources = t_data.get("sources_verified", "N/A")

            track_issues = []
            if status in ("Generated", "Final") and not has_link:
                track_issues.append("Suno Link missing")
            if sources.lower() == "pending":
                track_issues.append("Sources not verified")

            if track_issues:
                _warn("tracks", f"{t_slug}: Status={status}, issues: {', '.join(track_issues)}")
            else:
                _pass("tracks", f"{t_slug}: Status={status}")

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "skipped": skipped,
        "total": passed + failed + warnings + skipped,
        "checks": results,
        "issues": issues,
    })


@mcp.tool()
async def create_album_structure(
    album_slug: str,
    genre: str,
    documentary: bool = False,
) -> str:
    """Create a new album directory with templates.

    Creates the content directory structure and copies templates. Does NOT
    create audio or documents directories (those are created when needed).

    Args:
        album_slug: Album name as slug (e.g., "my-new-album")
        genre: Primary genre (e.g., "hip-hop", "electronic", "country", "folk", "rock")
        documentary: Whether to include research/sources templates

    Returns:
        JSON with {created: bool, path: str, files: [...]}
    """
    state = cache.get_state()
    config = state.get("config", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    content_root = config.get("content_root", "")
    artist = config.get("artist_name", "")

    if not content_root or not artist:
        return _safe_json({"error": "content_root or artist_name not configured"})

    normalized = _normalize_slug(album_slug)
    genre_slug = _normalize_slug(genre)

    album_path = Path(content_root) / "artists" / artist / "albums" / genre_slug / normalized
    tracks_path = album_path / "tracks"
    templates_path = PLUGIN_ROOT / "templates"

    # Check if already exists
    if album_path.exists():
        return _safe_json({
            "created": False,
            "error": f"Album directory already exists: {album_path}",
            "path": str(album_path),
        })

    # Create directories
    try:
        tracks_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return _safe_json({"error": f"Cannot create directory: {e}"})

    # Copy templates
    created_files = []

    # Album README (always)
    album_template = templates_path / "album.md"
    readme_dest = album_path / "README.md"
    if album_template.exists():
        shutil.copy2(str(album_template), str(readme_dest))
        created_files.append("README.md")

    # Documentary templates
    if documentary:
        research_template = templates_path / "research.md"
        sources_template = templates_path / "sources.md"

        if research_template.exists():
            shutil.copy2(str(research_template), str(album_path / "RESEARCH.md"))
            created_files.append("RESEARCH.md")
        if sources_template.exists():
            shutil.copy2(str(sources_template), str(album_path / "SOURCES.md"))
            created_files.append("SOURCES.md")

    created_files.append("tracks/")

    return _safe_json({
        "created": True,
        "path": str(album_path),
        "tracks_path": str(tracks_path),
        "genre": genre_slug,
        "documentary": documentary,
        "files": created_files,
    })


# =============================================================================
# Pre-Generation Gates
# =============================================================================


@mcp.tool()
async def run_pre_generation_gates(
    album_slug: str,
    track_slug: str = "",
) -> str:
    """Run all 6 pre-generation validation gates on a track or album.

    Gates:
        1. Sources Verified — sources_verified is not "Pending"
        2. Lyrics Reviewed — Lyrics Box populated, no [TODO]/[PLACEHOLDER]
        3. Pronunciation Resolved — All Pronunciation Notes entries applied
        4. Explicit Flag Set — Explicit field is "Yes" or "No"
        5. Style Prompt Complete — Non-empty Style Box with content
        6. Artist Names Cleared — No real artist names in Style Box

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Specific track slug/number (empty = all tracks)

    Returns:
        JSON with per-track gate results and verdicts
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

    all_tracks = album.get("tracks", {})

    # Determine which tracks to check
    if track_slug:
        normalized_track = _normalize_slug(track_slug)
        track_data = all_tracks.get(normalized_track)
        matched_slug = normalized_track

        if not track_data:
            prefix_matches = {s: d for s, d in all_tracks.items() if s.startswith(normalized_track)}
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
        tracks_to_check = {matched_slug: track_data}
    else:
        tracks_to_check = all_tracks

    # Load artist blocklist for gate 6
    blocklist = _load_artist_blocklist()

    track_results = []
    total_blocking = 0
    total_warnings = 0

    for t_slug, t_data in sorted(tracks_to_check.items()):
        gates = []
        blocking = 0
        warning_count = 0

        # Read track file if available
        file_text = None
        track_path = t_data.get("path", "")
        if track_path:
            try:
                file_text = Path(track_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                pass

        # Gate 1: Sources Verified
        sources = t_data.get("sources_verified", "N/A")
        if sources.lower() == "pending":
            gates.append({"gate": "Sources Verified", "status": "FAIL", "severity": "BLOCKING",
                          "detail": "Sources not yet verified by human"})
            blocking += 1
        else:
            gates.append({"gate": "Sources Verified", "status": "PASS",
                          "detail": f"Status: {sources}"})

        # Gate 2: Lyrics Reviewed
        lyrics_content = None
        if file_text:
            lyrics_section = _extract_markdown_section(file_text, "Lyrics Box")
            if lyrics_section:
                lyrics_content = _extract_code_block(lyrics_section)

        if not lyrics_content or not lyrics_content.strip():
            gates.append({"gate": "Lyrics Reviewed", "status": "FAIL", "severity": "BLOCKING",
                          "detail": "Lyrics Box is empty"})
            blocking += 1
        elif re.search(r'\[TODO\]|\[PLACEHOLDER\]', lyrics_content, re.IGNORECASE):
            gates.append({"gate": "Lyrics Reviewed", "status": "FAIL", "severity": "BLOCKING",
                          "detail": "Lyrics contain [TODO] or [PLACEHOLDER] markers"})
            blocking += 1
        else:
            gates.append({"gate": "Lyrics Reviewed", "status": "PASS",
                          "detail": "Lyrics populated"})

        # Gate 3: Pronunciation Resolved
        if file_text:
            pron_section = _extract_markdown_section(file_text, "Pronunciation Notes")
            pron_entries = []
            if pron_section:
                for line in pron_section.split("\n"):
                    if not line.startswith("|") or "---" in line or "Word" in line:
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 4:
                        word = parts[1].strip()
                        phonetic = parts[2].strip()
                        if word and word != "—" and phonetic and phonetic != "—":
                            pron_entries.append({"word": word, "phonetic": phonetic})

            if pron_entries and lyrics_content:
                unapplied = []
                for entry in pron_entries:
                    if not re.search(re.escape(entry["phonetic"]), lyrics_content, re.IGNORECASE):
                        unapplied.append(entry["word"])
                if unapplied:
                    gates.append({"gate": "Pronunciation Resolved", "status": "FAIL", "severity": "BLOCKING",
                                  "detail": f"Unapplied: {', '.join(unapplied)}"})
                    blocking += 1
                else:
                    gates.append({"gate": "Pronunciation Resolved", "status": "PASS",
                                  "detail": f"All {len(pron_entries)} entries applied"})
            else:
                gates.append({"gate": "Pronunciation Resolved", "status": "PASS",
                              "detail": "No pronunciation entries to check"})
        else:
            gates.append({"gate": "Pronunciation Resolved", "status": "SKIP",
                          "detail": "Track file not readable"})

        # Gate 4: Explicit Flag Set
        explicit = t_data.get("explicit")
        if explicit is None:
            gates.append({"gate": "Explicit Flag Set", "status": "WARN", "severity": "WARNING",
                          "detail": "Explicit field not set"})
            warning_count += 1
        else:
            gates.append({"gate": "Explicit Flag Set", "status": "PASS",
                          "detail": f"Explicit: {'Yes' if explicit else 'No'}"})

        # Gate 5: Style Prompt Complete
        style_content = None
        if file_text:
            style_section = _extract_markdown_section(file_text, "Style Box")
            if style_section:
                style_content = _extract_code_block(style_section)

        if not style_content or not style_content.strip():
            gates.append({"gate": "Style Prompt Complete", "status": "FAIL", "severity": "BLOCKING",
                          "detail": "Style Box is empty"})
            blocking += 1
        else:
            gates.append({"gate": "Style Prompt Complete", "status": "PASS",
                          "detail": f"Style prompt: {len(style_content)} chars"})

        # Gate 6: Artist Names Cleared
        if style_content:
            found_artists = []
            text_lower = style_content.lower()
            for entry in blocklist:
                pattern = re.compile(r'\b' + re.escape(entry["name"]) + r'\b', re.IGNORECASE)
                if pattern.search(text_lower):
                    found_artists.append(entry["name"])

            if found_artists:
                gates.append({"gate": "Artist Names Cleared", "status": "FAIL", "severity": "BLOCKING",
                              "detail": f"Found: {', '.join(found_artists)}"})
                blocking += 1
            else:
                gates.append({"gate": "Artist Names Cleared", "status": "PASS",
                              "detail": "No blocked artist names found"})
        else:
            gates.append({"gate": "Artist Names Cleared", "status": "SKIP",
                          "detail": "No style prompt to check"})

        verdict = "READY" if blocking == 0 else "NOT READY"
        total_blocking += blocking
        total_warnings += warning_count

        track_results.append({
            "track_slug": t_slug,
            "title": t_data.get("title", t_slug),
            "verdict": verdict,
            "blocking": blocking,
            "warnings": warning_count,
            "gates": gates,
        })

    if len(tracks_to_check) == 1:
        album_verdict = track_results[0]["verdict"]
    elif total_blocking == 0:
        album_verdict = "ALL READY"
    elif total_blocking < sum(t["blocking"] for t in track_results):
        album_verdict = "PARTIAL"
    else:
        album_verdict = "NOT READY"

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "album_verdict": album_verdict,
        "total_tracks": len(track_results),
        "total_blocking": total_blocking,
        "total_warnings": total_warnings,
        "tracks": track_results,
    })


def main():
    """Start the MCP server."""
    logger.info("Starting bitwize-music-state MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
