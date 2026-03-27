"""Idea management tools — create and update album ideas."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import _safe_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_ideas_path() -> Path | None:
    """Resolve the path to IDEAS.md using config."""
    state = _shared.cache.get_state()
    config = state.get("config", {})
    content_root = config.get("content_root", "")
    if not content_root:
        return None
    return Path(content_root) / "IDEAS.md"


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


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
        _shared.cache.rebuild()
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
        _shared.cache.rebuild()
    except Exception as e:
        logger.warning("Idea updated but cache rebuild failed: %s", e)

    return _safe_json({
        "success": True,
        "title": title.strip(),
        "field": label,
        "old_value": old_value,
        "new_value": value,
    })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp: Any) -> None:
    """Register idea management tools with the MCP server."""
    mcp.tool()(create_idea)
    mcp.tool()(update_idea)
