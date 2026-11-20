"""Laying a music video out as shots, for Suno's Sequences.

A Sequence is a timeline of shots over a song. Each shot holds a still (its
keyframe) or a generated clip of 5 to 15 seconds. The plugin's server never
talks to Suno: the music-video skill calls ``sequence-create`` and the tools
after it. This module plans the shots on the song's sections and builds the
request.

Clips are paid for by the second in Visuals credits, and Suno charges a clip by
the whole second, rounded up (measured with a dry run: a 9.44-second shot is
charged as 10). ``billed_seconds`` says what a plan would be charged for;
the price itself comes from Suno's dry run, never from here.
"""

from __future__ import annotations

import json
import math
import re
from itertools import pairwise
from typing import Any, TypeGuard

from tools.promotion import lyric_video as lv

# A clip is 5 to 15 seconds long, so a shot is at most 15.
MIN_CLIP_S = 5
MAX_CLIP_S = 15
DEFAULT_MAX_SHOT_S = 10

# sequence-create: "Plan at most 40 shots".
MAX_SHOTS = 40
MAX_NOTES = 1000
# sequence-create: at most 12 characters and 12 sets, and the style, characters,
# sets and shot notes together hold at most 32 KB.
MAX_NAMED = 12
MAX_KEPT_BYTES = 32 * 1024
_MIN_CS = MIN_CLIP_S * 100
DEFAULT_ASPECT = "16:9"

_SONG_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _number(value: Any) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _cs(seconds: float) -> int:
    """Seconds as whole hundredths, the unit the plan is worked out in.

    Suno takes a shot's length to the hundredth. Working in whole hundredths
    means a shot checked to be within the longest allowed still is after it is
    written out, with no rounding in between.
    """
    return round(float(seconds) * 100)


def _spans(total: int, sections: Any) -> list[tuple[int, int, str]]:
    """The song as back-to-back spans in hundredths, one per section, with no time lost.

    Each span runs from where the one before ended to its section's end, so a
    gap or an overlap in the sections changes nothing; the first starts at 0
    and the last ends with the song.
    """
    if not isinstance(sections, list):
        raise ValueError("The sections have to be a list of {start_s, end_s, label}")
    ends: list[tuple[int, str]] = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError(f"Not a section with a start_s and an end_s: {section!r}")
        first, last = section.get("start_s"), section.get("end_s")
        if not _number(first) or not _number(last):
            raise ValueError(f"Not a section with a start_s and an end_s: {section!r}")
        ends.append((_cs(last), str(section.get("label") or "")))
    ends.sort(key=lambda entry: entry[0])

    spans: list[tuple[int, int, str]] = []
    at = 0
    for end, label in ends:
        end = min(end, total)
        if end > at:
            spans.append((at, end, label))
            at = end
    if not spans:
        return [(0, total, "")]
    if at < total:
        start, _end, label = spans[-1]
        spans[-1] = (start, total, label)
    return spans


def _merged(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Join a span too short for a clip to its neighbour."""
    spans = list(spans)
    index = 0
    while len(spans) > 1 and index < len(spans):
        start, end, _label = spans[index]
        if end - start >= _MIN_CS:
            index += 1
            continue
        if index + 1 < len(spans):
            _next_start, next_end, next_label = spans[index + 1]
            spans[index:index + 2] = [(start, next_end, next_label)]
        else:
            prev_start, _prev_end, prev_label = spans[index - 1]
            spans[index - 1:index + 1] = [(prev_start, end, prev_label)]
            index -= 1
    return spans


def _cuts(start: int, end: int, longest: int, bar: float, first_bar: float) -> list[int]:
    """Where to cut a span, in hundredths, so that no piece is longer than *longest*.

    Equal pieces, or cuts on bar lines when there are bars and they leave every
    piece within *longest* and no shorter than equal pieces would be allowed
    to be: a bar line that would leave a shot too short for a clip is not taken.
    """
    length = end - start
    fewest = max(1, -(-length // longest))
    even = [start + (length * part) // fewest for part in range(1, fewest)]
    if bar <= 0:
        return even
    shortest = min(_MIN_CS, length // fewest)
    for pieces in range(fewest, fewest + 4):
        cuts = [
            _cs(first_bar + round(((start + length * part / pieces) / 100 - first_bar) / bar) * bar)
            for part in range(1, pieces)
        ]
        sizes = [after - before for before, after in pairwise([start, *cuts, end])]
        if all(shortest <= size <= longest for size in sizes):
            return cuts
    return even


def plan_shots(
    duration_s: float,
    sections: Any,
    *,
    max_shot_s: float = DEFAULT_MAX_SHOT_S,
    bpm: float = 0.0,
    time_signature: int = 4,
    first_downbeat_s: float = 0.0,
) -> list[dict[str, Any]]:
    """Shots that follow a song's sections, each short enough to be one clip.

    A new section starts a new shot. A section longer than *max_shot_s* is cut
    into equal parts, or on bar lines when the tempo is given and they fit. A
    section too short for a clip joins its neighbour. The shots cover the song
    exactly, and none is longer than *max_shot_s*.

    Args:
        duration_s: The song's length in seconds.
        sections: ``[{start_s, end_s, label}]`` from Suno's audio-analysis; an
            empty list cuts the song evenly.
        max_shot_s: The longest a shot may be, 5 to 15 seconds.
        bpm, time_signature, first_downbeat_s: The tempo, the beats in a bar
            and the time of the first downbeat, to cut long sections on bar
            lines. Left at 0, they are cut evenly.

    Returns:
        ``[{"start_s", "duration_s", "section"}]`` in order.

    Raises:
        ValueError: a length, a longest shot or sections that cannot be used,
            or a plan of more than 40 shots.
    """
    if not _number(duration_s) or duration_s <= 0:
        raise ValueError(f"The song's length has to be a number of seconds, not {duration_s!r}")
    if duration_s < MIN_CLIP_S:
        raise ValueError(f"A music video needs a song of at least {MIN_CLIP_S} seconds")
    if not _number(max_shot_s) or not MIN_CLIP_S <= max_shot_s <= MAX_CLIP_S:
        raise ValueError(
            f"The longest shot has to be {MIN_CLIP_S} to {MAX_CLIP_S} seconds, not {max_shot_s!r}",
        )
    total = _cs(duration_s)
    longest = int(float(max_shot_s) * 100)
    bar = 0.0
    if _number(bpm) and bpm > 0 and _number(time_signature) and time_signature > 0:
        bar = float(time_signature) * 60.0 / float(bpm)
    first_bar = float(first_downbeat_s) if _number(first_downbeat_s) else 0.0

    edges: list[int] = [0]
    labels: list[str] = []
    for start, end, label in _merged(_spans(total, sections)):
        for cut in (*_cuts(start, end, longest, bar, first_bar), end):
            edges.append(cut)
            labels.append(label)

    shots = [
        {"start_s": before / 100, "duration_s": (after - before) / 100, "section": label}
        for (before, after), label in zip(pairwise(edges), labels, strict=True)
    ]
    if len(shots) > MAX_SHOTS:
        raise ValueError(
            f"That is {len(shots)} shots, and Suno plans at most {MAX_SHOTS}. Allow longer shots.",
        )
    return shots


def billed_seconds(shots: list[dict[str, Any]]) -> int:
    """The seconds Suno would charge for if every shot were a clip.

    A clip is charged by the whole second, rounded up (measured with a dry
    run). A clip is at least five seconds long, so a shorter shot is counted
    as five here; what Suno charges for one was not measured.
    """
    return sum(max(MIN_CLIP_S, math.ceil(float(shot["duration_s"]) - 1e-9)) for shot in shots)


def _named(entries: Any, kind: str) -> list[dict[str, Any]]:
    """Characters or sets as sequence-create takes them: a name and 1 to 3 images each."""
    if not isinstance(entries, list):
        raise ValueError(f"The {kind}s have to be a list of {{name, asset_ids, description}}")
    if len(entries) > MAX_NAMED:
        raise ValueError(f"A Sequence takes at most {MAX_NAMED} {kind}s, not {len(entries)}")
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"Not a {kind} with a name and asset_ids: {entry!r}")
        name = entry.get("name")
        name = name.strip() if isinstance(name, str) else ""
        assets = entry.get("asset_ids")
        if not name or len(name) > 60 or name in seen:
            raise ValueError(f"Every {kind} needs a name of its own, at most 60 characters long")
        if (
            not isinstance(assets, list) or not 1 <= len(assets) <= 3
            or not all(isinstance(asset, str) and asset.strip() for asset in assets)
        ):
            raise ValueError(f"The {kind} '{name}' needs 1 to 3 reference images (asset_ids)")
        seen.add(name)
        item: dict[str, Any] = {"name": name, "asset_ids": [asset.strip() for asset in assets]}
        description = entry.get("description")
        description = description.strip() if isinstance(description, str) else ""
        if len(description) > 500:
            raise ValueError(f"The {kind} '{name}' has a description longer than 500 characters")
        if description:
            item["description"] = description
        cleaned.append(item)
    return cleaned


def build_sequence_request(
    song_id: str,
    title: str,
    shots: Any,
    *,
    aspect: str = DEFAULT_ASPECT,
    style: Any = None,
    lyrics: bool = False,
    characters: Any = None,
    sets: Any = None,
) -> dict[str, Any]:
    """The arguments for Suno's ``sequence-create``.

    Args:
        song_id: The keeper's clip id.
        title: The Sequence's name on suno.com, which finds it again later.
        shots: ``[{duration_s, notes?, characters?, set?}]`` in the order they
            play; anything else in a shot is left out.
        aspect: 16:9 (the default), 1:1 or 9:16.
        style: The look as an object, such as ``{look, palette, rules}``.
        lyrics: Burn the words in as they are sung.
        characters, sets: ``[{name, asset_ids, description?}]``; a shot may
            cite them by name.

    Raises:
        ValueError: an argument Suno would refuse.
    """
    if not isinstance(song_id, str) or not _SONG_ID_RE.fullmatch(song_id):
        raise ValueError(f"'{song_id}' is not a song id from Suno")
    name = title.strip() if isinstance(title, str) else ""
    if not name:
        raise ValueError("The Sequence needs a title, which finds it again on suno.com")
    shape = lv.normal_shape(aspect or DEFAULT_ASPECT)
    if shape is None:
        raise ValueError(f"'{aspect}' is not a shape Suno makes; use 16:9, 1:1 or 9:16")
    if style is not None and not isinstance(style, dict):
        raise ValueError("The style has to be an object, such as {look, palette, rules}")
    cast = _named(characters, "character") if characters else []
    places = _named(sets, "set") if sets else []
    cast_names = {entry["name"] for entry in cast}
    place_names = {entry["name"] for entry in places}

    if not isinstance(shots, list) or not shots:
        raise ValueError("The video needs at least one shot")
    if len(shots) > MAX_SHOTS:
        raise ValueError(f"That is {len(shots)} shots, and Suno plans at most {MAX_SHOTS}")
    cleaned: list[dict[str, Any]] = []
    for number, shot in enumerate(shots, start=1):
        length = shot.get("duration_s") if isinstance(shot, dict) else None
        if not _number(length) or not 0 < length <= MAX_CLIP_S:
            raise ValueError(
                f"Shot {number} needs a duration_s of up to {MAX_CLIP_S} seconds, not {length!r}",
            )
        item: dict[str, Any] = {"duration_s": length}
        notes = str(shot.get("notes") or "").strip()
        if len(notes) > MAX_NOTES:
            raise ValueError(f"Shot {number}'s notes are longer than {MAX_NOTES} characters")
        if notes:
            item["notes"] = notes
        cited = shot.get("characters")
        if cited:
            if (
                not isinstance(cited, list)
                or not all(isinstance(who, str) and who in cast_names for who in cited)
            ):
                raise ValueError(
                    f"Shot {number} cites a character that is not in the cast: {cited!r}",
                )
            item["characters"] = list(cited)
        place = shot.get("set")
        if place:
            if not isinstance(place, str) or place not in place_names:
                raise ValueError(f"Shot {number} cites a set that is not among the sets: {place!r}")
            item["set"] = place
        cleaned.append(item)

    kept = json.dumps(
        [style or {}, cast, places, [shot.get("notes", "") for shot in cleaned]],
        ensure_ascii=False,
    ).encode("utf-8")
    if len(kept) > MAX_KEPT_BYTES:
        raise ValueError(
            f"The style, the cast, the sets and the shot notes come to {len(kept) // 1024} KB, and "
            "a Sequence keeps at most 32 KB. Shorten the notes.",
        )

    request: dict[str, Any] = {
        "title": name, "song_id": song_id, "aspect": shape, "lyrics": bool(lyrics),
    }
    if style:
        request["style"] = style
    if cast:
        request["characters"] = cast
    if places:
        request["sets"] = places
    request["shots"] = cleaned
    return request
