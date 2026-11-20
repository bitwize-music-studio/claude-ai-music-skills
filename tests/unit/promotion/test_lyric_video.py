#!/usr/bin/env python3
"""tools/promotion/lyric_video.py — a lyric video Suno renders for a track.

Suno's ``video-assemble`` holds stills over a song and burns the words in as
they are sung. This module makes the still Suno is given, builds that tool's
request, saves the MP4 behind the link Suno gives back, and puts the mastered
audio under it.

Nothing here touches the network, and ffmpeg is replaced except in the one
test that says so.

Usage:
    python -m pytest tests/unit/promotion/test_lyric_video.py -v
"""

from __future__ import annotations

import http.client
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.promotion import lyric_video as lv

pytestmark = pytest.mark.unit

SONG = "0c1d2e3f-4a5b-4c6d-8e7f-a0b1c2d3e4f5"
ASSET = "ast_01a1b2c3-0d4e-7f50-8a61-b2c3d4e5f607"
# The shape of the link Suno's visuals-download gave for a video when it was measured.
LINK = (
    "https://suno-data-uploads.s3.amazonaws.com/studio/uploads/visual/"
    "c2pa_video_gen_01a1b2c3-1e2f-7a3b-9c4d-5e6f70819203.mp4?X-Amz-Expires=3600&X-Amz-Signature=abc"
)
RED, BLUE = (220, 30, 30), (30, 30, 220)


def _cover(path: Path, size=(3000, 3000), mode="RGB") -> Path:
    """A cover whose left half is red and right half blue, so its place in a frame can be read."""
    image = Image.new(mode, size, RED if mode == "RGB" else (*RED, 255))
    right = Image.new(mode, (size[0] // 2, size[1]), BLUE if mode == "RGB" else (*BLUE, 255))
    image.paste(right, (size[0] // 2, 0))
    image.save(path, "PNG")
    return path


def _near(pixel, colour, slack=40) -> bool:
    return all(abs(a - b) <= slack for a, b in zip(pixel[:3], colour, strict=True))


# ===========================================================================
# Shapes
# ===========================================================================


class TestShapes:
    @pytest.mark.parametrize(("written", "shape"), [
        ("16:9", "16:9"), ("16x9", "16:9"), (" 9:16 ", "9:16"), ("1X1", "1:1"), ("", "16:9"), (None, "16:9"),
    ])
    def test_a_shape_is_read_loosely(self, written, shape):
        assert lv.normal_shape(written) == shape

    @pytest.mark.parametrize("written", ["4:3", "wide", "16:10", 169])
    def test_a_shape_suno_does_not_make_is_none(self, written):
        assert lv.normal_shape(written) is None

    def test_a_shape_as_part_of_a_file_name(self):
        assert [lv.shape_slug(shape) for shape in ("16:9", "1:1", "9:16")] == ["16x9", "1x1", "9x16"]


# ===========================================================================
# prepare_still
# ===========================================================================


class TestPrepareStill:
    def test_a_wide_still_holds_the_whole_cover_in_the_middle(self, tmp_path):
        info = lv.prepare_still(_cover(tmp_path / "album.png"), tmp_path / "out" / "still.jpg", "16:9")
        assert (info["width"], info["height"]) == (1920, 1080)
        assert info["content_type"] == "image/jpeg"
        assert info["path"] == str(tmp_path / "out" / "still.jpg")
        with Image.open(info["path"]) as still:
            assert still.format == "JPEG" and still.size == (1920, 1080)
            # the cover is 1080 wide, centred: red left of the middle, blue right of it
            assert _near(still.getpixel((960 - 300, 540)), RED)
            assert _near(still.getpixel((960 + 300, 540)), BLUE)
            # beside it is the cover again, blurred and darkened, not a black bar
            edge = still.getpixel((60, 540))
            assert edge[0] > 40 and not _near(edge, RED)

    def test_a_square_still_is_just_the_cover(self, tmp_path):
        info = lv.prepare_still(_cover(tmp_path / "album.png"), tmp_path / "still.jpg", "1:1")
        assert (info["width"], info["height"]) == (1080, 1080)
        with Image.open(info["path"]) as still:
            assert _near(still.getpixel((30, 540)), RED) and _near(still.getpixel((1050, 540)), BLUE)

    def test_a_tall_still_holds_the_cover_in_the_middle(self, tmp_path):
        info = lv.prepare_still(_cover(tmp_path / "album.png"), tmp_path / "still.jpg", "9:16")
        assert (info["width"], info["height"]) == (1080, 1920)
        with Image.open(info["path"]) as still:
            assert _near(still.getpixel((200, 960)), RED) and _near(still.getpixel((880, 960)), BLUE)
            top = still.getpixel((200, 80))
            assert top[0] > 40 and not _near(top, RED)

    def test_it_fits_under_sunos_upload_limit_and_says_its_size(self, tmp_path):
        info = lv.prepare_still(_cover(tmp_path / "album.png"), tmp_path / "still.jpg", "16:9")
        assert info["bytes"] == (tmp_path / "still.jpg").stat().st_size
        assert 0 < info["bytes"] < 10 * 1024 * 1024

    def test_a_cover_with_transparency_is_flattened(self, tmp_path):
        info = lv.prepare_still(_cover(tmp_path / "album.png", mode="RGBA"), tmp_path / "still.jpg", "1:1")
        with Image.open(info["path"]) as still:
            assert still.mode == "RGB"

    def test_a_cover_that_is_not_square_is_fitted_not_stretched(self, tmp_path):
        info = lv.prepare_still(_cover(tmp_path / "wide.png", size=(1600, 800)), tmp_path / "still.jpg", "1:1")
        with Image.open(info["path"]) as still:
            assert still.size == (1080, 1080)
            assert _near(still.getpixel((270, 540)), RED) and _near(still.getpixel((810, 540)), BLUE)
            assert not _near(still.getpixel((270, 60)), RED)   # above the cover is backdrop

    def test_a_cover_turned_by_its_exif_tag_is_shown_the_way_it_is_viewed(self, tmp_path):
        """Stored 800x400, tagged 'rotate 90 CW': viewed, it is tall, red above blue."""
        stored = _cover(tmp_path / "phone.png", size=(800, 400))
        with Image.open(stored) as image:
            exif = Image.Exif()
            exif[0x0112] = 6
            image.convert("RGB").save(tmp_path / "phone.jpg", "JPEG", quality=95, exif=exif)
        info = lv.prepare_still(tmp_path / "phone.jpg", tmp_path / "still.jpg", "1:1")
        with Image.open(info["path"]) as still:
            assert _near(still.getpixel((540, 200)), RED, 40)
            assert _near(still.getpixel((540, 880)), BLUE, 40)
            assert not _near(still.getpixel((100, 540)), RED, 40)     # beside it is backdrop

    def test_a_long_thin_cover_does_not_blow_the_backdrop_up(self, tmp_path, monkeypatch):
        """Enlarged whole to cover a 9:16 frame, a 4000x40 cover would be 192,000 pixels wide."""
        sizes = []
        resize = Image.Image.resize

        def spy(self, size, *args, **kwargs):
            sizes.append(tuple(size))
            return resize(self, size, *args, **kwargs)

        monkeypatch.setattr(Image.Image, "resize", spy)
        info = lv.prepare_still(_cover(tmp_path / "strip.png", size=(4000, 40)), tmp_path / "still.jpg", "9:16")
        assert (info["width"], info["height"]) == (1080, 1920)
        assert sizes and max(max(size) for size in sizes) <= 4000

    def test_a_cover_too_large_to_open_safely_is_an_error_not_a_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
        with pytest.raises(ValueError, match=r"big\.png"):
            lv.prepare_still(_cover(tmp_path / "big.png", size=(100, 100)), tmp_path / "still.jpg", "1:1")
        assert not (tmp_path / "still.jpg").exists()

    def test_an_earlier_still_is_replaced(self, tmp_path):
        target = tmp_path / "still.jpg"
        target.write_bytes(b"old")
        lv.prepare_still(_cover(tmp_path / "album.png"), target, "1:1")
        with Image.open(target) as still:
            assert still.size == (1080, 1080)

    def test_a_missing_cover_or_an_unknown_shape_is_an_error(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            lv.prepare_still(tmp_path / "nope.png", tmp_path / "still.jpg", "16:9")
        with pytest.raises(ValueError, match="4:3"):
            lv.prepare_still(_cover(tmp_path / "album.png"), tmp_path / "still.jpg", "4:3")
        (tmp_path / "junk.png").write_bytes(b"not an image")
        with pytest.raises(ValueError, match="could not be read as an image"):
            lv.prepare_still(tmp_path / "junk.png", tmp_path / "still.jpg", "16:9")


# ===========================================================================
# build_request
# ===========================================================================


class TestBuildRequest:
    def test_a_short_song_is_one_still(self):
        request = lv.build_request(SONG, ASSET, 55.16, "16:9")
        assert request == {
            "song_id": SONG, "lyrics": True, "aspect": "16:9",
            "clips": [{"asset_id": ASSET, "duration_s": 55.16}],
        }

    @pytest.mark.parametrize(("duration", "count"), [
        (60, 1), (60.01, 2), (120, 2), (120.2, 3), (205.8, 4), (2400, 40),
    ])
    def test_a_longer_song_is_as_few_stills_as_fit_under_a_minute_each(self, duration, count):
        clips = lv.build_request(SONG, ASSET, duration, "1:1")["clips"]
        assert len(clips) == count
        assert all(0 < clip["duration_s"] <= 60 for clip in clips)
        assert {clip["asset_id"] for clip in clips} == {ASSET}
        # held for exactly the song: a still that outlasts it leaves silence at the end
        assert round(sum(clip["duration_s"] for clip in clips), 2) == duration

    def test_the_stills_are_even_so_none_is_a_sliver(self):
        clips = lv.build_request(SONG, ASSET, 120.2, "1:1")["clips"]
        assert min(clip["duration_s"] for clip in clips) > 40

    @pytest.mark.parametrize("duration", [0, -3, 2400.5, float("nan"), float("inf")])
    def test_a_length_suno_cannot_take_is_an_error(self, duration):
        with pytest.raises(ValueError):
            lv.build_request(SONG, ASSET, duration, "16:9")

    def test_an_unknown_shape_is_an_error(self):
        with pytest.raises(ValueError, match="4:3"):
            lv.build_request(SONG, ASSET, 55, "4:3")


# ===========================================================================
# download_video
# ===========================================================================


class _Response:
    """A reply as http.client hands it out: ``read1`` gives what one raw read got.

    ``read(n)`` is refused: it loops until it has n bytes, so a reply that
    drips in would hold it long past the deadline.
    """

    def __init__(
        self, data: bytes = b"", endless: bool = False, fail_after: int | None = None,
        piece: int | None = None, stated: int | None = None, on_read=None,
    ) -> None:
        self._data, self._at, self._endless, self._fail_after = data, 0, endless, fail_after
        self._piece, self._on_read = piece, on_read
        self.handed_out = 0
        self.reads = 0
        self.headers = {} if stated is None else {"Content-Length": str(stated)}

    def read(self, amount: int | None = None) -> bytes:
        raise AssertionError("read() waits until the amount is full; use read1()")

    def read1(self, amount: int = -1) -> bytes:
        assert amount is not None and amount > 0, "read the reply without a limit"
        self.reads += 1
        if self._on_read:
            self._on_read()
        if self._fail_after is not None and self.handed_out >= self._fail_after:
            raise ConnectionResetError("connection reset by peer")
        amount = min(amount, self._piece or amount)
        chunk = b"x" * amount if self._endless else self._data[self._at:self._at + amount]
        self._at += len(chunk)
        self.handed_out += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class _Opener:
    def __init__(self, **kwargs) -> None:
        self.response = _Response(**kwargs)
        self.requests, self.timeouts = [], []

    def open(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response


class TestDownloadVideo:
    def test_the_file_is_written_and_its_size_returned(self, tmp_path):
        data = b"\x00\x00\x00\x20ftypisom" + b"v" * 200_000
        opener = _Opener(data=data)
        dest = tmp_path / "videos" / "track.part"
        assert lv.download_video(LINK, dest, opener=opener) == len(data)
        assert dest.read_bytes() == data
        assert opener.requests[0].full_url == LINK
        assert opener.timeouts == [lv.TIMEOUT_S]

    def test_a_link_that_is_not_sunos_is_never_opened(self, tmp_path):
        opener = _Opener(data=b"x")
        with pytest.raises(ValueError, match=r"example\.org"):
            lv.download_video("https://example.org/video.mp4", tmp_path / "track.part", opener=opener)
        assert opener.requests == [] and list(tmp_path.iterdir()) == []

    def test_a_reply_that_never_ends_is_cut_off_and_leaves_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lv, "MAX_VIDEO_BYTES", 500_000)
        opener = _Opener(endless=True)
        with pytest.raises(ValueError, match="larger than"):
            lv.download_video(LINK, tmp_path / "track.part", opener=opener)
        assert opener.response.handed_out <= 500_000 + lv.CHUNK_BYTES
        assert list(tmp_path.iterdir()) == []

    def test_a_reply_that_trickles_in_is_given_up_on(self, tmp_path, monkeypatch):
        ticks = iter([0.0, 1.0, lv.TOTAL_TIMEOUT_S + 2.0, lv.TOTAL_TIMEOUT_S + 3.0])
        monkeypatch.setattr(lv.time, "monotonic", lambda: next(ticks))
        with pytest.raises(ValueError, match="longer than"):
            lv.download_video(LINK, tmp_path / "track.part", opener=_Opener(endless=True))
        assert list(tmp_path.iterdir()) == []

    def test_a_connection_that_breaks_leaves_nothing(self, tmp_path):
        with pytest.raises(OSError, match="reset"):
            lv.download_video(LINK, tmp_path / "track.part", opener=_Opener(endless=True, fail_after=100_000))
        assert list(tmp_path.iterdir()) == []

    def test_a_reply_that_stops_short_of_its_stated_length_is_refused(self, tmp_path):
        """A dropped connection ends the reply quietly: read1 just returns nothing."""
        half = b"\x00\x00\x00\x20ftypisom" + b"v" * 100_000
        opener = _Opener(data=half, stated=len(half) * 2)
        with pytest.raises(ValueError, match="stopped"):
            lv.download_video(LINK, tmp_path / "track.part", opener=opener)
        assert list(tmp_path.iterdir()) == []

    def test_a_reply_of_its_stated_length_is_kept(self, tmp_path):
        data = b"\x00\x00\x00\x20ftypisom" + b"v" * 5000
        dest = tmp_path / "track.part"
        assert lv.download_video(LINK, dest, opener=_Opener(data=data, stated=len(data))) == len(data)
        assert dest.read_bytes() == data

    def test_a_stated_length_that_cannot_be_read_is_not_held_against_the_reply(self, tmp_path):
        opener = _Opener(data=b"video")
        opener.response.headers = {"Content-Length": "soon"}
        assert lv.download_video(LINK, tmp_path / "track.part", opener=opener) == 5

    def test_the_deadline_is_checked_between_raw_reads(self, tmp_path, monkeypatch):
        """A reply that drips a little every few seconds is given up on, not waited out."""
        clock = {"now": 0.0}
        monkeypatch.setattr(lv.time, "monotonic", lambda: clock["now"])

        def tick():
            clock["now"] += 30.0

        opener = _Opener(endless=True, piece=1024, on_read=tick)
        with pytest.raises(ValueError, match="longer than"):
            lv.download_video(LINK, tmp_path / "track.part", opener=opener)
        assert opener.response.reads <= lv.TOTAL_TIMEOUT_S / 30 + 2
        assert opener.response.handed_out < lv.CHUNK_BYTES
        assert list(tmp_path.iterdir()) == []

    def test_without_an_opener_it_uses_one_that_stays_on_suno(self, tmp_path, monkeypatch):
        opener = _Opener(data=b"video")
        seen = {}

        def make(*, files=False):
            seen["files"] = files
            return opener

        monkeypatch.setattr(lv.suno_links, "opener", make)
        assert lv.download_video(LINK, tmp_path / "track.part") == 5
        assert seen == {"files": True}


# ===========================================================================
# probe and swap_audio
# ===========================================================================


def _done(stdout: str = "", returncode: int = 0, stderr: str = ""):
    return types.SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)


PROBE_VIDEO = json.dumps({
    "format": {"duration": "55.200000"},
    "streams": [
        {"codec_type": "video", "width": 1920, "height": 1080},
        {"codec_type": "audio"},
    ],
})


class TestProbe:
    def test_a_video_file(self, tmp_path):
        calls = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return _done(PROBE_VIDEO)

        info = lv.probe(tmp_path / "v.mp4", run=run)
        assert info == {"duration_s": 55.2, "video": True, "audio": True, "width": 1920, "height": 1080}
        assert calls[0][0][0] == "ffprobe" and str(tmp_path / "v.mp4") in calls[0][0]
        assert calls[0][1].get("timeout")

    def test_an_audio_file_has_no_picture(self):
        only_audio = json.dumps({"format": {"duration": "55.16"}, "streams": [{"codec_type": "audio"}]})
        info = lv.probe(Path("m.wav"), run=lambda cmd, **kw: _done(only_audio))
        assert info == {"duration_s": 55.16, "video": False, "audio": True, "width": None, "height": None}

    @pytest.mark.parametrize("run", [
        lambda cmd, **kw: _done("", returncode=1, stderr="Invalid data found"),
        lambda cmd, **kw: _done("not json"),
        lambda cmd, **kw: _done(json.dumps({"format": {}, "streams": []})),
    ])
    def test_a_file_ffprobe_cannot_read_is_an_error(self, run):
        with pytest.raises(ValueError):
            lv.probe(Path("v.mp4"), run=run)

    def test_counting_says_how_many_of_the_pictures_frames_are_really_there(self, tmp_path):
        counted = json.dumps({"format": {"duration": "20.0"}, "streams": [
            {"codec_type": "video", "width": 320, "height": 180, "nb_frames": "600", "nb_read_packets": "270"},
            {"codec_type": "audio", "nb_frames": "861", "nb_read_packets": "400"},
        ]})
        calls = []

        def run(cmd, **kwargs):
            calls.append(cmd)
            return _done(counted)

        info = lv.probe(tmp_path / "v.mp4", count=True, run=run)
        assert "-count_packets" in calls[0]
        assert (info["frames"], info["packets"]) == (600, 270)
        assert info["duration_s"] == 20.0 and info["video"] is True

    def test_a_count_ffprobe_does_not_give_is_none(self, tmp_path):
        bare = json.dumps({"format": {"duration": "20.0"}, "streams": [
            {"codec_type": "video", "width": 320, "height": 180, "nb_frames": "N/A"},
        ]})
        info = lv.probe(tmp_path / "v.mp4", count=True, run=lambda cmd, **kw: _done(bare))
        assert info["frames"] is None and info["packets"] is None

    def test_it_does_not_count_unless_asked(self, tmp_path):
        calls = []

        def run(cmd, **kwargs):
            calls.append(cmd)
            return _done(PROBE_VIDEO)

        info = lv.probe(tmp_path / "v.mp4", run=run)
        assert "-count_packets" not in calls[0] and "frames" not in info

    def test_no_ffprobe_is_an_error_that_says_so(self):
        def run(cmd, **kwargs):
            raise FileNotFoundError("ffprobe")

        with pytest.raises(ValueError, match="ffprobe"):
            lv.probe(Path("v.mp4"), run=run)


class TestSwapAudio:
    def test_the_picture_is_copied_and_the_master_goes_under_it(self, tmp_path):
        calls = []

        def run(cmd, **kwargs):
            calls.append(cmd)
            Path(cmd[-1]).write_bytes(b"muxed")
            return _done()

        lv.swap_audio(tmp_path / "v.mp4", tmp_path / "m.wav", tmp_path / "out.mp4", run=run)
        cmd = calls[0]
        assert cmd[0] == "ffmpeg" and cmd[-1] == str(tmp_path / "out.mp4")
        text = " ".join(cmd)
        assert "-map 0:v:0" in text and "-map 1:a:0" in text
        assert "-c:v copy" in text            # the burned-in words are not re-encoded
        assert "-shortest" in text

    def test_a_failed_mux_is_an_error_and_leaves_nothing(self, tmp_path):
        def run(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"half")
            return _done(returncode=1, stderr="Conversion failed!")

        with pytest.raises(ValueError, match="Conversion failed"):
            lv.swap_audio(tmp_path / "v.mp4", tmp_path / "m.wav", tmp_path / "out.mp4", run=run)
        assert not (tmp_path / "out.mp4").exists()


# ===========================================================================
# finish
# ===========================================================================


def _mp4(path: Path) -> Path:
    path.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"v" * 1000)
    return path


class TestFinish:
    def _finish(self, tmp_path, *, video_s=55.2, master_s=None, has_video=True, frames=None, packets=None):
        downloaded = _mp4(tmp_path / "track.part")
        dest = tmp_path / "track-16x9.mp4"
        master = None
        if master_s is not None:
            master = tmp_path / "master.wav"
            master.write_bytes(b"RIFF")
        swaps = []
        self.probed = []

        def probe(path, **kwargs):
            self.probed.append((Path(path).name, kwargs))
            if path == master:
                return {"duration_s": master_s, "video": False, "audio": True, "width": None, "height": None}
            return {"duration_s": video_s, "video": has_video, "audio": True,
                    "width": 1920 if has_video else None, "height": 1080 if has_video else None,
                    "frames": frames, "packets": packets}

        def swap(video, audio, out, **kwargs):
            swaps.append((video, audio, out))
            Path(out).write_bytes(b"with the master")

        return lv.finish(downloaded, dest, master, probe=probe, swap=swap), swaps, downloaded, dest

    def test_without_a_master_the_file_is_kept_as_suno_made_it(self, tmp_path):
        info, swaps, downloaded, dest = self._finish(tmp_path)
        assert swaps == []
        assert dest.read_bytes().startswith(b"\x00\x00\x00\x20ftyp") and not downloaded.exists()
        assert info["audio"] == "suno"
        assert info["path"] == str(dest)
        assert (info["width"], info["height"], info["duration_s"]) == (1920, 1080, 55.2)
        assert info["bytes"] == dest.stat().st_size

    @pytest.mark.parametrize("master_s", [55.2, 55.4, 55.0])
    def test_a_master_of_the_same_length_goes_under_the_picture(self, tmp_path, master_s):
        info, swaps, downloaded, dest = self._finish(tmp_path, master_s=master_s)
        assert len(swaps) == 1
        assert dest.read_bytes() == b"with the master" and not downloaded.exists()
        assert info["audio"] == "master" and info["audio_note"] == ""

    @pytest.mark.parametrize("master_s", [52.0, 58.5, 54.8, 55.6])
    def test_a_master_of_another_length_is_left_out_and_it_says_why(self, tmp_path, master_s):
        """The words are timed to the take: under audio of another length they would drift.

        Half a second of silence put before a master is enough to see.
        """
        info, swaps, _downloaded, dest = self._finish(tmp_path, master_s=master_s)
        assert swaps == []
        assert info["audio"] == "suno"
        assert f"{master_s:g}" in info["audio_note"] and "55.2" in info["audio_note"]
        assert dest.read_bytes().startswith(b"\x00\x00\x00\x20ftyp")

    def test_a_video_with_frames_missing_is_refused_and_removed(self, tmp_path):
        """A download cut short still states its full length; its frames give it away."""
        with pytest.raises(ValueError, match="stops early"):
            self._finish(tmp_path, frames=600, packets=270, master_s=55.2)
        assert list(tmp_path.glob("track*")) == []

    @pytest.mark.parametrize(("frames", "packets"), [(600, 600), (600, 599), (None, None), (600, None)])
    def test_a_video_with_its_frames_is_kept(self, tmp_path, frames, packets):
        info, _swaps, _downloaded, dest = self._finish(tmp_path, frames=frames, packets=packets)
        assert dest.is_file() and info["audio"] == "suno"

    def test_only_the_download_is_counted(self, tmp_path):
        self._finish(tmp_path, master_s=55.2)
        assert self.probed[0] == ("track.part", {"count": True})
        assert all(not kwargs.get("count") for name, kwargs in self.probed if name == "master.wav")

    def test_a_download_with_no_picture_in_it_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="no picture"):
            self._finish(tmp_path, has_video=False)
        assert not (tmp_path / "track-16x9.mp4").exists()
        assert not (tmp_path / "track.part").exists()

    def test_a_download_that_is_not_an_mp4_is_refused_before_ffmpeg_sees_it(self, tmp_path):
        downloaded = tmp_path / "track.part"
        downloaded.write_bytes(b"<html>sign in</html>" * 10)

        def probe(path, **kwargs):
            raise AssertionError("probed a file that is not an MP4")

        with pytest.raises(ValueError, match="not an MP4"):
            lv.finish(downloaded, tmp_path / "out.mp4", None, probe=probe)
        assert not downloaded.exists()

    def test_without_ffmpeg_the_video_is_kept_unchecked_and_it_says_so(self, tmp_path):
        """A machine with no ffmpeg still gets the file Suno made."""
        downloaded = _mp4(tmp_path / "track.part")
        master = tmp_path / "master.wav"
        master.write_bytes(b"RIFF")

        def probe(path, **kwargs):
            raise lv.ToolMissing("ffprobe is not installed, so the video cannot be checked")

        info = lv.finish(downloaded, tmp_path / "out.mp4", master, probe=probe)
        assert (tmp_path / "out.mp4").read_bytes().startswith(b"\x00\x00\x00\x20ftyp")
        assert info["audio"] == "suno" and "ffprobe" in info["audio_note"]
        assert info["duration_s"] is None and info["width"] is None

    def test_a_swap_that_fails_keeps_sunos_audio_and_says_so(self, tmp_path):
        downloaded = _mp4(tmp_path / "track.part")
        master = tmp_path / "master.wav"
        master.write_bytes(b"RIFF")

        def probe(path, **kwargs):
            return {"duration_s": 55.2, "video": path != master, "audio": True, "width": 1920, "height": 1080}

        def swap(video, audio, out, **kwargs):
            raise ValueError("ffmpeg could not put the master under the video: Conversion failed!")

        info = lv.finish(downloaded, tmp_path / "out.mp4", master, probe=probe, swap=swap)
        assert info["audio"] == "suno" and "Conversion failed" in info["audio_note"]
        assert (tmp_path / "out.mp4").read_bytes().startswith(b"\x00\x00\x00\x20ftyp")


# ===========================================================================
# With the real ffmpeg, where there is one
# ===========================================================================


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="needs ffmpeg and ffprobe",
)
class TestWithRealFfmpeg:
    def test_a_real_video_gets_the_master_under_it(self, tmp_path):
        video, master = tmp_path / "track.part", tmp_path / "master.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=teal:s=320x180:d=2",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest",
             "-pix_fmt", "yuv420p", "-f", "mp4", str(video)],
            check=True, timeout=120,
        )
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=2", str(master)],
            check=True, timeout=120,
        )
        info = lv.finish(video, tmp_path / "out.mp4", master)
        assert info["audio"] == "master"
        result = lv.probe(tmp_path / "out.mp4")
        assert result["video"] and result["audio"]
        assert (result["width"], result["height"]) == (320, 180)
        assert abs(result["duration_s"] - 2.0) < 0.3


    def test_a_real_video_cut_off_halfway_is_refused(self, tmp_path):
        """Faststart puts the index first, so half the file still claims the whole length."""
        whole, video = tmp_path / "whole.mp4", tmp_path / "track.part"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=6",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-shortest",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-f", "mp4", str(whole)],
            check=True, timeout=120,
        )
        data = whole.read_bytes()
        video.write_bytes(data[: len(data) // 2])
        assert abs(lv.probe(video)["duration_s"] - 6.0) < 0.3      # it still says six seconds
        with pytest.raises(ValueError, match="stops early"):
            lv.finish(video, tmp_path / "out.mp4", None)
        assert not video.exists() and not (tmp_path / "out.mp4").exists()

    def test_a_whole_real_video_passes_the_count(self, tmp_path):
        video = tmp_path / "track.part"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=2",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-f", "mp4", str(video)],
            check=True, timeout=120,
        )
        info = lv.finish(video, tmp_path / "out.mp4", None)
        assert info["audio"] == "suno" and (tmp_path / "out.mp4").is_file()
