"""Tests for tools.shared.logging_config module."""

import logging
import sys

from tools.shared.logging_config import ColorFormatter, setup_logging


class TestColorFormatter:
    """Tests for ColorFormatter."""

    def test_format_info(self):
        formatter = ColorFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "[INFO]" in result
        assert "hello world" in result

    def test_format_error(self):
        formatter = ColorFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="something broke", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "[ERROR]" in result
        assert "something broke" in result

    def test_format_warning(self):
        formatter = ColorFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="watch out", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "[WARN]" in result
        assert "watch out" in result

    def test_format_debug(self):
        formatter = ColorFormatter()
        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg="debug info", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "[DEBUG]" in result
        assert "debug info" in result

    def test_format_critical(self):
        formatter = ColorFormatter()
        record = logging.LogRecord(
            name="test", level=logging.CRITICAL, pathname="", lineno=0,
            msg="critical fail", args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "[CRITICAL]" in result
        assert "critical fail" in result

    def test_all_levels_have_colors(self):
        """Every standard level should have an entry in LEVEL_COLORS."""
        for level in (logging.DEBUG, logging.INFO, logging.WARNING,
                      logging.ERROR, logging.CRITICAL):
            assert level in ColorFormatter.LEVEL_COLORS


class TestSetupLogging:
    """Tests for setup_logging function."""

    def _cleanup_logger(self, name):
        """Remove handlers added during test."""
        logger = logging.getLogger(name)
        logger.handlers.clear()

    def test_returns_logger(self):
        name = "test_returns_logger"
        try:
            logger = setup_logging(name)
            assert isinstance(logger, logging.Logger)
            assert logger.name == name
        finally:
            self._cleanup_logger(name)

    def test_default_level_is_info(self):
        name = "test_default_level"
        try:
            logger = setup_logging(name)
            assert logger.level == logging.INFO
        finally:
            self._cleanup_logger(name)

    def test_verbose_sets_debug(self):
        name = "test_verbose"
        try:
            logger = setup_logging(name, verbose=True)
            assert logger.level == logging.DEBUG
        finally:
            self._cleanup_logger(name)

    def test_quiet_sets_warning(self):
        name = "test_quiet"
        try:
            logger = setup_logging(name, quiet=True)
            assert logger.level == logging.WARNING
        finally:
            self._cleanup_logger(name)

    def test_handler_writes_to_stderr(self):
        name = "test_stderr"
        try:
            logger = setup_logging(name)
            assert len(logger.handlers) == 1
            handler = logger.handlers[0]
            assert isinstance(handler, logging.StreamHandler)
            assert handler.stream is sys.stderr
        finally:
            self._cleanup_logger(name)

    def test_handler_uses_color_formatter(self):
        name = "test_formatter"
        try:
            logger = setup_logging(name)
            handler = logger.handlers[0]
            assert isinstance(handler.formatter, ColorFormatter)
        finally:
            self._cleanup_logger(name)

    def test_no_duplicate_handlers(self):
        name = "test_no_dupes"
        try:
            setup_logging(name)
            setup_logging(name)
            logger = logging.getLogger(name)
            assert len(logger.handlers) == 1
        finally:
            self._cleanup_logger(name)
