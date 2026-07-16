"""Configuration loading and override validation for bitwize-music tools."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"

logger = logging.getLogger(__name__)

# Known override files and their expected format
OVERRIDE_FILES: dict[str, dict[str, Any]] = {
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


# YAML 1.1 boolean literals. PyYAML converts these to bool when unquoted, so
# a string here means the user quoted the value in config.yaml/frontmatter.
_YAML_BOOL_LITERALS: dict[str, bool] = {
    "true": True, "yes": True, "on": True, "1": True,
    "false": False, "no": False, "off": False, "0": False,
}


def parse_yaml_bool(value: Any) -> bool:
    """Coerce a YAML-sourced value to bool, honoring quoted boolean strings.

    ``bool(value)`` treats any non-empty string as True, silently inverting
    quoted YAML booleans like ``"false"`` or ``"no"`` (#388). Accepts real
    bools, 0/1 numbers, and YAML 1.1 boolean literals (case-insensitive);
    raises ValueError for anything else so callers can fall back to their
    key's default with a warning.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        parsed = _YAML_BOOL_LITERALS.get(value.strip().lower())
        if parsed is not None:
            return parsed
    raise ValueError(f"not a boolean: {value!r}")


def coerce_yaml_bool(value: Any, *, default: bool = False, context: str = "") -> bool:
    """parse_yaml_bool with a warn-and-default fallback for gate sites.

    For boolean config gates where an unparseable value should fall back to
    the key's documented default rather than raise. ``context`` names the
    key in the warning (e.g. ``"cloud.enabled"``).
    """
    try:
        return parse_yaml_bool(value)
    except ValueError:
        logger.warning(
            "Cannot interpret %s=%r as a boolean — using default %s",
            context or "value",
            value,
            default,
        )
        return default


def load_config(
    required: bool = False,
    fallback: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Load ~/.bitwize-music/config.yaml.

    Args:
        required: If True, exit with error when config is missing.
        fallback: Default dict to return when config is missing and not required.

    Returns:
        Parsed config dict ({} for an empty file), or fallback/None when the
        config is missing, unreadable, unparseable, or not a YAML mapping.
    """
    if not CONFIG_PATH.exists():
        if required:
            import sys
            logger.error("Config file not found at %s", CONFIG_PATH)
            logger.error("Run /bitwize-music:configure to set up your configuration.")
            sys.exit(1)
        return fallback

    if yaml is None:
        logger.error("pyyaml is not installed. Install with: pip install pyyaml")  # type: ignore[unreachable]
        return fallback

    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.error("Error reading config: %s", e)
        if required:
            import sys
            sys.exit(1)
        return fallback

    if data is None:
        return {}
    if not isinstance(data, dict):
        # Valid YAML but wrong shape (e.g. top-level list or scalar) — callers
        # expect a mapping and would crash on .get() (#389)
        logger.error(
            "Config at %s parsed as %s, not a mapping — the file must contain "
            "top-level `key: value` pairs",
            CONFIG_PATH,
            type(data).__name__,
        )
        if required:
            import sys
            sys.exit(1)
        return fallback
    return data


def validate_overrides(overrides_dir: Path) -> list[dict[str, str]]:
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
    issues: list[dict[str, str]] = []

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
                    content = entry.read_text(encoding='utf-8')
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
