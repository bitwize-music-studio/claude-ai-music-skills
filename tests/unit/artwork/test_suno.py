#!/usr/bin/env python3
"""tools/artwork/suno.py — a cover made by Suno's image tool.

The plugin's server never calls Suno. This module builds the request the
album-art-director skill sends to Suno's ``image-create`` tool, and saves the
pictures behind the links ``visuals-download`` gives back.

Nothing here touches the network: ``fetch_image`` is handed a reader, and
``read_link`` an opener.

Usage:
    python -m pytest tests/unit/artwork/test_suno.py -v
"""

from __future__ import annotations

import http.client
import io
import struct
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.artwork import suno as suno_art  # noqa: E402

pytestmark = pytest.mark.unit

PROMPT = "A small paper boat on calm teal water at dawn. Flat minimalist illustration."
# The shape of the link Suno's visuals-download gave when it was measured.
LINK = "https://cdn1.suno.ai/visual/c2pa_video_gen_01a1f5e9-09e2-7d3a-89f1-7b081265d258.jpg"


def _image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (1024, 1024)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (30, 120, 130)).save(buffer, fmt)
    return buffer.getvalue()


def _png_claiming(width: int, height: int) -> bytes:
    """A small PNG whose header says it is *width* x *height*, with no pixels behind it."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b"")
    )


# ===========================================================================
# build_request
# ===========================================================================


class TestBuildRequest:
    def test_a_square_image_from_the_prompt(self):
        assert suno_art.build_request(PROMPT) == {"prompt": PROMPT, "aspect": "1:1"}

    def test_things_to_avoid_ride_along_in_the_prompt(self):
        """image-create has one text field, so the negative prompt is a last line of it."""
        request = suno_art.build_request(PROMPT, avoid="  text, watermark ")
        assert request["prompt"] == f"{PROMPT}\n\nAvoid: text, watermark"

    def test_a_model_is_sent_only_when_one_is_set(self):
        assert suno_art.build_request(PROMPT, model="image-1")["model"] == "image-1"
        assert "model" not in suno_art.build_request(PROMPT, model="")

    def test_the_prompt_is_trimmed(self):
        assert suno_art.build_request(f"\n  {PROMPT}\n")["prompt"] == PROMPT


class TestModelName:
    @pytest.mark.parametrize("written", ["image-1", "image-4", " Image-2 ", "video-2"])
    def test_a_model_id_is_kept_in_lower_case(self, written):
        assert suno_art.model_name(written) == written.strip().lower()

    @pytest.mark.parametrize("written", [None, "", 4, True, "image 4", "image-4; rm -rf", "x" * 41, "-image"])
    def test_anything_else_means_sunos_default(self, written):
        assert suno_art.model_name(written) == ""


# ===========================================================================
# is_suno_link
# ===========================================================================


class TestIsSunoLink:
    @pytest.mark.parametrize("url", [
        LINK,
        "https://cdn2.suno.ai/image_large_x.jpeg",
        "https://suno.ai/x.png",
        "https://suno.com/visual/ast_1",
        "https://CDN1.SUNO.AI/visual/x.jpg",
        "https://cdn1.suno.ai:443/visual/x.jpg",
    ])
    def test_an_https_address_on_sunos_hosts(self, url):
        assert suno_art.is_suno_link(url) is True

    @pytest.mark.parametrize("url", [
        "http://cdn1.suno.ai/visual/x.jpg",                 # not https
        "https://notsuno.ai/x.jpg",
        "https://suno.ai.example.org/x.jpg",
        "https://example.org/?next=cdn1.suno.ai/x.jpg",
        "https://cdn1.suno.ai@example.org/x.jpg",           # the host is example.org
        "file:///etc/passwd",
        "ftp://cdn1.suno.ai/x.jpg",
        "cdn1.suno.ai/visual/x.jpg",
        "https://cdn1.suno.ai:8443/visual/x.jpg",           # not the https port
        "https://cdn1.suno.ai:abc/visual/x.jpg",            # a port that is not a number
        "",
    ])
    def test_anything_else_is_not(self, url):
        assert suno_art.is_suno_link(url) is False


# ===========================================================================
# fetch_image
# ===========================================================================


class TestFetchImage:
    def test_the_picture_is_saved_and_its_size_returned(self, tmp_path):
        asked = []

        def read(url):
            asked.append(url)
            return _image_bytes("JPEG", (1024, 1024))

        result = suno_art.fetch_image(LINK, tmp_path, "cover-suno-1", read=read)
        assert result == {
            "ok": True, "path": str(tmp_path / "cover-suno-1.jpg"),
            "width": 1024, "height": 1024, "format": "JPEG",
        }
        assert asked == [LINK]
        with Image.open(tmp_path / "cover-suno-1.jpg") as saved:
            assert saved.size == (1024, 1024)

    @pytest.mark.parametrize(("fmt", "suffix"), [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")])
    def test_the_file_is_named_for_what_it_is_not_for_its_address(self, tmp_path, fmt, suffix):
        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=lambda url: _image_bytes(fmt))
        assert Path(result["path"]).name == f"cover{suffix}"
        assert result["format"] == fmt

    def test_the_folder_is_made_if_it_is_not_there(self, tmp_path):
        dest = tmp_path / "audio" / "artwork-candidates"
        result = suno_art.fetch_image(LINK, dest, "cover", read=lambda url: _image_bytes())
        assert result["ok"] is True and (dest / "cover.jpg").is_file()

    def test_a_link_that_is_not_sunos_is_refused_before_anything_is_fetched(self, tmp_path):
        def read(url):
            raise AssertionError("fetched a link that is not on Suno's hosts")

        result = suno_art.fetch_image("https://example.org/cover.jpg", tmp_path, "cover", read=read)
        assert result["ok"] is False
        assert "example.org" in result["error"]
        assert list(tmp_path.iterdir()) == []

    def test_bytes_that_are_not_an_image_are_an_error_and_leave_no_file(self, tmp_path):
        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=lambda url: b"<html>sign in</html>")
        assert result["ok"] is False and "not an image" in result["error"]
        assert list(tmp_path.iterdir()) == []

    def test_an_image_kind_a_cover_cannot_be_is_an_error(self, tmp_path):
        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=lambda url: _image_bytes("GIF"))
        assert result["ok"] is False and "GIF" in result["error"]
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("failure", [
        OSError("connection reset"), ValueError("larger than 40 MB"),
        urllib.error.URLError("timed out"),
    ])
    def test_a_download_that_fails_is_an_error(self, tmp_path, failure):
        def read(url):
            raise failure

        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=read)
        assert result["ok"] is False
        assert str(failure.args[0]) in result["error"]

    @pytest.mark.parametrize("failure", [
        http.client.IncompleteRead(b"half"), http.client.BadStatusLine("junk"),
        http.client.InvalidURL("nonnumeric port: 'abc'"),
    ])
    def test_a_reply_http_cannot_make_sense_of_is_an_error_too(self, tmp_path, failure):
        """http.client's errors are not OSErrors, and must not escape."""
        def read(url):
            raise failure

        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=read)
        assert result["ok"] is False and "The download failed" in result["error"]
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
    def test_a_picture_cut_short_is_not_a_candidate(self, tmp_path, fmt):
        """A header is not a picture: the file has to decode to its last pixel."""
        whole = _image_bytes(fmt)
        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=lambda url: whole[: len(whole) // 2])
        assert result["ok"] is False and "not an image" in result["error"]
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("size", [(9000, 9000), (30000, 30000)])
    def test_an_image_far_larger_than_a_cover_is_refused_unopened(self, tmp_path, size):
        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=lambda url: _png_claiming(*size))
        assert result["ok"] is False and "too large" in result["error"]
        assert list(tmp_path.iterdir()) == []

    def test_a_save_that_fails_part_way_leaves_nothing_behind(self, tmp_path, monkeypatch):
        def full_disk(fileno):
            raise OSError("No space left on device")

        monkeypatch.setattr(suno_art.os, "fsync", full_disk)
        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=lambda url: _image_bytes())
        assert result["ok"] is False and "No space left" in result["error"]
        assert list(tmp_path.iterdir()) == []

    def test_an_existing_file_is_never_overwritten(self, tmp_path):
        (tmp_path / "cover.jpg").write_bytes(b"the earlier candidate")
        result = suno_art.fetch_image(LINK, tmp_path, "cover", read=lambda url: _image_bytes())
        assert result["ok"] is False and "already" in result["error"]
        assert (tmp_path / "cover.jpg").read_bytes() == b"the earlier candidate"

    @pytest.mark.parametrize("stem", ["../cover", "a/b", "", "cover.png", "cover suno"])
    def test_only_a_plain_name_is_accepted(self, tmp_path, stem):
        result = suno_art.fetch_image(LINK, tmp_path, stem, read=lambda url: _image_bytes())
        assert result["ok"] is False


# ===========================================================================
# read_link
# ===========================================================================


class _Response:
    """A reply that hands its bytes out as asked, and refuses a read with no limit."""

    def __init__(self, data: bytes, endless: bool = False) -> None:
        self._data, self._at, self._endless = data, 0, endless
        self.handed_out = 0

    def read(self, amount: int | None = None) -> bytes:
        assert amount is not None and amount > 0, "read the reply without a limit"
        if self._endless:
            chunk = b"x" * amount
        else:
            chunk = self._data[self._at:self._at + amount]
            self._at += len(chunk)
        self.handed_out += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class _Opener:
    def __init__(self, data: bytes = b"", endless: bool = False) -> None:
        self.response = _Response(data, endless)
        self.requests, self.timeouts = [], []

    def open(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response


class TestReadLink:
    def test_the_bytes_come_back_and_the_wait_is_bounded(self):
        opener = _Opener(b"picture bytes")
        assert suno_art.read_link(LINK, opener=opener) == b"picture bytes"
        assert opener.requests[0].full_url == LINK
        assert opener.timeouts == [suno_art.TIMEOUT_S]

    def test_a_file_past_the_size_limit_is_refused(self, monkeypatch):
        monkeypatch.setattr(suno_art, "MAX_BYTES", 10)
        with pytest.raises(ValueError, match="larger than"):
            suno_art.read_link(LINK, opener=_Opener(b"x" * 11))

    def test_a_file_at_the_size_limit_is_read(self, monkeypatch):
        monkeypatch.setattr(suno_art, "MAX_BYTES", 10)
        assert suno_art.read_link(LINK, opener=_Opener(b"x" * 10)) == b"x" * 10

    def test_a_link_that_is_not_sunos_is_never_opened(self):
        opener = _Opener(b"")
        with pytest.raises(ValueError, match="example.org"):
            suno_art.read_link("https://example.org/x.jpg", opener=opener)
        assert opener.requests == []

    def test_a_reply_that_never_ends_is_cut_off_at_the_limit(self, monkeypatch):
        monkeypatch.setattr(suno_art, "MAX_BYTES", 1000)
        opener = _Opener(endless=True)
        with pytest.raises(ValueError, match="larger than"):
            suno_art.read_link(LINK, opener=opener)
        assert opener.response.handed_out <= 1000 + suno_art.CHUNK_BYTES

    def test_a_reply_that_trickles_in_is_given_up_on(self, monkeypatch):
        ticks = iter([0.0, 1.0, suno_art.TOTAL_TIMEOUT_S + 2.0, suno_art.TOTAL_TIMEOUT_S + 3.0])
        monkeypatch.setattr(suno_art.time, "monotonic", lambda: next(ticks))
        with pytest.raises(ValueError, match="longer than"):
            suno_art.read_link(LINK, opener=_Opener(endless=True))

    def test_without_an_opener_it_uses_the_one_that_stays_on_suno(self, monkeypatch):
        opener = _Opener(b"picture bytes")
        monkeypatch.setattr(suno_art, "default_opener", lambda: opener)
        assert suno_art.read_link(LINK) == b"picture bytes"
        assert len(opener.requests) == 1

    def test_the_default_opener_follows_redirects_only_on_suno(self):
        handlers = suno_art.default_opener().handlers
        assert any(isinstance(handler, suno_art.SunoOnlyRedirects) for handler in handlers)
        plain = [
            handler for handler in handlers
            if type(handler) is urllib.request.HTTPRedirectHandler
        ]
        assert plain == []


class TestRedirects:
    def _redirect(self, new_url: str):
        handler = suno_art.SunoOnlyRedirects()
        request = urllib.request.Request(LINK)
        return handler.redirect_request(request, io.BytesIO(b""), 302, "Found", {}, new_url)

    def test_a_redirect_that_stays_on_suno_is_followed(self):
        followed = self._redirect("https://cdn2.suno.ai/visual/x.jpg")
        assert followed is not None and followed.full_url == "https://cdn2.suno.ai/visual/x.jpg"

    @pytest.mark.parametrize("new_url", [
        "https://example.org/x.jpg", "http://cdn1.suno.ai/x.jpg", "file:///etc/passwd",
    ])
    def test_a_redirect_that_leaves_sunos_hosts_is_refused(self, new_url):
        with pytest.raises(urllib.error.HTTPError):
            self._redirect(new_url)
