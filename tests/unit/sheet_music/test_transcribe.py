"""Tests for tools/sheet-music/transcribe.py."""

import argparse
import importlib.util
import subprocess as real_subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test via importlib (hyphenated directory)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_module_path = _PROJECT_ROOT / "tools" / "sheet-music" / "transcribe.py"
_spec = importlib.util.spec_from_file_location("transcribe", _module_path)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# find_anthemscore
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFindAnthemscore:
    """Tests for AnthemScore detection across platforms."""

    @patch("platform.system", return_value="Linux")
    def test_returns_none_when_not_found(self, _mock_platform):
        with patch.object(Path, "exists", return_value=False):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                result = mod.find_anthemscore()
                assert result is None

    @patch("platform.system", return_value="Darwin")
    def test_falls_back_to_which(self, _mock_platform):
        with patch.object(Path, "exists", return_value=False):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="/usr/local/bin/anthemscore\n")):
                result = mod.find_anthemscore()
                assert result == "/usr/local/bin/anthemscore"


# ---------------------------------------------------------------------------
# get_wav_files
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetWavFiles:
    """Tests for WAV file discovery from files and directories."""

    def test_single_wav_file(self, tmp_path):
        wav = tmp_path / "track.wav"
        wav.write_bytes(b"RIFF fake wav")
        files, source_dir = mod.get_wav_files(wav)
        assert len(files) == 1
        assert files[0] == wav
        assert source_dir == tmp_path

    def test_directory_of_wavs(self, tmp_path):
        (tmp_path / "01-track.wav").write_bytes(b"wav1")
        (tmp_path / "02-track.wav").write_bytes(b"wav2")
        (tmp_path / "notes.txt").write_text("not audio")
        files, source_dir = mod.get_wav_files(tmp_path)
        assert len(files) == 2
        assert source_dir == tmp_path
        assert all(f.suffix == ".wav" for f in files)

    def test_non_wav_file_exits(self, tmp_path):
        mp3 = tmp_path / "track.mp3"
        mp3.write_bytes(b"fake mp3")
        with pytest.raises(SystemExit):
            mod.get_wav_files(mp3)

    def test_empty_directory_exits(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(SystemExit):
            mod.get_wav_files(empty)

    def test_nonexistent_path_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            mod.get_wav_files(tmp_path / "nonexistent")

    def test_sorted_order(self, tmp_path):
        (tmp_path / "02-beta.wav").write_bytes(b"wav")
        (tmp_path / "01-alpha.wav").write_bytes(b"wav")
        files, _ = mod.get_wav_files(tmp_path)
        assert files[0].stem == "01-alpha"
        assert files[1].stem == "02-beta"


# ---------------------------------------------------------------------------
# transcribe_track
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTranscribeTrack:
    """Tests for individual track transcription with mocked subprocess."""

    @pytest.fixture()
    def base_args(self):
        """Minimal argparse namespace for transcribe_track."""
        return argparse.Namespace(
            pdf=True, xml=True, midi=False,
            treble=False, bass=False, dry_run=False,
        )

    @pytest.fixture()
    def wav_file(self, tmp_path):
        f = tmp_path / "01-track.wav"
        f.write_bytes(b"RIFF wav data")
        return f

    @patch("subprocess.run")
    def test_successful_transcription(self, mock_run, wav_file, tmp_path, base_args):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/anthemscore"
        assert str(wav_file) in cmd
        assert "-a" in cmd

    @patch("subprocess.run")
    def test_failed_transcription(self, mock_run, wav_file, tmp_path, base_args):
        mock_run.return_value = MagicMock(returncode=1, stderr="codec error")
        result = mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        assert result is False

    @patch("subprocess.run", side_effect=real_subprocess.TimeoutExpired(cmd="anthemscore", timeout=300))
    def test_timeout(self, _mock_run, wav_file, tmp_path, base_args):
        result = mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        assert result is False

    @patch("subprocess.run", side_effect=OSError("anthemscore not found"))
    def test_oserror(self, _mock_run, wav_file, tmp_path, base_args):
        result = mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        assert result is False

    def test_dry_run_returns_true(self, wav_file, tmp_path, base_args):
        base_args.dry_run = True
        result = mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        assert result is True

    @patch("subprocess.run")
    def test_midi_flag_adds_m(self, mock_run, wav_file, tmp_path, base_args):
        base_args.midi = True
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd

    @patch("subprocess.run")
    def test_treble_flag(self, mock_run, wav_file, tmp_path, base_args):
        base_args.treble = True
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        cmd = mock_run.call_args[0][0]
        assert "-t" in cmd

    @patch("subprocess.run")
    def test_bass_flag(self, mock_run, wav_file, tmp_path, base_args):
        base_args.bass = True
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        cmd = mock_run.call_args[0][0]
        assert "-b" in cmd

    @patch("subprocess.run")
    def test_pdf_output_path(self, mock_run, wav_file, tmp_path, base_args):
        base_args.xml = False
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mod.transcribe_track("/usr/bin/anthemscore", wav_file, tmp_path, base_args)
        cmd = mock_run.call_args[0][0]
        assert str(tmp_path / "01-track.pdf") in cmd
        # xml flag is False, so -x should not be present
        assert "-x" not in cmd


# ---------------------------------------------------------------------------
# resolve_album_path
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestResolveAlbumPath:
    """resolve_album_path builds the canonical mirrored audio path (#375)."""

    @patch.object(mod, "read_config")
    def test_missing_key_returns_none(self, mock_config):
        mock_config.return_value = {"paths": {}}
        result = mod.resolve_album_path("my-album")
        assert result is None

    @patch.object(mod, "read_config")
    def test_path_traversal_rejected(self, mock_config, tmp_path):
        """Symlink under a genre dir that escapes audio_root is rejected."""
        audio_root = tmp_path / "audio"
        outside = tmp_path / "outside"
        outside.mkdir()
        genre_dir = audio_root / "artists" / "test-artist" / "albums" / "rock"
        genre_dir.mkdir(parents=True)
        # Symlink: .../albums/rock/evil -> {tmp}/outside
        (genre_dir / "evil").symlink_to(outside)

        mock_config.return_value = {
            "paths": {"audio_root": str(audio_root)},
            "artist": {"name": "test-artist"},
        }
        result = mod.resolve_album_path("evil")
        assert result is None

    def _config(self, tmp_path):
        return {
            "paths": {"audio_root": str(tmp_path)},
            "artist": {"name": "test-artist"},
        }

    def test_resolves_album_by_name(self, tmp_path):
        album_dir = tmp_path / "artists" / "test-artist" / "albums" / "rock" / "my-album"
        album_dir.mkdir(parents=True)
        with patch.object(mod, "read_config", return_value=self._config(tmp_path)):
            assert mod.resolve_album_path("my-album") == album_dir

    def test_returns_none_when_album_missing(self, tmp_path):
        (tmp_path / "artists" / "test-artist" / "albums" / "rock").mkdir(parents=True)
        with patch.object(mod, "read_config", return_value=self._config(tmp_path)):
            assert mod.resolve_album_path("nope") is None

    def test_missing_albums_root_returns_none(self, tmp_path):
        with patch.object(mod, "read_config", return_value=self._config(tmp_path)):
            assert mod.resolve_album_path("anything") is None

    def test_multiple_genre_twins_picks_first_sorted(self, tmp_path):
        for genre in ("rock", "jazz"):
            (tmp_path / "artists" / "test-artist" / "albums" / genre / "twin").mkdir(parents=True)
        with patch.object(mod, "read_config", return_value=self._config(tmp_path)):
            result = mod.resolve_album_path("twin")
        assert result == tmp_path / "artists" / "test-artist" / "albums" / "jazz" / "twin"

    def test_no_config_returns_none(self):
        with patch.object(mod, "read_config", return_value=None):
            assert mod.resolve_album_path("x") is None
