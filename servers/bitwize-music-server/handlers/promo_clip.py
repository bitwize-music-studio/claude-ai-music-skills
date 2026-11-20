"""A promo clip Suno generates — these tools plan it and save the one the user chose.

Suno's ``video-create`` makes a clip of 5 to 15 seconds for a passage of a
song, which becomes the clip's soundtrack. The plugin's server never talks to
Suno, so the promo-director skill calls that tool. These tools do the rest:
say what will be made and build the request, and save the chosen clip with the
album's other promo videos, with the same passage of the mastered audio under
the picture.

A clip is paid for by the second in Visuals credits, so the request always
names its model, and the skill prices it with ``dry_run: true`` and waits for a
go-ahead before it sends it for real.
"""

from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path
from typing import Any

from handlers._shared import _safe_json
from handlers.generation import _load_track, _problem, album_audio_dir, keeper_clip
from handlers.lyric_video import _cover, fetch_and_finish
from handlers.playback import _local_stages
from tools.promotion import suno_clip as sc

logger = logging.getLogger(__name__)

# The album's promo videos, beside its audio. The locally made ones end _promo.mp4.
CLIPS_DIR = "promo_videos"


# Stands in for the song while a track has no keeper, so the rest is still judged.
_NO_SONG = "00000000-0000-0000-0000-000000000000"


def _output(audio_dir: Path, track_slug: str) -> Path:
    return audio_dir / CLIPS_DIR / f"{track_slug}_suno.mp4"


async def get_promo_clip_plan(
    album_slug: str,
    track_slug: str,
    prompt: str = "",
    start_s: float = -1.0,
    duration_s: int = sc.DEFAULT_SECONDS,
    aspect: str = sc.DEFAULT_ASPECT,
    model: str = "",
    first_frame_asset_id: str = "",
    song_duration_s: float = 0.0,
    singing: bool = True,
) -> str:
    """Say how a generated promo clip for a track will be made, and build the request. Free.

    Suno's video-create makes a clip of 5 to 15 seconds for a passage of the
    track's keeper, which becomes its soundtrack. Read-only, and it never calls
    Suno: the calling skill does. Call it first with the album and the track,
    then again with the prompt and the passage to get `request`.

    The clip costs Visuals credits by the second. `request` never carries
    `dry_run`: send it to video-create with `dry_run: true` first for the
    price, tell the user, and send it without only after their go-ahead.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        prompt: What happens in the clip, and how the camera moves
        start_s: Where in the song the passage starts, in seconds; -1 while
            it is not chosen yet
        duration_s: The clip's length, 5 to 15 whole seconds
        aspect: 9:16 (the default), 1:1 or 16:9
        model: A video model id from Suno's visuals-models, such as video-1
            (Fast, 480p) or video-2 (Standard, 720p). Empty is video-1, the
            cheapest: the request always names a model
        first_frame_asset_id: An image on Suno for the clip to open on
        song_duration_s: The keeper's length in seconds, from audio-retrieve's
            metadata.duration, to check the passage fits in the song
        singing: False asks that no one on screen sing or mouth the words

    Returns:
        JSON with {found, album_slug, track_slug, title, song: {clip_id,
        source} | null, aspect, model, duration_s, cover (the album's cover
        file, or null), master: {path} | null, output: {path, exists}, request
        (the arguments for video-create, once the prompt and the passage are
        given, else null), ffmpeg, ready, problems: [{code, severity:
        blocking|warning, detail}]}. `ready` is false while any problem is
        blocking
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    audio_dir, error = album_audio_dir(ctx["album_slug"], ctx["album"])
    if error:
        return error
    assert audio_dir is not None

    output = _output(audio_dir, ctx["track_slug"])
    problems: list[dict[str, str]] = []

    clip_id, source, _link, problem = keeper_clip(ctx["text"])
    if problem:
        problems.append(problem)

    master = _local_stages(ctx["album_slug"], ctx["album"], ctx["track_slug"])["mastered"]
    if not master:
        problems.append(_problem(
            "no_master", "warning",
            "The track has no mastered file, so the clip will carry Suno's own audio. "
            "Master the track first to have the master under the picture",
        ))
    have_ffmpeg = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    if not have_ffmpeg:
        problems.append(_problem(
            "ffmpeg_missing", "warning",
            "ffmpeg is not installed, so the clip is saved as Suno makes it: unchecked, and "
            "with Suno's own audio",
        ))
    if output.is_file():
        problems.append(_problem(
            "clip_exists", "warning",
            f"{output.name} is already there. Saving a new one needs replace=true",
        ))

    # What was given is judged at once, before there is a prompt or a keeper: a
    # model that cannot be read must never be left for Suno to choose.
    named_model: str | None = None
    shape: str | None = None
    request: dict[str, Any] | None = None
    # Only -1 says the start is not chosen yet: any other negative is a mistake.
    have_prompt, have_start = bool(prompt.strip()), start_s != -1
    try:
        named_model = sc.normal_model(model)
        shape = sc.normal_aspect(aspect)
        if shape is None:
            raise ValueError(f"'{aspect}' is not a shape Suno makes; use 9:16, 1:1 or 16:9")
        built = sc.build_request(
            clip_id or _NO_SONG,
            prompt if have_prompt else "-",
            start_s if have_start else 0.0,
            duration_s, shape, named_model,
            song_duration_s=song_duration_s if song_duration_s > 0 else None,
            first_frame_asset_id=first_frame_asset_id, singing=singing,
        )
        if clip_id and have_prompt and have_start:
            request = built
    except ValueError as exc:
        problems.append(_problem("request_invalid", "blocking", str(exc)))

    cover = _cover(audio_dir, ctx["album"])
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": ctx["track"].get("title", ctx["track_slug"]),
        "song": {"clip_id": clip_id, "source": source} if clip_id else None,
        "aspect": shape,
        "model": named_model,
        "duration_s": duration_s,
        "cover": str(cover) if cover else None,
        "master": {"path": master} if master else None,
        "output": {"path": str(output), "exists": output.is_file()},
        "request": request,
        "ffmpeg": have_ffmpeg,
        "ready": not any(p["severity"] == "blocking" for p in problems),
        "problems": problems,
    })


async def save_promo_clip(
    album_slug: str,
    track_slug: str,
    link: str,
    start_s: float,
    song_duration_s: float = 0.0,
    master_audio: bool = True,
    replace: bool = False,
) -> str:
    """Save the promo clip Suno made, the take the user chose, with the album's promo videos.

    Pass the `url` Suno's visuals-download gave for the chosen take. The file
    is fetched (only an https link on Suno's hosts or its download bucket),
    checked to be a video, and saved under the album's promo_videos/ as
    <track>_suno.mp4. The clip's own sound is the passage of the Suno take:
    when the track has a mastered file as long as the take, the same passage
    of the master goes under the picture instead, which is copied, not
    re-encoded. Free: nothing is generated here.

    An earlier clip of the track is kept unless replace is true.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        link: The `url` from visuals-download
        start_s: Where in the song the clip's passage starts, in seconds: the
            request's song_start_s
        song_duration_s: The keeper's length in seconds, from audio-retrieve.
            Without it the master cannot be lined up, and Suno's audio is kept
        master_audio: Put the master's passage under the picture when there is one
        replace: Overwrite a clip that is already there

    Returns:
        JSON with {found, saved: true, path, width, height, duration_s, bytes,
        audio: "master" | "suno", audio_note, audio_start_s (where in the master
        the passage was taken from, or null)} or {found, saved: false, error}
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    audio_dir, error = album_audio_dir(ctx["album_slug"], ctx["album"])
    if error:
        return error
    assert audio_dir is not None

    def refused(message: str) -> str:
        return _safe_json({
            "found": True, "album_slug": ctx["album_slug"], "track_slug": ctx["track_slug"],
            "saved": False, "error": message,
        })

    if isinstance(start_s, bool) or not math.isfinite(start_s) or start_s < 0:
        return refused(f"The start of the passage has to be a time in seconds, not {start_s!r}.")
    output = _output(audio_dir, ctx["track_slug"])
    if output.exists() and not replace:
        return refused(
            f"{output.name} is already there. Nothing was changed. Ask the user, then pass "
            "replace=true to overwrite it."
        )

    master: Path | None = None
    if master_audio:
        found = _local_stages(ctx["album_slug"], ctx["album"], ctx["track_slug"])["mastered"]
        master = Path(found) if found else None
    song_s = song_duration_s if song_duration_s > 0 else None

    info, problem = await fetch_and_finish(
        link, output, lambda part, made: sc.finish_clip(part, made, master, start_s, song_s),
    )
    if info is None:
        return refused(problem or "Saving the clip failed.")

    logger.info("Saved a Suno promo clip for '%s' / '%s'", ctx["album_slug"], ctx["track_slug"])
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "saved": True,
        **info,
    })


def register(mcp: Any) -> None:
    """Register the promo-clip tools with the MCP server."""
    mcp.tool()(get_promo_clip_plan)
    mcp.tool()(save_promo_clip)
