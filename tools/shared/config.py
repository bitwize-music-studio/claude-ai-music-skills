"""Configuration loading and validation for bitwize-music tools."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate config structure and required fields.

    Args:
        config: Parsed config dict from load_config().

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: List[str] = []

    if not isinstance(config, dict):
        return ["Config is not a dict"]

    # Required: artist.name
    artist = config.get('artist')
    if not isinstance(artist, dict):
        errors.append("Missing 'artist' section")
    elif not isinstance(artist.get('name'), str) or not artist['name'].strip():
        errors.append("'artist.name' must be a non-empty string")

    # Required: paths.content_root, paths.audio_root
    paths = config.get('paths')
    if not isinstance(paths, dict):
        errors.append("Missing 'paths' section")
    else:
        for field in ('content_root', 'audio_root'):
            val = paths.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"'paths.{field}' must be a non-empty string")

        # Optional fields — validated only if present
        for field in ('documents_root',):
            val = paths.get(field)
            if val is not None and (not isinstance(val, str) or not val.strip()):
                errors.append(f"'paths.{field}' must be a non-empty string if set")

    # Optional: generation.service
    generation = config.get('generation')
    if generation is not None:
        if not isinstance(generation, dict):
            errors.append("'generation' must be a dict if set")
        else:
            service = generation.get('service')
            if service is not None and (not isinstance(service, str) or not service.strip()):
                errors.append("'generation.service' must be a non-empty string if set")

    return errors
