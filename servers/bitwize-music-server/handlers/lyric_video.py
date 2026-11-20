"""A lyric video for a track — Suno renders it; these tools plan it and save it.

Suno's ``video-assemble`` holds stills over a song and burns the words in as
they are sung. The plugin's server never talks to Suno, so the lyric-video
skill calls that tool. These tools do the rest: say what will be made and build
the request, write the picture Suno is given from the album's cover, and save
the MP4 beside the album's audio with the mastered audio under it.

Measured on a 55-second song: assembling, waiting and downloading spent no
credit of any kind, and Suno rendered the video in under a minute. Each call
leaves a Sequence in the user's Suno library.
"""

from __future__ import annotations

import asyncio
import contextlib
import http.client
import logging
import re
import secrets
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from handlers._shared import _find_album_or_error, _safe_json
from handlers.generation import (
    _instrumental_state,
    _load_track,
    _problem,
    album_audio_dir,
    keeper_clip,
)
from handlers.playback import _local_stages
from tools.promotion import lyric_video as lv

logger = logging.getLogger(__name__)

# Where lyric videos live, beside the album's audio, and the pictures made for Suno.
VIDEOS_DIR = "lyric_videos"
STILLS_DIR = "stills"

# The cover in the audio folder: import_album_art writes album.png; older albums
# have album.jpg. The album folder keeps its own copy as album-art.
_AUDIO_COVERS = ("album.png", "album.jpg", "album.jpeg")
_CONTENT_COVERS = ("album-art.png", "album-art.jpg", "album-art.jpeg")

# An image on Suno: an asset id from image-create or an upload, or a preset's ref.
_ASSET_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:-]{3,79}")


def _cover(audio_dir: Path, album: dict[str, Any]) -> Path | None:
    """The album's cover: the one beside the audio, else the album folder's copy."""
    content_dir = Path(str(album.get("path") or ""))
    candidates = [audio_dir / name for name in _AUDIO_COVERS]
    if album.get("path"):
        candidates += [content_dir / name for name in _CONTENT_COVERS]
    return next((path for path in candidates if path.is_file()), None)


def _paths(audio_dir: Path, album_slug: str, track_slug: str, shape: str) -> dict[str, Path]:
    videos = audio_dir / VIDEOS_DIR
    slug = lv.shape_slug(shape)
    return {
        "videos": videos,
        "output": videos / f"{track_slug}-{slug}.mp4",
        "still": videos / STILLS_DIR / f"{album_slug}-{slug}.jpg",
    }


def _shape_or_error(shape: str) -> tuple[str | None, str | None]:
    normal = lv.normal_shape(shape)
    if normal is None:
        return None, _safe_json({
            "found": True,
            "error": f"'{shape}' is not a shape Suno makes; use 16:9, 1:1 or 9:16",
        })
    return normal, None


async def fetch_and_finish(
    link: str, output: Path, finish: Callable[[Path, Path], dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch a Suno download link and turn it into the file at *output*.

    The download lands beside *output* under a name of its own, *finish* turns
    it into a second file, and only a finished file takes *output*'s place: an
    earlier file there survives anything that goes wrong, and two saves at once
    never write to the same working file. Neither working file is left behind.

    Args:
        link: The `url` Suno's visuals-download gave.
        output: Where the finished file goes.
        finish: ``finish(downloaded, dest)`` checks the download, writes *dest*
            and returns what it holds.

    Returns:
        ``(info, None)``, or ``(None, message)`` when nothing was saved.
    """
    token = secrets.token_hex(4)
    part = output.with_name(f"{output.name}.{token}.part")
    made = output.with_name(f"{output.name}.{token}.new")
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, lv.download_video, link, part)
        info = await loop.run_in_executor(None, finish, part, made)
        made.replace(output)
    except (ValueError, OSError, http.client.HTTPException) as exc:
        return None, str(exc)
    except Exception as exc:  # whatever a library raises, the caller gets an answer
        logger.warning("Saving a video from Suno failed: %s", exc)
        return None, f"Saving the video failed: {exc}"
    finally:
        for leftover in (part, made):
            with contextlib.suppress(OSError):
                leftover.unlink(missing_ok=True)
    return {**info, "path": str(output)}, None


async def get_lyric_video_plan(
    album_slug: str,
    track_slug: str,
    shape: str = "16:9",
    asset_id: str = "",
    duration_s: float = 0.0,
) -> str:
    """Say how a track's lyric video will be made, and build the request. Free.

    Suno's video-assemble holds the album's cover under the track's keeper and
    burns the words in as they are sung. Read-only, and it never calls Suno:
    the calling skill does. Call it first with the album and the track, then
    again with asset_id and duration_s once both are known, to get `request`.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        shape: 16:9 (the default), 1:1 or 9:16
        asset_id: The image on Suno to hold under the words: the id
            visuals-upload-complete gave for the uploaded still, or one from
            image-create
        duration_s: The keeper's length in seconds, from audio-retrieve's
            metadata.duration

    Returns:
        JSON with {found, album_slug, track_slug, title, shape, song:
        {clip_id, source} | null, cover (the album's cover file, or null),
        still: {path} (where prepare_lyric_video_still writes the picture for
        Suno), master: {path} | null, output: {path, exists}, request (the
        arguments for video-assemble, once asset_id and duration_s are given,
        else null), ffmpeg (whether ffmpeg and ffprobe are installed), ready,
        problems: [{code, severity: blocking|warning, detail}]}. `ready` is
        false while any problem is blocking
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

    text: str = ctx["text"]
    paths = _paths(audio_dir, ctx["album_slug"], ctx["track_slug"], normal)
    problems: list[dict[str, str]] = []

    clip_id, source, _link, problem = keeper_clip(text)
    if problem:
        problems.append(problem)
    instrumental, _ = _instrumental_state(text)
    if instrumental:
        problems.append(_problem(
            "instrumental", "blocking",
            "The track is instrumental, so there are no words for a lyric video to show",
        ))

    asset = asset_id.strip()
    cover = _cover(audio_dir, ctx["album"])
    if cover is None and not asset:
        problems.append(_problem(
            "no_cover", "blocking",
            "The album has no cover to hold under the words. File one with "
            "/bitwize-music:import-art or make it with /bitwize-music:album-art-director, or "
            "pass asset_id for an image that is already on Suno",
        ))

    master = _local_stages(ctx["album_slug"], ctx["album"], ctx["track_slug"])["mastered"]
    if not master:
        problems.append(_problem(
            "no_master", "warning",
            "The track has no mastered file, so the video will carry Suno's own audio. "
            "Master the track first to have the master under the words",
        ))

    have_ffmpeg = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    if not have_ffmpeg:
        problems.append(_problem(
            "ffmpeg_missing", "warning",
            "ffmpeg is not installed, so the video is saved as Suno makes it: unchecked, and "
            "with Suno's own audio",
        ))
    if paths["output"].is_file():
        problems.append(_problem(
            "video_exists", "warning",
            f"{paths['output'].name} is already there. Saving a new one needs replace=true",
        ))

    request: dict[str, Any] | None = None
    try:
        if asset and not _ASSET_ID_RE.fullmatch(asset):
            raise ValueError(f"'{asset}' is not an asset id from Suno")
        if clip_id and asset and duration_s:
            request = lv.build_request(clip_id, asset, duration_s, normal)
    except ValueError as exc:
        problems.append(_problem("request_invalid", "blocking", str(exc)))

    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": ctx["track"].get("title", ctx["track_slug"]),
        "shape": normal,
        "song": {"clip_id": clip_id, "source": source} if clip_id else None,
        "cover": str(cover) if cover else None,
        "still": {"path": str(paths["still"])},
        "master": {"path": master} if master else None,
        "output": {"path": str(paths["output"]), "exists": paths["output"].is_file()},
        "request": request,
        "ffmpeg": have_ffmpeg,
        "ready": not any(p["severity"] == "blocking" for p in problems),
        "problems": problems,
    })


async def prepare_lyric_video_still(album_slug: str, shape: str = "16:9") -> str:
    """Write the picture Suno holds under a lyric video's words, from the album's cover.

    The whole cover sits in the middle of a frame of the video's shape; where
    the frame is wider or taller, the space beside it is the cover again,
    blurred and darkened. Saved as a JPEG under the album's
    lyric_videos/stills/, small enough for Suno's upload. One still serves
    every track of the album. Free; nothing is sent anywhere.

    Upload it with Suno's visuals-upload-create and visuals-upload-complete,
    then pass the asset id to get_lyric_video_plan.

    Args:
        album_slug: Album slug (e.g., "my-album")
        shape: 16:9 (the default), 1:1 or 9:16

    Returns:
        JSON with {found, album_slug, shape, cover, still: {path, width,
        height, bytes, content_type}} or {found, error}
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None
    normal, error = _shape_or_error(shape)
    if error:
        return error
    assert normal is not None
    audio_dir, error = album_audio_dir(normalized, album)
    if error:
        return error
    assert audio_dir is not None

    cover = _cover(audio_dir, album)
    if cover is None:
        return _safe_json({
            "found": True, "album_slug": normalized,
            "error": "The album has no cover yet. File one with /bitwize-music:import-art or "
                     "make it with /bitwize-music:album-art-director.",
        })
    dest = _paths(audio_dir, normalized, "", normal)["still"]
    loop = asyncio.get_running_loop()
    try:
        still = await loop.run_in_executor(None, lv.prepare_still, cover, dest, normal)
    except (ValueError, OSError) as exc:
        return _safe_json({"found": True, "album_slug": normalized, "error": str(exc)})
    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "shape": normal,
        "cover": str(cover),
        "still": still,
    })


async def save_lyric_video(
    album_slug: str,
    track_slug: str,
    link: str,
    shape: str = "16:9",
    master_audio: bool = True,
    replace: bool = False,
) -> str:
    """Save the lyric video Suno made beside the album's audio.

    Pass the `url` Suno's visuals-download gave for the video. The file is
    fetched (only an https link on Suno's hosts or its download bucket),
    checked to be a video, and saved under the album's lyric_videos/. The
    video's own sound is the Suno take: when the track has a mastered file of
    the same length, the master goes under the picture instead, which is
    copied, not re-encoded. Free: nothing is generated here.

    An earlier video of the same track and shape is kept unless replace is true.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        link: The `url` from visuals-download
        shape: The shape the video was made in: 16:9 (the default), 1:1 or 9:16
        master_audio: Put the mastered file under the picture when there is one
        replace: Overwrite a video that is already there

    Returns:
        JSON with {found, saved: true, path, shape, width, height, duration_s,
        bytes, audio: "master" | "suno", audio_note} or {found, saved: false,
        error}
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

    def refused(message: str) -> str:
        return _safe_json({
            "found": True, "album_slug": ctx["album_slug"], "track_slug": ctx["track_slug"],
            "saved": False, "error": message,
        })

    paths = _paths(audio_dir, ctx["album_slug"], ctx["track_slug"], normal)
    output = paths["output"]
    if output.exists() and not replace:
        return refused(
            f"{output.name} is already there. Nothing was changed. Ask the user, then pass "
            "replace=true to overwrite it."
        )

    master: Path | None = None
    if master_audio:
        found = _local_stages(ctx["album_slug"], ctx["album"], ctx["track_slug"])["mastered"]
        master = Path(found) if found else None

    info, problem = await fetch_and_finish(
        link, output, lambda part, made: lv.finish(part, made, master),
    )
    if info is None:
        return refused(problem or "Saving the video failed.")

    logger.info("Saved a lyric video for '%s' / '%s'", ctx["album_slug"], ctx["track_slug"])
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "saved": True,
        "shape": normal,
        **info,
    })


def register(mcp: Any) -> None:
    """Register the lyric-video tools with the MCP server."""
    mcp.tool()(get_lyric_video_plan)
    mcp.tool()(prepare_lyric_video_still)
    mcp.tool()(save_lyric_video)
