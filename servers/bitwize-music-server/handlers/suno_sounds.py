"""Sounds from Suno — the request for a sound effect, a one-shot or a loop.

Suno makes short sounds from a description (the ``sounds-create`` tool, as
suno.com's Sounds does): rain for an intro, a riser, a drum loop. This tool
writes that request for an album, fits a loop to one of its tracks when asked,
and says where the files belong. The plugin's server never talks to Suno; the
skill sends it.

Measured: one call made two sounds of about 20 seconds for 1 song
credit each. The two can differ in kind — for "soft rain on a window" one was
rain and the other had a piano melody in it — so both need hearing. A loop
asked for at 96 BPM in G came back at 96 BPM; the key was not confirmed.
sounds-create takes no workspace, so the sounds are filed afterwards.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from handlers._shared import _extract_markdown_section, _find_album_or_error, _safe_json
from handlers.generation import (
    _album_workspace,
    _load_track,
    _problem,
    _section_code,
    album_audio_dir,
)
from handlers.take_check import asked_bpm

logger = logging.getLogger(__name__)

# Limits from the Suno MCP `sounds-create` schema.
_MAX_DESCRIPTION = 500
_MAX_TITLE = 256
_MIN_TEMPO, _MAX_TEMPO = 1, 300
_SOUNDS_PER_CALL = 2
_CREDITS_PER_SOUND = 1
_FILE_SLUG_LENGTH = 48

# A key as a Style Box names it. The note letter is upper case, so "a major label"
# is not a key; "key of D" needs no mode, "A minor" does.
_NOTE = r"([A-G])\s?(#|♯|b|♭)?"
_KEY_OF_RE = re.compile(
    r"\b(?i:key)(?:\s+(?i:of)|:)\s*" + _NOTE + r"(?:\s*(?i:(major|minor|maj|min|m)))?\b"
)
_KEY_MODE_RE = re.compile(r"\b" + _NOTE + r"\s*(?i:(major|minor))\b")
# sounds-create spells every accidental as a sharp.
_AS_SHARP = {
    "Cb": "B", "Db": "C#", "Eb": "D#", "Fb": "E", "Gb": "F#", "Ab": "G#", "Bb": "A#",
    "E#": "F", "B#": "C",
}


def _file_slug(text: str) -> str:
    """A short file-name stem for a sound, from its title or description."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:_FILE_SLUG_LENGTH].strip("-") or "sound"


def asked_key(text: str, style: str | None) -> str | None:
    """The key a track asks for, as sounds-create spells it (``G``, ``A#m``), or None.

    Read from the Style Box first, then the Musical Direction section.
    """
    for source in (style or "", _extract_markdown_section(text, "Musical Direction") or ""):
        match = _KEY_OF_RE.search(source) or _KEY_MODE_RE.search(source)
        if not match:
            continue
        accidental = {"♯": "#", "♭": "b"}.get(match.group(2) or "", match.group(2) or "")
        note = match.group(1) + accidental
        note = _AS_SHARP.get(note, note)
        mode = (match.group(3) or "").lower()
        return note + ("m" if mode in ("minor", "min", "m") else "")
    return None


async def get_sound_request(
    album_slug: str,
    description: str,
    loop: bool = False,
    fit_track: str = "",
    title: str = "",
) -> str:
    """Build the Suno request for a sound effect, a one-shot or a loop for an album.

    Send the returned request to sounds-create with an idempotency key. One
    call makes two sounds of about 20 seconds and spends 1 song credit each
    (measured), so show the cost and get a go-ahead first. The two sounds can
    differ in kind, so let the user hear both. sounds-create takes no
    workspace: when workspace is not null, file the two with
    workspaces-update-clips. A sound is saved under the album's audio folder
    in sounds/, which the mastering tools never read.

    Args:
        album_slug: Album slug
        description: What the sound is ("rain on a tin roof", "boom bap
            drums"), up to 500 characters
        loop: True for a seamless loop, False for a one-shot
        fit_track: A track slug or number: the sound is given that track's
            tempo and key, read from its Style Box. For musical material (a
            drum loop, a riser); leave empty for an effect or an ambience
        title: A name for the sound; Suno uses the description when empty

    Returns:
        JSON with found, album_slug, supported (false when a blocking problem
        means nothing should be sent), tool ("sounds-create"), request
        (description, loop, and tempo, key and title when set), fit
        ({track_slug, tempo, key} or null), sounds (2 per call), credits (2 per
        call), workspace ({id, name} to file the sounds in, or null), save
        ({dir, files}: where the two sounds belong if they are downloaded) and
        problems ([{code, severity: blocking|warning, detail}])
    """
    album_slug, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    problems: list[dict[str, str]] = []
    description = " ".join(description.split())
    title = " ".join(title.split())
    if not description:
        problems.append(_problem(
            "needs_description", "blocking",
            "Say what the sound is — for example \"rain on a tin roof\"",
        ))
    elif len(description) > _MAX_DESCRIPTION:
        problems.append(_problem(
            "description_too_long", "blocking",
            f"The description is {len(description)} characters; Suno accepts {_MAX_DESCRIPTION}",
        ))
    if len(title) > _MAX_TITLE:
        problems.append(_problem(
            "title_too_long", "blocking",
            f"The title is {len(title)} characters; Suno accepts {_MAX_TITLE}",
        ))

    fit: dict[str, Any] | None = None
    if fit_track.strip():
        ctx, error = _load_track(album_slug, fit_track)
        if error:
            return error
        assert ctx is not None
        style = _section_code(ctx["text"], "Style Box")
        bpm = asked_bpm(ctx["text"], style)
        tempo = min(max(round(sum(bpm) / 2), _MIN_TEMPO), _MAX_TEMPO) if bpm else None
        fit = {
            "track_slug": ctx["track_slug"],
            "tempo": tempo,
            "key": asked_key(ctx["text"], style),
        }
        if fit["tempo"] is None and fit["key"] is None:
            problems.append(_problem(
                "nothing_to_fit", "warning",
                f"{ctx['track_slug']} names no tempo and no key in its Style Box or Musical "
                "Direction, so the sound is not fitted to it",
            ))

    audio_dir, error = album_audio_dir(album_slug, album)
    if error:
        return error
    assert audio_dir is not None
    sounds_dir = audio_dir / "sounds"
    stem = _file_slug(title or description)

    supported = not any(p["severity"] == "blocking" for p in problems)
    request: dict[str, Any] = {}
    if supported:
        request = {"description": description, "loop": bool(loop)}
        if fit and fit["tempo"] is not None:
            request["tempo"] = fit["tempo"]
        if fit and fit["key"] is not None:
            request["key"] = fit["key"]
        if title:
            request["title"] = title

    return _safe_json({
        "found": True,
        "album_slug": album_slug,
        "supported": supported,
        "tool": "sounds-create",
        "request": request,
        "fit": fit,
        "sounds": _SOUNDS_PER_CALL,
        "credits": _SOUNDS_PER_CALL * _CREDITS_PER_SOUND,
        "workspace": _album_workspace(album),
        "save": {
            "dir": str(sounds_dir),
            "files": [
                str(sounds_dir / f"{stem}-{number}.wav")
                for number in range(1, _SOUNDS_PER_CALL + 1)
            ],
        },
        "problems": problems,
    })


def register(mcp: Any) -> None:
    """Register the sound request with the MCP server."""
    mcp.tool()(get_sound_request)
