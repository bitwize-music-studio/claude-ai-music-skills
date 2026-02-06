#!/usr/bin/env python3
"""
Unit tests for Colors utility class.

Usage:
    python -m pytest tools/shared/tests/test_colors.py -v
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.shared.colors import Colors


class TestColors:
    """Tests for Colors class."""

    def setup_method(self):
        """Reset colors to defaults before each test."""
        Colors.RED = '\033[0;31m'
        Colors.GREEN = '\033[0;32m'
        Colors.YELLOW = '\033[1;33m'
        Colors.BLUE = '\033[0;34m'
        Colors.CYAN = '\033[0;36m'
        Colors.BOLD = '\033[1m'
        Colors.NC = '\033[0m'

    def test_colors_have_ansi_codes(self):
        """Color attributes contain ANSI escape codes."""
        assert '\033[' in Colors.RED
        assert '\033[' in Colors.GREEN
        assert '\033[' in Colors.YELLOW
        assert '\033[' in Colors.BLUE
        assert '\033[' in Colors.CYAN
        assert '\033[' in Colors.BOLD
        assert '\033[' in Colors.NC

    def test_disable_clears_all_codes(self):
        """disable() sets all color attributes to empty strings."""
        Colors.disable()
        assert Colors.RED == ''
        assert Colors.GREEN == ''
        assert Colors.YELLOW == ''
        assert Colors.BLUE == ''
        assert Colors.CYAN == ''
        assert Colors.BOLD == ''
        assert Colors.NC == ''

    def test_disable_is_idempotent(self):
        """Calling disable() twice doesn't cause errors."""
        Colors.disable()
        Colors.disable()
        assert Colors.RED == ''

    def test_auto_disables_when_not_tty(self, monkeypatch):
        """auto() disables colors when stdout is not a TTY."""
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: False)
        Colors.auto()
        assert Colors.RED == ''
        assert Colors.GREEN == ''

    def test_auto_keeps_colors_when_tty(self, monkeypatch):
        """auto() keeps colors when stdout is a TTY."""
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        Colors.auto()
        assert '\033[' in Colors.RED
        assert '\033[' in Colors.GREEN

    def test_colors_usable_in_format_strings(self):
        """Colors work in f-string formatting."""
        msg = f"{Colors.RED}error{Colors.NC}"
        assert 'error' in msg
        assert Colors.RED in msg
        assert Colors.NC in msg

    def test_disabled_colors_produce_clean_output(self):
        """After disable, formatted strings contain no escape codes."""
        Colors.disable()
        msg = f"{Colors.RED}error{Colors.NC}"
        assert msg == 'error'
        assert '\033' not in msg
