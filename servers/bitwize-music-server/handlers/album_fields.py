"""Album README upkeep — one field at a time, and the Tracklist table.

    update_album_field     release date, explicit flag, track count, concept, anchor track
    sync_album_tracklist   rebuild the README's Tracklist table from the track files
    after_track_status_change
                           called by update_track_field: keeps the track's README row and
                           the album status in step with the track

Every edit works on lines, never on re-dumped YAML, so the comments and the
hand-written parts of an album README survive.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._atomic import atomic_write_text
from handlers._shared import _find_album_or_error, _safe_json
from handlers.generation import _frontmatter_bounds, _split_row
from tools.state.indexer import write_state
from tools.state.parsers import _extract_table_value, parse_album_readme

logger = logging.getLogger(__name__)

_ALBUM_IN_PROGRESS = "In Progress"
_ALBUM_COMPLETE = "Complete"
_TRACK_FINAL = "Final"
_EMPTY_CELL = "—"

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TRACK_NUMBER_RE = re.compile(r"(\d+)")
_TRACKLIST_HEADING_RE = re.compile(r"^#{1,3}\s+Tracklist\s*$")
_DETAILS_HEADING_RE = re.compile(r"(?m)^#{1,3}\s+Album Details\s*$")
_TRUE = frozenset({"yes", "true", "y", "1"})
_FALSE = frozenset({"no", "false", "n", "0"})

# field name -> (canonical name, kind)
_FIELDS = {
    "release-date": ("release_date", "release_date"),
    "release_date": ("release_date", "release_date"),
    "explicit": ("explicit", "explicit"),
    "tracks": ("tracks", "tracks"),
    "concept": ("concept", "concept"),
    "anchor-track": ("anchor_track", "anchor_track"),
    "anchor_track": ("anchor_track", "anchor_track"),
}


# =============================================================================
# Line-level edits
# =============================================================================


def _set_frontmatter_scalar(text: str, key: str, rendered: str) -> str | None:
    """*text* with frontmatter ``key`` set to *rendered*, or None without frontmatter.

    Keeps the line's trailing comment. A commented-out template line
    (``# key: ...``) is taken over; a key that is absent is added before the
    closing ``---``.
    """
    lines = text.split("\n")
    end = _frontmatter_bounds(lines)
    if end is None:
        return None
    live = re.compile(rf"^{re.escape(key)}:\s*(.*?)(\s+#.*)?$")
    template = re.compile(rf"^#\s*{re.escape(key)}:\s*(.*?)(\s+#.*)?$")
    for pattern in (live, template):
        for i in range(1, end):
            match = pattern.match(lines[i])
            if match:
                lines[i] = f"{key}: {rendered}{match.group(2) or ''}"
                return "\n".join(lines)
    return "\n".join([*lines[:end], f"{key}: {rendered}", *lines[end:]])


def _set_details_row(text: str, key: str, value: str) -> str | None:
    """*text* with the Album Details row ``| **key** | ... |`` set, or None if absent."""
    heading = _DETAILS_HEADING_RE.search(text)
    pattern = re.compile(
        r"^(\|\s*\*\*" + re.escape(key) + r"\*\*\s*\|)\s*.*?\s*\|[ \t]*$", re.MULTILINE,
    )
    match = pattern.search(text, heading.end() if heading else 0)
    if not match:
        return None
    return text[:match.start()] + f"{match.group(1)} {value} |" + text[match.end():]


def _cell(value: str) -> str:
    """Text made safe for a table cell: one line, pipes escaped."""
    return " ".join(value.split()).replace("\\|", "|").replace("|", "\\|")


# =============================================================================
# update_album_field
# =============================================================================


def _apply_field(text: str, kind: str, value: str) -> tuple[str | None, str]:
    """Apply one field edit. Returns ``(new_text, shown_value)`` or ``(None, error)``."""
    value = value.strip()
    if kind == "release_date":
        if value:
            if not _DATE_RE.fullmatch(value):
                return None, f"Release date '{value}' is not YYYY-MM-DD"
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                return None, f"Release date '{value}' is not a real date"
        updated = _set_frontmatter_scalar(text, "release_date", json.dumps(value))
        return (updated, value) if updated else (None, "README.md has no YAML frontmatter")

    if kind == "explicit":
        lowered = value.lower()
        if lowered not in _TRUE | _FALSE:
            return None, f"Explicit '{value}' is not Yes or No"
        flag = lowered in _TRUE
        updated = _set_frontmatter_scalar(text, "explicit", "true" if flag else "false")
        if updated is None:
            return None, "README.md has no YAML frontmatter"
        shown = "Yes" if flag else "No"
        return _set_details_row(updated, "Explicit", shown) or updated, shown

    if kind == "tracks":
        if not value.isdigit():
            return None, f"Tracks '{value}' is not a whole number"
        updated = _set_details_row(text, "Tracks", str(int(value)))
        return (updated, str(int(value))) if updated else (None, "No Tracks row in Album Details")

    if kind == "concept":
        if not value:
            return None, "The concept cannot be empty"
        shown = _cell(value)
        updated = _set_details_row(text, "Concept", shown)
        return (updated, shown) if updated else (None, "No Concept row in Album Details")

    # anchor_track
    if value.lower() in ("", "auto", "none", "null"):
        rendered = "null"
    elif value.isdigit() and int(value) >= 1:
        rendered = str(int(value))
    else:
        return None, f"Anchor track '{value}' is not a track number (1 or more) or 'auto'"
    updated = _set_frontmatter_scalar(text, "anchor_track", rendered)
    return (updated, rendered) if updated else (None, "README.md has no YAML frontmatter")


async def update_album_field(album_slug: str, field: str, value: str) -> str:
    """Update one field of an album's README.md and refresh the state cache.

    Edits the line in place, so comments and everything else in the README are
    kept. For the album's status use update_album_status, which checks the
    transition; for streaming links use update_streaming_url.

    Args:
        album_slug: Album slug (e.g., "my-album")
        field: Field to update. Options:
            "release-date" — frontmatter release_date, YYYY-MM-DD ("" clears it)
            "explicit" — Yes or No; sets the frontmatter flag and the Album Details row
            "tracks" — the Album Details Tracks count
            "concept" — the Album Details one-line concept
            "anchor-track" — frontmatter anchor_track for album mastering: a track
                number, or "auto" to let mastering choose
        value: New value for the field

    Returns:
        JSON with success, album_slug, field, value and path, or an error
    """
    entry = _FIELDS.get(field.lower().strip())
    if field.lower().strip() == "status":
        return _safe_json({
            "error": "Use update_album_status for the album's status — it checks the transition",
        })
    if not entry:
        options = sorted({name for name in _FIELDS if "_" not in name})
        return _safe_json({
            "error": f"Unknown field '{field}'. Valid options: {', '.join(options)}",
        })
    canonical, kind = entry

    album_slug, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None
    readme = Path(album.get("path") or "") / "README.md"
    if not album.get("path") or not readme.is_file():
        return _safe_json({"error": f"README.md not found for album '{album_slug}'"})
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read {readme}: {e}"})

    updated, shown = _apply_field(text, kind, value)
    if updated is None:
        return _safe_json({"error": shown})
    try:
        atomic_write_text(readme, updated)
    except OSError as e:
        return _safe_json({"error": f"Cannot write {readme}: {e}"})

    _refresh_album_entry(album_slug, album, readme)
    logger.info("Updated album %s field '%s' to '%s'", album_slug, canonical, shown)
    return _safe_json({
        "success": True,
        "album_slug": album_slug,
        "field": canonical,
        "value": shown,
        "path": str(readme),
    })


def _refresh_album_entry(album_slug: str, album: dict[str, Any], readme: Path) -> None:
    """Re-read the README into the album's cache entry. The file is already written."""
    try:
        parsed = parse_album_readme(readme)
        for key in ("explicit", "release_date", "track_count", "anchor_track"):
            if key in parsed:
                album[key] = parsed[key]
        album["readme_mtime"] = readme.stat().st_mtime
        write_state(_shared.cache.get_state())
    except Exception as e:
        logger.warning("README written but cache update failed for %s: %s", album_slug, e)


# =============================================================================
# Tracklist table
# =============================================================================


def _tracklist_table(lines: list[str]) -> tuple[int, int, int] | None:
    """``(header, first_row, end)`` line indexes of the Tracklist table, or None.

    ``end`` is one past the table's last line.
    """
    heading = next((i for i, line in enumerate(lines) if _TRACKLIST_HEADING_RE.match(line)), None)
    if heading is None:
        return None
    header = None
    for i in range(heading + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("|"):
            header = i
            break
        if stripped.startswith("#"):
            return None
    if header is None or header + 1 >= len(lines) or "-" not in lines[header + 1]:
        return None
    end = header + 2
    while end < len(lines) and lines[end].strip().startswith("|"):
        end += 1
    return header, header + 2, end


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _number_of(text: str) -> int | None:
    match = _TRACK_NUMBER_RE.match(text.strip())
    return int(match.group(1)) if match else None


def _sync_row_status(readme: Path, track_slug: str, status: str) -> bool:
    """Set the Status cell of one track's Tracklist row. True when the file changed."""
    number = _number_of(track_slug)
    if number is None or not status:
        return False
    try:
        lines = readme.read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeDecodeError):
        return False
    table = _tracklist_table(lines)
    if table is None:
        return False
    _, first, end = table
    for i in range(first, end):
        cells = _split_row(lines[i].strip())
        if len(cells) >= 3 and _number_of(cells[0]) == number:
            if cells[-1] == status:
                return False
            cells[-1] = status
            lines[i] = _row(cells)
            try:
                atomic_write_text(readme, "\n".join(lines))
            except OSError as e:
                logger.warning("Cannot update the Tracklist row in %s: %s", readme, e)
                return False
            return True
    return False


async def sync_album_tracklist(album_slug: str, dry_run: bool = False) -> str:
    """Rebuild an album README's Tracklist table from its track files.

    The table is written by hand and drifts: a renamed track, a new track, a
    status that moved on. This sets each row's number, title (as a link to the
    track file) and status from the track files, adds rows for tracks the table
    lacks, and drops rows whose track is gone. Every other column of an existing
    row (POV, Concept, Duration, ...) is kept as written. The Album Details
    Tracks count follows.

    update_track_field already keeps a track's Status cell current; use this
    tool to repair the rest, or before a release.

    Args:
        album_slug: Album slug
        dry_run: Report what would change without writing

    Returns:
        JSON with changed, dry_run, rows (the number of tracks), added and
        updated (track slugs), removed (the numbers of dropped rows) and
        tracks_row (the Tracks count now in Album Details, when that row
        exists), or an error
    """
    album_slug, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None
    readme = Path(album.get("path") or "") / "README.md"
    if not album.get("path") or not readme.is_file():
        return _safe_json({"error": f"README.md not found for album '{album_slug}'"})
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read {readme}: {e}"})

    lines = text.split("\n")
    table = _tracklist_table(lines)
    if table is None:
        return _safe_json({"error": "README.md has no Tracklist table to sync"})
    header, first, end = table
    columns = [name.strip().lower() for name in _split_row(lines[header].strip())]
    width = len(columns)
    if width < 3:
        return _safe_json({"error": "The Tracklist table needs #, Title and Status columns"})
    title_col = columns.index("title") if "title" in columns else 1

    existing: dict[int, list[str]] = {}
    old_rows: dict[int, str] = {}
    for i in range(first, end):
        cells = _split_row(lines[i].strip())
        number = _number_of(cells[0]) if cells else None
        if number is None:
            continue
        existing[number] = (cells + [_EMPTY_CELL] * width)[:width]
        old_rows[number] = _row(existing[number])
    padded = not existing or any(
        cells[0].strip().startswith("0") or len(cells[0].strip()) > 1 for cells in existing.values()
    )

    new_rows: list[str] = []
    added: list[str] = []
    updated: list[str] = []
    seen: set[int] = set()
    tracks = album.get("tracks") or {}
    for slug, track in sorted(tracks.items()):
        match = _TRACK_NUMBER_RE.match(slug)
        if not match:
            continue
        number = int(match.group(1))
        seen.add(number)
        cells = list(existing.get(number) or [_EMPTY_CELL] * width)
        if number not in existing and "pov" in columns:
            cells[columns.index("pov")] = _track_pov(track)
        cells[0] = match.group(1) if padded else str(number)
        cells[title_col] = f"[{_cell(str(track.get('title') or slug))}](tracks/{slug}.md)"
        cells[-1] = str(track.get("status") or _EMPTY_CELL)
        row = _row(cells)
        new_rows.append(row)
        if number not in existing:
            added.append(slug)
        elif row != old_rows[number]:
            updated.append(slug)
    removed = [
        _split_row(lines[i].strip())[0].strip()
        for i in range(first, end)
        if (number := _number_of(_split_row(lines[i].strip())[0])) is not None and number not in seen
    ]

    new_text = "\n".join([*lines[:first], *new_rows, *lines[end:]])
    tracks_row: int | None = None
    if _extract_table_value(new_text, "Tracks") is not None:
        with_count = _set_details_row(new_text, "Tracks", str(len(new_rows)))
        if with_count is not None:
            new_text, tracks_row = with_count, len(new_rows)

    changed = new_text != text
    if changed and not dry_run:
        try:
            atomic_write_text(readme, new_text)
        except OSError as e:
            return _safe_json({"error": f"Cannot write {readme}: {e}"})
        _refresh_album_entry(album_slug, album, readme)

    result: dict[str, Any] = {
        "changed": changed,
        "dry_run": dry_run,
        "album_slug": album_slug,
        "rows": len(new_rows),
        "added": added,
        "updated": updated,
        "removed": removed,
    }
    if tracks_row is not None:
        result["tracks_row"] = tracks_row
    return _safe_json(result)


def _track_pov(track: dict[str, Any]) -> str:
    """The POV a track file records, for a row the table did not have yet."""
    path = track.get("path") or ""
    if not path:
        return _EMPTY_CELL
    try:
        pov = _extract_table_value(Path(path).read_text(encoding="utf-8"), "POV")
    except (OSError, UnicodeDecodeError):
        return _EMPTY_CELL
    return _cell(pov) if pov and pov.strip() else _EMPTY_CELL


# =============================================================================
# Following a track's status
# =============================================================================


async def after_track_status_change(
    album_slug: str, track_slug: str, status: str,
) -> dict[str, Any]:
    """Keep the album in step after a track's status changed.

    Sets the track's Status cell in the README Tracklist, and advances the album
    from In Progress to Complete once every track is Final. Returns what it did:
    ``readme_tracklist: "updated"`` and/or ``album_status: {"from", "to"}``.
    """
    extras: dict[str, Any] = {}
    state = _shared.cache.get_state()
    album = state.get("albums", {}).get(album_slug)
    if not album:
        return extras

    readme = Path(album.get("path") or "") / "README.md"
    if album.get("path") and readme.is_file() and _sync_row_status(readme, track_slug, status):
        extras["readme_tracklist"] = "updated"
        try:
            album["readme_mtime"] = readme.stat().st_mtime
            write_state(state)
        except Exception as e:
            logger.warning("Tracklist row updated but cache update failed for %s: %s", album_slug, e)

    tracks = album.get("tracks") or {}
    if (
        album.get("status") == _ALBUM_IN_PROGRESS
        and tracks
        and all(track.get("status") == _TRACK_FINAL for track in tracks.values())
    ):
        from handlers.status import update_album_status  # lazy: status imports core

        result = json.loads(await update_album_status(album_slug, _ALBUM_COMPLETE))
        if result.get("success"):
            extras["album_status"] = {"from": _ALBUM_IN_PROGRESS, "to": _ALBUM_COMPLETE}
        else:
            logger.info(
                "Album %s not advanced to Complete: %s", album_slug, result.get("error"),
            )
    return extras


def register(mcp: Any) -> None:
    """Register the album upkeep tools with the MCP server."""
    mcp.tool()(update_album_field)
    mcp.tool()(sync_album_tracklist)
