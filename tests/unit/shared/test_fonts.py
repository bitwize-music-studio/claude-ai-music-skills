#!/usr/bin/env python3
"""
Unit tests for font discovery utility.

Usage:
    python -m pytest tools/shared/tests/test_fonts.py -v
"""

import sys
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.shared.fonts import find_font


class TestFindFont:
    """Tests for find_font()."""

    def test_returns_string_or_none(self):
        """find_font returns a string path or None."""
        result = find_font()
        assert result is None or isinstance(result, str)

    def test_returned_font_exists(self):
        """If a font is found, the file actually exists."""
        result = find_font()
        if result is not None:
            assert Path(result).exists()

    def test_returns_none_when_no_fonts(self):
        """Returns None when no system fonts exist."""
        with mock.patch('tools.shared.fonts.Path') as MockPath:
            # Make all Path().exists() return False
            MockPath.return_value.exists.return_value = False
            result = find_font()
            assert result is None

    def test_returns_first_available_font(self):
        """Returns the first font that exists from the search list."""
        def mock_exists(self):
            # Only the third font path exists
            path_str = str(self)
            if 'Helvetica' in path_str:
                return True
            return False

        with mock.patch.object(Path, 'exists', mock_exists):
            result = find_font()
            if result is not None:
                assert 'Helvetica' in result
