#!/usr/bin/env python3
"""tools/promotion/suno_clip.py — a promo clip Suno generates for a passage of a song.

    normal_model(value)      — the video model to ask for, never left to Suno's default
    build_request(...)       — the arguments for Suno's video-create
    finish_clip(...)         — the downloaded clip, with the master's passage under it

Nothing here talks to Suno, and ffprobe and ffmpeg are replaced except in the
one test that runs the real ones.

Usage:
    python -m pytest tests/unit/promotion/test_suno_clip.py -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.promotion import lyric_video as lv
from tools.promotion import suno_clip as sc

pytestmark = pytest.mark.unit

SONG = "0c1d2e3f-4a5b-4c6d-8e7f-a0b1c2d3e4f5"
ASSET = "ast_01a1b2c3-0d4e-7f50-8a61-b2c3d4e5f607"
PROMPT = "Slow push in on a row of lanterns on a windowsill. No people."


def _request(**kwargs):
    base = {"song_id": SONG, "prompt": PROMPT, "start_s": 47.2, "duration_s": 15}
    return sc.build_request(**{**base, **kwargs})


# ===========================================================================
# normal_model
# ===========================================================================


class TestNormalModel:
    def test_nothing_written_is_the_cheapest_model_never_sunos_default(self):
        assert sc.normal_model("") == sc.DEFAULT_MODEL == "video-1"
        assert sc.normal_model(None) == "video-1"

    @pytest.mark.parametrize(("written", "model"), [
        ("video-2", "video-2"), (" Video-1 ", "video-1"), ("video-5", "video-5"),
    ])
    def test_a_model_id_is_passed_on(self, written, model):
        assert sc.normal_model(written) == model

    @pytest.mark.parametrize("written", ["fast", "video 2", "video-2; rm", "720p", 2, "image-1", "v"])
    def test_anything_else_is_refused_not_dropped(self, written):
        with pytest.raises(ValueError, match="video model"):
            sc.normal_model(written)


# ===========================================================================
# build_request
# ===========================================================================


class TestBuildRequest:
    def test_the_passage_of_the_song(self):
        assert _request() == {
            "prompt": PROMPT,
            "song_id": SONG,
            "song_start_s": 47.2,
            "duration_s": 15,
            "aspect": "9:16",
            "model": "video-1",
        }

    def test_the_model_is_always_named(self):
        """Left out, Suno uses its Standard model: twice the price a second."""
        assert _request(model="")["model"] == "video-1"
        assert _request(model="video-2")["model"] == "video-2"

    def test_it_never_carries_dry_run_or_a_resolution(self):
        assert not {"dry_run", "resolution", "idempotency_key"} & set(_request())

    @pytest.mark.parametrize(("written", "aspect"), [
        ("1x1", "1:1"), ("16:9", "16:9"), ("", "9:16"), ("   ", "9:16"), (None, "9:16"),
    ])
    def test_the_shape(self, written, aspect):
        assert _request(aspect=written)["aspect"] == aspect

    def test_a_shape_suno_does_not_make(self):
        with pytest.raises(ValueError, match="4:3"):
            _request(aspect="4:3")

    def test_a_first_frame(self):
        assert _request(first_frame_asset_id=ASSET)["first_frame_asset_id"] == ASSET
        assert "first_frame_asset_id" not in _request(first_frame_asset_id="  ")

    def test_a_first_frame_that_is_not_an_asset_id(self):
        with pytest.raises(ValueError, match="asset"):
            _request(first_frame_asset_id="../../etc/passwd")

    def test_no_one_singing_on_screen(self):
        assert _request(singing=False)["lip_sync"] is False
        assert "lip_sync" not in _request(singing=True)

    def test_the_prompt_is_trimmed_and_needed(self):
        assert _request(prompt=f"  {PROMPT}\n")["prompt"] == PROMPT
        with pytest.raises(ValueError, match="prompt"):
            _request(prompt="   ")

    @pytest.mark.parametrize("seconds", [5, 10, 15, 12.0])
    def test_a_length_suno_makes(self, seconds):
        made = _request(duration_s=seconds)["duration_s"]
        assert made == int(seconds) and isinstance(made, int)

    @pytest.mark.parametrize("seconds", [4, 16, 0, -5, 7.5, 60, "15", None, True])
    def test_a_length_it_does_not(self, seconds):
        with pytest.raises(ValueError, match="5 to 15"):
            _request(duration_s=seconds)

    @pytest.mark.parametrize("start", [-0.1, float("nan"), float("inf"), "12", None, True])
    def test_a_start_that_is_not_a_time(self, start):
        with pytest.raises(ValueError, match="start"):
            _request(start_s=start)

    def test_the_start_is_kept_to_hundredths(self):
        assert _request(start_s=47.23678)["song_start_s"] == 47.24
        assert _request(start_s=0)["song_start_s"] == 0

    def test_a_passage_that_runs_past_the_end_of_the_song(self):
        assert _request(start_s=40, duration_s=15, song_duration_s=55.16)["song_start_s"] == 40
        with pytest.raises(ValueError, match="past the end"):
            _request(start_s=41, duration_s=15, song_duration_s=55.16)

    def test_a_song_shorter_than_the_clip(self):
        with pytest.raises(ValueError, match="past the end"):
            _request(start_s=0, duration_s=15, song_duration_s=9.0)

    @pytest.mark.parametrize("song", ["", "not-a-song", "../x", SONG + "0"])
    def test_a_song_id_that_is_not_one(self, song):
        with pytest.raises(ValueError, match="song"):
            _request(song_id=song)


# ===========================================================================
# finish_clip
# ===========================================================================


def _mp4(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"v" * 400)
    return path


def _probe_answers(answers):
    """A stand-in for probe(): each path's answer, or an exception to raise."""
    def probe(path, **kwargs):
        answer = answers[Path(path).name]
        if isinstance(answer, Exception):
            raise answer
        return answer
    return probe


CLIP = {"duration_s": 15.04, "video": True, "audio": True, "width": 720, "height": 1280}
MASTER = {"duration_s": 205.9, "video": False, "audio": True, "width": None, "height": None}


@pytest.fixture
def files(tmp_path):
    return {
        "down": _mp4(tmp_path / "clip.mp4.part"),
        "dest": tmp_path / "out" / "clip.mp4",
        "master": tmp_path / "master.wav",
    }


def _swap_recorder(calls):
    def swap(video, audio, dest, **kwargs):
        calls.append({"video": Path(video), "audio": Path(audio), "dest": Path(dest), **kwargs})
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"swapped")
    return swap


class TestFinishClip:
    def test_without_a_master_the_clip_is_kept_as_suno_made_it(self, files):
        files["dest"].parent.mkdir()
        info = sc.finish_clip(
            files["down"], files["dest"], None, 47.2, 205.8,
            probe=_probe_answers({"clip.mp4.part": CLIP}), swap=_swap_recorder([]),
        )
        assert info == {
            "path": str(files["dest"]), "duration_s": 15.04, "width": 720, "height": 1280,
            "bytes": files["dest"].stat().st_size, "audio": "suno", "audio_note": "",
            "audio_start_s": None,
        }
        assert not files["down"].exists()

    def test_the_masters_passage_goes_under_the_picture(self, files):
        calls = []
        info = sc.finish_clip(
            files["down"], files["dest"], files["master"], 47.2, 205.8,
            probe=_probe_answers({"clip.mp4.part": CLIP, "master.wav": MASTER}),
            swap=_swap_recorder(calls),
        )
        (call,) = calls
        assert (call["video"], call["audio"], call["dest"]) == (
            files["down"], files["master"], files["dest"],
        )
        assert call["audio_start_s"] == 47.2 and call["seconds"] == 15.04
        assert info["audio"] == "master" and info["audio_note"] == ""
        assert info["audio_start_s"] == 47.2            # which passage of the master it was
        assert files["dest"].read_bytes() == b"swapped" and not files["down"].exists()

    def test_a_master_of_another_length_than_the_take_is_left_out(self, files):
        """Its timeline is not the take's, so the passage would be another one."""
        calls = []
        files["dest"].parent.mkdir()
        info = sc.finish_clip(
            files["down"], files["dest"], files["master"], 47.2, 180.0,
            probe=_probe_answers({"clip.mp4.part": CLIP, "master.wav": MASTER}),
            swap=_swap_recorder(calls),
        )
        assert calls == [] and info["audio"] == "suno"
        assert "205.9" in info["audio_note"] and "180" in info["audio_note"]

    def test_without_the_takes_length_the_master_is_left_out(self, files):
        calls = []
        files["dest"].parent.mkdir()
        info = sc.finish_clip(
            files["down"], files["dest"], files["master"], 47.2, None,
            probe=_probe_answers({"clip.mp4.part": CLIP, "master.wav": MASTER}),
            swap=_swap_recorder(calls),
        )
        assert calls == [] and info["audio"] == "suno" and "length" in info["audio_note"]

    def test_a_passage_at_the_very_end_of_a_slightly_shorter_master_still_gets_it(self, files):
        """A master may be a quarter of a second shorter than the take; ffmpeg stops with the shorter."""
        calls = []
        shorter = {**MASTER, "duration_s": 205.6}
        info = sc.finish_clip(
            files["down"], files["dest"], files["master"], 190.76, 205.8,
            probe=_probe_answers({"clip.mp4.part": CLIP, "master.wav": shorter}),
            swap=_swap_recorder(calls),
        )
        assert len(calls) == 1 and info["audio"] == "master"

    def test_a_passage_that_runs_past_the_masters_end_is_left_out(self, files):
        calls = []
        files["dest"].parent.mkdir()
        info = sc.finish_clip(
            files["down"], files["dest"], files["master"], 200.0, 205.8,
            probe=_probe_answers({"clip.mp4.part": CLIP, "master.wav": MASTER}),
            swap=_swap_recorder(calls),
        )
        assert calls == [] and info["audio"] == "suno" and "end" in info["audio_note"]

    def test_a_download_that_is_not_a_video_is_refused_and_removed(self, files):
        files["down"].write_bytes(b"<html>Access denied</html>")
        with pytest.raises(ValueError, match="not an MP4"):
            sc.finish_clip(files["down"], files["dest"], None, 0, 60, probe=_probe_answers({}))
        assert not files["down"].exists() and not files["dest"].exists()

    def test_a_download_without_a_picture_is_refused(self, files):
        sound_only = {**CLIP, "video": False, "width": None, "height": None}
        with pytest.raises(ValueError, match="no picture"):
            sc.finish_clip(
                files["down"], files["dest"], None, 0, 60,
                probe=_probe_answers({"clip.mp4.part": sound_only}),
            )
        assert not files["down"].exists()

    def test_without_ffmpeg_the_clip_is_kept_unchecked(self, files):
        calls = []
        files["dest"].parent.mkdir()
        info = sc.finish_clip(
            files["down"], files["dest"], files["master"], 47.2, 205.8,
            probe=_probe_answers({"clip.mp4.part": lv.ToolMissing("ffprobe is not installed.")}),
            swap=_swap_recorder(calls),
        )
        assert calls == [] and info["audio"] == "suno"
        assert "not installed" in info["audio_note"] and files["dest"].is_file()

    def test_a_swap_that_fails_keeps_sunos_audio(self, files):
        def broken(video, audio, dest, **kwargs):
            raise ValueError("ffmpeg could not put the master under the video: boom")

        files["dest"].parent.mkdir()
        info = sc.finish_clip(
            files["down"], files["dest"], files["master"], 47.2, 205.8,
            probe=_probe_answers({"clip.mp4.part": CLIP, "master.wav": MASTER}), swap=broken,
        )
        assert info["audio"] == "suno" and "boom" in info["audio_note"]
        assert files["dest"].is_file() and not files["down"].exists()


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")
class TestWithRealFfmpeg:
    def test_the_masters_passage_really_goes_under_the_clip(self, tmp_path):
        """A 6 s clip with a 440 Hz tone; a 30 s master that is 880 Hz only from 10 s to 16 s."""
        clip, master, dest = tmp_path / "clip.part", tmp_path / "master.wav", tmp_path / "out.mp4"
        quiet = {"check": True, "capture_output": True}
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=180x320:r=30:d=6",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-shortest", "-pix_fmt", "yuv420p",
            "-f", "mp4", str(clip),
        ], **quiet)
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=10",
            "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=6",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=14",
            "-filter_complex", "[1:a]aformat=channel_layouts=stereo[t];[0:a][t][2:a]concat=n=3:v=0:a=1",
            str(master),
        ], **quiet)

        info = sc.finish_clip(clip, dest, master, 10.0, 30.0)

        assert info["audio"] == "master", info["audio_note"]
        assert abs(info["duration_s"] - 6.0) < 0.2
        probed = lv.probe(dest)
        assert probed["video"] and probed["audio"] and abs(probed["duration_s"] - 6.0) < 0.3
        # The master is silent outside 10 s to 16 s, and its tone is 880 Hz where the
        # clip's own is 440. So both ends of the result must be loud above 700 Hz:
        # the clip's own audio would be quiet there, and a passage a few seconds
        # off would be silent at one end.
        def level(*where: str) -> float:
            heard = subprocess.run([
                "ffmpeg", "-v", "info", *where, "-i", str(dest), "-vn", "-af",
                "highpass=f=700,highpass=f=700,highpass=f=700,volumedetect", "-f", "null", "-",
            ], capture_output=True, text=True, check=True).stderr
            return float(heard.split("mean_volume:")[1].split("dB")[0])

        assert level("-t", "0.5") > -32
        assert level("-sseof", "-0.5") > -32
