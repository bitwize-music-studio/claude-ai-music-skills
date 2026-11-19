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

import io
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tools.artwork.cover import _pillow

# A cover is square.
ASPECT = "1:1"
# One image-create call makes two takes (measured; the models list `max_takes: 2`).
TAKES = 2
# A 1024x1024 JPEG was about 600 KB when measured; this leaves room for a far
# larger image and still stops a download that is not one.
MAX_BYTES = 40 * 1024 * 1024
TIMEOUT_S = 60

# Suno serves pages from suno.com and files from suno.ai.
_DOMAINS = ("suno.ai", "suno.com")
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
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_suno_link(url: str) -> bool:
    """Whether *url* is an https address on one of Suno's hosts.

    Decided by the parsed scheme and host, never by where "suno" appears in the
    text, so ``suno.ai.example.org`` and ``cdn1.suno.ai@example.org`` are not
    Suno's.
    """
    try:
        scheme = urlparse(url).scheme
    except ValueError:
        return False
    host = link_host(url)
    return scheme == "https" and any(host == domain or host.endswith(f".{domain}") for domain in _DOMAINS)


class SunoOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only while it stays on Suno's hosts, over https."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str,
    ) -> urllib.request.Request | None:
        if not is_suno_link(newurl):
            raise urllib.error.HTTPError(
                newurl, code, "the download was redirected away from Suno's hosts", headers, fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_link(url: str, *, opener: Any = None) -> bytes:
    """The bytes behind a Suno download link.

    Raises:
        ValueError: the link is not https on one of Suno's hosts, or the file
            is larger than ``MAX_BYTES``.
        OSError: the download failed (urllib's errors are OSErrors).
    """
    if not is_suno_link(url):
        raise ValueError(f"Not a download link on Suno's hosts: {link_host(url) or 'no host'}")
    if opener is None:
        opener = urllib.request.build_opener(SunoOnlyRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with opener.open(request, timeout=TIMEOUT_S) as response:
        data: bytes = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    return data


def fetch_image(
    url: str, dest_dir: Path, stem: str, *, read: Reader = read_link,
) -> dict[str, Any]:
    """Save the picture behind a Suno download link as ``<dest_dir>/<stem><suffix>``.

    The suffix follows what the file is (``.jpg``, ``.png`` or ``.webp``), not
    what its address says. An existing file is never overwritten.

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
    except (OSError, ValueError) as exc:
        return failed(f"The download failed: {exc}")

    try:
        image_module = _pillow()
        with image_module.open(io.BytesIO(data)) as probe:
            probe.verify()
        with image_module.open(io.BytesIO(data)) as image:
            width, height = image.size
            kind = str(image.format or "")
    except (OSError, SyntaxError, ValueError) as exc:  # UnidentifiedImageError is an OSError
        return failed(f"What Suno sent is not an image: {exc}")

    suffix = _SUFFIX.get(kind)
    if suffix is None:
        return failed(
            f"Suno sent a {kind or 'nameless'} image; a cover is read from a JPEG, a PNG or a WebP",
        )
    target = dest_dir / f"{stem}{suffix}"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as handle:  # "x": never write over an earlier candidate
            handle.write(data)
    except FileExistsError:
        return failed(f"{target.name} is already there; nothing was overwritten")
    except OSError as exc:
        return failed(f"Could not save {target.name}: {exc}")
    return {
        "ok": True, "path": str(target), "width": int(width), "height": int(height), "format": kind,
    }
