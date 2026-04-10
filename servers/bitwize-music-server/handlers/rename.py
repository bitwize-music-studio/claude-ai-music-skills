"""Rename tools — album and track renaming with mirrored path updates."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._atomic import atomic_write_text
from handlers._shared import (
    _derive_title_from_slug,
    _find_album_or_error,
    _find_track_or_error,
    _normalize_slug,
    _safe_json,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


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
    from tools.state.indexer import write_state

    normalized_old = _normalize_slug(old_slug)
    normalized_new = _normalize_slug(new_slug)

    if normalized_old == normalized_new:
        return _safe_json({"error": "Old and new slugs are the same after normalization."})

    # Get state and validate old album exists
    state = _shared.cache.get_state()
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
        for _track_slug, track_data in album_data.get("tracks", {}).items():
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
    from tools.state.indexer import write_state
    from tools.state.parsers import parse_track_file

    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    tracks = album.get("tracks", {})
    normalized_new = _normalize_slug(new_track_slug)

    matched_slug, track_data, error = _find_track_or_error(tracks, old_track_slug, album_slug)
    if error:
        return error
    assert track_data is not None

    if _normalize_slug(old_track_slug) == normalized_new:
        return _safe_json({"error": "Old and new track slugs are the same after normalization."})

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
            atomic_write_text(new_path, updated_text)
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
        except (ValueError, OSError, KeyError) as exc:
            logger.warning("Could not re-parse track after rename %s: %s", new_path, exc)
        tracks[normalized_new] = old_track_data
        state = _shared.cache.get_state_ref()  # same object that album/tracks reference into
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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp: Any) -> None:
    """Register rename tools with the MCP server."""
    mcp.tool()(rename_album)
    mcp.tool()(rename_track)
