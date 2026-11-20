"""A music video for a track — laid out and generated on Suno; planned and saved here.

Suno's Sequences lay a music video out as a timeline of shots over a song.
Each shot gets a keyframe, the cut can be exported as an animatic to judge the
pacing, and then shots are turned into generated clips. The plugin's server
never talks to Suno, so the music-video skill calls those tools. These tools
do the rest: plan the shots on the song's sections, build the request for
``sequence-create``, and save the animatic and the finished video beside the
album's audio.

Laying the video out and exporting it are free (measured). Keyframes and clips
spend Visuals credits, and clips are charged by the whole second, so the skill
prices every paid step with ``dry_run: true`` and waits for a go-ahead.
"""

from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path
from typing import Any

from handlers._shared import _safe_json
from handlers.generation import (
    _instrumental_state,
    _load_track,
    _problem,
    album_audio_dir,
    keeper_clip,
)
from handlers.lyric_video import fetch_and_finish
from handlers.playback import _local_stages
from tools.promotion import lyric_video as lv
from tools.promotion import music_video as mv

logger = logging.getLogger(__name__)

# Where music videos live, beside the album's audio.
VIDEOS_DIR = "music_videos"
KINDS = ("video", "animatic")


def _paths(audio_dir: Path, track_slug: str, shape: str) -> dict[str, Path]:
    stem = f"{track_slug}-{lv.shape_slug(shape)}"
    folder = audio_dir / VIDEOS_DIR
    return {"video": folder / f"{stem}.mp4", "animatic": folder / f"{stem}-animatic.mp4"}


def _shape_or_error(shape: str) -> tuple[str | None, str | None]:
    normal = lv.normal_shape(shape or mv.DEFAULT_ASPECT)
    if normal is None:
        return None, _safe_json({
            "found": True,
            "error": f"'{shape}' is not a shape Suno makes; use 16:9, 1:1 or 9:16",
        })
    return normal, None


async def get_music_video_plan(
    album_slug: str,
    track_slug: str,
    shape: str = "16:9",
    shots: list[dict[str, Any]] | None = None,
    style: dict[str, Any] | None = None,
    lyrics: bool = False,
    characters: list[dict[str, Any]] | None = None,
    sets: list[dict[str, Any]] | None = None,
) -> str:
    """Say how a track's music video will be made, and build the request for the Sequence. Free.

    A Sequence on Suno is a timeline of shots over the track's keeper.
    Read-only, and it never calls Suno: the calling skill does. Call it first
    with the album and the track, then again with the shots the user approved
    to get `request`, the arguments for Suno's sequence-create.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        shape: 16:9 (the default), 1:1 or 9:16
        shots: The shots in the order they play, each {duration_s, notes,
            characters?, set?}: the lengths from plan_music_video_shots, the
            notes saying what each shot shows and how the camera moves
        style: The look, as an object such as {look, palette, rules}
        lyrics: Burn the words in as they are sung
        characters: The cast, each {name, asset_ids (1 to 3 images on Suno),
            description?}, for shots to cite by name
        sets: The places, in the same form

    Returns:
        JSON with {found, album_slug, track_slug, title, shape, song:
        {clip_id, source} | null, sequence_title, master: {path} | null,
        output: {path, exists}, animatic: {path, exists}, request (the
        arguments for sequence-create, once shots are given, else null),
        ffmpeg, ready, problems: [{code, severity: blocking|warning, detail}]}.
        `ready` is false while any problem is blocking
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    normal, error = _shape_or_error(shape)
    if error:
        return error
    assert normal is not None
    audio_dir, error = album_audio_dir(ctx["album_slug"], ctx["album"])
    if error:
        return error
    assert audio_dir is not None

    title = str(ctx["track"].get("title", ctx["track_slug"]))
    sequence_title = f"{title} (music video)"
    paths = _paths(audio_dir, ctx["track_slug"], normal)
    problems: list[dict[str, str]] = []

    clip_id, source, _link, problem = keeper_clip(ctx["text"])
    if problem:
        problems.append(problem)
    instrumental, _ = _instrumental_state(ctx["text"])
    if instrumental and lyrics:
        problems.append(_problem(
            "instrumental", "blocking",
            "The track is instrumental, so there are no words to burn in. Leave lyrics off",
        ))

    master = _local_stages(ctx["album_slug"], ctx["album"], ctx["track_slug"])["mastered"]
    if not master:
        problems.append(_problem(
            "no_master", "warning",
            "The track has no mastered file, so the video will carry Suno's own audio. "
            "Master the track first to have the master under the picture",
        ))
    have_ffmpeg = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    if not have_ffmpeg:
        problems.append(_problem(
            "ffmpeg_missing", "warning",
            "ffmpeg is not installed, so the video is saved as Suno makes it: unchecked, and "
            "with Suno's own audio",
        ))
    if paths["video"].is_file():
        problems.append(_problem(
            "video_exists", "warning",
            f"{paths['video'].name} is already there. Saving a new one needs replace=true",
        ))
    if paths["animatic"].is_file():
        problems.append(_problem(
            "animatic_exists", "warning",
            f"{paths['animatic'].name} is already there. A new animatic takes its place",
        ))

    request: dict[str, Any] | None = None
    if shots is not None:
        try:
            built = mv.build_sequence_request(
                clip_id or _NO_SONG, sequence_title, shots, aspect=normal, style=style,
                lyrics=lyrics, characters=characters, sets=sets,
            )
            if clip_id and not any(p["severity"] == "blocking" for p in problems):
                request = built
        except ValueError as exc:
            problems.append(_problem("request_invalid", "blocking", str(exc)))

    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": title,
        "shape": normal,
        "song": {"clip_id": clip_id, "source": source} if clip_id else None,
        "sequence_title": sequence_title,
        "master": {"path": master} if master else None,
        "output": {"path": str(paths["video"]), "exists": paths["video"].is_file()},
        "animatic": {"path": str(paths["animatic"]), "exists": paths["animatic"].is_file()},
        "request": request,
        "ffmpeg": have_ffmpeg,
        "ready": not any(p["severity"] == "blocking" for p in problems),
        "problems": problems,
    })


# Stands in for the song while a track has no keeper, so the shots are still judged.
_NO_SONG = "00000000-0000-0000-0000-000000000000"


async def plan_music_video_shots(
    duration_s: float,
    sections: list[dict[str, Any]],
    max_shot_s: float = mv.DEFAULT_MAX_SHOT_S,
    bpm: float = 0.0,
    time_signature: int = 4,
    first_downbeat_s: float = 0.0,
    credits_per_second: float = 0.0,
) -> str:
    """Lay a song out as shots for a music video, and say what clips would be charged for. Free.

    A new section starts a new shot; a section longer than max_shot_s is cut
    into equal parts, or on bar lines when the tempo is given and they fit; a
    section too short for a clip joins its neighbour. The shots cover the song
    exactly, and none is longer than max_shot_s. Nothing is sent anywhere.

    Suno charges a clip by the whole second, rounded up (measured with a dry
    run). `billed_seconds` is what the plan would be charged for if every shot
    became a clip.

    Args:
        duration_s: The song's length in seconds, from audio-retrieve
        sections: [{start_s, end_s, label}] from Suno's audio-analysis; an
            empty list cuts the song evenly
        max_shot_s: The longest a shot may be, 5 to 15 seconds
        bpm: The tempo from audio-analysis, to cut long sections on bar lines
        time_signature: Beats in a bar, from audio-analysis
        first_downbeat_s: The time of the first beat whose bar_position is 1
        credits_per_second: A video model's price from visuals-models, for an
            estimate. The dry run of sequence-generate gives the real price

    Returns:
        JSON with {shots: [{number, start_s, duration_s, section, billed_s}],
        shot_count, total_s, billed_seconds, and with credits_per_second also
        estimate_credits and estimate_note} or {error}
    """
    try:
        shots = mv.plan_shots(
            duration_s, sections, max_shot_s=max_shot_s, bpm=bpm,
            time_signature=time_signature, first_downbeat_s=first_downbeat_s,
        )
    except ValueError as exc:
        return _safe_json({"error": str(exc)})
    result: dict[str, Any] = {
        "shots": [
            {"number": number, **shot, "billed_s": mv.billed_seconds([shot])}
            for number, shot in enumerate(shots, start=1)
        ],
        "shot_count": len(shots),
        "total_s": round(sum(shot["duration_s"] for shot in shots), 2),
        "billed_seconds": mv.billed_seconds(shots),
    }
    if (
        isinstance(credits_per_second, (int, float)) and not isinstance(credits_per_second, bool)
        and math.isfinite(credits_per_second) and credits_per_second > 0
    ):
        result["estimate_credits"] = round(result["billed_seconds"] * credits_per_second)
        result["estimate_note"] = (
            "If every shot became a clip at that price. An estimate only: the dry run of "
            "sequence-generate gives the price that counts."
        )
    return _safe_json(result)


async def save_music_video(
    album_slug: str,
    track_slug: str,
    link: str,
    shape: str = "16:9",
    kind: str = "video",
    master_audio: bool = True,
    replace: bool = False,
) -> str:
    """Save a music video Suno exported, the animatic or the finished cut, beside the album's audio.

    Pass the `url` Suno's visuals-download gave for the export. The file is
    fetched (only an https link on Suno's hosts or its download bucket),
    checked to be a whole video, and saved under the album's music_videos/.

    kind "animatic" is the draft made of keyframes: saved as
    <track>-<shape>-animatic.mp4 with Suno's own audio, and a new one takes
    the place of the one before. kind "video" is the finished cut: saved as
    <track>-<shape>.mp4, with the mastered audio under the picture when the
    track has a master of the same length, and kept unless replace is true.
    Free: nothing is generated here.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        link: The `url` from visuals-download
        shape: The shape the video was made in: 16:9 (the default), 1:1 or 9:16
        kind: "video" (the default) or "animatic"
        master_audio: Put the mastered file under a finished video when there is one
        replace: Overwrite a finished video that is already there

    Returns:
        JSON with {found, saved: true, kind, path, shape, width, height,
        duration_s, bytes, audio: "master" | "suno", audio_note} or {found,
        saved: false, error}
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    normal, error = _shape_or_error(shape)
    if error:
        return error
    assert normal is not None
    if kind not in KINDS:
        return _safe_json({
            "found": True, "error": f"'{kind}' is not a kind of export; use video or animatic",
        })
    audio_dir, error = album_audio_dir(ctx["album_slug"], ctx["album"])
    if error:
        return error
    assert audio_dir is not None

    def refused(message: str) -> str:
        return _safe_json({
            "found": True, "album_slug": ctx["album_slug"], "track_slug": ctx["track_slug"],
            "saved": False, "error": message,
        })

    output = _paths(audio_dir, ctx["track_slug"], normal)[kind]
    if kind == "video" and output.exists() and not replace:
        return refused(
            f"{output.name} is already there. Nothing was changed. Ask the user, then pass "
            "replace=true to overwrite it."
        )

    master: Path | None = None
    if kind == "video" and master_audio:
        found = _local_stages(ctx["album_slug"], ctx["album"], ctx["track_slug"])["mastered"]
        master = Path(found) if found else None

    info, problem = await fetch_and_finish(
        link, output, lambda part, made: lv.finish(part, made, master),
    )
    if info is None:
        return refused(problem or "Saving the video failed.")

    logger.info("Saved a music video (%s) for '%s' / '%s'", kind, ctx["album_slug"], ctx["track_slug"])
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "saved": True,
        "kind": kind,
        "shape": normal,
        **info,
    })


def register(mcp: Any) -> None:
    """Register the music-video tools with the MCP server."""
    mcp.tool()(get_music_video_plan)
    mcp.tool()(plan_music_video_shots)
    mcp.tool()(save_music_video)
