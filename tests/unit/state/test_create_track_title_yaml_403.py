#!/usr/bin/env python3
"""Unit tests for create_track frontmatter YAML escaping (issue #403).

create_track filled the template with a blanket
``template.replace("[Track Title]", title)``. Because the template
frontmatter carries the title as a quoted scalar (``title: "[Track Title]"``),
a title containing a double quote (e.g. ``Say "Goodbye"``) produced
``title: "Say "Goodbye""`` — invalid YAML. parse_frontmatter() then failed and
every frontmatter field (title, track_number, explicit) was silently dropped.

The frontmatter title must receive a properly escaped YAML double-quoted
scalar (json.dumps output is valid YAML) so the whole frontmatter block still
parses and the title round-trips exactly, while the human-readable body (H1,
details table) keeps the raw title.

Usage:
    python -m pytest tests/unit/state/test_create_track_title_yaml_403.py -v
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed (same pattern as test_create_track_validation.py)
# ---------------------------------------------------------------------------

try:
    import mcp  # noqa: F401
except ImportError:
    class _FakeFastMCP:
        def __init__(self, name: str = "") -> None:
            self.name = name
            self._tools: dict = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self, transport: str = "stdio") -> None:
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
    spec = importlib.util.spec_from_file_location("state_server_track_yaml", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import status as _status_mod  # noqa: E402
from tools.state.parsers import parse_frontmatter  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures: realistic filesystem layout + mock cache (mirrors
# test_create_track_validation.py)
# ---------------------------------------------------------------------------


class MockStateCache:
    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state

    def rebuild(self) -> dict:
        return self._state


@pytest.fixture
def cache_with_album(tmp_path: Path):
    """Install a mock cache populated with a single album with a tracks/ dir."""
    content_root = tmp_path / "content"
    album_dir = (
        content_root / "artists" / "test-artist" / "albums" / "electronic"
        / "test-album"
    )
    tracks_dir = album_dir / "tracks"
    tracks_dir.mkdir(parents=True)
    (album_dir / "README.md").write_text(
        "# Test Album\n\n## Album Details\n\n| **Title** | Test Album |\n",
        encoding="utf-8",
    )

    album_data = {
        "title": "Test Album",
        "status": "In Progress",
        "genre": "electronic",
        "explicit": False,
        "path": str(album_dir),
        "track_count": 0,
        "tracks_completed": 0,
        "tracks": {},
    }

    state = {
        "version": 2,
        "config": {
            "content_root": str(content_root),
            "artist_name": "test-artist",
            "generation": {},
        },
        "albums": {"test-album": album_data},
        "session": {},
    }

    orig_cache = _shared_mod.cache
    orig_plugin_root = _shared_mod.PLUGIN_ROOT
    _shared_mod.cache = MockStateCache(state)
    # Real template lives at PROJECT_ROOT/templates/track.md
    _shared_mod.PLUGIN_ROOT = PROJECT_ROOT

    yield state, tracks_dir

    _shared_mod.cache = orig_cache
    _shared_mod.PLUGIN_ROOT = orig_plugin_root


def _create(title: str, track_number="1") -> dict:
    return json.loads(_run(
        _status_mod.create_track("test-album", track_number, title)
    ))


def _written_content(tracks_dir: Path) -> str:
    files = list(tracks_dir.iterdir())
    assert len(files) == 1, f"expected exactly one track file, got {files}"
    return files[0].read_text(encoding="utf-8")


# ===========================================================================
# Frontmatter must stay valid YAML and the title must round-trip exactly
# ===========================================================================


class TestFrontmatterTitleEscaping:
    # NOTE: titles containing a backslash are rejected earlier by
    # _normalize_slug (path-separator guard) and never reach the frontmatter
    # fill, so they are out of scope here. #403 is specifically about a
    # double quote breaking the quoted YAML scalar. json.dumps still escapes
    # backslashes correctly for any title that does reach the fill.
    @pytest.mark.parametrize(
        "title",
        [
            'Say "Goodbye"',
            'Quote "Test" Song',
            '"Leading quote',
            'Trailing quote"',
            "It's a \"trap\"",
        ],
    )
    def test_special_char_title_frontmatter_round_trips(
        self, cache_with_album, title
    ):
        _state, tracks_dir = cache_with_album

        result = _create(title)
        assert result["created"] is True

        content = _written_content(tracks_dir)
        fm = parse_frontmatter(content)

        # Frontmatter must parse cleanly (no degraded _error) ...
        assert "_error" not in fm, fm.get("_error")
        # ... and the title must survive verbatim.
        assert fm.get("title") == title

    def test_double_quote_title_preserves_sibling_frontmatter_fields(
        self, cache_with_album
    ):
        """The bug dropped *all* frontmatter fields, not just the title."""
        _state, tracks_dir = cache_with_album

        result = _create('Say "Goodbye"', track_number="4")
        assert result["created"] is True

        fm = parse_frontmatter(_written_content(tracks_dir))
        assert "_error" not in fm
        assert fm.get("track_number") == 4
        assert fm.get("explicit") is False
        assert fm.get("instrumental") is False

    def test_double_quote_title_kept_readable_in_body(self, cache_with_album):
        """Human-readable body (H1 + details table) keeps the raw title."""
        _state, tracks_dir = cache_with_album

        _create('Say "Goodbye"')
        content = _written_content(tracks_dir)

        assert '# Say "Goodbye"' in content
        assert '| **Title** | Say "Goodbye" |' in content
        # The unescaped raw title must never leak into the frontmatter scalar.
        assert 'title: "Say "Goodbye""' not in content


# ===========================================================================
# Normal titles keep working
# ===========================================================================


class TestNormalTitleUnaffected:
    def test_plain_title_round_trips(self, cache_with_album):
        _state, tracks_dir = cache_with_album

        result = _create("My New Track")
        assert result["created"] is True

        content = _written_content(tracks_dir)
        fm = parse_frontmatter(content)
        assert "_error" not in fm
        assert fm.get("title") == "My New Track"
        assert fm.get("track_number") == 1
        assert "# My New Track" in content
        assert "| **Title** | My New Track |" in content
