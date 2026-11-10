"""Suno generation bridge — track file to API request, take logging, import planning.

Nothing in this module talks to Suno. A skill asks these tools what to send,
calls the Suno MCP server itself, then hands the resulting clip ids back for
logging. That keeps the Suno side swappable and this side testable offline.
See reference/suno/mcp-api-mapping.md for the mapping these tools implement.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._atomic import atomic_write_text
from handlers._shared import (
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _find_track_or_error,
    _safe_json,
)
from handlers.gates import _KNOWN_MODELS, _parse_duration_seconds
from tools.state.indexer import write_state
from tools.state.parsers import _extract_table_value, parse_frontmatter

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Limits from the Suno MCP `audio-create` schema.
_MAX_TITLE = 256
_MAX_LYRICS = 5000
_MAX_STYLE = 1000
_MAX_NEGATIVE_STYLE = 1000
_MIN_DURATION = 15
_MAX_DURATION = 360

# Request keys Suno only accepts on accounts with the `controls.advanced` feature.
_NEEDS_ADVANCED_CONTROLS = ("controls", "negative_style", "vocal_gender")

# Table cells and code blocks that mean "nothing set".
_UNSET = frozenset({"", "—", "\u2013", "-", "n/a", "none", "(none)", "auto"})

# Untouched placeholders from templates/track.md — never worth sending to Suno.
_TEMPLATE_STYLE = (
    "[genre], [tempo/BPM], [mood], [vocal description], [instruments], [production notes]"
)
_TEMPLATE_EXCLUDE = "[exclusions, if any]"
_TEMPLATE_LYRICS_MARKER = "[Lyrics here...]"

_SLIDER_RE = re.compile(r"(\d{1,3})\s*%?")

# Generation Log (templates/track.md § Generation Log)
_CLIP_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_GENERATION_LOG_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+Generation Log[ \t]*$")
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+\S")
_ROW_NUMBER_RE = re.compile(r"\|\s*(\d+)\s*\|")
_PLACEHOLDER_ROW_RE = re.compile(r"\|(?:\s*[—\u2013-]\s*\|){2,}")
_LOG_TABLE_HEADER = "| # | Date | Model | Result | Notes | Rating |"
_LOG_TABLE_SEPARATOR = "|---|------|-------|--------|-------|--------|"


# =============================================================================
# Helpers
# =============================================================================


def _load_track(
    album_slug: str, track_slug: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a track through the state cache and read its file.

    Returns ``(context, None)`` or ``(None, error_json)``. The context carries
    ``album_slug``, ``album``, ``track_slug``, ``track`` (the cache entry, by
    reference), ``path`` and ``text``.
    """
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return None, error
    assert album is not None

    matched_slug, track, error = _find_track_or_error(
        album.get("tracks", {}), track_slug, album_slug,
    )
    if error:
        return None, error
    assert track is not None

    track_path = track.get("path", "")
    if not track_path:
        return None, _safe_json({
            "found": False,
            "error": f"No path stored for track '{matched_slug}'",
        })

    path = Path(track_path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, _safe_json({"found": False, "error": f"Cannot read track file: {e}"})

    return {
        "album_slug": normalized_album,
        "album": album,
        "track_slug": matched_slug,
        "track": track,
        "path": path,
        "text": text,
    }, None


def _section_code(text: str, heading: str) -> str | None:
    """The first code block under *heading*, stripped; None when absent or empty."""
    section = _extract_markdown_section(text, heading)
    if section is None:
        return None
    code = _extract_code_block(section)
    if code is None or not code.strip():
        return None
    return code.strip()


def _problem(code: str, severity: str, detail: str) -> dict[str, str]:
    """A problem entry. *severity* is ``blocking`` or ``warning``."""
    return {"code": code, "severity": severity, "detail": detail}


def _instrumental_state(text: str) -> tuple[bool, dict[str, str] | None]:
    """Whether the track is instrumental, plus a problem if its two flags disagree.

    Frontmatter ``instrumental:`` and the Track Details ``Instrumental`` row are
    meant to match (the pre-generation check enforces it). Either one alone is
    accepted, so older track files without frontmatter still resolve.
    """
    frontmatter = parse_frontmatter(text)
    fm_value: bool | None = None
    if "_error" not in frontmatter and isinstance(frontmatter.get("instrumental"), bool):
        fm_value = frontmatter["instrumental"]

    table_raw = (_extract_table_value(text, "Instrumental") or "").strip().lower()
    table_value: bool | None = None
    if table_raw in ("yes", "true"):
        table_value = True
    elif table_raw in ("no", "false"):
        table_value = False

    if fm_value is not None and table_value is not None and fm_value != table_value:
        return False, _problem(
            "instrumental_mismatch", "blocking",
            f"Frontmatter says instrumental: {str(fm_value).lower()} but Track Details "
            f"says {'Yes' if table_value else 'No'} — make them match",
        )
    if fm_value is not None:
        return fm_value, None
    return bool(table_value), None


def _slider(
    settings: str, key: str, problems: list[dict[str, str]],
) -> float | None:
    """A 0-100 Generation Settings slider as the API's 0-1 fraction, or None if unset."""
    raw = (_extract_table_value(settings, key) or "").strip()
    if raw.lower() in _UNSET:
        return None
    slug = key.lower().replace(" ", "_")
    match = _SLIDER_RE.fullmatch(raw)
    if not match:
        problems.append(_problem(
            f"{slug}_unrecognized", "warning",
            f"{key} '{raw}' is not a number from 0 to 100 — left at Suno's default",
        ))
        return None
    value = int(match.group(1))
    if value > 100:
        problems.append(_problem(
            f"{slug}_clamped", "warning", f"{key} {value} is above 100 — sent as 100",
        ))
        value = 100
    return round(value / 100, 2)


# =============================================================================
# get_generation_request
# =============================================================================


async def get_generation_request(album_slug: str, track_slug: str) -> str:
    """Build the Suno MCP `audio-create` arguments for a track, from its track file.

    Read-only, and it never calls Suno: the calling skill sends ``request`` to the
    Suno MCP server itself. Maps the track's Suno Inputs — Style Box, Exclude
    Styles, Generation Settings and Lyrics Box — to the API's parameters.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")

    Returns:
        JSON with:
            supported: False when a blocking problem means nothing should be sent
            request: arguments for audio-create (title, style, lyrics, negative_style,
                model, instrumental, max_mode, vocal_gender, duration, controls)
            needs_grant: request keys that need the account's `controls.advanced`
                feature — drop them when account-usage does not list it
            ignored: Generation Settings with no API equivalent (Variety above Off)
            problems: [{code, severity: blocking|warning, detail}]
            track_status: the track's current status
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]
    track: dict[str, Any] = ctx["track"]

    problems: list[dict[str, str]] = []
    ignored: list[dict[str, str]] = []
    request: dict[str, Any] = {}

    title = str(track.get("title") or ctx["track_slug"]).strip()
    request["title"] = title
    if len(title) > _MAX_TITLE:
        problems.append(_problem(
            "title_too_long", "blocking",
            f"Title is {len(title)} characters; Suno accepts {_MAX_TITLE}",
        ))

    instrumental, mismatch = _instrumental_state(text)
    if mismatch:
        problems.append(mismatch)
    if instrumental:
        request["instrumental"] = True

    style = _section_code(text, "Style Box")
    if style is None:
        problems.append(_problem(
            "style_missing", "blocking",
            "Style Box is empty — run /bitwize-music:suno-engineer",
        ))
    elif style == _TEMPLATE_STYLE:
        problems.append(_problem(
            "style_placeholder", "blocking",
            "Style Box still holds the template placeholder — run /bitwize-music:suno-engineer",
        ))
    else:
        request["style"] = style
        if len(style) > _MAX_STYLE:
            problems.append(_problem(
                "style_too_long", "blocking",
                f"Style Box is {len(style)} characters; Suno accepts {_MAX_STYLE}",
            ))

    lyrics = _section_code(text, "Lyrics Box")
    if lyrics is not None and _TEMPLATE_LYRICS_MARKER in lyrics:
        problems.append(_problem(
            "lyrics_placeholder", "blocking",
            "Lyrics Box still holds the template placeholder",
        ))
    elif lyrics is None:
        # An instrumental may omit lyrics; its section tags are optional structure.
        if not instrumental:
            problems.append(_problem(
                "lyrics_missing", "blocking",
                "Lyrics Box is empty — run /bitwize-music:lyric-writer",
            ))
    else:
        request["lyrics"] = lyrics
        if len(lyrics) > _MAX_LYRICS:
            problems.append(_problem(
                "lyrics_too_long", "blocking",
                f"Lyrics Box is {len(lyrics)} characters; Suno accepts {_MAX_LYRICS}",
            ))

    exclude = _section_code(text, "Exclude Styles")
    if exclude is not None and exclude.lower() not in _UNSET and exclude != _TEMPLATE_EXCLUDE:
        request["negative_style"] = exclude
        if len(exclude) > _MAX_NEGATIVE_STYLE:
            problems.append(_problem(
                "negative_style_too_long", "blocking",
                f"Exclude Styles is {len(exclude)} characters; Suno accepts {_MAX_NEGATIVE_STYLE}",
            ))

    settings = _extract_markdown_section(text, "Generation Settings")
    if settings is None:
        problems.append(_problem(
            "generation_settings_missing", "warning",
            "No Generation Settings section — Suno's defaults are used for model, sliders "
            "and duration (add one from templates/track.md § Generation Settings)",
        ))
    else:
        model_raw = (_extract_table_value(settings, "Model") or "").strip()
        model = model_raw.lower()
        if model in _KNOWN_MODELS:
            request["model"] = model
        elif model.startswith("custom:"):
            problems.append(_problem(
                "custom_model_unsupported", "blocking",
                f"Model '{model_raw}' is a Custom Model, which the Suno MCP does not offer — "
                "generate this track on suno.com (use /bitwize-music:clipboard)",
            ))
        elif model in _UNSET:
            problems.append(_problem(
                "model_unset", "warning", "No model set — Suno's default model is used",
            ))
        else:
            problems.append(_problem(
                "model_unrecognized", "blocking",
                f"Model '{model_raw}' not recognized — use v6, v6-wild or v6-mini",
            ))

        if (_extract_table_value(settings, "Max Mode") or "").strip().lower() == "on":
            request["max_mode"] = True

        variety = (_extract_table_value(settings, "Variety") or "").strip()
        if variety.lower() not in _UNSET and variety.lower() not in ("off", "0"):
            ignored.append({
                "setting": "Variety",
                "value": variety,
                "reason": "no API equivalent — through the MCP Suno uses the Style Box as written",
            })

        gender = (_extract_table_value(settings, "Vocal Gender") or "").strip().lower()
        if gender in ("male", "female"):
            if not instrumental:
                request["vocal_gender"] = gender
        elif gender not in _UNSET:
            problems.append(_problem(
                "vocal_gender_unrecognized", "warning",
                f"Vocal Gender '{gender}' is not Male or Female — left to Suno",
            ))

        duration_raw = (_extract_table_value(settings, "Duration") or "").strip()
        seconds = _parse_duration_seconds(duration_raw)
        if seconds is not None:
            clamped = min(max(seconds, _MIN_DURATION), _MAX_DURATION)
            if clamped != seconds:
                problems.append(_problem(
                    "duration_clamped", "warning",
                    f"Duration {duration_raw} is outside Suno's {_MIN_DURATION} to {_MAX_DURATION} s "
                    f"range — sent as {clamped} s",
                ))
            request["duration"] = clamped
        elif duration_raw.lower() not in _UNSET:
            problems.append(_problem(
                "duration_unrecognized", "warning",
                f"Duration '{duration_raw}' is not Auto or m:ss — left to Suno",
            ))

        controls: dict[str, float] = {}
        weirdness = _slider(settings, "Weirdness", problems)
        if weirdness is not None:
            controls["weirdness"] = weirdness
        style_influence = _slider(settings, "Style Influence", problems)
        if style_influence is not None:
            controls["style_influence"] = style_influence
        if controls:
            request["controls"] = controls

    supported = not any(p["severity"] == "blocking" for p in problems)
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "track_status": track.get("status", ""),
        "supported": supported,
        "request": request,
        "needs_grant": [key for key in _NEEDS_ADVANCED_CONTROLS if key in request],
        "ignored": ignored,
        "problems": problems,
    })


# =============================================================================
# log_generation
# =============================================================================


def _today() -> str:
    """Today's date for a Generation Log row (a seam for tests)."""
    return datetime.date.today().isoformat()


def _cell(value: str) -> str:
    """Flatten a value so it cannot break out of a markdown table cell."""
    return re.sub(r"\s+", " ", value.replace("|", "/")).strip()


def _fmt_duration(seconds: float) -> str:
    """Seconds as m:ss."""
    total = round(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _generation_log_bounds(lines: list[str]) -> tuple[int, int] | None:
    """``(heading index, end index)`` of the Generation Log section, or None.

    The section runs to the next heading of the same or a higher level.
    """
    for i, line in enumerate(lines):
        heading = _GENERATION_LOG_HEADING_RE.match(line)
        if not heading:
            continue
        level = len(heading.group(1))
        for j in range(i + 1, len(lines)):
            other = _HEADING_RE.match(lines[j])
            if other and len(other.group(1)) <= level:
                return i, j
        return i, len(lines)
    return None


async def log_generation(
    album_slug: str,
    track_slug: str,
    model: str,
    clips: list[dict[str, Any]],
    notes: str = "",
) -> str:
    """Append Suno takes to a track's Generation Log, one row per clip.

    Each row links the take as https://suno.com/song/<clip_id>, so the clip id
    travels with the log. Rows are numbered on from the highest existing row; the
    template's placeholder row is replaced by the first real one. Rating is left
    as "—" — a human marks the keeper. This tool does not change the track's
    Status; call update_track_field(status, "Generated") for that.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        model: Model the takes were generated with (e.g., "v6")
        clips: One entry per take: {"clip_id": Suno clip UUID, "status":
            "complete" or "error", "duration_s": optional seconds,
            "error": optional reason for a failed take}
        notes: Text for the Notes column of every row (e.g., "via MCP, 10 credits")

    Returns:
        JSON with the rows written ({row, clip_id, url, status}) or an error
    """
    if not clips:
        return _safe_json({"error": "No clips to log"})

    cleaned: list[dict[str, Any]] = []
    for clip in clips:
        clip_id = str(clip.get("clip_id", "")).strip().lower()
        if not _CLIP_ID_RE.fullmatch(clip_id):
            return _safe_json({
                "error": f"Invalid clip id '{clip.get('clip_id', '')}' — expected a Suno clip UUID",
            })
        duration = clip.get("duration_s")
        cleaned.append({
            "clip_id": clip_id,
            "status": str(clip.get("status", "complete")).strip().lower() or "complete",
            "duration_s": (
                float(duration)
                if isinstance(duration, int | float) and not isinstance(duration, bool)
                else None
            ),
            "error": str(clip.get("error") or "").strip(),
        })

    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    path: Path = ctx["path"]

    lines = ctx["text"].split("\n")
    bounds = _generation_log_bounds(lines)
    if bounds is None:
        return _safe_json({
            "error": "Track file has no Generation Log section — add one "
                     "(see templates/track.md § Generation Log)",
            "track_slug": ctx["track_slug"],
        })
    start, end = bounds

    table_rows = [i for i in range(start + 1, end) if lines[i].lstrip().startswith("|")]
    numbers = [
        int(match.group(1))
        for i in table_rows
        if (match := _ROW_NUMBER_RE.match(lines[i].lstrip()))
    ]
    next_number = max(numbers, default=0) + 1

    today = _today()
    model_cell = _cell(model) or "—"
    new_rows: list[str] = []
    logged: list[dict[str, Any]] = []
    for offset, clip in enumerate(cleaned):
        number = next_number + offset
        failed = clip["status"] == "error"
        url = f"https://suno.com/song/{clip['clip_id']}"
        parts: list[str] = []
        if clip["duration_s"] is not None:
            parts.append(_fmt_duration(clip["duration_s"]))
        if notes.strip():
            parts.append(notes)
        if failed and clip["error"]:
            parts.append(f"error: {clip['error']}")
        result_cell = "Failed" if failed else f"[Listen]({url})"
        notes_cell = _cell(", ".join(parts)) or "—"
        new_rows.append(
            f"| {number} | {today} | {model_cell} | {result_cell} | {notes_cell} | — |"
        )
        logged.append({
            "row": number, "clip_id": clip["clip_id"], "url": url, "status": clip["status"],
        })

    placeholder = next(
        (i for i in table_rows if _PLACEHOLDER_ROW_RE.fullmatch(lines[i].strip())), None,
    )
    if placeholder is not None:
        lines[placeholder:placeholder + 1] = new_rows
    elif table_rows:
        insert_at = table_rows[-1] + 1
        lines[insert_at:insert_at] = new_rows
    else:
        # No table yet: add one at the end of the section, above its trailing blank lines.
        insert_at = end
        while insert_at > start + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines[insert_at:insert_at] = ["", _LOG_TABLE_HEADER, _LOG_TABLE_SEPARATOR, *new_rows]

    try:
        atomic_write_text(path, "\n".join(lines))
    except OSError as e:
        return _safe_json({"error": f"Cannot write track file: {e}"})

    logger.info(
        "Logged %d take(s) for %s.%s", len(logged), ctx["album_slug"], ctx["track_slug"],
    )

    # The file is written either way; a failed cache refresh self-heals on rebuild.
    try:
        ctx["track"]["mtime"] = path.stat().st_mtime
        write_state(_shared.cache.get_state())
    except Exception as e:
        logger.warning(
            "Generation Log written but cache update failed for %s.%s: %s",
            ctx["album_slug"], ctx["track_slug"], e,
        )

    return _safe_json({
        "success": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "rows": logged,
    })


def register(mcp: Any) -> None:
    """Register Suno generation bridge tools with the MCP server."""
    mcp.tool()(get_generation_request)
    mcp.tool()(log_generation)
