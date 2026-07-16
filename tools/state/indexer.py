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

from __future__ import annotations

import argparse
import contextlib
import copy
import errno
import functools
import json
import logging
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# fcntl is Unix-only (CPython does not ship it on Windows), so the lock
# primitives are platform-gated. Both variants expose the same contract:
# _flock_nb raises OSError with errno EACCES/EAGAIN when the lock is held
# elsewhere, which is what _acquire_lock_with_timeout's backoff loop expects.
if sys.platform == "win32":
    import msvcrt

    def _flock_nb(lock_fd: Any) -> None:
        """Try to take an exclusive non-blocking lock on the first byte."""
        lock_fd.seek(0)
        msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)

    def _funlock(lock_fd: Any) -> None:
        """Release the byte lock (best-effort).

        Windows raises when unlocking a region this handle does not hold,
        and write_state() unlocks in ``finally`` even after a lock timeout.
        The handle is closed immediately after, which releases any lock.
        """
        lock_fd.seek(0)
        with contextlib.suppress(OSError):
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _flock_nb(lock_fd: Any) -> None:
        """Try to take an exclusive non-blocking flock on the file."""
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _funlock(lock_fd: Any) -> None:
        """Release the flock (no-op if not held)."""
        fcntl.flock(lock_fd, fcntl.LOCK_UN)

# Lock timeout in seconds (prevents indefinite blocking)
LOCK_TIMEOUT_SECONDS = 10

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
from tools.shared.config import CONFIG_PATH, parse_yaml_bool
from tools.shared.logging_config import setup_logging
from tools.state.parsers import (
    parse_album_readme,
    parse_ideas_file,
    parse_skill_file,
    parse_track_file,
)

logger = logging.getLogger(__name__)

# Schema version for state.json
CURRENT_VERSION = "1.4.0"

# Cache location (constant, not configurable)
CACHE_DIR = Path.home() / ".bitwize-music" / "cache"
STATE_FILE = CACHE_DIR / "state.json"
LOCK_FILE = CACHE_DIR / "state.lock"

CONFIG_FILE = CONFIG_PATH

def _read_plugin_version(plugin_root: Path) -> str | None:
    """Read plugin version from .claude-plugin/plugin.json.

    Args:
        plugin_root: Root directory of the plugin.

    Returns:
        Version string (e.g., "0.43.1"), or None if unreadable.
    """
    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        return None
    try:
        with open(plugin_json, encoding='utf-8') as f:
            data = json.load(f)
        version = data.get('version')
        return version if isinstance(version, str) else None
    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.warning("Cannot read plugin version: %s", e)
        return None


def _migrate_1_0_to_1_1(state: dict[str, Any]) -> dict[str, Any]:
    """Migrate state from 1.0.0 to 1.1.0: add skills section."""
    if 'skills' not in state:
        state['skills'] = {
            'skills_root': '',
            'skills_root_mtime': 0.0,
            'count': 0,
            'model_counts': {},
            'items': {},
        }
    return state


def _migrate_1_1_to_1_2(state: dict[str, Any]) -> dict[str, Any]:
    """Migrate state from 1.1.0 to 1.2.0: add plugin_version field."""
    if 'plugin_version' not in state:
        state['plugin_version'] = None
    return state


def _migrate_1_2_to_1_3(state: dict[str, Any]) -> dict[str, Any]:
    """Migrate state from 1.2.0 to 1.3.0: add album_collisions field."""
    if 'album_collisions' not in state:
        state['album_collisions'] = []
    return state


def _migrate_1_3_to_1_4(state: dict[str, Any]) -> dict[str, Any]:
    """Migrate state from 1.3.0 to 1.4.0: re-coerce cached explicit flags.

    The pre-#388 parsers stored quoted frontmatter booleans (e.g.
    explicit: "false") as raw truthy strings; re-coerce cached values so
    they don't linger until the source file's mtime changes.
    """
    def _fix(entry: dict[str, Any]) -> None:
        if 'explicit' in entry:
            try:
                entry['explicit'] = parse_yaml_bool(entry['explicit'])
            except ValueError:
                entry['explicit'] = False

    for album in (state.get('albums') or {}).values():
        if isinstance(album, dict):
            _fix(album)
            for track in (album.get('tracks') or {}).values():
                if isinstance(track, dict):
                    _fix(track)
    return state


# Migration chain for schema upgrades
# Format: "from_version": (migration_fn, "to_version")
MIGRATIONS: dict[str, tuple[Any, str]] = {
    "1.0.0": (_migrate_1_0_to_1_1, "1.1.0"),
    "1.1.0": (_migrate_1_1_to_1_2, "1.2.0"),
    "1.2.0": (_migrate_1_2_to_1_3, "1.3.0"),
    "1.3.0": (_migrate_1_3_to_1_4, "1.4.0"),
}


def read_config() -> dict[str, Any] | None:
    """Read ~/.bitwize-music/config.yaml.

    Returns:
        Parsed config dict ({} for an empty file), or None if missing,
        unreadable, unparseable, or not a YAML mapping.
    """
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE, encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.error("Cannot read config: %s", e)
        return None
    if data is None:
        return {}
    if not isinstance(data, dict):
        # Valid YAML but wrong shape (e.g. top-level list or scalar) — callers
        # expect a mapping and would crash on .get() (#389)
        logger.error(
            "Config at %s parsed as %s, not a mapping — the file must contain "
            "top-level `key: value` pairs",
            CONFIG_FILE,
            type(data).__name__,
        )
        return None
    return data


def resolve_path(raw: str) -> Path:
    """Resolve a config path, expanding ~ and making absolute."""
    return Path(os.path.expanduser(raw)).resolve()


def get_config_mtime() -> float:
    """Get config file modification time."""
    try:
        return CONFIG_FILE.stat().st_mtime
    except OSError:
        return 0.0


def _cfg_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a config section as a dict, treating anything else as empty.

    An empty YAML section header (e.g. `paths:` with nothing under it) parses
    to None, not {}. config.get('paths', {}) returns that None (the key
    exists), so None must be normalized to {} here — otherwise .get() on None
    aborts every cache rebuild/update. (#376)
    A non-mapping value (e.g. `paths: [a, b]`) crashes the same way; the
    isinstance check runs before normalization so falsy non-mappings
    (`paths: []`) warn like truthy ones. (#391)
    """
    value = config.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        # Log only the key and type, never the value — sections like
        # `database` may carry credentials that must not leak into logs.
        logger.warning(
            "Config section %s is not a mapping (got %s) — using defaults",
            key, type(value).__name__,
        )
        return {}
    return value


def build_config_section(config: dict[str, Any]) -> dict[str, Any]:
    """Build the config section of state.json."""
    paths = _cfg_section(config, 'paths')
    artist = _cfg_section(config, 'artist')

    # NOTE: these warnings log only the key and type, never the raw value —
    # some sections (`database`) carry credentials that must not leak
    # into logs.
    def _cfg_bool(section: dict[str, Any], key: str, default: bool) -> bool:
        # bool() would turn quoted strings like "false" into True (#388);
        # parse YAML boolean literals, falling back to the key's default.
        value = section.get(key, default)
        try:
            return parse_yaml_bool(value)
        except ValueError:
            logger.warning(
                "Config %s is not a boolean (got %s) — using %s",
                key, type(value).__name__, default,
            )
            return default

    def _cfg_int(section: dict[str, Any], key: str, default: int) -> int:
        # int(True) == 1 would silently mangle the setting; int() raises
        # ValueError/TypeError on non-numeric strings and non-scalars (#391)
        # and OverflowError on YAML `.inf` floats.
        value = section.get(key, default)
        if isinstance(value, bool):
            logger.warning(
                "Config %s is not an integer (got %s) — using %s",
                key, type(value).__name__, default,
            )
            return default
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            logger.warning(
                "Config %s is not an integer (got %s) — using %s",
                key, type(value).__name__, default,
            )
            return default

    def _cfg_str(section: dict[str, Any], key: str, default: str) -> str:
        # Non-string path values (e.g. `content_root: 42`) crash resolve_path
        # and string concatenation (#391). A blank key (`overrides:` with no
        # value) parses to None and means "unset" — default silently,
        # mirroring the #376 empty-section semantics.
        value = section.get(key, default)
        if value is None:
            return default
        if not isinstance(value, str):
            logger.warning(
                "Config %s is not a string (got %s) — using %r",
                key, type(value).__name__, default,
            )
            return default
        return value

    content_root_raw = _cfg_str(paths, 'content_root', '.')
    content_root = str(resolve_path(content_root_raw))

    # Resolve overrides directory (custom path or default to {content_root}/overrides)
    overrides_raw = _cfg_str(paths, 'overrides', '')
    overrides_dir = str(resolve_path(overrides_raw)) if overrides_raw else str(Path(content_root) / 'overrides')

    # Database config (expose enabled flag, mask credentials)
    db_config = _cfg_section(config, 'database')
    db_enabled = _cfg_bool(db_config, 'enabled', False)
    database_section = {
        'enabled': db_enabled,
        'host': db_config.get('host', '') if db_enabled else '',
        'name': db_config.get('name', '') if db_enabled else '',
    }

    # Generation config (service settings and gates)
    gen_config = _cfg_section(config, 'generation')
    additional_genres_raw = gen_config.get('additional_genres', [])
    generation_section = {
        'service': gen_config.get('service', 'suno'),
        'require_suno_link_for_final': _cfg_bool(gen_config, 'require_suno_link_for_final', True),
        'max_lyric_words': _cfg_int(gen_config, 'max_lyric_words', 800),
        'require_source_path_for_documentary': _cfg_bool(
            gen_config, 'require_source_path_for_documentary', True),
        'additional_genres': [str(g).lower().strip() for g in additional_genres_raw]
        if isinstance(additional_genres_raw, list) else [],
    }

    return {
        'content_root': content_root,
        'audio_root': str(resolve_path(_cfg_str(paths, 'audio_root', content_root_raw + '/audio'))),
        'documents_root': str(resolve_path(_cfg_str(paths, 'documents_root', content_root_raw + '/documents'))),
        'overrides_dir': overrides_dir,
        'artist_name': _cfg_str(artist, 'name', ''),
        'config_mtime': get_config_mtime(),
        'database': database_section,
        'generation': generation_section,
    }


def scan_albums(
    content_root: Path,
    artist_name: str,
    collisions: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Scan all album READMEs and their tracks.

    Args:
        content_root: Root content directory.
        artist_name: Artist name from config.
        collisions: Optional out-param; collision records are appended
            when the same album slug exists under multiple genres (#392).

    Returns:
        Dict mapping album slug to album data.
    """
    albums: dict[str, dict[str, Any]] = {}
    albums_dir = content_root / "artists" / artist_name / "albums"

    if not albums_dir.exists():
        return albums

    # Group same-slug dirs structurally first (the sorted glob keeps
    # genre order deterministic): albums/{genre}/{album}/README.md.
    # The winner of a collision is the FIRST candidate that actually
    # indexes — i.e. whose README parses — not merely the first dir, so
    # an unreadable first twin never silently hands the slug to a later
    # twin without a collision record (#392).
    readmes_by_slug: dict[str, list[Path]] = {}
    for readme_path in sorted(albums_dir.glob("*/*/README.md")):
        readmes_by_slug.setdefault(
            readme_path.parent.name, []).append(readme_path)

    for album_slug, readme_paths in readmes_by_slug.items():
        winner_dir: Path | None = None
        for readme_path in readme_paths:
            album_dir = readme_path.parent

            album_data = parse_album_readme(readme_path)
            if '_error' in album_data:
                logger.warning("Skipping %s: %s", readme_path, album_data['_error'])
                continue  # try the next same-slug candidate, if any

            # Scan tracks
            tracks = scan_tracks(album_dir)

            try:
                readme_mtime = readme_path.stat().st_mtime
            except OSError:
                continue  # File removed between glob and stat

            albums[album_slug] = {
                'path': str(album_dir),
                'genre': album_dir.parent.name,
                'title': album_data.get('title', album_slug),
                'status': album_data.get('status', 'Unknown'),
                'explicit': album_data.get('explicit', False),
                'anchor_track': album_data.get('anchor_track'),
                'layout': album_data.get('layout'),
                'mastering': album_data.get('mastering') or {},
                'release_date': album_data.get('release_date'),
                'track_count': album_data.get('track_count', len(tracks)),
                'tracks_completed': album_data.get('tracks_completed', 0),
                'streaming_urls': album_data.get('streaming_urls', {}),
                'readme_mtime': readme_mtime,
                'tracks': tracks,
            }
            winner_dir = album_dir
            break  # remaining same-slug dirs are shadowed, never parsed

        if len(readme_paths) > 1 and winner_dir is not None:
            # Emit the record only with kept = the entry actually present
            # in the albums map. If no candidate indexed, there is no
            # entry and no record (the parse warnings above already fired).
            kept = albums[album_slug]
            shadowed = sorted(
                ({'genre': p.parent.parent.name, 'path': str(p.parent)}
                 for p in readme_paths if p.parent != winner_dir),
                key=lambda s: s['genre'],
            )
            logger.warning(
                "Album slug collision: '%s' — keeping %s, shadowing %s. "
                "Rename one album (/bitwize-music:rename) or move the "
                "directory, then rebuild the state cache.",
                album_slug, kept['path'],
                ', '.join(s['path'] for s in shadowed),
            )
            if collisions is not None:
                collisions.append({
                    'slug': album_slug,
                    'kept': {'genre': kept['genre'], 'path': kept['path']},
                    'shadowed': shadowed,
                })

    return albums


def scan_tracks(album_dir: Path) -> dict[str, dict[str, Any]]:
    """Scan all track files in an album's tracks/ directory.

    Args:
        album_dir: Path to album directory.

    Returns:
        Dict mapping track slug to track data.
    """
    tracks: dict[str, dict[str, Any]] = {}
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


def _ideas_path(config: dict[str, Any], content_root: Path) -> Path:
    """Resolve the ideas file path (custom paths.ideas_file or default)."""
    ideas_file_raw = _cfg_section(config, 'paths').get('ideas_file', '')
    if ideas_file_raw is None:
        # A blank `ideas_file:` key parses to None and means "unset" —
        # default silently (#376 semantics)
        ideas_file_raw = ''
    elif not isinstance(ideas_file_raw, str):
        # Non-string values crash resolve_path (#391)
        logger.warning(
            "Config ideas_file is not a string (got %s) — using default",
            type(ideas_file_raw).__name__,
        )
        ideas_file_raw = ''
    if ideas_file_raw:
        return resolve_path(ideas_file_raw)
    return content_root / "IDEAS.md"


def scan_ideas(config: dict[str, Any], content_root: Path) -> dict[str, Any]:
    """Scan IDEAS.md file.

    Args:
        config: Full config dict.
        content_root: Content root path.

    Returns:
        Dict with ideas data, or empty structure.
    """
    ideas_path = _ideas_path(config, content_root)

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

    try:
        file_mtime = ideas_path.stat().st_mtime
    except OSError:
        file_mtime = 0.0

    return {
        'file_mtime': file_mtime,
        'counts': ideas_data.get('counts', {}),
        'items': ideas_data.get('items', []),
    }


def scan_skills(plugin_root: Path) -> dict[str, Any]:
    """Scan all skill SKILL.md files and build skills index.

    Args:
        plugin_root: Root of the plugin directory containing skills/.

    Returns:
        Dict with skills_root, skills_root_mtime, count, model_counts, items.
    """
    skills_dir = plugin_root / "skills"
    result: dict[str, Any] = {
        'skills_root': str(skills_dir),
        'skills_root_mtime': 0.0,
        'count': 0,
        'model_counts': {},
        'items': {},
    }

    if not skills_dir.exists():
        return result

    with contextlib.suppress(OSError):
        result['skills_root_mtime'] = skills_dir.stat().st_mtime

    model_counts: dict[str, int] = {}
    items: dict[str, dict[str, Any]] = {}

    for skill_path in sorted(skills_dir.glob("*/SKILL.md")):
        skill_data = parse_skill_file(skill_path)
        if '_error' in skill_data:
            logger.warning("Skipping skill %s: %s", skill_path, skill_data['_error'])
            continue

        name = skill_data['name']
        items[name] = skill_data

        tier = skill_data.get('model_tier', 'unknown')
        model_counts[tier] = model_counts.get(tier, 0) + 1

    result['items'] = items
    result['count'] = len(items)
    result['model_counts'] = model_counts
    return result


def build_state(config: dict[str, Any],
                plugin_root: Path | None = None) -> dict[str, Any]:
    """Build complete state from scratch.

    Args:
        config: Parsed config dict.
        plugin_root: Plugin root directory for skill scanning.
            Defaults to _PROJECT_ROOT.

    Returns:
        Complete state dict ready for JSON serialization.
    """
    if plugin_root is None:
        plugin_root = _PROJECT_ROOT

    config_section = build_config_section(config)
    content_root = Path(config_section['content_root'])
    artist_name = config_section['artist_name']

    installed_version = _read_plugin_version(plugin_root)
    album_collisions: list[dict[str, Any]] = []
    albums = scan_albums(content_root, artist_name, album_collisions)
    return {
        'version': CURRENT_VERSION,
        'generated_at': datetime.now(UTC).isoformat(),
        # plugin_version = currently-installed version, refreshed every build
        # (used for display). last_migrated_version = the version through
        # which migrations have been processed; only advances on explicit
        # acknowledgment. Seeding it to the installed version here is correct
        # for a brand-new install (no historical migrations to surface); a
        # rebuild over an existing state carries the prior value forward via
        # carry_migration_tracking(). See issue #320.
        'plugin_version': installed_version,
        'last_migrated_version': installed_version,
        'config': config_section,
        'albums': albums,
        'album_collisions': album_collisions,
        'ideas': scan_ideas(config, content_root),
        'skills': scan_skills(plugin_root),
        'session': {
            'last_album': None,
            'last_track': None,
            'last_phase': None,
            'pending_actions': [],
            'updated_at': None,
        },
    }


def incremental_update(
    existing_state: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any] | None:
    """Incrementally update state, only re-parsing changed files.

    Compares mtime of each file against stored mtime. Only re-parses
    files that have been modified since last scan.

    Args:
        existing_state: Current state dict.
        config: Parsed config dict.

    Returns:
        Updated state dict, or None when a top-level state section is
        wrong-typed and a full rebuild is required.
    """
    # Wrong-typed top-level sections (e.g. "config": [] or "albums": "x")
    # would crash the .get() lookups below — hand back None so the caller
    # falls back to a full rebuild, the same contract as migrate_state
    # (#393 family).
    for section_key in ('config', 'albums'):
        section_value = existing_state.get(section_key, {})
        if not isinstance(section_value, dict):
            logger.warning(
                "State section %s is not a mapping (got %s) — "
                "full rebuild required",
                section_key, type(section_value).__name__,
            )
            return None

    config_section = build_config_section(config)
    content_root = Path(config_section['content_root'])
    artist_name = config_section['artist_name']

    state = copy.deepcopy(existing_state)
    state['config'] = config_section
    state['generated_at'] = datetime.now(UTC).isoformat()

    # Update plugin_version from current plugin.json
    state['plugin_version'] = _read_plugin_version(_PROJECT_ROOT)

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
            _cfg_section(config, 'paths').get('ideas_file') !=
            existing_state.get('_ideas_file_raw')
        )

        if path_fields_changed:
            # Content root or artist name changed — full album rescan required
            rescan_collisions: list[dict[str, Any]] = []
            state['albums'] = scan_albums(content_root, artist_name, rescan_collisions)
            state['album_collisions'] = rescan_collisions
        # else: only non-path config changed (urls, generation, etc.) — keep albums

        if ideas_path_changed:
            state['ideas'] = scan_ideas(config, content_root)
        # else: ideas path unchanged — keep ideas

        # Store ideas_file_raw for future comparison
        state['_ideas_file_raw'] = _cfg_section(config, 'paths').get('ideas_file', '')
        return state

    # Incremental album update
    albums_dir = content_root / "artists" / artist_name / "albums"
    existing_albums = state.get('albums', {})

    if albums_dir.exists():
        collisions: list[dict[str, Any]] = []
        # Group same-slug dirs structurally first (the sorted glob keeps
        # genre order deterministic). The winner of a collision is the
        # FIRST candidate that actually indexes — a cache-valid entry
        # (path+mtime match) or a successful re-parse — mirroring
        # scan_albums, so record['kept'] always matches the albums
        # map (#392).
        readmes_by_slug: dict[str, list[Path]] = {}
        for readme_path in sorted(albums_dir.glob("*/*/README.md")):
            readmes_by_slug.setdefault(
                readme_path.parent.name, []).append(readme_path)

        current_album_slugs = set()
        for slug, readme_paths in readmes_by_slug.items():
            current_album_slugs.add(slug)
            existing_album = existing_albums.get(slug)

            winner_dir: Path | None = None
            for readme_path in readme_paths:
                album_dir = readme_path.parent

                # Check if README changed
                try:
                    readme_mtime = readme_path.stat().st_mtime
                except OSError:
                    continue  # File removed between glob and stat
                # The path must match too — a cross-genre twin's cached
                # entry must never be reused for the winner (#392).
                if (existing_album
                        and existing_album.get('path') == str(album_dir)
                        and existing_album.get('readme_mtime') == readme_mtime):
                    # README unchanged — the cache-valid entry counts as
                    # successfully indexed without re-parsing; check
                    # individual tracks only. Documented corner: a README
                    # that becomes unreadable WITHOUT an mtime change keeps
                    # its cached entry here, while a full rebuild would
                    # skip it.
                    _update_tracks_incremental(existing_album, album_dir)
                    winner_dir = album_dir
                    break  # remaining same-slug dirs are shadowed

                # README changed, new album, or cached entry points at a
                # different path — re-parse album-level data
                album_data = parse_album_readme(readme_path)
                if '_error' in album_data:
                    logger.warning(
                        "Skipping %s: %s", readme_path, album_data['_error'])
                    continue  # try the next same-slug candidate, if any

                genre = album_dir.parent.name

                # Preserve existing tracks and update incrementally
                # (README change doesn't mean track files changed) —
                # but only when the cached entry is for this same
                # directory, not a cross-genre twin.
                if (existing_album
                        and existing_album.get('path') == str(album_dir)
                        and existing_album.get('tracks')):
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
                    'anchor_track': album_data.get('anchor_track'),
                    'layout': album_data.get('layout'),
                    'mastering': album_data.get('mastering') or {},
                    'release_date': album_data.get('release_date'),
                    'track_count': album_data.get('track_count', len(tracks)),
                    'tracks_completed': album_data.get('tracks_completed', 0),
                    'streaming_urls': album_data.get('streaming_urls', {}),
                    'readme_mtime': readme_mtime,
                    'tracks': tracks,
                }
                winner_dir = album_dir
                break  # remaining same-slug dirs are shadowed

            if len(readme_paths) > 1 and winner_dir is not None:
                # Emit the record only with kept = the entry actually
                # present in the albums map. If no candidate indexed,
                # there is no record (the parse warnings above already
                # fired).
                kept = existing_albums[slug]
                shadowed = sorted(
                    ({'genre': p.parent.parent.name, 'path': str(p.parent)}
                     for p in readme_paths if p.parent != winner_dir),
                    key=lambda s: s['genre'],
                )
                collisions.append({
                    'slug': slug,
                    'kept': {'genre': kept['genre'], 'path': kept['path']},
                    'shadowed': shadowed,
                })
                logger.warning(
                    "Album slug collision: '%s' — keeping %s, shadowing %s. "
                    "Rename one album (/bitwize-music:rename) or move the "
                    "directory, then rebuild the state cache.",
                    slug, kept['path'],
                    ', '.join(s['path'] for s in shadowed),
                )

        # Remove albums that no longer exist on disk
        for slug in list(existing_albums.keys()):
            if slug not in current_album_slugs:
                del existing_albums[slug]

        # Collisions are recomputed only when the albums dir was actually
        # scanned — when it's missing, the albums map is deliberately
        # preserved above, so preserve the matching collision records
        # too (#392).
        state['album_collisions'] = collisions

    state['albums'] = existing_albums

    # Incremental ideas update
    ideas_path = _ideas_path(config, content_root)

    old_ideas_mtime = state.get('ideas', {}).get('file_mtime', 0)
    if ideas_path.exists():
        current_mtime = ideas_path.stat().st_mtime
        if current_mtime != old_ideas_mtime:
            state['ideas'] = scan_ideas(config, content_root)
    else:
        state['ideas'] = {'file_mtime': 0.0, 'counts': {}, 'items': []}

    # Incremental skills update
    existing_skills = state.get('skills', {})
    skills_root = existing_skills.get('skills_root', '')
    if skills_root:
        skills_dir = Path(skills_root)
        old_skills_mtime = existing_skills.get('skills_root_mtime', 0.0)
        if skills_dir.exists():
            try:
                current_skills_mtime = skills_dir.stat().st_mtime
            except OSError:
                current_skills_mtime = 0.0
            if current_skills_mtime != old_skills_mtime:
                state['skills'] = scan_skills(skills_dir.parent)
        # else: skills dir removed, keep existing (stale but harmless)
    # If no skills_root stored, leave skills as-is (migration will have added empty)

    return state


def _update_tracks_incremental(album: dict[str, Any], album_dir: Path) -> None:
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
    completed_statuses = {'Final', 'Generated'}
    album['tracks_completed'] = sum(
        1 for t in existing_tracks.values()
        if t.get('status') in completed_statuses
    )


def _acquire_lock_with_timeout(lock_fd: Any, timeout: int | float = LOCK_TIMEOUT_SECONDS) -> None:
    """Acquire an exclusive file lock with exponential backoff.

    Uses only OS-level advisory locking (``fcntl.flock`` on Unix,
    ``msvcrt.locking`` on Windows via ``_flock_nb``) — no mtime-based stale
    detection, which had a TOCTOU race.  These locks auto-release when the
    holding process dies, so stale locks self-heal.

    Args:
        lock_fd: Open file descriptor for the lock file.
        timeout: Maximum seconds to wait for the lock.

    Raises:
        TimeoutError: If lock cannot be acquired within timeout.
    """
    deadline = time.monotonic() + timeout
    wait = 0.05  # Initial backoff

    while True:
        try:
            _flock_nb(lock_fd)
            return  # Lock acquired
        except OSError as e:
            if e.errno not in (errno.EACCES, errno.EAGAIN):
                raise  # Unexpected error

        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Could not acquire state lock within {timeout}s. "
                f"Lock file: {LOCK_FILE}"
            )

        time.sleep(min(wait, deadline - time.monotonic()))
        wait = min(wait * 2, 1.0)  # Cap at 1 second


def write_state(state: dict[str, Any]) -> None:
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
        # Append mode: 'w' would truncate, which fails on Windows while
        # another process holds a byte-range lock on the file.
        lock_fd = open(LOCK_FILE, 'a', encoding='utf-8')  # noqa: SIM115
        _acquire_lock_with_timeout(lock_fd)

        # Use tempfile for unpredictable filename in the same directory
        tmp_fd = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode='w', dir=CACHE_DIR, suffix='.tmp',
            prefix='.state_', delete=False, encoding='utf-8'
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
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
        raise
    finally:
        if lock_fd is not None:
            _funlock(lock_fd)
            lock_fd.close()


def _quarantine_corrupt_state(reason: str) -> dict[str, Any]:
    """Back up an unusable state file and return an empty state."""
    logger.error("%s — backing up and returning empty state", reason)
    try:
        import shutil

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        backup_path = CACHE_DIR / f"state.{timestamp}.corrupt"
        shutil.copy2(STATE_FILE, backup_path)
        logger.error("Corrupted state backed up to %s", backup_path)
    except OSError as backup_err:
        logger.error("Could not backup corrupted state: %s", backup_err)
    return {}


def read_state() -> dict[str, Any] | None:
    """Read state from cache file.

    Returns:
        Parsed state dict, empty dict if corrupted or not a JSON object
        (after backup), or None if missing.
    """
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return _quarantine_corrupt_state(f"Corrupted state file: {e}")
    if not isinstance(data, dict):
        # JSON-valid but wrong shape (list/str/number) — same recovery as
        # corrupted JSON: back it up and start fresh (#393 family)
        return _quarantine_corrupt_state(
            f"State file is {type(data).__name__}, not a JSON object"
        )
    return data


def migrate_state(state: dict[str, Any]) -> dict[str, Any] | None:
    """Apply all needed migrations in sequence.

    Args:
        state: Current state dict.

    Returns:
        Migrated state dict. If the state is not a dict, migration fails,
        or the version is unrecognized, returns None to trigger full rebuild.
    """
    # Defensive: JSON-valid non-object states (list/str/number) reach here
    # from callers that bypass read_state()'s shape check — .get() below
    # would crash (#393 family)
    if not isinstance(state, dict):
        logger.warning(  # type: ignore[unreachable]
            "State is %s, not a dict — triggering full rebuild",
            type(state).__name__,
        )
        return None

    version = state.get('version', '0.0.0')

    # Non-string version (e.g. JSON "version": 1.2) would crash
    # _version_compare — treat as unrecognized and rebuild (#393)
    if not isinstance(version, str):
        logger.warning(
            "Non-string state version %r — triggering full rebuild", version
        )
        return None

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
    def _parts(v: str) -> list[int]:
        parts: list[int] = []
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
    for x, y in zip(pa, pb, strict=True):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def carry_migration_tracking(
    new_state: dict[str, Any],
    existing_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Preserve ``last_migrated_version`` across a full rebuild.

    ``build_state`` seeds ``last_migrated_version`` to the installed version,
    which is correct for a brand-new install (there are no historical
    migrations to surface). But when rebuilding over an EXISTING state we must
    not let a rebuild silently mark migrations as processed — carry the prior
    value forward. For a state written before this field existed the prior
    value is absent, so we record ``None``, keeping any pending migrations
    visible until they are explicitly acknowledged. See issue #320.

    Args:
        new_state: Freshly built state (mutated in place).
        existing_state: The prior on-disk state, or ``None`` for a first build.

    Returns:
        ``new_state`` (for convenient chaining).
    """
    if existing_state is None:
        return new_state
    prior = existing_state.get('last_migrated_version')
    if prior is not None and not isinstance(prior, str):
        # A wrong-typed value must not survive rebuilds only to crash
        # get_pending_migrations' version comparison later — drop it to
        # None, which keeps pending migrations visible (#393 family).
        logger.warning(
            "Non-string last_migrated_version (got %s) — treating as untracked",
            type(prior).__name__,
        )
        prior = None
    new_state['last_migrated_version'] = prior
    return new_state


def parse_migration_file(path: Path) -> dict[str, Any] | None:
    """Parse a migration markdown file's YAML frontmatter.

    Args:
        path: Path to a ``migrations/<version>.md`` file.

    Returns:
        Dict with ``version`` (frontmatter value, falling back to the file
        stem), ``summary``, ``categories``, ``actions``, ``body`` and
        ``file``; or ``None`` if the file is unreadable, has no frontmatter,
        or the frontmatter is not a valid YAML mapping.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith('---'):
        return None
    parts = text.split('---', 2)
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    version = meta.get('version')
    if not isinstance(version, str) or not version.strip():
        version = path.stem
    return {
        'version': version,
        'summary': meta.get('summary', ''),
        'categories': meta.get('categories', []),
        'actions': meta.get('actions', []),
        'body': parts[2].strip(),
        'file': str(path),
    }


def get_pending_migrations(
    state: dict[str, Any],
    plugin_root: Path | None = None,
) -> dict[str, Any]:
    """Compute migration notes the user has not yet processed.

    Compares the installed plugin version (``.claude-plugin/plugin.json``)
    against the state's ``last_migrated_version`` and returns the migration
    notes that fall in between, sorted ascending by version.

    Null semantics: when ``last_migrated_version`` is absent/``None`` (a state
    written before tracking existed — never a fresh install, which
    ``build_state`` seeds to the installed version) the full backlog up to the
    installed version is surfaced once, so a pre-tracking upgrader is no longer
    silently skipped. See issue #320.

    Args:
        state: Current state dict.
        plugin_root: Plugin root directory. Defaults to ``_PROJECT_ROOT``.

    Returns:
        Dict with ``installed_version``, ``last_migrated_version``,
        ``pending`` (list of parsed migrations) and ``reason`` (one of
        ``"untracked"``, ``"upgrade"``, ``"current"``, or ``"unknown"`` when
        the installed version can't be read).
    """
    if plugin_root is None:
        plugin_root = _PROJECT_ROOT
    installed = _read_plugin_version(plugin_root)
    last = state.get('last_migrated_version')
    if last is not None and not isinstance(last, str):
        # A wrong-typed value would crash _version_compare's .split() —
        # treat it as untracked, the same branch as a missing value
        # (#393 family).
        logger.warning(
            "Non-string last_migrated_version (got %s) — treating as untracked",
            type(last).__name__,
        )
        last = None

    parsed: list[dict[str, Any]] = []
    migrations_dir = plugin_root / 'migrations'
    if migrations_dir.is_dir():
        for mf in migrations_dir.glob('*.md'):
            if mf.name == 'README.md':
                continue
            migration = parse_migration_file(mf)
            if migration is not None:
                parsed.append(migration)

    # Cannot compare without an installed version — surface nothing (no crash).
    # Distinct from "current" so callers/telemetry can tell "up to date" apart
    # from "couldn't read plugin.json".
    if installed is None:
        return {
            'installed_version': None,
            'last_migrated_version': last,
            'pending': [],
            'reason': 'unknown',
        }

    # Only consider migrations at or below the installed version.
    candidates = [
        m for m in parsed if _version_compare(m['version'], installed) <= 0
    ]

    if last is None:
        pending = candidates
        reason = 'untracked'
    else:
        pending = [
            m for m in candidates if _version_compare(m['version'], last) > 0
        ]
        reason = 'upgrade' if pending else 'current'

    pending.sort(key=functools.cmp_to_key(
        lambda a, b: _version_compare(a['version'], b['version'])
    ))

    return {
        'installed_version': installed,
        'last_migrated_version': last,
        'pending': pending,
        'reason': reason,
    }


def validate_state(state: dict[str, Any]) -> list[str]:
    """Validate state against expected schema.

    Returns:
        List of validation error strings. Empty if valid.
    """
    errors = []

    if not isinstance(state, dict):
        return ["State is not a dict"]  # type: ignore[unreachable]

    # Required top-level keys
    required_keys = {'version', 'generated_at', 'plugin_version', 'config', 'albums', 'ideas', 'skills', 'session'}
    missing = required_keys - set(state.keys())
    if missing:
        errors.append(f"Missing top-level keys: {', '.join(missing)}")

    # Version check
    version = state.get('version', '')
    if not version:
        errors.append("Missing version field")
    elif not isinstance(version, str):
        errors.append(f"Version should be string, got {type(version).__name__}")

    # Plugin version check (string or null)
    if 'plugin_version' in state:
        pv = state['plugin_version']
        if pv is not None and not isinstance(pv, str):
            errors.append(f"plugin_version should be string or null, got {type(pv).__name__}")

    # Last-migrated version check (string or null; optional for legacy states)
    if 'last_migrated_version' in state:
        lmv = state['last_migrated_version']
        if lmv is not None and not isinstance(lmv, str):
            errors.append(
                f"last_migrated_version should be string or null, got {type(lmv).__name__}"
            )

    # Config section
    config = state.get('config', {})
    if isinstance(config, dict):
        for key in ('content_root', 'audio_root', 'overrides_dir', 'artist_name', 'config_mtime'):
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

    # Album collisions section (added in 1.3.0; absent on older states is
    # fine — the migration adds it)
    if 'album_collisions' in state:
        album_collisions = state['album_collisions']
        if isinstance(album_collisions, list):
            for i, entry in enumerate(album_collisions):
                if not isinstance(entry, dict):
                    errors.append(f"album_collisions[{i}] should be a dict")
                    continue
                for key in ('slug', 'kept', 'shadowed'):
                    if key not in entry:
                        errors.append(f"album_collisions[{i}] missing '{key}'")
        else:
            errors.append("album_collisions should be a list")

    # Ideas section
    ideas = state.get('ideas', {})
    if isinstance(ideas, dict):
        if 'counts' not in ideas:
            errors.append("Missing ideas.counts")
        if 'items' not in ideas:
            errors.append("Missing ideas.items")
    else:
        errors.append("ideas should be a dict")

    # Skills section
    skills = state.get('skills', {})
    if isinstance(skills, dict):
        if 'count' not in skills:
            errors.append("Missing skills.count")
        if 'items' not in skills:
            errors.append("Missing skills.items")
        elif isinstance(skills.get('items'), dict):
            for skill_name, skill in skills['items'].items():
                if not isinstance(skill, dict):
                    errors.append(f"Skill '{skill_name}' should be a dict")
                    continue
                for key in ('name', 'description', 'model_tier'):
                    if key not in skill:
                        errors.append(f"Skill '{skill_name}' missing '{key}'")
    else:
        errors.append("skills should be a dict")

    # Session section
    session = state.get('session', {})
    if not isinstance(session, dict):
        errors.append("session should be a dict")

    return errors


# ==========================================================================
# CLI Commands
# ==========================================================================

def cmd_rebuild(args: argparse.Namespace) -> int:
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
    # Carry migration tracking so a rebuild never silently acknowledges
    # pending migrations (issue #320).
    carry_migration_tracking(state, existing)

    write_state(state)

    album_count = len(state['albums'])
    track_count = sum(
        len(a.get('tracks', {})) for a in state['albums'].values()
    )
    ideas_count = len(state.get('ideas', {}).get('items', []))
    skills_count = state.get('skills', {}).get('count', 0)

    plugin_version = state.get('plugin_version', '?')
    logger.info("State cache rebuilt")
    print(f"  Plugin: {plugin_version or '?'}")
    print(f"  Albums: {album_count}")
    print(f"  Tracks: {track_count}")
    print(f"  Ideas: {ideas_count}")
    print(f"  Skills: {skills_count}")
    collisions = state.get('album_collisions', [])
    if collisions:
        print(f"  Collisions: {len(collisions)}")
        logger.warning(
            "%d album slug collision(s) detected — run 'show' for details; "
            "rename with /bitwize-music:rename or move the directory",
            len(collisions),
        )
    print(f"  Saved to: {STATE_FILE}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
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
    if state is None:
        logger.info("State sections invalid, performing full rebuild...")
        return cmd_rebuild(args)
    write_state(state)

    collisions = state.get('album_collisions', [])
    if collisions:
        logger.warning(
            "%d album slug collision(s) detected — run 'show' for details; "
            "rename with /bitwize-music:rename or move the directory",
            len(collisions),
        )
    logger.info("State cache updated")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
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


def _validate_session_value(value: str, field: str, max_len: int = 256) -> str | None:
    """Validate a session context value. Returns error message or None."""
    if len(value) > max_len:
        return f"{field} too long ({len(value)} chars, max {max_len})"
    if '\x00' in value:
        return f"{field} contains null bytes"
    return None


def cmd_session(args: argparse.Namespace) -> int:
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

    session['updated_at'] = datetime.now(UTC).isoformat()
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


def cmd_cleanup(args: argparse.Namespace) -> int:
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


def cmd_show(args: argparse.Namespace) -> int:
    """Pretty-print current state summary."""
    state = read_state()
    if state is None:
        print("No state file found. Run: python3 tools/state/indexer.py rebuild")
        return 1

    print(f"{Colors.BOLD}State Cache Summary{Colors.NC}")
    print(f"  Schema: {state.get('version', '?')}")
    print(f"  Plugin: {state.get('plugin_version') or '?'}")
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

    # Album slug collisions (#392)
    collisions = state.get('album_collisions', [])
    if collisions:
        print(f"{Colors.BOLD}{Colors.YELLOW}Album slug collisions ({len(collisions)}):{Colors.NC}")
        for collision in collisions:
            kept = collision.get('kept', {})
            print(f"  {collision.get('slug', '?')}: keeping {kept.get('genre', '?')} ({kept.get('path', '?')})")
            for s in collision.get('shadowed', []):
                print(f"    shadowed: {s.get('genre', '?')} ({s.get('path', '?')})")
        print("  Fix: rename one album (/bitwize-music:rename) or move the directory, then rebuild.")
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

    # Skills
    skills = state.get('skills', {})
    skills_count = skills.get('count', 0)
    model_counts = skills.get('model_counts', {})
    print(f"{Colors.BOLD}Skills ({skills_count}):{Colors.NC}")
    if model_counts:
        tier_parts = [f"{tier}: {count}" for tier, count in sorted(model_counts.items())]
        print(f"  By model: {', '.join(tier_parts)}")
    if args.verbose and skills.get('items'):
        for name, skill in sorted(skills['items'].items()):
            tier = skill.get('model_tier', '?')
            invocable = '' if skill.get('user_invocable', True) else ' [internal]'
            print(f"    {name} ({tier}){invocable}")
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


def main() -> int:
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
