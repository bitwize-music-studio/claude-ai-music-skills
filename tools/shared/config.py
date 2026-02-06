"""Configuration loading and override validation for bitwize-music tools."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"

logger = logging.getLogger(__name__)

# Known override files and their expected format
OVERRIDE_FILES = {
    'CLAUDE.md': {
        'extension': '.md',
        'must_contain': None,  # Free-form markdown instructions
        'max_size_kb': 500,
    },
    'pronunciation-guide.md': {
        'extension': '.md',
        'must_contain': re.compile(r'\|.*\|.*\|', re.MULTILINE),  # Should have a table
        'max_size_kb': 200,
    },
}


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


def validate_overrides(overrides_dir: Path) -> List[Dict[str, str]]:
    """Validate override files in the given directory.

    Checks that override files follow expected format:
    - Correct file extension
    - Not excessively large
    - Contains expected structural elements (e.g., tables for pronunciation)

    Args:
        overrides_dir: Path to the overrides directory.

    Returns:
        List of issue dicts with 'file', 'level' ('error'|'warning'), and 'message' keys.
        Empty list means all overrides are valid.
    """
    issues: List[Dict[str, str]] = []

    if not overrides_dir.exists():
        return issues  # No overrides dir is fine (optional)

    if not overrides_dir.is_dir():
        issues.append({
            'file': str(overrides_dir),
            'level': 'error',
            'message': 'Overrides path exists but is not a directory',
        })
        return issues

    for entry in sorted(overrides_dir.iterdir()):
        if entry.name.startswith('.'):
            continue

        # Check if it's a known override file
        if entry.name in OVERRIDE_FILES:
            spec = OVERRIDE_FILES[entry.name]

            # Check extension
            if entry.suffix != spec['extension']:
                issues.append({
                    'file': entry.name,
                    'level': 'error',
                    'message': f"Expected {spec['extension']} extension, got {entry.suffix}",
                })
                continue

            # Check size
            size_kb = entry.stat().st_size / 1024
            if size_kb > spec['max_size_kb']:
                issues.append({
                    'file': entry.name,
                    'level': 'warning',
                    'message': f"File is {size_kb:.0f}KB, exceeds recommended {spec['max_size_kb']}KB",
                })

            # Check content pattern
            if spec['must_contain'] is not None:
                try:
                    content = entry.read_text()
                    if not spec['must_contain'].search(content):
                        issues.append({
                            'file': entry.name,
                            'level': 'warning',
                            'message': 'File does not contain expected structure '
                                       '(e.g., pronunciation guide should have a table)',
                        })
                except (OSError, UnicodeDecodeError) as e:
                    issues.append({
                        'file': entry.name,
                        'level': 'error',
                        'message': f"Cannot read file: {e}",
                    })
        else:
            # Unknown override file — warn but don't fail
            if entry.suffix not in ('.md', '.yaml', '.yml'):
                issues.append({
                    'file': entry.name,
                    'level': 'warning',
                    'message': f"Unexpected file type in overrides directory: {entry.suffix}",
                })

    return issues
