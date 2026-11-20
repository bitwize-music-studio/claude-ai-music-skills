"""A cover made by Suno's image tool.

The plugin's server never calls Suno. The album-art-director skill sends the
request built here to Suno's ``image-create`` tool, waits with
``visuals-wait``, asks ``visuals-download`` for a link to each take, and hands
those links to ``fetch_image``, which saves each picture beside the album's
audio, where candidates from Codex go too.

Measured with Suno's Fast model (``image-1``): one call made two 1024x1024
JPEGs for 1 Visuals credit, and each download link was a plain https address
on ``cdn1.suno.ai``.

Pillow is imported on first use, as in ``cover.py``.
"""

from __future__ import annotations

import http.client
import io
import os
import re
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.artwork.cover import _pillow
from tools.shared import suno_links

# A cover is square.
ASPECT = "1:1"
# One image-create call makes two takes (measured; the models list `max_takes: 2`).
TAKES = 2
# A 1024x1024 JPEG was about 600 KB when measured; this leaves room for a far
# larger image and still stops a download that is not one.
MAX_BYTES = 40 * 1024 * 1024
# 8000x8000: far past any cover, and far short of an image built to exhaust memory.
MAX_PIXELS = 64_000_000
# How long one read may stall, and how long the whole download may take.
TIMEOUT_S = 60
TOTAL_TIMEOUT_S = 120
CHUNK_BYTES = 64 * 1024

_USER_AGENT = "bitwize-music-mcp/1.0 (album art)"

# A model id such as "image-1". It goes into a request, so it is checked first.
_MODEL_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
# The candidate's file name without its suffix. It becomes a path, so it is checked first.
_STEM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}")
# What Pillow calls the formats a cover can be read from, and the suffix each gets.
_SUFFIX = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

Reader = Callable[[str], bytes]


def model_name(value: Any) -> str:
    """``artwork.suno_model`` from config as a model id, or ``""`` for Suno's default."""
    if not isinstance(value, str):
        return ""
    name = value.strip().lower()
    return name if _MODEL_RE.fullmatch(name) else ""


def written_model(value: Any) -> str:
    """``artwork.suno_model`` as it was written, for the art plan to judge.

    Nothing is dropped here: a model id with a typing mistake has to reach
    the plan, which stops on it. Left to become ``""`` it would quietly pick
    Suno's default, at fifty times the price of the Fast model.
    """
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return "(unreadable)"
    return str(value).strip().lower()


def build_request(prompt: str, avoid: str = "", model: str = "") -> dict[str, str]:
    """The arguments for Suno's ``image-create`` that make a cover from *prompt*.

    ``image-create`` has one text field, so *avoid* (the album's negative
    prompt) goes in as a last line of it. *model* is sent only when set;
    without one Suno uses its own default.
    """
    text = prompt.strip()
    if avoid.strip():
        text += f"\n\nAvoid: {avoid.strip()}"
    request = {"prompt": text, "aspect": ASPECT}
    if model:
        request["model"] = model
    return request


def link_host(url: str) -> str:
    """The host a link points at, lower-cased; ``""`` when it has none."""
    return suno_links.link_host(url)


def is_suno_link(url: str) -> bool:
    """Whether *url* is an https address on one of Suno's own hosts, on the https port.

    The rule lives in ``tools/shared/suno_links.py``. An image's link is on
    Suno's own domains, so the download bucket video links use is not accepted
    here.
    """
    return suno_links.is_suno_link(url)


# Follow a redirect only while it stays on Suno's hosts, over https.
SunoOnlyRedirects = suno_links.SunoRedirects


def default_opener() -> urllib.request.OpenerDirector:
    """An opener whose redirects stay on Suno's hosts."""
    return suno_links.opener()


def read_link(url: str, *, opener: Any = None) -> bytes:
    """The bytes behind a Suno download link.

    Read a chunk at a time, so a reply that never ends stops at ``MAX_BYTES``
    and one that trickles in stops at ``TOTAL_TIMEOUT_S``.

    Raises:
        ValueError: the link is not https on one of Suno's hosts, the file is
            larger than ``MAX_BYTES``, or the download took too long.
        OSError: the download failed (urllib's own errors are OSErrors).
        http.client.HTTPException: the reply was not HTTP that could be read.
    """
    if not is_suno_link(url):
        raise ValueError(f"Not a download link on Suno's hosts: {link_host(url) or 'no host'}")
    if opener is None:
        opener = default_opener()
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    started = time.monotonic()
    chunks: list[bytes] = []
    size = 0
    with opener.open(request, timeout=TIMEOUT_S) as response:
        while True:
            chunk: bytes = response.read(CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB")
            if time.monotonic() - started > TOTAL_TIMEOUT_S:
                raise ValueError(f"The download took longer than {TOTAL_TIMEOUT_S} seconds")
            chunks.append(chunk)
    return b"".join(chunks)


def fetch_image(
    url: str, dest_dir: Path, stem: str, *, read: Reader = read_link,
) -> dict[str, Any]:
    """Save the picture behind a Suno download link as ``<dest_dir>/<stem><suffix>``.

    The suffix follows what the file is (``.jpg``, ``.png`` or ``.webp``), not
    what its address says. The picture has to decode whole, so a download cut
    short is not saved. An existing file is never overwritten.

    Returns:
        ``{"ok": True, "path", "width", "height", "format"}``, or
        ``{"ok": False, "error"}`` with nothing left on disk.
    """
    def failed(message: str) -> dict[str, Any]:
        return {"ok": False, "error": message}

    if not _STEM_RE.fullmatch(stem):
        return failed(f"'{stem}' is not a plain file name")
    if not is_suno_link(url):
        return failed(f"Not a download link on Suno's hosts: {link_host(url) or 'no host'}")
    try:
        data = read(url)
    except (OSError, ValueError, http.client.HTTPException) as exc:  # the last is no OSError
        return failed(f"The download failed: {exc}")

    try:
        image_module = _pillow()
    except ValueError as exc:
        return failed(str(exc))
    too_large = "The image is too large to be a cover"
    try:
        with image_module.open(io.BytesIO(data)) as image:
            width, height = image.size
            kind = str(image.format or "")
            if width * height > MAX_PIXELS:
                return failed(f"{too_large}: {width}x{height}")
            # A header is not a picture: a JPEG cut short opens, and only fails to decode.
            image.load()
    except image_module.DecompressionBombError:
        return failed(too_large)
    except (OSError, SyntaxError, ValueError) as exc:  # UnidentifiedImageError is an OSError
        return failed(f"What Suno sent is not an image: {exc}")

    suffix = _SUFFIX.get(kind)
    if suffix is None:
        return failed(
            f"Suno sent a {kind or 'nameless'} image; a cover is read from a JPEG, a PNG or a WebP",
        )
    target = dest_dir / f"{stem}{suffix}"
    created = False
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as handle:  # "x": never write over an earlier candidate
            created = True
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        if created:
            target.unlink(missing_ok=True)  # ours: the open above made it
        elif isinstance(exc, FileExistsError) and target.exists():
            return failed(f"{target.name} is already there; nothing was overwritten")
        return failed(f"Could not save {target.name}: {exc}")
    return {
        "ok": True, "path": str(target), "width": int(width), "height": int(height), "format": kind,
    }
