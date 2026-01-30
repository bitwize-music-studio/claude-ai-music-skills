"""Logging configuration for bitwize-music tools."""

import logging
import sys

from tools.shared.colors import Colors


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


def setup_logging(name, verbose=False, quiet=False):
    """Configure logging for a tool.

    Args:
        name: Logger name (typically __name__ or tool name)
        verbose: If True, show DEBUG messages
        quiet: If True, show only WARNING and above

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

    return logger
