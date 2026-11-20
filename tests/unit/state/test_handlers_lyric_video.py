#!/usr/bin/env python3
"""handlers/lyric_video.py — a lyric video for a track, rendered by Suno.

    get_lyric_video_plan(album, track, shape, asset_id, duration_s)  — what will be made, and the request
    prepare_lyric_video_still(album, shape)                          — the picture Suno is given
    save_lyric_video(album, track, link, ...)                        — the MP4 Suno made, beside the audio

None of them talks to Suno: the lyric-video skill calls Suno's video-assemble
and hands the link back. Nothing is fetched here; the download and ffmpeg are
replaced. The track-file builder and the album fixture come from
test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_lyric_video.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: F401  (album is a fixture)
    CLIP_A,
    CLIP_B,
    LEGACY_KEEPER_ROW,
    _row,
    _run,
    album,
    server,
)

from handlers import lyric_video as handler

pytestmark = pytest.mark.unit

ASSET = "ast_01a1b2c3-0d4e-7f50-8a61-b2c3d4e5f607"
LINK = (
    "https://suno-data-uploads.s3.amazonaws.com/studio/uploads/visual/"
    "c2pa_video_gen_01a1b2c3-1e2f-7a3b-9c4d-5e6f70819203.mp4?X-Amz-Expires=3600&X-Amz-Signature=abc"
)
KEEPER = f"[Listen](https://suno.com/song/{CLIP_A})"


def _plan(track="01-first-track", **kwargs):
    return json.loads(_run(handler.get_lyric_video_plan("test-album", track, **kwargs)))


def _still(**kwargs):
    return json.loads(_run(handler.prepare_lyric_video_still("test-album", **kwargs)))


def _save(link=LINK, track="01-first-track", **kwargs):
    return json.loads(_run(handler.save_lyric_video("test-album", track, link, **kwargs)))


def _codes(result, severity=None):
    return [p["code"] for p in result["problems"] if severity is None or p["severity"] == severity]


def _image(path: Path, size=(3000, 3000), fmt="PNG") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (30, 120, 130)).save(path, fmt)
    return path


@pytest.fixture
def track(album, monkeypatch):  # noqa: F811
    """The album fixture with an approved take, a cover and ffmpeg on the path."""
    album(suno_link=KEEPER, log_rows=(_row(1, CLIP_A, "✓"), _row(2, CLIP_B)), status="Final")
    _image(album.audio_dir / "album.png")
    monkeypatch.setattr(handler.shutil, "which", lambda name: f"/usr/bin/{name}")
    return album


# ===========================================================================
# get_lyric_video_plan
# ===========================================================================


class TestPlan:
    def test_a_track_with_a_keeper_and_a_cover(self, track):
        plan = _plan()
        assert plan["found"] is True
        assert (plan["album_slug"], plan["track_slug"], plan["title"]) == (
            "test-album", "01-first-track", "First Track",
        )
        assert plan["shape"] == "16:9"
        assert plan["song"] == {"clip_id": CLIP_A, "source": "suno_link"}
        assert plan["cover"] == str(track.audio_dir / "album.png")
        assert plan["still"] == {"path": str(track.audio_dir / "lyric_videos" / "stills" / "test-album-16x9.jpg")}
        assert plan["output"] == {
            "path": str(track.audio_dir / "lyric_videos" / "01-first-track-16x9.mp4"), "exists": False,
        }
        assert plan["request"] is None
        assert plan["ffmpeg"] is True
        assert _codes(plan, "blocking") == []
        assert plan["ready"] is True

    def test_it_says_the_video_will_carry_sunos_audio_while_there_is_no_master(self, track):
        plan = _plan()
        assert plan["master"] is None
        assert _codes(plan, "warning") == ["no_master"]

    def test_the_master_is_named_when_there_is_one(self, track):
        master = track.audio_dir / "mastered" / "01-first-track.wav"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"RIFF")
        plan = _plan()
        assert plan["master"] == {"path": str(master)}
        assert "no_master" not in _codes(plan)

    @pytest.mark.parametrize(("written", "shape", "slug"), [
        ("9x16", "9:16", "9x16"), ("1:1", "1:1", "1x1"), ("", "16:9", "16x9"),
    ])
    def test_the_shape_names_the_files(self, track, written, shape, slug):
        plan = _plan(shape=written)
        assert plan["shape"] == shape
        assert plan["output"]["path"].endswith(f"01-first-track-{slug}.mp4")
        assert plan["still"]["path"].endswith(f"test-album-{slug}.jpg")

    def test_a_shape_suno_does_not_make_is_an_error(self, track):
        result = _plan(shape="4:3")
        assert "error" in result and "4:3" in result["error"]

    def test_a_track_number_finds_the_track(self, track):
        assert _plan("01")["track_slug"] == "01-first-track"

    def test_no_approved_take_blocks(self, album):  # noqa: F811
        _image(album.audio_dir / "album.png")
        plan = _plan()
        assert _codes(plan, "blocking") == ["no_keeper"]
        assert plan["song"] is None and plan["ready"] is False

    def test_a_share_link_from_before_mcp_generation_blocks(self, album):  # noqa: F811
        album(suno_link="[Keeper](https://suno.com/s/4hZKwZySCc8Lc63Q)", log_rows=(LEGACY_KEEPER_ROW,))
        _image(album.audio_dir / "album.png")
        assert _codes(_plan(), "blocking") == ["legacy_link"]

    def test_an_instrumental_track_has_no_words_to_show(self, track):
        track(suno_link=KEEPER, log_rows=(_row(1, CLIP_A, "✓"),), instrumental_fm="true",
              instrumental_table="Yes")
        plan = _plan()
        assert _codes(plan, "blocking") == ["instrumental"]
        assert plan["ready"] is False

    def test_no_cover_blocks_unless_an_image_already_on_suno_is_named(self, track):
        (track.audio_dir / "album.png").unlink()
        plan = _plan()
        assert _codes(plan, "blocking") == ["no_cover"]
        assert plan["cover"] is None and plan["ready"] is False
        named = _plan(asset_id=ASSET)
        assert "no_cover" not in _codes(named) and named["ready"] is True

    @pytest.mark.parametrize("name", ["album.jpg", "album.jpeg"])
    def test_an_older_albums_jpeg_cover_is_found(self, track, name):
        (track.audio_dir / "album.png").unlink()
        _image(track.audio_dir / name, fmt="JPEG")
        assert _plan()["cover"] == str(track.audio_dir / name)

    def test_the_cover_in_the_album_folder_serves_when_the_audio_folder_has_none(self, track):
        (track.audio_dir / "album.png").unlink()
        art = _image(track.path.parent.parent / "album-art.png")
        assert _plan()["cover"] == str(art)

    def test_the_request_comes_once_the_image_and_the_songs_length_are_known(self, track):
        plan = _plan(asset_id=ASSET, duration_s=205.8)
        assert plan["request"] == handler.lv.build_request(CLIP_A, ASSET, 205.8, "16:9")
        assert plan["request"]["song_id"] == CLIP_A and plan["request"]["lyrics"] is True
        assert len(plan["request"]["clips"]) == 4

    def test_one_of_the_two_alone_gives_no_request(self, track):
        assert _plan(asset_id=ASSET)["request"] is None
        assert _plan(duration_s=205.8)["request"] is None

    @pytest.mark.parametrize(("kwargs", "fragment"), [
        ({"asset_id": "../etc/passwd", "duration_s": 60}, "asset"),
        ({"asset_id": ASSET, "duration_s": 2500}, "2500"),
        ({"asset_id": ASSET, "duration_s": -1}, "length"),
    ])
    def test_a_request_that_cannot_be_built_blocks_and_says_why(self, track, kwargs, fragment):
        plan = _plan(**kwargs)
        assert _codes(plan, "blocking") == ["request_invalid"]
        (blocking,) = [p for p in plan["problems"] if p["severity"] == "blocking"]
        assert fragment in blocking["detail"]
        assert plan["request"] is None and plan["ready"] is False

    def test_no_request_while_the_track_has_no_keeper(self, album):  # noqa: F811
        _image(album.audio_dir / "album.png")
        assert _plan(asset_id=ASSET, duration_s=60)["request"] is None

    def test_a_video_already_there_is_a_warning(self, track):
        out = track.audio_dir / "lyric_videos" / "01-first-track-16x9.mp4"
        out.parent.mkdir(parents=True)
        out.write_bytes(b"earlier")
        plan = _plan()
        assert plan["output"]["exists"] is True
        assert "video_exists" in _codes(plan, "warning")
        assert plan["ready"] is True

    def test_no_ffmpeg_is_a_warning_not_a_stop(self, track, monkeypatch):
        monkeypatch.setattr(handler.shutil, "which", lambda name: None)
        plan = _plan()
        assert plan["ffmpeg"] is False
        assert "ffmpeg_missing" in _codes(plan, "warning")
        assert plan["ready"] is True

    def test_an_unknown_track_or_album(self, track):
        assert _plan("99-missing")["found"] is False
        assert json.loads(_run(handler.get_lyric_video_plan("no-such-album", "01")))["found"] is False


# ===========================================================================
# prepare_lyric_video_still
# ===========================================================================


class TestPrepareStill:
    def test_the_still_is_written_where_the_plan_said(self, track):
        result = _still()
        planned = _plan()["still"]["path"]
        assert result["found"] is True and result["shape"] == "16:9"
        assert result["still"]["path"] == planned
        assert (result["still"]["width"], result["still"]["height"]) == (1920, 1080)
        assert result["still"]["content_type"] == "image/jpeg"
        assert result["still"]["bytes"] == Path(planned).stat().st_size
        assert result["cover"] == str(track.audio_dir / "album.png")
        with Image.open(planned) as still:
            assert still.size == (1920, 1080)

    def test_another_shape(self, track):
        result = _still(shape="9x16")
        assert (result["still"]["width"], result["still"]["height"]) == (1080, 1920)
        assert result["still"]["path"].endswith("test-album-9x16.jpg")

    def test_the_cover_is_left_alone(self, track):
        before = (track.audio_dir / "album.png").read_bytes()
        _still()
        assert (track.audio_dir / "album.png").read_bytes() == before

    def test_no_cover_is_an_error(self, track):
        (track.audio_dir / "album.png").unlink()
        result = _still()
        assert "error" in result and "cover" in result["error"].lower()

    def test_a_shape_suno_does_not_make_is_an_error(self, track):
        assert "4:3" in _still(shape="4:3")["error"]

    def test_an_unknown_album(self, track):
        result = json.loads(_run(handler.prepare_lyric_video_still("no-such-album")))
        assert result.get("found") is False or "error" in result


# ===========================================================================
# save_lyric_video
# ===========================================================================


@pytest.fixture
def suno(track, monkeypatch):
    """A Suno that hands over a video, and an ffmpeg that does as it is told."""
    calls = {"download": [], "finish": []}

    def download(url, dest, **kwargs):
        calls["download"].append({"url": url, "dest": Path(dest)})
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"\x00\x00\x00\x20ftypisom" + b"v" * 500)
        return 512

    def finish(downloaded, dest, master, **kwargs):
        calls["finish"].append({"downloaded": Path(downloaded), "dest": Path(dest), "master": master})
        Path(downloaded).replace(dest)
        return {
            "path": str(dest), "duration_s": 55.2, "width": 1920, "height": 1080, "bytes": 512,
            "audio": "master" if master else "suno", "audio_note": "",
        }

    monkeypatch.setattr(handler.lv, "download_video", download)
    monkeypatch.setattr(handler.lv, "finish", finish)
    track.calls = calls
    return track


class TestSave:
    def test_the_video_is_saved_beside_the_audio(self, suno):
        result = _save()
        out = suno.audio_dir / "lyric_videos" / "01-first-track-16x9.mp4"
        assert result["found"] is True and result["saved"] is True
        assert result["path"] == str(out) and out.is_file()
        assert (result["shape"], result["width"], result["height"]) == ("16:9", 1920, 1080)
        assert result["duration_s"] == 55.2
        (download,) = suno.calls["download"]
        assert download["url"] == LINK
        assert download["dest"].parent == out.parent and download["dest"].name != out.name
        assert suno.calls["finish"][0]["master"] is None
        assert result["audio"] == "suno"

    def test_the_master_goes_under_it_when_there_is_one(self, suno):
        master = suno.audio_dir / "mastered" / "01-first-track.wav"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"RIFF")
        result = _save()
        assert suno.calls["finish"][0]["master"] == master
        assert result["audio"] == "master"

    def test_the_master_can_be_left_out(self, suno):
        master = suno.audio_dir / "mastered" / "01-first-track.wav"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"RIFF")
        assert _save(master_audio=False)["audio"] == "suno"
        assert suno.calls["finish"][0]["master"] is None

    def test_the_shape_names_the_file(self, suno):
        result = _save(shape="1x1")
        assert result["shape"] == "1:1"
        assert result["path"].endswith("01-first-track-1x1.mp4")

    def test_an_earlier_video_is_kept_unless_replacing_is_asked_for(self, suno):
        out = suno.audio_dir / "lyric_videos" / "01-first-track-16x9.mp4"
        out.parent.mkdir(parents=True)
        out.write_bytes(b"earlier")
        refused = _save()
        assert refused["saved"] is False and "replace" in refused["error"]
        assert out.read_bytes() == b"earlier" and suno.calls["download"] == []
        replaced = _save(replace=True)
        assert replaced["saved"] is True
        assert out.read_bytes() != b"earlier"

    def test_a_link_that_is_not_sunos_is_refused_and_nothing_is_fetched(self, track):
        result = _save("https://example.org/video.mp4")
        assert result["saved"] is False and "example.org" in result["error"]
        folder = track.audio_dir / "lyric_videos"
        assert not folder.exists() or list(folder.iterdir()) == []

    def test_a_download_that_fails_is_reported(self, suno, monkeypatch):
        def broken(url, dest, **kwargs):
            raise OSError("connection reset")

        monkeypatch.setattr(handler.lv, "download_video", broken)
        result = _save()
        assert result["saved"] is False and "connection reset" in result["error"]

    def test_a_download_that_is_not_a_video_is_reported_and_nothing_is_kept(self, suno, monkeypatch):
        def not_video(downloaded, dest, master, **kwargs):
            Path(downloaded).unlink()
            raise ValueError("What Suno sent is not an MP4")

        monkeypatch.setattr(handler.lv, "finish", not_video)
        result = _save()
        assert result["saved"] is False and "not an MP4" in result["error"]
        assert list((suno.audio_dir / "lyric_videos").iterdir()) == []

    def test_whatever_else_goes_wrong_is_reported_not_raised(self, suno, monkeypatch):
        def explode(downloaded, dest, master, **kwargs):
            raise RuntimeError("ffmpeg fell over")

        monkeypatch.setattr(handler.lv, "finish", explode)
        result = _save()
        assert result["saved"] is False and "ffmpeg fell over" in result["error"]
        assert list((suno.audio_dir / "lyric_videos").iterdir()) == []

    def test_a_shape_suno_does_not_make_is_an_error(self, suno):
        result = _save(shape="4:3")
        assert "error" in result and suno.calls["download"] == []

    def test_an_unknown_track(self, suno):
        assert _save(track="99-missing")["found"] is False
        assert suno.calls["download"] == []


class TestTheyAreRegisteredTools:
    @pytest.mark.parametrize("name", [
        "get_lyric_video_plan", "prepare_lyric_video_still", "save_lyric_video",
    ])
    def test_the_server_exposes_it(self, name):
        assert callable(getattr(server, name, None))
