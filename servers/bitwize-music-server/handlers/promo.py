"""Promo directory tools — promo status and content retrieval."""

import logging
from pathlib import Path

from handlers._shared import _find_album_or_error, _safe_json
from handlers.status import _PROMO_FILES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp):
    """Register promo tools with the MCP server."""
    mcp.tool()(get_promo_status)
    mcp.tool()(get_promo_content)
