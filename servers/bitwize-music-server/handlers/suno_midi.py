"""MIDI from Suno — the keeper to transcribe and where its .mid file goes.

Suno can transcribe one of the user's own songs to a multi-track MIDI file
(the `audio-midi` tool, as suno.com's Studio does). The plugin's server never
talks to Suno; this tool tells a skill which clip to ask for and where to save
the file, next to the AnthemScore output the sheet-music tools already use.
"""

from __future__ import annotations

from typing import Any

from handlers._shared import _safe_json
from handlers.generation import _load_track, album_audio_dir, keeper_clip

# Suno charges 10 song credits for a transcription; a stem made with Get Stems is free,
# and a song already transcribed is served again at no cost (Suno's tool description).
_MIDI_CREDITS = 10


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


def register(mcp: Any) -> None:
    """Register the Suno MIDI plan with the MCP server."""
    mcp.tool()(get_suno_midi_plan)
