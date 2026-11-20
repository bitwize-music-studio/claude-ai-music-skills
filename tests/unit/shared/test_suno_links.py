#!/usr/bin/env python3
"""tools/shared/suno_links.py — which addresses are Suno's.

The plugin's server fetches a link a model hands it in two places: a cover
image and a lyric video. Both go through this check.

Usage:
    python -m pytest tests/unit/shared/test_suno_links.py -v
"""

from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.shared import suno_links

pytestmark = pytest.mark.unit

# The shapes Suno's download links had when they were measured.
IMAGE_LINK = "https://cdn1.suno.ai/visual/c2pa_video_gen_01a1b2c3-0d4e-7f50-8a61-b2c3d4e5f607.jpg"
VIDEO_LINK = (
    "https://suno-data-uploads.s3.amazonaws.com/studio/uploads/visual/"
    "c2pa_video_gen_01a1b2c3-1e2f-7a3b-9c4d-5e6f70819203.mp4"
    "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=3600&X-Amz-Signature=abc123"
)


class TestSunosOwnHosts:
    @pytest.mark.parametrize("url", [
        IMAGE_LINK, "https://suno.com/visual/ast_1", "https://cdn2.suno.ai:443/x.jpg",
    ])
    def test_sunos_domains_count_either_way(self, url):
        assert suno_links.is_suno_link(url) is True
        assert suno_links.is_suno_link(url, files=True) is True

    def test_the_download_bucket_counts_only_when_files_are_asked_for(self):
        assert suno_links.is_suno_link(VIDEO_LINK, files=True) is True
        assert suno_links.is_suno_link(VIDEO_LINK) is False

    @pytest.mark.parametrize("url", [
        "https://another-bucket.s3.amazonaws.com/studio/uploads/x.mp4",
        "https://s3.amazonaws.com/suno-data-uploads/x.mp4",                   # path style: any bucket
        "https://suno-data-uploads.s3.amazonaws.com.example.org/x.mp4",
        "https://xsuno-data-uploads.s3.amazonaws.com/x.mp4",
        "https://suno-data-uploads.s3.amazonaws.com@example.org/x.mp4",
        "http://suno-data-uploads.s3.amazonaws.com/x.mp4",                    # not https
        "https://suno-data-uploads.s3.amazonaws.com:8443/x.mp4",              # not the https port
        "https://suno-data-uploads.s3.amazonaws.com:abc/x.mp4",
        "https://example.org/?to=suno-data-uploads.s3.amazonaws.com",
        "https://notsuno.ai/x.mp4", "file:///etc/passwd", "",
    ])
    def test_nothing_else_on_amazon_or_anywhere_is_sunos(self, url):
        assert suno_links.is_suno_link(url, files=True) is False

    def test_the_host_is_read_without_its_case_or_its_port(self):
        assert suno_links.link_host("https://CDN1.Suno.AI:443/x.jpg") == "cdn1.suno.ai"
        assert suno_links.link_host("not a link") == ""


class TestRedirects:
    def _redirect(self, handler, new_url: str):
        request = urllib.request.Request(IMAGE_LINK)
        return handler.redirect_request(request, io.BytesIO(b""), 302, "Found", {}, new_url)

    def test_a_redirect_to_the_bucket_is_followed_only_for_files(self):
        followed = self._redirect(suno_links.SunoFileRedirects(), VIDEO_LINK)
        assert followed is not None and followed.full_url == VIDEO_LINK
        with pytest.raises(urllib.error.HTTPError):
            self._redirect(suno_links.SunoRedirects(), VIDEO_LINK)

    @pytest.mark.parametrize("handler", [suno_links.SunoRedirects, suno_links.SunoFileRedirects])
    def test_a_redirect_that_leaves_suno_is_refused(self, handler):
        with pytest.raises(urllib.error.HTTPError):
            self._redirect(handler(), "https://example.org/x.mp4")

    @pytest.mark.parametrize(("files", "handler"), [
        (False, suno_links.SunoRedirects), (True, suno_links.SunoFileRedirects),
    ])
    def test_the_opener_carries_the_matching_redirect_rule(self, files, handler):
        handlers = suno_links.opener(files=files).handlers
        assert any(type(found) is handler for found in handlers)
        assert not any(type(found) is urllib.request.HTTPRedirectHandler for found in handlers)
