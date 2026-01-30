"""Configuration loading for bitwize-music tools."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"

logger = logging.getLogger(__name__)


def load_config(
    required: bool = False,
    fallback: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Load ~/.bitwize-music/config.yaml.

    Args:
        required: If True, exit with error when config is missing.
        fallback: Default dict to return when config is missing and not required.

    Returns:
        Parsed config dict, fallback dict, or None if missing/invalid.
    """
    if not CONFIG_PATH.exists():
        if required:
            import sys
            logger.error("Config file not found at %s", CONFIG_PATH)
            logger.error("Run /bitwize-music:configure to set up your configuration.")
            sys.exit(1)
        return fallback

    if yaml is None:
        logger.error("pyyaml is not installed. Install with: pip install pyyaml")
        return fallback

    try:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        logger.error("Error reading config: %s", e)
        if required:
            import sys
            sys.exit(1)
        return fallback
