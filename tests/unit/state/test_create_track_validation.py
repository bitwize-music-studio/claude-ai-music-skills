#!/usr/bin/env python3
"""Unit tests for create_track track_number validation (issue #372).

create_track previously crashed with an unhandled ValueError when
track_number contained non-digits (e.g. "1a"), and silently created a
spurious track "00" for empty/whitespace input. It must instead return the
module's structured ``{"error": ...}`` JSON for any track_number that is not
a positive integer, and preserve normal behavior for valid ints and numeric
strings.

Usage:
    python -m pytest tests/unit/state/test_create_track_validation.py -v
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
# Mock MCP SDK if not installed (same pattern as test_handlers_rename.py)
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
    spec = importlib.util.spec_from_file_location("state_server_create_track", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import status as _status_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures: realistic filesystem layout + mock cache
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


def _create(track_number, title: str = "My New Track") -> dict:
    return json.loads(_run(
        _status_mod.create_track("test-album", track_number, title)
    ))


# ===========================================================================
# Invalid track_number values — structured error, no exception, no file
# ===========================================================================


class TestCreateTrackInvalidNumbers:
    @pytest.mark.parametrize("bad", ["abc", "1a", "v2", "track1", "", " "])
    def test_non_numeric_string_returns_structured_error(self, cache_with_album, bad):
        _state, tracks_dir = cache_with_album

        result = _create(bad)

        assert "error" in result
        assert "track_number" in result["error"]
        assert list(tracks_dir.iterdir()) == []

    def test_error_names_the_invalid_value(self, cache_with_album):
        result = _create("1a")

        assert "error" in result
        assert "1a" in result["error"]

    def test_none_returns_structured_error(self, cache_with_album):
        _state, tracks_dir = cache_with_album

        result = _create(None)

        assert "error" in result
        assert list(tracks_dir.iterdir()) == []

    @pytest.mark.parametrize("bad", [-1, 0])
    def test_non_positive_int_returns_structured_error(self, cache_with_album, bad):
        _state, tracks_dir = cache_with_album

        result = _create(bad)

        assert "error" in result
        assert str(bad) in result["error"]
        assert list(tracks_dir.iterdir()) == []

    @pytest.mark.parametrize("bad", ["-1", "0", "00"])
    def test_non_positive_numeric_string_returns_structured_error(
        self, cache_with_album, bad
    ):
        _state, tracks_dir = cache_with_album

        result = _create(bad)

        assert "error" in result
        assert list(tracks_dir.iterdir()) == []

    def test_bool_true_returns_structured_error(self, cache_with_album):
        """bool is an int subclass — True must not become track 01."""
        _state, tracks_dir = cache_with_album

        result = _create(True)

        assert "error" in result
        assert "True" in result["error"]
        assert list(tracks_dir.iterdir()) == []


# ===========================================================================
# Valid track_number values — normal behavior preserved
# ===========================================================================


class TestCreateTrackValidNumbers:
    def test_numeric_string_creates_zero_padded_track(self, cache_with_album):
        _state, tracks_dir = cache_with_album

        result = _create("7")

        assert result["created"] is True
        assert result["filename"] == "07-my-new-track.md"
        assert result["track_slug"] == "07-my-new-track"
        track_path = tracks_dir / "07-my-new-track.md"
        assert track_path.exists()
        content = track_path.read_text(encoding="utf-8")
        assert "track_number: 7" in content
        assert "| **Track #** | 07 |" in content

    def test_plain_int_creates_zero_padded_track(self, cache_with_album):
        _state, tracks_dir = cache_with_album

        result = _create(7)

        assert result["created"] is True
        assert result["filename"] == "07-my-new-track.md"
        assert (tracks_dir / "07-my-new-track.md").exists()

    def test_zero_padded_string_preserved(self, cache_with_album):
        _state, tracks_dir = cache_with_album

        result = _create("03")

        assert result["created"] is True
        assert result["filename"] == "03-my-new-track.md"
        content = (tracks_dir / "03-my-new-track.md").read_text(encoding="utf-8")
        assert "track_number: 3" in content

    def test_two_digit_number_not_repadded(self, cache_with_album):
        _state, _tracks_dir = cache_with_album

        result = _create("12")

        assert result["created"] is True
        assert result["filename"] == "12-my-new-track.md"

    def test_existing_track_still_reports_duplicate(self, cache_with_album):
        _state, tracks_dir = cache_with_album
        (tracks_dir / "07-my-new-track.md").write_text("stub", encoding="utf-8")

        result = _create("7")

        assert result["created"] is False
        assert "error" in result
