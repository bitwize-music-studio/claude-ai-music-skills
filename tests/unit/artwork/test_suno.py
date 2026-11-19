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

import io
import sys
import urllib.error
import urllib.request
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
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, amount: int = -1) -> bytes:
        return self._data if amount < 0 else self._data[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class _Opener:
    def __init__(self, data: bytes) -> None:
        self.data, self.requests, self.timeouts = data, [], []

    def open(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return _Response(self.data)


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
