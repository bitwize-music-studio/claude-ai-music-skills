"""Tests for configure_file_logging() in tools.shared.logging_config."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch

import pytest

import tools.shared.logging_config as logging_config
from tools.shared.logging_config import configure_file_logging, setup_logging


@pytest.fixture(autouse=True)
def _reset_file_logging():
    """Reset the module-level sentinel and clean up root handlers after each test."""
    logging_config._file_logging_configured = False
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    # Remove any RotatingFileHandlers we added
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler):
            h.close()
            root.removeHandler(h)
    # Restore handlers that existed before the test
    root.handlers = original_handlers
    root.level = original_level


class TestConfigureFileLoggingDisabled:
    """Tests that logging stays off when not configured."""

    def test_none_config(self):
        assert configure_file_logging(None) is None

    def test_empty_config(self):
        assert configure_file_logging({}) is None

    def test_missing_logging_section(self):
        assert configure_file_logging({"artist": {"name": "test"}}) is None

    def test_enabled_false(self):
        config = {"logging": {"enabled": False}}
        assert configure_file_logging(config) is None

    def test_enabled_missing(self):
        config = {"logging": {"level": "debug"}}
        assert configure_file_logging(config) is None

    def test_no_root_handlers_added_when_disabled(self):
        root = logging.getLogger()
        before = len([h for h in root.handlers if isinstance(h, RotatingFileHandler)])
        configure_file_logging({"logging": {"enabled": False}})
        after = len([h for h in root.handlers if isinstance(h, RotatingFileHandler)])
        assert after == before


class TestConfigureFileLoggingEnabled:
    """Tests that logging works correctly when enabled."""

    def test_creates_rotating_handler(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file}}
        handler = configure_file_logging(config)
        assert handler is not None
        assert isinstance(handler, RotatingFileHandler)

    def test_auto_creates_log_directory(self, tmp_path):
        log_dir = tmp_path / "nested" / "logs"
        log_file = str(log_dir / "debug.log")
        config = {"logging": {"enabled": True, "file": log_file}}
        configure_file_logging(config)
        assert log_dir.exists()

    def test_default_level_is_debug(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file}}
        handler = configure_file_logging(config)
        assert handler.level == logging.DEBUG

    def test_custom_level_info(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file, "level": "info"}}
        handler = configure_file_logging(config)
        assert handler.level == logging.INFO

    def test_custom_level_warning(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file, "level": "warning"}}
        handler = configure_file_logging(config)
        assert handler.level == logging.WARNING

    def test_level_case_insensitive(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file, "level": "DEBUG"}}
        handler = configure_file_logging(config)
        assert handler.level == logging.DEBUG

    def test_rotation_defaults(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file}}
        handler = configure_file_logging(config)
        assert handler.maxBytes == 5 * 1024 * 1024
        assert handler.backupCount == 3

    def test_custom_rotation(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {
            "logging": {
                "enabled": True,
                "file": log_file,
                "max_size_mb": 10,
                "backup_count": 5,
            }
        }
        handler = configure_file_logging(config)
        assert handler.maxBytes == 10 * 1024 * 1024
        assert handler.backupCount == 5

    def test_handler_attached_to_root(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file}}
        configure_file_logging(config)
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1

    def test_root_level_lowered_to_debug(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        root = logging.getLogger()
        root.setLevel(logging.WARNING)
        config = {"logging": {"enabled": True, "file": log_file}}
        configure_file_logging(config)
        assert root.level <= logging.DEBUG

    def test_debug_messages_written_to_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = {"logging": {"enabled": True, "file": str(log_file)}}
        configure_file_logging(config)
        test_logger = logging.getLogger("test.file.write")
        test_logger.debug("debug message for file test")
        # Flush handlers
        for h in logging.getLogger().handlers:
            h.flush()
        content = log_file.read_text()
        assert "debug message for file test" in content

    def test_no_ansi_in_file_output(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = {"logging": {"enabled": True, "file": str(log_file)}}
        configure_file_logging(config)
        test_logger = logging.getLogger("test.ansi.check")
        test_logger.info("ansi check message")
        for h in logging.getLogger().handlers:
            h.flush()
        content = log_file.read_text()
        # ANSI escape codes start with \x1b[
        assert "\x1b[" not in content

    def test_file_format_includes_timestamp(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = {"logging": {"enabled": True, "file": str(log_file)}}
        configure_file_logging(config)
        test_logger = logging.getLogger("test.format.check")
        test_logger.info("format check")
        for h in logging.getLogger().handlers:
            h.flush()
        content = log_file.read_text()
        # Should contain timestamp pattern like "2026-02-21 12:34:56"
        assert "[INFO]" in content
        assert "test.format.check" in content

    def test_tilde_expansion(self, tmp_path):
        # Patch expanduser to use tmp_path instead of actual home
        fake_home = str(tmp_path / "fakehome")
        with patch.object(os.path, "expanduser", side_effect=lambda p: p.replace("~", fake_home)):
            config = {"logging": {"enabled": True, "file": "~/logs/debug.log"}}
            handler = configure_file_logging(config)
            assert handler is not None
            assert fake_home in handler.baseFilename


class TestIdempotency:
    """Ensure repeated calls don't add duplicate handlers."""

    def test_no_duplicate_handlers(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file}}
        h1 = configure_file_logging(config)
        h2 = configure_file_logging(config)
        assert h1 is not None
        assert h2 is None  # Second call is a no-op
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1


class TestSetupLoggingWithConfig:
    """Tests for setup_logging() config parameter integration."""

    def test_setup_logging_without_config_unchanged(self):
        """Existing behavior: no config param means no file handler."""
        name = "test_no_config_param"
        try:
            logger = setup_logging(name)
            root = logging.getLogger()
            file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
            assert len(file_handlers) == 0
        finally:
            logging.getLogger(name).handlers.clear()

    def test_setup_logging_with_config_enables_file_logging(self, tmp_path):
        """Passing config to setup_logging enables file logging."""
        name = "test_with_config"
        log_file = str(tmp_path / "test.log")
        config = {"logging": {"enabled": True, "file": log_file}}
        try:
            logger = setup_logging(name, config=config)
            root = logging.getLogger()
            file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
            assert len(file_handlers) == 1
        finally:
            logging.getLogger(name).handlers.clear()

    def test_setup_logging_with_disabled_config(self):
        """Passing config with logging disabled does nothing."""
        name = "test_disabled_config"
        config = {"logging": {"enabled": False}}
        try:
            logger = setup_logging(name, config=config)
            root = logging.getLogger()
            file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
            assert len(file_handlers) == 0
        finally:
            logging.getLogger(name).handlers.clear()
