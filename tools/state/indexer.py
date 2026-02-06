#!/usr/bin/env python3
"""
State cache indexer for claude-ai-music-skills.

Scans all markdown files and produces a JSON state cache at
~/.bitwize-music/cache/state.json. Markdown files remain the source
of truth; state is a cache that can always be rebuilt.

Commands:
    rebuild  - Full scan, writes fresh state.json
    update   - Incremental update (only re-parse files with newer mtime)
    validate - Check state.json against schema
    show     - Pretty-print current state summary
    session  - Update session context in state.json

Usage (either form works):
    python3 tools/state/indexer.py rebuild
    python3 -m tools.state.indexer rebuild
"""

import argparse
import copy
import errno
import fcntl
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Lock timeout in seconds (prevents indefinite blocking)
LOCK_TIMEOUT_SECONDS = 10
# Stale lock threshold in seconds (locks older than this are considered abandoned)
STALE_LOCK_SECONDS = 60

# Ensure project root is on sys.path so this file works both as:
#   python3 tools/state/indexer.py rebuild
#   python3 -m tools.state.indexer rebuild
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Try to import yaml, provide helpful error if missing
try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

from tools.shared.colors import Colors
from tools.shared.config import CONFIG_PATH
from tools.shared.logging_config import setup_logging
from tools.state.parsers import parse_album_readme, parse_ideas_file, parse_track_file

logger = logging.getLogger(__name__)

# Schema version for state.json
CURRENT_VERSION = "1.0.0"

# Cache location (constant, not configurable)
CACHE_DIR = Path.home() / ".bitwize-music" / "cache"
STATE_FILE = CACHE_DIR / "state.json"
LOCK_FILE = CACHE_DIR / "state.lock"

CONFIG_FILE = CONFIG_PATH

# Migration chain for schema upgrades
# Format: "from_version": (migration_fn, "to_version")
MIGRATIONS: Dict[str, tuple] = {
    # Future migrations go here:
    # "1.0.0": (migrate_1_0_to_1_1, "1.1.0"),
}


def read_config() -> Optional[Dict[str, Any]]:
    """Read ~/.bitwize-music/config.yaml.

    Returns:
        Parsed config dict, or None if missing/invalid.
    """
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        logger.error("Cannot read config: %s", e)
        return None


def resolve_path(raw: str) -> Path:
    """Resolve a config path, expanding ~ and making absolute."""
    return Path(os.path.expanduser(raw)).resolve()


def get_config_mtime() -> float:
    """Get config file modification time."""
    try:
        return CONFIG_FILE.stat().st_mtime
    except OSError:
        return 0.0


def build_config_section(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build the config section of state.json."""
    paths = config.get('paths', {})
    artist = config.get('artist', {})

    content_root_raw = paths.get('content_root', '.')
    return {
        'content_root': str(resolve_path(content_root_raw)),
        'audio_root': str(resolve_path(paths.get('audio_root', content_root_raw + '/audio'))),
        'documents_root': str(resolve_path(paths.get('documents_root', content_root_raw + '/documents'))),
        'artist_name': artist.get('name', ''),
        'config_mtime': get_config_mtime(),
    }


def scan_albums(content_root: Path, artist_name: str) -> Dict[str, Dict[str, Any]]:
    """Scan all album READMEs and their tracks.

    Args:
        content_root: Root content directory.
        artist_name: Artist name from config.

    Returns:
        Dict mapping album slug to album data.
    """
    albums: Dict[str, Dict[str, Any]] = {}
    albums_dir = content_root / "artists" / artist_name / "albums"

    if not albums_dir.exists():
        return albums

    # Glob for album READMEs: albums/{genre}/{album}/README.md
    for readme_path in sorted(albums_dir.glob("*/*/README.md")):
        album_dir = readme_path.parent
        album_slug = album_dir.name
        genre = album_dir.parent.name

        album_data = parse_album_readme(readme_path)
        if '_error' in album_data:
            logger.warning("Skipping %s: %s", readme_path, album_data['_error'])
            continue

        # Scan tracks
        tracks = scan_tracks(album_dir)

        try:
            readme_mtime = readme_path.stat().st_mtime
        except OSError:
            continue  # File removed between glob and stat

        albums[album_slug] = {
            'path': str(album_dir),
            'genre': genre,
            'title': album_data.get('title', album_slug),
            'status': album_data.get('status', 'Unknown'),
            'explicit': album_data.get('explicit', False),
            'release_date': album_data.get('release_date'),
            'track_count': album_data.get('track_count', len(tracks)),
            'tracks_completed': album_data.get('tracks_completed', 0),
            'readme_mtime': readme_mtime,
            'tracks': tracks,
        }

    return albums


def scan_tracks(album_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Scan all track files in an album's tracks/ directory.

    Args:
        album_dir: Path to album directory.

    Returns:
        Dict mapping track slug to track data.
    """
    tracks: Dict[str, Dict[str, Any]] = {}
    tracks_dir = album_dir / "tracks"

    if not tracks_dir.exists():
        return tracks

    for track_path in sorted(tracks_dir.glob("*.md")):
        track_slug = track_path.stem  # e.g., "01-track-name"
        track_data = parse_track_file(track_path)

        if '_error' in track_data:
            logger.warning("Skipping %s: %s", track_path, track_data['_error'])
            continue

        try:
            track_mtime = track_path.stat().st_mtime
        except OSError:
            continue  # File removed between glob and stat

        tracks[track_slug] = {
            'path': str(track_path),
            'title': track_data.get('title', track_slug),
            'status': track_data.get('status', 'Unknown'),
            'explicit': track_data.get('explicit', False),
            'has_suno_link': track_data.get('has_suno_link', False),
            'sources_verified': track_data.get('sources_verified', 'N/A'),
            'mtime': track_mtime,
        }

    return tracks


def scan_ideas(config: Dict[str, Any], content_root: Path) -> Dict[str, Any]:
    """Scan IDEAS.md file.

    Args:
        config: Full config dict.
        content_root: Content root path.

    Returns:
        Dict with ideas data, or empty structure.
    """
    ideas_file_raw = config.get('paths', {}).get('ideas_file', '')
    if ideas_file_raw:
        ideas_path = resolve_path(ideas_file_raw)
    else:
        ideas_path = content_root / "IDEAS.md"

    if not ideas_path.exists():
        return {
            'file_mtime': 0.0,
            'counts': {},
            'items': [],
        }

    ideas_data = parse_ideas_file(ideas_path)
    if '_error' in ideas_data:
        logger.warning("Cannot parse IDEAS.md: %s", ideas_data['_error'])
        return {
            'file_mtime': 0.0,
            'counts': {},
            'items': [],
        }

    return {
        'file_mtime': ideas_path.stat().st_mtime,
        'counts': ideas_data.get('counts', {}),
        'items': ideas_data.get('items', []),
    }


def build_state(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build complete state from scratch.

    Args:
        config: Parsed config dict.

    Returns:
        Complete state dict ready for JSON serialization.
    """
    config_section = build_config_section(config)
    content_root = Path(config_section['content_root'])
    artist_name = config_section['artist_name']

    return {
        'version': CURRENT_VERSION,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'config': config_section,
        'albums': scan_albums(content_root, artist_name),
        'ideas': scan_ideas(config, content_root),
        'session': {
            'last_album': None,
            'last_track': None,
            'last_phase': None,
            'pending_actions': [],
            'updated_at': None,
        },
    }


def incremental_update(existing_state: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Incrementally update state, only re-parsing changed files.

    Compares mtime of each file against stored mtime. Only re-parses
    files that have been modified since last scan.

    Args:
        existing_state: Current state dict.
        config: Parsed config dict.

    Returns:
        Updated state dict.
    """
    config_section = build_config_section(config)
    content_root = Path(config_section['content_root'])
    artist_name = config_section['artist_name']

    state = copy.deepcopy(existing_state)
    state['config'] = config_section
    state['generated_at'] = datetime.now(timezone.utc).isoformat()

    # Check if config changed — smart rescan based on which fields changed
    old_config = existing_state.get('config', {})
    old_config_mtime = old_config.get('config_mtime', 0)
    if config_section['config_mtime'] != old_config_mtime:
        # Determine which config fields changed to decide rescan scope
        path_fields_changed = (
            config_section.get('content_root') != old_config.get('content_root') or
            config_section.get('artist_name') != old_config.get('artist_name')
        )
        ideas_path_changed = (
            path_fields_changed or
            config.get('paths', {}).get('ideas_file') !=
            existing_state.get('_ideas_file_raw')
        )

        if path_fields_changed:
            # Content root or artist name changed — full album rescan required
            state['albums'] = scan_albums(content_root, artist_name)
        # else: only non-path config changed (urls, generation, etc.) — keep albums

        if ideas_path_changed:
            state['ideas'] = scan_ideas(config, content_root)
        # else: ideas path unchanged — keep ideas

        # Store ideas_file_raw for future comparison
        state['_ideas_file_raw'] = config.get('paths', {}).get('ideas_file', '')
        return state

    # Incremental album update
    albums_dir = content_root / "artists" / artist_name / "albums"
    existing_albums = state.get('albums', {})

    if albums_dir.exists():
        # Find current albums on disk
        current_album_slugs = set()
        for readme_path in albums_dir.glob("*/*/README.md"):
            album_dir = readme_path.parent
            slug = album_dir.name
            current_album_slugs.add(slug)

            existing_album = existing_albums.get(slug)

            # Check if README changed
            try:
                readme_mtime = readme_path.stat().st_mtime
            except OSError:
                continue  # File removed between glob and stat
            if existing_album and existing_album.get('readme_mtime') == readme_mtime:
                # README unchanged, check individual tracks only
                _update_tracks_incremental(existing_album, album_dir)
            else:
                # README changed or new album — re-parse album-level data
                album_data = parse_album_readme(readme_path)
                if '_error' not in album_data:
                    genre = album_dir.parent.name

                    # Preserve existing tracks and update incrementally
                    # (README change doesn't mean track files changed)
                    if existing_album and existing_album.get('tracks'):
                        tracks = existing_album['tracks']
                        _update_tracks_incremental(
                            {'tracks': tracks}, album_dir
                        )
                    else:
                        tracks = scan_tracks(album_dir)

                    existing_albums[slug] = {
                        'path': str(album_dir),
                        'genre': genre,
                        'title': album_data.get('title', slug),
                        'status': album_data.get('status', 'Unknown'),
                        'explicit': album_data.get('explicit', False),
                        'release_date': album_data.get('release_date'),
                        'track_count': album_data.get('track_count', len(tracks)),
                        'tracks_completed': album_data.get('tracks_completed', 0),
                        'readme_mtime': readme_mtime,
                        'tracks': tracks,
                    }

        # Remove albums that no longer exist on disk
        for slug in list(existing_albums.keys()):
            if slug not in current_album_slugs:
                del existing_albums[slug]

    state['albums'] = existing_albums

    # Incremental ideas update
    ideas_file_raw = config.get('paths', {}).get('ideas_file', '')
    if ideas_file_raw:
        ideas_path = resolve_path(ideas_file_raw)
    else:
        ideas_path = content_root / "IDEAS.md"

    old_ideas_mtime = state.get('ideas', {}).get('file_mtime', 0)
    if ideas_path.exists():
        current_mtime = ideas_path.stat().st_mtime
        if current_mtime != old_ideas_mtime:
            state['ideas'] = scan_ideas(config, content_root)
    else:
        state['ideas'] = {'file_mtime': 0.0, 'counts': {}, 'items': []}

    return state


def _update_tracks_incremental(album: Dict[str, Any], album_dir: Path):
    """Update individual tracks within an album incrementally."""
    tracks_dir = album_dir / "tracks"
    if not tracks_dir.exists():
        return

    existing_tracks = album.get('tracks', {})
    current_track_slugs = set()

    for track_path in sorted(tracks_dir.glob("*.md")):
        slug = track_path.stem
        current_track_slugs.add(slug)
        try:
            current_mtime = track_path.stat().st_mtime
        except OSError:
            continue  # File removed between glob and stat

        existing_track = existing_tracks.get(slug)
        if existing_track and existing_track.get('mtime') == current_mtime:
            continue  # Unchanged

        # Re-parse this track
        track_data = parse_track_file(track_path)
        if '_error' not in track_data:
            existing_tracks[slug] = {
                'path': str(track_path),
                'title': track_data.get('title', slug),
                'status': track_data.get('status', 'Unknown'),
                'explicit': track_data.get('explicit', False),
                'has_suno_link': track_data.get('has_suno_link', False),
                'sources_verified': track_data.get('sources_verified', 'N/A'),
                'mtime': current_mtime,
            }

    # Remove tracks that no longer exist
    for slug in list(existing_tracks.keys()):
        if slug not in current_track_slugs:
            del existing_tracks[slug]

    album['tracks'] = existing_tracks

    # Recompute completed count
    completed_statuses = {'Final', 'Generated', 'Complete'}
    album['tracks_completed'] = sum(
        1 for t in existing_tracks.values()
        if t.get('status') in completed_statuses
    )


def _acquire_lock_with_timeout(lock_fd, timeout: int = LOCK_TIMEOUT_SECONDS):
    """Acquire an exclusive file lock with timeout and stale lock recovery.

    Args:
        lock_fd: Open file descriptor for the lock file.
        timeout: Maximum seconds to wait for the lock.

    Raises:
        TimeoutError: If lock cannot be acquired within timeout.
    """
    deadline = time.monotonic() + timeout

    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return  # Lock acquired
        except OSError as e:
            if e.errno not in (errno.EACCES, errno.EAGAIN):
                raise  # Unexpected error

        # Check for stale lock
        try:
            lock_age = time.time() - LOCK_FILE.stat().st_mtime
            if lock_age > STALE_LOCK_SECONDS:
                logger.warning(
                    "Stale lock detected (%.0fs old), recovering", lock_age
                )
                # Touch the lock file to reset mtime, then retry
                LOCK_FILE.touch()
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except OSError:
                    pass  # Still held, continue waiting
        except OSError:
            pass  # Lock file may have been removed

        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Could not acquire state lock within {timeout}s. "
                f"Lock file: {LOCK_FILE}"
            )

        time.sleep(0.1)


def write_state(state: Dict[str, Any]):
    """Write state to cache file atomically with file locking.

    Acquires an exclusive lock (with timeout) to prevent concurrent writes,
    then writes to a temp file and renames for atomicity.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Restrict cache directory to owner-only access
    os.chmod(str(CACHE_DIR), 0o700)

    lock_fd = None
    tmp_fd = None
    tmp_path = None
    try:
        lock_fd = open(LOCK_FILE, 'w')
        _acquire_lock_with_timeout(lock_fd)

        # Use tempfile for unpredictable filename in the same directory
        tmp_fd = tempfile.NamedTemporaryFile(
            mode='w', dir=CACHE_DIR, suffix='.tmp',
            prefix='.state_', delete=False
        )
        tmp_path = Path(tmp_fd.name)
        # Restrict temp file to owner-only access
        os.chmod(tmp_fd.name, 0o600)
        json.dump(state, tmp_fd, indent=2, default=str)
        tmp_fd.write('\n')
        tmp_fd.flush()
        os.fsync(tmp_fd.fileno())
        tmp_fd.close()
        tmp_fd = None
        os.replace(str(tmp_path), str(STATE_FILE))
    except (OSError, TimeoutError) as e:
        logger.error("Cannot write state file: %s", e)
        # Clean up temp file
        if tmp_fd is not None:
            tmp_fd.close()
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()


def read_state() -> Optional[Dict[str, Any]]:
    """Read state from cache file.

    Returns:
        Parsed state dict, or None if missing/corrupted.
    """
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Corrupted state file: %s", e)
        return None


def migrate_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Apply all needed migrations in sequence.

    Args:
        state: Current state dict.

    Returns:
        Migrated state dict. If migration fails or version is
        unrecognized, returns None to trigger full rebuild.
    """
    version = state.get('version', '0.0.0')

    # If version is newer than what we know, rebuild
    if _version_compare(version, CURRENT_VERSION) > 0:
        return None  # Downgrade scenario, rebuild

    # If major version differs, rebuild
    if version.split('.')[0] != CURRENT_VERSION.split('.')[0]:
        return None

    # Apply migrations
    while version in MIGRATIONS:
        fn, next_version = MIGRATIONS[version]
        try:
            state = fn(state)
            state['version'] = next_version
            version = next_version
        except Exception as e:
            logger.warning("Migration failed: %s", e)
            return None

    return state


def _version_compare(a: str, b: str) -> int:
    """Compare two version strings. Returns -1, 0, or 1.

    Handles variable-length versions (e.g., "1.0" vs "1.0.0") by
    zero-padding the shorter one. Non-numeric parts are treated as 0.
    """
    def _parts(v):
        parts = []
        for x in v.split('.'):
            try:
                parts.append(int(x))
            except ValueError:
                parts.append(0)
        return parts
    pa, pb = _parts(a), _parts(b)
    # Pad shorter list with zeros
    max_len = max(len(pa), len(pb))
    pa.extend([0] * (max_len - len(pa)))
    pb.extend([0] * (max_len - len(pb)))
    for x, y in zip(pa, pb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def validate_state(state: Dict[str, Any]) -> List[str]:
    """Validate state against expected schema.

    Returns:
        List of validation error strings. Empty if valid.
    """
    errors = []

    if not isinstance(state, dict):
        return ["State is not a dict"]

    # Required top-level keys
    required_keys = {'version', 'generated_at', 'config', 'albums', 'ideas', 'session'}
    missing = required_keys - set(state.keys())
    if missing:
        errors.append(f"Missing top-level keys: {', '.join(missing)}")

    # Version check
    version = state.get('version', '')
    if not version:
        errors.append("Missing version field")
    elif not isinstance(version, str):
        errors.append(f"Version should be string, got {type(version).__name__}")

    # Config section
    config = state.get('config', {})
    if isinstance(config, dict):
        for key in ('content_root', 'audio_root', 'artist_name', 'config_mtime'):
            if key not in config:
                errors.append(f"Missing config.{key}")
    else:
        errors.append("config should be a dict")

    # Albums section
    albums = state.get('albums', {})
    if isinstance(albums, dict):
        for slug, album in albums.items():
            if not isinstance(album, dict):
                errors.append(f"Album '{slug}' should be a dict")
                continue
            for key in ('path', 'genre', 'title', 'status', 'tracks'):
                if key not in album:
                    errors.append(f"Album '{slug}' missing '{key}'")

            # Validate tracks
            tracks = album.get('tracks', {})
            if isinstance(tracks, dict):
                for track_slug, track in tracks.items():
                    if not isinstance(track, dict):
                        errors.append(f"Track '{slug}/{track_slug}' should be a dict")
                        continue
                    for key in ('path', 'title', 'status'):
                        if key not in track:
                            errors.append(f"Track '{slug}/{track_slug}' missing '{key}'")
    else:
        errors.append("albums should be a dict")

    # Ideas section
    ideas = state.get('ideas', {})
    if isinstance(ideas, dict):
        if 'counts' not in ideas:
            errors.append("Missing ideas.counts")
        if 'items' not in ideas:
            errors.append("Missing ideas.items")
    else:
        errors.append("ideas should be a dict")

    # Session section
    session = state.get('session', {})
    if not isinstance(session, dict):
        errors.append("session should be a dict")

    return errors


# ==========================================================================
# CLI Commands
# ==========================================================================

def cmd_rebuild(args):
    """Full rebuild of state cache."""
    logger.info("Building project index...")

    config = read_config()
    if config is None:
        logger.error("Config not found at %s", CONFIG_FILE)
        logger.error("Run /bitwize-music:configure to set up.")
        return 1

    state = build_state(config)

    # Preserve session data from existing state if present
    existing = read_state()
    if existing and 'session' in existing:
        state['session'] = existing['session']

    write_state(state)

    album_count = len(state['albums'])
    track_count = sum(
        len(a.get('tracks', {})) for a in state['albums'].values()
    )
    ideas_count = len(state.get('ideas', {}).get('items', []))

    logger.info("State cache rebuilt")
    print(f"  Albums: {album_count}")
    print(f"  Tracks: {track_count}")
    print(f"  Ideas: {ideas_count}")
    print(f"  Saved to: {STATE_FILE}")
    return 0


def cmd_update(args):
    """Incremental update of state cache."""
    config = read_config()
    if config is None:
        logger.error("Config not found at %s", CONFIG_FILE)
        return 1

    existing = read_state()
    if existing is None:
        logger.info("No existing state, performing full rebuild...")
        return cmd_rebuild(args)

    # Check schema version
    migrated = migrate_state(existing)
    if migrated is None:
        logger.info("State schema changed, performing full rebuild...")
        return cmd_rebuild(args)

    state = incremental_update(migrated, config)
    write_state(state)

    logger.info("State cache updated")
    return 0


def cmd_validate(args):
    """Validate state.json against schema."""
    state = read_state()
    if state is None:
        logger.error("No state file found at %s", STATE_FILE)
        logger.error("Run: python3 tools/state/indexer.py rebuild")
        return 1

    errors = validate_state(state)
    if errors:
        logger.error("State validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    # Also check version
    version = state.get('version', '')
    if version != CURRENT_VERSION:
        logger.warning("Version mismatch: state=%s, expected=%s", version, CURRENT_VERSION)
    else:
        logger.info("State is valid (v%s)", version)

    return 0


def _validate_session_value(value: str, field: str, max_len: int = 256) -> Optional[str]:
    """Validate a session context value. Returns error message or None."""
    if len(value) > max_len:
        return f"{field} too long ({len(value)} chars, max {max_len})"
    if '\x00' in value:
        return f"{field} contains null bytes"
    return None


def cmd_session(args):
    """Update session context in state.json."""
    state = read_state()
    if state is None:
        logger.error("No state file found. Run: python3 tools/state/indexer.py rebuild")
        return 1

    session = state.get('session', {})

    if args.clear:
        session = {
            'last_album': None,
            'last_track': None,
            'last_phase': None,
            'pending_actions': [],
            'updated_at': None,
        }
    else:
        for field, value in [('album', args.album), ('track', args.track),
                             ('phase', args.phase), ('add_action', args.add_action)]:
            if value is not None:
                err = _validate_session_value(value, field)
                if err:
                    logger.error("Invalid session value: %s", err)
                    return 1

        if args.album is not None:
            session['last_album'] = args.album
        if args.track is not None:
            session['last_track'] = args.track
        if args.phase is not None:
            session['last_phase'] = args.phase
        if args.add_action:
            actions = session.get('pending_actions', [])
            if len(actions) >= 100:
                logger.error("Too many pending actions (max 100). Use --clear to reset.")
                return 1
            actions.append(args.add_action)
            session['pending_actions'] = actions

    session['updated_at'] = datetime.now(timezone.utc).isoformat()
    state['session'] = session
    write_state(state)

    logger.info("Session updated")
    if session.get('last_album'):
        print(f"  Album: {session['last_album']}")
    if session.get('last_phase'):
        print(f"  Phase: {session['last_phase']}")
    if session.get('last_track'):
        print(f"  Track: {session['last_track']}")
    if session.get('pending_actions'):
        print(f"  Pending actions: {len(session['pending_actions'])}")
    return 0


def cmd_cleanup(args):
    """Remove albums from cache that no longer exist on disk."""
    state = read_state()
    if state is None:
        logger.error("No state file found. Run: python3 tools/state/indexer.py rebuild")
        return 1

    albums = state.get('albums', {})
    if not albums:
        logger.info("No albums in cache, nothing to clean up")
        return 0

    stale = []
    for slug, album in albums.items():
        album_path = album.get('path', '')
        if album_path and not Path(album_path).exists():
            stale.append(slug)

    if not stale:
        logger.info("All %d album paths exist on disk, nothing to clean up", len(albums))
        return 0

    for slug in stale:
        path = albums[slug].get('path', '?')
        if args.dry_run:
            logger.info("[DRY RUN] Would remove: %s (%s)", slug, path)
        else:
            logger.warning("Removing stale album: %s (%s)", slug, path)
            del albums[slug]

    if not args.dry_run:
        state['albums'] = albums
        write_state(state)
        logger.info("Removed %d stale album(s) from cache", len(stale))
    else:
        logger.info("[DRY RUN] Would remove %d stale album(s)", len(stale))

    return 0


def cmd_show(args):
    """Pretty-print current state summary."""
    state = read_state()
    if state is None:
        print("No state file found. Run: python3 tools/state/indexer.py rebuild")
        return 1

    print(f"{Colors.BOLD}State Cache Summary{Colors.NC}")
    print(f"  Version: {state.get('version', '?')}")
    print(f"  Generated: {state.get('generated_at', '?')}")
    print()

    # Config
    config = state.get('config', {})
    print(f"{Colors.BOLD}Config:{Colors.NC}")
    print(f"  Artist: {config.get('artist_name', '?')}")
    print(f"  Content root: {config.get('content_root', '?')}")
    print()

    # Albums
    albums = state.get('albums', {})
    print(f"{Colors.BOLD}Albums ({len(albums)}):{Colors.NC}")
    for slug, album in albums.items():
        track_count = len(album.get('tracks', {}))
        completed = album.get('tracks_completed', 0)
        status = album.get('status', '?')
        genre = album.get('genre', '?')
        status_color = Colors.GREEN if status == 'Released' else (
            Colors.YELLOW if status == 'In Progress' else Colors.NC
        )
        print(f"  {slug} ({genre}) - {status_color}{status}{Colors.NC} [{completed}/{track_count} tracks]")

        if args.verbose and album.get('tracks'):
            for track_slug, track in album['tracks'].items():
                t_status = track.get('status', '?')
                suno = ' [suno]' if track.get('has_suno_link') else ''
                print(f"    {track_slug}: {t_status}{suno}")
    print()

    # Ideas
    ideas = state.get('ideas', {})
    counts = ideas.get('counts', {})
    if counts:
        print(f"{Colors.BOLD}Ideas:{Colors.NC}")
        for status, count in counts.items():
            print(f"  {status}: {count}")
    else:
        print(f"{Colors.BOLD}Ideas:{Colors.NC} (none)")
    print()

    # Session
    session = state.get('session', {})
    if session.get('last_album'):
        print(f"{Colors.BOLD}Last Session:{Colors.NC}")
        print(f"  Album: {session.get('last_album', '?')}")
        if session.get('last_track'):
            print(f"  Track: {session['last_track']}")
        if session.get('last_phase'):
            print(f"  Phase: {session['last_phase']}")
        if session.get('pending_actions'):
            print("  Pending:")
            for action in session['pending_actions']:
                print(f"    - {action}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='State cache indexer for claude-ai-music-skills',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 tools/state/indexer.py rebuild
    python3 tools/state/indexer.py session --album my-album --phase Writing
    python3 -m tools.state.indexer show -v
        """
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # rebuild
    subparsers.add_parser('rebuild', help='Full scan, writes fresh state.json')

    # update
    subparsers.add_parser('update', help='Incremental update (only re-parse changed files)')

    # validate
    subparsers.add_parser('validate', help='Check state.json against schema')

    # show
    show_parser = subparsers.add_parser('show', help='Pretty-print current state summary')
    show_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    # cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove albums from cache that no longer exist on disk')
    cleanup_parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without changing state')

    # session
    session_parser = subparsers.add_parser('session', help='Update session context in state.json')
    session_parser.add_argument('--album', help='Set last_album')
    session_parser.add_argument('--track', help='Set last_track')
    session_parser.add_argument('--phase', help='Set last_phase')
    session_parser.add_argument('--add-action', help='Append a pending action')
    session_parser.add_argument('--clear', action='store_true', help='Clear all session data before applying')

    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    setup_logging(__name__)

    commands = {
        'rebuild': cmd_rebuild,
        'update': cmd_update,
        'validate': cmd_validate,
        'show': cmd_show,
        'cleanup': cmd_cleanup,
        'session': cmd_session,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main() or 0)
