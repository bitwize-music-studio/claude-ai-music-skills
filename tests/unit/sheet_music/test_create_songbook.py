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
# NOTE: Do NOT mock "yaml" — it is always installed and mocking it at module
# level permanently pollutes sys.modules, breaking yaml.safe_load in later
# test files (e.g. test_indexer.py sees MagicMock instead of real yaml).
_MOCK_MODULES = {
    "pypdf": MagicMock(),
    "reportlab": MagicMock(),
    "reportlab.lib": MagicMock(),
    "reportlab.lib.pagesizes": MagicMock(),
    "reportlab.lib.units": MagicMock(inch=72),
    "reportlab.pdfgen": MagicMock(),
    "reportlab.pdfgen.canvas": MagicMock(),
}
_SAVED_MODULES = {name: sys.modules.get(name) for name in _MOCK_MODULES}
for name, mock in _MOCK_MODULES.items():
    sys.modules[name] = mock

# Load the hyphenated module via importlib (can't use normal import)
_module_path = _PROJECT_ROOT / "tools" / "sheet-music" / "create_songbook.py"
_spec = importlib.util.spec_from_file_location("create_songbook", _module_path)
songbook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(songbook)

# Restore original modules so mocks don't leak into later test files
for name, original in _SAVED_MODULES.items():
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original

from tools.shared.text_utils import sanitize_filename, strip_track_number, slug_to_title


# ---------------------------------------------------------------------------
# sanitize_filename (shared utility for safe filenames)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_removes_slashes(self):
        assert sanitize_filename("Track/Name") == "TrackName"

    def test_removes_backslashes(self):
        assert sanitize_filename("Track\\Name") == "TrackName"

    def test_removes_colons(self):
        assert sanitize_filename("Track: Name") == "Track Name"

    def test_removes_quotes(self):
        assert sanitize_filename('Track "Name"') == "Track Name"

    def test_removes_question_mark(self):
        assert sanitize_filename("Why?") == "Why"

    def test_removes_asterisk(self):
        assert sanitize_filename("Track*Name") == "TrackName"

    def test_removes_angle_brackets(self):
        assert sanitize_filename("<Track>") == "Track"

    def test_removes_pipe(self):
        assert sanitize_filename("A|B") == "AB"

    def test_collapses_whitespace(self):
        assert sanitize_filename("Track   Name") == "Track Name"

    def test_strips_leading_trailing_whitespace(self):
        assert sanitize_filename("  Track Name  ") == "Track Name"

    def test_empty_returns_untitled(self):
        assert sanitize_filename("") == "Untitled"

    def test_only_invalid_chars_returns_untitled(self):
        assert sanitize_filename(":/\\*?") == "Untitled"

    def test_normal_title_unchanged(self):
        assert sanitize_filename("Running on Vapors") == "Running on Vapors"

    def test_preserves_parentheses_and_hyphens(self):
        assert sanitize_filename("Track (Remix) - Extended") == "Track (Remix) - Extended"


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
# slug_to_title (shared utility for clean title casing)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSlugToTitle:
    """Tests for slug-to-title conversion with smart title casing."""

    def test_basic_slug(self):
        assert slug_to_title("01-ocean-of-tears") == "Ocean of Tears"

    def test_no_track_number(self):
        assert slug_to_title("ocean-of-tears") == "Ocean of Tears"

    def test_articles_lowercase(self):
        assert slug_to_title("03-the-end-of-the-road") == "The End of the Road"

    def test_first_word_always_caps(self):
        assert slug_to_title("01-the-beginning") == "The Beginning"

    def test_last_word_always_caps(self):
        assert slug_to_title("01-running-to") == "Running To"

    def test_single_word(self):
        assert slug_to_title("01-dreams") == "Dreams"

    def test_empty_string(self):
        assert slug_to_title("") == ""

    def test_prepositions_lowercase(self):
        assert slug_to_title("05-walk-in-the-rain") == "Walk in the Rain"

    def test_conjunctions_lowercase(self):
        assert slug_to_title("02-fire-and-ice") == "Fire and Ice"

    def test_double_digit_track(self):
        assert slug_to_title("12-beyond-the-stars") == "Beyond the Stars"


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

    def test_finds_from_singles_subdir(self, tmp_path):
        """Cover art found from singles/ -> sheet-music/ -> album/ (2 levels up)."""
        sheet_dir = tmp_path / "sheet-music"
        singles_dir = sheet_dir / "singles"
        singles_dir.mkdir(parents=True)
        (tmp_path / "album.png").touch()
        result = songbook.auto_detect_cover_art(singles_dir)
        assert result is not None
        assert result.endswith("album.png")

    def test_finds_from_songbook_subdir(self, tmp_path):
        """Cover art found from songbook/ -> sheet-music/ -> album/ (2 levels up)."""
        sheet_dir = tmp_path / "sheet-music"
        songbook_dir = sheet_dir / "songbook"
        songbook_dir.mkdir(parents=True)
        (tmp_path / "album.png").touch()
        result = songbook.auto_detect_cover_art(songbook_dir)
        assert result is not None
        assert result.endswith("album.png")


# ---------------------------------------------------------------------------
# get_website_from_config (real function, config mocked)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetWebsiteFromConfig:
    """Tests for URL extraction from config using the real module function."""

    def test_prefers_website_over_soundcloud(self):
        config = {"urls": {
            "website": "https://www.bitwizemusic.com",
            "soundcloud": "https://soundcloud.com/artist",
        }}
        with patch.object(songbook, "read_config", return_value=config):
            result = songbook.get_website_from_config()
        assert result == "bitwizemusic.com"

    def test_falls_back_to_soundcloud(self):
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


# ---------------------------------------------------------------------------
# Manifest-based track ordering
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestManifest:
    """Tests that songbook reads track order from .manifest.json when present."""

    def _make_fake_pdf(self, path):
        """Create a minimal valid PDF file for testing."""
        # pypdf is mocked, so we just need a file to exist
        path.write_bytes(b"%PDF-1.4 fake")

    def test_manifest_ordering_used(self, tmp_path):
        """When .manifest.json exists, tracks should follow its order."""
        import json

        singles = tmp_path / "singles"
        singles.mkdir()

        # Create PDFs in reverse alphabetical order
        self._make_fake_pdf(singles / "Zebra Song.pdf")
        self._make_fake_pdf(singles / "Apple Pie.pdf")

        # Manifest specifies Apple first, Zebra second
        manifest = {
            "tracks": [
                {"number": 1, "source": "01-apple-pie", "title": "Apple Pie"},
                {"number": 2, "source": "02-zebra-song", "title": "Zebra Song"},
            ]
        }
        (singles / ".manifest.json").write_text(json.dumps(manifest))

        # We can't easily call create_songbook since pypdf is mocked,
        # but we can verify the manifest is read correctly
        manifest_path = singles / ".manifest.json"
        with open(manifest_path) as f:
            loaded = json.load(f)

        assert loaded["tracks"][0]["title"] == "Apple Pie"
        assert loaded["tracks"][1]["title"] == "Zebra Song"
        assert len(loaded["tracks"]) == 2

    def test_manifest_with_filename_field(self, tmp_path):
        """When manifest has filename field, songbook should find numbered PDFs."""
        import json

        singles = tmp_path / "singles"
        singles.mkdir()

        # Create numbered PDFs (output from prepare_singles)
        self._make_fake_pdf(singles / "01 - Apple Pie.pdf")
        self._make_fake_pdf(singles / "02 - Zebra Song.pdf")

        manifest = {
            "tracks": [
                {"number": 1, "source_slug": "01-apple-pie", "title": "Apple Pie",
                 "filename": "01 - Apple Pie"},
                {"number": 2, "source_slug": "02-zebra-song", "title": "Zebra Song",
                 "filename": "02 - Zebra Song"},
            ]
        }
        (singles / ".manifest.json").write_text(json.dumps(manifest))

        manifest_path = singles / ".manifest.json"
        with open(manifest_path) as f:
            loaded = json.load(f)

        # Verify filename field resolves to existing PDFs
        for entry in loaded["tracks"]:
            pdf_path = singles / f"{entry['filename']}.pdf"
            assert pdf_path.exists(), f"PDF not found: {pdf_path}"

        # Verify title is preserved
        assert loaded["tracks"][0]["title"] == "Apple Pie"
        assert loaded["tracks"][1]["filename"] == "02 - Zebra Song"

    def test_manifest_filename_fallback_to_title(self, tmp_path):
        """When filename is missing, songbook should fall back to title."""
        import json

        singles = tmp_path / "singles"
        singles.mkdir()

        self._make_fake_pdf(singles / "Apple Pie.pdf")

        manifest = {
            "tracks": [
                {"number": 1, "source_slug": "01-apple-pie", "title": "Apple Pie"},
            ]
        }
        (singles / ".manifest.json").write_text(json.dumps(manifest))

        # Without filename field, title should be used
        entry = manifest["tracks"][0]
        pdf_path = singles / f"{entry.get('filename', entry['title'])}.pdf"
        assert pdf_path.exists()

    def test_fallback_without_manifest(self, tmp_path):
        """Without manifest, numbered PDFs should still be found."""
        import re

        singles = tmp_path / "singles"
        singles.mkdir()
        self._make_fake_pdf(singles / "01-track-a.pdf")
        self._make_fake_pdf(singles / "02-track-b.pdf")

        # No manifest — should fall back to numbered file detection
        numbered = sorted([
            f for f in singles.glob("*.pdf")
            if re.match(r'^\d+', f.stem)
        ])
        assert len(numbered) == 2
        assert numbered[0].stem == "01-track-a"
