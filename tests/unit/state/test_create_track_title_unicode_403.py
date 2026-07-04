#!/usr/bin/env python3
"""Unit tests for create_track frontmatter non-ASCII readability (issue #403 polish).

The #403 fix writes the frontmatter title via ``json.dumps(title)``. With the
default ``ensure_ascii=True`` a non-ASCII title is emitted as ``\\uXXXX``
escapes inside the quoted scalar (e.g. ``title: "caf\\u00e9"`` for ``café``).
It round-trips (YAML decodes the escape back to ``café``), but the on-disk
frontmatter no longer matches the human-readable body (H1/table keep the raw
``café``). Passing ``ensure_ascii=False`` keeps quotes/backslashes escaped
while preserving readable unicode, aligning the frontmatter with the body.

These tests pin the readable-frontmatter behavior; they FAIL on the
``ensure_ascii=True`` output and PASS once ``ensure_ascii=False`` is used.

Usage:
    python -m pytest tests/unit/state/test_create_track_title_unicode_403.py -v
"""

from __future__ import annotations

import asyncio
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
    spec = importlib.util.spec_from_file_location("state_server_track_unicode", SERVER_PATH)
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
# test_create_track_title_yaml_403.py)
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
# Non-ASCII titles stay human-readable in the frontmatter scalar
# ===========================================================================


class TestFrontmatterTitleUnicodeReadable:
    @pytest.mark.parametrize(
        "title",
        [
            "café",
            "naïve",
            "Björk",
            "Résumé",
            "日本語",
        ],
    )
    def test_non_ascii_title_written_readable(self, cache_with_album, title):
        """The frontmatter scalar keeps readable unicode, not \\uXXXX escapes."""
        _state, tracks_dir = cache_with_album

        result = _create(title)
        assert result["created"] is True

        content = _written_content(tracks_dir)

        # The readable, unescaped title appears verbatim in the quoted scalar
        # (this is what ensure_ascii=False produces; ensure_ascii=True would
        # instead emit \uXXXX escapes and this line would be absent).
        assert f'title: "{title}"' in content

        # Frontmatter still parses cleanly and the title round-trips exactly.
        fm = parse_frontmatter(content)
        assert "_error" not in fm, fm.get("_error")
        assert fm.get("title") == title

    def test_frontmatter_matches_readable_body(self, cache_with_album):
        """Frontmatter title reads the same as the H1/table body (no escapes)."""
        _state, tracks_dir = cache_with_album

        _create("café")
        content = _written_content(tracks_dir)

        # Body keeps the raw unicode ...
        assert "# café" in content
        assert "| **Title** | café |" in content
        # ... and the frontmatter now matches it, with no \uXXXX artifact.
        assert 'title: "café"' in content
        assert "caf\\u00e9" not in content


# ===========================================================================
# A double quote must still be escaped (the original #403 correctness fix) —
# ensure_ascii=False must not regress quote/backslash escaping.
# ===========================================================================


class TestSpecialCharsStillEscaped:
    def test_double_quote_title_still_valid_yaml(self, cache_with_album):
        _state, tracks_dir = cache_with_album

        result = _create('Say "Goodbye"')
        assert result["created"] is True

        content = _written_content(tracks_dir)
        fm = parse_frontmatter(content)
        assert "_error" not in fm
        assert fm.get("title") == 'Say "Goodbye"'
        # The raw unescaped quotes must never leak into the scalar.
        assert 'title: "Say "Goodbye""' not in content

    def test_ascii_title_byte_identical_scalar(self, cache_with_album):
        """A plain ASCII title is unaffected by ensure_ascii=False."""
        _state, tracks_dir = cache_with_album

        _create("My New Track")
        content = _written_content(tracks_dir)
        assert 'title: "My New Track"' in content
