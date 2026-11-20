"""A promo clip Suno generates for a passage of a track's keeper.

Suno's ``video-create`` makes a clip of 5 to 15 seconds from a prompt. Given a
song and where in it to start, the video model hears that passage and it
becomes the clip's soundtrack. The plugin's server never talks to Suno: the
promo-director skill calls the tool. This module builds the request, and turns
the file Suno sends into the promo clip, with the same passage of the mastered
audio under the picture.

Unlike a lyric video, a clip is paid for by the second in Visuals credits, so
the request always names its model: left out, Suno uses its Standard model at
twice the price a second.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.promotion import lyric_video as lv

# The clip lengths video-create takes, in whole seconds.
MIN_SECONDS = 5
MAX_SECONDS = 15
DEFAULT_SECONDS = 15

# Vertical, for Reels, Shorts and TikTok: video-create's own default.
DEFAULT_ASPECT = "9:16"

# Suno's Fast model, the cheapest a second. Never left for Suno to choose.
DEFAULT_MODEL = "video-1"

# How far the master's length may be from the take's and still share its timeline.
MASTER_TOLERANCE_S = lv.MASTER_TOLERANCE_S

# A passage may end this far past the song's stated length: lengths are rounded.
_END_SLACK_S = 0.05

_MODEL_RE = re.compile(r"video-[a-z0-9][a-z0-9.-]{0,30}")
_SONG_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_ASSET_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:-]{3,79}")


def normal_model(value: Any) -> str:
    """The video model to ask for: *value*, or the cheapest when nothing is written.

    Raises:
        ValueError: *value* is not a video model id. It is refused, not
            dropped, because a request without a model is Suno's Standard one.
    """
    if value is None or value == "":
        return DEFAULT_MODEL
    model = value.strip().lower() if isinstance(value, str) else ""
    if not _MODEL_RE.fullmatch(model):
        raise ValueError(
            f"'{value}' is not a video model id such as video-1 (Fast, 480p) or "
            "video-2 (Standard, 720p)",
        )
    return model


def normal_aspect(value: Any) -> str | None:
    """A clip's shape as ``video-create`` names it; vertical when nothing is written."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_ASPECT
    return lv.normal_shape(value)


def _seconds(value: Any) -> int:
    whole = (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value) and float(value).is_integer()
    )
    if not whole or not MIN_SECONDS <= int(value) <= MAX_SECONDS:
        raise ValueError(
            f"A clip is {MIN_SECONDS} to {MAX_SECONDS} whole seconds long, not {value!r}",
        )
    return int(value)


def _start(value: Any) -> float:
    if (
        not isinstance(value, (int, float)) or isinstance(value, bool)
        or not math.isfinite(value) or value < 0
    ):
        raise ValueError(f"The start of the passage has to be a time in seconds, not {value!r}")
    return round(float(value), 2)


def build_request(
    song_id: str,
    prompt: str,
    start_s: float,
    duration_s: int = DEFAULT_SECONDS,
    aspect: str = DEFAULT_ASPECT,
    model: str = "",
    *,
    song_duration_s: float | None = None,
    first_frame_asset_id: str = "",
    singing: bool = True,
) -> dict[str, Any]:
    """The arguments for Suno's ``video-create``: a clip for a passage of a song.

    The request never carries ``dry_run``: the caller sends it once with
    ``dry_run: true`` for the price, and again without it after a go-ahead.

    Args:
        song_id: The keeper's clip id.
        prompt: What happens in the clip, and how the camera moves.
        start_s: Where in the song the passage starts, in seconds.
        duration_s: The clip's length, 5 to 15 whole seconds.
        aspect: 9:16 (the default), 1:1 or 16:9.
        model: A video model id; the cheapest when empty.
        song_duration_s: The song's length, to check the passage fits in it.
        first_frame_asset_id: An image on Suno for the clip to open on.
        singing: False asks that no one on screen sing or mouth the words.

    Raises:
        ValueError: an argument Suno would refuse, or a passage that runs past
            the end of the song.
    """
    if not isinstance(song_id, str) or not _SONG_ID_RE.fullmatch(song_id):
        raise ValueError(f"'{song_id}' is not a song id from Suno")
    text = prompt.strip() if isinstance(prompt, str) else ""
    if not text:
        raise ValueError("The clip needs a prompt: what happens in it, and how the camera moves")
    seconds = _seconds(duration_s)
    start = _start(start_s)
    shape = normal_aspect(aspect)
    if shape is None:
        raise ValueError(f"'{aspect}' is not a shape Suno makes; use 9:16, 1:1 or 16:9")
    if song_duration_s is not None and start + seconds > song_duration_s + _END_SLACK_S:
        raise ValueError(
            f"A {seconds}-second passage from {start:g} s runs past the end of the song "
            f"({song_duration_s:g} s)",
        )
    request: dict[str, Any] = {
        "prompt": text,
        "song_id": song_id,
        "song_start_s": start,
        "duration_s": seconds,
        "aspect": shape,
        "model": normal_model(model),
    }
    frame = first_frame_asset_id.strip() if isinstance(first_frame_asset_id, str) else ""
    if frame:
        if not _ASSET_ID_RE.fullmatch(frame):
            raise ValueError(f"'{first_frame_asset_id}' is not an asset id from Suno")
        request["first_frame_asset_id"] = frame
    if not singing:
        request["lip_sync"] = False
    return request


def finish_clip(
    downloaded: Path,
    dest: Path,
    master: Path | None,
    start_s: float,
    song_duration_s: float | None,
    *,
    probe: Callable[..., dict[str, Any]] = lv.probe,
    swap: Callable[..., None] = lv.swap_audio,
) -> dict[str, Any]:
    """Turn the file Suno sent into the promo clip at *dest*.

    The download has to be an MP4 with a picture in it. The clip's sound is the
    passage of the Suno take. When *master* is given and is as long as the take
    (*song_duration_s*), to within ``MASTER_TOLERANCE_S``, it shares the take's
    timeline, and the same passage of the master replaces Suno's audio; the
    picture is copied untouched. Otherwise Suno's audio is kept, and
    ``audio_note`` says why. Without ffmpeg the file is kept unchecked.

    *downloaded* is gone afterwards, whatever happens.

    Returns:
        ``{"path", "duration_s", "width", "height", "bytes", "audio", "audio_note",
        "audio_start_s"}``; ``audio_start_s`` is where in the master the passage
        was taken from, or None when Suno's audio was kept.

    Raises:
        ValueError: the download is not a video.
    """
    info, note = lv.check_download(downloaded, probe=probe)
    audio = "suno"
    if master is not None and not note:
        try:
            master_s = probe(master)["duration_s"]
            clip_s = info["duration_s"]
            if song_duration_s is None or song_duration_s <= 0:
                note = (
                    "The take's length was not given, so the master could not be lined up "
                    "with it. Suno's own audio was kept."
                )
            elif abs(master_s - song_duration_s) > MASTER_TOLERANCE_S:
                note = (
                    f"The master is {master_s:g} s long and the take {song_duration_s:g} s, so "
                    "the passage would be another one. Suno's own audio was kept."
                )
            elif start_s + clip_s > master_s + MASTER_TOLERANCE_S + _END_SLACK_S:
                note = (
                    f"The passage runs past the end of the master ({master_s:g} s). "
                    "Suno's own audio was kept."
                )
            else:
                swap(downloaded, master, dest, audio_start_s=start_s, seconds=clip_s)
                audio = "master"
        except ValueError as exc:
            note = f"{exc} Suno's own audio was kept."

    if audio == "master":
        downloaded.unlink(missing_ok=True)
    else:
        os.replace(downloaded, dest)
    return {
        "path": str(dest),
        "duration_s": info["duration_s"],
        "width": info["width"],
        "height": info["height"],
        "bytes": dest.stat().st_size,
        "audio": audio,
        "audio_note": note,
        "audio_start_s": start_s if audio == "master" else None,
    }
