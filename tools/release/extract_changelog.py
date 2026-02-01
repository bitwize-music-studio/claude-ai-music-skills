#!/usr/bin/env python3
"""
Extract release notes for a specific version from CHANGELOG.md.

Finds the ## [VERSION] section and extracts everything up to the next
## [ heading. Validates the result is non-empty.

Usage:
    python tools/release/extract_changelog.py 0.23.0
    python tools/release/extract_changelog.py 0.23.0 path/to/CHANGELOG.md

Exit codes:
    0 - Success, notes printed to stdout
    1 - Version not found or section is empty
"""

import re
import sys
from pathlib import Path


def extract_release_notes(version: str, changelog_path: Path) -> str:
    """Extract release notes for a version from a changelog file.

    Args:
        version: Version string (e.g., "0.23.0").
        changelog_path: Path to the CHANGELOG.md file.

    Returns:
        Extracted release notes text, stripped of leading/trailing whitespace.

    Raises:
        FileNotFoundError: If changelog_path does not exist.
        ValueError: If version section not found or is empty.
    """
    text = changelog_path.read_text(encoding="utf-8")

    # Escape dots in version for regex
    escaped = re.escape(version)

    # Match from ## [VERSION] (with optional date suffix) to next ## [ heading
    pattern = rf"^## \[{escaped}\][^\n]*\n(.*?)(?=^## \[|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)

    if match is None:
        raise ValueError(f"No section found for version [{version}]")

    notes = match.group(1).strip()
    if not notes:
        raise ValueError(f"Section [{version}] exists but is empty")

    return notes


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: extract_changelog.py VERSION [CHANGELOG_PATH]", file=sys.stderr)
        return 1

    version = sys.argv[1]
    changelog_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("CHANGELOG.md")

    try:
        notes = extract_release_notes(version, changelog_path)
    except FileNotFoundError:
        print(f"Error: {changelog_path} not found", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
