#!/usr/bin/env python3
"""handlers/music_video.py — a music video for a track, laid out and generated on Suno.

    get_music_video_plan(album, track, shape, shots, ...)  — what will be made, and the Sequence request
    plan_music_video_shots(duration_s, sections, ...)      — shots on the song's sections, and what clips bill
    save_music_video(album, track, link, kind, ...)        — the animatic or the finished video, beside the audio

None of them talks to Suno: the music-video skill calls Suno's Sequence tools
and hands the link back. Nothing is fetched here; the download and ffmpeg are
replaced. The album fixture comes from test_handlers_generation.py and the
track fixture from test_handlers_lyric_video.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_music_video.py -v
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
    track,
)

from handlers import music_video as handler

pytestmark = pytest.mark.unit

LINK = (
    "https://suno-data-uploads.s3.amazonaws.com/studio/uploads/visual/"
    "c2pa_video_gen_01a1b2c3-1e2f-7a3b-9c4d-5e6f70819203.mp4?X-Amz-Expires=3600&X-Amz-Signature=abc"
)
SECTIONS = [
    {"start_s": 0, "end_s": 9.44, "label": "A"},
    {"start_s": 9.44, "end_s": 29.32, "label": "B"},
    {"start_s": 29.32, "end_s": 38.68, "label": "C"},
    {"start_s": 38.68, "end_s": 48.36, "label": "D"},
    {"start_s": 48.36, "end_s": 55.16, "label": "E"},
]
SHOTS = [
    {"duration_s": 9.44, "notes": "Wide: a windowsill at dawn. Slow push in."},
    {"duration_s": 9.94, "notes": "Close on a row of lanterns."},
]


def _plan(track_slug="01-first-track", **kwargs):
    return json.loads(_run(handler.get_music_video_plan("test-album", track_slug, **kwargs)))


def _shots(duration_s=55.16, sections=SECTIONS, **kwargs):
    return json.loads(_run(handler.plan_music_video_shots(duration_s, sections, **kwargs)))


def _save(link=LINK, track_slug="01-first-track", **kwargs):
    return json.loads(_run(handler.save_music_video("test-album", track_slug, link, **kwargs)))


# ===========================================================================
# get_music_video_plan
# ===========================================================================


class TestPlan:
    def test_a_track_with_a_keeper(self, track):
        plan = _plan()
        folder = track.audio_dir / "music_videos"
        assert plan["found"] is True
        assert (plan["album_slug"], plan["track_slug"], plan["title"]) == (
            "test-album", "01-first-track", "First Track",
        )
        assert plan["shape"] == "16:9"
        assert plan["song"] == {"clip_id": CLIP_A, "source": "suno_link"}
        assert plan["sequence_title"] == "First Track (music video)"
        assert plan["output"] == {"path": str(folder / "01-first-track-16x9.mp4"), "exists": False}
        assert plan["animatic"] == {
            "path": str(folder / "01-first-track-16x9-animatic.mp4"), "exists": False,
        }
        assert plan["request"] is None and plan["ffmpeg"] is True
        assert _codes(plan, "blocking") == [] and plan["ready"] is True

    def test_the_request_comes_with_the_shots(self, track):
        plan = _plan(shots=SHOTS, style={"look": "watercolour"}, lyrics=True)
        assert plan["request"] == handler.mv.build_sequence_request(
            CLIP_A, "First Track (music video)", SHOTS, aspect="16:9",
            style={"look": "watercolour"}, lyrics=True,
        )
        assert plan["request"]["song_id"] == CLIP_A and len(plan["request"]["shots"]) == 2

    def test_the_cast_and_the_sets_reach_the_request(self, track):
        cast = [{"name": "Mara", "asset_ids": ["ast_1234"], "description": "red coat"}]
        places = [{"name": "Kitchen", "asset_ids": ["ast_5678"]}]
        assert _codes(_plan(shots=[{"duration_s": 8, "characters": [3]}], characters=cast), "blocking") == ["request_invalid"]
        shots = [{"duration_s": 8, "notes": "Mara at the window.", "characters": ["Mara"], "set": "Kitchen"}]
        request = _plan(shots=shots, characters=cast, sets=places)["request"]
        assert request["characters"] == cast and request["sets"] == places
        assert request["shots"][0]["characters"] == ["Mara"] and request["shots"][0]["set"] == "Kitchen"

    @pytest.mark.parametrize(("written", "shape", "slug"), [("9x16", "9:16", "9x16"), ("1:1", "1:1", "1x1")])
    def test_the_shape_names_the_files(self, track, written, shape, slug):
        plan = _plan(shape=written, shots=SHOTS)
        assert plan["shape"] == shape and plan["request"]["aspect"] == shape
        assert plan["output"]["path"].endswith(f"01-first-track-{slug}.mp4")
        assert plan["animatic"]["path"].endswith(f"01-first-track-{slug}-animatic.mp4")

    def test_a_shape_suno_does_not_make_is_an_error(self, track):
        assert "4:3" in _plan(shape="4:3")["error"]

    def test_shots_suno_would_refuse_block_and_say_why(self, track):
        plan = _plan(shots=[{"duration_s": 16}])
        assert _codes(plan, "blocking") == ["request_invalid"]
        assert plan["request"] is None and plan["ready"] is False
        (blocking,) = [p for p in plan["problems"] if p["severity"] == "blocking"]
        assert "15" in blocking["detail"]

    def test_no_approved_take_blocks_and_gives_no_request(self, album):  # noqa: F811
        plan = _plan(shots=SHOTS)
        assert _codes(plan, "blocking") == ["no_keeper"]
        assert plan["song"] is None and plan["request"] is None and plan["ready"] is False

    def test_a_share_link_from_before_mcp_generation_blocks(self, album):  # noqa: F811
        album(suno_link="[Keeper](https://suno.com/s/4hZKwZySCc8Lc63Q)", log_rows=(LEGACY_KEEPER_ROW,))
        assert _codes(_plan(), "blocking") == ["legacy_link"]

    def test_an_instrumental_track_can_have_a_video_but_no_words(self, track):
        track(suno_link=KEEPER, log_rows=(_row(1, CLIP_A, "✓"),), instrumental_fm="true",
              instrumental_table="Yes")
        assert _plan(shots=SHOTS)["ready"] is True
        plan = _plan(shots=SHOTS, lyrics=True)
        assert _codes(plan, "blocking") == ["instrumental"] and plan["request"] is None

    def test_no_master_and_no_ffmpeg_are_warnings(self, track, monkeypatch):
        monkeypatch.setattr(handler.shutil, "which", lambda name: None)
        plan = _plan()
        assert {"no_master", "ffmpeg_missing"} <= set(_codes(plan, "warning"))
        assert plan["master"] is None and plan["ffmpeg"] is False and plan["ready"] is True

    def test_files_already_there_are_warnings(self, track):
        folder = track.audio_dir / "music_videos"
        folder.mkdir(parents=True)
        (folder / "01-first-track-16x9.mp4").write_bytes(b"earlier")
        (folder / "01-first-track-16x9-animatic.mp4").write_bytes(b"earlier")
        plan = _plan()
        assert plan["output"]["exists"] is True and plan["animatic"]["exists"] is True
        assert {"video_exists", "animatic_exists"} <= set(_codes(plan, "warning"))

    def test_an_unknown_track_or_album(self, track):
        assert _plan("99-missing")["found"] is False
        assert json.loads(_run(handler.get_music_video_plan("no-such-album", "01")))["found"] is False


# ===========================================================================
# plan_music_video_shots
# ===========================================================================


class TestPlanShots:
    def test_the_shots_and_what_clips_would_be_charged_for(self):
        result = _shots()
        assert result["shot_count"] == 6 and result["total_s"] == 55.16
        assert [shot["duration_s"] for shot in result["shots"]] == [9.44, 9.94, 9.94, 9.36, 9.68, 6.8]
        assert [shot["number"] for shot in result["shots"]] == [1, 2, 3, 4, 5, 6]
        assert result["billed_seconds"] == 57
        assert "estimate_credits" not in result

    def test_each_shot_says_what_its_clip_would_be_charged_for(self):
        result = _shots()
        assert [shot["billed_s"] for shot in result["shots"]] == [10, 10, 10, 10, 10, 7]

    def test_an_estimate_when_the_price_a_second_is_given(self):
        result = _shots(credits_per_second=15)
        assert result["estimate_credits"] == 57 * 15
        assert "dry run" in result["estimate_note"]

    def test_the_options_reach_the_planner(self):
        assert _shots(max_shot_s=15)["shot_count"] < _shots(max_shot_s=6)["shot_count"]
        on_bars = _shots(bpm=189.4, time_signature=4, first_downbeat_s=0.149)
        assert on_bars["shot_count"] == 7

    def test_a_song_with_no_sections(self):
        result = _shots(sections=[])
        assert result["total_s"] == 55.16 and result["shot_count"] == 6

    @pytest.mark.parametrize(("kwargs", "fragment"), [
        ({"duration_s": 0}, "length"),
        ({"max_shot_s": 30}, "5 to 15"),
        ({"sections": [{"label": "A"}]}, "section"),
        ({"duration_s": 600.0, "sections": [], "max_shot_s": 6}, "40"),
    ])
    def test_a_plan_that_cannot_be_made_is_an_error(self, kwargs, fragment):
        result = _shots(**kwargs)
        assert fragment in result["error"] and "shots" not in result


# ===========================================================================
# save_music_video
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
            "path": str(dest), "duration_s": 205.8, "width": 1920, "height": 1080, "bytes": 512,
            "audio": "master" if master else "suno", "audio_note": "",
        }

    monkeypatch.setattr(handler.lv, "download_video", download)
    monkeypatch.setattr(handler.lv, "finish", finish)
    track.calls = calls
    return track


def _master(track_dir) -> Path:
    master = track_dir.audio_dir / "mastered" / "01-first-track.wav"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"RIFF")
    return master


class TestSave:
    def test_the_finished_video_is_saved_beside_the_audio(self, suno):
        result = _save()
        out = suno.audio_dir / "music_videos" / "01-first-track-16x9.mp4"
        assert result["found"] is True and result["saved"] is True and result["kind"] == "video"
        assert result["path"] == str(out) and out.is_file()
        assert (result["shape"], result["width"], result["height"]) == ("16:9", 1920, 1080)
        assert suno.calls["download"][0]["url"] == LINK

    def test_the_master_goes_under_the_finished_video(self, suno):
        master = _master(suno)
        assert _save()["audio"] == "master"
        assert suno.calls["finish"][0]["master"] == master

    def test_the_master_can_be_left_out(self, suno):
        _master(suno)
        assert _save(master_audio=False)["audio"] == "suno"

    def test_an_animatic_is_a_draft_with_its_own_name_and_sunos_audio(self, suno):
        _master(suno)
        result = _save(kind="animatic")
        out = suno.audio_dir / "music_videos" / "01-first-track-16x9-animatic.mp4"
        assert result["saved"] is True and result["kind"] == "animatic"
        assert result["path"] == str(out) and out.is_file()
        assert suno.calls["finish"][0]["master"] is None and result["audio"] == "suno"

    def test_a_new_animatic_replaces_the_one_before_without_asking(self, suno):
        """It is a draft, made again after every change to the cut."""
        out = suno.audio_dir / "music_videos" / "01-first-track-16x9-animatic.mp4"
        out.parent.mkdir(parents=True)
        out.write_bytes(b"earlier")
        assert _save(kind="animatic")["saved"] is True
        assert out.read_bytes() != b"earlier"

    def test_an_earlier_finished_video_is_kept_unless_replacing_is_asked_for(self, suno):
        out = suno.audio_dir / "music_videos" / "01-first-track-16x9.mp4"
        out.parent.mkdir(parents=True)
        out.write_bytes(b"earlier")
        refused = _save()
        assert refused["saved"] is False and "replace" in refused["error"]
        assert out.read_bytes() == b"earlier" and suno.calls["download"] == []
        assert _save(replace=True)["saved"] is True

    def test_the_shape_names_the_file(self, suno):
        assert _save(shape="9x16")["path"].endswith("01-first-track-9x16.mp4")

    def test_a_kind_that_is_neither_is_an_error(self, suno):
        result = _save(kind="teaser")
        assert "teaser" in result["error"] and suno.calls["download"] == []

    def test_a_shape_suno_does_not_make_is_an_error(self, suno):
        assert "4:3" in _save(shape="4:3")["error"] and suno.calls["download"] == []

    def test_a_link_that_is_not_sunos_is_refused_and_nothing_is_fetched(self, track):
        result = _save("https://example.org/video.mp4")
        assert result["saved"] is False and "example.org" in result["error"]
        folder = track.audio_dir / "music_videos"
        assert not folder.exists() or list(folder.iterdir()) == []

    def test_a_download_that_is_not_a_video_leaves_nothing(self, suno, monkeypatch):
        def not_video(downloaded, dest, master, **kwargs):
            Path(downloaded).unlink()
            raise ValueError("What Suno sent is not an MP4")

        monkeypatch.setattr(handler.lv, "finish", not_video)
        result = _save()
        assert result["saved"] is False and "not an MP4" in result["error"]
        assert list((suno.audio_dir / "music_videos").iterdir()) == []

    def test_an_unknown_track(self, suno):
        assert _save(track_slug="99-missing")["found"] is False
        assert suno.calls["download"] == []


class TestTheyAreRegisteredTools:
    @pytest.mark.parametrize("name", [
        "get_music_video_plan", "plan_music_video_shots", "save_music_video",
    ])
    def test_the_server_exposes_it(self, name):
        assert callable(getattr(server, name, None))
