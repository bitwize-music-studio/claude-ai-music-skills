"""Tests for _update_frontmatter_block non-mapping frontmatter validation (issue #378).

``_update_frontmatter_block`` documents a ``(True, None)`` / ``(False, error)``
contract, but frontmatter that parses to a YAML list or scalar used to raise
``TypeError`` at ``fm[key] = values``. These tests pin the contract: non-dict
frontmatter must return ``(False, error_string)`` and leave the file untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers._shared import _update_frontmatter_block  # noqa: E402


class TestNonMappingFrontmatter:
    """Non-dict frontmatter must return (False, error), never raise."""

    def test_list_frontmatter_returns_false_error(self, tmp_path: Path) -> None:
        md = tmp_path / "track.md"
        original = "---\n- a\n- b\n---\n# Body\n"
        md.write_text(original, encoding="utf-8")

        ok, err = _update_frontmatter_block(md, "sheet_music", {"pdf": "http://x/y.pdf"})

        assert ok is False
        assert err is not None
        assert "not a mapping" in err
        assert str(md) in err
        assert "list" in err
        # File must be left untouched on failure.
        assert md.read_text(encoding="utf-8") == original

    def test_scalar_frontmatter_returns_false_error(self, tmp_path: Path) -> None:
        md = tmp_path / "track.md"
        original = "---\njust a string\n---\n# Body\n"
        md.write_text(original, encoding="utf-8")

        ok, err = _update_frontmatter_block(md, "sheet_music", {"pdf": "http://x/y.pdf"})

        assert ok is False
        assert err is not None
        assert "not a mapping" in err
        assert str(md) in err
        assert "str" in err
        assert md.read_text(encoding="utf-8") == original


class TestValidMappingFrontmatter:
    """Regression guard: dict frontmatter keeps working."""

    def test_mapping_frontmatter_updates_successfully(self, tmp_path: Path) -> None:
        md = tmp_path / "track.md"
        md.write_text("---\ntitle: Song\n---\n# Body\n", encoding="utf-8")

        ok, err = _update_frontmatter_block(md, "sheet_music", {"pdf": "http://x/y.pdf"})

        assert ok is True
        assert err is None
        text = md.read_text(encoding="utf-8")
        assert "title: Song" in text
        assert "sheet_music:" in text
        assert "pdf: http://x/y.pdf" in text
        assert "# Body" in text
