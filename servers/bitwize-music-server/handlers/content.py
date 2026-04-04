"""Content and override tools — loading reference files, overrides, and clipboard formatting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import (
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _find_track_or_error,
    _safe_json,
)


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
    state = _shared.cache.get_state()
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
    try:
        override_path.relative_to(safe_root)
    except ValueError:
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

    assert _shared.PLUGIN_ROOT is not None
    ref_path = (_shared.PLUGIN_ROOT / "reference" / ref_name).resolve()
    safe_root = (_shared.PLUGIN_ROOT / "reference").resolve()
    try:
        ref_path.relative_to(safe_root)
    except ValueError:
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
    valid_types = {"lyrics", "style", "exclude", "streaming", "streaming-lyrics", "all", "suno"}
    if content_type not in valid_types:
        return _safe_json({
            "error": f"Invalid content_type '{content_type}'. Options: {', '.join(sorted(valid_types))}",
        })

    # Resolve track file
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    tracks = album.get("tracks", {})
    matched_slug, track_data, error = _find_track_or_error(tracks, track_slug, album_slug)
    if error:
        return error
    assert track_data is not None

    track_path = track_data.get("path", "")
    if not track_path:
        return _safe_json({"found": False, "error": f"No path stored for track '{matched_slug}'"})

    try:
        text = Path(track_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track file: {e}"})

    def _get_section_content(heading_name: str) -> str | None:
        """Extract code block content from a section."""
        section_text = _extract_markdown_section(text, heading_name)
        if section_text is None:
            return None
        code = _extract_code_block(section_text)
        return code if code is not None else section_text

    content: str | None = None
    if content_type == "style":
        style = _get_section_content("Style Box")
        exclude = _get_section_content("Exclude Styles")
        if style and exclude:
            content = f"{style}, {exclude}"
        else:
            content = style
    elif content_type == "exclude":
        content = _get_section_content("Exclude Styles")
    elif content_type == "lyrics":
        content = _get_section_content("Lyrics Box")
    elif content_type in ("streaming", "streaming-lyrics"):
        content = _get_section_content("Streaming Lyrics")
    elif content_type == "all":
        style = _get_section_content("Style Box")
        exclude = _get_section_content("Exclude Styles")
        lyrics = _get_section_content("Lyrics Box")
        if style is None and lyrics is None:
            content = None
        else:
            parts = []
            if style:
                parts.append(style)
            if exclude:
                parts.append(f"Exclude: {exclude}")
            if lyrics:
                parts.append(lyrics)
            content = "\n\n---\n\n".join(parts)
    elif content_type == "suno":
        style = _get_section_content("Style Box")
        exclude = _get_section_content("Exclude Styles")
        lyrics = _get_section_content("Lyrics Box")
        title = track_data.get("title", matched_slug)
        if style is None and lyrics is None:
            content = None
        else:
            content = json.dumps({
                "title": title,
                "style": style or "",
                "exclude_styles": exclude or "",
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


def register(mcp: Any) -> None:
    """Register content tools with the MCP server."""
    mcp.tool()(load_override)
    mcp.tool()(get_reference)
    mcp.tool()(format_for_clipboard)
