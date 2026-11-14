"""Take check — does a generated take match its track file?

The plugin's server never talks to Suno. These tools write the questions a skill
puts to Suno's listening agent (the `audio-listen` tool: free, text in, text
out) and turn its answers into a short advisory report: lyric lines that are not
sung, changed or hard to understand; tempo against the Style Box; the voice
against Vocal Gender; excluded elements that are heard; performance problems.
The report states what was heard. It never ranks takes or picks one.

Why the listening agent and not Suno's other analysis tools (measured):
`audio-lyrics-alignment` returned, for a library song, a transcript
missing two lines that are plainly sung — every word marked `success` — while
the agent placed all four lines correctly, as a local transcription confirmed.
`audio-analysis` carries the same tempo and key but also every beat of the song,
far too much to pass through a model for a check.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from handlers import _shared
from handlers._shared import _extract_markdown_section, _safe_json
from handlers.gates import _parse_duration_seconds
from handlers.generation import (
    _TEMPLATE_EXCLUDE,
    _UNSET,
    _bare_exclusions,
    _instrumental_state,
    _load_track,
    _section_code,
    parse_generation_log,
)
from tools.state.parsers import _extract_table_value

logger = logging.getLogger(__name__)

# audio-listen accepts a question of up to 2000 characters.
_QUESTION_LIMIT = 1900
_LINE_LIMIT = 240          # a longer lyric line is cut in the question
_QUOTED_LINES = 3          # flagged lines quoted in a detail before "and N more"
_QUOTED_CHANGES = 6        # "what was heard instead" notes shown in the lyrics detail
_TEMPO_TOLERANCE = 0.04    # a measured tempo within 4% of the one asked for matches
_DURATION_TOLERANCE = 0.20

_CLIP_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_TAG_LINE_RE = re.compile(r"\[([^\]]*)\]")
_INLINE_TAG_RE = re.compile(r"\[[^\]]*\]")
_BPM_RE = re.compile(r"(\d{2,3})(?:\s*[-\u2013]\s*(\d{2,3}))?\s*bpm", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_FENCE_RE = re.compile(r"```(?:json)?[ \t]*\n?(.*?)```", re.DOTALL | re.IGNORECASE)

_LINE_FIELDS = (
    "missing_lines (numbers of lines that are not sung), changed_lines (numbers of lines "
    "sung with different words), unclear_lines (numbers of lines that are hard to understand), "
    "changes (a list of short strings, one for each changed or unclear line, saying what you "
    "hear instead)"
)
_SOUND_FIELDS = (
    "bpm, key, time_signature, has_vocals (true or false), vocal_gender (\"male\", \"female\", "
    "\"mixed\" or \"none\"), vocal (a short description), instruments (a list), problems (a "
    "list of short strings, empty if none), ends_cleanly (true or false)"
)
_SOUND_TASK = (
    "Measure the tempo and key, describe the instruments you hear, and name any problem a "
    "producer should know about: garbled or mispronounced words, clipping or distortion, an "
    "abrupt ending, a section that repeats or is cut short."
)

_FIRST_HEAD = (
    "Check this take against what was asked for. These are the lyric lines it should sing, "
    "numbered, with section names in brackets:\n"
)
_FIRST_TAIL = (
    "\nListen to the whole song. For each numbered line decide whether it is sung as written. "
    f"{_SOUND_TASK} Describe the lead vocal too.\n"
    f"End with a JSON block with these fields: {_LINE_FIELDS}, {_SOUND_FIELDS}."
)
_NEXT_HEAD = (
    "These lyric lines come from later in the same song, numbered, with section names in "
    "brackets:\n"
)
_NEXT_TAIL = (
    "\nFor each numbered line decide whether it is sung as written.\n"
    f"End with a JSON block with these fields: {_LINE_FIELDS}."
)
_INSTRUMENTAL_QUESTION = (
    "This take should be an instrumental with no singing. Listen to the whole piece. "
    f"{_SOUND_TASK} Say whether any voice is heard.\n"
    f"End with a JSON block with these fields: {_SOUND_FIELDS}."
)
_SOUND_ONLY_QUESTION = (
    f"Listen to the whole song. {_SOUND_TASK} Describe the lead vocal too.\n"
    f"End with a JSON block with these fields: {_SOUND_FIELDS}."
)


# =============================================================================
# Reading the track file
# =============================================================================


def lyric_lines(lyrics: str) -> list[dict[str, Any]]:
    """The lines a take should sing, numbered from 1, each with its section name.

    A line that is only a bracket tag (``[Verse 1 - soft intimate]``, ``[End]``)
    names the section that follows and is not a sung line; the name is the part
    before `` - ``. Tags inside a sung line are dropped from its text.
    """
    lines: list[dict[str, Any]] = []
    section = ""
    for raw in lyrics.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        tag = _TAG_LINE_RE.fullmatch(stripped)
        if tag:
            section = tag.group(1).split(" - ")[0].strip()
            continue
        text = " ".join(_INLINE_TAG_RE.sub(" ", stripped).split())
        if text:
            lines.append({"n": len(lines) + 1, "section": section, "text": text})
    return lines


def asked_bpm(text: str, style: str | None) -> list[int] | None:
    """The tempo the track asks for, as ``[low, high]`` (equal for a single tempo).

    Read from the Style Box first, then the Musical Direction section.
    """
    for source in (style or "", _extract_markdown_section(text, "Musical Direction") or ""):
        match = _BPM_RE.search(source)
        if match:
            low = int(match.group(1))
            high = int(match.group(2)) if match.group(2) else low
            return sorted((low, high))
    return None


def _exclusions(text: str) -> list[str]:
    """Exclude Styles as bare, lower-case elements."""
    exclude = _section_code(text, "Exclude Styles")
    if exclude is None or exclude.lower() in _UNSET or exclude == _TEMPLATE_EXCLUDE:
        return []
    bare, _ = _bare_exclusions(exclude)
    return [item.strip().lower() for item in bare.split(",") if item.strip()]


def _targets(text: str, instrumental: bool) -> dict[str, Any]:
    """What the track file asks for, in the terms the agent's answer can be held against."""
    settings = _extract_markdown_section(text, "Generation Settings") or ""
    gender = (_extract_table_value(settings, "Vocal Gender") or "").strip().lower()
    return {
        "bpm": asked_bpm(text, _section_code(text, "Style Box")),
        "vocal_gender": gender if gender in ("male", "female") and not instrumental else None,
        "exclude": _exclusions(text),
        "duration_s": _parse_duration_seconds(_extract_table_value(text, "Target Duration")),
    }


def _takes(text: str) -> tuple[list[dict[str, Any]], list[int]]:
    """The takes that can be checked, and the ones to check by default.

    A take needs a clip id, so share links from before MCP generation are left
    out. So is a version of another take (an instrumental version): the lyric
    check has nothing to hold it against. The default mirrors
    /bitwize-music:listen: the newest two takes while none is approved, the
    approved ones after that.
    """
    takes = [
        {
            "take": take["row"], "clip_id": take["clip_id"], "keeper": take["approved"],
            "duration_s": take["duration_s"],
        }
        for take in parse_generation_log(text) if take["clip_id"] and not take["version"]
    ]
    keepers = [take["take"] for take in takes if take["keeper"]]
    return takes, keepers or [take["take"] for take in takes[-2:]]


# =============================================================================
# Questions
# =============================================================================


def _render(lines: list[dict[str, Any]]) -> str:
    """Numbered lines, with a ``[Section]`` header wherever the section changes."""
    out: list[str] = []
    section: str | None = None
    for line in lines:
        if line["section"] != section:
            section = line["section"]
            if section:
                out.append(f"[{section}]")
        out.append(f"{line['n']}. {line['text'][:_LINE_LIMIT]}")
    return "\n".join(out)


def build_questions(lines: list[dict[str, Any]], instrumental: bool) -> list[dict[str, Any]]:
    """The questions to put to audio-listen about one take.

    ``[{"question", "first", "last"}]``: each question asks about the lyric lines
    numbered first..last, and only the first asks about the sound of the take.
    A track without lyric lines gets a single question about its sound
    (``first`` and ``last`` are 0).
    """
    if instrumental:
        return [{"question": _INSTRUMENTAL_QUESTION, "first": 0, "last": 0}]
    if not lines:
        return [{"question": _SOUND_ONLY_QUESTION, "first": 0, "last": 0}]

    questions: list[dict[str, Any]] = []
    start = 0
    while start < len(lines):
        head, tail = (_FIRST_HEAD, _FIRST_TAIL) if not questions else (_NEXT_HEAD, _NEXT_TAIL)
        budget = _QUESTION_LIMIT - len(head) - len(tail)
        end = start + 1  # a question always carries at least one line
        while end < len(lines) and len(_render(lines[start:end + 1])) <= budget:
            end += 1
        chunk = lines[start:end]
        questions.append({
            "question": head + _render(chunk) + tail,
            "first": chunk[0]["n"],
            "last": chunk[-1]["n"],
        })
        start = end
    return questions


async def get_take_check_plan(album_slug: str, track_slug: str) -> str:
    """The questions to put to Suno's listening agent to check a track's takes.

    A take check asks Suno's audio-listen tool (free; nothing is made or
    changed) whether a take sings the track's lyric lines as written and how it
    sounds, then holds the answers against the track file with
    evaluate_take_check. Put every question to every take being checked, in
    order: audio-listen(id: <clip_id>, question: <question>), then
    audio-listen-wait. At most five questions may be unanswered at once.

    Args:
        album_slug: Album slug
        track_slug: Track slug or number

    Returns:
        JSON with found, album_slug, track_slug, title, instrumental,
        takes ([{take, clip_id, keeper, duration_s}] — takes with a Suno clip id),
        default_takes (take numbers to check when the user names none: the
        newest two while none is approved, the approved ones after that),
        lines ([{n, section, text}] — the lyric lines, numbered),
        questions ([{question, first, last}] — each covers lines first..last;
        an instrumental gets one question about its sound),
        targets ({bpm: [low, high] or null, vocal_gender, exclude, duration_s}
        — what the track file asks for), and enabled (config
        generation.take_check, default true: whether /bitwize-music:generate
        runs the check on its own)
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]

    instrumental, _ = _instrumental_state(text)
    lines = [] if instrumental else lyric_lines(_section_code(text, "Lyrics Box") or "")
    takes, default_takes = _takes(text)
    generation = _shared.cache.get_state().get("config", {}).get("generation", {}) or {}
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": ctx["track"].get("title", ctx["track_slug"]),
        "instrumental": instrumental,
        "takes": takes,
        "default_takes": default_takes,
        "lines": lines,
        "questions": build_questions(lines, instrumental),
        "targets": _targets(text, instrumental),
        "enabled": bool(generation.get("take_check", True)),
    })


# =============================================================================
# Reading the agent's answers
# =============================================================================


def _answer_fields(answer: str) -> dict[str, Any] | None:
    """The JSON object in an answer: its last fenced block, else a bare ``{...}``."""
    candidates = [block.strip() for block in _FENCE_RE.findall(answer)]
    start, end = answer.find("{"), answer.rfind("}")
    if start != -1 and end > start:
        candidates.insert(0, answer[start:end + 1])
    for candidate in reversed(candidates):
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _line_numbers(value: Any, first: int, last: int) -> set[int]:
    """The line numbers in an answer's list that belong to its own question."""
    if not isinstance(value, list):
        return set()
    numbers: set[int] = set()
    for item in value:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            number = item
        elif isinstance(item, float) and item.is_integer():
            number = int(item)
        elif isinstance(item, str) and item.strip().isdigit():
            number = int(item.strip())
        else:
            continue
        if first <= number <= last:
            numbers.add(number)
    return numbers


def _number(value: Any) -> float | None:
    """A positive number from a JSON number or from text such as "190.2 BPM"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        match = _NUMBER_RE.search(value)
        return float(match.group()) if match else None
    return None


def _strings(value: Any) -> list[str]:
    """A list of short texts from a JSON list (or one string), without trailing full stops."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    texts = (str(item).strip().rstrip(".") for item in value if isinstance(item, (str, int, float)))
    return [text for text in texts if text]


# =============================================================================
# Checks
# =============================================================================


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    """A report line. *status* is ``ok``, ``warn`` or ``info``."""
    return {"check": name, "status": status, "detail": detail}


def _quote(lines: list[dict[str, Any]], verb: str) -> str:
    """"line 2 not sung: "..."" for one line; a count and the first few for more."""
    if len(lines) == 1:
        return f'line {lines[0]["n"]} {verb}: "{lines[0]["text"]}"'
    quoted = ", ".join(f'{line["n"]} "{line["text"]}"' for line in lines[:_QUOTED_LINES])
    more = f" and {len(lines) - _QUOTED_LINES} more" if len(lines) > _QUOTED_LINES else ""
    return f"{len(lines)} lines {verb}: {quoted}{more}"


def _tempo_check(asked: list[int] | None, measured: float | None) -> dict[str, str] | None:
    if measured is None:
        return None
    if asked is None:
        return _check("tempo", "info", f"{measured:g} BPM measured; the track names no tempo")
    low, high = asked
    asked_text = str(low) if low == high else f"{low}-{high}"
    # A tagger often counts a relaxed song at twice its felt tempo, or a busy one at half.
    for factor, counted in ((1.0, ""), (0.5, "double time"), (2.0, "half time")):
        if low * (1 - _TEMPO_TOLERANCE) <= measured * factor <= high * (1 + _TEMPO_TOLERANCE):
            if not counted:
                return _check("tempo", "ok", f"{measured:g} BPM (asked {asked_text})")
            return _check(
                "tempo", "ok",
                f"{measured:g} BPM measured: the {asked_text} asked for, counted in {counted}",
            )
    return _check("tempo", "warn", f"{measured:g} BPM measured, {asked_text} asked")


def _vocal_check(asked: str | None, fields: dict[str, Any]) -> dict[str, str] | None:
    heard = str(fields.get("vocal_gender") or "").strip().lower()
    description = str(fields.get("vocal") or "").strip()
    if heard == "none" or fields.get("has_vocals") is False:
        return _check("vocal", "warn", "no voice heard")
    if asked and heard in ("male", "female") and heard != asked:
        return _check("vocal", "warn", f"{heard} lead heard, {asked} asked")
    label = f"{heard} lead" if heard in ("male", "female") else (
        "male and female voices" if heard == "mixed" else heard
    )
    detail = " — ".join(part for part in (label, description) if part)
    if not detail:
        return None
    matched = bool(asked) and heard == asked
    return _check("vocal", "ok" if matched else "info", detail)


def _excluded_heard(exclude: list[str], fields: dict[str, Any]) -> list[str]:
    """Excluded elements that turn up among the instruments or in the voice description."""
    heard_in = " | ".join(_strings(fields.get("instruments")) + _strings(fields.get("vocal"))).lower()
    found = []
    for item in exclude:
        # "drums" also means "drum machine"; "synth" also means "synths". "bass" stays "bass".
        stem = item[:-1] if item.endswith("s") and not item.endswith("ss") and len(item) > 3 else item
        if re.search(rf"(?<!\w){re.escape(stem)}(?:e?s)?(?!\w)", heard_in):
            found.append(item)
    return found


def _fmt_duration(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


async def evaluate_take_check(
    album_slug: str,
    track_slug: str,
    clip_id: str,
    answers: list[str],
    duration_s: float = 0.0,
) -> str:
    """Hold the listening agent's answers about one take against the track file.

    Call it once per take, after audio-listen-wait has answered every question
    from get_take_check_plan. The report is advisory: it says what the agent
    heard and where that differs from the track file. The agent can be wrong,
    so a flagged line is a place to listen, not proof. Never use the report to
    pick a take.

    Args:
        album_slug: Album slug
        track_slug: Track slug or number
        clip_id: The take's Suno clip id
        answers: The agent's answers, word for word, one per question and in
            the order of get_take_check_plan's questions
        duration_s: The take's length in seconds; 0 uses the length recorded
            in the Generation Log, if any

    Returns:
        JSON with found, clip_id, take (its Generation Log row, or null),
        status ("ok" or "warn"), summary ("nothing flagged" or "N things to
        check"), checks ([{check, status: ok|warn|info, detail}] for lyrics,
        tempo, key, vocal, excluded, problems, ending, duration, unread),
        flagged_lines ({missing, changed, unclear}: [{n, section, text}]),
        changes (the agent's notes on what it heard instead) and findings
        (what the agent measured: bpm, key, time_signature, vocal_gender,
        vocal, instruments), or an error
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]

    clip_id = clip_id.strip().lower()
    if not _CLIP_ID_RE.fullmatch(clip_id):
        return _safe_json({"error": f"Not a Suno clip id: '{clip_id}'"})

    instrumental, _ = _instrumental_state(text)
    lines = [] if instrumental else lyric_lines(_section_code(text, "Lyrics Box") or "")
    questions = build_questions(lines, instrumental)
    if len(answers) != len(questions):
        expected = f"{len(questions)} answer{'' if len(questions) == 1 else 's'}"
        return _safe_json({
            "error": f"Expected {expected}, one per question in get_take_check_plan, "
                     f"got {len(answers)}",
        })

    # --- read the answers -------------------------------------------------------
    fields: dict[str, Any] = {}
    flagged: dict[str, set[int]] = {"missing": set(), "changed": set(), "unclear": set()}
    changes: list[str] = []
    unread: list[dict[str, Any]] = []
    checked_lines = 0
    for question, answer in zip(questions, answers, strict=True):
        data = _answer_fields(str(answer))
        if data is None:
            unread.append(question)
            continue
        checked_lines += question["last"] - question["first"] + 1 if question["first"] else 0
        for kind in flagged:
            flagged[kind] |= _line_numbers(data.get(f"{kind}_lines"), question["first"], question["last"])
        changes += _strings(data.get("changes"))
        for key, value in data.items():
            if value is not None and key not in fields:
                fields[key] = value
    flagged["changed"] -= flagged["missing"]
    flagged["unclear"] -= flagged["missing"] | flagged["changed"]
    by_number = {line["n"]: line for line in lines}
    flagged_lines = {
        kind: [by_number[number] for number in sorted(numbers)] for kind, numbers in flagged.items()
    }

    # --- checks -----------------------------------------------------------------
    targets = _targets(text, instrumental)
    logged = next(
        (row for row in parse_generation_log(text) if row["clip_id"] == clip_id), None,
    )
    checks: list[dict[str, str]] = []
    read_any = len(unread) < len(questions)

    if instrumental:
        if read_any and ("has_vocals" in fields or "vocal_gender" in fields):
            voiced = fields.get("has_vocals") is True or str(
                fields.get("vocal_gender") or "none").strip().lower() not in ("none", "")
            checks.append(
                _check("lyrics", "warn", "a voice is heard on an instrumental track") if voiced
                else _check("lyrics", "ok", "no voice heard")
            )
    elif lines and checked_lines:
        details = [
            _quote(flagged_lines[kind], verb)
            for kind, verb in (
                ("missing", "not sung"),
                ("changed", "sung with different words"),
                ("unclear", "hard to understand"),
            ) if flagged_lines[kind]
        ]
        if details:
            if changes and (flagged_lines["changed"] or flagged_lines["unclear"]):
                more = f" and {len(changes) - _QUOTED_CHANGES} more" if len(changes) > _QUOTED_CHANGES else ""
                details.append("heard: " + "; ".join(changes[:_QUOTED_CHANGES]) + more)
            checks.append(_check("lyrics", "warn", "; ".join(details)))
        elif checked_lines == len(lines):
            checks.append(_check("lyrics", "ok", f"all {len(lines)} lines sung as written"))
        else:
            checks.append(_check(
                "lyrics", "ok", f"{checked_lines} of {len(lines)} lines checked, none flagged",
            ))

    tempo = _tempo_check(targets["bpm"], _number(fields.get("bpm")))
    if tempo:
        checks.append(tempo)
    key = str(fields.get("key") or "").strip()
    if key:
        checks.append(_check("key", "info", key))
    if not instrumental and read_any:
        vocal = _vocal_check(targets["vocal_gender"], fields)
        if vocal:
            checks.append(vocal)
    heard = _excluded_heard(targets["exclude"], fields)
    if heard:
        checks.append(_check("excluded", "warn", f"excluded but heard: {', '.join(heard)}"))
    problems = _strings(fields.get("problems"))
    if problems:
        checks.append(_check("problems", "warn", "; ".join(problems)))
    if fields.get("ends_cleanly") is False:
        checks.append(_check("ending", "warn", "does not end cleanly"))
    target_s = targets["duration_s"]
    if not duration_s or duration_s <= 0:
        # Not given: use the length log_generation recorded for this take, if any.
        duration_s = float(logged["duration_s"]) if logged and logged["duration_s"] else 0.0
    if target_s and duration_s and duration_s > 0:
        within = abs(duration_s - target_s) <= target_s * _DURATION_TOLERANCE
        checks.append(_check(
            "duration", "ok" if within else "warn",
            f"{_fmt_duration(duration_s)} (target {_fmt_duration(target_s)})" if within
            else f"{_fmt_duration(duration_s)}, target {_fmt_duration(target_s)}",
        ))
    if unread:
        gaps = "; ".join(
            f"lines {q['first']}-{q['last']} were not checked" if q["first"]
            else "the sound of the take was not checked" for q in unread
        )
        checks.append(_check(
            "unread", "info",
            f"{len(unread)} of {len(questions)} answers had no readable JSON: {gaps}",
        ))

    warnings = sum(1 for check in checks if check["status"] == "warn")
    take = logged["row"] if logged else None
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "clip_id": clip_id,
        "take": take,
        "status": "warn" if warnings else "ok",
        "summary": (
            "nothing flagged" if not warnings
            else f"{warnings} thing{'' if warnings == 1 else 's'} to check"
        ),
        "checks": checks,
        "flagged_lines": flagged_lines,
        "changes": changes,
        "findings": {
            key: fields[key]
            for key in ("bpm", "key", "time_signature", "vocal_gender", "vocal", "instruments")
            if key in fields
        },
    })


def register(mcp: Any) -> None:
    """Register the take-check tools with the MCP server."""
    mcp.tool()(get_take_check_plan)
    mcp.tool()(evaluate_take_check)
