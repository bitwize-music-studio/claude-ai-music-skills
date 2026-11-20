"""A lyric video Suno renders for a track.

Suno's ``video-assemble`` holds stills over a song and, with ``lyrics: true``,
burns the words in as they are sung. The plugin's server never calls Suno, so
the lyric-video skill does. This module does the parts around it:

* ``prepare_still`` makes the picture Suno is given, from the album's cover;
* ``build_request`` builds ``video-assemble``'s arguments;
* ``download_video`` saves the MP4 behind the link ``visuals-download`` gives;
* ``finish`` checks it and puts the mastered audio under the picture.

Measured on a 55-second song: rendering and downloading spent no credit of any
kind; the MP4 was H.264 at 30 frames a second with 48 kHz AAC, 1080x1080 for
1:1 and 1920x1080 for 16:9, about 11 MB; every sung line was shown, lit word by
word; a square still in a 16:9 video sat between black bars; a still held
longer than the song left silence at the end; the link was a signed address on
``suno-data-uploads.s3.amazonaws.com``.

Pillow is imported on first use, as in ``tools/artwork/cover.py``.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.artwork.cover import _flattened, _pillow
from tools.shared import suno_links

# The shapes video-assemble takes, and the size of the still made for each.
# Suno renders at 1080 on the short side.
SHAPES: dict[str, tuple[int, int]] = {"16:9": (1920, 1080), "1:1": (1080, 1080), "9:16": (1080, 1920)}
DEFAULT_SHAPE = "16:9"

# video-assemble holds a still for at most 60 seconds and takes at most 40 clips.
STILL_SECONDS = 60
MAX_CLIPS = 40

# A 55-second video was 11 MB when measured; this leaves room for a long song.
MAX_VIDEO_BYTES = 1024 * 1024 * 1024
# How long one read may stall, and how long the whole download may take.
TIMEOUT_S = 60
TOTAL_TIMEOUT_S = 900
CHUNK_BYTES = 256 * 1024
_USER_AGENT = "bitwize-music-mcp/1.0 (lyric video)"

# The words are timed to the take. A master of another length would drift under them.
MASTER_TOLERANCE_S = 1.0
_PROBE_TIMEOUT_S = 60
_MUX_TIMEOUT_S = 900

Runner = Callable[..., Any]


class ToolMissing(ValueError):
    """ffprobe or ffmpeg is not installed."""


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------


def normal_shape(value: Any) -> str | None:
    """A shape as ``video-assemble`` names it, or None when Suno does not make it.

    ``16x9`` is read as ``16:9``; nothing written means the default.
    """
    if value is None:
        return DEFAULT_SHAPE
    if not isinstance(value, str):
        return None
    text = value.strip().lower().replace("x", ":")
    if not text:
        return DEFAULT_SHAPE
    return text if text in SHAPES else None


def shape_slug(shape: str) -> str:
    """A shape as part of a file name: ``16:9`` is ``16x9``."""
    return shape.replace(":", "x")


def _known(shape: str) -> tuple[int, int]:
    if shape not in SHAPES:
        raise ValueError(f"'{shape}' is not a shape Suno makes; use 16:9, 1:1 or 9:16")
    return SHAPES[shape]


# ---------------------------------------------------------------------------
# The still
# ---------------------------------------------------------------------------


def prepare_still(cover: Path, dest: Path, shape: str) -> dict[str, Any]:
    """Write the picture Suno holds under the words, from the album's cover.

    The whole cover sits in the middle of the frame. Where the frame is wider
    or taller than the cover, the space beside it is the cover again, enlarged,
    blurred and darkened: Suno puts black bars there when it is handed a square
    picture for a 16:9 video (measured).

    Saved as a JPEG, which keeps it well under the 10 MB Suno accepts.

    Returns:
        ``{"path", "width", "height", "bytes", "content_type"}``

    Raises:
        ValueError: unknown shape, or the cover is missing or not an image.
    """
    width, height = _known(shape)
    if not cover.is_file():
        raise ValueError(f"Cover not found: {cover}")
    image_module = _pillow()
    try:
        with image_module.open(cover) as opened:
            art = _flattened(opened)
            art.load()
    except (OSError, SyntaxError, ValueError) as exc:  # UnidentifiedImageError is an OSError
        raise ValueError(f"{cover.name} is not an image: {exc}") from exc

    fit = min(width / art.width, height / art.height)
    front = art.resize(
        (max(1, round(art.width * fit)), max(1, round(art.height * fit))), image_module.Resampling.LANCZOS,
    )
    if front.size == (width, height):
        frame = front
    else:
        from PIL import ImageEnhance, ImageFilter

        fill = max(width / art.width, height / art.height)
        back = art.resize(
            (max(width, round(art.width * fill)), max(height, round(art.height * fill))),
            image_module.Resampling.BILINEAR,
        )
        left, top = (back.width - width) // 2, (back.height - height) // 2
        back = back.crop((left, top, left + width, top + height))
        frame = ImageEnhance.Brightness(back.filter(ImageFilter.GaussianBlur(40))).enhance(0.55)
        frame.paste(front, ((width - front.width) // 2, (height - front.height) // 2))

    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.save(dest, "JPEG", quality=92, optimize=True)
    return {
        "path": str(dest), "width": width, "height": height,
        "bytes": dest.stat().st_size, "content_type": "image/jpeg",
    }


# ---------------------------------------------------------------------------
# The request
# ---------------------------------------------------------------------------


def build_request(song_id: str, asset_id: str, duration_s: float, shape: str) -> dict[str, Any]:
    """The arguments for Suno's ``video-assemble``: one still under the whole song.

    The still is repeated as few times as fit under a minute each, evenly, for
    exactly the song's length: a still that outlasts the song leaves silence
    at the end (measured).

    Raises:
        ValueError: unknown shape, or a length Suno cannot take.
    """
    _known(shape)
    if not isinstance(duration_s, (int, float)) or isinstance(duration_s, bool) \
            or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("The song's length has to be a number of seconds above zero")
    hundredths = round(duration_s * 100)
    count = max(1, math.ceil(hundredths / (STILL_SECONDS * 100)))
    if count > MAX_CLIPS:
        raise ValueError(
            f"The song is {duration_s:g} s long; Suno assembles at most "
            f"{MAX_CLIPS * STILL_SECONDS} s of stills",
        )
    base, extra = divmod(hundredths, count)
    return {
        "song_id": song_id,
        "lyrics": True,
        "aspect": shape,
        "clips": [
            {"asset_id": asset_id, "duration_s": (base + (1 if index < extra else 0)) / 100}
            for index in range(count)
        ],
    }


# ---------------------------------------------------------------------------
# The download
# ---------------------------------------------------------------------------


def download_video(url: str, dest: Path, *, opener: Any = None) -> int:
    """Save the file behind a Suno download link to *dest*; returns its size.

    The link has to be an https address on Suno's hosts or its download bucket,
    and a redirect is followed only while it stays there. Read a chunk at a
    time, so a reply that never ends stops at ``MAX_VIDEO_BYTES`` and one that
    trickles in stops at ``TOTAL_TIMEOUT_S``. Whatever goes wrong, nothing is
    left at *dest*.

    Raises:
        ValueError: not a Suno link, too large, or too slow.
        OSError, http.client.HTTPException: the download failed.
    """
    if not suno_links.is_suno_link(url, files=True):
        raise ValueError(
            f"Not a download link on Suno's hosts: {suno_links.link_host(url) or 'no host'}",
        )
    if opener is None:
        opener = suno_links.opener(files=True)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    dest.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    size = 0
    try:
        with opener.open(request, timeout=TIMEOUT_S) as response, open(dest, "wb") as handle:
            while True:
                chunk: bytes = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_VIDEO_BYTES:
                    raise ValueError(
                        f"The file is larger than {MAX_VIDEO_BYTES // (1024 * 1024)} MB",
                    )
                if time.monotonic() - started > TOTAL_TIMEOUT_S:
                    raise ValueError(f"The download took longer than {TOTAL_TIMEOUT_S} seconds")
                handle.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return size


# ---------------------------------------------------------------------------
# ffprobe and ffmpeg
# ---------------------------------------------------------------------------


def probe(path: Path, *, run: Runner = subprocess.run) -> dict[str, Any]:
    """What ffprobe says a media file holds.

    Returns:
        ``{"duration_s", "video", "audio", "width", "height"}``

    Raises:
        ToolMissing: ffprobe is not installed.
        ValueError: ffprobe could not read the file.
    """
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height", "-of", "json", str(path),
    ]
    try:
        done = run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_PROBE_TIMEOUT_S, stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise ToolMissing(
            "ffprobe is not installed, so the video cannot be checked. Install ffmpeg.",
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"ffprobe could not read {path.name}: {exc}") from exc
    if done.returncode != 0:
        raise ValueError(f"ffprobe could not read {path.name}: {str(done.stderr).strip()[:300]}")
    try:
        data = json.loads(done.stdout)
        duration = float(data["format"]["duration"])
        streams = list(data.get("streams") or [])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"ffprobe could not read {path.name}: no duration in its answer") from exc
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    return {
        "duration_s": round(duration, 3),
        "video": video is not None,
        "audio": any(s.get("codec_type") == "audio" for s in streams),
        "width": int(video["width"]) if video and video.get("width") else None,
        "height": int(video["height"]) if video and video.get("height") else None,
    }


def swap_audio(video: Path, audio: Path, dest: Path, *, run: Runner = subprocess.run) -> None:
    """Write *video*'s picture with *audio* under it to *dest*.

    The picture is copied, not re-encoded, so the burned-in words stay as Suno
    rendered them. Nothing is left at *dest* when it fails.

    Raises:
        ToolMissing: ffmpeg is not installed.
        ValueError: ffmpeg failed.
    """
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-shortest", "-movflags", "+faststart", "-f", "mp4", str(dest),
    ]
    problem = ""
    try:
        done = run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_MUX_TIMEOUT_S, stdin=subprocess.DEVNULL,
        )
        if done.returncode != 0:
            problem = str(done.stderr).strip()[:300] or f"exit {done.returncode}"
    except FileNotFoundError as exc:
        dest.unlink(missing_ok=True)
        raise ToolMissing("ffmpeg is not installed, so the master cannot go under the video.") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        problem = str(exc)
    if problem:
        dest.unlink(missing_ok=True)
        raise ValueError(f"ffmpeg could not put the master under the video: {problem}")


def _looks_like_mp4(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            head = handle.read(12)
    except OSError:
        return False
    return len(head) == 12 and head[4:8] == b"ftyp"


def finish(
    downloaded: Path,
    dest: Path,
    master: Path | None,
    *,
    probe: Callable[..., dict[str, Any]] = probe,
    swap: Callable[..., None] = swap_audio,
) -> dict[str, Any]:
    """Turn the file Suno sent into the lyric video at *dest*.

    The download has to be an MP4 with a picture in it. When *master* is given
    and is as long as the video, to within ``MASTER_TOLERANCE_S``, it replaces
    Suno's audio: the video's sound is the take, not the master. A master of
    another length is left out, because the words are timed to the take.
    Without ffmpeg the file is kept as Suno made it, unchecked.

    *downloaded* is gone afterwards, whatever happens.

    Returns:
        ``{"path", "duration_s", "width", "height", "bytes", "audio", "audio_note"}``.
        ``audio`` is ``"master"`` or ``"suno"``; ``audio_note`` says why when it
        is not the master although one was given.

    Raises:
        ValueError: the download is not a video.
    """
    info: dict[str, Any] = {"duration_s": None, "width": None, "height": None}
    audio, note = "suno", ""
    try:
        if not _looks_like_mp4(downloaded):
            raise ValueError("What Suno sent is not an MP4")
        try:
            info = probe(downloaded)
        except ToolMissing as exc:
            master = None
            note = f"{exc} The file was saved as Suno made it, with Suno's own audio."
        else:
            if not info["video"]:
                raise ValueError("What Suno sent has no picture in it")
    except ValueError:
        downloaded.unlink(missing_ok=True)
        raise

    if master is not None:
        try:
            master_s = probe(master)["duration_s"]
            if abs(master_s - info["duration_s"]) <= MASTER_TOLERANCE_S:
                swap(downloaded, master, dest)
                audio = "master"
            else:
                note = (
                    f"The master is {master_s:g} s long and the video {info['duration_s']:g} s, so "
                    "the words would drift under it. Suno's own audio was kept."
                )
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
    }
