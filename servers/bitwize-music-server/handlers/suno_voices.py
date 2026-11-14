"""A saved Suno Voice on a track — the Voice row /bitwize-music:generate reads.

A track sings in one of the user's Voices when the **Voice** row of its
``## Cover / Voice Setup`` block names it (``templates/track.md``, subsection
``### Voice Selection``). get_generation_request reads that row, and the
generate skill turns the name into Suno's ``voice_id`` with ``voices-list``.
This tool writes the row, adding the block where the template puts it when a
track has none, so a Voice can be put on a track or a whole album without
hand-editing the files.

The plugin's server never talks to Suno: the skill confirms the Voice exists
on the user's account with ``voices-list`` before calling this tool, and a new
Voice is made on suno.com through the link ``voices-start`` returns.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from handlers._atomic import atomic_write_text
from handlers._shared import _find_album_or_error, _safe_json
from handlers.generation import (
    _PLACEHOLDER_CELL_RE,
    _UNSET,
    _instrumental_state,
    _load_track,
)

logger = logging.getLogger(__name__)

_SECTION = "Cover / Voice Setup"
_SUBSECTION = "Voice Selection"
_NEXT_SECTION = "Suno Inputs"  # the template puts the block just above it
_ROWS = ("Voice", "Vocal identity", "Saved from")
_OFF = "—"
_MAX_VOICE = 200  # what voices-list accepts as a query
_MAX_DETAIL = 500

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_ROW_RE = re.compile(r"^\|\s*\*\*(?P<key>[^*|]+?)\*\*\s*\|\s*(?P<value>.*?)\s*\|\s*$")
_TABLE_HEAD = ["| Attribute | Detail |", "|-----------|--------|"]


# =============================================================================
# Reading and writing the block
# =============================================================================


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """``(line index, level, title)`` for each heading outside a code block."""
    found = []
    fenced = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((i, len(match.group(1)), match.group(2).strip()))
    return found


def _span(heads: list[tuple[int, int, str]], level: int, title: str,
          start: int = 0, end: int | None = None) -> tuple[int, int] | None:
    """Lines ``[heading, end)`` of the first heading *title* at *level* in [start, end)."""
    for n, (i, lvl, text) in enumerate(heads):
        if i < start or (end is not None and i >= end):
            continue
        if lvl == level and text.casefold() == title.casefold():
            stop = next((j for j, lv, _ in heads[n + 1:] if lv <= level), None)
            if end is not None:
                stop = end if stop is None else min(stop, end)
            return i, stop if stop is not None else -1
    return None


def _unset(value: str) -> bool:
    return value.strip().casefold() in _UNSET or bool(_PLACEHOLDER_CELL_RE.fullmatch(value.strip()))


def _table(rows: dict[str, str]) -> list[str]:
    return _TABLE_HEAD + [f"| **{key}** | {value} |" for key, value in rows.items()]


def _trim_blank_tail(lines: list[str], start: int, stop: int) -> int:
    """The index after the last non-blank line in ``lines[start:stop]``."""
    while stop > start and not lines[stop - 1].strip():
        stop -= 1
    return stop


def _with_voice(text: str, voice: str, saved_from: str, vocal_identity: str) -> str:
    """*text* with its Voice Selection rows set. *voice* is ``_OFF`` to take it off."""
    lines = text.split("\n")
    heads = _headings(lines)

    def new_rows(old: dict[str, str]) -> dict[str, str]:
        old_voice = "" if _unset(old.get("Voice", "")) else old["Voice"].strip()
        same = voice != _OFF and old_voice.casefold() == voice.casefold()
        rows = {
            "Voice": old_voice if same else voice,
            "Vocal identity": vocal_identity or (old.get("Vocal identity", _OFF) if same else _OFF),
            "Saved from": saved_from or (old.get("Saved from", _OFF) if same else _OFF),
        }
        rows.update({k: v for k, v in old.items() if k not in _ROWS})  # rows a user added
        return rows

    section = _span(heads, 2, _SECTION)
    if section is None:
        block = [f"## {_SECTION}", "", f"### {_SUBSECTION}", "", *_table(new_rows({})), ""]
        anchor = _span(heads, 2, _NEXT_SECTION)
        if anchor is not None:
            at = anchor[0]
            return "\n".join([*lines[:at], *block, *lines[at:]])
        body = text.rstrip("\n")
        return body + "\n\n" + "\n".join(block)

    sec_start, sec_end = section
    sec_end = len(lines) if sec_end == -1 else sec_end
    sub = _span(heads, 3, _SUBSECTION, sec_start + 1, sec_end)
    if sub is None:
        tail = _trim_blank_tail(lines, sec_start, sec_end)
        block = ["", f"### {_SUBSECTION}", "", *_table(new_rows({})), ""]
        return "\n".join([*lines[:tail], *block, *lines[sec_end:]])

    sub_start, sub_end = sub
    sub_end = sec_end if sub_end == -1 else sub_end
    first = next((i for i in range(sub_start + 1, sub_end) if lines[i].lstrip().startswith("|")), None)
    if first is None:
        tail = _trim_blank_tail(lines, sub_start, sub_end)
        return "\n".join([*lines[:tail], "", *_table(new_rows({})), "", *lines[sub_end:]])
    last = first
    while last + 1 < sub_end and lines[last + 1].lstrip().startswith("|"):
        last += 1
    old: dict[str, str] = {}
    for line in lines[first:last + 1]:
        match = _ROW_RE.match(line.strip())
        if match:
            old[match.group("key").strip()] = match.group("value").strip()
    return "\n".join([*lines[:first], *_table(new_rows(old)), *lines[last + 1:]])


# =============================================================================
# The tool
# =============================================================================


def _bad_cell(name: str, value: str, limit: int) -> str | None:
    """Why *value* cannot go in a table cell, or None."""
    if "|" in value or "\n" in value or "\r" in value:
        return f"{name} cannot contain '|' or a line break: it goes in a table cell"
    if len(value) > limit:
        return f"{name} is longer than {limit} characters"
    return None


def _apply(path: Path, text: str, voice: str, saved_from: str, vocal_identity: str) -> bool:
    """Write the Voice rows to *path*; True when the file changed.

    Taking the Voice off a track that has no Cover / Voice Setup block leaves
    the file alone rather than adding an empty block.
    """
    if voice == _OFF and _span(_headings(text.split("\n")), 2, _SECTION) is None:
        return False
    updated = _with_voice(text, voice, saved_from, vocal_identity)
    if updated == text:
        return False
    atomic_write_text(path, updated)
    return True


async def set_track_voice(
    album_slug: str,
    voice: str,
    track_slug: str = "",
    saved_from: str = "",
    vocal_identity: str = "",
) -> str:
    """Put one of the user's saved Suno Voices on a track, or take it off.

    Writes the Voice row of the track's Cover / Voice Setup block, which
    get_generation_request reads, so the next generation sings in that Voice.
    A track without the block gets one where templates/track.md puts it,
    above Suno Inputs. This plugin cannot reach Suno: confirm the Voice is on
    the user's account with Suno's voices-list first. Nothing is generated and
    nothing is charged. Takes already made keep the voice they were sung in.

    Args:
        album_slug: Album slug (e.g., "my-album")
        voice: The Voice's name exactly as voices-list gives it, or its id (for
            a public Voice, or when two of the user's Voices share a name).
            "—" takes the Voice off.
        track_slug: Track slug or number (e.g., "01-track-name" or "01"); empty
            puts the Voice on every track of the album that has lyrics, and
            lists the instrumental ones it skipped
        saved_from: The song the Voice was made from, e.g.
            https://suno.com/song/<root_clip_id from voices-list>
        vocal_identity: What the Voice sounds like, e.g. "male baritone, warm"

    Returns:
        JSON with voice (null when taken off), updated, unchanged and skipped
        ({track, reason}) track lists, or an error
    """
    raw = (voice or "").strip()
    if not raw:
        return _safe_json({"error": "Name the Voice, or give '—' to take the Voice off"})
    off = raw.casefold() in _UNSET
    for name, value, limit in (("Voice", raw, _MAX_VOICE),
                               ("saved_from", saved_from.strip(), _MAX_DETAIL),
                               ("vocal_identity", vocal_identity.strip(), _MAX_DETAIL)):
        problem = _bad_cell(name, value, limit)
        if problem:
            return _safe_json({"error": problem})
    chosen = _OFF if off else raw
    detail = ("", "") if off else (saved_from.strip(), vocal_identity.strip())

    result: dict[str, Any] = {
        "album_slug": album_slug,
        "voice": None if off else raw,
        "updated": [],
        "unchanged": [],
        "skipped": [],
    }

    if track_slug.strip():
        ctx, error = _load_track(album_slug, track_slug)
        if error:
            return error
        assert ctx is not None
        if not off and _instrumental_state(ctx["text"])[0]:
            return _safe_json({
                "error": f"'{ctx['track_slug']}' is instrumental — a Voice sings, so it "
                         "cannot be put on an instrumental track",
            })
        result["album_slug"] = ctx["album_slug"]
        changed = _apply(ctx["path"], ctx["text"], chosen, *detail)
        result["updated" if changed else "unchanged"].append(ctx["track_slug"])
        return _safe_json(result)

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None
    result["album_slug"] = normalized
    for slug, track in sorted(album.get("tracks", {}).items()):
        path_str = track.get("path") or ""
        if not path_str:
            result["skipped"].append({"track": slug, "reason": "no track file"})
            continue
        path = Path(path_str)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            result["skipped"].append({"track": slug, "reason": f"cannot read the track file: {e}"})
            continue
        if not off and _instrumental_state(text)[0]:
            result["skipped"].append({"track": slug, "reason": "instrumental"})
            continue
        changed = _apply(path, text, chosen, *detail)
        result["updated" if changed else "unchanged"].append(slug)
    return _safe_json(result)


def register(mcp: Any) -> None:
    """Register the Suno Voice tool with the MCP server."""
    mcp.tool()(set_track_voice)
