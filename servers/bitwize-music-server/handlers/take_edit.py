"""Take edit — the request that changes part of a take and keeps the rest.

Suno can edit a finished song: change a few words or lines, cut or add a line,
redo a time range, add or drop an instrument. Through its MCP server that is an
audio-create call with the song in ``reference_audio_ids`` and a plain-language
``description`` that names the song by title. This tool writes that request from
the track file. The plugin's server never talks to Suno; the skill sends it.

Measured on a one-minute test song: one call made two edited takes
for 10 song credits in under a minute; both kept the source's title and exact
length, sang the changed word, and came back with the lyrics updated; the
album's ``workspace_id`` and a ``model`` were accepted alongside.

The same call makes an instrumental version of a take ("remove all the
vocals"): two takes of the source's exact length with no voice on them, for 10
credits. Asking for an a cappella the same way did not work in that test — one
take came back as the instrumental, the other as a shorter re-sung song with
its guitar — so only the instrumental is offered; the vocals stem is the a
cappella.
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any

from handlers._shared import _extract_markdown_section, _safe_json
from handlers.gates import _KNOWN_MODELS
from handlers.generation import (
    VERSIONS,
    _album_workspace,
    _instrumental_state,
    _load_track,
    _problem,
    _section_code,
    keeper_clip,
    parse_generation_log,
)
from handlers.take_check import lyric_lines
from tools.state.parsers import _extract_table_value

logger = logging.getLogger(__name__)

_MAX_DESCRIPTION = 3000
# Past this many changed places Suno re-sings the whole song as a cover.
_MAX_EDIT_PLACES = 5
# The wording measured to drop the vocals and keep the rest of the take.
_VERSION_REQUESTS = {
    "instrumental": (
        "remove all the vocals to make an instrumental version. Keep everything else as it is."
    ),
}
_ID_OR_LINK_RE = re.compile(
    r"https?://|suno\.com|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


# =============================================================================
# Lyric changes
# =============================================================================


def lyric_changes(old_lyrics: str, new_lyrics: str) -> list[dict[str, str]]:
    """What turns the sung lines of *old_lyrics* into those of *new_lyrics*.

    Each entry is ``{"kind": "change", "old", "new"}``, ``{"kind": "cut",
    "old"}`` or ``{"kind": "add", "new", "after"}`` (``after`` is the line it
    follows, empty at the start). Section tags and performance cues are not
    sung, so changing them is not a change.
    """
    old = [line["text"] for line in lyric_lines(old_lyrics)]
    new = [line["text"] for line in lyric_lines(new_lyrics)]
    changes: list[dict[str, str]] = []
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        olds, news = old[i1:i2], new[j1:j2]
        paired = min(len(olds), len(news))
        changes += [
            {"kind": "change", "old": olds[k], "new": news[k]} for k in range(paired)
        ]
        changes += [{"kind": "cut", "old": line} for line in olds[paired:]]
        for offset, line in enumerate(news[paired:]):
            position = j1 + paired + offset
            changes.append({
                "kind": "add", "new": line, "after": new[position - 1] if position else "",
            })
    return changes


def _quote(text: str) -> str:
    """*text* in double quotes, or in single quotes when it holds a double quote."""
    return f"'{text}'" if '"' in text else f'"{text}"'


def _describe(change: dict[str, str]) -> str:
    if change["kind"] == "change":
        return f"change {_quote(change['old'])} to {_quote(change['new'])}"
    if change["kind"] == "cut":
        return f"cut the line {_quote(change['old'])}"
    if change["after"]:
        return f"after the line {_quote(change['after'])}, add the line {_quote(change['new'])}"
    return f"add the line {_quote(change['new'])} at the start"


# =============================================================================
# Which take
# =============================================================================


def _source_take(
    text: str, take: int,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """The take to edit: ``(source, None)`` or ``(None, problem)``.

    A row number picks that take. Without one, the keeper is edited; failing
    that, the only take that can be.
    """
    rows = parse_generation_log(text)
    if not rows:
        return None, _problem(
            "no_takes", "blocking",
            "The Generation Log has no takes — generate the track first",
        )
    keeper_id, _, _, _ = keeper_clip(text)

    def source(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "take": row["row"],
            "clip_id": row["clip_id"],
            "url": f"https://suno.com/song/{row['clip_id']}",
            "keeper": bool(row["approved"] or row["clip_id"] == keeper_id),
            "version": row["version"],
        }

    if take:
        row = next((r for r in rows if r["row"] == take), None)
        if row is None:
            return None, _problem(
                "take_not_found", "blocking",
                f"The Generation Log has no row {take}",
            )
        if not row["clip_id"]:
            return None, _problem(
                "take_has_no_clip_id", "blocking",
                f"Row {take} is a share link from before MCP generation and cannot be edited "
                "through the MCP — edit it on suno.com",
            )
        return source(row), None

    # A version of a take is never the default: it is kept beside the track, not as it.
    editable = [r for r in rows if r["clip_id"] and not r["version"]]
    if not editable:
        return None, _problem(
            "take_has_no_clip_id", "blocking",
            "Every logged take is a share link from before MCP generation — edit on suno.com",
        )
    if keeper_id:
        row = next((r for r in editable if r["clip_id"] == keeper_id), None)
        if row:
            return source(row), None
    if len(editable) == 1:
        return source(editable[0]), None
    listed = ", ".join(str(r["row"]) for r in editable)
    return None, _problem(
        "take_ambiguous", "blocking",
        f"Say which take to edit — rows {listed} are all undecided",
    )


# =============================================================================
# get_edit_request
# =============================================================================


async def get_edit_request(
    album_slug: str,
    track_slug: str,
    take: int = 0,
    instruction: str = "",
    take_lyrics: str = "",
    version: str = "",
) -> str:
    """Build the Suno request that edits one take in place, or makes a version of it.

    An edit changes part of a finished take and keeps the rest of its audio:
    a few words or lines, a cut or added line, a redone time range, an
    instrument added or dropped. Send the returned request to audio-create
    with an idempotency key, and nothing else: duration, instrumental and
    vocal_gender make Suno regenerate the whole song. One call makes two edited
    takes and spends song credits (10, measured), so show the cost and get a
    go-ahead first.

    Give either the user's words or the take's lyrics:
      - instruction: what to change ("drop the synth", "redo 0:45 to 1:00 with
        more energy", "change 'the light is gone' to 'the light came home'").
        The song's title is put in front; ids and links are refused.
      - take_lyrics: the lyrics the take was made with (audio-retrieve ->
        metadata.lyrics). The edit then brings the take in line with the
        track's Lyrics Box — the way to apply a pronunciation or wording fix
        made in the track file.

    Or ask for a version of the take instead of a change to it:
      - version: "instrumental" takes the vocals off and keeps the rest. Log
        the two takes that come back with log_notes in their notes; they are
        then kept beside the track and never taken for its keeper, and
        get_suno_import_plan(version) saves the one the user marks. An a
        cappella is not offered: asked for this way it came back wrong, and
        the vocals stem of a stem split is the a cappella.

    Args:
        album_slug: Album slug
        track_slug: Track slug or number
        take: Generation Log row of the take to edit; 0 picks the keeper, or
            the only take with a clip id
        instruction: What to change, in plain words (wins over take_lyrics)
        take_lyrics: The lyrics the take was generated with
        version: "instrumental" to make that version of the take (wins over
            instruction and take_lyrics)

    Returns:
        JSON with found, title, supported (false when a blocking problem means
        nothing should be sent), mode ("instruction", "lyrics" or "version"),
        version ("instrumental" or ""), source ({take, clip_id, url, keeper,
        version}), request (reference_audio_ids, description, and model and
        workspace_id when the track has them), log_notes (for a version: the
        words its Generation Log notes must carry), changes ([{kind:
        change|cut|add, old, new, after}] in lyrics mode), places (how many
        places change; past 5 Suno re-sings the whole song) and problems
        ([{code, severity: blocking|warning, detail}])
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]
    title = str(ctx["track"].get("title") or ctx["track_slug"]).strip()

    problems: list[dict[str, str]] = []
    changes: list[dict[str, str]] = []
    description = ""
    mode: str | None = None

    source, problem = _source_take(text, take)
    if problem:
        problems.append(problem)

    instruction = " ".join(instruction.split())
    version = " ".join(version.lower().replace("-", " ").split())
    if version:
        mode = "version"
        if version not in VERSIONS:
            problems.append(_problem(
                "version_unsupported", "blocking",
                f"'{version}' is not a version this makes — only: {', '.join(VERSIONS)}. An a "
                "cappella asked for this way came back wrong when measured; the vocals stem "
                "is the a cappella (/bitwize-music:import-audio --from-suno <album> <track> --stems)",
            ))
        else:
            description = f"In {title}, {_VERSION_REQUESTS[version]}"
            if version == "instrumental" and _instrumental_state(text)[0]:
                problems.append(_problem(
                    "already_instrumental", "blocking",
                    "The track is an instrumental already — there are no vocals to take off",
                ))
            if source and source["version"]:
                problems.append(_problem(
                    "source_is_a_version", "blocking",
                    f"Row {source['take']} is itself a version of another take — make the "
                    "version from the take it came from",
                ))
    elif instruction:
        mode = "instruction"
        if _ID_OR_LINK_RE.search(instruction):
            problems.append(_problem(
                "id_or_link_in_instruction", "blocking",
                "Suno takes no ids or links in an edit instruction — name the song by its title",
            ))
        named = title.lower() in instruction.lower()
        description = instruction if named else f"In {title}, {instruction}"
    elif take_lyrics.strip():
        mode = "lyrics"
        changes = lyric_changes(take_lyrics, _section_code(text, "Lyrics Box") or "")
        if not changes:
            problems.append(_problem(
                "nothing_to_change", "blocking",
                "The Lyrics Box sings the same lines as the take — say what to change instead",
            ))
        else:
            description = f"In {title}, " + "; ".join(_describe(c) for c in changes) + "."
            if len(changes) > _MAX_EDIT_PLACES:
                problems.append(_problem(
                    "edit_rewrites_song", "warning",
                    f"{len(changes)} places differ. Past {_MAX_EDIT_PLACES}, Suno re-sings the "
                    "whole song as a cover instead of editing it — regenerating with "
                    "/bitwize-music:generate may serve better",
                ))
    else:
        problems.append(_problem(
            "needs_instruction", "blocking",
            "Say what to change, or pass the take's lyrics (audio-retrieve -> metadata.lyrics) "
            "to edit it to match the Lyrics Box",
        ))

    if len(description) > _MAX_DESCRIPTION:
        problems.append(_problem(
            "description_too_long", "blocking",
            f"The edit instruction is {len(description)} characters; Suno accepts "
            f"{_MAX_DESCRIPTION}",
        ))

    supported = not any(p["severity"] == "blocking" for p in problems)
    request: dict[str, Any] = {}
    if supported and source:
        request = {"reference_audio_ids": [source["clip_id"]], "description": description}
        settings = _extract_markdown_section(text, "Generation Settings") or ""
        model = (_extract_table_value(settings, "Model") or "").strip().lower()
        if model in _KNOWN_MODELS:
            request["model"] = model
        workspace = _album_workspace(ctx["album"])
        if workspace:
            request["workspace_id"] = workspace["id"]

    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": title,
        "supported": supported,
        "mode": mode,
        "version": version if mode == "version" and version in VERSIONS else "",
        "source": source,
        "request": request,
        "log_notes": (
            f"{version} version of take {source['take']}"
            if supported and source and mode == "version" else ""
        ),
        "changes": changes,
        "places": len(changes),
        "problems": problems,
    })


def register(mcp: Any) -> None:
    """Register the take-edit tool with the MCP server."""
    mcp.tool()(get_edit_request)
