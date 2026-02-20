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
    get_python_command  - Get venv Python path for bash script invocation
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
    check_cross_track_repetition - Scan album for words/phrases repeated across tracks
    extract_distinctive_phrases - Extract distinctive n-grams from lyrics for plagiarism checking
    count_syllables     - Syllable counts per line with consistency analysis
    analyze_readability - Flesch Reading Ease and vocabulary stats
    analyze_rhyme_scheme - Rhyme scheme detection with section awareness
    validate_section_structure - Section tag validation and balance checking
    get_album_full      - Combined album + track sections query
    validate_album_structure - Structural validation of album directories
    create_album_structure - Create album directory with templates
    run_pre_generation_gates - Run all 8 pre-generation validation gates
    check_streaming_lyrics - Check streaming lyrics readiness for release
    get_streaming_urls    - Get streaming platform URLs for an album
    update_streaming_url  - Set a streaming platform URL
    verify_streaming_urls - Check if streaming URLs are live/reachable
    list_skills         - List all skills with optional filtering
    get_skill           - Get full detail for one skill (fuzzy match)
    update_album_status - Update album status in README.md
    create_track        - Create a new track file from template
    get_promo_status    - Check promo/ directory file status
    get_promo_content   - Read a specific promo file
    get_plugin_version  - Get stored vs current plugin version
    create_idea         - Add a new idea to IDEAS.md
    update_idea         - Update a field in an existing idea
    rename_album        - Rename album slug, title, and directories
    rename_track        - Rename track slug, title, and file

    # Processing tools (mastering, sheet music, promo videos)
    analyze_audio       - Analyze audio tracks for mastering decisions
    qc_audio            - Run technical QC checks on audio tracks
    master_audio        - Master audio tracks for streaming
    fix_dynamic_track   - Fix tracks with excessive dynamic range
    master_with_reference - Master using a reference track
    transcribe_audio    - Convert WAV to sheet music via AnthemScore
    fix_sheet_music_titles - Strip track numbers from MusicXML titles
    create_songbook     - Combine sheet music PDFs into a songbook
    generate_promo_videos - Generate promo videos with waveform visualization
    generate_album_sampler - Generate album sampler video for social media
    master_album        - End-to-end mastering pipeline (analyze → QC → master → verify → status)

    # Database tools (tweet/promo management)
    db_init               - Initialize database tables (CREATE IF NOT EXISTS)
    db_list_tweets        - List tweets with optional album/status filtering
    db_create_tweet       - Insert a new tweet linked to an album/track
    db_update_tweet       - Update tweet fields (text, posted, enabled, media)
    db_delete_tweet       - Delete a tweet by ID
    db_search_tweets      - Full-text search across tweet content
    db_sync_album         - Upsert album + tracks from plugin state to database
    db_get_tweet_stats    - Tweet counts by status for an album or globally
"""
import asyncio
import json
import logging
import os
import re
import shutil
import statistics
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
    read_config,
    read_state,
    write_state,
    CURRENT_VERSION,
    STATE_FILE,
    CONFIG_FILE,
)
from tools.state.parsers import parse_album_readme, parse_track_file

# Initialize FastMCP server
mcp = FastMCP("bitwize-music-mcp")


# ---------------------------------------------------------------------------
# Status constants — single source of truth for track and album statuses.
# Use these instead of string literals to prevent typos and simplify refactoring.
# ---------------------------------------------------------------------------

# Track statuses (in order)
TRACK_NOT_STARTED = "Not Started"
TRACK_SOURCES_PENDING = "Sources Pending"
TRACK_SOURCES_VERIFIED = "Sources Verified"
TRACK_IN_PROGRESS = "In Progress"
TRACK_GENERATED = "Generated"
TRACK_FINAL = "Final"

# Album statuses (in order)
ALBUM_CONCEPT = "Concept"
ALBUM_RESEARCH_COMPLETE = "Research Complete"
ALBUM_SOURCES_VERIFIED = "Sources Verified"
ALBUM_IN_PROGRESS = "In Progress"
ALBUM_COMPLETE = "Complete"
ALBUM_RELEASED = "Released"

# Sets for membership checks
TRACK_COMPLETED_STATUSES = {TRACK_FINAL, TRACK_GENERATED}
ALBUM_VALID_STATUSES = [
    ALBUM_CONCEPT, ALBUM_RESEARCH_COMPLETE, ALBUM_SOURCES_VERIFIED,
    ALBUM_IN_PROGRESS, ALBUM_COMPLETE, ALBUM_RELEASED,
]

# Default for missing status fields
STATUS_UNKNOWN = "Unknown"

# Valid primary genres for album creation
_VALID_GENRES = frozenset({
    "hip-hop", "electronic", "rock", "folk", "country", "pop", "metal",
    "jazz", "rnb", "classical", "reggae", "punk", "indie-folk", "blues",
    "gospel", "latin", "k-pop",
})

_GENRE_ALIASES = {
    "r&b": "rnb", "rb": "rnb", "r-and-b": "rnb",
    "hip hop": "hip-hop", "hiphop": "hip-hop",
    "k pop": "k-pop", "kpop": "k-pop",
    "indie folk": "indie-folk",
}


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
        """Force full rebuild from markdown files.

        Thread-safe: holds the lock for the session-preservation and
        write phase so concurrent update_session() calls are not lost.
        """
        logger.info("Starting full state rebuild")
        config = read_config()
        if config is None:
            logger.error("Config not found at %s", CONFIG_FILE)
            return {"error": f"Config not found at {CONFIG_FILE}"}

        try:
            state = build_state(config, plugin_root=PLUGIN_ROOT)
        except Exception as e:
            logger.error("State build failed: %s", e)
            return {"error": f"State build failed: {e}"}

        # Lock for the read-existing → merge-session → write cycle
        # so concurrent update_session() writes are not overwritten.
        with self._lock:
            existing = read_state()
            if existing and "session" in existing:
                state["session"] = existing["session"]
            write_state(state)
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

        Thread-safe: holds the lock for the entire read-modify-write cycle
        to prevent concurrent updates from overwriting each other.
        """
        from datetime import datetime, timezone

        with self._lock:
            if self._is_stale() or self._state is None:
                self._load_from_disk()
            state = self._state
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
            self._update_mtimes()
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
        """Load state from disk into memory.

        If the on-disk state has a different schema version than the running
        code, an inline rebuild is performed (preserving session data).  This
        handles the upgrade path transparently — users with a v1.0.0 cache
        get a full rebuild to v1.1.0 (with skills) on first MCP access.
        """
        self._state = read_state()
        self._update_mtimes()
        if self._state is None:
            logger.warning("No state file found, will need rebuild")
        else:
            version = self._state.get("version", "")
            if version != CURRENT_VERSION:
                logger.info(
                    "State version %s != current %s, auto-rebuilding",
                    version, CURRENT_VERSION,
                )
                config = read_config()
                if config is not None:
                    try:
                        session = self._state.get("session", {})
                        state = build_state(config, plugin_root=PLUGIN_ROOT)
                        state["session"] = session
                        write_state(state)
                        self._state = state
                        self._update_mtimes()
                        logger.info(
                            "Auto-rebuild complete (v%s -> v%s)",
                            version, CURRENT_VERSION,
                        )
                    except Exception:
                        logger.warning(
                            "Auto-rebuild failed, using existing state",
                            exc_info=True,
                        )
                else:
                    logger.warning("Config not found, cannot auto-rebuild")
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
        status = album.get("status", STATUS_UNKNOWN)

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
            "status": track.get("status", STATUS_UNKNOWN),
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
    skills_count = state.get("skills", {}).get("count", 0)

    return _safe_json({
        "success": True,
        "albums": album_count,
        "tracks": track_count,
        "ideas": ideas_count,
        "skills": skills_count,
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
async def get_python_command() -> str:
    """Get the correct Python command for running plugin scripts via bash.

    Returns the absolute path to the venv Python interpreter and the plugin
    root directory. Use this before any bash invocation of plugin Python
    scripts to avoid hitting system Python (which lacks dependencies).

    Returns:
        JSON with:
            python: Absolute path to ~/.bitwize-music/venv/bin/python3
            plugin_root: Absolute path to the plugin directory
            venv_exists: Whether the venv exists
            usage: Ready-to-paste command template
            warning: Only present if venv is missing, with install instructions
    """
    venv_python = Path.home() / ".bitwize-music" / "venv" / "bin" / "python3"
    venv_exists = venv_python.is_file()

    result: dict[str, Any] = {
        "python": str(venv_python),
        "plugin_root": str(PLUGIN_ROOT),
        "venv_exists": venv_exists,
        "usage": f'{venv_python} "$PLUGIN_DIR/tools/<script>.py" <args>',
    }

    if not venv_exists:
        result["warning"] = (
            "Venv not found at ~/.bitwize-music/venv. "
            "Create it with: python3 -m venv ~/.bitwize-music/venv && "
            "~/.bitwize-music/venv/bin/pip install pyloudnorm scipy numpy "
            "soundfile matchering pillow pyyaml boto3"
        )

    return _safe_json(result)


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
    """Full-text search across albums, tracks, ideas, and skills.

    Args:
        query: Search query (case-insensitive substring match)
        scope: What to search - "albums", "tracks", "ideas", "skills", or "all" (default)

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
                    "status": album.get("status", STATUS_UNKNOWN),
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
                        "status": track.get("status", STATUS_UNKNOWN),
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

    if scope in ("all", "skills"):
        skill_matches = []
        for name, skill in state.get("skills", {}).get("items", {}).items():
            description = skill.get("description", "")
            model_tier = skill.get("model_tier", "")
            if (query_lower in name.lower() or
                    query_lower in description.lower() or
                    query_lower in model_tier.lower()):
                skill_matches.append({
                    "name": name,
                    "description": description,
                    "model_tier": model_tier,
                    "user_invocable": skill.get("user_invocable", True),
                })
        results["skills"] = skill_matches

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
        audio:     {audio_root}/artists/{artist}/albums/{genre}/{album}/
        documents: {documents_root}/artists/{artist}/albums/{genre}/{album}/
        tracks:    {content_root}/artists/{artist}/albums/{genre}/{album}/tracks/
        overrides: {overrides_path} or {content_root}/overrides/

    Args:
        path_type: One of "content", "audio", "documents", "tracks", "overrides"
        album_slug: Album slug (e.g., "my-album"). Ignored for "overrides".
        genre: Genre slug. Required for "content", "audio", "documents", and "tracks". If omitted, looked up from state cache.

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

    # All album path types need genre — try state cache if not provided
    if path_type in ("content", "tracks", "audio", "documents") and not genre:
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

    root_map = {
        "content": content_root,
        "tracks": content_root,
        "audio": audio_root,
        "documents": documents_root,
    }
    base = Path(root_map[path_type]) / "artists" / artist / "albums" / genre / normalized
    if path_type == "tracks":
        base = base / "tracks"
    resolved = str(base)

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
        status = track.get("status", STATUS_UNKNOWN)

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
_RE_CODE_BLOCK = re.compile(r'```(?:[^\n]*\n)(.*?)```|```(.*?)```', re.DOTALL)

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
    "mood": "Mood & Imagery",
    "mood-imagery": "Mood & Imagery",
    "lyrical-approach": "Lyrical Approach",
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
    """Extract the first code block from section text.

    Handles both ``​`lang\\ncontent``​` and ``​`content``​` forms,
    stripping any language identifier on the opening fence line.
    """
    match = _RE_CODE_BLOCK.search(section_text)
    if match:
        # group(1) = content after lang+newline; group(2) = inline content
        content = match.group(1) if match.group(1) is not None else (match.group(2) or "")
        return content.strip()
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
        return _safe_json({"found": False, "error": f"No path stored for track '{matched_slug}'"})

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


@mcp.tool()
async def update_track_field(
    album_slug: str,
    track_slug: str,
    field: str,
    value: str,
    force: bool = False,
) -> str:
    """Update a metadata field in a track's markdown file.

    Modifies the track's details table (| **Key** | Value |) and rebuilds
    the state cache to reflect the change.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        field: Field to update. Options:
            "status" — Track status (Not Started, Sources Pending, Sources Verified, In Progress, Generated, Final)
            "explicit" — Explicit flag (Yes, No)
            "suno-link" or "suno_link" — Suno generation link
            "sources-verified" or "sources_verified" — Verification status
            "stems" — Stems available (Yes, No)
            "pov" — Point of view
        value: New value for the field
        force: Override transition validation (for recovery/correction only)

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

    # Validate status value against allowed track statuses
    if field_key == "status" and value.lower().strip() not in _VALID_TRACK_STATUSES:
        return _safe_json({
            "error": (
                f"Invalid track status '{value}'. Valid options: "
                "Not Started, Sources Pending, Sources Verified, "
                "In Progress, Generated, Final"
            ),
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

    # Validate status transition before any file I/O
    if field_key == "status":
        current_status = track_data.get("status", TRACK_NOT_STARTED)
        err = _validate_track_transition(current_status, value, force=force)
        if err:
            return _safe_json({"error": err})

    track_path = track_data.get("path", "")
    if not track_path:
        return _safe_json({"found": False, "error": f"No path stored for track '{matched_slug}'"})

    # Read the file
    path = Path(track_path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track file: {e}"})

    # Pre-generation gate enforcement: block transition to "Generated" if gates fail
    if field_key == "status" and not force:
        canonical_new = _CANONICAL_TRACK_STATUS.get(value.lower().strip(), value)
        if canonical_new == TRACK_GENERATED:
            blocklist = _load_artist_blocklist()
            state_config = (cache.get_state()).get("config", {})
            gen_cfg = state_config.get("generation", {})
            gate_blocking, _, gate_results = _check_pre_gen_gates_for_track(
                track_data, text, blocklist,
                max_lyric_words=gen_cfg.get("max_lyric_words", 800),
            )
            if gate_blocking > 0:
                return _safe_json({
                    "error": f"Cannot transition to 'Generated' — {gate_blocking} pre-generation gate(s) failed",
                    "failed_gates": [g for g in gate_results if g.get("severity") == "BLOCKING"],
                    "hint": "Fix the issues above, or use force=True to override.",
                })

    # Suno link gate: block Generated → Final if no Suno link (configurable)
    if field_key == "status" and not force:
        canonical_new = _CANONICAL_TRACK_STATUS.get(value.lower().strip(), value)
        if canonical_new == TRACK_FINAL:
            state_config = (cache.get_state()).get("config", {})
            gen_config = state_config.get("generation", {})
            require_link = gen_config.get("require_suno_link_for_final", True)
            if require_link and not track_data.get("has_suno_link", False):
                return _safe_json({
                    "error": "Cannot mark track as 'Final' — no Suno link set. "
                             "Set the Suno link first with update_track_field("
                             "suno-link), or use force=True to override. "
                             "To disable this check, set "
                             "generation.require_suno_link_for_final: false in config.",
                })

    # Source verification gate: check that actual source links exist
    if field_key in ("sources-verified", "sources_verified") and not force:
        val_lower = value.lower()
        if "verified" in val_lower and "pending" not in val_lower:
            has_links = False
            # Check 1: SOURCES.md in album directory
            album_path = album.get("path", "")
            if album_path:
                sources_path = Path(album_path) / "SOURCES.md"
                if sources_path.exists():
                    try:
                        sources_text = sources_path.read_text(encoding="utf-8")
                        if _MARKDOWN_LINK_RE.search(sources_text):
                            has_links = True
                    except (OSError, UnicodeDecodeError):
                        pass
            # Check 2: Track file Source section for inline links
            if not has_links:
                source_section = _extract_markdown_section(text, "Source")
                if source_section and _MARKDOWN_LINK_RE.search(source_section):
                    has_links = True
            if not has_links:
                return _safe_json({
                    "error": (
                        "Cannot verify sources — no markdown links found in "
                        "SOURCES.md or track Source section. Add [text](url) "
                        "links before verifying, or use force=True to override."
                    ),
                })

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

    new_row = f"{match.group(1)} {value} |"
    updated_text = text[:match.start()] + new_row + text[match.end():]

    # Write back
    try:
        path.write_text(updated_text, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write track file: {e}"})

    logger.info("Updated %s.%s field '%s' to '%s'", normalized_album, matched_slug, table_key, value)

    # Re-parse the track and update cache. If this fails, the file write
    # already succeeded — log the error but still report success.
    parsed = {}
    try:
        parsed = parse_track_file(path)
        if matched_slug in tracks:
            tracks[matched_slug].update({
                "status": parsed.get("status", tracks[matched_slug].get("status")),
                "explicit": parsed.get("explicit", tracks[matched_slug].get("explicit")),
                "has_suno_link": parsed.get("has_suno_link", tracks[matched_slug].get("has_suno_link")),
                "sources_verified": parsed.get("sources_verified", tracks[matched_slug].get("sources_verified")),
                "mtime": path.stat().st_mtime,
            })
            write_state(state)
    except Exception as e:
        logger.warning("File written but cache update failed for %s.%s: %s", normalized_album, matched_slug, e)

    return _safe_json({
        "success": True,
        "album_slug": normalized_album,
        "track_slug": matched_slug,
        "field": table_key,
        "value": value,
        "track": parsed,
    })


def _detect_phase(album: dict) -> str:
    """Detect the current workflow phase for an album.

    Matches the decision tree from the resume skill.
    """
    status = album.get("status", STATUS_UNKNOWN)
    tracks = album.get("tracks", {})

    if status == ALBUM_RELEASED:
        return "Released"
    if status == ALBUM_COMPLETE:
        return "Ready to Release"

    track_statuses = [t.get("status", STATUS_UNKNOWN) for t in tracks.values()]
    sources = [t.get("sources_verified", "N/A") for t in tracks.values()]

    if status == ALBUM_CONCEPT or not track_statuses:
        return "Planning"

    # Count by status
    not_started = sum(1 for s in track_statuses if s == TRACK_NOT_STARTED)
    in_progress = sum(1 for s in track_statuses if s == TRACK_IN_PROGRESS)
    generated = sum(1 for s in track_statuses if s == TRACK_GENERATED)
    final = sum(1 for s in track_statuses if s == TRACK_FINAL)
    total = len(track_statuses)
    sources_pending = sum(1 for s in sources if s.lower() == "pending")

    if sources_pending > 0:
        return "Source Verification"
    if not_started > 0 or in_progress > 0:
        return "Writing"
    if generated == 0 and final == 0:
        return "Ready to Write"
    if generated > 0 and (generated + final) < total:
        return "Generating"
    if generated > 0 and final == 0:
        return "Mastering"
    if final == total:
        return "Ready to Release"

    # Fallback phase name (not an album status constant — this is a workflow phase)
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
        s = track.get("status", STATUS_UNKNOWN)
        status_counts[s] = status_counts.get(s, 0) + 1

    tracks_completed = sum(
        count for s, count in status_counts.items() if s in TRACK_COMPLETED_STATUSES
    )

    completion_pct = round((tracks_completed / track_count * 100), 1) if track_count > 0 else 0.0

    # Detect phase
    phase = _detect_phase(album)

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "album_title": album.get("title", normalized),
        "album_status": album.get("status", STATUS_UNKNOWN),
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

    override_path = (Path(overrides_dir) / override_name).resolve()
    safe_root = Path(overrides_dir).resolve()
    if not str(override_path).startswith(str(safe_root) + "/") and override_path != safe_root:
        return _safe_json({
            "error": "Invalid override path: name must not escape overrides directory",
            "override_name": override_name,
        })
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

    ref_path = (PLUGIN_ROOT / "reference" / ref_name).resolve()
    safe_root = (PLUGIN_ROOT / "reference").resolve()
    if not str(ref_path).startswith(str(safe_root) + "/") and ref_path != safe_root:
        return _safe_json({
            "error": "Invalid reference path: name must not escape reference directory",
        })
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
            "suno" — JSON object with title, style, and lyrics for Suno auto-fill

    Returns:
        JSON with {content: str, content_type: str, track_slug: str}
    """
    valid_types = {"lyrics", "style", "streaming", "streaming-lyrics", "all", "suno"}
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
        return _safe_json({"found": False, "error": f"No path stored for track '{matched_slug}'"})

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
    elif content_type == "suno":
        style = _get_section_content("Style Box")
        lyrics = _get_section_content("Lyrics Box")
        title = track_data.get("title", matched_slug)
        if style is None and lyrics is None:
            content = None
        else:
            content = json.dumps({
                "title": title,
                "style": style or "",
                "lyrics": lyrics or "",
            }, ensure_ascii=False)
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
        JSON with {has_homographs: bool, matches: [{word, line, line_number, options}], count: int}
    """
    if not text.strip():
        return _safe_json({"has_homographs": False, "matches": [], "count": 0})

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

    return _safe_json({"has_homographs": len(results) > 0, "matches": results, "count": len(results)})


# Artist blocklist cache — loaded lazily from reference file
_artist_blocklist_cache: Optional[list] = None
_artist_blocklist_patterns: Optional[dict] = None  # name -> compiled re.Pattern
_artist_blocklist_mtime: float = 0.0
_artist_blocklist_lock = threading.Lock()


def _load_artist_blocklist() -> list:
    """Load and parse the artist blocklist from the reference file.

    Automatically reloads when the source file changes on disk.
    Returns a list of dicts: [{name: str, alternative: str, genre: str}]
    """
    global _artist_blocklist_cache, _artist_blocklist_patterns
    global _artist_blocklist_mtime
    with _artist_blocklist_lock:
        blocklist_path = PLUGIN_ROOT / "reference" / "suno" / "artist-blocklist.md"
        try:
            current_mtime = blocklist_path.stat().st_mtime if blocklist_path.exists() else 0.0
        except OSError:
            current_mtime = 0.0
        if _artist_blocklist_cache is not None and current_mtime == _artist_blocklist_mtime:
            return _artist_blocklist_cache

        entries = []

        if not blocklist_path.exists():
            logger.warning("Artist blocklist not found at %s", blocklist_path)
            _artist_blocklist_cache = entries
            _artist_blocklist_patterns = {}
            _artist_blocklist_mtime = current_mtime
            return entries

        try:
            text = blocklist_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.error("Cannot read artist blocklist: %s", e)
            _artist_blocklist_cache = entries
            _artist_blocklist_patterns = {}
            _artist_blocklist_mtime = current_mtime
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
        _artist_blocklist_mtime = current_mtime
        # Pre-compile patterns for each artist name
        _artist_blocklist_patterns = {
            entry["name"]: re.compile(r'\b' + re.escape(entry["name"]) + r'\b', re.IGNORECASE)
            for entry in entries
        }
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
        JSON with {clean: bool, matches: [{name, alternative, genre}], count: int}
    """
    if not text.strip():
        return _safe_json({"clean": True, "matches": [], "count": 0})

    blocklist = _load_artist_blocklist()
    matches = []

    for entry in blocklist:
        name = entry["name"]
        pattern = _artist_blocklist_patterns.get(name)
        if pattern and pattern.search(text):
            matches.append({
                "name": name,
                "alternative": entry["alternative"],
                "genre": entry["genre"],
            })

    return _safe_json({
        "clean": len(matches) == 0,
        "matches": matches,
        "count": len(matches),
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
        return _safe_json({"found": False, "error": f"No path stored for track '{matched_slug}'"})

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
_explicit_word_patterns: Optional[dict] = None  # word -> compiled re.Pattern
_explicit_word_mtime: float = 0.0
_explicit_word_lock = threading.Lock()


def _load_explicit_words() -> set:
    """Load the explicit word set, merging base list with user overrides.

    Automatically reloads when the user override file changes on disk.
    """
    global _explicit_word_cache, _explicit_word_patterns
    global _explicit_word_mtime

    # Resolve the override file path BEFORE acquiring _explicit_word_lock
    # to avoid lock ordering issues (cache.get_state() acquires cache._lock).
    override_path = None
    try:
        state = cache.get_state()
        config = state.get("config", {})
        overrides_dir = config.get("overrides_dir", "")
        if not overrides_dir:
            content_root = config.get("content_root", "")
            overrides_dir = str(Path(content_root) / "overrides")
        override_path = Path(overrides_dir) / "explicit-words.md"
    except Exception:
        pass

    with _explicit_word_lock:

        try:
            current_mtime = override_path.stat().st_mtime if override_path and override_path.exists() else 0.0
        except OSError:
            current_mtime = 0.0

        if _explicit_word_cache is not None and current_mtime == _explicit_word_mtime:
            return _explicit_word_cache

        words = set(_BASE_EXPLICIT_WORDS)

        # Load user overrides (override_path already resolved above)
        try:
            if override_path and override_path.exists():
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
        except (OSError, UnicodeDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to load explicit word overrides: %s", e)

        _explicit_word_cache = words
        _explicit_word_mtime = current_mtime
        # Pre-compile patterns for each word
        _explicit_word_patterns = {
            w: re.compile(r'\b' + re.escape(w) + r'\b', re.IGNORECASE)
            for w in words
        }
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
        JSON with {has_explicit: bool, matches: [{word, line, line_number, count}],
                   total_count: int, unique_words: int}
    """
    if not text.strip():
        return _safe_json({
            "has_explicit": False, "matches": [], "total_count": 0, "unique_words": 0,
        })

    _load_explicit_words()

    # Scan line by line using pre-compiled patterns
    hits: dict = {}  # word -> {count, lines: [{line, line_number}]}
    for line_num, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        # Skip section tags
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        for word, pattern in _explicit_word_patterns.items():
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
        "matches": found,
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

# Cross-track repetition analysis constants
_WORD_TOKEN_RE = re.compile(r"[a-zA-Z']+")

# Stopwords: English function words + common song filler + ubiquitous song vocabulary.
# These appear so often across tracks that flagging them is noise, not signal.
_CROSS_TRACK_STOPWORDS = frozenset({
    # English function words
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet", "for",
    "in", "on", "at", "to", "of", "by", "up", "as", "if", "is", "it",
    "be", "am", "are", "was", "were", "been", "being", "do", "did",
    "does", "done", "has", "had", "have", "having", "he", "she", "we",
    "me", "my", "her", "his", "its", "our", "us", "they", "them",
    "their", "you", "your", "who", "what", "that", "this", "with",
    "from", "not", "no", "can", "will", "would", "could", "should",
    "may", "might", "shall", "just", "how", "when", "where", "why",
    "all", "each", "every", "some", "any", "than", "then", "too",
    "also", "very", "more", "most", "much", "many", "such", "own",
    "same", "other", "about", "into", "over", "after", "before",
    "through", "between", "under", "again", "out", "off", "here",
    "there", "which", "these", "those", "only", "im", "ive", "ill",
    "id", "dont", "wont", "cant", "didnt", "isnt", "wasnt", "youre",
    "youve", "youll", "youd", "hes", "shes", "weve", "theyre",
    "theyve", "theyll", "aint", "gonna", "wanna", "gotta",
    # Common song filler / vocables
    "oh", "ooh", "ah", "ahh", "yeah", "yea", "hey", "na", "la",
    "da", "uh", "huh", "mmm", "whoa", "wo", "yo",
    # Ubiquitous song vocabulary — too common to flag
    "love", "heart", "baby", "night", "day", "time", "life", "way",
    "feel", "know", "see", "come", "go", "get", "got", "let", "take",
    "make", "say", "said", "back", "down", "like", "right", "left",
    "good", "new", "now", "one", "two", "still", "never", "ever",
    "keep", "need", "want", "look", "think", "thought", "mind",
    "world", "man", "eye", "eyes", "hand", "hands",
})


def _tokenize_lyrics_by_line(lyrics: str) -> list:
    """Split lyrics into per-line word lists, skipping section tags.

    Lowercases all words, strips leading/trailing apostrophes, and filters
    out single-character tokens.
    """
    result = []
    for line in lyrics.split("\n"):
        stripped = line.strip()
        if not stripped or _SECTION_TAG_RE.match(stripped):
            continue
        words = []
        for token in _WORD_TOKEN_RE.findall(stripped.lower()):
            # Strip leading/trailing apostrophes (e.g., 'bout -> bout)
            clean = token.strip("'")
            if len(clean) > 1:
                words.append(clean)
        if words:
            result.append(words)
    return result


def _ngrams_from_lines(lines: list, min_n: int = 2, max_n: int = 4) -> list:
    """Generate n-grams from per-line word lists, never crossing line boundaries.

    Skips n-grams where every word is a stopword.
    """
    phrases = []
    for words in lines:
        for n in range(min_n, max_n + 1):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]
                # Skip if all words are stopwords
                if all(w in _CROSS_TRACK_STOPWORDS for w in gram):
                    continue
                phrases.append(" ".join(gram))
    return phrases


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


@mcp.tool()
async def check_cross_track_repetition(
    album_slug: str,
    min_tracks: int = 3,
) -> str:
    """Scan all tracks in an album for words/phrases repeated across multiple tracks.

    Extracts lyrics from every track, tokenizes into words and 2-4 word
    n-grams, and flags items appearing in N+ tracks. Filters out stopwords
    and common song vocabulary automatically.

    Args:
        album_slug: Album slug (e.g., "my-album")
        min_tracks: Minimum number of tracks a word/phrase must appear in
                    to be flagged (default 3, floor 2)

    Returns:
        JSON with flagged words, phrases, and summary stats
    """
    # Floor min_tracks at 2 — repeating in 1 track is not cross-track
    if min_tracks < 2:
        min_tracks = 2

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
    if not all_tracks:
        return _safe_json({
            "found": True,
            "album_slug": normalized_album,
            "track_count": 0,
            "min_tracks_threshold": min_tracks,
            "repeated_words": [],
            "repeated_phrases": [],
            "summary": {
                "flagged_words": 0,
                "flagged_phrases": 0,
                "most_repeated_word": None,
                "most_repeated_phrase": None,
            },
        })

    # Per-track word and phrase sets, plus occurrence counts
    # word -> set of track slugs where it appears
    word_tracks: dict[str, set] = {}
    # word -> total count across all tracks
    word_total: dict[str, int] = {}
    # phrase -> set of track slugs
    phrase_tracks: dict[str, set] = {}
    # phrase -> total count across all tracks
    phrase_total: dict[str, int] = {}

    tracks_analyzed = 0

    for t_slug, t_data in sorted(all_tracks.items()):
        track_path = t_data.get("path", "")
        if not track_path:
            continue

        try:
            text = Path(track_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Extract Lyrics Box
        lyrics_section = _extract_markdown_section(text, "Lyrics Box")
        lyrics = ""
        if lyrics_section:
            code = _extract_code_block(lyrics_section)
            lyrics = code if code else lyrics_section

        if not lyrics.strip():
            continue

        tracks_analyzed += 1
        lines = _tokenize_lyrics_by_line(lyrics)

        # Count words for this track
        track_word_counts: dict[str, int] = {}
        for words in lines:
            for w in words:
                track_word_counts[w] = track_word_counts.get(w, 0) + 1

        for w, count in track_word_counts.items():
            if w not in word_tracks:
                word_tracks[w] = set()
                word_total[w] = 0
            word_tracks[w].add(t_slug)
            word_total[w] += count

        # Count phrases for this track
        phrases = _ngrams_from_lines(lines)
        track_phrase_counts: dict[str, int] = {}
        for p in phrases:
            track_phrase_counts[p] = track_phrase_counts.get(p, 0) + 1

        for p, count in track_phrase_counts.items():
            if p not in phrase_tracks:
                phrase_tracks[p] = set()
                phrase_total[p] = 0
            phrase_tracks[p].add(t_slug)
            phrase_total[p] += count

    # Filter to items in >= min_tracks, exclude stopwords for words
    repeated_words = []
    for w, track_set in word_tracks.items():
        if len(track_set) >= min_tracks and w not in _CROSS_TRACK_STOPWORDS:
            repeated_words.append({
                "word": w,
                "track_count": len(track_set),
                "tracks": sorted(track_set),
                "total_occurrences": word_total[w],
            })

    repeated_phrases = []
    for p, track_set in phrase_tracks.items():
        if len(track_set) >= min_tracks:
            repeated_phrases.append({
                "phrase": p,
                "track_count": len(track_set),
                "tracks": sorted(track_set),
                "total_occurrences": phrase_total[p],
            })

    # Sort by track_count descending, then alphabetically
    repeated_words.sort(key=lambda x: (-x["track_count"], x["word"]))
    repeated_phrases.sort(key=lambda x: (-x["track_count"], x["phrase"]))

    summary = {
        "flagged_words": len(repeated_words),
        "flagged_phrases": len(repeated_phrases),
        "most_repeated_word": repeated_words[0] if repeated_words else None,
        "most_repeated_phrase": repeated_phrases[0] if repeated_phrases else None,
    }

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "track_count": tracks_analyzed,
        "min_tracks_threshold": min_tracks,
        "repeated_words": repeated_words,
        "repeated_phrases": repeated_phrases,
        "summary": summary,
    })


# =============================================================================
# Plagiarism / Distinctive Phrase Extraction
# =============================================================================

# Common song cliches — phrases so ubiquitous they're not useful plagiarism signals.
_COMMON_SONG_PHRASES = frozenset({
    # Love / heartbreak
    "break my heart", "broke my heart", "breaking my heart",
    "falling in love", "fall in love", "fell in love",
    "heart and soul", "heart on my sleeve",
    "love you forever", "love you more",
    "hold me close", "hold me tight",
    "never let go", "never let you go",
    "take my hand", "hold my hand",
    "tear me apart", "tore me apart",
    "missing you tonight", "thinking of you",
    "all my love", "give my love",
    "you and me", "me and you",
    # Night / time
    "middle of the night", "dead of night",
    "end of the world", "end of time",
    "light of day", "break of dawn",
    "run out of time", "running out of time",
    "turn back time", "stand the test of time",
    "day and night", "night and day",
    # Pain / struggle
    "pain inside", "pain in my heart",
    "down on my knees", "brought to my knees",
    "weight of the world", "world on my shoulders",
    "lost my mind", "losing my mind",
    "break me down", "breaking me down",
    "pick me up", "lift me up",
    "fight for you", "fight for love",
    "set me free", "set you free",
    "let me go", "let it go",
    # Movement / journey
    "walking away", "walk away",
    "running away", "run away",
    "long way home", "find my way",
    "find my way home", "find my way back",
    "road to nowhere", "path to follow",
    # Fire / light
    "burning inside", "fire inside",
    "light in the dark", "light in the darkness",
    "shine so bright", "shining bright",
    "spark in the dark",
    # Generic emotional
    "cant stop thinking", "cant get enough",
    "never be the same", "nothing is the same",
    "over and over", "again and again",
    "round and round", "on and on",
    "the way you make me feel",
    "what you do to me", "what you mean to me",
    "take me away", "far away",
    "here with me", "stay with me",
    "come back to me", "back to you",
    "all night long", "tonight tonight",
    "dreams come true", "make it through",
    "side by side", "hand in hand",
    "once upon a time", "happily ever after",
})

# Section priority for ranking phrase importance.
# Higher = more important for plagiarism (chorus hooks matter most).
_SECTION_PRIORITY = {
    "chorus": 3,
    "hook": 3,
    "pre-chorus": 2,
    "bridge": 2,
    "outro": 2,
    "verse": 1,
    "intro": 1,
}


def _tokenize_lyrics_with_sections(lyrics: str) -> list:
    """Split lyrics into per-line dicts tracking section context.

    Returns a list of dicts, each with:
        section: str — current section name (e.g., "Chorus", "Verse 1")
        section_type: str — normalized type (e.g., "chorus", "verse")
        line_number: int — 1-based line number in original text
        words: list[str] — lowercased, cleaned word tokens
        raw_line: str — original line text (stripped)
    """
    result = []
    current_section = "Unknown"
    current_section_type = "verse"  # default

    for line_num, line in enumerate(lyrics.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            continue

        # Check for section tag
        if _SECTION_TAG_RE.match(stripped):
            # Extract section name from brackets
            current_section = stripped[1:-1].strip()
            # Normalize section type (strip numbers: "Verse 2" -> "verse")
            section_lower = current_section.lower()
            # Check longest keys first so "pre-chorus" matches before "chorus"
            for stype in sorted(_SECTION_PRIORITY, key=len, reverse=True):
                if stype in section_lower:
                    current_section_type = stype
                    break
            else:
                current_section_type = "verse"  # default for unknown sections
            continue

        # Tokenize the line
        words = []
        for token in _WORD_TOKEN_RE.findall(stripped.lower()):
            clean = token.strip("'")
            if len(clean) > 1:
                words.append(clean)

        if words:
            result.append({
                "section": current_section,
                "section_type": current_section_type,
                "line_number": line_num,
                "words": words,
                "raw_line": stripped,
            })

    return result


def _extract_distinctive_ngrams(
    lines_with_sections: list,
    min_n: int = 4,
    max_n: int = 7,
) -> list:
    """Extract distinctive n-grams from section-aware tokenized lines.

    Generates n-grams of length min_n..max_n, filters out:
      - n-grams where ALL words are stopwords
      - n-grams matching common song cliches
    Deduplicates by keeping the highest-priority section occurrence.
    Returns sorted by priority descending, then word count descending.
    """
    # phrase -> best entry (highest priority)
    seen: dict = {}

    for line_data in lines_with_sections:
        words = line_data["words"]
        priority = _SECTION_PRIORITY.get(line_data["section_type"], 1)

        for n in range(min_n, max_n + 1):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]

                # Skip if all stopwords
                if all(w in _CROSS_TRACK_STOPWORDS for w in gram):
                    continue

                phrase = " ".join(gram)

                # Skip common song cliches
                if phrase in _COMMON_SONG_PHRASES:
                    continue

                # Keep highest-priority occurrence
                if phrase not in seen or priority > seen[phrase]["priority"]:
                    seen[phrase] = {
                        "phrase": phrase,
                        "word_count": n,
                        "section": line_data["section"],
                        "section_type": line_data["section_type"],
                        "line_number": line_data["line_number"],
                        "raw_line": line_data["raw_line"],
                        "priority": priority,
                    }

    # Sort: priority desc, word_count desc, phrase asc
    results = sorted(
        seen.values(),
        key=lambda x: (-x["priority"], -x["word_count"], x["phrase"]),
    )
    return results


@mcp.tool()
async def extract_distinctive_phrases(text: str) -> str:
    """Extract distinctive phrases from lyrics for plagiarism checking.

    Takes raw lyrics text, extracts 4-7 word n-grams with section awareness,
    filters common song cliches and stopword-only phrases, and ranks by
    section priority (chorus/hook > verse). Returns phrases and pre-formatted
    web search suggestions.

    Args:
        text: Lyrics text to scan (with [Section] tags)

    Returns:
        JSON with {phrases: [...], total_phrases: int,
                   sections_found: [...], search_suggestions: [...]}
    """
    if not text or not text.strip():
        return _safe_json({
            "phrases": [],
            "total_phrases": 0,
            "sections_found": [],
            "search_suggestions": [],
        })

    # Tokenize with section tracking
    lines = _tokenize_lyrics_with_sections(text)

    # Extract distinctive n-grams
    ngrams = _extract_distinctive_ngrams(lines)

    # Collect unique sections found
    sections_found = sorted({
        line_data["section"]
        for line_data in lines
    })

    # Build phrases list
    phrases = []
    for ng in ngrams:
        phrases.append({
            "phrase": ng["phrase"],
            "word_count": ng["word_count"],
            "section": ng["section"],
            "line_number": ng["line_number"],
            "raw_line": ng["raw_line"],
            "priority": ng["priority"],
        })

    # Build search suggestions — top 15, formatted for WebSearch
    search_suggestions = []
    for ng in ngrams[:15]:
        search_suggestions.append({
            "query": f'"{ng["phrase"]}" lyrics',
            "priority": ng["priority"],
            "section": ng["section"],
        })

    return _safe_json({
        "phrases": phrases,
        "total_phrases": len(phrases),
        "sections_found": sections_found,
        "search_suggestions": search_suggestions,
    })


# ---------------------------------------------------------------------------
# Lyrics Analysis Helpers
# ---------------------------------------------------------------------------

def _count_syllables_word(word: str) -> int:
    """Count syllables in a single word using vowel cluster heuristic.

    Rules:
    1. Count vowel groups (aeiouy; consecutive vowels = 1 group)
    2. Subtract trailing silent 'e' if count > 1
    3. Handle consonant-'le' endings (bottle, apple — add 1)
    4. Floor at 1
    """
    if not word:
        return 0
    word = word.lower().strip("'")
    if not word:
        return 0

    vowels = set("aeiouy")
    count = 0
    prev_vowel = False

    for char in word:
        if char in vowels:
            if not prev_vowel:
                count += 1
            prev_vowel = True
        else:
            prev_vowel = False

    # Silent 'e' at end
    if word.endswith("e") and count > 1:
        count -= 1

    # Consonant + 'le' endings (bottle, apple, little)
    if len(word) >= 3 and word.endswith("le") and word[-3] not in vowels:
        count += 1

    return max(count, 1)


def _get_rhyme_tail(word: str) -> str:
    """Extract rhyme tail from last vowel cluster to end of word.

    Strips trailing 's' for plural tolerance before extracting.
    Examples: "night" -> "ight", "away" -> "ay", "desire" -> "ire"
    """
    if not word:
        return ""
    word = word.lower().strip("'")
    if not word:
        return ""

    # Strip trailing 's' for plural tolerance
    if len(word) > 2 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]

    vowels = set("aeiouy")

    # Handle silent 'e' — if word ends with consonant + 'e', find the
    # vowel cluster before the 'e' but include 'e' in the returned tail
    scan_word = word
    if len(word) > 2 and word.endswith("e") and word[-2] not in vowels:
        scan_word = word[:-1]

    # Find last vowel cluster start in scan_word
    last_vowel_pos = -1
    for i in range(len(scan_word) - 1, -1, -1):
        if scan_word[i] in vowels:
            last_vowel_pos = i
            # Walk back through consecutive vowels
            while i > 0 and scan_word[i - 1] in vowels:
                i -= 1
                last_vowel_pos = i
            break

    if last_vowel_pos < 0:
        return word  # No vowels — return whole word

    # Return from vowel position to end of ORIGINAL word
    return word[last_vowel_pos:]


def _words_rhyme(w1: str, w2: str) -> bool:
    """Check if two words rhyme by comparing rhyme tails.

    Requires tails >= 2 chars. Identical words return False
    (flagged as self-rhyme separately).
    """
    if not w1 or not w2:
        return False
    w1_clean = w1.lower().strip("'")
    w2_clean = w2.lower().strip("'")
    if w1_clean == w2_clean:
        return False
    tail1 = _get_rhyme_tail(w1)
    tail2 = _get_rhyme_tail(w2)
    if len(tail1) < 2 or len(tail2) < 2:
        return False
    return tail1 == tail2


@mcp.tool()
async def count_syllables(text: str) -> str:
    """Get syllable counts per line with section tracking and consistency analysis.

    Parses lyrics by section, counts syllables per line, and calculates
    consistency (stdev > 3 = "UNEVEN").

    Args:
        text: Lyrics text to analyze (with [Section] tags)

    Returns:
        JSON with {sections: [{section, lines: [{line_number, text,
        syllable_count, word_count}], avg_syllables_per_line, line_count}],
        summary: {total_syllables, total_lines, avg_syllables_per_line,
        min_line, max_line, consistency}}
    """
    if not text or not text.strip():
        return _safe_json({
            "sections": [],
            "summary": {
                "total_syllables": 0,
                "total_lines": 0,
                "avg_syllables_per_line": 0,
                "min_line": 0,
                "max_line": 0,
                "consistency": "N/A",
            },
        })

    sections = []
    current_section = "Unknown"
    current_lines = []
    all_syllable_counts = []

    for line_num, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            continue

        if _SECTION_TAG_RE.match(stripped):
            # Save previous section if it has lines
            if current_lines:
                avg = sum(l["syllable_count"] for l in current_lines) / len(current_lines)
                sections.append({
                    "section": current_section,
                    "lines": current_lines,
                    "avg_syllables_per_line": round(avg, 1),
                    "line_count": len(current_lines),
                })
            current_section = stripped[1:-1].strip()
            current_lines = []
            continue

        # Count syllables for this line
        words = _WORD_TOKEN_RE.findall(stripped)
        syllable_count = sum(_count_syllables_word(w) for w in words)
        all_syllable_counts.append(syllable_count)

        current_lines.append({
            "line_number": line_num,
            "text": stripped,
            "syllable_count": syllable_count,
            "word_count": len(words),
        })

    # Don't forget last section
    if current_lines:
        avg = sum(l["syllable_count"] for l in current_lines) / len(current_lines)
        sections.append({
            "section": current_section,
            "lines": current_lines,
            "avg_syllables_per_line": round(avg, 1),
            "line_count": len(current_lines),
        })

    # Summary
    total_syllables = sum(all_syllable_counts)
    total_lines = len(all_syllable_counts)
    avg_overall = round(total_syllables / total_lines, 1) if total_lines else 0
    min_line = min(all_syllable_counts) if all_syllable_counts else 0
    max_line = max(all_syllable_counts) if all_syllable_counts else 0

    if total_lines >= 2:
        stdev = statistics.stdev(all_syllable_counts)
        consistency = "UNEVEN" if stdev > 3 else "CONSISTENT"
    else:
        consistency = "N/A"

    return _safe_json({
        "sections": sections,
        "summary": {
            "total_syllables": total_syllables,
            "total_lines": total_lines,
            "avg_syllables_per_line": avg_overall,
            "min_line": min_line,
            "max_line": max_line,
            "consistency": consistency,
        },
    })


@mcp.tool()
async def analyze_readability(text: str) -> str:
    """Analyze readability of lyrics text using Flesch Reading Ease.

    Reuses _count_syllables_word. Pure math — no NLP dependencies.

    Args:
        text: Lyrics text to analyze (with or without [Section] tags)

    Returns:
        JSON with {word_stats: {total_words, unique_words, vocabulary_richness,
        avg_word_length, avg_syllables_per_word}, line_stats: {total_lines,
        avg_words_per_line, min_words_line, max_words_line},
        readability: {flesch_reading_ease, grade_level, assessment}}
    """
    if not text or not text.strip():
        return _safe_json({
            "word_stats": {
                "total_words": 0,
                "unique_words": 0,
                "vocabulary_richness": 0,
                "avg_word_length": 0,
                "avg_syllables_per_word": 0,
            },
            "line_stats": {
                "total_lines": 0,
                "avg_words_per_line": 0,
                "min_words_line": 0,
                "max_words_line": 0,
            },
            "readability": {
                "flesch_reading_ease": 0,
                "grade_level": "N/A",
                "assessment": "No content to analyze",
            },
        })

    all_words = []
    words_per_line = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or _SECTION_TAG_RE.match(stripped):
            continue
        words = _WORD_TOKEN_RE.findall(stripped)
        if words:
            all_words.extend(words)
            words_per_line.append(len(words))

    if not all_words:
        return _safe_json({
            "word_stats": {
                "total_words": 0,
                "unique_words": 0,
                "vocabulary_richness": 0,
                "avg_word_length": 0,
                "avg_syllables_per_word": 0,
            },
            "line_stats": {
                "total_lines": 0,
                "avg_words_per_line": 0,
                "min_words_line": 0,
                "max_words_line": 0,
            },
            "readability": {
                "flesch_reading_ease": 0,
                "grade_level": "N/A",
                "assessment": "No content to analyze",
            },
        })

    total_words = len(all_words)
    unique_words = len(set(w.lower() for w in all_words))
    total_syllables = sum(_count_syllables_word(w) for w in all_words)
    total_lines = len(words_per_line)

    avg_word_length = round(
        sum(len(w) for w in all_words) / total_words, 1
    )
    avg_syllables_per_word = round(total_syllables / total_words, 2)
    vocabulary_richness = round(unique_words / total_words, 2)

    avg_words_per_line = round(total_words / total_lines, 1)
    min_words_line = min(words_per_line)
    max_words_line = max(words_per_line)

    # Flesch Reading Ease
    asl = total_words / total_lines  # avg sentence (line) length
    asw = total_syllables / total_words  # avg syllables per word
    flesch = round(206.835 - (1.015 * asl) - (84.6 * asw), 1)

    # Grade level assessment
    if flesch >= 90:
        grade_level = "Very Easy"
        assessment = "Very easy to read — conversational, accessible lyrics"
    elif flesch >= 80:
        grade_level = "Easy"
        assessment = "Easy to read — clear, natural language"
    elif flesch >= 70:
        grade_level = "Standard"
        assessment = "Standard readability — well-crafted lyrics"
    elif flesch >= 60:
        grade_level = "Moderate"
        assessment = "Moderately complex — dense or literary vocabulary"
    else:
        grade_level = "Complex"
        assessment = "Complex vocabulary — may challenge listeners on first hearing"

    return _safe_json({
        "word_stats": {
            "total_words": total_words,
            "unique_words": unique_words,
            "vocabulary_richness": vocabulary_richness,
            "avg_word_length": avg_word_length,
            "avg_syllables_per_word": avg_syllables_per_word,
        },
        "line_stats": {
            "total_lines": total_lines,
            "avg_words_per_line": avg_words_per_line,
            "min_words_line": min_words_line,
            "max_words_line": max_words_line,
        },
        "readability": {
            "flesch_reading_ease": flesch,
            "grade_level": grade_level,
            "assessment": assessment,
        },
    })


@mcp.tool()
async def analyze_rhyme_scheme(text: str) -> str:
    """Analyze rhyme scheme of lyrics with section awareness.

    Parses by section, extracts end words, builds rhyme groups (A/B/C letters),
    and detects self-rhymes.

    Args:
        text: Lyrics text to analyze (with [Section] tags)

    Returns:
        JSON with {sections: [{section, section_type, scheme, lines: [{line_number,
        end_word, rhyme_group, rhyme_tail}], issues: []}],
        issues: [{type, section, line_numbers, word, severity}],
        summary: {total_sections, sections_with_issues, self_rhymes}}
    """
    if not text or not text.strip():
        return _safe_json({
            "sections": [],
            "issues": [],
            "summary": {
                "total_sections": 0,
                "sections_with_issues": 0,
                "self_rhymes": 0,
            },
        })

    # Parse into sections using _tokenize_lyrics_with_sections
    tokenized = _tokenize_lyrics_with_sections(text)

    # Group by section
    section_groups = {}
    section_order = []
    for entry in tokenized:
        sec = entry["section"]
        if sec not in section_groups:
            section_groups[sec] = {
                "section": sec,
                "section_type": entry["section_type"],
                "entries": [],
            }
            section_order.append(sec)
        section_groups[sec]["entries"].append(entry)

    all_issues = []
    result_sections = []

    for sec_name in section_order:
        group = section_groups[sec_name]
        entries = group["entries"]
        section_type = group["section_type"]

        # Extract end words
        end_words = []
        for entry in entries:
            if entry["words"]:
                end_words.append({
                    "line_number": entry["line_number"],
                    "end_word": entry["words"][-1],
                    "rhyme_tail": _get_rhyme_tail(entry["words"][-1]),
                })

        # Build rhyme groups
        rhyme_labels = {}  # rhyme_tail -> label letter
        next_label = 0
        lines_data = []

        for ew in end_words:
            tail = ew["rhyme_tail"]
            # Find matching group
            assigned = False
            for existing_tail, label in rhyme_labels.items():
                if len(tail) >= 2 and len(existing_tail) >= 2 and tail == existing_tail:
                    lines_data.append({
                        "line_number": ew["line_number"],
                        "end_word": ew["end_word"],
                        "rhyme_group": label,
                        "rhyme_tail": tail,
                    })
                    assigned = True
                    break

            if not assigned:
                label = chr(ord("A") + next_label) if next_label < 26 else f"Z{next_label}"
                next_label += 1
                rhyme_labels[tail] = label
                lines_data.append({
                    "line_number": ew["line_number"],
                    "end_word": ew["end_word"],
                    "rhyme_group": label,
                    "rhyme_tail": tail,
                })

        scheme = "".join(ld["rhyme_group"] for ld in lines_data)

        # Detect issues within this section
        section_issues = []

        # Self-rhymes: same word used as end word in multiple lines
        word_lines = {}
        for ld in lines_data:
            w = ld["end_word"].lower()
            if w not in word_lines:
                word_lines[w] = []
            word_lines[w].append(ld["line_number"])

        for w, lnums in word_lines.items():
            if len(lnums) > 1:
                issue = {
                    "type": "self_rhyme",
                    "section": sec_name,
                    "line_numbers": lnums,
                    "word": w,
                    "severity": "warning",
                }
                section_issues.append(issue)
                all_issues.append(issue)

        result_sections.append({
            "section": sec_name,
            "section_type": section_type,
            "scheme": scheme,
            "lines": lines_data,
            "issues": section_issues,
        })

    # Summary counts
    self_rhymes = sum(1 for i in all_issues if i["type"] == "self_rhyme")
    sections_with_issues = sum(1 for s in result_sections if s["issues"])

    return _safe_json({
        "sections": result_sections,
        "issues": all_issues,
        "summary": {
            "total_sections": len(result_sections),
            "sections_with_issues": sections_with_issues,
            "self_rhymes": self_rhymes,
        },
    })


@mcp.tool()
async def validate_section_structure(text: str) -> str:
    """Validate section structure of lyrics.

    Checks: valid tags present, balanced section lengths (V1 vs V2 diff > 2
    lines flagged), empty sections, duplicate consecutive tags.

    Args:
        text: Lyrics text to validate (with [Section] tags)

    Returns:
        JSON with {sections: [{tag, line_number, content_lines, section_type}],
        issues: [{type, sections/tag, line_number, severity}],
        summary: {total_sections, has_verse, has_chorus, has_bridge,
        issues_count, section_balance}}
    """
    if not text or not text.strip():
        return _safe_json({
            "sections": [],
            "issues": [{
                "type": "no_content",
                "tag": None,
                "line_number": 0,
                "severity": "error",
            }],
            "summary": {
                "total_sections": 0,
                "has_verse": False,
                "has_chorus": False,
                "has_bridge": False,
                "issues_count": 1,
                "section_balance": "N/A",
            },
        })

    sections = []
    issues = []
    current_tag = None
    current_tag_line = 0
    content_line_count = 0
    prev_tag = None

    lines = text.split("\n")

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        if _SECTION_TAG_RE.match(stripped):
            # Save previous section or warn about untagged content
            if current_tag is None and content_line_count > 0:
                issues.append({
                    "type": "content_before_first_tag",
                    "tag": None,
                    "line_number": 1,
                    "severity": "warning",
                })
            if current_tag is not None:
                # Check for empty section
                if content_line_count == 0:
                    issues.append({
                        "type": "empty_section",
                        "tag": current_tag,
                        "line_number": current_tag_line,
                        "severity": "warning",
                    })
                tag_name = current_tag[1:-1].strip()
                section_lower = tag_name.lower()
                section_type = "verse"
                for stype in sorted(_SECTION_PRIORITY, key=len, reverse=True):
                    if stype in section_lower:
                        section_type = stype
                        break
                sections.append({
                    "tag": current_tag,
                    "line_number": current_tag_line,
                    "content_lines": content_line_count,
                    "section_type": section_type,
                })

            # Check for duplicate consecutive tags
            if stripped == prev_tag:
                issues.append({
                    "type": "duplicate_consecutive_tag",
                    "tag": stripped,
                    "line_number": line_num,
                    "severity": "error",
                })

            prev_tag = stripped
            current_tag = stripped
            current_tag_line = line_num
            content_line_count = 0

        elif stripped:
            content_line_count += 1

    # Save last section
    if current_tag is not None:
        if content_line_count == 0:
            issues.append({
                "type": "empty_section",
                "tag": current_tag,
                "line_number": current_tag_line,
                "severity": "warning",
            })
        tag_name = current_tag[1:-1].strip()
        section_lower = tag_name.lower()
        section_type = "verse"
        for stype in sorted(_SECTION_PRIORITY, key=len, reverse=True):
            if stype in section_lower:
                section_type = stype
                break
        sections.append({
            "tag": current_tag,
            "line_number": current_tag_line,
            "content_lines": content_line_count,
            "section_type": section_type,
        })

    # Check for no section tags at all
    if not sections:
        issues.append({
            "type": "no_section_tags",
            "tag": None,
            "line_number": 0,
            "severity": "warning",
        })

    # Detect section types present
    types_present = {s["section_type"] for s in sections}
    has_verse = "verse" in types_present
    has_chorus = "chorus" in types_present or "hook" in types_present
    has_bridge = "bridge" in types_present

    # Check missing common sections
    if sections and not has_verse:
        issues.append({
            "type": "missing_verse",
            "tag": None,
            "line_number": 0,
            "severity": "info",
        })
    if sections and not has_chorus:
        issues.append({
            "type": "missing_chorus",
            "tag": None,
            "line_number": 0,
            "severity": "info",
        })

    # Check section balance — compare verse lengths
    verse_sections = [s for s in sections if s["section_type"] == "verse"]
    section_balance = "BALANCED"
    if len(verse_sections) >= 2:
        lengths = [s["content_lines"] for s in verse_sections]
        max_diff = max(lengths) - min(lengths)
        if max_diff > 2:
            section_balance = "UNBALANCED"
            # Find the unbalanced pair
            issues.append({
                "type": "unbalanced_sections",
                "sections": [s["tag"] for s in verse_sections],
                "line_number": verse_sections[0]["line_number"],
                "severity": "warning",
                "detail": f"Verse line counts vary by {max_diff} lines: {lengths}",
            })

    return _safe_json({
        "sections": sections,
        "issues": issues,
        "summary": {
            "total_sections": len(sections),
            "has_verse": has_verse,
            "has_chorus": has_chorus,
            "has_bridge": has_bridge,
            "issues_count": len(issues),
            "section_balance": section_balance,
        },
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
            "status": album.get("status", STATUS_UNKNOWN),
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
            "status": track.get("status", STATUS_UNKNOWN),
            "explicit": track.get("explicit", False),
            "has_suno_link": track.get("has_suno_link", False),
            "sources_verified": track.get("sources_verified", "N/A"),
            "path": track.get("path", ""),
        }

        # Read sections from disk if requested
        if sections and track.get("path"):
            try:
                file_text = Path(track["path"]).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read track file %s: %s", track["path"], e)
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

    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")
    album_path = album.get("path", "")
    genre = album.get("genre", "")
    audio_path = str(Path(audio_root) / "artists" / artist / "albums" / genre / normalized)

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
        wrong_path = Path(audio_root) / artist / normalized  # old flat structure

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
            status = t_data.get("status", STATUS_UNKNOWN)
            has_link = t_data.get("has_suno_link", False)
            sources = t_data.get("sources_verified", "N/A")

            track_issues = []
            if status in TRACK_COMPLETED_STATUSES and not has_link:
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
    genre_slug = _GENRE_ALIASES.get(genre_slug, genre_slug)

    gen_cfg = config.get("generation", {})
    additional = set(gen_cfg.get("additional_genres", []))
    all_genres = _VALID_GENRES | additional
    if genre_slug not in all_genres:
        return _safe_json({
            "error": f"Invalid genre '{genre}'. Valid genres: {', '.join(sorted(all_genres))}",
            "hint": "Use a primary genre, or add custom genres via "
                    "generation.additional_genres in config.",
        })

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


def _check_pre_gen_gates_for_track(
    t_data: dict, file_text: Optional[str], blocklist: list,
    max_lyric_words: int = 800,
) -> tuple[int, int, list[dict]]:
    """Run pre-generation gates on a single track.

    Returns (blocking_count, warning_count, gates_list).
    """
    gates: list[dict] = []
    blocking = 0
    warning_count = 0

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
        gates.append({"gate": "Explicit Flag Set", "status": "FAIL", "severity": "BLOCKING",
                      "detail": "Explicit field not set — set to Yes or No before generating"})
        blocking += 1
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

    # Gate 6: Artist Names Cleared (uses pre-compiled patterns)
    if style_content:
        found_artists = []
        for entry in blocklist:
            name = entry["name"]
            pattern = _artist_blocklist_patterns.get(name)
            if pattern and pattern.search(style_content):
                found_artists.append(name)

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

    # Gate 7: Homograph Check — scan lyrics for unresolved homographs
    if lyrics_content and lyrics_content.strip():
        found_homographs = []
        for line in lyrics_content.split("\n"):
            stripped = line.strip()
            # Skip section tags like [Verse 1], [Chorus], etc.
            if stripped.startswith("[") and stripped.endswith("]"):
                continue
            for word, pattern in _HOMOGRAPH_PATTERNS.items():
                if pattern.search(line):
                    if word not in found_homographs:
                        found_homographs.append(word)
        if found_homographs:
            gates.append({"gate": "Homograph Check", "status": "FAIL", "severity": "BLOCKING",
                          "detail": f"Unresolved homographs: {', '.join(found_homographs)}"})
            blocking += 1
        else:
            gates.append({"gate": "Homograph Check", "status": "PASS",
                          "detail": "No homograph risks found"})
    elif not lyrics_content or not lyrics_content.strip():
        gates.append({"gate": "Homograph Check", "status": "SKIP",
                      "detail": "No lyrics to check"})

    # Gate 8: Lyric Length — configurable word count limit
    if lyrics_content and lyrics_content.strip():
        lyric_words = [
            w for line in lyrics_content.split("\n")
            if line.strip() and not _SECTION_TAG_RE.match(line.strip())
            for w in line.split() if w
        ]
        wc = len(lyric_words)
        if wc > max_lyric_words:
            gates.append({"gate": "Lyric Length", "status": "FAIL", "severity": "BLOCKING",
                          "detail": f"Lyrics are {wc} words — limit is {max_lyric_words}"})
            blocking += 1
        else:
            gates.append({"gate": "Lyric Length", "status": "PASS",
                          "detail": f"{wc} words (limit {max_lyric_words})"})
    else:
        gates.append({"gate": "Lyric Length", "status": "SKIP",
                      "detail": "No lyrics to check"})

    return blocking, warning_count, gates


@mcp.tool()
async def run_pre_generation_gates(
    album_slug: str,
    track_slug: str = "",
) -> str:
    """Run all 8 pre-generation validation gates on a track or album.

    Gates:
        1. Sources Verified — sources_verified is not "Pending"
        2. Lyrics Reviewed — Lyrics Box populated, no [TODO]/[PLACEHOLDER]
        3. Pronunciation Resolved — All Pronunciation Notes entries applied
        4. Explicit Flag Set — Explicit field is "Yes" or "No"
        5. Style Prompt Complete — Non-empty Style Box with content
        6. Artist Names Cleared — No real artist names in Style Box
        7. Homograph Check — No unresolved homographs in lyrics
        8. Lyric Length — Lyrics under 800-word Suno limit

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

    # Read configurable gate limits
    state_config = state.get("config", {})
    gen_cfg = state_config.get("generation", {})
    max_lyric_words = gen_cfg.get("max_lyric_words", 800)

    track_results = []
    total_blocking = 0
    total_warnings = 0

    for t_slug, t_data in sorted(tracks_to_check.items()):
        # Read track file if available
        file_text = None
        track_path = t_data.get("path", "")
        if track_path:
            try:
                file_text = Path(track_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read track file for pre-gen gates %s: %s", track_path, e)

        blocking, warning_count, gates = _check_pre_gen_gates_for_track(
            t_data, file_text, blocklist,
            max_lyric_words=max_lyric_words,
        )

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
    elif any(t["blocking"] == 0 for t in track_results):
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


# =============================================================================
# Release Readiness Checks
# =============================================================================

# Template placeholder markers — if streaming lyrics contain these, the section
# hasn't been filled in yet.
_STREAMING_PLACEHOLDER_MARKERS = [
    "Plain lyrics here",
    "Capitalize first letter of each line",
    "No end punctuation",
    "Write out all repeats fully",
    "Blank lines between sections only",
]

# End-of-line punctuation that shouldn't appear in streaming lyrics.
# Ellipsis (...) is allowed, so we match single trailing punctuation only.
_END_PUNCT_RE = re.compile(r'[.,:;!?]$')


@mcp.tool()
async def check_streaming_lyrics(album_slug: str, track_slug: str = "") -> str:
    """Check streaming lyrics readiness for an album's tracks.

    Validates that each track has properly formatted streaming lyrics
    (plain text for Spotify/Apple Music). Runs 7 checks per track:
        1. Section Exists — "Streaming Lyrics" heading found
        2. Not Empty — Code block has content beyond whitespace
        3. Not Placeholder — Content doesn't match template placeholder
        4. No Section Tags — No [Verse], [Chorus] etc. lines
        5. Lines Capitalized — Non-blank lines start uppercase
        6. No End Punctuation — Lines don't end with .,:;!? (ellipsis allowed)
        7. Word Count — >= 20 words; if Suno Lyrics exist, >= 80% of Suno count

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Specific track slug/number (empty = all tracks)

    Returns:
        JSON with per-track check results and verdicts
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

    track_results = []
    total_blocking = 0
    total_warnings = 0

    for t_slug, t_data in sorted(tracks_to_check.items()):
        checks = []
        blocking = 0
        warning_count = 0
        streaming_word_count = 0
        suno_word_count = 0

        # Read track file
        file_text = None
        track_path = t_data.get("path", "")
        if track_path:
            try:
                file_text = Path(track_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read track file for streaming check %s: %s",
                               track_path, e)

        # Extract streaming lyrics section
        streaming_content = None
        if file_text:
            streaming_section = _extract_markdown_section(file_text, "Streaming Lyrics")
            if streaming_section:
                streaming_content = _extract_code_block(streaming_section)

        # Check 1: Section Exists
        if not file_text:
            checks.append({"check": "Section Exists", "status": "FAIL", "severity": "BLOCKING",
                           "detail": "Track file not readable"})
            blocking += 1
        elif _extract_markdown_section(file_text, "Streaming Lyrics") is None:
            checks.append({"check": "Section Exists", "status": "FAIL", "severity": "BLOCKING",
                           "detail": "No '## Streaming Lyrics' heading found"})
            blocking += 1
        else:
            checks.append({"check": "Section Exists", "status": "PASS",
                           "detail": "Section heading found"})

        # Check 2: Not Empty
        if streaming_content and streaming_content.strip():
            checks.append({"check": "Not Empty", "status": "PASS",
                           "detail": "Content present"})
        else:
            checks.append({"check": "Not Empty", "status": "FAIL", "severity": "BLOCKING",
                           "detail": "Streaming lyrics code block is empty or missing"})
            blocking += 1

        # Check 3: Not Placeholder
        if streaming_content and streaming_content.strip():
            is_placeholder = any(
                marker.lower() in streaming_content.lower()
                for marker in _STREAMING_PLACEHOLDER_MARKERS
            )
            if is_placeholder:
                checks.append({"check": "Not Placeholder", "status": "FAIL", "severity": "BLOCKING",
                               "detail": "Content matches template placeholder text"})
                blocking += 1
            else:
                checks.append({"check": "Not Placeholder", "status": "PASS",
                               "detail": "Content is not placeholder"})
        else:
            checks.append({"check": "Not Placeholder", "status": "SKIP",
                           "detail": "No content to check"})

        # Checks 4-7 only run if we have actual content
        if streaming_content and streaming_content.strip():
            lines = streaming_content.split("\n")
            non_blank_lines = [(i + 1, line) for i, line in enumerate(lines) if line.strip()]

            # Check 4: No Section Tags
            tagged_lines = [(ln, line.strip()) for ln, line in non_blank_lines
                            if _SECTION_TAG_RE.match(line.strip())]
            if tagged_lines:
                examples = ", ".join(f"{tag} (line {ln})" for ln, tag in tagged_lines[:5])
                if len(tagged_lines) > 5:
                    examples += f", ... ({len(tagged_lines)} total)"
                checks.append({"check": "No Section Tags", "status": "WARN", "severity": "WARNING",
                               "detail": f"Found {len(tagged_lines)} tag(s): {examples}"})
                warning_count += 1
            else:
                checks.append({"check": "No Section Tags", "status": "PASS",
                               "detail": "No section tags found"})

            # Check 5: Lines Capitalized
            uncapped = [(ln, line.strip()) for ln, line in non_blank_lines
                        if line.strip() and not line.strip()[0].isupper()
                        and not _SECTION_TAG_RE.match(line.strip())]
            if uncapped:
                examples = ", ".join(
                    f"line {ln}: \"{text[:40]}\"" for ln, text in uncapped[:5]
                )
                if len(uncapped) > 5:
                    examples += f", ... ({len(uncapped)} total)"
                checks.append({"check": "Lines Capitalized", "status": "WARN", "severity": "WARNING",
                               "detail": f"{len(uncapped)} line(s) not capitalized: {examples}"})
                warning_count += 1
            else:
                checks.append({"check": "Lines Capitalized", "status": "PASS",
                               "detail": "All lines start uppercase"})

            # Check 6: No End Punctuation (ellipsis ... is allowed)
            punctuated = []
            for ln, line in non_blank_lines:
                stripped = line.strip()
                if _SECTION_TAG_RE.match(stripped):
                    continue
                # Allow ellipsis (... or more dots)
                if stripped.endswith("..."):
                    continue
                if _END_PUNCT_RE.search(stripped):
                    punctuated.append((ln, stripped))
            if punctuated:
                examples = ", ".join(
                    f"line {ln}: \"{text[-30:]}\"" for ln, text in punctuated[:5]
                )
                if len(punctuated) > 5:
                    examples += f", ... ({len(punctuated)} total)"
                checks.append({"check": "No End Punctuation", "status": "WARN", "severity": "WARNING",
                               "detail": f"{len(punctuated)} line(s) end with punctuation: {examples}"})
                warning_count += 1
            else:
                checks.append({"check": "No End Punctuation", "status": "PASS",
                               "detail": "No trailing punctuation found"})

            # Check 7: Word Count
            # Count words excluding section tags
            words = []
            for line in lines:
                stripped = line.strip()
                if not stripped or _SECTION_TAG_RE.match(stripped):
                    continue
                words.extend(stripped.split())
            streaming_word_count = len(words)

            # Get Suno lyrics word count for comparison
            if file_text:
                suno_section = _extract_markdown_section(file_text, "Lyrics Box")
                if suno_section:
                    suno_content = _extract_code_block(suno_section)
                    if suno_content:
                        suno_words = []
                        for sline in suno_content.split("\n"):
                            s = sline.strip()
                            if not s or _SECTION_TAG_RE.match(s):
                                continue
                            suno_words.extend(s.split())
                        suno_word_count = len(suno_words)

            if streaming_word_count < 20:
                checks.append({"check": "Word Count", "status": "WARN", "severity": "WARNING",
                               "detail": f"Only {streaming_word_count} words (minimum 20 expected)"})
                warning_count += 1
            elif suno_word_count > 0 and streaming_word_count < suno_word_count * 0.8:
                pct = round(streaming_word_count / suno_word_count * 100)
                checks.append({"check": "Word Count", "status": "WARN", "severity": "WARNING",
                               "detail": f"{streaming_word_count} words = {pct}% of Suno lyrics "
                                         f"({suno_word_count} words). Expected >= 80%"})
                warning_count += 1
            else:
                detail = f"{streaming_word_count} words"
                if suno_word_count > 0:
                    pct = round(streaming_word_count / suno_word_count * 100)
                    detail += f" ({pct}% of Suno lyrics)"
                checks.append({"check": "Word Count", "status": "PASS", "detail": detail})
        else:
            # No content — skip content-dependent checks
            for check_name in ("No Section Tags", "Lines Capitalized",
                               "No End Punctuation", "Word Count"):
                checks.append({"check": check_name, "status": "SKIP",
                               "detail": "No content to check"})

        verdict = "READY" if blocking == 0 else "NOT READY"
        total_blocking += blocking
        total_warnings += warning_count

        result = {
            "track_slug": t_slug,
            "title": t_data.get("title", t_slug),
            "verdict": verdict,
            "blocking": blocking,
            "warnings": warning_count,
            "word_count": streaming_word_count,
            "checks": checks,
        }
        if suno_word_count > 0:
            result["suno_word_count"] = suno_word_count
        track_results.append(result)

    if len(tracks_to_check) == 1:
        album_verdict = track_results[0]["verdict"]
    elif total_blocking == 0:
        album_verdict = "ALL READY"
    elif any(t["blocking"] == 0 for t in track_results):
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


# =============================================================================
# Streaming URL Management
# =============================================================================

# Canonical platform names and accepted aliases
_STREAMING_PLATFORMS = {
    "soundcloud": "soundcloud",
    "spotify": "spotify",
    "apple_music": "apple_music",
    "apple-music": "apple_music",
    "applemusic": "apple_music",
    "youtube_music": "youtube_music",
    "youtube-music": "youtube_music",
    "youtubemusic": "youtube_music",
    "amazon_music": "amazon_music",
    "amazon-music": "amazon_music",
    "amazonmusic": "amazon_music",
}

# All 5 canonical platform keys (in display order)
_STREAMING_PLATFORM_KEYS = [
    "soundcloud", "spotify", "apple_music", "youtube_music", "amazon_music",
]

# Map from canonical platform key to DB column name
_PLATFORM_DB_COLUMNS = {
    "soundcloud": "soundcloud_url",
    "spotify": "spotify_url",
    "apple_music": "apple_music_url",
    "youtube_music": "youtube_url",
    "amazon_music": "amazon_music_url",
}


@mcp.tool()
async def get_streaming_urls(album_slug: str) -> str:
    """Get streaming platform URLs for an album.

    Returns all 5 platform slots with their current value (empty string
    if not set), plus a count of filled/missing platforms.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with URLs per platform, filled_count, and missing list
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    # Get streaming URLs from state cache
    streaming = album.get("streaming_urls", {})

    # Build full response with all 5 slots
    urls = {}
    missing = []
    for key in _STREAMING_PLATFORM_KEYS:
        val = streaming.get(key, "")
        urls[key] = val
        if not val:
            missing.append(key)

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "urls": urls,
        "filled_count": len(_STREAMING_PLATFORM_KEYS) - len(missing),
        "total_platforms": len(_STREAMING_PLATFORM_KEYS),
        "missing": missing,
    })


@mcp.tool()
async def update_streaming_url(album_slug: str, platform: str, url: str) -> str:
    """Set a streaming platform URL for an album.

    Updates the YAML frontmatter in the album's README.md and refreshes
    the state cache. If a database is configured, also syncs the URL
    there (best-effort).

    Args:
        album_slug: Album slug (e.g., "my-album")
        platform: Platform name. Accepts:
            "soundcloud", "spotify", "apple_music" (or "apple-music"),
            "youtube_music" (or "youtube-music"), "amazon_music" (or "amazon-music")
        url: The streaming URL (must start with http:// or https://).
            Pass empty string to clear.

    Returns:
        JSON with update result or error
    """
    import yaml

    # Validate platform
    canonical_platform = _STREAMING_PLATFORMS.get(platform.lower().replace(" ", "_"))
    if not canonical_platform:
        return _safe_json({
            "error": f"Unknown platform '{platform}'. Valid: "
                     f"{', '.join(_STREAMING_PLATFORM_KEYS)}",
        })

    # Validate URL (allow empty to clear)
    if url and not url.startswith(("http://", "https://")):
        return _safe_json({
            "error": f"Invalid URL: must start with http:// or https:// (got '{url[:50]}')",
        })

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    readme_path = Path(album_path) / "README.md"
    if not readme_path.exists():
        return _safe_json({"error": f"README.md not found at {readme_path}"})

    # Read file
    try:
        text = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read README.md: {e}"})

    # Parse and update frontmatter
    if not text.startswith("---"):
        return _safe_json({"error": "README.md has no YAML frontmatter"})

    lines = text.split("\n")
    end_index = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index == -1:
        return _safe_json({"error": "Cannot find closing --- in frontmatter"})

    frontmatter_text = "\n".join(lines[1:end_index])
    try:
        fm = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        return _safe_json({"error": f"Cannot parse frontmatter YAML: {e}"})

    # Update streaming URL using targeted regex replacement to preserve
    # YAML comments and formatting (yaml.dump would strip comments).
    fm_lines = lines[1:end_index]
    updated = False
    for idx, fm_line in enumerate(fm_lines):
        # Match lines like "  soundcloud: ..." or "  apple_music: ..."
        stripped = fm_line.lstrip()
        if stripped.startswith(f"{canonical_platform}:"):
            # Replace the value, preserving indent
            indent = fm_line[:len(fm_line) - len(stripped)]
            if url:
                fm_lines[idx] = f'{indent}{canonical_platform}: "{url}"'
            else:
                fm_lines[idx] = f"{indent}{canonical_platform}: \"\""
            updated = True
            break

    if not updated:
        # Platform key not found in frontmatter — need to add/create streaming block
        if "streaming" not in fm or not isinstance(fm.get("streaming"), dict):
            fm["streaming"] = {}
        fm["streaming"][canonical_platform] = url
        new_fm_text = yaml.dump(
            fm, default_flow_style=False, allow_unicode=True, sort_keys=False,
        ).rstrip("\n")
        fm_lines = new_fm_text.split("\n")

    # Reconstruct file: --- + frontmatter lines + --- + rest of file
    rest_of_file = "\n".join(lines[end_index + 1:])
    new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + rest_of_file

    # Write back
    try:
        readme_path.write_text(new_text, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write README.md: {e}"})

    # Re-parse and update state cache
    album_data = parse_album_readme(readme_path)
    state = cache.get_state()
    if state and "albums" in state and normalized in state["albums"]:
        state["albums"][normalized]["streaming_urls"] = album_data.get(
            "streaming_urls", {}
        )
        write_state(state)

    # Best-effort DB sync
    db_synced = False
    try:
        dep_err = _check_db_deps()
        if not dep_err:
            conn, conn_err = _get_db_connection()
            if conn and not conn_err:
                db_col = _PLATFORM_DB_COLUMNS.get(canonical_platform)
                if db_col:
                    cur = conn.cursor()
                    cur.execute(
                        f"UPDATE albums SET {db_col} = %s, updated_at = now() "  # nosec B608 - db_col is from allowlist, not user input
                        f"WHERE slug = %s",
                        (url, normalized),
                    )
                    conn.commit()
                    db_synced = cur.rowcount > 0
                conn.close()
    except Exception as e:
        logger.warning("DB sync failed for streaming URL: %s", e)

    return _safe_json({
        "success": True,
        "album_slug": normalized,
        "platform": canonical_platform,
        "url": url,
        "db_synced": db_synced,
    })


@mcp.tool()
async def verify_streaming_urls(album_slug: str) -> str:
    """Check if streaming URLs are live and reachable.

    For each non-empty streaming URL, performs an HTTP HEAD request to
    verify the link is reachable. Reports status per platform.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with per-platform reachability results
    """
    import urllib.request
    import urllib.error

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    streaming = album.get("streaming_urls", {})

    def _check_url(url: str) -> dict:
        """Check a single URL (blocking). Run in executor to avoid blocking the event loop."""
        result_entry = {"url": url}
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(
                    url, method=method,
                    headers={
                        "User-Agent": "bitwize-music-mcp/1.0 (link checker)",
                    },
                )
                with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 - URL validated above
                    status_code = resp.getcode()
                    final_url = resp.geturl()
                    result_entry["reachable"] = True
                    result_entry["status_code"] = status_code
                    if final_url != url:
                        result_entry["redirect_url"] = final_url
                    break  # Success, no need to try GET
            except urllib.error.HTTPError as e:
                if method == "HEAD" and e.code in (405, 403):
                    continue  # HEAD rejected, try GET
                result_entry["reachable"] = False
                result_entry["status_code"] = e.code
                result_entry["error"] = str(e.reason)
                break
            except (urllib.error.URLError, OSError, ValueError) as e:
                if method == "HEAD":
                    continue  # Network issue on HEAD, try GET
                result_entry["reachable"] = False
                result_entry["error"] = str(e)
                break

        if "reachable" not in result_entry:
            result_entry["reachable"] = False
            result_entry["error"] = "Both HEAD and GET requests failed"

        return result_entry

    import asyncio
    loop = asyncio.get_running_loop()

    results = {}
    reachable_count = 0
    unreachable_count = 0
    not_set_count = 0

    for key in _STREAMING_PLATFORM_KEYS:
        url = streaming.get(key, "")
        if not url:
            results[key] = {"url": "", "reachable": None, "status": "not_set"}
            not_set_count += 1
            continue

        # Run blocking HTTP in thread pool to avoid blocking the event loop
        result_entry = await loop.run_in_executor(None, _check_url, url)
        results[key] = result_entry
        if result_entry.get("reachable"):
            reachable_count += 1
        else:
            unreachable_count += 1

    all_reachable = reachable_count > 0 and unreachable_count == 0 and not_set_count == 0

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "results": results,
        "all_reachable": all_reachable,
        "reachable_count": reachable_count,
        "unreachable_count": unreachable_count,
        "not_set_count": not_set_count,
    })


@mcp.tool()
async def list_skills(model_filter: str = "", category: str = "") -> str:
    """List all skills with optional filtering.

    Args:
        model_filter: Filter by model tier ("opus", "sonnet", "haiku")
        category: Filter by keyword in description (case-insensitive substring match)

    Returns:
        JSON with skills list, count, and model_counts
    """
    state = cache.get_state()
    skills = state.get("skills", {})
    items = skills.get("items", {})

    result_items = []
    for name, skill in sorted(items.items()):
        # Apply model filter
        if model_filter:
            if skill.get("model_tier", "").lower() != model_filter.lower():
                continue

        # Apply category/description filter
        if category:
            description = skill.get("description", "").lower()
            if category.lower() not in description:
                continue

        result_items.append({
            "name": name,
            "description": skill.get("description", ""),
            "model": skill.get("model", ""),
            "model_tier": skill.get("model_tier", "unknown"),
            "user_invocable": skill.get("user_invocable", True),
            "argument_hint": skill.get("argument_hint"),
        })

    return _safe_json({
        "skills": result_items,
        "count": len(result_items),
        "total": skills.get("count", 0),
        "model_counts": skills.get("model_counts", {}),
    })


@mcp.tool()
async def get_skill(name: str) -> str:
    """Get full detail for a specific skill.

    Args:
        name: Skill name, slug, or partial match (e.g., "lyric-writer", "lyric")

    Returns:
        JSON with skill data, or error with available skills
    """
    state = cache.get_state()
    skills = state.get("skills", {})
    items = skills.get("items", {})

    if not items:
        return _safe_json({
            "found": False,
            "error": "No skills in state cache. Run rebuild_state first.",
        })

    normalized = _normalize_slug(name)

    # Exact match first
    if normalized in items:
        return _safe_json({
            "found": True,
            "name": normalized,
            "skill": items[normalized],
        })

    # Fuzzy match: substring match on skill names
    matches = {
        skill_name: data
        for skill_name, data in items.items()
        if normalized in skill_name or skill_name in normalized
    }

    if len(matches) == 1:
        skill_name = next(iter(matches))
        return _safe_json({
            "found": True,
            "name": skill_name,
            "skill": matches[skill_name],
        })
    elif len(matches) > 1:
        return _safe_json({
            "found": False,
            "multiple_matches": list(matches.keys()),
            "error": f"Multiple skills match '{name}': {', '.join(matches.keys())}",
        })
    else:
        return _safe_json({
            "found": False,
            "available_skills": sorted(items.keys()),
            "error": f"No skill found matching '{name}'",
        })


# =============================================================================
# Album Status & Track Creation Tools
# =============================================================================

# Valid album statuses (from CLAUDE.md workflow)
_VALID_ALBUM_STATUSES = {s.lower() for s in ALBUM_VALID_STATUSES}

# Valid track statuses (from CLAUDE.md workflow / state-schema.md)
_VALID_TRACK_STATUSES = {
    TRACK_NOT_STARTED.lower(), TRACK_SOURCES_PENDING.lower(),
    TRACK_SOURCES_VERIFIED.lower(), TRACK_IN_PROGRESS.lower(),
    TRACK_GENERATED.lower(), TRACK_FINAL.lower(),
}

# --- Valid status transitions (from CLAUDE.md workflow) ---
# Not Started → In Progress is allowed (non-documentary albums skip sources)
_VALID_TRACK_TRANSITIONS = {
    TRACK_NOT_STARTED: {TRACK_SOURCES_PENDING, TRACK_IN_PROGRESS},
    TRACK_SOURCES_PENDING: {TRACK_SOURCES_VERIFIED},
    TRACK_SOURCES_VERIFIED: {TRACK_IN_PROGRESS},
    TRACK_IN_PROGRESS: {TRACK_GENERATED},
    TRACK_GENERATED: {TRACK_FINAL},
    TRACK_FINAL: set(),  # terminal
}

# Concept → In Progress is allowed (non-documentary albums skip sources)
_VALID_ALBUM_TRANSITIONS = {
    ALBUM_CONCEPT: {ALBUM_RESEARCH_COMPLETE, ALBUM_IN_PROGRESS},
    ALBUM_RESEARCH_COMPLETE: {ALBUM_SOURCES_VERIFIED},
    ALBUM_SOURCES_VERIFIED: {ALBUM_IN_PROGRESS},
    ALBUM_IN_PROGRESS: {ALBUM_COMPLETE},
    ALBUM_COMPLETE: {ALBUM_RELEASED},
    ALBUM_RELEASED: set(),  # terminal
}

# Canonical status lookup for case-insensitive matching
_CANONICAL_TRACK_STATUS = {s.lower(): s for s in _VALID_TRACK_TRANSITIONS}
_CANONICAL_ALBUM_STATUS = {s.lower(): s for s in _VALID_ALBUM_TRANSITIONS}

# Status level mappings for album/track consistency checks
_TRACK_STATUS_LEVEL = {
    TRACK_NOT_STARTED: 0, TRACK_SOURCES_PENDING: 1, TRACK_SOURCES_VERIFIED: 2,
    TRACK_IN_PROGRESS: 3, TRACK_GENERATED: 4, TRACK_FINAL: 5,
}
_ALBUM_STATUS_LEVEL = {
    ALBUM_CONCEPT: 0, ALBUM_RESEARCH_COMPLETE: 1, ALBUM_SOURCES_VERIFIED: 2,
    ALBUM_IN_PROGRESS: 3, ALBUM_COMPLETE: 4, ALBUM_RELEASED: 5,
}


def _check_album_track_consistency(album: dict, new_status: str) -> Optional[str]:
    """Check if album status is consistent with its tracks' statuses.

    Returns error message if inconsistent, or None if OK.

    Rules:
    - Album "In Progress" → at least 1 track past "Not Started"
    - Album "Complete" → ALL tracks at Generated or Final
    - Album "Released" → ALL tracks at Final
    - Levels 0-2 (Concept/Research/Sources Verified) → no track requirements
    - Empty albums (no tracks) → always pass
    """
    canonical = _CANONICAL_ALBUM_STATUS.get(new_status.lower().strip(), new_status)
    album_level = _ALBUM_STATUS_LEVEL.get(canonical)
    if album_level is None or album_level <= 2:
        return None  # no track requirements for early statuses

    tracks = album.get("tracks", {})
    if not tracks:
        return None  # empty albums always pass

    if canonical == ALBUM_IN_PROGRESS:
        # At least 1 track must be past Not Started
        has_active = any(
            _TRACK_STATUS_LEVEL.get(t.get("status", TRACK_NOT_STARTED), 0) > 0
            for t in tracks.values()
        )
        if not has_active:
            return (
                "Cannot set album to 'In Progress' — all tracks are still 'Not Started'. "
                "At least one track must have progressed."
            )

    elif canonical == ALBUM_COMPLETE:
        # ALL tracks must be at Generated or Final
        below = [
            slug for slug, t in tracks.items()
            if _TRACK_STATUS_LEVEL.get(t.get("status", TRACK_NOT_STARTED), 0) < _TRACK_STATUS_LEVEL[TRACK_GENERATED]
        ]
        if below:
            return (
                f"Cannot set album to 'Complete' — {len(below)} track(s) below 'Generated': "
                f"{', '.join(sorted(below)[:5])}. All tracks must be Generated or Final."
            )

    elif canonical == ALBUM_RELEASED:
        # ALL tracks must be at Final
        non_final = [
            slug for slug, t in tracks.items()
            if t.get("status", TRACK_NOT_STARTED) != TRACK_FINAL
        ]
        if non_final:
            return (
                f"Cannot set album to 'Released' — {len(non_final)} track(s) not Final: "
                f"{', '.join(sorted(non_final)[:5])}. All tracks must be Final."
            )

    return None


def _validate_track_transition(current: str, new: str, *, force: bool = False) -> Optional[str]:
    """Return error message if transition is invalid, or None if OK."""
    if force:
        return None
    canonical_current = _CANONICAL_TRACK_STATUS.get(current.lower().strip(), current)
    canonical_new = _CANONICAL_TRACK_STATUS.get(new.lower().strip(), new)
    allowed = _VALID_TRACK_TRANSITIONS.get(canonical_current)
    if allowed is None:
        return None  # unknown current status — don't block (recovery)
    if canonical_new not in allowed:
        return (
            f"Invalid transition: '{canonical_current}' → '{canonical_new}'. "
            f"Allowed next: {', '.join(sorted(allowed)) or 'none (terminal)'}. "
            f"Use force=True to override."
        )
    return None


def _validate_album_transition(current: str, new: str, *, force: bool = False) -> Optional[str]:
    """Return error message if transition is invalid, or None if OK."""
    if force:
        return None
    canonical_current = _CANONICAL_ALBUM_STATUS.get(current.lower().strip(), current)
    canonical_new = _CANONICAL_ALBUM_STATUS.get(new.lower().strip(), new)
    allowed = _VALID_ALBUM_TRANSITIONS.get(canonical_current)
    if allowed is None:
        return None  # unknown current status — don't block (recovery)
    if canonical_new not in allowed:
        return (
            f"Invalid transition: '{canonical_current}' → '{canonical_new}'. "
            f"Allowed next: {', '.join(sorted(allowed)) or 'none (terminal)'}. "
            f"Use force=True to override."
        )
    return None


# Expected promo files (from templates/promo/)
_PROMO_FILES = [
    "campaign.md", "twitter.md", "instagram.md",
    "tiktok.md", "facebook.md", "youtube.md",
]

# Album art file patterns for release readiness check
_ALBUM_ART_PATTERNS = [
    "album.png", "album.jpg", "album-art.png", "album-art.jpg",
    "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
]


def _find_album_or_error(album_slug: str) -> tuple:
    """Find album in state cache, return (normalized_slug, album_data, error_json).

    If album found: (slug, data, None)
    If not found: (slug, None, error_json_string)
    """
    state = cache.get_state()
    albums = state.get("albums", {})
    normalized = _normalize_slug(album_slug)
    album = albums.get(normalized)

    if not album:
        return normalized, None, _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    return normalized, album, None


@mcp.tool()
async def update_album_status(album_slug: str, status: str, force: bool = False) -> str:
    """Update an album's status in its README.md file.

    Modifies the album details table (| **Status** | Value |) and updates
    the state cache to reflect the change.

    Args:
        album_slug: Album slug (e.g., "my-album")
        status: New status. Valid options:
            "Concept", "Research Complete", "Sources Verified",
            "In Progress", "Complete", "Released"
        force: Override transition validation (for recovery/correction only)

    Returns:
        JSON with update result or error
    """
    # Validate status
    if status.lower().strip() not in _VALID_ALBUM_STATUSES:
        return _safe_json({
            "error": (
                f"Invalid status '{status}'. Valid options: "
                + ", ".join(ALBUM_VALID_STATUSES)
            ),
        })

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    # Validate status transition
    current_status = album.get("status", ALBUM_CONCEPT)
    err = _validate_album_transition(current_status, status, force=force)
    if err:
        return _safe_json({"error": err})

    # Documentary album gate: albums with SOURCES.md cannot skip Concept → In Progress (configurable)
    if not force:
        state_config = (cache.get_state()).get("config", {})
        gen_cfg = state_config.get("generation", {})
        require_source_path = gen_cfg.get("require_source_path_for_documentary", True)
        if require_source_path:
            canonical_status = _CANONICAL_ALBUM_STATUS.get(status.lower().strip(), status)
            canonical_current = _CANONICAL_ALBUM_STATUS.get(
                current_status.lower().strip(), current_status)
            if canonical_current == ALBUM_CONCEPT and canonical_status == ALBUM_IN_PROGRESS:
                album_path = album.get("path", "")
                if album_path:
                    sources_path = Path(album_path) / "SOURCES.md"
                    if sources_path.exists():
                        return _safe_json({
                            "error": "Cannot skip to 'In Progress' — this album has SOURCES.md "
                                     "(documentary). Transition through 'Research Complete' → "
                                     "'Sources Verified' → 'In Progress' instead, or use "
                                     "force=True to override. To disable this check, set "
                                     "generation.require_source_path_for_documentary: false "
                                     "in config.",
                        })

    # Album/track consistency gate: album status must not exceed track statuses
    if not force:
        consistency_err = _check_album_track_consistency(album, status)
        if consistency_err:
            return _safe_json({"error": consistency_err})

    # Source verification gate: all tracks must be verified before album
    # can advance to Sources Verified
    if status.lower().strip() == ALBUM_SOURCES_VERIFIED.lower() and not force:
        tracks = album.get("tracks", {})
        unverified = [
            s for s, t in tracks.items()
            if t.get("status", TRACK_NOT_STARTED) in
            {TRACK_NOT_STARTED, TRACK_SOURCES_PENDING}
        ]
        if unverified:
            return _safe_json({
                "error": (
                    f"Cannot mark album as Sources Verified — {len(unverified)} track(s) "
                    f"still unverified: {', '.join(unverified[:5])}"
                ),
            })

    # Release readiness gate: audio, mastered files, and album art must exist
    canonical_status = _CANONICAL_ALBUM_STATUS.get(status.lower().strip(), status)
    if canonical_status == ALBUM_RELEASED and not force:
        release_issues = []
        state_config = (cache.get_state()).get("config", {})
        tracks = album.get("tracks", {})

        # Check 1: All tracks Final (explicit message, complements consistency check)
        non_final = [s for s, t in tracks.items() if t.get("status") != TRACK_FINAL]
        if non_final:
            release_issues.append(
                f"{len(non_final)} track(s) not Final: {', '.join(sorted(non_final)[:5])}"
            )

        # Check 2: Audio files exist
        audio_root = state_config.get("audio_root", "")
        artist_name = state_config.get("artist_name", "")
        genre = album.get("genre", "")
        audio_path = Path(audio_root) / "artists" / artist_name / "albums" / genre / normalized
        if not audio_path.is_dir() or not list(audio_path.glob("*.wav")):
            release_issues.append("No WAV files in audio directory")

        # Check 3: Mastered audio exists
        mastered_dir = audio_path / "mastered"
        if not mastered_dir.is_dir() or not list(mastered_dir.glob("*.wav")):
            release_issues.append("No mastered audio files")

        # Check 4: Album art exists
        if not any((audio_path / p).exists() for p in _ALBUM_ART_PATTERNS):
            release_issues.append("No album art found")

        # Check 5: Streaming lyrics ready
        streaming_issues = []
        for t_slug, t_data in tracks.items():
            track_path_str = t_data.get("path", "")
            if not track_path_str:
                streaming_issues.append(f"{t_slug}: no track path")
                continue
            try:
                tfile = Path(track_path_str).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                streaming_issues.append(f"{t_slug}: cannot read track file")
                continue
            section = _extract_markdown_section(tfile, "Streaming Lyrics")
            if not section:
                streaming_issues.append(f"{t_slug}: missing Streaming Lyrics section")
                continue
            block = _extract_code_block(section)
            if not block or not block.strip():
                streaming_issues.append(f"{t_slug}: empty Streaming Lyrics")
                continue
            if any(m.lower() in block.lower() for m in _STREAMING_PLACEHOLDER_MARKERS):
                streaming_issues.append(f"{t_slug}: placeholder content in Streaming Lyrics")
        if streaming_issues:
            release_issues.append(
                f"Streaming lyrics not ready for {len(streaming_issues)} track(s): "
                + ", ".join(streaming_issues[:5])
            )

        if release_issues:
            return _safe_json({
                "error": (
                    f"Cannot release album — {len(release_issues)} issue(s) found"
                ),
                "issues": release_issues,
                "hint": "Use force=True to override.",
            })

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    readme_path = Path(album_path) / "README.md"
    if not readme_path.exists():
        return _safe_json({"error": f"README.md not found at {readme_path}"})

    # Read file
    try:
        text = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read README.md: {e}"})

    # Find and replace the Status row
    pattern = re.compile(
        r'^(\|\s*\*\*Status\*\*\s*\|)\s*.*?\s*\|',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return _safe_json({"error": "Status field not found in album README.md table"})

    old_status = album.get("status", STATUS_UNKNOWN)
    new_row = f"{match.group(1)} {status} |"
    updated_text = text[:match.start()] + new_row + text[match.end():]

    # Write back
    try:
        readme_path.write_text(updated_text, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write README.md: {e}"})

    logger.info("Updated album '%s' status to '%s'", normalized, status)

    # Update cache — mutate the album dict already in state (obtained from
    # _find_album_or_error) and write the same state object; do NOT re-fetch
    # via cache.get_state() which could return a different object if the cache
    # was invalidated between calls.
    try:
        parsed = parse_album_readme(readme_path)
        album["status"] = parsed.get("status", status)
        state = cache._state  # same object album references into
        if state:
            write_state(state)
    except Exception as e:
        logger.warning("File written but cache update failed for album %s: %s", normalized, e)

    return _safe_json({
        "success": True,
        "album_slug": normalized,
        "old_status": old_status,
        "new_status": status,
    })


@mcp.tool()
async def create_track(
    album_slug: str,
    track_number: str,
    title: str,
    documentary: bool = False,
) -> str:
    """Create a new track file in an album from the track template.

    Copies the track template, fills in track number and title placeholders,
    and optionally keeps documentary sections (Source, Original Quote).

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_number: Two-digit track number (e.g., "01", "02")
        title: Track title (e.g., "My New Track")
        documentary: Keep source/quote sections (default: strip them)

    Returns:
        JSON with created file path or error
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    tracks_dir = Path(album_path) / "tracks"
    if not tracks_dir.is_dir():
        return _safe_json({"error": f"tracks/ directory not found in {album_path}"})

    # Normalize track number to zero-padded two digits
    num = track_number.strip().lstrip("0") or "0"
    padded = num.zfill(2)

    # Build slug from number and title
    title_slug = _normalize_slug(title)
    filename = f"{padded}-{title_slug}.md"
    track_path = tracks_dir / filename

    if track_path.exists():
        return _safe_json({
            "created": False,
            "error": f"Track file already exists: {track_path}",
            "path": str(track_path),
        })

    # Read template
    template_path = PLUGIN_ROOT / "templates" / "track.md"
    if not template_path.exists():
        return _safe_json({"error": f"Track template not found at {template_path}"})

    try:
        template = template_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track template: {e}"})

    # Fill in placeholders
    album_title = album.get("title", normalized)
    content = template.replace("[Track Title]", title)
    content = content.replace("| **Track #** | XX |", f"| **Track #** | {padded} |")
    content = content.replace("[Album Name](../README.md)", f"[{album_title}](../README.md)")
    content = content.replace("[Character/Perspective]", "—")
    content = content.replace("[Track's role in the album narrative]", "—")

    # Fill frontmatter placeholders
    content = content.replace("track_number: 0", f"track_number: {int(padded)}")
    content = content.replace(
        "explicit: false",
        f"explicit: {'true' if album.get('explicit', False) else 'false'}",
    )

    # Strip documentary sections if not needed
    if not documentary:
        # Remove from <!-- SOURCE-BASED TRACKS --> to <!-- END SOURCE SECTIONS -->
        source_start = content.find("<!-- SOURCE-BASED TRACKS")
        source_end = content.find("<!-- END SOURCE SECTIONS -->")
        if source_start != -1 and source_end != -1:
            content = content[:source_start] + content[source_end + len("<!-- END SOURCE SECTIONS -->"):]

        # Remove Documentary/True Story sections
        doc_start = content.find("<!-- DOCUMENTARY/TRUE STORY")
        doc_end = content.find("<!-- END DOCUMENTARY SECTIONS -->")
        if doc_start != -1 and doc_end != -1:
            content = content[:doc_start] + content[doc_end + len("<!-- END DOCUMENTARY SECTIONS -->"):]

    # Write file
    try:
        track_path.write_text(content, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write track file: {e}"})

    logger.info("Created track %s in album '%s'", filename, normalized)

    return _safe_json({
        "created": True,
        "path": str(track_path),
        "album_slug": normalized,
        "track_slug": f"{padded}-{title_slug}",
        "filename": filename,
    })


# =============================================================================
# Promo Directory Tools
# =============================================================================


@mcp.tool()
async def get_promo_status(album_slug: str) -> str:
    """Get the status of promo/ directory files for an album.

    Checks which promo files exist and whether they have content beyond
    the template placeholder text.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with promo directory status and per-file details
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    promo_dir = Path(album_path) / "promo"
    if not promo_dir.is_dir():
        return _safe_json({
            "found": True,
            "album_slug": normalized,
            "promo_exists": False,
            "files": [],
            "populated": 0,
            "total": len(_PROMO_FILES),
        })

    files = []
    populated = 0
    for fname in _PROMO_FILES:
        fpath = promo_dir / fname
        if not fpath.exists():
            files.append({"file": fname, "exists": False, "populated": False, "word_count": 0})
            continue

        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            files.append({"file": fname, "exists": True, "populated": False, "word_count": 0})
            continue

        # Count non-template words (skip lines that are template placeholders)
        words = 0
        for line in text.split("\n"):
            stripped = line.strip()
            # Skip headings, table formatting, empty lines, and common placeholders
            if (not stripped or stripped.startswith("#") or stripped.startswith("|")
                    or stripped.startswith("---") or stripped.startswith("```")):
                continue
            # Skip lines that are clearly template placeholders
            if stripped.startswith("[") and stripped.endswith("]"):
                continue
            words += len(stripped.split())

        # Consider "populated" if there are meaningful words beyond basic structure
        is_populated = words > 20
        if is_populated:
            populated += 1

        files.append({
            "file": fname,
            "exists": True,
            "populated": is_populated,
            "word_count": words,
        })

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "promo_exists": True,
        "files": files,
        "populated": populated,
        "total": len(_PROMO_FILES),
        "ready": populated == len(_PROMO_FILES),
    })


@mcp.tool()
async def get_promo_content(album_slug: str, platform: str) -> str:
    """Read the content of a specific promo file for an album.

    Args:
        album_slug: Album slug (e.g., "my-album")
        platform: Platform name — one of: campaign, twitter, instagram,
                  tiktok, facebook, youtube

    Returns:
        JSON with file content or error
    """
    # Validate platform
    platform_key = platform.lower().strip()
    filename = f"{platform_key}.md"
    if filename not in _PROMO_FILES:
        return _safe_json({
            "error": f"Unknown platform '{platform}'. Valid options: "
                     + ", ".join(f.replace(".md", "") for f in _PROMO_FILES),
        })

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    promo_path = Path(album_path) / "promo" / filename
    if not promo_path.exists():
        return _safe_json({
            "found": False,
            "error": f"Promo file not found: {promo_path}",
            "album_slug": normalized,
            "platform": platform_key,
        })

    try:
        content = promo_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read promo file: {e}"})

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "platform": platform_key,
        "path": str(promo_path),
        "content": content,
    })


# =============================================================================
# Plugin Version Tool
# =============================================================================


@mcp.tool()
async def get_plugin_version() -> str:
    """Get the current and stored plugin version.

    Compares the plugin version stored in state.json with the current
    version from .claude-plugin/plugin.json. Useful for upgrade detection.

    Returns:
        JSON with stored_version, current_version, and needs_upgrade flag
    """
    state = cache.get_state()
    stored = state.get("plugin_version")

    # Read current version from plugin.json
    plugin_json = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    current = None
    try:
        if plugin_json.exists():
            data = json.loads(plugin_json.read_text(encoding="utf-8"))
            current = data.get("version")
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Cannot read plugin.json: %s", e)

    needs_upgrade = False
    if stored is None and current is not None:
        needs_upgrade = True  # First run
    elif stored and current and stored != current:
        needs_upgrade = True

    return _safe_json({
        "stored_version": stored,
        "current_version": current,
        "needs_upgrade": needs_upgrade,
        "plugin_root": str(PLUGIN_ROOT),
    })


# =============================================================================
# Idea Management Tools
# =============================================================================


def _resolve_ideas_path() -> Optional[Path]:
    """Resolve the path to IDEAS.md using config."""
    state = cache.get_state()
    config = state.get("config", {})
    content_root = config.get("content_root", "")
    if not content_root:
        return None
    return Path(content_root) / "IDEAS.md"


@mcp.tool()
async def create_idea(
    title: str,
    genre: str = "",
    idea_type: str = "",
    concept: str = "",
) -> str:
    """Add a new album idea to IDEAS.md.

    Appends a new idea entry using the standard format. Creates IDEAS.md
    from template if it doesn't exist.

    Args:
        title: Idea title (e.g., "Cyberpunk Dreams")
        genre: Target genre (e.g., "electronic", "hip-hop")
        idea_type: Idea type (e.g., "Documentary", "Thematic", "Narrative")
        concept: One-sentence concept pitch

    Returns:
        JSON with success or error
    """
    if not title.strip():
        return _safe_json({"error": "Title cannot be empty"})

    ideas_path = _resolve_ideas_path()
    if not ideas_path:
        return _safe_json({"error": "Cannot resolve IDEAS.md path (no content_root in config)"})

    # Read existing content or start from scratch
    if ideas_path.exists():
        try:
            text = ideas_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return _safe_json({"error": f"Cannot read IDEAS.md: {e}"})
    else:
        text = "# Album Ideas\n\n---\n\n## Ideas\n"

    # Check for duplicate title
    if f"### {title.strip()}\n" in text:
        return _safe_json({
            "created": False,
            "error": f"Idea '{title.strip()}' already exists in IDEAS.md",
        })

    # Build the new idea block
    lines = [f"\n### {title.strip()}\n"]
    if genre:
        lines.append(f"**Genre**: {genre}")
    if idea_type:
        lines.append(f"**Type**: {idea_type}")
    if concept:
        lines.append(f"**Concept**: {concept}")
    lines.append("**Status**: Pending\n")
    new_block = "\n".join(lines)

    # Append to file
    updated = text.rstrip() + "\n" + new_block

    try:
        ideas_path.parent.mkdir(parents=True, exist_ok=True)
        ideas_path.write_text(updated, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write IDEAS.md: {e}"})

    logger.info("Created idea '%s' in IDEAS.md", title.strip())

    # Rebuild ideas in cache
    try:
        cache.rebuild()
    except Exception as e:
        logger.warning("Idea created but cache rebuild failed: %s", e)

    return _safe_json({
        "created": True,
        "title": title.strip(),
        "genre": genre,
        "type": idea_type,
        "status": "Pending",
        "path": str(ideas_path),
    })


@mcp.tool()
async def update_idea(title: str, field: str, value: str) -> str:
    """Update a field in an existing idea in IDEAS.md.

    Args:
        title: Exact idea title to find (e.g., "Cyberpunk Dreams")
        field: Field to update — "status", "genre", "type", or "concept"
        value: New value for the field

    Returns:
        JSON with success or error
    """
    valid_fields = {"status", "genre", "type", "concept"}
    field_key = field.lower().strip()
    if field_key not in valid_fields:
        return _safe_json({
            "error": f"Unknown field '{field}'. Valid options: {', '.join(sorted(valid_fields))}",
        })

    # Map field key to bold label used in IDEAS.md
    field_labels = {
        "status": "Status",
        "genre": "Genre",
        "type": "Type",
        "concept": "Concept",
    }
    label = field_labels[field_key]

    ideas_path = _resolve_ideas_path()
    if not ideas_path:
        return _safe_json({"error": "Cannot resolve IDEAS.md path (no content_root in config)"})

    if not ideas_path.exists():
        return _safe_json({"error": "IDEAS.md not found"})

    try:
        text = ideas_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read IDEAS.md: {e}"})

    # Find the idea section by title
    title_pattern = re.compile(r'^###\s+' + re.escape(title.strip()) + r'\s*$', re.MULTILINE)
    title_match = title_pattern.search(text)
    if not title_match:
        return _safe_json({
            "found": False,
            "error": f"Idea '{title.strip()}' not found in IDEAS.md",
        })

    # Find the field within this idea's section (between this ### and next ###)
    section_start = title_match.end()
    next_section = re.search(r'^###\s+', text[section_start:], re.MULTILINE)
    section_end = section_start + next_section.start() if next_section else len(text)
    section_text = text[section_start:section_end]

    field_pattern = re.compile(
        r'^(\*\*' + re.escape(label) + r'\*\*\s*:\s*)(.+)$',
        re.MULTILINE,
    )
    field_match = field_pattern.search(section_text)
    if not field_match:
        return _safe_json({
            "error": f"Field '{label}' not found in idea '{title.strip()}'",
        })

    # Replace the field value
    old_value = field_match.group(2).strip()
    abs_start = section_start + field_match.start()
    abs_end = section_start + field_match.end()
    new_line = f"{field_match.group(1)}{value}"
    updated_text = text[:abs_start] + new_line + text[abs_end:]

    try:
        ideas_path.write_text(updated_text, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write IDEAS.md: {e}"})

    logger.info("Updated idea '%s' field '%s' to '%s'", title.strip(), label, value)

    # Rebuild ideas in cache
    try:
        cache.rebuild()
    except Exception as e:
        logger.warning("Idea updated but cache rebuild failed: %s", e)

    return _safe_json({
        "success": True,
        "title": title.strip(),
        "field": label,
        "old_value": old_value,
        "new_value": value,
    })


def _derive_title_from_slug(slug: str) -> str:
    """Derive a display title from a slug.

    Strips leading track number prefix (e.g., "01-") and converts hyphens
    to spaces with title case.

    Examples:
        "01-my-track-name" → "My Track Name"
        "my-album"         → "My Album"
    """
    import re as _re
    # Strip leading track number prefix like "01-", "02-"
    stripped = _re.sub(r'^\d+-', '', slug)
    return stripped.replace('-', ' ').title()


@mcp.tool()
async def rename_album(old_slug: str, new_slug: str, new_title: str = "") -> str:
    """Rename album slug, title, and directories.

    Renames the album across all mirrored path trees (content, audio,
    documents), updates the README.md title, and refreshes the state cache.

    Args:
        old_slug: Current album slug (e.g., "old-album-name")
        new_slug: New album slug (e.g., "new-album-name")
        new_title: New display title (if empty, derived from new_slug via title case)

    Returns:
        JSON with rename result or error
    """
    normalized_old = _normalize_slug(old_slug)
    normalized_new = _normalize_slug(new_slug)

    if normalized_old == normalized_new:
        return _safe_json({"error": "Old and new slugs are the same after normalization."})

    # Get state and validate old album exists
    state = cache.get_state()
    albums = state.get("albums", {})

    if normalized_old not in albums:
        return _safe_json({
            "error": f"Album '{old_slug}' not found.",
            "available_albums": list(albums.keys()),
        })

    if normalized_new in albums:
        return _safe_json({
            "error": f"Album '{new_slug}' already exists.",
        })

    album = albums[normalized_old]

    # Get config for path resolution
    config = state.get("config", {})
    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    content_root = config.get("content_root", "")
    audio_root = config.get("audio_root", "")
    documents_root = config.get("documents_root", "")
    artist = config.get("artist_name", "")
    genre = album.get("genre", "")

    if not artist:
        return _safe_json({"error": "No artist_name in config."})

    # Resolve paths
    content_dir_old = Path(content_root) / "artists" / artist / "albums" / genre / normalized_old
    content_dir_new = Path(content_root) / "artists" / artist / "albums" / genre / normalized_new
    audio_dir_old = Path(audio_root) / "artists" / artist / "albums" / genre / normalized_old
    audio_dir_new = Path(audio_root) / "artists" / artist / "albums" / genre / normalized_new
    docs_dir_old = Path(documents_root) / "artists" / artist / "albums" / genre / normalized_old
    docs_dir_new = Path(documents_root) / "artists" / artist / "albums" / genre / normalized_new

    # Content directory MUST exist
    if not content_dir_old.is_dir():
        return _safe_json({
            "error": f"Content directory not found: {content_dir_old}",
        })

    # Derive title
    title = new_title.strip() if new_title else _derive_title_from_slug(normalized_new)

    # Rename content directory
    content_moved = False
    audio_moved = False
    documents_moved = False

    try:
        shutil.move(str(content_dir_old), str(content_dir_new))
        content_moved = True
    except OSError as e:
        return _safe_json({
            "error": f"Failed to rename content directory: {e}",
            "content_moved": False,
            "audio_moved": False,
            "documents_moved": False,
        })

    # Rename audio directory if it exists
    if audio_dir_old.is_dir():
        try:
            shutil.move(str(audio_dir_old), str(audio_dir_new))
            audio_moved = True
        except OSError as e:
            logger.warning("Content dir renamed but audio dir failed: %s", e)

    # Rename documents directory if it exists
    if docs_dir_old.is_dir():
        try:
            shutil.move(str(docs_dir_old), str(docs_dir_new))
            documents_moved = True
        except OSError as e:
            logger.warning("Content dir renamed but documents dir failed: %s", e)

    # Update README.md title (H1 heading) if it exists
    readme_path = content_dir_new / "README.md"
    if readme_path.exists():
        try:
            text = readme_path.read_text(encoding="utf-8")
            heading_pattern = re.compile(r'^#\s+(.+)$', re.MULTILINE)
            match = heading_pattern.search(text)
            if match:
                updated_text = text[:match.start()] + f"# {title}" + text[match.end():]
                readme_path.write_text(updated_text, encoding="utf-8")
        except OSError as e:
            logger.warning("Directories moved but README title update failed: %s", e)

    # Update state cache
    tracks_updated = 0
    try:
        album_data = albums.pop(normalized_old)
        album_data["path"] = str(content_dir_new)
        album_data["title"] = title

        # Update track paths
        for track_slug, track_data in album_data.get("tracks", {}).items():
            old_track_path = track_data.get("path", "")
            if old_track_path:
                track_data["path"] = old_track_path.replace(
                    str(content_dir_old), str(content_dir_new)
                )
                tracks_updated += 1

        albums[normalized_new] = album_data
        write_state(state)
    except Exception as e:
        logger.warning("Directories moved but cache update failed: %s", e)

    logger.info("Renamed album '%s' to '%s'", normalized_old, normalized_new)

    return _safe_json({
        "success": True,
        "old_slug": normalized_old,
        "new_slug": normalized_new,
        "title": title,
        "content_moved": content_moved,
        "audio_moved": audio_moved,
        "documents_moved": documents_moved,
        "tracks_updated": tracks_updated,
    })


@mcp.tool()
async def rename_track(
    album_slug: str,
    old_track_slug: str,
    new_track_slug: str,
    new_title: str = "",
) -> str:
    """Rename track slug, title, and file.

    Renames the track markdown file, updates the title in the metadata table,
    and refreshes the state cache.

    Args:
        album_slug: Album containing the track (e.g., "my-album")
        old_track_slug: Current track slug or prefix (e.g., "01-old-name" or "01")
        new_track_slug: New track slug (e.g., "01-new-name")
        new_title: New display title (if empty, derived from new_slug)

    Returns:
        JSON with rename result or error
    """
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    tracks = album.get("tracks", {})
    normalized_old = _normalize_slug(old_track_slug)
    normalized_new = _normalize_slug(new_track_slug)

    if normalized_old == normalized_new:
        return _safe_json({"error": "Old and new track slugs are the same after normalization."})

    # Find old track (exact or prefix match)
    track_data = tracks.get(normalized_old)
    matched_slug = normalized_old
    if not track_data:
        prefix_matches = {s: d for s, d in tracks.items() if s.startswith(normalized_old)}
        if len(prefix_matches) == 1:
            matched_slug = next(iter(prefix_matches))
            track_data = prefix_matches[matched_slug]
        elif len(prefix_matches) > 1:
            return _safe_json({
                "error": f"Multiple tracks match '{old_track_slug}': {', '.join(prefix_matches.keys())}",
            })
        else:
            return _safe_json({
                "error": f"Track '{old_track_slug}' not found in album '{album_slug}'.",
                "available_tracks": list(tracks.keys()),
            })

    # Check new slug doesn't already exist
    if normalized_new in tracks:
        return _safe_json({
            "error": f"Track '{new_track_slug}' already exists in album '{album_slug}'.",
        })

    old_path = Path(track_data.get("path", ""))
    if not old_path.exists():
        return _safe_json({
            "error": f"Track file not found on disk: {old_path}",
        })

    # Build new path
    new_path = old_path.parent / f"{normalized_new}.md"

    # Derive title
    title = new_title.strip() if new_title else _derive_title_from_slug(normalized_new)

    # Rename file
    try:
        shutil.move(str(old_path), str(new_path))
    except OSError as e:
        return _safe_json({"error": f"Failed to rename track file: {e}"})

    # Update title in metadata table
    try:
        text = new_path.read_text(encoding="utf-8")
        title_pattern = re.compile(
            r'^(\|\s*\*\*Title\*\*\s*\|)\s*.*?\s*\|',
            re.MULTILINE,
        )
        match = title_pattern.search(text)
        if match:
            new_row = f"{match.group(1)} {title} |"
            updated_text = text[:match.start()] + new_row + text[match.end():]
            # Also update H1 heading if present
            heading_pattern = re.compile(r'^#\s+(.+)$', re.MULTILINE)
            h1_match = heading_pattern.search(updated_text)
            if h1_match:
                updated_text = updated_text[:h1_match.start()] + f"# {title}" + updated_text[h1_match.end():]
            new_path.write_text(updated_text, encoding="utf-8")
        else:
            logger.warning("Title field not found in track metadata table for %s", matched_slug)
    except OSError as e:
        logger.warning("File renamed but title update failed: %s", e)

    # Update state cache — use the same state object that _find_album_or_error
    # returned references into; do NOT re-fetch via cache.get_state() which
    # could return a different object if the cache was invalidated.
    try:
        old_track_data = tracks.pop(matched_slug)
        old_track_data["path"] = str(new_path)
        old_track_data["title"] = title
        # Re-parse the track for fresh metadata
        try:
            parsed = parse_track_file(new_path)
            old_track_data.update({
                "status": parsed.get("status", old_track_data.get("status")),
                "explicit": parsed.get("explicit", old_track_data.get("explicit")),
                "has_suno_link": parsed.get("has_suno_link", old_track_data.get("has_suno_link")),
                "sources_verified": parsed.get("sources_verified", old_track_data.get("sources_verified")),
                "mtime": new_path.stat().st_mtime,
            })
        except Exception:
            pass
        tracks[normalized_new] = old_track_data
        state = cache._state  # same object that album/tracks reference into
        if state:
            write_state(state)
    except Exception as e:
        logger.warning("File renamed but cache update failed: %s", e)

    logger.info("Renamed track '%s' to '%s' in album '%s'", matched_slug, normalized_new, normalized_album)

    return _safe_json({
        "success": True,
        "album_slug": normalized_album,
        "old_slug": matched_slug,
        "new_slug": normalized_new,
        "title": title,
        "old_path": str(old_path),
        "new_path": str(new_path),
    })


# =============================================================================
# Processing Tools — Mastering, Sheet Music, Promo Videos
# =============================================================================
#
# These tools wrap the Python scripts in tools/mastering/, tools/sheet-music/,
# and tools/promotion/ so Claude can invoke them directly via MCP instead of
# telling the user to run CLI commands.
#
# Architecture:
# - Direct import of library functions (not subprocess) for structured results
# - asyncio.run_in_executor() for CPU-heavy work (keeps MCP event loop alive)
# - Lazy dependency checking at invocation time (server starts without optional deps)
# - Block-and-return (no streaming/progress — MCP has no such mechanism)
# =============================================================================


def _resolve_audio_dir(album_slug: str, subfolder: str = "") -> tuple:
    """Resolve album slug to audio directory path.

    Returns (error_json_or_None, Path_or_None).
    """
    state = cache.get_state()
    config = state.get("config", {})
    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")
    if not audio_root or not artist:
        return _safe_json({"error": "audio_root or artist_name not configured"}), None
    normalized = _normalize_slug(album_slug)
    albums = state.get("albums", {})
    album_data = albums.get(normalized, {})
    genre = album_data.get("genre", "")
    if not genre:
        return _safe_json({
            "error": f"Genre not found for album '{album_slug}'. Ensure album exists in state.",
        }), None
    audio_path = Path(audio_root) / "artists" / artist / "albums" / genre / normalized
    if subfolder:
        audio_path = audio_path / subfolder
    if not audio_path.is_dir():
        return _safe_json({
            "error": f"Audio directory not found: {audio_path}",
            "suggestion": "Check album slug or download audio first.",
        }), None
    return None, audio_path


def _check_mastering_deps() -> Optional[str]:
    """Return error message if mastering deps missing, else None."""
    missing = []
    for mod in ("numpy", "scipy", "soundfile", "pyloudnorm"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return (
            f"Missing mastering dependencies: {', '.join(missing)}. "
            "Install: pip install pyloudnorm scipy numpy soundfile"
        )
    return None


def _check_ffmpeg() -> Optional[str]:
    """Return error message if ffmpeg not found, else None."""
    if not shutil.which("ffmpeg"):
        return (
            "ffmpeg not found. Install: "
            "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
        )
    return None


def _check_matchering() -> Optional[str]:
    """Return error message if matchering not installed, else None."""
    try:
        __import__("matchering")
    except ImportError:
        return "matchering not installed. Install: pip install matchering"
    return None


def _import_sheet_music_module(module_name: str):
    """Import a module from tools/sheet-music/ using importlib (hyphenated dir)."""
    import importlib.util
    module_path = PLUGIN_ROOT / "tools" / "sheet-music" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"sheet_music_{module_name}", str(module_path)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check_anthemscore() -> Optional[str]:
    """Return error message if AnthemScore not found, else None."""
    try:
        transcribe_mod = _import_sheet_music_module("transcribe")
        if transcribe_mod.find_anthemscore() is None:
            return (
                "AnthemScore not found. Install from: https://www.lunaverus.com/ "
                "(Professional edition recommended for CLI support)"
            )
    except Exception:
        # Fall back to path search
        paths = [
            "/Applications/AnthemScore.app/Contents/MacOS/AnthemScore",
            "/usr/bin/anthemscore",
            "/usr/local/bin/anthemscore",
        ]
        if not any(Path(p).exists() for p in paths) and not shutil.which("anthemscore"):
            return (
                "AnthemScore not found. Install from: https://www.lunaverus.com/ "
                "(Professional edition recommended for CLI support)"
            )
    return None


def _check_songbook_deps() -> Optional[str]:
    """Return error message if songbook deps missing, else None."""
    missing = []
    for mod in ("pypdf", "reportlab"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return (
            f"Missing songbook dependencies: {', '.join(missing)}. "
            "Install: pip install pypdf reportlab"
        )
    return None


@mcp.tool()
async def analyze_audio(album_slug: str, subfolder: str = "") -> str:
    """Analyze audio tracks for mastering decisions.

    Scans WAV files in the album's audio directory and returns per-track
    metrics including LUFS, peak levels, spectral balance, and tinniness.

    Args:
        album_slug: Album slug (e.g., "my-album")
        subfolder: Optional subfolder within audio dir (e.g., "mastered")

    Returns:
        JSON with per-track metrics, summary, and recommendations
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug, subfolder)
    if err:
        return err

    from tools.mastering.analyze_tracks import analyze_track

    wav_files = sorted(audio_dir.glob("*.wav"))
    wav_files = [f for f in wav_files if "venv" not in str(f)]
    if not wav_files:
        return _safe_json({
            "error": f"No WAV files found in {audio_dir}",
            "suggestion": "Check the album slug or subfolder.",
        })

    loop = asyncio.get_running_loop()
    results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        results.append(result)

    # Build summary
    import numpy as np
    lufs_values = [r["lufs"] for r in results]
    avg_lufs = float(np.mean(lufs_values))
    lufs_range = float(max(lufs_values) - min(lufs_values))
    tinny_tracks = [r["filename"] for r in results if r["tinniness_ratio"] > 0.6]

    recommendations = []
    if lufs_range > 2.0:
        recommendations.append(
            f"LUFS range is {lufs_range:.1f} dB — target < 2 dB for album consistency."
        )
    if tinny_tracks:
        recommendations.append(
            f"Tinny tracks needing high-mid EQ cut (2-6kHz): {', '.join(tinny_tracks)}"
        )
    if avg_lufs < -16:
        recommendations.append(
            f"Average LUFS is {avg_lufs:.1f} — consider boosting toward -14 LUFS for streaming."
        )

    return _safe_json({
        "tracks": results,
        "summary": {
            "track_count": len(results),
            "avg_lufs": avg_lufs,
            "lufs_range": lufs_range,
            "tinny_tracks": tinny_tracks,
        },
        "recommendations": recommendations,
    })


@mcp.tool()
async def qc_audio(album_slug: str, subfolder: str = "", checks: str = "") -> str:
    """Run technical QC checks on audio tracks.

    Scans WAV files for mono compatibility, phase correlation, clipping,
    clicks/pops, silence issues, format validation, and spectral balance.

    Args:
        album_slug: Album slug (e.g., "my-album")
        subfolder: Optional subfolder within audio dir (e.g., "mastered")
        checks: Comma-separated checks to run (default: all).
                Options: mono, phase, clipping, clicks, silence, format, spectral

    Returns:
        JSON with per-track QC results, summary, and verdicts
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug, subfolder)
    if err:
        return err

    from tools.mastering.qc_tracks import qc_track, ALL_CHECKS

    wav_files = sorted(audio_dir.glob("*.wav"))
    wav_files = [f for f in wav_files if "venv" not in str(f)]
    if not wav_files:
        return _safe_json({
            "error": f"No WAV files found in {audio_dir}",
            "suggestion": "Check the album slug or subfolder.",
        })

    # Parse checks filter
    active_checks = None
    if checks:
        active_checks = [c.strip() for c in checks.split(",")]
        invalid = [c for c in active_checks if c not in ALL_CHECKS]
        if invalid:
            return _safe_json({
                "error": f"Unknown checks: {', '.join(invalid)}",
                "valid_checks": ALL_CHECKS,
            })

    loop = asyncio.get_running_loop()
    results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, qc_track, str(wav), active_checks)
        results.append(result)

    # Build summary
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    warned = sum(1 for r in results if r["verdict"] == "WARN")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")

    if failed > 0:
        verdict = "FAILURES FOUND"
    elif warned > 0:
        verdict = "WARNINGS"
    else:
        verdict = "ALL PASS"

    return _safe_json({
        "tracks": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "warned": warned,
            "failed": failed,
        },
        "verdict": verdict,
    })


@mcp.tool()
async def master_audio(
    album_slug: str,
    genre: str = "",
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float = 0.0,
    cut_highs: float = 0.0,
    dry_run: bool = False,
    source_subfolder: str = "",
) -> str:
    """Master audio tracks for streaming platforms.

    Normalizes loudness, applies optional EQ, and limits peaks. Creates
    mastered files in a mastered/ subfolder within the audio directory.

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset to apply (overrides EQ/LUFS defaults if set)
        target_lufs: Target integrated loudness (default: -14.0)
        ceiling_db: True peak ceiling in dB (default: -1.0)
        cut_highmid: High-mid EQ cut in dB at 3.5kHz (e.g., -2.0)
        cut_highs: High shelf cut in dB at 8kHz
        dry_run: If true, analyze only without writing files
        source_subfolder: Read WAV files from this subfolder instead of the
            base audio dir (e.g., "polished" to master from mix-engineer output)

    Returns:
        JSON with per-track results, settings applied, and summary
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    # If source_subfolder specified, read from that subfolder
    source_dir = audio_dir
    if source_subfolder:
        source_dir = audio_dir / source_subfolder
        if not source_dir.is_dir():
            return _safe_json({
                "error": f"Source subfolder not found: {source_dir}",
                "suggestion": f"Run polish_audio first to create {source_subfolder}/ output.",
            })

    from tools.mastering.master_tracks import (
        master_track as _master_track,
        load_genre_presets,
    )
    import numpy as np
    import soundfile as sf
    import pyloudnorm as pyln

    # Apply genre preset if specified
    effective_lufs = target_lufs
    effective_highmid = cut_highmid
    effective_highs = cut_highs
    genre_applied = None

    if genre:
        presets = load_genre_presets()
        genre_key = genre.lower()
        if genre_key not in presets:
            return _safe_json({
                "error": f"Unknown genre: {genre}",
                "available_genres": sorted(presets.keys()),
            })
        preset_lufs, preset_highmid, preset_highs = presets[genre_key]
        # Genre preset provides defaults; explicit non-default args override
        if target_lufs == -14.0:
            effective_lufs = preset_lufs
        if cut_highmid == 0.0:
            effective_highmid = preset_highmid
        if cut_highs == 0.0:
            effective_highs = preset_highs
        genre_applied = genre_key

    # Build EQ settings
    eq_settings = []
    if effective_highmid != 0:
        eq_settings.append((3500, effective_highmid, 1.5))
    if effective_highs != 0:
        eq_settings.append((8000, effective_highs, 0.7))

    output_dir = audio_dir / "mastered"
    if not dry_run:
        output_dir.mkdir(exist_ok=True)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {source_dir}"})

    loop = asyncio.get_running_loop()
    track_results = []

    for wav_file in wav_files:
        output_path = output_dir / wav_file.name
        if dry_run:
            # Dry run: just measure current loudness
            def _dry_run_measure(path):
                data, rate = sf.read(str(path))
                if len(data.shape) == 1:
                    data = np.column_stack([data, data])
                meter = pyln.Meter(rate)
                current = meter.integrated_loudness(data)
                if not np.isfinite(current):
                    return None
                return {
                    "filename": path.name,
                    "original_lufs": current,
                    "final_lufs": effective_lufs,
                    "gain_applied": effective_lufs - current,
                    "final_peak": -1.0,
                    "dry_run": True,
                }
            result = await loop.run_in_executor(None, _dry_run_measure, wav_file)
        else:
            def _do_master(in_path, out_path):
                return _master_track(
                    str(in_path), str(out_path),
                    target_lufs=effective_lufs,
                    eq_settings=eq_settings if eq_settings else None,
                    ceiling_db=ceiling_db,
                )
            result = await loop.run_in_executor(None, _do_master, wav_file, output_path)
            if result and not result.get("skipped"):
                result["filename"] = wav_file.name

        if result and not result.get("skipped"):
            track_results.append(result)

    if not track_results:
        return _safe_json({"error": "No tracks processed (all silent or no WAV files)."})

    gains = [r["gain_applied"] for r in track_results]
    finals = [r["final_lufs"] for r in track_results]

    return _safe_json({
        "tracks": track_results,
        "settings": {
            "target_lufs": effective_lufs,
            "ceiling_db": ceiling_db,
            "cut_highmid": effective_highmid,
            "cut_highs": effective_highs,
            "genre": genre_applied,
            "dry_run": dry_run,
        },
        "summary": {
            "tracks_processed": len(track_results),
            "gain_range": [min(gains), max(gains)],
            "final_lufs_range": max(finals) - min(finals),
            "output_dir": str(output_dir) if not dry_run else None,
        },
    })


@mcp.tool()
async def fix_dynamic_track(album_slug: str, track_filename: str) -> str:
    """Fix a track with excessive dynamic range that won't reach target LUFS.

    Applies gentle compression followed by standard mastering to bring
    the track into line with the rest of the album.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_filename: WAV filename (e.g., "01-track-name.wav")

    Returns:
        JSON with before/after metrics
    """
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    input_path = audio_dir / track_filename
    if not input_path.exists():
        return _safe_json({
            "error": f"Track file not found: {input_path}",
            "available_files": [f.name for f in audio_dir.glob("*.wav")],
        })

    output_dir = audio_dir / "mastered"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / track_filename

    from tools.mastering.fix_dynamic_track import gentle_compress
    from tools.mastering.master_tracks import apply_eq, soft_clip

    def _do_fix(in_path, out_path):
        import numpy as np
        import soundfile as sf
        import pyloudnorm as pyln

        data, rate = sf.read(str(in_path))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])

        meter = pyln.Meter(rate)
        original_lufs = meter.integrated_loudness(data)

        # Step 1: EQ
        data = apply_eq(data, rate, 3500, -2.0, 1.5)
        # Step 2: Gentle compression
        data = gentle_compress(data, threshold_db=-12, ratio=2.5, rate=rate)
        # Step 3: Normalize to -14 LUFS
        post_comp_lufs = meter.integrated_loudness(data)
        target_lufs = -14.0
        if np.isfinite(post_comp_lufs):
            gain_db = target_lufs - post_comp_lufs
            gain_linear = 10 ** (gain_db / 20)
            data = data * gain_linear
        # Step 4: Limit peaks
        ceiling = 10 ** (-1.0 / 20)
        peak = np.max(np.abs(data))
        if peak > ceiling:
            data = data * (ceiling / peak)
        data = soft_clip(data, ceiling)

        final_lufs = meter.integrated_loudness(data)
        final_peak = 20 * np.log10(np.max(np.abs(data))) if np.max(np.abs(data)) > 0 else float("-inf")

        sf.write(str(out_path), data, rate, subtype="PCM_16")

        return {
            "filename": in_path.name,
            "original_lufs": float(original_lufs),
            "final_lufs": float(final_lufs),
            "final_peak_db": float(final_peak),
            "output_path": str(out_path),
        }

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _do_fix, input_path, output_path)
    return _safe_json(result)


@mcp.tool()
async def master_with_reference(
    album_slug: str,
    reference_filename: str,
    target_filename: str = "",
) -> str:
    """Master tracks using a professionally mastered reference track.

    Uses the matchering library to match your track(s) to a reference.
    If target_filename is empty, processes all WAV files in the album's
    audio directory.

    Args:
        album_slug: Album slug (e.g., "my-album")
        reference_filename: Reference WAV filename in audio dir (e.g., "reference.wav")
        target_filename: Optional single target WAV (empty = batch all)

    Returns:
        JSON with per-track results
    """
    dep_err = _check_matchering()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    reference_path = audio_dir / reference_filename
    if not reference_path.exists():
        return _safe_json({
            "error": f"Reference file not found: {reference_path}",
            "suggestion": "Place the reference WAV in the album's audio directory.",
        })

    output_dir = audio_dir / "mastered"
    output_dir.mkdir(exist_ok=True)

    try:
        from tools.mastering.reference_master import master_with_reference as _ref_master
    except (ImportError, SystemExit):
        return _safe_json({
            "error": "matchering not installed. Install: pip install matchering",
        })

    loop = asyncio.get_running_loop()

    if target_filename:
        # Single file
        target_path = audio_dir / target_filename
        if not target_path.exists():
            return _safe_json({
                "error": f"Target file not found: {target_path}",
                "available_files": [f.name for f in audio_dir.glob("*.wav")],
            })
        output_path = output_dir / target_filename

        try:
            await loop.run_in_executor(
                None, _ref_master, target_path, reference_path, output_path
            )
            return _safe_json({
                "tracks": [{"filename": target_filename, "success": True, "output": str(output_path)}],
                "summary": {"success": 1, "failed": 0},
            })
        except Exception as e:
            return _safe_json({
                "tracks": [{"filename": target_filename, "success": False, "error": str(e)}],
                "summary": {"success": 0, "failed": 1},
            })
    else:
        # Batch all WAVs
        wav_files = sorted([
            f for f in audio_dir.glob("*.wav")
            if "venv" not in str(f) and f != reference_path
        ])
        if not wav_files:
            return _safe_json({"error": f"No WAV files found in {audio_dir}"})

        results = []
        for wav_file in wav_files:
            output_path = output_dir / wav_file.name
            try:
                await loop.run_in_executor(
                    None, _ref_master, wav_file, reference_path, output_path
                )
                results.append({"filename": wav_file.name, "success": True, "output": str(output_path)})
            except Exception as e:
                results.append({"filename": wav_file.name, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r["success"])
        return _safe_json({
            "tracks": results,
            "summary": {"success": success_count, "failed": len(results) - success_count},
        })


@mcp.tool()
async def transcribe_audio(
    album_slug: str,
    track_filename: str = "",
    formats: str = "pdf,xml",
    dry_run: bool = False,
) -> str:
    """Convert WAV files to sheet music using AnthemScore.

    Transcribes tracks from the album's audio directory into PDF and/or
    MusicXML format, outputting to a sheet-music/ subfolder.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_filename: Optional single WAV filename (empty = all WAVs)
        formats: Comma-separated output formats: "pdf", "xml", "midi" (default: "pdf,xml")
        dry_run: If true, show what would be done without doing it

    Returns:
        JSON with per-track results and summary
    """
    anthemscore_err = _check_anthemscore()
    if anthemscore_err:
        return _safe_json({"error": anthemscore_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    transcribe_mod = _import_sheet_music_module("transcribe")
    find_anthemscore = transcribe_mod.find_anthemscore
    transcribe_track = transcribe_mod.transcribe_track

    anthemscore_path = find_anthemscore()
    if not anthemscore_path:
        return _safe_json({
            "error": "AnthemScore not found on this system.",
            "suggestion": "Install from https://www.lunaverus.com/",
        })

    output_dir = audio_dir / "sheet-music"
    if not dry_run:
        output_dir.mkdir(exist_ok=True)

    # Parse formats
    fmt_list = [f.strip().lower() for f in formats.split(",")]

    # Build a namespace-like object for transcribe_track's args
    class Args:
        pass
    args = Args()
    args.pdf = "pdf" in fmt_list
    args.xml = "xml" in fmt_list
    args.midi = "midi" in fmt_list
    args.treble = False
    args.bass = False
    args.dry_run = dry_run

    if track_filename:
        wav_files = [audio_dir / track_filename]
        if not wav_files[0].exists():
            return _safe_json({
                "error": f"Track file not found: {wav_files[0]}",
                "available_files": [f.name for f in audio_dir.glob("*.wav")],
            })
    else:
        wav_files = sorted(audio_dir.glob("*.wav"))
        wav_files = [f for f in wav_files if "venv" not in str(f)]

    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {audio_dir}"})

    loop = asyncio.get_running_loop()
    results = []
    for wav_file in wav_files:
        success = await loop.run_in_executor(
            None, transcribe_track, anthemscore_path, wav_file, output_dir, args
        )
        outputs = []
        if success and not dry_run:
            for fmt in fmt_list:
                ext = {"pdf": ".pdf", "xml": ".xml", "midi": ".mid"}.get(fmt, "")
                out_file = output_dir / f"{wav_file.stem}{ext}"
                if out_file.exists():
                    outputs.append(str(out_file))
        results.append({
            "filename": wav_file.name,
            "success": success,
            "outputs": outputs,
        })

    success_count = sum(1 for r in results if r["success"])
    return _safe_json({
        "tracks": results,
        "summary": {
            "success": success_count,
            "failed": len(results) - success_count,
            "output_dir": str(output_dir),
            "formats": fmt_list,
        },
    })


@mcp.tool()
async def fix_sheet_music_titles(
    album_slug: str,
    dry_run: bool = False,
    export_pdf: bool = True,
) -> str:
    """Strip track number prefixes from MusicXML titles and optionally re-export PDFs.

    Fixes titles like "01 - Song Name" → "Song Name" in MusicXML files
    within the album's sheet-music/ directory.

    Args:
        album_slug: Album slug (e.g., "my-album")
        dry_run: If true, show changes without modifying files
        export_pdf: If true and MuseScore is available, re-export PDFs after fixing

    Returns:
        JSON with per-file results
    """
    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    sheet_dir = audio_dir / "sheet-music"
    if not sheet_dir.is_dir():
        return _safe_json({
            "error": f"Sheet music directory not found: {sheet_dir}",
            "suggestion": "Run transcribe_audio first to generate sheet music.",
        })

    import re as _re
    fix_titles_mod = _import_sheet_music_module("fix_titles")
    _fix_xml_title = fix_titles_mod.fix_xml_title

    xml_files = sorted([
        f for f in sheet_dir.glob("*.xml")
        if _re.match(r"^\d+", f.stem)
    ])
    musicxml_files = sorted([
        f for f in sheet_dir.glob("*.musicxml")
        if _re.match(r"^\d+", f.stem)
    ])
    xml_files.extend(musicxml_files)

    if not xml_files:
        return _safe_json({
            "error": f"No XML files with track number prefixes found in {sheet_dir}",
        })

    results = []
    for xml_file in xml_files:
        new_title = _fix_xml_title(xml_file, dry_run=dry_run)
        results.append({
            "filename": xml_file.name,
            "fixed": new_title is not None,
            "new_title": new_title,
        })

    fixed_count = sum(1 for r in results if r["fixed"])

    # Export PDFs if requested
    pdf_results = []
    if export_pdf and fixed_count > 0 and not dry_run:
        musescore = fix_titles_mod.find_musescore()
        if musescore:
            for xml_file in xml_files:
                success = fix_titles_mod.export_pdf(xml_file, musescore, dry_run=dry_run)
                pdf_results.append({"filename": xml_file.name, "exported": success})
        else:
            pdf_results = [{"warning": "MuseScore not found, skipping PDF export"}]

    return _safe_json({
        "files": results,
        "fixed_count": fixed_count,
        "pdf_exports": pdf_results,
    })


@mcp.tool()
async def create_songbook(
    album_slug: str,
    title: str,
    page_size: str = "letter",
) -> str:
    """Combine sheet music PDFs into a KDP-ready songbook.

    Creates a complete songbook with title page, copyright page, table
    of contents, and all track sheet music.

    Args:
        album_slug: Album slug (e.g., "my-album")
        title: Songbook title (e.g., "My Album Songbook")
        page_size: Page size - "letter", "9x12", or "6x9" (default: "letter")

    Returns:
        JSON with output path and metadata
    """
    dep_err = _check_songbook_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    sheet_dir = audio_dir / "sheet-music"
    if not sheet_dir.is_dir():
        return _safe_json({
            "error": f"Sheet music directory not found: {sheet_dir}",
            "suggestion": "Run transcribe_audio and fix_sheet_music_titles first.",
        })

    songbook_mod = _import_sheet_music_module("create_songbook")
    _create_songbook = songbook_mod.create_songbook
    auto_detect_cover_art = songbook_mod.auto_detect_cover_art
    get_website_from_config = songbook_mod.get_website_from_config

    # Get artist from state
    state = cache.get_state()
    config = state.get("config", {})
    artist = config.get("artist_name", "Unknown Artist")

    # Auto-detect cover art and website
    cover = auto_detect_cover_art(str(sheet_dir))
    website = get_website_from_config()

    # Build output path
    safe_title = title.replace(" ", "_").replace("/", "-")
    output_path = sheet_dir / f"{safe_title}.pdf"

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        lambda: _create_songbook(
            source_dir=str(sheet_dir),
            output_path=str(output_path),
            title=title,
            artist=artist,
            page_size_name=page_size,
            cover_image=cover,
            website=website,
        ),
    )

    if success:
        return _safe_json({
            "success": True,
            "output_path": str(output_path),
            "title": title,
            "artist": artist,
            "page_size": page_size,
        })
    else:
        return _safe_json({"error": "Songbook creation failed. Check sheet music directory."})


@mcp.tool()
async def generate_promo_videos(
    album_slug: str,
    style: str = "pulse",
    duration: int = 15,
    track_filename: str = "",
) -> str:
    """Generate promo videos with waveform visualization for social media.

    Creates 15-second vertical videos (1080x1920) combining album artwork,
    audio waveform visualization, and track titles.

    Args:
        album_slug: Album slug (e.g., "my-album")
        style: Visualization style - "pulse", "mirror", "mountains", "colorwave",
               "neon", "dual", "bars", "line", "circular" (default: "pulse")
        duration: Video duration in seconds (default: 15)
        track_filename: Optional single track WAV filename (empty = batch all)

    Returns:
        JSON with per-track results and summary
    """
    ffmpeg_err = _check_ffmpeg()
    if ffmpeg_err:
        return _safe_json({"error": ffmpeg_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    # Find artwork
    artwork_patterns = [
        "album.png", "album.jpg", "album-art.png", "album-art.jpg",
        "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
    ]
    artwork = None
    for pattern in artwork_patterns:
        candidate = audio_dir / pattern
        if candidate.exists():
            artwork = candidate
            break
    if not artwork:
        return _safe_json({
            "error": "No album artwork found in audio directory.",
            "suggestion": "Place album.png in the audio directory or use /bitwize-music:import-art.",
            "looked_for": artwork_patterns,
        })

    from tools.promotion.generate_promo_video import (
        generate_waveform_video,
        batch_process_album,
    )
    from tools.shared.fonts import find_font

    # Get artist from state
    state = cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "bitwize")

    font_path = find_font()

    output_dir = audio_dir / "promo_videos"
    output_dir.mkdir(exist_ok=True)

    loop = asyncio.get_running_loop()

    if track_filename:
        # Single track
        track_path = audio_dir / track_filename
        if not track_path.exists():
            # Also check mastered/
            track_path = audio_dir / "mastered" / track_filename
            if not track_path.exists():
                return _safe_json({
                    "error": f"Track file not found: {track_filename}",
                    "available_files": [f.name for f in audio_dir.glob("*.wav")],
                })

        # Resolve title: prefer markdown title from state cache over filename
        title = None
        albums = state.get("albums", {})
        normalized = _normalize_slug(album_slug)
        album_data = albums.get(normalized)
        if album_data:
            # Match track by stem (filename without extension)
            track_stem = track_path.stem
            track_slug = _normalize_slug(track_stem)
            tracks = album_data.get("tracks", {})
            track_data = tracks.get(track_slug)
            if track_data:
                title = track_data.get("title")

        if not title:
            # Fall back to cleaning up the filename
            import re as _re
            title = track_path.stem
            if " - " in title:
                title = title.split(" - ", 1)[-1]
            else:
                title = _re.sub(r"^\d{1,2}[\.\-_\s]+", "", title)
            title = title.replace("-", " ").replace("_", " ").title()

        output_path = output_dir / f"{track_path.stem}_promo.mp4"

        success = await loop.run_in_executor(
            None,
            lambda: generate_waveform_video(
                audio_path=track_path,
                artwork_path=artwork,
                title=title,
                output_path=output_path,
                duration=duration,
                style=style,
                artist_name=artist,
                font_path=font_path,
            ),
        )

        return _safe_json({
            "tracks": [{"filename": track_filename, "output": str(output_path), "success": success}],
            "summary": {"success": 1 if success else 0, "failed": 0 if success else 1},
        })
    else:
        # Batch all tracks
        # Resolve content dir for title lookup
        albums = state.get("albums", {})
        normalized = _normalize_slug(album_slug)
        content_dir = None
        album_data = albums.get(normalized)
        if album_data:
            content_dir_path = Path(album_data.get("path", ""))
            if content_dir_path.is_dir():
                content_dir = content_dir_path

        await loop.run_in_executor(
            None,
            lambda: batch_process_album(
                album_dir=audio_dir,
                artwork_path=artwork,
                output_dir=output_dir,
                duration=duration,
                style=style,
                artist_name=artist,
                font_path=font_path,
                content_dir=content_dir,
            ),
        )

        # Collect results from output dir
        output_files = sorted(output_dir.glob("*_promo.mp4"))
        results = [{"filename": f.name, "output": str(f), "success": True} for f in output_files]

        return _safe_json({
            "tracks": results,
            "summary": {
                "success": len(results),
                "output_dir": str(output_dir),
            },
        })


@mcp.tool()
async def generate_album_sampler(
    album_slug: str,
    clip_duration: int = 12,
    crossfade: float = 0.5,
) -> str:
    """Generate an album sampler video cycling through all tracks.

    Creates a single promotional video with short clips from each track,
    designed to fit Twitter's 2:20 (140 second) limit.

    Args:
        album_slug: Album slug (e.g., "my-album")
        clip_duration: Duration per track clip in seconds (default: 12)
        crossfade: Crossfade duration between clips in seconds (default: 0.5)

    Returns:
        JSON with output path, tracks included, and duration
    """
    ffmpeg_err = _check_ffmpeg()
    if ffmpeg_err:
        return _safe_json({"error": ffmpeg_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    # Find artwork
    artwork_patterns = [
        "album.png", "album.jpg", "album-art.png", "album-art.jpg",
        "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
    ]
    artwork = None
    for pattern in artwork_patterns:
        candidate = audio_dir / pattern
        if candidate.exists():
            artwork = candidate
            break
    if not artwork:
        return _safe_json({
            "error": "No album artwork found in audio directory.",
            "suggestion": "Place album.png in the audio directory.",
        })

    from tools.promotion.generate_album_sampler import (
        generate_album_sampler as _gen_sampler,
    )

    # Get artist from state
    state = cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "bitwize")

    # Pre-resolve titles from state cache (proper titles from markdown metadata)
    titles: dict[str, str] = {}
    albums = state.get("albums", {})
    normalized = _normalize_slug(album_slug)
    album_data = albums.get(normalized)
    if album_data:
        for track_slug, track_data in album_data.get("tracks", {}).items():
            title = track_data.get("title")
            if title:
                titles[track_slug] = title

    output_dir = audio_dir / "promo_videos"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "album_sampler.mp4"

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        lambda: _gen_sampler(
            tracks_dir=audio_dir,
            artwork_path=artwork,
            output_path=output_path,
            clip_duration=clip_duration,
            crossfade=crossfade,
            artist_name=artist,
            titles=titles,
        ),
    )

    if success and output_path.exists():
        file_size = output_path.stat().st_size / (1024 * 1024)
        # Count audio files
        audio_extensions = {".wav", ".mp3", ".flac", ".m4a"}
        track_count = sum(
            1 for f in audio_dir.iterdir()
            if f.suffix.lower() in audio_extensions
        )
        expected_duration = track_count * clip_duration - max(0, track_count - 1) * crossfade

        return _safe_json({
            "success": True,
            "output_path": str(output_path),
            "tracks_included": track_count,
            "clip_duration": clip_duration,
            "crossfade": crossfade,
            "expected_duration_seconds": expected_duration,
            "file_size_mb": round(file_size, 1),
            "twitter_limit_ok": expected_duration <= 140,
        })
    else:
        return _safe_json({"error": "Album sampler generation failed."})


@mcp.tool()
async def master_album(
    album_slug: str,
    genre: str = "",
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float = 0.0,
    cut_highs: float = 0.0,
) -> str:
    """End-to-end mastering pipeline: analyze, QC, master, verify, update status.

    Runs 7 sequential stages, stopping on failure:
        1. Pre-flight — resolve audio dir, check deps, find WAV files
        2. Analyze — measure LUFS, peaks, spectral balance on raw files
        3. Pre-QC — run technical QC checks on raw files (fails on FAIL verdict)
        4. Master — normalize loudness, apply EQ, limit peaks
        5. Verify — check mastered output meets targets (±0.5 dB LUFS, peak < ceiling)
        6. Post-QC — run technical QC on mastered files (fails on FAIL verdict)
        7. Update status — set tracks to Final, album to Complete

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset to apply (overrides EQ/LUFS defaults if set)
        target_lufs: Target integrated loudness (default: -14.0)
        ceiling_db: True peak ceiling in dB (default: -1.0)
        cut_highmid: High-mid EQ cut in dB at 3.5kHz (e.g., -2.0)
        cut_highs: High shelf cut in dB at 8kHz

    Returns:
        JSON with per-stage results, settings, warnings, and failure info
    """
    stages = {}
    warnings = []

    # --- Stage 1: Pre-flight ---
    dep_err = _check_mastering_deps()
    if dep_err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {"status": "fail", "detail": dep_err}},
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {"status": "fail", "detail": "Audio directory not found"}},
            "failed_stage": "pre_flight",
            "failure_detail": json.loads(err),
        })

    wav_files = sorted([
        f for f in audio_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    if not wav_files:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": {"pre_flight": {
                "status": "fail",
                "detail": f"No WAV files found in {audio_dir}",
            }},
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": f"No WAV files in {audio_dir}"},
        })

    stages["pre_flight"] = {
        "status": "pass",
        "track_count": len(wav_files),
        "audio_dir": str(audio_dir),
    }

    # Resolve genre presets and effective settings (same logic as master_audio)
    from tools.mastering.master_tracks import (
        master_track as _master_track,
        load_genre_presets,
    )
    import numpy as np

    effective_lufs = target_lufs
    effective_highmid = cut_highmid
    effective_highs = cut_highs
    genre_applied = None

    if genre:
        presets = load_genre_presets()
        genre_key = genre.lower()
        if genre_key not in presets:
            return _safe_json({
                "album_slug": album_slug,
                "stage_reached": "pre_flight",
                "stages": stages,
                "failed_stage": "pre_flight",
                "failure_detail": {
                    "reason": f"Unknown genre: {genre}",
                    "available_genres": sorted(presets.keys()),
                },
            })
        preset_lufs, preset_highmid, preset_highs = presets[genre_key]
        if target_lufs == -14.0:
            effective_lufs = preset_lufs
        if cut_highmid == 0.0:
            effective_highmid = preset_highmid
        if cut_highs == 0.0:
            effective_highs = preset_highs
        genre_applied = genre_key

    settings = {
        "genre": genre_applied,
        "target_lufs": effective_lufs,
        "ceiling_db": ceiling_db,
        "cut_highmid": effective_highmid,
        "cut_highs": effective_highs,
    }

    loop = asyncio.get_running_loop()

    # --- Stage 2: Analysis ---
    from tools.mastering.analyze_tracks import analyze_track

    analysis_results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        analysis_results.append(result)

    lufs_values = [r["lufs"] for r in analysis_results]
    avg_lufs = float(np.mean(lufs_values))
    lufs_range = float(max(lufs_values) - min(lufs_values))
    tinny_tracks = [r["filename"] for r in analysis_results if r["tinniness_ratio"] > 0.6]

    if tinny_tracks:
        for t in tinny_tracks:
            warnings.append(f"Pre-master: {t} — tinny (high-mid spike)")

    stages["analysis"] = {
        "status": "pass",
        "avg_lufs": round(avg_lufs, 1),
        "lufs_range": round(lufs_range, 1),
        "tinny_tracks": tinny_tracks,
    }

    # --- Stage 3: Pre-QC ---
    from tools.mastering.qc_tracks import qc_track

    pre_qc_results = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, qc_track, str(wav), None)
        pre_qc_results.append(result)

    pre_passed = sum(1 for r in pre_qc_results if r["verdict"] == "PASS")
    pre_warned = sum(1 for r in pre_qc_results if r["verdict"] == "WARN")
    pre_failed = sum(1 for r in pre_qc_results if r["verdict"] == "FAIL")

    # Collect warnings
    for r in pre_qc_results:
        for check_name, check_info in r["checks"].items():
            if check_info["status"] == "WARN":
                warnings.append(f"Pre-QC {r['filename']}: {check_name} WARN — {check_info['detail']}")

    if pre_failed > 0:
        failed_tracks = [r for r in pre_qc_results if r["verdict"] == "FAIL"]
        fail_details = []
        for r in failed_tracks:
            for check_name, check_info in r["checks"].items():
                if check_info["status"] == "FAIL":
                    fail_details.append({
                        "filename": r["filename"],
                        "check": check_name,
                        "status": "FAIL",
                        "detail": check_info["detail"],
                    })

        stages["pre_qc"] = {
            "status": "fail",
            "passed": pre_passed,
            "warned": pre_warned,
            "failed": pre_failed,
            "verdict": "FAILURES FOUND",
        }
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_qc",
            "stages": stages,
            "settings": settings,
            "warnings": warnings,
            "failed_stage": "pre_qc",
            "failure_detail": {
                "tracks_failed": [r["filename"] for r in failed_tracks],
                "details": fail_details,
            },
        })

    stages["pre_qc"] = {
        "status": "pass",
        "passed": pre_passed,
        "warned": pre_warned,
        "failed": 0,
        "verdict": "ALL PASS" if pre_warned == 0 else "WARNINGS",
    }

    # --- Stage 4: Mastering ---
    eq_settings = []
    if effective_highmid != 0:
        eq_settings.append((3500, effective_highmid, 1.5))
    if effective_highs != 0:
        eq_settings.append((8000, effective_highs, 0.7))

    output_dir = audio_dir / "mastered"
    output_dir.mkdir(exist_ok=True)

    master_results = []
    for wav_file in wav_files:
        output_path = output_dir / wav_file.name

        def _do_master(in_path, out_path, lufs, eq, ceil):
            return _master_track(
                str(in_path), str(out_path),
                target_lufs=lufs,
                eq_settings=eq if eq else None,
                ceiling_db=ceil,
            )

        result = await loop.run_in_executor(
            None, _do_master, wav_file, output_path,
            effective_lufs, eq_settings, ceiling_db,
        )
        if result and not result.get("skipped"):
            result["filename"] = wav_file.name
            master_results.append(result)

    if not master_results:
        stages["mastering"] = {"status": "fail", "detail": "No tracks processed (all silent)"}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "mastering",
            "stages": stages,
            "settings": settings,
            "warnings": warnings,
            "failed_stage": "mastering",
            "failure_detail": {"reason": "No tracks processed (all silent or no WAV files)"},
        })

    stages["mastering"] = {
        "status": "pass",
        "tracks_processed": len(master_results),
        "settings": settings,
        "output_dir": str(output_dir),
    }

    # --- Stage 5: Verification ---
    mastered_files = sorted([
        f for f in output_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    verify_results = []
    for wav in mastered_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        verify_results.append(result)

    verify_lufs = [r["lufs"] for r in verify_results]
    verify_avg = float(np.mean(verify_lufs))
    verify_range = float(max(verify_lufs) - min(verify_lufs))

    # Check thresholds
    out_of_spec = []
    for r in verify_results:
        issues = []
        if abs(r["lufs"] - effective_lufs) > 0.5:
            issues.append(f"LUFS {r['lufs']:.1f} outside ±0.5 dB of target {effective_lufs}")
        if r["peak_db"] > ceiling_db:
            issues.append(f"Peak {r['peak_db']:.1f} dB exceeds ceiling {ceiling_db} dB")
        if issues:
            out_of_spec.append({"filename": r["filename"], "issues": issues})

    album_range_fail = verify_range >= 1.0

    if out_of_spec or album_range_fail:
        fail_detail = {}
        if out_of_spec:
            fail_detail["tracks_out_of_spec"] = out_of_spec
        if album_range_fail:
            fail_detail["album_lufs_range"] = round(verify_range, 2)
            fail_detail["album_range_limit"] = 1.0

        stages["verification"] = {
            "status": "fail",
            "avg_lufs": round(verify_avg, 1),
            "lufs_range": round(verify_range, 2),
            "all_within_spec": False,
        }
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "verification",
            "stages": stages,
            "settings": settings,
            "warnings": warnings,
            "failed_stage": "verification",
            "failure_detail": fail_detail,
        })

    stages["verification"] = {
        "status": "pass",
        "avg_lufs": round(verify_avg, 1),
        "lufs_range": round(verify_range, 2),
        "all_within_spec": True,
    }

    # --- Stage 6: Post-QC ---
    post_qc_results = []
    for wav in mastered_files:
        result = await loop.run_in_executor(None, qc_track, str(wav), None)
        post_qc_results.append(result)

    post_passed = sum(1 for r in post_qc_results if r["verdict"] == "PASS")
    post_warned = sum(1 for r in post_qc_results if r["verdict"] == "WARN")
    post_failed = sum(1 for r in post_qc_results if r["verdict"] == "FAIL")

    for r in post_qc_results:
        for check_name, check_info in r["checks"].items():
            if check_info["status"] == "WARN":
                warnings.append(f"Post-QC {r['filename']}: {check_name} WARN — {check_info['detail']}")

    if post_failed > 0:
        failed_tracks = [r for r in post_qc_results if r["verdict"] == "FAIL"]
        fail_details = []
        for r in failed_tracks:
            for check_name, check_info in r["checks"].items():
                if check_info["status"] == "FAIL":
                    fail_details.append({
                        "filename": r["filename"],
                        "check": check_name,
                        "status": "FAIL",
                        "detail": check_info["detail"],
                    })

        stages["post_qc"] = {
            "status": "fail",
            "passed": post_passed,
            "warned": post_warned,
            "failed": post_failed,
            "verdict": "FAILURES FOUND",
        }
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "post_qc",
            "stages": stages,
            "settings": settings,
            "warnings": warnings,
            "failed_stage": "post_qc",
            "failure_detail": {
                "tracks_failed": [r["filename"] for r in failed_tracks],
                "details": fail_details,
            },
        })

    stages["post_qc"] = {
        "status": "pass",
        "passed": post_passed,
        "warned": post_warned,
        "failed": 0,
        "verdict": "ALL PASS" if post_warned == 0 else "WARNINGS",
    }

    # --- Stage 7: Update statuses ---
    # Use the in-memory state directly rather than re-fetching via
    # cache.get_state(), which could reload from disk and lose any
    # concurrent modifications made during the lengthy processing stages.
    state = cache._state or {}
    albums = state.get("albums", {})
    normalized_album = _normalize_slug(album_slug)
    album_data = albums.get(normalized_album)

    tracks_updated = 0
    status_errors = []

    if album_data:
        tracks = album_data.get("tracks", {})

        for track_slug, track_info in tracks.items():
            current_track_status = track_info.get("status", TRACK_NOT_STARTED)

            # Only transition Generated → Final; skip already-Final tracks
            if current_track_status.lower() == TRACK_FINAL.lower():
                continue  # already Final — nothing to do
            if current_track_status.lower() != TRACK_GENERATED.lower():
                status_errors.append(
                    f"Skipped '{track_slug}': status is '{current_track_status}' "
                    f"(expected '{TRACK_GENERATED}')"
                )
                continue

            track_path_str = track_info.get("path", "")
            if not track_path_str:
                status_errors.append(f"No path for track '{track_slug}'")
                continue

            track_path = Path(track_path_str)
            if not track_path.exists():
                status_errors.append(f"Track file not found: {track_path}")
                continue

            try:
                text = track_path.read_text(encoding="utf-8")
                pattern = re.compile(
                    r'^(\|\s*\*\*Status\*\*\s*\|)\s*.*?\s*\|',
                    re.MULTILINE,
                )
                match = pattern.search(text)
                if match:
                    new_row = f"{match.group(1)} {TRACK_FINAL} |"
                    updated_text = text[:match.start()] + new_row + text[match.end():]
                    track_path.write_text(updated_text, encoding="utf-8")

                    # Update cache
                    parsed = parse_track_file(track_path)
                    track_info.update({
                        "status": parsed.get("status", TRACK_FINAL),
                        "mtime": track_path.stat().st_mtime,
                    })
                    tracks_updated += 1
                else:
                    status_errors.append(f"Status field not found in {track_slug}")
            except Exception as e:
                status_errors.append(f"Error updating {track_slug}: {e}")

        # Update album status to Complete if all tracks are Final
        all_final = all(
            t.get("status", "").lower() == TRACK_FINAL.lower()
            for t in tracks.values()
        )
        album_status = None
        if all_final:
            album_path_str = album_data.get("path", "")
            if album_path_str:
                readme_path = Path(album_path_str) / "README.md"
                if readme_path.exists():
                    try:
                        text = readme_path.read_text(encoding="utf-8")
                        pattern = re.compile(
                            r'^(\|\s*\*\*Status\*\*\s*\|)\s*.*?\s*\|',
                            re.MULTILINE,
                        )
                        match = pattern.search(text)
                        if match:
                            new_row = f"{match.group(1)} {ALBUM_COMPLETE} |"
                            updated_text = text[:match.start()] + new_row + text[match.end():]
                            readme_path.write_text(updated_text, encoding="utf-8")
                            album_data["status"] = ALBUM_COMPLETE
                            album_status = ALBUM_COMPLETE
                    except Exception as e:
                        status_errors.append(f"Error updating album status: {e}")

        # Persist state cache
        try:
            write_state(state)
        except Exception as e:
            status_errors.append(f"Cache write failed: {e}")
    else:
        status_errors.append(f"Album '{album_slug}' not found in state cache")

    if status_errors:
        for err_msg in status_errors:
            warnings.append(f"Status update: {err_msg}")

    stages["status_update"] = {
        "status": "pass",
        "tracks_updated": tracks_updated,
        "album_status": album_status,
        "errors": status_errors if status_errors else None,
    }

    return _safe_json({
        "album_slug": album_slug,
        "stage_reached": "complete",
        "stages": stages,
        "settings": settings,
        "warnings": warnings,
        "failed_stage": None,
        "failure_detail": None,
    })


# =============================================================================
# Mix Polish Tools (per-stem audio cleanup before mastering)
# =============================================================================


def _check_mixing_deps() -> Optional[str]:
    """Return error message if mixing deps missing, else None."""
    missing = []
    for mod in ("numpy", "scipy", "soundfile", "noisereduce"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return (
            f"Missing mixing dependencies: {', '.join(missing)}. "
            "Install: pip install noisereduce scipy numpy soundfile"
        )
    return None


@mcp.tool()
async def polish_audio(
    album_slug: str,
    genre: str = "",
    use_stems: bool = True,
    dry_run: bool = False,
) -> str:
    """Polish audio tracks by processing stems or full mixes.

    When use_stems=True (default), looks for stem WAV files in a stems/
    subfolder with per-track directories (vocals.wav, drums.wav, bass.wav,
    other.wav). Processes each stem with targeted cleanup and remixes them.

    When use_stems=False, processes full mix WAV files directly.

    Writes polished output to a polished/ subfolder. Originals are preserved.

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset for stem-specific settings (e.g., "hip-hop")
        use_stems: If true, process per-stem WAVs; if false, process full mixes
        dry_run: If true, analyze only without writing files

    Returns:
        JSON with per-track results, settings, and summary
    """
    dep_err = _check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    from tools.mixing.mix_tracks import (
        mix_track_stems,
        mix_track_full,
        load_mix_presets,
        STEM_NAMES,
    )

    # Validate genre if specified
    if genre:
        presets = load_mix_presets()
        genre_key = genre.lower()
        if genre_key not in presets.get('genres', {}):
            return _safe_json({
                "error": f"Unknown genre: {genre}",
                "available_genres": sorted(presets.get('genres', {}).keys()),
            })

    output_dir = audio_dir / "polished"
    if not dry_run:
        output_dir.mkdir(exist_ok=True)

    loop = asyncio.get_running_loop()
    track_results = []

    if use_stems:
        # Stems mode: look for stems/ subdirectory with track folders
        stems_dir = audio_dir / "stems"
        if not stems_dir.is_dir():
            return _safe_json({
                "error": f"No stems/ directory found in {audio_dir}",
                "suggestion": "Import stems first, or use use_stems=false for full-mix mode.",
            })

        track_dirs = sorted([d for d in stems_dir.iterdir() if d.is_dir()])
        if not track_dirs:
            return _safe_json({"error": f"No track directories in {stems_dir}"})

        for track_dir in track_dirs:
            stem_paths = {}
            for stem_name in STEM_NAMES:
                stem_file = track_dir / f"{stem_name}.wav"
                if stem_file.exists():
                    stem_paths[stem_name] = str(stem_file)

            if not stem_paths:
                continue

            out_path = str(output_dir / f"{track_dir.name}.wav")

            def _do_stems(sp, op, g, dr):
                return mix_track_stems(sp, op, genre=g, dry_run=dr)

            result = await loop.run_in_executor(
                None, _do_stems, stem_paths, out_path,
                genre or None, dry_run,
            )

            if result:
                result["track_name"] = track_dir.name
                track_results.append(result)

    else:
        # Full-mix mode: process WAV files directly
        wav_files = sorted([
            f for f in audio_dir.iterdir()
            if f.suffix.lower() == ".wav" and "venv" not in str(f)
        ])

        if not wav_files:
            return _safe_json({"error": f"No WAV files found in {audio_dir}"})

        for wav_file in wav_files:
            out_path = str(output_dir / wav_file.name)

            def _do_full(ip, op, g, dr):
                return mix_track_full(ip, op, genre=g, dry_run=dr)

            result = await loop.run_in_executor(
                None, _do_full, str(wav_file), out_path,
                genre or None, dry_run,
            )

            if result:
                track_results.append(result)

    if not track_results:
        return _safe_json({"error": "No tracks were processed."})

    return _safe_json({
        "tracks": track_results,
        "settings": {
            "genre": genre or None,
            "use_stems": use_stems,
            "dry_run": dry_run,
        },
        "summary": {
            "tracks_processed": len(track_results),
            "mode": "stems" if use_stems else "full_mix",
            "output_dir": str(output_dir) if not dry_run else None,
        },
    })


@mcp.tool()
async def analyze_mix_issues(
    album_slug: str,
) -> str:
    """Analyze audio files for common mix issues and recommend settings.

    Scans WAV files for noise floor, muddiness (low-mid energy), harshness
    (high-mid energy), clicks, and stereo issues. Returns per-track diagnostics
    with recommended mix-engineer settings.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with per-track analysis, detected issues, and recommendations
    """
    dep_err = _check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    import numpy as np
    import soundfile as sf

    loop = asyncio.get_running_loop()

    wav_files = sorted([
        f for f in audio_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {audio_dir}"})

    def _analyze_one(wav_path):
        data, rate = sf.read(str(wav_path))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])

        result = {"filename": wav_path.name, "issues": [], "recommendations": {}}

        # Overall metrics
        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data ** 2)))
        result["peak"] = peak
        result["rms"] = rms

        # Noise floor estimate (quietest 10% of signal)
        abs_signal = np.abs(data[:, 0])
        sorted_abs = np.sort(abs_signal)
        noise_floor = float(np.mean(sorted_abs[:len(sorted_abs) // 10]))
        result["noise_floor"] = noise_floor
        if noise_floor > 0.005:
            result["issues"].append("elevated_noise_floor")
            result["recommendations"]["noise_reduction"] = min(0.8, noise_floor * 100)

        # Spectral analysis (simplified: energy in frequency bands)
        from scipy import signal as sig
        freqs, psd = sig.welch(data[:, 0], rate, nperseg=min(4096, len(data)))

        # Low-mid energy (150-400 Hz) — muddiness indicator
        low_mid_mask = (freqs >= 150) & (freqs <= 400)
        total_energy = float(np.sum(psd))
        if total_energy > 0:
            low_mid_ratio = float(np.sum(psd[low_mid_mask])) / total_energy
            result["low_mid_ratio"] = low_mid_ratio
            if low_mid_ratio > 0.35:
                result["issues"].append("muddy_low_mids")
                result["recommendations"]["mud_cut_db"] = -3.0

        # High-mid energy (2-5 kHz) — harshness indicator
        high_mid_mask = (freqs >= 2000) & (freqs <= 5000)
        if total_energy > 0:
            high_mid_ratio = float(np.sum(psd[high_mid_mask])) / total_energy
            result["high_mid_ratio"] = high_mid_ratio
            if high_mid_ratio > 0.25:
                result["issues"].append("harsh_highmids")
                result["recommendations"]["high_tame_db"] = -2.0

        # Click detection (sudden amplitude spikes)
        diff = np.diff(data[:, 0])
        diff_std = float(np.std(diff))
        if diff_std > 0:
            click_count = int(np.sum(np.abs(diff) > 6 * diff_std))
            result["click_count"] = click_count
            if click_count > 10:
                result["issues"].append("clicks_detected")
                result["recommendations"]["click_removal"] = True

        # Sub-bass rumble (< 30 Hz)
        sub_mask = freqs < 30
        if total_energy > 0:
            sub_ratio = float(np.sum(psd[sub_mask])) / total_energy
            result["sub_ratio"] = sub_ratio
            if sub_ratio > 0.15:
                result["issues"].append("sub_rumble")
                result["recommendations"]["highpass_cutoff"] = 35

        if not result["issues"]:
            result["issues"].append("none_detected")

        return result

    track_analyses = []
    for wav_file in wav_files:
        analysis = await loop.run_in_executor(None, _analyze_one, wav_file)
        track_analyses.append(analysis)

    # Album-level summary
    all_issues = set()
    for a in track_analyses:
        all_issues.update(i for i in a["issues"] if i != "none_detected")

    return _safe_json({
        "tracks": track_analyses,
        "album_summary": {
            "tracks_analyzed": len(track_analyses),
            "common_issues": sorted(all_issues),
            "audio_dir": str(audio_dir),
        },
    })


@mcp.tool()
async def polish_album(
    album_slug: str,
    genre: str = "",
) -> str:
    """End-to-end mix polish pipeline: analyze, polish stems, verify.

    Runs 3 sequential stages:
        1. Analyze — scan for mix issues and recommend settings
        2. Polish — process stems (or full mixes) with appropriate settings
        3. Verify — check polished output quality

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset for stem-specific settings

    Returns:
        JSON with per-stage results, settings, and recommendations
    """
    dep_err = _check_mixing_deps()
    if dep_err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "failed_stage": "pre_flight",
            "failure_detail": json.loads(err),
        })

    stages = {}

    # Determine mode: stems or full mix
    stems_dir = audio_dir / "stems"
    use_stems = stems_dir.is_dir() and any(stems_dir.iterdir())

    stages["pre_flight"] = {
        "status": "pass",
        "audio_dir": str(audio_dir),
        "mode": "stems" if use_stems else "full_mix",
        "stems_dir": str(stems_dir) if use_stems else None,
    }

    # --- Stage 1: Analysis ---
    analysis_json = await analyze_mix_issues(album_slug)
    analysis = json.loads(analysis_json)

    if "error" in analysis:
        stages["analysis"] = {"status": "fail", "detail": analysis["error"]}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "analysis",
            "stages": stages,
            "failed_stage": "analysis",
            "failure_detail": analysis,
        })

    stages["analysis"] = {
        "status": "pass",
        "tracks_analyzed": analysis["album_summary"]["tracks_analyzed"],
        "common_issues": analysis["album_summary"]["common_issues"],
    }

    # --- Stage 2: Polish ---
    polish_json = await polish_audio(
        album_slug=album_slug,
        genre=genre,
        use_stems=use_stems,
        dry_run=False,
    )
    polish = json.loads(polish_json)

    if "error" in polish:
        stages["polish"] = {"status": "fail", "detail": polish["error"]}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "polish",
            "stages": stages,
            "failed_stage": "polish",
            "failure_detail": polish,
        })

    stages["polish"] = {
        "status": "pass",
        "tracks_processed": polish["summary"]["tracks_processed"],
        "output_dir": polish["summary"]["output_dir"],
    }

    # --- Stage 3: Verify polished output ---
    import numpy as np
    import soundfile as sf

    polished_dir = audio_dir / "polished"
    if not polished_dir.is_dir():
        stages["verify"] = {"status": "fail", "detail": "polished/ directory not found"}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "verify",
            "stages": stages,
            "failed_stage": "verify",
        })

    polished_files = sorted([
        f for f in polished_dir.iterdir()
        if f.suffix.lower() == ".wav"
    ])

    loop = asyncio.get_running_loop()
    verify_results = []

    for wav in polished_files:
        def _verify(path):
            data, rate = sf.read(str(path))
            peak = float(np.max(np.abs(data)))
            rms = float(np.sqrt(np.mean(data ** 2)))
            finite = bool(np.all(np.isfinite(data)))
            return {
                "filename": path.name,
                "peak": peak,
                "rms": rms,
                "all_finite": finite,
                "clipping": peak > 0.99,
            }

        result = await loop.run_in_executor(None, _verify, wav)
        verify_results.append(result)

    clipping = [r["filename"] for r in verify_results if r["clipping"]]
    non_finite = [r["filename"] for r in verify_results if not r["all_finite"]]

    verify_pass = not clipping and not non_finite
    stages["verify"] = {
        "status": "pass" if verify_pass else "warn",
        "tracks_verified": len(verify_results),
        "clipping_tracks": clipping,
        "non_finite_tracks": non_finite,
    }

    return _safe_json({
        "album_slug": album_slug,
        "stage_reached": "complete",
        "stages": stages,
        "analysis": analysis.get("tracks"),
        "polish": polish.get("tracks"),
        "next_step": f"master_audio('{album_slug}', source_subfolder='polished')",
    })


# =============================================================================
# Database Tools (tweet/promo management)
# =============================================================================

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
    schema_path = PLUGIN_ROOT / "tools" / "database" / "schema.sql"
    if not schema_path.exists():
        return ""
    return schema_path.read_text(encoding="utf-8")


def _get_migration_files() -> list:
    """Get sorted list of migration SQL files."""
    migrations_dir = PLUGIN_ROOT / "tools" / "database" / "migrations"
    if not migrations_dir.exists():
        return []
    return sorted(migrations_dir.glob("*.sql"))


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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
        status = album_data.get("status", STATUS_UNKNOWN)

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


@mcp.tool()
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


def main():
    """Start the MCP server."""
    logger.info("Starting bitwize-music-state MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
