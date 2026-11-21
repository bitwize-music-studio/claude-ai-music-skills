#!/usr/bin/env python3
"""Regression tests: a BOM before frontmatter, and IDEAS **Key:** fields (#669).

7. A file saved with a UTF-8 byte order mark starts with U+FEFF, not "---",
   so every ``startswith('---')`` check called it a file with no frontmatter:
   a README parsed with ``release_date`` None, ``explicit`` False and no
   warning. The parser and every other frontmatter reader and writer now look
   past the mark.
9. ``_extract_bold_field`` read ``**Status**: Pending`` but not
   ``**Status:** Pending``, so a hand-edited idea fell back to Pending and lost
   its genre.

Usage:
    python -m pytest tests/unit/state/test_frontmatter_bom_ideas_669.py -v
"""

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

try:
    import mcp.server.fastmcp  # noqa: F401
except ImportError:

    class _FakeFastMCP:
        def __init__(self, name="", **kwargs):
            self.name = name
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self, transport="stdio"):
            pass

    mcp_mod = types.ModuleType("mcp")
    mcp_server_mod = types.ModuleType("mcp.server")
    mcp_fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    mcp_fastmcp_mod.FastMCP = _FakeFastMCP
    mcp_mod.server = mcp_server_mod
    mcp_server_mod.fastmcp = mcp_fastmcp_mod

    sys.modules["mcp"] = mcp_mod
    sys.modules["mcp.server"] = mcp_server_mod
    sys.modules["mcp.server.fastmcp"] = mcp_fastmcp_mod


def _import_server():
    spec = importlib.util.spec_from_file_location("state_server_bom_669", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_server = _import_server()
from handlers import _shared as _shared_mod
from handlers import generation as _generation_mod
from handlers import streaming as _streaming_mod
from tools.state.indexer import parse_migration_file
from tools.state.parsers import (
    _extract_bold_field,
    parse_album_readme,
    parse_frontmatter,
    parse_ideas_file,
    parse_track_file,
)

BOM = "\ufeff"


# ===========================================================================
# 7. BOM before the frontmatter
# ===========================================================================


class TestParseFrontmatterBom:

    def test_bom_frontmatter_parses(self):
        fm = parse_frontmatter(BOM + "---\ntitle: My Song\nexplicit: true\n---\n# My Song\n")
        assert fm == {"title": "My Song", "explicit": True}

    def test_bom_track_file_keeps_explicit(self, tmp_path):
        track = tmp_path / "01-my-song.md"
        track.write_text(
            BOM + "---\ntitle: My Song\nexplicit: true\n---\n\n# My Song\n\n"
            "| Attribute | Detail |\n|---|---|\n| **Status** | Final |\n",
            encoding="utf-8",
        )
        assert parse_track_file(track)["explicit"] is True

    def test_bom_album_readme_keeps_release_date(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            BOM + "---\ntitle: Alb\nrelease_date: 2026-01-15\nexplicit: true\n---\n"
            "# Alb\n\n| **Status** | In Progress |\n",
            encoding="utf-8",
        )
        result = parse_album_readme(readme)
        assert str(result["release_date"]) == "2026-01-15"
        assert result["explicit"] is True


class TestOtherFrontmatterReadersBom:

    def test_update_frontmatter_block(self, tmp_path):
        md = tmp_path / "track.md"
        md.write_text(BOM + "---\ntitle: X\n---\n# Body\n", encoding="utf-8")
        ok, err = _shared_mod._update_frontmatter_block(md, "sheet_music", {"pdf": "a.pdf"})
        assert (ok, err) == (True, None)
        assert parse_frontmatter(md.read_text(encoding="utf-8"))["sheet_music"] == {"pdf": "a.pdf"}

    def test_generation_frontmatter_bounds(self):
        assert _generation_mod._frontmatter_bounds([BOM + "---", "title: X", "---", "body"]) == 2

    def test_migration_file(self, tmp_path):
        note = tmp_path / "0.1.0.md"
        note.write_text(BOM + "---\nversion: 0.1.0\nsummary: hi\n---\nBody\n", encoding="utf-8")
        parsed = parse_migration_file(note)
        assert parsed is not None
        assert parsed["summary"] == "hi"

    def test_update_streaming_url(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            BOM + '---\ntitle: Test Album\nstreaming:\n  spotify: "https://old-url.com"\n---\n# Test Album\n',
            encoding="utf-8",
        )
        state = {"version": 2, "albums": {"test-album": {
            "title": "Test Album", "status": "Released", "genre": "electronic",
            "path": str(tmp_path), "streaming_urls": {"spotify": "https://old-url.com"}, "tracks": {},
        }}}

        class _Cache:
            def get_state(self):
                return state

            def get_state_ref(self):
                return state

            def rebuild(self):
                return state

        orig_cache = _shared_mod.cache
        _shared_mod.cache = _Cache()
        try:
            with patch("tools.state.indexer.write_state"), \
                 patch("handlers.database._check_db_deps", side_effect=ImportError("no db")):
                result = json.loads(asyncio.run(_streaming_mod.update_streaming_url(
                    "test-album", "spotify", "https://open.spotify.com/album/new",
                )))
        finally:
            _shared_mod.cache = orig_cache
        assert "error" not in result
        fm = parse_frontmatter(readme.read_text(encoding="utf-8"))
        assert fm["streaming"]["spotify"] == "https://open.spotify.com/album/new"


# ===========================================================================
# 9. IDEAS **Key:** fields
# ===========================================================================


class TestBoldColonIdeaFields:

    def test_colon_inside_bold(self):
        assert _extract_bold_field("**Status:** In Progress", "Status") == "In Progress"

    def test_colon_after_bold_still_works(self):
        # Guard: the documented form.
        assert _extract_bold_field("**Status**: In Progress", "Status") == "In Progress"

    def test_bold_without_colon_is_not_a_field(self):
        # Guard: a colon is still required, inside or after the bold.
        assert _extract_bold_field("**Status** In Progress", "Status") is None

    def test_ideas_file(self, tmp_path):
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text(
            "# Ideas\n\n## Ideas\n\n### Salt Roads\n\n**Genre:** folk\n**Status:** In Progress\n",
            encoding="utf-8",
        )
        item = parse_ideas_file(ideas)["items"][0]
        assert item["status"] == "In Progress"
        assert item["genre"] == "folk"
