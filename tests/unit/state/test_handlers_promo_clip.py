#!/usr/bin/env python3
"""handlers/promo_clip.py — a promo clip Suno generates for a passage of a track.

    get_promo_clip_plan(album, track, prompt, start_s, ...)  — what will be made, and the request
    save_promo_clip(album, track, link, start_s, ...)        — the clip the user chose, in promo_videos/

Neither talks to Suno: the promo-director skill calls Suno's video-create and
hands the link back. Nothing is fetched here; the download and ffmpeg are
replaced. The album fixture comes from test_handlers_generation.py and the
track fixture from test_handlers_lyric_video.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_promo_clip.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: F401  (album is a fixture)
    CLIP_A,
    LEGACY_KEEPER_ROW,
    _row,
    _run,
    album,
    server,
)
from tests.unit.state.test_handlers_lyric_video import (  # noqa: F401  (track is a fixture)
    KEEPER,
    _codes,
    _image,
    track,
)

from handlers import promo_clip as handler

pytestmark = pytest.mark.unit

ASSET = "ast_01a1b2c3-0d4e-7f50-8a61-b2c3d4e5f607"
LINK = (
    "https://suno-data-uploads.s3.amazonaws.com/studio/uploads/visual/"
    "c2pa_video_gen_01a1b2c3-1e2f-7a3b-9c4d-5e6f70819203.mp4?X-Amz-Expires=3600&X-Amz-Signature=abc"
)
PROMPT = "Slow push in on a row of lanterns on a windowsill. No people."


def _plan(track_slug="01-first-track", **kwargs):
    return json.loads(_run(handler.get_promo_clip_plan("test-album", track_slug, **kwargs)))


def _save(link=LINK, track_slug="01-first-track", start_s=47.2, **kwargs):
    return json.loads(_run(handler.save_promo_clip("test-album", track_slug, link, start_s, **kwargs)))


# ===========================================================================
# get_promo_clip_plan
# ===========================================================================


class TestPlan:
    def test_a_track_with_a_keeper(self, track):
        plan = _plan()
        assert plan["found"] is True
        assert (plan["album_slug"], plan["track_slug"], plan["title"]) == (
            "test-album", "01-first-track", "First Track",
        )
        assert plan["song"] == {"clip_id": CLIP_A, "source": "suno_link"}
        assert (plan["aspect"], plan["model"], plan["duration_s"]) == ("9:16", "video-1", 15)
        assert plan["output"] == {
            "path": str(track.audio_dir / "promo_videos" / "01-first-track_suno.mp4"), "exists": False,
        }
        assert plan["cover"] == str(track.audio_dir / "album.png")
        assert plan["request"] is None
        assert plan["ffmpeg"] is True
        assert _codes(plan, "blocking") == [] and plan["ready"] is True

    def test_the_request_comes_with_the_prompt_and_the_passage(self, track):
        plan = _plan(prompt=PROMPT, start_s=47.2, song_duration_s=205.8)
        assert plan["request"] == handler.sc.build_request(
            CLIP_A, PROMPT, 47.2, 15, "9:16", "video-1", song_duration_s=205.8,
        )
        assert plan["request"]["model"] == "video-1" and plan["request"]["song_id"] == CLIP_A
        assert "dry_run" not in plan["request"]

    def test_no_request_without_a_prompt_or_without_a_start(self, track):
        assert _plan(prompt=PROMPT)["request"] is None
        assert _plan(start_s=47.2)["request"] is None

    @pytest.mark.parametrize("start", [-5.0, -0.5, float("nan")])
    def test_only_minus_one_means_the_start_is_not_chosen_yet(self, track, start):
        """Any other negative is a mistake, not a request still being put together."""
        plan = _plan(prompt=PROMPT, start_s=start)
        assert _codes(plan, "blocking") == ["request_invalid"]
        assert plan["request"] is None and plan["ready"] is False

    def test_a_blank_shape_is_the_vertical_default(self, track):
        plan = _plan(prompt=PROMPT, start_s=10, aspect="   ")
        assert plan["aspect"] == "9:16" and plan["request"]["aspect"] == "9:16"

    def test_a_passage_from_the_very_start(self, track):
        assert _plan(prompt=PROMPT, start_s=0.0)["request"]["song_start_s"] == 0

    def test_the_options_reach_the_request(self, track):
        request = _plan(
            prompt=PROMPT, start_s=10, duration_s=5, aspect="1x1", model="video-2",
            first_frame_asset_id=ASSET, singing=False,
        )["request"]
        assert (request["duration_s"], request["aspect"], request["model"]) == (5, "1:1", "video-2")
        assert request["first_frame_asset_id"] == ASSET and request["lip_sync"] is False

    def test_an_instrumental_track_can_have_a_clip(self, track):
        track(suno_link=KEEPER, log_rows=(_row(1, CLIP_A, "✓"),), instrumental_fm="true",
              instrumental_table="Yes")
        plan = _plan(prompt=PROMPT, start_s=10)
        assert plan["ready"] is True and plan["request"] is not None

    def test_no_approved_take_blocks(self, album):  # noqa: F811
        plan = _plan(prompt=PROMPT, start_s=10)
        assert _codes(plan, "blocking") == ["no_keeper"]
        assert plan["song"] is None and plan["request"] is None and plan["ready"] is False

    def test_a_share_link_from_before_mcp_generation_blocks(self, album):  # noqa: F811
        album(suno_link="[Keeper](https://suno.com/s/4hZKwZySCc8Lc63Q)", log_rows=(LEGACY_KEEPER_ROW,))
        assert _codes(_plan(), "blocking") == ["legacy_link"]

    @pytest.mark.parametrize(("kwargs", "fragment"), [
        ({"duration_s": 30}, "5 to 15"),
        ({"aspect": "4:3"}, "4:3"),
        ({"model": "fast"}, "video model"),
        ({"first_frame_asset_id": "../etc/passwd"}, "asset"),
        ({"start_s": 200.0, "song_duration_s": 205.8}, "past the end"),
    ])
    def test_a_request_that_cannot_be_built_blocks_and_says_why(self, track, kwargs, fragment):
        plan = _plan(**{"prompt": PROMPT, "start_s": 10.0, **kwargs})
        assert _codes(plan, "blocking") == ["request_invalid"]
        (blocking,) = [p for p in plan["problems"] if p["severity"] == "blocking"]
        assert fragment in blocking["detail"]
        assert plan["request"] is None and plan["ready"] is False

    def test_a_mistyped_model_blocks_before_there_is_a_prompt(self, track):
        """Dropped, the request would be Suno's Standard model at twice the price."""
        plan = _plan(model="vidoe 1")
        assert _codes(plan, "blocking") == ["request_invalid"]
        assert plan["model"] is None and plan["ready"] is False

    def test_no_master_is_a_warning(self, track):
        plan = _plan()
        assert plan["master"] is None and "no_master" in _codes(plan, "warning")

    def test_the_master_is_named_when_there_is_one(self, track):
        master = track.audio_dir / "mastered" / "01-first-track.wav"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"RIFF")
        plan = _plan()
        assert plan["master"] == {"path": str(master)} and "no_master" not in _codes(plan)

    def test_no_cover_is_not_a_problem(self, track):
        (track.audio_dir / "album.png").unlink()
        plan = _plan()
        assert plan["cover"] is None and plan["ready"] is True

    def test_a_clip_already_there_is_a_warning(self, track):
        out = track.audio_dir / "promo_videos" / "01-first-track_suno.mp4"
        out.parent.mkdir(parents=True)
        out.write_bytes(b"earlier")
        plan = _plan()
        assert plan["output"]["exists"] is True and "clip_exists" in _codes(plan, "warning")

    def test_no_ffmpeg_is_a_warning(self, track, monkeypatch):
        monkeypatch.setattr(handler.shutil, "which", lambda name: None)
        plan = _plan()
        assert plan["ffmpeg"] is False and "ffmpeg_missing" in _codes(plan, "warning")
        assert plan["ready"] is True

    def test_a_track_number_finds_the_track(self, track):
        assert _plan("01")["track_slug"] == "01-first-track"

    def test_an_unknown_track_or_album(self, track):
        assert _plan("99-missing")["found"] is False
        assert json.loads(_run(handler.get_promo_clip_plan("no-such-album", "01")))["found"] is False


# ===========================================================================
# save_promo_clip
# ===========================================================================


@pytest.fixture
def suno(track, monkeypatch):
    """A Suno that hands over a clip, and an ffmpeg that does as it is told."""
    calls = {"download": [], "finish": []}

    def download(url, dest, **kwargs):
        calls["download"].append({"url": url, "dest": Path(dest)})
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"\x00\x00\x00\x20ftypisom" + b"v" * 500)
        return 512

    def finish(downloaded, dest, master, start_s, song_duration_s, **kwargs):
        calls["finish"].append({
            "downloaded": Path(downloaded), "dest": Path(dest), "master": master,
            "start_s": start_s, "song_duration_s": song_duration_s,
        })
        Path(downloaded).replace(dest)
        return {
            "path": str(dest), "duration_s": 15.04, "width": 480, "height": 854, "bytes": 512,
            "audio": "master" if master else "suno", "audio_note": "",
            "audio_start_s": start_s if master else None,
        }

    monkeypatch.setattr(handler.sc.lv, "download_video", download)
    monkeypatch.setattr(handler.sc, "finish_clip", finish)
    track.calls = calls
    return track


class TestSave:
    def test_the_clip_is_saved_with_the_promo_videos(self, suno):
        result = _save(song_duration_s=205.8)
        out = suno.audio_dir / "promo_videos" / "01-first-track_suno.mp4"
        assert result["found"] is True and result["saved"] is True
        assert result["path"] == str(out) and out.is_file()
        assert (result["width"], result["height"], result["duration_s"]) == (480, 854, 15.04)
        (download,) = suno.calls["download"]
        assert download["url"] == LINK
        assert download["dest"].parent == out.parent and download["dest"].name != out.name
        (finish,) = suno.calls["finish"]
        assert (finish["start_s"], finish["song_duration_s"], finish["master"]) == (47.2, 205.8, None)
        assert result["audio"] == "suno"

    def test_the_masters_passage_goes_under_it_when_there_is_a_master(self, suno):
        master = suno.audio_dir / "mastered" / "01-first-track.wav"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"RIFF")
        result = _save(song_duration_s=205.8)
        assert result["audio"] == "master" and result["audio_start_s"] == 47.2
        assert suno.calls["finish"][0]["master"] == master

    def test_the_master_can_be_left_out(self, suno):
        master = suno.audio_dir / "mastered" / "01-first-track.wav"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"RIFF")
        assert _save(master_audio=False)["audio"] == "suno"
        assert suno.calls["finish"][0]["master"] is None

    def test_no_song_length_given_reaches_finish_as_none(self, suno):
        _save()
        assert suno.calls["finish"][0]["song_duration_s"] is None

    def test_an_earlier_clip_is_kept_unless_replacing_is_asked_for(self, suno):
        out = suno.audio_dir / "promo_videos" / "01-first-track_suno.mp4"
        out.parent.mkdir(parents=True)
        out.write_bytes(b"earlier")
        refused = _save()
        assert refused["saved"] is False and "replace" in refused["error"]
        assert out.read_bytes() == b"earlier" and suno.calls["download"] == []
        assert _save(replace=True)["saved"] is True
        assert out.read_bytes() != b"earlier"

    def test_the_other_promo_videos_are_left_alone(self, suno):
        local = suno.audio_dir / "promo_videos" / "01-first-track_promo.mp4"
        local.parent.mkdir(parents=True)
        local.write_bytes(b"made locally")
        _save()
        assert local.read_bytes() == b"made locally"

    def test_a_link_that_is_not_sunos_is_refused_and_nothing_is_fetched(self, track):
        result = _save("https://example.org/clip.mp4")
        assert result["saved"] is False and "example.org" in result["error"]
        folder = track.audio_dir / "promo_videos"
        assert not folder.exists() or list(folder.iterdir()) == []

    @pytest.mark.parametrize("start", [-1.0, float("nan")])
    def test_a_start_that_is_not_a_time_is_refused_before_anything_is_fetched(self, suno, start):
        result = _save(start_s=start)
        assert result["saved"] is False and "start" in result["error"]
        assert suno.calls["download"] == []

    def test_a_download_that_fails_is_reported(self, suno, monkeypatch):
        def broken(url, dest, **kwargs):
            raise OSError("connection reset")

        monkeypatch.setattr(handler.sc.lv, "download_video", broken)
        result = _save()
        assert result["saved"] is False and "connection reset" in result["error"]

    def test_a_download_that_is_not_a_video_leaves_nothing(self, suno, monkeypatch):
        def not_video(downloaded, dest, master, start_s, song_duration_s, **kwargs):
            Path(downloaded).unlink()
            raise ValueError("What Suno sent is not an MP4")

        monkeypatch.setattr(handler.sc, "finish_clip", not_video)
        result = _save()
        assert result["saved"] is False and "not an MP4" in result["error"]
        assert list((suno.audio_dir / "promo_videos").iterdir()) == []

    def test_whatever_else_goes_wrong_is_reported_not_raised(self, suno, monkeypatch):
        def explode(downloaded, dest, master, start_s, song_duration_s, **kwargs):
            raise RuntimeError("ffmpeg fell over")

        monkeypatch.setattr(handler.sc, "finish_clip", explode)
        result = _save()
        assert result["saved"] is False and "ffmpeg fell over" in result["error"]
        assert list((suno.audio_dir / "promo_videos").iterdir()) == []

    def test_an_unknown_track(self, suno):
        assert _save(track_slug="99-missing")["found"] is False
        assert suno.calls["download"] == []


class TestTheyAreRegisteredTools:
    @pytest.mark.parametrize("name", ["get_promo_clip_plan", "save_promo_clip"])
    def test_the_server_exposes_it(self, name):
        assert callable(getattr(server, name, None))
