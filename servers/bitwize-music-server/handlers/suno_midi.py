"""MIDI to and from Suno — the keeper to transcribe, and the score to play.

Suno can transcribe one of the user's own songs to a multi-track MIDI file
(the `audio-midi` tool, as suno.com's Studio does), and it can make a song
that plays a MIDI score the user uploads. The plugin's server never talks to
Suno; these tools tell a skill which clip to ask for and where to save the
file — next to the AnthemScore output the sheet-music tools already use — and
check a MIDI file before it is uploaded.

Measured: a stem's transcription was free and came back at once as
a format-1 file; uploaded again as a score (midi-upload-create, a multipart
POST, midi-upload-complete) and sent to audio-create with a description, it
made two instrumentals for 10 song credits on v6-wild.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from handlers._shared import _safe_json
from handlers.generation import (
    _MIDI_MODEL,
    _instrumental_state,
    _load_track,
    _problem,
    album_audio_dir,
    keeper_clip,
)

# Suno charges 10 song credits for a transcription; a stem made with Get Stems is free,
# and a song already transcribed is served again at no cost (Suno's tool description).
_MIDI_CREDITS = 10
# A score: up to 256 KB (midi-upload-create), and one audio-create call for two takes.
_MAX_SCORE_BYTES = 262144
_SCORE_CREDITS = 10
_MIDI_HEADER = struct.Struct(">4sIHHH")  # "MThd", header length 6, format, tracks, division


async def get_suno_midi_plan(album_slug: str, track_slug: str) -> str:
    """Which Suno clip to transcribe to MIDI for a track, and where the file goes.

    /bitwize-music:sheet-music-publisher uses this to fetch a multi-track MIDI
    of the approved take through Suno's audio-midi tool. That call spends song
    credits (10 per song, none for a stem or a song transcribed before; it
    needs a Suno plan with Studio), so state the cost and get a go-ahead first.
    Then call audio-midi(id) until its status is ok and save its url to
    midi.path.

    Args:
        album_slug: Album slug
        track_slug: Track slug or number

    Returns:
        JSON with found, album_slug, track_slug, title, clip_id (the keeper, or
        null), clip_source, song_url, midi ({path, existing}), credits (what a
        first transcription costs) and problems ([{code, severity, detail}] —
        no_keeper, keeper_ambiguous or legacy_link when there is no clip id)
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None

    clip_id, clip_source, link_url, problem = keeper_clip(ctx["text"])
    audio_dir, error = album_audio_dir(ctx["album_slug"], ctx["album"])
    if error:
        return error
    assert audio_dir is not None

    target = audio_dir / "sheet-music" / "source" / f"{ctx['track_slug']}.mid"
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": ctx["track"].get("title", ctx["track_slug"]),
        "clip_id": clip_id,
        "clip_source": clip_source,
        "song_url": f"https://suno.com/song/{clip_id}" if clip_id else link_url,
        "midi": {"path": str(target), "existing": target.is_file()},
        "credits": _MIDI_CREDITS,
        "problems": [problem] if problem else [],
    })


def _read_score(path: Path) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """A MIDI file's size and header: ``(facts, None)`` or ``(None, problem)``."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            head = handle.read(_MIDI_HEADER.size)
    except OSError as e:
        return None, _problem("midi_file_not_found", "blocking", f"Cannot read {path}: {e}")
    if len(head) < _MIDI_HEADER.size:
        return None, _problem(
            "not_a_midi_file", "blocking", f"{path.name} is not a MIDI file — it is too short",
        )
    magic, length, fmt, tracks, division = _MIDI_HEADER.unpack(head)
    if magic != b"MThd" or length != 6 or fmt > 2 or tracks < 1:
        return None, _problem(
            "not_a_midi_file", "blocking",
            f"{path.name} is not a MIDI file — it does not start with a MIDI header",
        )
    if size > _MAX_SCORE_BYTES:
        return None, _problem(
            "midi_too_large", "blocking",
            f"{path.name} is {size:,} bytes; Suno accepts a score up to {_MAX_SCORE_BYTES:,} "
            "(256 KB) — export fewer tracks or a shorter passage",
        )
    return {"bytes": size, "format": fmt, "tracks": tracks, "division": division}, None


async def get_midi_score_plan(album_slug: str, track_slug: str, midi_path: str = "") -> str:
    """Check the MIDI file a track is to be made from, before it is sent to Suno.

    /bitwize-music:generate uses this for a track made from a score: Suno
    plays an uploaded MIDI file as the song's melody. With no path given, the
    track's own file is used — the one MIDI From Suno saves under
    sheet-music/source/ — so a transcription can be edited and sent back.
    Then upload it (midi-upload-create, a multipart POST of the file,
    midi-upload-complete) and pass the upload's id to get_generation_request
    as midi_upload_id. The song costs credits like any other (10, measured).

    Args:
        album_slug: Album slug
        track_slug: Track slug or number
        midi_path: The .mid or .midi file to play; empty uses the track's own
            under the album's sheet-music/source/ folder

    Returns:
        JSON with found, album_slug, track_slug, title, supported (false when
        there is no usable file), midi ({path, source: "given" or
        "sheet-music", bytes, format, tracks, division}, or null), max_bytes
        (Suno's limit), model ("v6-wild", the only model that plays a score),
        credits (what the song costs), sketch (true for a vocal track: Suno
        takes no lyrics with a score, so the score makes an instrumental sketch
        to cover) and problems ([{code, severity, detail}] — no_midi_file,
        midi_file_not_found, not_a_midi_file or midi_too_large)
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None

    audio_dir, error = album_audio_dir(ctx["album_slug"], ctx["album"])
    if error:
        return error
    assert audio_dir is not None

    problems: list[dict[str, str]] = []
    midi: dict[str, Any] | None = None
    given = midi_path.strip()
    own = audio_dir / "sheet-music" / "source" / f"{ctx['track_slug']}.mid"
    path = Path(given).expanduser() if given else own
    if not path.is_file():
        problems.append(
            _problem("midi_file_not_found", "blocking", f"No file at {path}") if given
            else _problem(
                "no_midi_file", "blocking",
                f"No MIDI file given, and the track has none of its own at {own} — pass a "
                ".mid file, or make the track's with /bitwize-music:sheet-music-publisher "
                "(MIDI From Suno)",
            )
        )
    else:
        facts, problem = _read_score(path)
        if problem:
            problems.append(problem)
        elif facts:
            midi = {"path": str(path), "source": "given" if given else "sheet-music", **facts}

    instrumental, _ = _instrumental_state(ctx["text"])
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": ctx["track"].get("title", ctx["track_slug"]),
        "supported": midi is not None,
        "midi": midi,
        "max_bytes": _MAX_SCORE_BYTES,
        "model": _MIDI_MODEL,
        "credits": _SCORE_CREDITS,
        "sketch": not instrumental,
        "problems": problems,
    })


def register(mcp: Any) -> None:
    """Register the Suno MIDI plans with the MCP server."""
    mcp.tool()(get_suno_midi_plan)
    mcp.tool()(get_midi_score_plan)
