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
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional

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
from tools.state.indexer import (
    build_state,
    read_config,
    read_state,
    write_state,
    CURRENT_VERSION,
    STATE_FILE,
    CONFIG_FILE,
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

    def _update_mtimes(self):
        """Update cached mtime values."""
        try:
            if STATE_FILE.exists():
                self._state_mtime = STATE_FILE.stat().st_mtime
            if CONFIG_FILE.exists():
                self._config_mtime = CONFIG_FILE.stat().st_mtime
        except OSError:
            pass

    def get_state_ref(self) -> dict:
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
    core,
    content,
    text_analysis,
    lyrics_analysis,
    album_ops,
    gates,
    streaming,
    skills,
    status,
    promo,
    health,
    ideas,
    rename,
    processing,
    database,
    maintenance,
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
from handlers._shared import (  # noqa: E402, F401
    TRACK_NOT_STARTED, TRACK_SOURCES_PENDING, TRACK_SOURCES_VERIFIED,
    TRACK_IN_PROGRESS, TRACK_GENERATED, TRACK_FINAL,
    ALBUM_CONCEPT, ALBUM_RESEARCH_COMPLETE, ALBUM_SOURCES_VERIFIED,
    ALBUM_IN_PROGRESS, ALBUM_COMPLETE, ALBUM_RELEASED,
    TRACK_COMPLETED_STATUSES, ALBUM_VALID_STATUSES, STATUS_UNKNOWN,
    _VALID_GENRES, _GENRE_ALIASES,
    _normalize_slug, _safe_json,
    _extract_markdown_section, _extract_code_block,
    _update_frontmatter_block, _find_album_or_error,
    _resolve_audio_dir, _derive_title_from_slug,
    _find_wav_source_dir, _SECTION_NAMES, _STREAMING_PLATFORMS,
    _RE_SECTION, _RE_CODE_BLOCK,
    _SECTION_TAG_RE, _WORD_TOKEN_RE, _CROSS_TRACK_STOPWORDS,
    _MARKDOWN_LINK_RE,
)

# Core tools
from handlers.core import (  # noqa: E402, F401
    find_album, list_albums, get_track, list_tracks,
    get_session, update_session, rebuild_state, get_config,
    get_python_command, get_ideas, search, get_pending_verifications,
    resolve_path, resolve_track_file, list_track_files,
    extract_section, update_track_field, get_album_progress,
)

# Content tools
from handlers.content import (  # noqa: E402, F401
    load_override, get_reference, format_for_clipboard,
)

# Text analysis tools
from handlers.text_analysis import (  # noqa: E402, F401
    check_homographs, scan_artist_names, check_pronunciation_enforcement,
    check_explicit_content, extract_links, get_lyrics_stats,
    check_cross_track_repetition,
)

# Lyrics analysis tools
from handlers.lyrics_analysis import (  # noqa: E402, F401
    extract_distinctive_phrases, count_syllables,
    analyze_readability, analyze_rhyme_scheme, validate_section_structure,
)

# Album ops tools
from handlers.album_ops import (  # noqa: E402, F401
    get_album_full, validate_album_structure, create_album_structure,
)

# Gates tools
from handlers.gates import (  # noqa: E402, F401
    run_pre_generation_gates, check_streaming_lyrics,
)

# Streaming tools
from handlers.streaming import (  # noqa: E402, F401
    get_streaming_urls, update_streaming_url, verify_streaming_urls,
)

# Skills tools
from handlers.skills import (  # noqa: E402, F401
    list_skills, get_skill,
)

# Status tools
from handlers.status import (  # noqa: E402, F401
    update_album_status, create_track,
    _VALID_TRACK_STATUSES, _VALID_TRACK_TRANSITIONS, _VALID_ALBUM_TRANSITIONS,
    _CANONICAL_TRACK_STATUS, _CANONICAL_ALBUM_STATUS,
    _TRACK_STATUS_LEVEL, _ALBUM_STATUS_LEVEL,
    _validate_track_transition, _validate_album_transition,
    _check_album_track_consistency,
)

# Promo tools
from handlers.promo import (  # noqa: E402, F401
    get_promo_status, get_promo_content,
)

# Health tools
from handlers.health import (  # noqa: E402, F401
    get_plugin_version, check_venv_health,
)

# Ideas tools
from handlers.ideas import (  # noqa: E402, F401
    create_idea, update_idea,
)

# Rename tools
from handlers.rename import (  # noqa: E402, F401
    rename_album, rename_track,
)

# Processing tools
from handlers.processing import (  # noqa: E402, F401
    analyze_audio, qc_audio, master_audio, fix_dynamic_track,
    master_with_reference, transcribe_audio, prepare_singles,
    create_songbook, publish_sheet_music,
    generate_promo_videos, generate_album_sampler,
    master_album, polish_audio, analyze_mix_issues, polish_album,
)

# Database tools
from handlers.database import (  # noqa: E402, F401
    db_init, db_list_tweets, db_create_tweet, db_update_tweet,
    db_delete_tweet, db_search_tweets, db_sync_album, db_get_tweet_stats,
)

# Maintenance tools
from handlers.maintenance import (  # noqa: E402, F401
    reset_mastering, cleanup_legacy_venvs, migrate_audio_layout,
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
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
