#!/usr/bin/env python3
"""
Unit tests for CHANGELOG release notes extraction.

Usage:
    python -m pytest tools/release/tests/test_extract_changelog.py -v
"""

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from tools.release.extract_changelog import extract_release_notes


SAMPLE_CHANGELOG = dedent("""\
    # Changelog

    ## [Unreleased]

    ## [0.3.0] - 2026-01-15

    ### Added
    - New feature X
    - New feature Y

    ### Fixed
    - Bug fix Z

    ## [0.2.0] - 2026-01-10

    ### Added
    - Initial feature A

    ## [0.1.0] - 2026-01-01

    ### Added
    - First release
""")


class TestExtractReleaseNotes:
    """Tests for extract_release_notes()."""

    def test_extracts_middle_version(self, tmp_path):
        """Extracts notes for a version between other versions."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        notes = extract_release_notes("0.2.0", cl)
        assert "Initial feature A" in notes
        assert "New feature X" not in notes
        assert "First release" not in notes

    def test_extracts_latest_version(self, tmp_path):
        """Extracts notes for the most recent versioned section."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        notes = extract_release_notes("0.3.0", cl)
        assert "New feature X" in notes
        assert "Bug fix Z" in notes
        assert "Initial feature A" not in notes

    def test_extracts_last_version(self, tmp_path):
        """Extracts notes for the final version in the file."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        notes = extract_release_notes("0.1.0", cl)
        assert "First release" in notes
        assert "Initial feature A" not in notes

    def test_missing_version_raises(self, tmp_path):
        """Missing version raises ValueError."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        with pytest.raises(ValueError, match="No section found"):
            extract_release_notes("99.99.99", cl)

    def test_empty_section_raises(self, tmp_path):
        """Empty version section raises ValueError."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(dedent("""\
            # Changelog

            ## [1.0.0] - 2026-01-01

            ## [0.9.0] - 2025-12-01

            ### Added
            - Something
        """))

        with pytest.raises(ValueError, match="exists but is empty"):
            extract_release_notes("1.0.0", cl)

    def test_missing_file_raises(self, tmp_path):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_release_notes("1.0.0", tmp_path / "nope.md")

    def test_strips_whitespace(self, tmp_path):
        """Result has no leading/trailing whitespace."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        notes = extract_release_notes("0.3.0", cl)
        assert notes == notes.strip()

    def test_version_with_dots_not_regex_wildcard(self, tmp_path):
        """Dots in version are literal, not regex wildcards."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(dedent("""\
            # Changelog

            ## [0.3.0] - 2026-01-15

            ### Added
            - Real notes

            ## [0X3Y0] - 2026-01-10

            ### Added
            - Fake notes
        """))

        notes = extract_release_notes("0.3.0", cl)
        assert "Real notes" in notes
        assert "Fake notes" not in notes

    def test_preserves_markdown_structure(self, tmp_path):
        """Extracted notes preserve ### headings and list structure."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        notes = extract_release_notes("0.3.0", cl)
        assert "### Added" in notes
        assert "### Fixed" in notes
        assert "- New feature X" in notes


class TestExtractChangelogCLI:
    """Tests for CLI invocation."""

    def test_cli_success(self, tmp_path):
        """CLI prints notes and exits 0 for valid version."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        result = subprocess.run(
            [sys.executable, "-m", "tools.release.extract_changelog", "0.3.0", str(cl)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0
        assert "New feature X" in result.stdout

    def test_cli_missing_version(self, tmp_path):
        """CLI exits 1 for missing version."""
        cl = tmp_path / "CHANGELOG.md"
        cl.write_text(SAMPLE_CHANGELOG)

        result = subprocess.run(
            [sys.executable, "-m", "tools.release.extract_changelog", "99.99.99", str(cl)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_cli_no_args(self):
        """CLI exits 1 with usage message when no args given."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.release.extract_changelog"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 1
        assert "Usage" in result.stderr
