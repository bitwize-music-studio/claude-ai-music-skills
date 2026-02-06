"""Tests for tools.shared.progress module."""

import io
import sys
from unittest.mock import patch

from tools.shared.progress import ProgressBar


class TestProgressBarInit:
    """Tests for ProgressBar initialization."""

    def test_init_defaults(self):
        bar = ProgressBar(10)
        assert bar.total == 10
        assert bar.prefix == ""
        assert bar.width == 40
        assert bar.current == 0

    def test_init_custom(self):
        bar = ProgressBar(5, prefix="Test", width=20)
        assert bar.total == 5
        assert bar.prefix == "Test"
        assert bar.width == 20

    def test_is_tty_detection(self):
        with patch.object(sys.stderr, 'isatty', return_value=True):
            bar = ProgressBar(10)
            assert bar.is_tty is True

        with patch.object(sys.stderr, 'isatty', return_value=False):
            bar = ProgressBar(10)
            assert bar.is_tty is False


class TestProgressBarUpdate:
    """Tests for ProgressBar.update()."""

    def test_increments_current(self):
        bar = ProgressBar(5)
        bar.is_tty = False  # suppress output
        bar.update()
        assert bar.current == 1
        bar.update()
        assert bar.current == 2

    def test_silent_on_non_tty(self):
        """No stderr output when not a TTY."""
        stderr = io.StringIO()
        bar = ProgressBar(3)
        bar.is_tty = False
        with patch('sys.stderr', stderr):
            bar.update("file.wav")
        assert stderr.getvalue() == ""

    def test_writes_to_stderr_on_tty(self):
        """Writes progress bar to stderr when TTY."""
        stderr = io.StringIO()
        bar = ProgressBar(3, prefix="Test")
        bar.is_tty = True
        with patch('sys.stderr', stderr):
            bar.update("file.wav")
        output = stderr.getvalue()
        assert "Test" in output
        assert "1/3" in output
        assert "file.wav" in output
        assert "\r" in output

    def test_writes_newline_at_completion(self):
        """Writes newline when bar reaches 100%."""
        stderr = io.StringIO()
        bar = ProgressBar(2, prefix="Done")
        bar.is_tty = True
        with patch('sys.stderr', stderr):
            bar.update("a")
            bar.update("b")
        output = stderr.getvalue()
        assert output.endswith("\n")

    def test_no_newline_before_completion(self):
        """No trailing newline before bar reaches total."""
        stderr = io.StringIO()
        bar = ProgressBar(3)
        bar.is_tty = True
        with patch('sys.stderr', stderr):
            bar.update("a")
        output = stderr.getvalue()
        assert not output.endswith("\n")

    def test_truncates_long_item_names(self):
        """Long item names are truncated with ellipsis."""
        stderr = io.StringIO()
        bar = ProgressBar(1)
        bar.is_tty = True
        long_name = "a" * 50
        with patch('sys.stderr', stderr):
            bar.update(long_name)
        output = stderr.getvalue()
        assert "..." in output

    def test_empty_item_name(self):
        """Update with no item name works."""
        stderr = io.StringIO()
        bar = ProgressBar(1)
        bar.is_tty = True
        with patch('sys.stderr', stderr):
            bar.update()
        output = stderr.getvalue()
        assert "1/1" in output

    def test_bar_characters(self):
        """Progress bar uses block characters."""
        stderr = io.StringIO()
        bar = ProgressBar(2, width=10)
        bar.is_tty = True
        with patch('sys.stderr', stderr):
            bar.update()
        output = stderr.getvalue()
        assert "\u2588" in output  # filled block
        assert "\u2591" in output  # empty block


class TestProgressBarFinish:
    """Tests for ProgressBar.finish()."""

    def test_finish_writes_newline_if_incomplete(self):
        """finish() writes newline when progress is incomplete."""
        stderr = io.StringIO()
        bar = ProgressBar(5)
        bar.is_tty = True
        bar.current = 3
        with patch('sys.stderr', stderr):
            bar.finish()
        assert stderr.getvalue() == "\n"

    def test_finish_no_newline_if_complete(self):
        """finish() does nothing when already at total."""
        stderr = io.StringIO()
        bar = ProgressBar(5)
        bar.is_tty = True
        bar.current = 5
        with patch('sys.stderr', stderr):
            bar.finish()
        assert stderr.getvalue() == ""

    def test_finish_silent_on_non_tty(self):
        """finish() does nothing on non-TTY."""
        stderr = io.StringIO()
        bar = ProgressBar(5)
        bar.is_tty = False
        bar.current = 2
        with patch('sys.stderr', stderr):
            bar.finish()
        assert stderr.getvalue() == ""
