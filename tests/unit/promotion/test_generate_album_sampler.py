"""Tests for tools/promotion/generate_album_sampler.py utility functions."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock heavy optional deps before import so tests behave consistently
# regardless of whether the deps are installed on this machine.
# Save originals and restore after import to prevent MagicMock pollution
# leaking into later test files (e.g. PIL.__version__ becomes MagicMock).
_MOCK_DEPS = ["librosa", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"]
_SAVED_DEPS = {dep: sys.modules.get(dep) for dep in _MOCK_DEPS}
for dep in _MOCK_DEPS:
    sys.modules[dep] = MagicMock()

from tools.promotion.generate_album_sampler import get_track_title

# Restore original modules to avoid polluting later tests
for dep, original in _SAVED_DEPS.items():
    if original is None:
        sys.modules.pop(dep, None)
    else:
        sys.modules[dep] = original


# ---------------------------------------------------------------------------
# get_track_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetTrackTitle:
    """Tests for track title extraction from filenames."""

    def test_dash_separator(self):
        assert get_track_title("08 - 116 Cadets.wav") == "116 Cadets"

    def test_number_prefix_removed(self):
        assert get_track_title("01_my-great-track.wav") == "My Great Track"

    def test_slug_converted(self):
        assert get_track_title("03-fire-in-the-sky.wav") == "Fire In The Sky"

    def test_no_prefix(self):
        assert get_track_title("song-name.wav") == "Song Name"

    def test_two_digit_prefix(self):
        assert get_track_title("12.my_song.mp3") == "My Song"

    def test_three_digit_number_preserved(self):
        """Track numbers with 3+ digits (like '116') should NOT be stripped."""
        result = get_track_title("116-cadets.wav")
        # "116" has 3 digits so the regex shouldn't strip it
        assert "116" in result

    def test_underscore_to_space(self):
        assert get_track_title("01_hello_world.wav") == "Hello World"

    def test_title_case(self):
        result = get_track_title("05 - all lowercase words.wav")
        assert result == "All Lowercase Words"

    def test_single_word(self):
        assert get_track_title("01-anthem.wav") == "Anthem"

    def test_extension_removed(self):
        result = get_track_title("01-track.mp4")
        assert ".mp4" not in result
