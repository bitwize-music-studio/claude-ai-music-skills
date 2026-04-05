"""Tests for tools/promotion/generate_all_promos.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.promotion import generate_all_promos as mod


# ---------------------------------------------------------------------------
# find_mastered_dir
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFindMasteredDir:
    """Tests for locating the mastered tracks directory."""

    def test_album_dir_with_audio(self, tmp_path):
        (tmp_path / "01-track.wav").write_bytes(b"audio")
        result = mod.find_mastered_dir(tmp_path)
        assert result == tmp_path

    def test_wavs_mastered_subdir(self, tmp_path):
        mastered = tmp_path / "wavs" / "mastered"
        mastered.mkdir(parents=True)
        (mastered / "01-track.wav").write_bytes(b"audio")
        result = mod.find_mastered_dir(tmp_path)
        assert result == mastered

    def test_mastered_subdir(self, tmp_path):
        mastered = tmp_path / "mastered"
        mastered.mkdir()
        (mastered / "01-track.flac").write_bytes(b"audio")
        result = mod.find_mastered_dir(tmp_path)
        assert result == mastered

    def test_wavs_subdir(self, tmp_path):
        wavs = tmp_path / "wavs"
        wavs.mkdir()
        (wavs / "song.mp3").write_bytes(b"audio")
        result = mod.find_mastered_dir(tmp_path)
        assert result == wavs

    def test_no_audio_falls_back_to_album_dir(self, tmp_path):
        (tmp_path / "readme.txt").write_text("no audio here")
        result = mod.find_mastered_dir(tmp_path)
        assert result == tmp_path

    def test_prefers_album_dir_over_subdirs(self, tmp_path):
        """Album dir itself has audio, should be returned first."""
        (tmp_path / "track.wav").write_bytes(b"audio")
        mastered = tmp_path / "mastered"
        mastered.mkdir()
        (mastered / "track.wav").write_bytes(b"audio")
        result = mod.find_mastered_dir(tmp_path)
        assert result == tmp_path

    def test_recognizes_m4a(self, tmp_path):
        (tmp_path / "song.m4a").write_bytes(b"audio")
        result = mod.find_mastered_dir(tmp_path)
        assert result == tmp_path


# ---------------------------------------------------------------------------
# find_artwork
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFindArtwork:
    """Tests for album artwork discovery."""

    def test_finds_album_png(self, tmp_path):
        (tmp_path / "album.png").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == tmp_path / "album.png"

    def test_finds_album_jpg(self, tmp_path):
        (tmp_path / "album.jpg").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == tmp_path / "album.jpg"

    def test_prefers_png_over_jpg(self, tmp_path):
        (tmp_path / "album.png").write_bytes(b"img")
        (tmp_path / "album.jpg").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == tmp_path / "album.png"

    def test_finds_artwork_png(self, tmp_path):
        (tmp_path / "artwork.png").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == tmp_path / "artwork.png"

    def test_finds_cover_jpg(self, tmp_path):
        (tmp_path / "cover.jpg").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == tmp_path / "cover.jpg"

    def test_finds_album_art_png(self, tmp_path):
        (tmp_path / "album-art.png").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == tmp_path / "album-art.png"

    def test_finds_in_wavs_subdir(self, tmp_path):
        wavs = tmp_path / "wavs"
        wavs.mkdir()
        (wavs / "album.png").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == wavs / "album.png"

    def test_finds_in_mastered_subdir(self, tmp_path):
        mastered = tmp_path / "wavs" / "mastered"
        mastered.mkdir(parents=True)
        (mastered / "album.jpg").write_bytes(b"img")
        result = mod.find_artwork(tmp_path)
        assert result == mastered / "album.jpg"

    def test_returns_none_when_missing(self, tmp_path):
        result = mod.find_artwork(tmp_path)
        assert result is None

    def test_no_false_positive_on_non_art(self, tmp_path):
        (tmp_path / "track.wav").write_bytes(b"audio")
        (tmp_path / "readme.md").write_text("text")
        result = mod.find_artwork(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# main (integration-level tests with mocked subprocess)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMainOrchestration:
    """Tests for main() batch orchestration with mocked subprocess."""

    def _setup_album(self, tmp_path):
        """Create a minimal album directory for testing."""
        (tmp_path / "01-track.wav").write_bytes(b"audio")
        (tmp_path / "02-track.wav").write_bytes(b"audio")
        (tmp_path / "album.png").write_bytes(b"img")
        return tmp_path

    @patch("subprocess.run")
    def test_generates_both_promos_and_sampler(self, mock_run, tmp_path):
        album = self._setup_album(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)

        with patch("sys.argv", ["prog", str(album)]):
            # main() does not sys.exit on success
            mod.main()

        assert mock_run.call_count == 2  # track promos + sampler

    @patch("subprocess.run")
    def test_tracks_only(self, mock_run, tmp_path):
        album = self._setup_album(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)

        with patch("sys.argv", ["prog", str(album), "--tracks-only"]):
            mod.main()

        # Should only call generate_promo_video.py, not generate_album_sampler.py
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "generate_promo_video.py" in str(cmd)

    @patch("subprocess.run")
    def test_sampler_only(self, mock_run, tmp_path):
        album = self._setup_album(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)

        with patch("sys.argv", ["prog", str(album), "--sampler-only"]):
            mod.main()

        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "generate_album_sampler.py" in str(cmd)

    @patch("subprocess.run")
    def test_partial_failure_exits_with_error(self, mock_run, tmp_path):
        album = self._setup_album(tmp_path)
        # First call succeeds, second fails
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1),
        ]

        with patch("sys.argv", ["prog", str(album)]):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 1

    def test_missing_artwork_exits(self, tmp_path):
        (tmp_path / "track.wav").write_bytes(b"audio")
        # No artwork file

        with patch("sys.argv", ["prog", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 1

    def test_nonexistent_dir_exits(self, tmp_path):
        with patch("sys.argv", ["prog", str(tmp_path / "nonexistent")]):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 1

    @patch("subprocess.run")
    def test_style_argument_passed(self, mock_run, tmp_path):
        album = self._setup_album(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)

        with patch("sys.argv", ["prog", str(album), "--tracks-only", "--style", "neon"]):
            mod.main()

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "neon" in cmd_str

    @patch("subprocess.run")
    def test_clip_duration_passed_to_sampler(self, mock_run, tmp_path):
        album = self._setup_album(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)

        with patch("sys.argv", ["prog", str(album), "--sampler-only", "--clip-duration", "20"]):
            mod.main()

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "20" in cmd_str
