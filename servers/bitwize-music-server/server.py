#!/usr/bin/env python3
"""
MCP server for bitwize-music plugin.

Provides structured access to albums, tracks, sessions, config, paths,
and track content without shelling out to Python or reading files manually.

Transport: stdio

Usage:
    python3 servers/bitwize-music-server/server.py

Tool handlers are organized into modules under ``handlers/``:

    core            - Albums, tracks, sessions, config, search, paths
    content         - Overrides, reference files, clipboard formatting
    text_analysis   - Homographs, artist names, pronunciation, explicit content
    lyrics_analysis - Syllable counting, readability, rhyme analysis, plagiarism
    album_ops       - Album structure validation and creation
    gates           - Pre-generation gates and release readiness checks
    streaming       - Streaming URL management
    skills          - Skills listing and detail queries
    status          - Album status transitions and track creation
    promo           - Promo directory status and content retrieval
    health          - Plugin version and venv health checks
    ideas           - Idea management (create, update)
    rename          - Album and track renaming
    processing      - Audio mastering, sheet music, promo videos, mix polishing
    database        - Tweet/promo management via PostgreSQL
    maintenance     - Reset mastering, legacy cleanup, audio layout migration
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

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

# Add server directory to sys.path for handlers package imports
SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

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
from datetime import UTC

from tools.state.indexer import (
    CONFIG_FILE,
    CURRENT_VERSION,
    STATE_FILE,
    build_state,
    read_config,
    read_state,
    write_state,
)
from tools.state.parsers import parse_album_readme, parse_track_file  # noqa: F401

# Initialize FastMCP server
mcp = FastMCP("bitwize-music-mcp")


# ---------------------------------------------------------------------------
# StateCache — in-memory state with lazy loading and staleness detection
# ---------------------------------------------------------------------------

class StateCache:
    """In-memory cache for state data with lazy loading and staleness detection.

    Thread-safe: all public methods acquire a lock before accessing state.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, Any] | None = None
        self._state_mtime: float = 0.0
        self._config_mtime: float = 0.0

    def get_state(self) -> dict[str, Any]:
        """Get state, loading from disk if needed or stale."""
        with self._lock:
            if self._is_stale() or self._state is None:
                logger.debug("State cache miss, loading from disk")
                self._load_from_disk()
            return self._state or {}

    def rebuild(self) -> dict[str, Any]:
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

    def update_session(self, **kwargs: Any) -> dict[str, Any]:
        """Update session fields and persist.

        Thread-safe: holds the lock for the entire read-modify-write cycle
        to prevent concurrent updates from overwriting each other.
        """
        from datetime import datetime

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

            session["updated_at"] = datetime.now(UTC).isoformat()
            state["session"] = session
            write_state(state)
            self._update_mtimes()
            return session  # type: ignore[no-any-return]

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

    def _load_from_disk(self) -> None:
        """Load state from disk into memory.

        If the on-disk state has a different schema version than the running
        code, an inline rebuild is performed (preserving session data).  This
        handles the upgrade path transparently.
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

    def _update_mtimes(self) -> None:
        """Update cached mtime values."""
        try:
            if STATE_FILE.exists():
                self._state_mtime = STATE_FILE.stat().st_mtime
            if CONFIG_FILE.exists():
                self._config_mtime = CONFIG_FILE.stat().st_mtime
        except OSError:
            pass

    def get_state_ref(self) -> dict[str, Any]:
        """Get a direct reference to the current in-memory state dict.

        Unlike get_state(), this does NOT check for staleness or reload from
        disk. Use only when you need to mutate the state object that album/track
        references point into (e.g., after writing a file and updating the cache
        in-place).
        """
        return self._state or {}


# Global cache instance
cache = StateCache()


# ---------------------------------------------------------------------------
# Initialize shared state for handler modules
# ---------------------------------------------------------------------------

from handlers import _shared

_shared.cache = cache
_shared.PLUGIN_ROOT = PLUGIN_ROOT


# ---------------------------------------------------------------------------
# Register all handler modules
# ---------------------------------------------------------------------------

from handlers import (
    album_ops,
    content,
    core,
    database,
    gates,
    health,
    ideas,
    lyrics_analysis,
    maintenance,
    processing,
    promo,
    rename,
    skills,
    status,
    streaming,
    text_analysis,
)

core.register(mcp)
content.register(mcp)
text_analysis.register(mcp)
lyrics_analysis.register(mcp)
album_ops.register(mcp)
gates.register(mcp)
streaming.register(mcp)
skills.register(mcp)
status.register(mcp)
promo.register(mcp)
health.register(mcp)
ideas.register(mcp)
rename.register(mcp)
processing.register(mcp)
database.register(mcp)
maintenance.register(mcp)


# ---------------------------------------------------------------------------
# Re-exports for backward compatibility (tests import server.X)
# ---------------------------------------------------------------------------

# Status constants and shared helpers (used by tests)
from handlers._shared import (  # noqa: F401
    _CROSS_TRACK_STOPWORDS,
    _GENRE_ALIASES,
    _MARKDOWN_LINK_RE,
    _RE_CODE_BLOCK,
    _RE_SECTION,
    _SECTION_NAMES,
    _SECTION_TAG_RE,
    _STREAMING_PLATFORMS,
    _get_valid_genres,
    _WORD_TOKEN_RE,
    ALBUM_COMPLETE,
    ALBUM_CONCEPT,
    ALBUM_IN_PROGRESS,
    ALBUM_RELEASED,
    ALBUM_RESEARCH_COMPLETE,
    ALBUM_SOURCES_VERIFIED,
    ALBUM_VALID_STATUSES,
    STATUS_UNKNOWN,
    TRACK_COMPLETED_STATUSES,
    TRACK_FINAL,
    TRACK_GENERATED,
    TRACK_IN_PROGRESS,
    TRACK_NOT_STARTED,
    TRACK_SOURCES_PENDING,
    TRACK_SOURCES_VERIFIED,
    _derive_title_from_slug,
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _find_wav_source_dir,
    _normalize_slug,
    _resolve_audio_dir,
    _safe_json,
    _update_frontmatter_block,
)

# Album ops tools
from handlers.album_ops import (  # noqa: F401
    create_album_structure,
    get_album_full,
    validate_album_structure,
)

# Content tools
from handlers.content import (  # noqa: F401
    format_for_clipboard,
    get_reference,
    load_override,
)

# Core tools
from handlers.core import (  # noqa: F401
    extract_section,
    find_album,
    get_album_progress,
    get_config,
    get_ideas,
    get_pending_verifications,
    get_python_command,
    get_session,
    get_track,
    list_albums,
    list_track_files,
    list_tracks,
    rebuild_state,
    resolve_path,
    resolve_track_file,
    search,
    update_session,
    update_track_field,
)

# Database tools
from handlers.database import (  # noqa: F401
    db_create_tweet,
    db_delete_tweet,
    db_get_tweet_stats,
    db_init,
    db_list_tweets,
    db_search_tweets,
    db_sync_album,
    db_update_tweet,
)

# Gates tools
from handlers.gates import (  # noqa: F401
    check_streaming_lyrics,
    run_pre_generation_gates,
)

# Health tools
from handlers.health import (  # noqa: F401
    check_venv_health,
    diagnose,
    get_plugin_version,
)

# Ideas tools
from handlers.ideas import (  # noqa: F401
    create_idea,
    update_idea,
)

# Lyrics analysis tools
from handlers.lyrics_analysis import (  # noqa: F401
    analyze_readability,
    analyze_rhyme_scheme,
    count_syllables,
    extract_distinctive_phrases,
    validate_section_structure,
)

# Maintenance tools
from handlers.maintenance import (  # noqa: F401
    cleanup_legacy_venvs,
    migrate_audio_layout,
    reset_mastering,
)

# Processing tools
from handlers.processing import (  # noqa: F401
    analyze_audio,
    analyze_mix_issues,
    create_songbook,
    fix_dynamic_track,
    generate_album_sampler,
    generate_promo_videos,
    master_album,
    master_audio,
    master_with_reference,
    polish_album,
    polish_audio,
    prepare_singles,
    publish_sheet_music,
    qc_audio,
    transcribe_audio,
)

# Promo tools
from handlers.promo import (  # noqa: F401
    get_promo_content,
    get_promo_status,
)

# Rename tools
from handlers.rename import (  # noqa: F401
    rename_album,
    rename_track,
)

# Skills tools
from handlers.skills import (  # noqa: F401
    get_skill,
    list_skills,
)

# Status tools
from handlers.status import (  # noqa: F401
    _ALBUM_STATUS_LEVEL,
    _CANONICAL_ALBUM_STATUS,
    _CANONICAL_TRACK_STATUS,
    _TRACK_STATUS_LEVEL,
    _VALID_ALBUM_TRANSITIONS,
    _VALID_TRACK_STATUSES,
    _VALID_TRACK_TRANSITIONS,
    _check_album_track_consistency,
    _validate_album_transition,
    _validate_track_transition,
    create_track,
    update_album_status,
)

# Streaming tools
from handlers.streaming import (  # noqa: F401
    get_streaming_urls,
    update_streaming_url,
    verify_streaming_urls,
)

# Text analysis tools
from handlers.text_analysis import (  # noqa: F401
    check_cross_track_repetition,
    check_explicit_content,
    check_homographs,
    check_pronunciation_enforcement,
    extract_links,
    get_lyrics_stats,
    scan_artist_names,
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the MCP server."""
    # Enable file-based debug logging if configured
    from tools.shared.logging_config import configure_file_logging
    config = read_config()
    if config:
        configure_file_logging(config)

    logger.info("Starting bitwize-music-state MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
