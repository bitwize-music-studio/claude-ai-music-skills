"""Which addresses are Suno's.

The plugin's server never calls Suno, but it does fetch a download link a model
hands it in two places: a cover image (``tools/artwork/suno.py``) and a lyric
video (``tools/promotion/lyric_video.py``). A link is fetched only when this
module says it is Suno's, and a redirect is followed only while it stays so.

Measured: an image's link was on ``cdn1.suno.ai``; an MP3's and two MP4s' were
signed addresses on ``suno-data-uploads.s3.amazonaws.com``.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

# Suno serves pages from suno.com and images from suno.ai, on the https port.
SUNO_DOMAINS = ("suno.ai", "suno.com")
# The bucket Suno signs audio and video downloads from. An exact host: nothing
# else on amazonaws.com is Suno's, and a path-style address could name any bucket.
SUNO_FILE_HOSTS = ("suno-data-uploads.s3.amazonaws.com",)
_PORTS = (None, 443)


def link_host(url: str) -> str:
    """The host a link points at, lower-cased; ``""`` when it has none."""
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_suno_link(url: str, *, files: bool = False) -> bool:
    """Whether *url* is an https address on one of Suno's hosts, on the https port.

    With *files*, the bucket Suno signs audio and video downloads from counts
    too. Decided by the parsed scheme, host and port, never by where "suno"
    appears in the text, so ``suno.ai.example.org`` and
    ``cdn1.suno.ai@example.org`` are not Suno's.
    """
    try:
        parsed = urlparse(url)
        port = parsed.port  # raises for a port that is not a number
    except ValueError:
        return False
    if parsed.scheme != "https" or port not in _PORTS:
        return False
    host = link_host(url)
    if any(host == domain or host.endswith(f".{domain}") for domain in SUNO_DOMAINS):
        return True
    return files and host in SUNO_FILE_HOSTS


class SunoRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only while it stays on Suno's own hosts, over https."""

    files = False

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str,
    ) -> urllib.request.Request | None:
        if not is_suno_link(newurl, files=self.files):
            raise urllib.error.HTTPError(
                newurl, code, "the download was redirected away from Suno's hosts", headers, fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SunoFileRedirects(SunoRedirects):
    """The same, with Suno's download bucket allowed as well."""

    files = True


def opener(*, files: bool = False) -> urllib.request.OpenerDirector:
    """An opener whose redirects stay on Suno's hosts."""
    return urllib.request.build_opener(SunoFileRedirects if files else SunoRedirects)
