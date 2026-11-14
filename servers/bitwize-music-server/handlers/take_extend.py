"""Take extension — the request that carries a take on from a point in its audio.

Suno can continue a finished song from any second of it: more verses for a
take that stopped early, a new ending for one that went wrong late. Through
its MCP server that is ``audio-extensions-create`` with the take, the time to
carry on from, and the lyrics that follow; the answer holds only the
continuation, and ``audio-full-song`` joins it to what came before. This tool
writes the first request from the track file. The plugin's server never talks
to Suno; the skill sends it.

Measured on a one-minute test song: one call made two continuations
for 10 song credits; joining was free and each continuation joined into its
own whole song; the joined song ran to the continue point plus the
continuation, sang the new verse in the same voice, and was not filed in the
workspace the continuations went to. Continuing from mid-phrase left an
audible cut, so the time belongs at the end of a line.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from handlers._shared import _safe_json
from handlers.generation import (
    _fmt_duration,
    _instrumental_state,
    _load_track,
    _problem,
    _section_code,
    get_generation_request,
    parse_generation_log,
)
from handlers.take_edit import _source_take

logger = logging.getLogger(__name__)

# One audio-extensions-create call makes two continuations for 10 song credits
# (measured). Max Mode costs a multiple of that; the album plan uses the same factor.
_EXTENSION_CREDITS = 10
_MAX_MODE_FACTOR = 2
_MIN_CONTINUE_AT = 0.4      # the least audio-extensions-create accepts
_PAST_END_SLACK = 1.0       # the Generation Log holds a take's length in whole seconds
_MAX_LYRICS = 5000
_TIME_RE = re.compile(r"(?:(\d{1,3}):)?(\d{1,4}(?:\.\d+)?)")
_TAG_LINE_RE = re.compile(r"\[([^\]]*)\]")
_NUMBERED_RE = re.compile(r"(.*?)\s*#\s*(\d+)")
# Problems get_generation_request finds that also hold for a continuation. The rest are
# about what an extension never sends: the lyrics as a whole, a cover source, a duration.
_CARRIED = (
    "style_", "negative_style_", "model_", "custom_model_", "variety_", "weirdness_",
    "generation_settings_", "instrumental_mismatch", "voice_on_instrumental",
)


# =============================================================================
# Where to carry on from, and with what
# =============================================================================


def _seconds(value: str) -> float | None:
    """``"46"``, ``"46.5"``, ``"1:02"`` or ``"1:02.5"`` as seconds; None when it is none of them."""
    match = _TIME_RE.fullmatch(value)
    if not match:
        return None
    seconds = float(match.group(2))
    if match.group(1) is None:
        return seconds
    if seconds >= 60:
        return None
    return int(match.group(1)) * 60 + seconds


def lyric_sections(lyrics: str) -> list[dict[str, Any]]:
    """The sections of a Lyrics Box in order: ``[{name, label, line}]``.

    A line that is only a bracket tag opens a section; its name is the part
    before `` - ``. ``label`` is the name, with ``#n`` added when the name
    repeats (``Chorus #2``); ``line`` is the tag's line index.
    """
    sections: list[dict[str, Any]] = []
    for index, raw in enumerate(lyrics.splitlines()):
        tag = _TAG_LINE_RE.fullmatch(raw.strip())
        if tag:
            name = tag.group(1).split(" - ")[0].strip()
            if name:
                sections.append({"name": name, "line": index})
    totals = Counter(section["name"].lower() for section in sections)
    seen: Counter[str] = Counter()
    for section in sections:
        key = section["name"].lower()
        seen[key] += 1
        section["label"] = (
            f"{section['name']} #{seen[key]}" if totals[key] > 1 else section["name"]
        )
    return sections


def _pick_section(
    sections: list[dict[str, Any]], wanted: str,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """The section *wanted* names: ``(section, None)`` or ``(None, problem)``.

    Brackets, case and a performance cue are ignored; ``Chorus #2`` picks the
    second Chorus.
    """
    cleaned = wanted.strip().strip("[]").split(" - ")[0].strip()
    listed = ", ".join(section["label"] for section in sections) or "none"

    def named(name: str) -> list[dict[str, Any]]:
        return [section for section in sections if section["name"].lower() == name.lower()]

    matches = named(cleaned)
    number: int | None = None
    if not matches:
        numbered = _NUMBERED_RE.fullmatch(cleaned)
        if numbered:
            matches, number = named(numbered.group(1).strip()), int(numbered.group(2))
    if not matches or (number is not None and not 1 <= number <= len(matches)):
        return None, _problem(
            "section_not_found", "blocking",
            f"The Lyrics Box has no section '{wanted.strip()}' — it has: {listed}",
        )
    if number is not None:
        return matches[number - 1], None
    if len(matches) > 1:
        choices = ", ".join(section["label"] for section in matches)
        return None, _problem(
            "section_ambiguous", "blocking",
            f"The Lyrics Box has {len(matches)} sections named {matches[0]['name']} — "
            f"say which: {choices}",
        )
    return matches[0], None


# =============================================================================
# get_extension_request
# =============================================================================


async def get_extension_request(
    album_slug: str,
    track_slug: str,
    take: int = 0,
    continue_at: str = "",
    from_section: str = "",
) -> str:
    """Build the Suno request that carries a take on from a point in its audio.

    An extension keeps a take up to continue_at and generates what follows:
    more of a song that stopped early, or a new second half for one that went
    wrong late. Send the returned request to audio-extensions-create with an
    idempotency key. One call makes two continuations and spends song credits
    (10, measured; Max Mode costs more), so show the cost and get a go-ahead
    first. Each continuation holds only the new part: call
    audio-full-song(id: <continuation>) for each — free — to get the whole
    songs, and log those. A joined song is not filed in the album's workspace;
    file it with workspaces-update-clips.

    The words that follow come from the track's Lyrics Box, from the section
    named in from_section to the end, so they have passed the same checks as
    the rest of the track. To add new words, write them into the Lyrics Box
    first. The style, exclusions, model and sliders are the track's own.

    Args:
        album_slug: Album slug
        track_slug: Track slug or number
        take: Generation Log row of the take to carry on; 0 picks the keeper,
            or the only take with a clip id
        continue_at: Where in the take to carry on from: seconds ("46",
            "46.5"), minutes and seconds ("0:46"), or "end" for the take's
            whole length. Choose the end of a line — a continuation from
            mid-phrase leaves an audible cut
        from_section: The Lyrics Box section the continuation starts with
            ("Verse 2", "Bridge", "Chorus #2" for the second Chorus); empty
            sends no lyrics and Suno writes on by itself

    Returns:
        JSON with found, title, supported (false when a blocking problem means
        nothing should be sent), tool ("audio-extensions-create"), source
        ({take, clip_id, url, keeper, version, duration_s}), continue_at_s and
        continue_at (m:ss), from_section (the section picked, or ""), sections
        (the Lyrics Box's section names in order, numbered where a name
        repeats), request (id, continue_at, and lyrics, style, negative_style,
        model, max_mode, controls and workspace_id when the track has them),
        voice ({name} when the track names a saved Voice — add its id as
        voice_id — else null), needs_grant (request keys that need the
        account's controls.advanced feature), join ({tool: "audio-full-song",
        credits: 0}), credits (the estimated cost of the call), log_notes (the
        words to put in the Generation Log notes of the joined songs) and
        problems ([{code, severity: blocking|warning, detail}])
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]
    title = str(ctx["track"].get("title") or ctx["track_slug"]).strip()

    problems: list[dict[str, str]] = []

    # --- which take ---------------------------------------------------------------
    source, problem = _source_take(text, take)
    if problem:
        problems.append(problem)
    duration_s: int | None = None
    if source:
        duration_s = next(
            (row["duration_s"] for row in parse_generation_log(text) if row["row"] == source["take"]),
            None,
        )
        source = {**source, "duration_s": duration_s}
        if source["version"]:
            problems.append(_problem(
                "source_is_a_version", "blocking",
                f"Row {source['take']} is a version of another take — carry on the take it "
                "came from",
            ))

    # --- the track's own style, model and sliders -------------------------------------
    built = json.loads(await get_generation_request(album_slug, track_slug))
    if built.get("kind") == "speech":
        problems.append(_problem(
            "extension_not_for_speech", "blocking",
            "A spoken-word track is not extended — change the script and generate it again",
        ))
    problems += [p for p in built.get("problems", []) if p["code"].startswith(_CARRIED)]

    # --- where to carry on from -----------------------------------------------------
    at: float | None = None
    wanted_at = continue_at.strip().lower()
    if not wanted_at:
        problems.append(_problem(
            "needs_continue_at", "blocking",
            "Say where the take should carry on from — the time in the take where the part "
            "to keep ends, at the end of a line",
        ))
    elif wanted_at == "end":
        if duration_s is None:
            problems.append(_problem(
                "take_length_unknown", "blocking",
                "The Generation Log holds no length for this take — give the time to carry on "
                "from instead of 'end'",
            ))
        else:
            at = float(duration_s)
            problems.append(_problem(
                "continue_from_end", "warning",
                "Carrying on from the very end keeps the take's own ending — its last chord "
                "or fade stays in the middle of the song. To replace the ending, carry on "
                "from before it",
            ))
    else:
        at = _seconds(wanted_at)
        if at is None:
            problems.append(_problem(
                "continue_at_unrecognized", "blocking",
                f"'{continue_at.strip()}' is not a time — give seconds (46) or m:ss (0:46)",
            ))
        elif at < _MIN_CONTINUE_AT:
            at = None
            problems.append(_problem(
                "continue_at_too_early", "blocking",
                f"Suno carries a take on from {_MIN_CONTINUE_AT} s at the earliest — to redo "
                "it from the start, generate it again",
            ))
        elif duration_s is not None and at > duration_s + _PAST_END_SLACK:
            problems.append(_problem(
                "continue_at_past_end", "blocking",
                f"{_fmt_duration(at)} is past the end of the take, which is "
                f"{_fmt_duration(duration_s)} long",
            ))
            at = None

    # --- the words that follow --------------------------------------------------------
    instrumental, _ = _instrumental_state(text)
    lyrics_box = _section_code(text, "Lyrics Box") or ""
    sections = lyric_sections(lyrics_box)
    lyrics = ""
    picked = ""
    if from_section.strip():
        section, problem = _pick_section(sections, from_section)
        if problem:
            problems.append(problem)
        elif section:
            picked = section["label"]
            lyrics = "\n".join(lyrics_box.splitlines()[section["line"]:]).strip()
            if len(lyrics) > _MAX_LYRICS:
                problems.append(_problem(
                    "lyrics_too_long", "blocking",
                    f"The lyrics from {picked} on are {len(lyrics)} characters; Suno accepts "
                    f"{_MAX_LYRICS}",
                ))
    elif not instrumental and built.get("kind") != "speech":
        listed = ", ".join(section["label"] for section in sections) or "none"
        problems.append(_problem(
            "no_section_named", "warning",
            "No section named, so no lyrics are sent and Suno writes on by itself. To have "
            f"the track's own words sung, name the section to carry on with — it has: {listed}",
        ))

    # --- the request ------------------------------------------------------------------
    supported = not any(p["severity"] == "blocking" for p in problems)
    request: dict[str, Any] = {}
    if supported and source and at is not None:
        base: dict[str, Any] = built.get("request") or {}
        request = {"id": source["clip_id"], "continue_at": at}
        if lyrics:
            request["lyrics"] = lyrics
        for key in ("style", "negative_style", "model", "max_mode"):
            if key in base:
                request[key] = base[key]
        # On an extension audio_influence means likeness to the source take, which the
        # track file does not set; its Audio Influence is about a Voice or a cover source.
        controls = {
            key: value for key, value in (base.get("controls") or {}).items()
            if key != "audio_influence"
        }
        if controls:
            request["controls"] = controls
        if "workspace_id" in base:
            request["workspace_id"] = base["workspace_id"]

    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": title,
        "supported": supported,
        "tool": "audio-extensions-create",
        "source": source,
        "continue_at_s": at,
        "continue_at": _fmt_duration(at) if at is not None else "",
        "from_section": picked,
        "sections": [section["label"] for section in sections],
        "request": request,
        "voice": built.get("voice") if request else None,
        "needs_grant": [
            key for key in built.get("needs_grant", [])
            if key in request or (
                key.startswith("controls.")
                and key.split(".", 1)[1] in request.get("controls", {})
            )
        ],
        "join": {"tool": "audio-full-song", "credits": 0},
        "credits": _EXTENSION_CREDITS * (_MAX_MODE_FACTOR if request.get("max_mode") else 1),
        "log_notes": (
            f"take {source['take']} extended from {_fmt_duration(at)}"
            if request and source and at is not None else ""
        ),
        "problems": problems,
    })


def register(mcp: Any) -> None:
    """Register the take-extension tool with the MCP server."""
    mcp.tool()(get_extension_request)
