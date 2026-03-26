"""Core query tools — albums, tracks, sessions, config, search, paths."""

import logging
import re
from pathlib import Path
from typing import Any

from tools.state.indexer import write_state
from tools.state.parsers import parse_track_file

from handlers._shared import (
    _normalize_slug, _safe_json, _extract_markdown_section, _extract_code_block,
    _SECTION_NAMES, _CODE_BLOCK_SECTIONS,
    _find_track_or_error,
    TRACK_NOT_STARTED,
    TRACK_IN_PROGRESS, TRACK_GENERATED, TRACK_FINAL,
    TRACK_COMPLETED_STATUSES, STATUS_UNKNOWN,
    ALBUM_CONCEPT,
    ALBUM_COMPLETE, ALBUM_RELEASED,
    _MARKDOWN_LINK_RE,
)
from handlers import _shared

logger = logging.getLogger("bitwize-music-state")


# =============================================================================
# Module-specific constants
# =============================================================================

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


# =============================================================================
# Helper functions
# =============================================================================

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


# =============================================================================
# Tool functions
# =============================================================================

async def find_album(name: str) -> str:
    """Find an album by name with fuzzy matching.

    Auto-rebuilds state cache if empty or missing, so callers never need
    fallback glob logic.

    Args:
        name: Album name, slug, or partial match (e.g., "my-album", "my album", "My Album")

    Returns:
        JSON with found album data, or error with available albums
    """
    state = _shared.cache.get_state()
    albums = state.get("albums", {})

    # Auto-rebuild if state is empty or missing albums
    if not albums:
        logger.info("find_album: no albums in cache, attempting auto-rebuild")
        rebuilt = _shared.cache.rebuild()
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


async def list_albums(status_filter: str = "") -> str:
    """List all albums with summary info.

    Args:
        status_filter: Optional status to filter by (e.g., "In Progress", "Complete", "Released")

    Returns:
        JSON array of album summaries
    """
    state = _shared.cache.get_state()
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


async def get_track(album_slug: str, track_slug: str) -> str:
    """Get details for a specific track.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug (e.g., "01-track-name")

    Returns:
        JSON with track data or error
    """
    state = _shared.cache.get_state()
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


async def list_tracks(album_slug: str) -> str:
    """List all tracks for an album in one call (avoids N+1 queries).

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with all tracks for the album, or error if album not found
    """
    state = _shared.cache.get_state()
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


async def get_session() -> str:
    """Get current session context.

    Returns:
        JSON with session data (last_album, last_track, last_phase, pending_actions)
    """
    state = _shared.cache.get_state()
    session = state.get("session", {})
    return _safe_json({"session": session})


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
    session = _shared.cache.update_session(
        album=album or None,
        track=track or None,
        phase=phase or None,
        action=action or None,
        clear=clear,
    )
    return _safe_json({"session": session})


async def rebuild_state() -> str:
    """Force full rebuild of state cache from markdown files.

    Use when state seems stale or after manual file edits.

    Returns:
        JSON with rebuild result summary
    """
    state = _shared.cache.rebuild()

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


async def get_config() -> str:
    """Get resolved configuration (paths, artist name, settings).

    Returns:
        JSON with config section from state
    """
    state = _shared.cache.get_state()
    config = state.get("config", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    return _safe_json({"config": config})


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
        "plugin_root": str(_shared.PLUGIN_ROOT),
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


async def get_ideas(status_filter: str = "") -> str:
    """Get album ideas with status counts.

    Args:
        status_filter: Optional status to filter by (e.g., "Pending", "In Progress")

    Returns:
        JSON with ideas counts and items
    """
    state = _shared.cache.get_state()
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


async def search(query: str, scope: str = "all") -> str:
    """Full-text search across albums, tracks, ideas, and skills.

    Args:
        query: Search query (case-insensitive substring match)
        scope: What to search - "albums", "tracks", "ideas", "skills", or "all" (default)

    Returns:
        JSON with matching results grouped by type
    """
    state = _shared.cache.get_state()
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


async def get_pending_verifications() -> str:
    """Get albums and tracks with pending source verification.

    Returns:
        JSON with tracks where sources_verified is 'Pending', grouped by album
    """
    state = _shared.cache.get_state()
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

    state = _shared.cache.get_state()
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


async def resolve_track_file(album_slug: str, track_slug: str) -> str:
    """Find a track's file path and return its full metadata from state cache.

    More complete than get_track — includes the resolved file path and album context.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")

    Returns:
        JSON with track path, metadata, and album context
    """
    state = _shared.cache.get_state()
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


async def list_track_files(album_slug: str, status_filter: str = "") -> str:
    """List all tracks for an album with file paths and optional status filtering.

    Unlike list_tracks, includes file paths and supports filtering by status.

    Args:
        album_slug: Album slug (e.g., "my-album")
        status_filter: Optional status filter (e.g., "Not Started", "In Progress", "Generated", "Final")

    Returns:
        JSON with track list including paths, or error if album not found
    """
    state = _shared.cache.get_state()
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
    state = _shared.cache.get_state()
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
    matched_slug, track_data, error = _find_track_or_error(tracks, track_slug, album_slug)
    if error:
        return error

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
    code_content = None
    if heading in _CODE_BLOCK_SECTIONS:
        code_content = _extract_code_block(content)

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "track_slug": matched_slug,
        "section": heading,
        "content": code_content if code_content is not None else content,
        "raw_content": content if code_content is not None else None,
    })


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
    # Lazy imports to avoid circular dependencies
    from handlers.text_analysis import _load_artist_blocklist
    from handlers.gates import _check_pre_gen_gates_for_track
    from handlers.status import (
        _VALID_TRACK_STATUSES, _CANONICAL_TRACK_STATUS, _validate_track_transition,
    )

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
    state = _shared.cache.get_state()
    albums = state.get("albums", {})
    normalized_album = _normalize_slug(album_slug)
    album = albums.get(normalized_album)

    if not album:
        return _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
        })

    tracks = album.get("tracks", {})
    matched_slug, track_data, error = _find_track_or_error(tracks, track_slug, album_slug)
    if error:
        return error

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
            state_config = state.get("config", {})
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
            state_config = state.get("config", {})
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
    state = _shared.cache.get_state()
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
# Registration
# =============================================================================

def register(mcp):
    """Register core query tools with the MCP server."""
    mcp.tool()(find_album)
    mcp.tool()(list_albums)
    mcp.tool()(get_track)
    mcp.tool()(list_tracks)
    mcp.tool()(get_session)
    mcp.tool()(update_session)
    mcp.tool()(rebuild_state)
    mcp.tool()(get_config)
    mcp.tool()(get_python_command)
    mcp.tool()(get_ideas)
    mcp.tool()(search)
    mcp.tool()(get_pending_verifications)
    mcp.tool()(resolve_path)
    mcp.tool()(resolve_track_file)
    mcp.tool()(list_track_files)
    mcp.tool()(extract_section)
    mcp.tool()(update_track_field)
    mcp.tool()(get_album_progress)
