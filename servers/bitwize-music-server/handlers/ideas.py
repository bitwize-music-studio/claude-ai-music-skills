"""Idea management tools — create, update, and promote album ideas."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
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


def _derive_slug_from_title(title: str) -> str:
    """Derive an album slug from an idea title.

    Strips diacritics (NFKD + ASCII-only), elides apostrophes so contractions
    stay intact (``Who's`` → ``whos``, not ``who-s``), lowercases, and reduces
    any run of non-alphanumeric characters to a single hyphen. Trailing
    hyphens are trimmed. Empty result means the title had no usable characters.
    """
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    # Elide apostrophes (straight + curly already stripped via ASCII encode)
    # before the general non-alphanumeric → hyphen pass, so "Who's" → "whos".
    ascii_only = ascii_only.replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def _find_idea_in_state(title: str) -> dict[str, Any] | None:
    """Find an idea by title (case-insensitive exact match) in the state cache."""
    state = _shared.cache.get_state()
    items = state.get("ideas", {}).get("items", [])
    needle = title.strip().lower()
    for item in items:
        if isinstance(item, dict) and item.get("title", "").strip().lower() == needle:
            return item
    return None


def _inject_concept_into_readme(
    readme_path: Path, idea_title: str, concept: str
) -> bool:
    """Insert a Concept block into the album README after the first H1 heading.

    Returns True on success, False if the file is unreadable or has no H1.
    """
    if not readme_path.exists():
        return False
    try:
        text = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    block = (
        f"\n\n## Concept\n\n"
        f"_Promoted from idea **{idea_title}**:_\n\n"
        f"> {concept}\n"
    )

    # Insert after the first H1 heading (skipping YAML frontmatter).
    h1 = re.search(r'^(# .+?)$', text, re.MULTILINE)
    if h1:
        insert_pos = h1.end()
        new_text = text[:insert_pos] + block + text[insert_pos:]
    else:
        new_text = text.rstrip() + block

    try:
        readme_path.write_text(new_text, encoding="utf-8")
    except OSError:
        return False
    return True


def _set_promoted_to_field(title: str, slug: str) -> bool:
    """Add or update ``**Promoted To**: <slug>`` in the idea's IDEAS.md section."""
    ideas_path = _resolve_ideas_path()
    if not ideas_path or not ideas_path.exists():
        return False
    try:
        text = ideas_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    title_pattern = re.compile(
        r'^###\s+' + re.escape(title.strip()) + r'\s*$', re.MULTILINE
    )
    title_match = title_pattern.search(text)
    if not title_match:
        return False

    section_start = title_match.end()
    next_section = re.search(r'^###\s+', text[section_start:], re.MULTILINE)
    section_end = (
        section_start + next_section.start() if next_section else len(text)
    )
    section_text = text[section_start:section_end]

    promoted_re = re.compile(
        r'^\*\*Promoted To\*\*\s*:\s*.+$', re.MULTILINE
    )
    if promoted_re.search(section_text):
        new_section = promoted_re.sub(f"**Promoted To**: {slug}", section_text)
    else:
        # Insert right after the Status line; fall back to end of section.
        status_re = re.compile(r'^(\*\*Status\*\*\s*:\s*.+)$', re.MULTILINE)
        status_match = status_re.search(section_text)
        if status_match:
            insert_pos = status_match.end()
            new_section = (
                section_text[:insert_pos]
                + f"\n**Promoted To**: {slug}"
                + section_text[insert_pos:]
            )
        else:
            new_section = section_text.rstrip() + f"\n**Promoted To**: {slug}\n"

    new_text = text[:section_start] + new_section + text[section_end:]
    try:
        ideas_path.write_text(new_text, encoding="utf-8")
    except OSError:
        return False
    return True


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


async def promote_idea(
    idea_title: str,
    album_slug: str = "",
    documentary: bool = False,
) -> str:
    """Promote an album idea into an actual album project.

    Looks up the idea by title, auto-derives a slug from the title (unless one
    is supplied), creates the album directory structure via
    ``create_album_structure``, injects the idea's concept text into the new
    album README, and advances the idea's status from ``Pending`` to
    ``In Progress`` with a ``Promoted To`` back-link.

    Args:
        idea_title: Exact idea title as stored in IDEAS.md.
        album_slug: Optional override slug; auto-derived from the title if empty.
        documentary: If True, also creates RESEARCH.md and SOURCES.md.

    Returns:
        JSON with ``{promoted: True, slug, genre, album_path, files, ...}`` on
        success, or ``{error: ...}`` on failure.
    """
    # Lazy import to avoid any circular-import risk at module load time.
    from handlers.album_ops import create_album_structure

    idea = _find_idea_in_state(idea_title)
    if idea is None:
        return _safe_json({
            "error": f"Idea '{idea_title}' not found in IDEAS.md",
            "hint": "Use get_ideas to list available ideas.",
        })

    status = idea.get("status", "Pending").strip()
    if status.lower() != "pending":
        return _safe_json({
            "error": (
                f"Idea '{idea_title}' is already promoted "
                f"(current status: {status})"
            ),
            "current_status": status,
            "promoted_to": idea.get("promoted_to", ""),
        })

    genre = idea.get("genre", "").strip()
    if not genre:
        return _safe_json({
            "error": (
                f"Idea '{idea_title}' has no genre set. "
                f"Set the **Genre** field in IDEAS.md before promoting."
            ),
        })

    slug = album_slug.strip() if album_slug.strip() else _derive_slug_from_title(idea_title)
    if not slug:
        return _safe_json({
            "error": (
                f"Cannot derive album slug from title '{idea_title}'. "
                f"Supply an explicit album_slug."
            ),
        })

    # Use the canonical idea title from the state cache for all downstream
    # IDEAS.md mutations. The cache lookup is case-insensitive (users can pass
    # "kleine welt"), but update_idea and _set_promoted_to_field match the
    # markdown file case-sensitively — if we passed the caller's casing through
    # untouched, a lowercase call against a title-case idea would promote the
    # album on disk but leave IDEAS.md untouched, producing a silent
    # half-promotion (#328 review I2).
    canonical_title = (idea.get("title") or idea_title).strip() or idea_title.strip()

    # Create album — surface errors verbatim. create_album_structure's
    # `_normalize_slug` raises ValueError on path-traversal inputs (`..`, `/`,
    # `\`, NULs) when the caller supplied an explicit `album_slug`; catch it
    # and return a structured error to honor this function's "no raised
    # exceptions for documented failure modes" contract (#328 review I1).
    try:
        album_result_json = await create_album_structure(slug, genre, documentary)
    except ValueError as exc:
        return _safe_json({
            "error": f"Invalid album_slug '{slug}': {exc}",
            "idea_title": canonical_title,
            "slug": slug,
            "genre": genre,
        })
    album_result = json.loads(album_result_json)
    if not album_result.get("created"):
        error_msg = album_result.get("error", "Failed to create album structure")
        return _safe_json({
            "error": error_msg,
            "idea_title": canonical_title,
            "slug": slug,
            "genre": genre,
        })

    album_path = Path(album_result["path"])

    concept = idea.get("concept", "").strip()
    concept_injected = False
    if concept:
        concept_injected = _inject_concept_into_readme(
            album_path / "README.md", canonical_title, concept
        )

    # Update idea: status → In Progress, Promoted To → slug. Failures here are
    # non-fatal (album already created); log but don't roll back. Use
    # canonical_title so the IDEAS.md regex match succeeds regardless of the
    # caller's casing (#328 review I2).
    status_result = json.loads(
        await update_idea(canonical_title, "status", "In Progress")
    )
    if status_result.get("error"):
        logger.warning(
            "Album created but status update failed for '%s': %s",
            canonical_title, status_result.get("error"),
        )
    if not _set_promoted_to_field(canonical_title, slug):
        # Non-fatal, but operators need to see this — the album is created
        # and status is flipped, but the IDEAS.md back-link is missing so
        # the two sides will drift apart (#328 review I3).
        logger.warning(
            "Album '%s' created but Promoted To back-link in IDEAS.md could "
            "not be written for idea '%s'",
            slug, canonical_title,
        )

    try:
        _shared.cache.rebuild()
    except Exception as e:
        logger.warning("promote_idea: cache rebuild failed: %s", e)

    return _safe_json({
        "promoted": True,
        "idea_title": canonical_title,
        "slug": slug,
        "genre": genre,
        "documentary": documentary,
        "album_path": str(album_path),
        "tracks_path": album_result.get("tracks_path", ""),
        "files": album_result.get("files", []),
        "concept_injected": concept_injected,
    })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp: Any) -> None:
    """Register idea management tools with the MCP server."""
    mcp.tool()(create_idea)
    mcp.tool()(update_idea)
    mcp.tool()(promote_idea)
