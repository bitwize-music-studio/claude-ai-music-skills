"""Logging configuration for bitwize-music tools."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from tools.shared.colors import Colors

# Sentinel to track whether file logging has already been configured
_file_logging_configured = False


class ColorFormatter(logging.Formatter):
    """Formatter that uses Colors class for TTY-aware colored output."""

    LEVEL_COLORS = {
        logging.DEBUG: ('CYAN', '[DEBUG]'),
        logging.INFO: ('GREEN', '[INFO]'),
        logging.WARNING: ('YELLOW', '[WARN]'),
        logging.ERROR: ('RED', '[ERROR]'),
        logging.CRITICAL: ('RED', '[CRITICAL]'),
    }

    def format(self, record):
        color_name, prefix = self.LEVEL_COLORS.get(record.levelno, ('NC', '[LOG]'))
        color = getattr(Colors, color_name, '')
        nc = Colors.NC
        return f"{color}{prefix}{nc} {record.getMessage()}"


def setup_logging(name, verbose=False, quiet=False, config=None):
    """Configure logging for a tool.

    Args:
        name: Logger name (typically __name__ or tool name)
        verbose: If True, show DEBUG messages
        quiet: If True, show only WARNING and above
        config: Optional config dict; if provided and logging is enabled,
                attaches a file handler via configure_file_logging()

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(ColorFormatter())
        logger.addHandler(handler)

    if verbose:
        logger.setLevel(logging.DEBUG)
    elif quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    if config is not None:
        configure_file_logging(config)

    return logger


def configure_file_logging(config):
    """Attach a RotatingFileHandler to the root logger if config enables it.

    Reads the 'logging' section from config. When enabled, creates a file
    handler with plain-text format (no ANSI colors) and attaches it to the
    root logger so all loggers in the process write to the debug log.

    Args:
        config: Config dict (from read_config() or yaml.safe_load())

    Returns:
        The file handler if logging was enabled, None otherwise.
    """
    global _file_logging_configured

    if config is None:
        return None

    log_config = config.get("logging")
    if not log_config or not log_config.get("enabled", False):
        return None

    # Idempotent — don't add duplicate file handlers
    if _file_logging_configured:
        return None

    # Resolve settings with defaults
    level_str = log_config.get("level", "debug").upper()
    level = getattr(logging, level_str, logging.DEBUG)
    log_file = os.path.expanduser(
        log_config.get("file", "~/.bitwize-music/logs/debug.log")
    )
    max_bytes = log_config.get("max_size_mb", 5) * 1024 * 1024
    backup_count = log_config.get("backup_count", 3)

    # Auto-create log directory
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create handler with plain-text format (no ANSI escape codes)
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Attach to root logger so all loggers inherit it
    root = logging.getLogger()
    root.addHandler(handler)

    # Ensure root logger level allows debug messages through
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    _file_logging_configured = True
    logging.getLogger("bitwize-music").debug(
        "File logging enabled: %s (level=%s)", log_file, level_str
    )

    return handler
