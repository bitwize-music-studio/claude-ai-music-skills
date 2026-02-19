"""Tests for tools/sheet-music/create_songbook.py utility functions."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock heavy optional deps before import so tests behave consistently
# regardless of whether the deps are installed on this machine.
_MOCK_MODULES = {
    "pypdf": MagicMock(),
    "reportlab": MagicMock(),
    "reportlab.lib": MagicMock(),
    "reportlab.lib.pagesizes": MagicMock(),
    "reportlab.lib.units": MagicMock(inch=72),
    "reportlab.pdfgen": MagicMock(),
    "reportlab.pdfgen.canvas": MagicMock(),
}
for name, mock in _MOCK_MODULES.items():
    sys.modules[name] = mock

# Load the hyphenated module via importlib (can't use normal import)
_module_path = _PROJECT_ROOT / "tools" / "sheet-music" / "create_songbook.py"
_spec = importlib.util.spec_from_file_location("create_songbook", _module_path)
songbook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(songbook)

from tools.shared.text_utils import strip_track_number


# ---------------------------------------------------------------------------
# strip_track_number (shared utility used by songbook)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStripTrackNumber:
    """Tests for track number prefix removal."""

    def test_dash_separator(self):
        assert strip_track_number("01 - Track Name") == "Track Name"

    def test_no_space_dash(self):
        assert strip_track_number("01-Track Name") == "Track Name"

    def test_single_digit(self):
        assert strip_track_number("1 - Track Name") == "Track Name"

    def test_dot_separator(self):
        assert strip_track_number("01. Track Name") == "Track Name"

    def test_no_prefix(self):
        assert strip_track_number("Track Name") == "Track Name"

    def test_empty_string(self):
        assert strip_track_number("") == ""

    def test_double_digit(self):
        assert strip_track_number("12 - Twelve") == "Twelve"


# ---------------------------------------------------------------------------
# auto_detect_cover_art (real function from module)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAutoDetectCoverArt:
    """Tests for album art auto-detection from the real module function."""

    def test_finds_png(self, tmp_path):
        sheet_dir = tmp_path / "sheet-music"
        sheet_dir.mkdir()
        (tmp_path / "album.png").touch()
        result = songbook.auto_detect_cover_art(sheet_dir)
        assert result is not None
        assert result.endswith("album.png")

    def test_finds_jpg(self, tmp_path):
        sheet_dir = tmp_path / "sheet-music"
        sheet_dir.mkdir()
        (tmp_path / "album.jpg").touch()
        result = songbook.auto_detect_cover_art(sheet_dir)
        assert result is not None
        assert result.endswith("album.jpg")

    def test_prefers_png_over_jpg(self, tmp_path):
        sheet_dir = tmp_path / "sheet-music"
        sheet_dir.mkdir()
        (tmp_path / "album.png").touch()
        (tmp_path / "album.jpg").touch()
        result = songbook.auto_detect_cover_art(sheet_dir)
        assert result.endswith("album.png")

    def test_no_cover_art(self, tmp_path):
        sheet_dir = tmp_path / "sheet-music"
        sheet_dir.mkdir()
        result = songbook.auto_detect_cover_art(sheet_dir)
        assert result is None


# ---------------------------------------------------------------------------
# get_website_from_config (real function, config mocked)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetWebsiteFromConfig:
    """Tests for URL extraction from config using the real module function."""

    def test_prefers_soundcloud(self):
        config = {"urls": {
            "soundcloud": "https://soundcloud.com/artist",
            "spotify": "https://open.spotify.com/artist/123",
        }}
        with patch.object(songbook, "read_config", return_value=config):
            result = songbook.get_website_from_config()
        assert result == "soundcloud.com/artist"

    def test_falls_back_to_bandcamp(self):
        config = {"urls": {"bandcamp": "https://artist.bandcamp.com"}}
        with patch.object(songbook, "read_config", return_value=config):
            result = songbook.get_website_from_config()
        assert result == "artist.bandcamp.com"

    def test_strips_www(self):
        config = {"urls": {"soundcloud": "https://www.soundcloud.com/artist"}}
        with patch.object(songbook, "read_config", return_value=config):
            result = songbook.get_website_from_config()
        assert result == "soundcloud.com/artist"

    def test_strips_trailing_slash(self):
        config = {"urls": {"soundcloud": "https://soundcloud.com/artist/"}}
        with patch.object(songbook, "read_config", return_value=config):
            result = songbook.get_website_from_config()
        assert result == "soundcloud.com/artist"

    def test_no_urls_section(self):
        config = {"artist": {"name": "test"}}
        with patch.object(songbook, "read_config", return_value=config):
            result = songbook.get_website_from_config()
        assert result is None

    def test_empty_config(self):
        with patch.object(songbook, "read_config", return_value=None):
            result = songbook.get_website_from_config()
        assert result is None

    def test_empty_urls(self):
        config = {"urls": {}}
        with patch.object(songbook, "read_config", return_value=config):
            result = songbook.get_website_from_config()
        assert result is None
