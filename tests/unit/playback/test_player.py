#!/usr/bin/env python3
"""Unit tests for tools/playback/player.py — local audio lookup and playback.

No test makes a sound: the player process, the process table and the clock are
all faked. Playback state lands in the isolated state-cache directory that the
autouse conftest fixture points ``tools.state.indexer.CACHE_DIR`` at.

Usage:
    python -m pytest tests/unit/playback/test_player.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.playback import player

pytestmark = pytest.mark.unit


class FakePopen:
    """Stands in for subprocess.Popen: records the call, never starts anything."""

    instances: list[FakePopen] = []

    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.pid = 4000 + len(FakePopen.instances)
        self.returncode = None
        FakePopen.instances.append(self)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def kill(self):
        self.returncode = -9


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A fake audio root with one wav, mpv 'installed', and no real processes."""
    FakePopen.instances = []
    player._children.clear()

    audio_root = tmp_path / "audio"
    album = audio_root / "artists" / "a" / "albums" / "rock" / "album"
    album.mkdir(parents=True)
    wav = album / "01-first-track.wav"
    wav.write_bytes(b"RIFF")

    terminated: list[int] = []

    def fake_terminate(pid):
        terminated.append(pid)
        child = player._children.get(pid)
        if child is not None:
            child.returncode = -15

    clock = {"now": 1000.0}
    monkeypatch.setattr(player.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "mpv" else None)
    monkeypatch.setattr(player.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(player, "_terminate", fake_terminate)
    monkeypatch.setattr(player, "_process_name", lambda pid: None)
    monkeypatch.setattr(player.time, "time", lambda: clock["now"])

    class Rig:
        pass

    r = Rig()
    r.audio_root = audio_root
    r.album = album
    r.wav = wav
    r.roots = [audio_root, player.takes_cache_dir()]
    r.terminated = terminated
    r.clock = clock
    return r


# ===========================================================================
# find_player / build_command
# ===========================================================================


class TestFindPlayer:
    @pytest.mark.parametrize(
        "installed,expected",
        [
            ({"mpv", "ffplay", "afplay"}, "mpv"),
            ({"ffplay", "afplay"}, "ffplay"),
            ({"afplay"}, "afplay"),
            (set(), None),
        ],
    )
    def test_preference_order(self, monkeypatch, installed, expected):
        monkeypatch.setattr(
            player.shutil, "which", lambda name: f"/bin/{name}" if name in installed else None,
        )
        assert player.find_player() == expected


class TestBuildCommand:
    @pytest.fixture(autouse=True)
    def _which(self, monkeypatch):
        monkeypatch.setattr(player.shutil, "which", lambda name: f"/bin/{name}")

    def test_mpv(self):
        cmd = player.build_command("mpv", Path("/a/b.wav"), start_s=90, length_s=30)
        assert cmd == [
            "/bin/mpv", "--no-config", "--no-video", "--no-terminal", "--really-quiet",
            "--start=90", "--length=30", "--", str(Path("/a/b.wav")),
        ]

    def test_mpv_from_the_top(self):
        cmd = player.build_command("mpv", Path("/a/b.wav"))
        assert "--start=0" not in cmd
        assert not any(arg.startswith("--length") for arg in cmd)
        assert cmd[-2:] == ["--", str(Path("/a/b.wav"))]

    def test_ffplay(self):
        cmd = player.build_command("ffplay", Path("/a/b.mp3"), start_s=12.5, length_s=10)
        assert cmd == [
            "/bin/ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
            "-ss", "12.5", "-t", "10", "-i", str(Path("/a/b.mp3")),
        ]

    def test_afplay_has_no_seek(self):
        cmd = player.build_command("afplay", Path("/a/b.wav"), start_s=30, length_s=5)
        assert cmd == ["/bin/afplay", "-t", "5", str(Path("/a/b.wav"))]

    def test_unknown_player(self):
        with pytest.raises(player.PlaybackError):
            player.build_command("winamp", Path("/a/b.wav"))


# ===========================================================================
# validate_path
# ===========================================================================


class TestValidatePath:
    def test_file_under_audio_root_is_accepted(self, rig):
        assert player.validate_path(str(rig.wav), rig.roots) == rig.wav

    def test_file_in_takes_cache_is_accepted(self, rig):
        take = player.takes_cache_dir() / "4ef71736-b95e-489b-b5ac-1a41badceb08.mp3"
        take.parent.mkdir(parents=True)
        take.write_bytes(b"ID3")
        assert player.validate_path(take, rig.roots) == take

    @pytest.mark.parametrize(
        "url",
        ["https://suno.com/song/abc.mp3", "http://example.com/a.wav", "file:///etc/a.wav"],
    )
    def test_urls_are_rejected(self, rig, url):
        with pytest.raises(player.PlaybackError, match="local files"):
            player.validate_path(url, rig.roots)

    def test_relative_path_is_rejected(self, rig):
        with pytest.raises(player.PlaybackError, match="absolute"):
            player.validate_path("album/01-first-track.wav", rig.roots)

    def test_non_audio_extension_is_rejected(self, rig):
        script = rig.album / "notes.sh"
        script.write_text("echo hi", encoding="utf-8")
        with pytest.raises(player.PlaybackError, match="Not an audio file"):
            player.validate_path(script, rig.roots)

    def test_missing_file_is_rejected(self, rig):
        with pytest.raises(player.PlaybackError, match="not found"):
            player.validate_path(rig.album / "99-missing.wav", rig.roots)

    def test_file_outside_the_roots_is_rejected(self, rig, tmp_path):
        outside = tmp_path / "elsewhere.wav"
        outside.write_bytes(b"RIFF")
        with pytest.raises(player.PlaybackError, match="outside"):
            player.validate_path(outside, rig.roots)

    def test_traversal_out_of_the_root_is_rejected(self, rig, tmp_path):
        outside = tmp_path / "elsewhere.wav"
        outside.write_bytes(b"RIFF")
        sneaky = rig.audio_root / ".." / "elsewhere.wav"
        with pytest.raises(player.PlaybackError, match="outside"):
            player.validate_path(sneaky, rig.roots)

    def test_symlinked_album_directory_is_accepted(self, rig, tmp_path):
        real = tmp_path / "external-drive" / "album"
        real.mkdir(parents=True)
        (real / "01-first-track.wav").write_bytes(b"RIFF")
        link = rig.audio_root / "linked-album"
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:
            pytest.skip("symlinks not available on this platform")
        target = link / "01-first-track.wav"
        assert player.validate_path(target, rig.roots) == target


# ===========================================================================
# find_track_audio
# ===========================================================================


class TestFindTrackAudio:
    def test_exact_slug(self, rig):
        assert player.find_track_audio(rig.album, "01-first-track") == rig.wav

    def test_hand_named_download_matches_by_track_number(self, rig):
        rig.wav.unlink()
        named = rig.album / "01 - First Track.wav"
        named.write_bytes(b"RIFF")
        assert player.find_track_audio(rig.album, "01-first-track") == named

    def test_exact_slug_wins_over_number_match(self, rig):
        (rig.album / "01 - First Track.wav").write_bytes(b"RIFF")
        assert player.find_track_audio(rig.album, "01-first-track") == rig.wav

    def test_wav_wins_over_other_formats(self, rig):
        (rig.album / "01-first-track.mp3").write_bytes(b"ID3")
        assert player.find_track_audio(rig.album, "01-first-track") == rig.wav

    def test_ambiguous_number_match_returns_none(self, rig):
        rig.wav.unlink()
        (rig.album / "01 - First Track.wav").write_bytes(b"RIFF")
        (rig.album / "01 - First Track (alt).wav").write_bytes(b"RIFF")
        assert player.find_track_audio(rig.album, "01-first-track") is None

    def test_other_tracks_and_non_audio_are_ignored(self, rig):
        rig.wav.unlink()
        (rig.album / "02-second-track.wav").write_bytes(b"RIFF")
        (rig.album / "01-first-track.txt").write_text("notes", encoding="utf-8")
        (rig.album / "01-first-track").mkdir()
        assert player.find_track_audio(rig.album, "01-first-track") is None

    def test_missing_directory(self, rig):
        assert player.find_track_audio(rig.album / "mastered", "01-first-track") is None


# ===========================================================================
# play / stop / status
# ===========================================================================


class TestPlay:
    def test_starts_a_detached_player_and_records_state(self, rig):
        result = player.play(rig.wav, rig.roots, start_s=30)

        proc = FakePopen.instances[0]
        assert proc.command[0] == "/usr/bin/mpv"
        assert "--start=30" in proc.command
        assert proc.command[-1] == str(rig.wav)
        assert proc.kwargs["stdin"] is subprocess.DEVNULL
        assert proc.kwargs["stdout"] is subprocess.DEVNULL
        assert proc.kwargs["stderr"] is subprocess.DEVNULL
        if sys.platform == "win32":
            assert proc.kwargs["creationflags"] == 0x00000008 | 0x00000200
        else:
            assert proc.kwargs["start_new_session"] is True

        assert result["playing"] is True
        assert result["player"] == "mpv"
        assert result["pid"] == proc.pid
        assert result["path"] == str(rig.wav)
        assert "mpv" in result["command"]

        state = json.loads(player.state_path().read_text(encoding="utf-8"))
        assert state == {
            "pid": proc.pid, "player": "mpv", "path": str(rig.wav),
            "started_at": 1000.0, "start_s": 30.0,
        }

    def test_a_new_playback_stops_the_current_one(self, rig):
        first = player.play(rig.wav, rig.roots)
        second = player.play(rig.wav, rig.roots)
        assert rig.terminated == [first["pid"]]
        assert second["pid"] != first["pid"]
        assert json.loads(player.state_path().read_text(encoding="utf-8"))["pid"] == second["pid"]

    def test_afplay_cannot_seek(self, rig, monkeypatch):
        monkeypatch.setattr(
            player.shutil, "which", lambda name: "/usr/bin/afplay" if name == "afplay" else None,
        )
        result = player.play(rig.wav, rig.roots, start_s=45)
        assert result["start_s"] == 0.0
        assert "afplay" in result["warnings"][0]
        assert FakePopen.instances[0].command == ["/usr/bin/afplay", str(rig.wav)]

    def test_no_player_installed(self, rig, monkeypatch):
        monkeypatch.setattr(player.shutil, "which", lambda name: None)
        with pytest.raises(player.PlaybackError, match="mpv"):
            player.play(rig.wav, rig.roots)
        assert FakePopen.instances == []

    @pytest.mark.parametrize("start_s,length_s", [(-1, None), (0, 0), (0, -5)])
    def test_bad_times_are_rejected(self, rig, start_s, length_s):
        with pytest.raises(player.PlaybackError):
            player.play(rig.wav, rig.roots, start_s=start_s, length_s=length_s)

    def test_bad_path_starts_nothing(self, rig):
        with pytest.raises(player.PlaybackError):
            player.play("https://suno.com/song/x.mp3", rig.roots)
        assert FakePopen.instances == []


class TestStopAndStatus:
    def test_nothing_playing(self, rig):
        assert player.status() == {"playing": False}
        assert player.stop()["stopped"] is False

    def test_status_reports_position(self, rig):
        started = player.play(rig.wav, rig.roots, start_s=30)
        rig.clock["now"] += 12.5
        assert player.status() == {
            "playing": True, "pid": started["pid"], "player": "mpv",
            "path": str(rig.wav), "position_s": 42.5,
        }

    def test_stop_terminates_and_returns_position(self, rig):
        started = player.play(rig.wav, rig.roots, start_s=30)
        rig.clock["now"] += 12.5
        result = player.stop()
        assert result == {"stopped": True, "path": str(rig.wav), "position_s": 42.5}
        assert rig.terminated == [started["pid"]]
        assert not player.state_path().exists()
        assert player.status() == {"playing": False}

    def test_finished_playback_clears_state(self, rig):
        player.play(rig.wav, rig.roots)
        FakePopen.instances[0].returncode = 0
        assert player.status() == {"playing": False}
        assert not player.state_path().exists()
        assert rig.terminated == []

    def test_restarted_server_can_stop_a_player_it_recognises(self, rig, monkeypatch):
        """State from a previous server process: no Popen handle, so the process
        table decides. A matching player is stopped."""
        player.cache_dir().mkdir(parents=True, exist_ok=True)
        player.state_path().write_text(
            json.dumps({"pid": 777, "player": "mpv", "path": str(rig.wav),
                        "started_at": 990.0, "start_s": 0.0}),
            encoding="utf-8",
        )
        monkeypatch.setattr(player, "_process_name", lambda pid: "/opt/homebrew/bin/mpv")
        assert player.stop()["stopped"] is True
        assert rig.terminated == [777]

    def test_a_recycled_pid_is_never_killed(self, rig, monkeypatch):
        """The pid in the state file now belongs to something else."""
        player.cache_dir().mkdir(parents=True, exist_ok=True)
        player.state_path().write_text(
            json.dumps({"pid": 777, "player": "mpv", "path": str(rig.wav),
                        "started_at": 990.0, "start_s": 0.0}),
            encoding="utf-8",
        )
        monkeypatch.setattr(player, "_process_name", lambda pid: "/usr/sbin/sshd")
        assert player.stop()["stopped"] is False
        assert rig.terminated == []
        assert not player.state_path().exists()

    def test_corrupt_state_file_is_ignored(self, rig):
        player.cache_dir().mkdir(parents=True, exist_ok=True)
        player.state_path().write_text("{not json", encoding="utf-8")
        assert player.status() == {"playing": False}


# ===========================================================================
# audio_duration
# ===========================================================================


class TestAudioDuration:
    def test_reads_a_wav(self, tmp_path):
        pytest.importorskip("soundfile")
        path = tmp_path / "tone.wav"
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x00" * 4000)
        assert player.audio_duration(path) == pytest.approx(0.5)

    def test_unreadable_file_is_unknown(self, tmp_path):
        path = tmp_path / "broken.wav"
        path.write_bytes(b"not audio")
        assert player.audio_duration(path) is None
