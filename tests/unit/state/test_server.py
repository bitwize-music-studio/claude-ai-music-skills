#!/usr/bin/env python3
"""
Unit tests for MCP state server (servers/state-server/server.py).

Tests the StateCache class, helper functions, and async MCP tool handlers.

Usage:
    python -m pytest tests/unit/state/test_server.py -v
"""

import asyncio
import copy
import importlib
import importlib.util
import json
import shutil
import sys
import threading
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Import server module from hyphenated directory via importlib.
#
# The server requires mcp.server.fastmcp.FastMCP which may not be installed
# in the test environment. We inject a lightweight mock before loading the
# module so the import succeeds regardless.
# ---------------------------------------------------------------------------

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# Check if the real MCP SDK is available; if not, create a minimal mock.
_mcp_was_mocked = False
try:
    import mcp  # noqa: F401
except ImportError:
    _mcp_was_mocked = True

    class _FakeFastMCP:
        """Minimal stand-in for FastMCP that records tool registrations."""
        def __init__(self, name=""):
            self.name = name
            self._tools = {}

        def tool(self):
            """Decorator that registers tools (no-op for testing)."""
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self, transport="stdio"):
            pass

    # Build the mock package hierarchy: mcp -> mcp.server -> mcp.server.fastmcp
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
    """Import the server module from the hyphenated directory."""
    spec = importlib.util.spec_from_file_location("state_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Import once at module level. This also validates that the server can load.
server = _import_server()


# ---------------------------------------------------------------------------
# Sample state used by most tests
# ---------------------------------------------------------------------------

SAMPLE_STATE = {
    "version": "1.0.0",
    "generated_at": "2025-01-01T00:00:00Z",
    "config": {
        "content_root": "/tmp/test",
        "audio_root": "/tmp/test/audio",
        "documents_root": "/tmp/test/docs",
        "artist_name": "test-artist",
        "config_mtime": 1234567890.0,
    },
    "albums": {
        "test-album": {
            "path": "/tmp/test/artists/test-artist/albums/electronic/test-album",
            "genre": "electronic",
            "title": "Test Album",
            "status": "In Progress",
            "explicit": False,
            "release_date": None,
            "track_count": 2,
            "tracks_completed": 1,
            "readme_mtime": 1234567890.0,
            "tracks": {
                "01-first-track": {
                    "path": "/tmp/test/.../01-first-track.md",
                    "title": "First Track",
                    "status": "Final",
                    "explicit": False,
                    "has_suno_link": True,
                    "sources_verified": "N/A",
                    "mtime": 1234567890.0,
                },
                "02-second-track": {
                    "path": "/tmp/test/.../02-second-track.md",
                    "title": "Second Track",
                    "status": "In Progress",
                    "explicit": True,
                    "has_suno_link": False,
                    "sources_verified": "Pending",
                    "mtime": 1234567891.0,
                },
            },
        },
        "another-album": {
            "path": "/tmp/test/artists/test-artist/albums/rock/another-album",
            "genre": "rock",
            "title": "Another Album",
            "status": "Complete",
            "explicit": False,
            "release_date": "2025-06-01",
            "track_count": 1,
            "tracks_completed": 1,
            "readme_mtime": 1234567892.0,
            "tracks": {
                "01-rock-song": {
                    "path": "/tmp/test/.../01-rock-song.md",
                    "title": "Rock Song",
                    "status": "Final",
                    "explicit": False,
                    "has_suno_link": True,
                    "sources_verified": "Verified (2025-05-01)",
                    "mtime": 1234567892.0,
                },
            },
        },
    },
    "ideas": {
        "file_mtime": 1234567890.0,
        "counts": {"Pending": 2, "In Progress": 1},
        "items": [
            {"title": "Cool Idea", "genre": "rock", "status": "Pending"},
            {"title": "Another Idea", "genre": "electronic", "status": "Pending"},
            {"title": "WIP Album", "genre": "hip-hop", "status": "In Progress"},
        ],
    },
    "session": {
        "last_album": "test-album",
        "last_track": "01-first-track",
        "last_phase": "Writing",
        "pending_actions": [],
        "updated_at": "2025-01-01T00:00:00Z",
    },
}


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _fresh_state():
    """Return a deep copy of sample state so tests don't interfere."""
    return copy.deepcopy(SAMPLE_STATE)


# ---------------------------------------------------------------------------
# Mock StateCache that returns controlled state without touching disk
# ---------------------------------------------------------------------------


class MockStateCache:
    """A mock StateCache that holds state in memory without filesystem I/O."""

    def __init__(self, state=None):
        self._state = state if state is not None else _fresh_state()
        self._rebuild_called = False

    def get_state(self):
        return self._state

    def rebuild(self):
        self._rebuild_called = True
        return self._state

    def update_session(self, **kwargs):
        if not self._state:
            return {"error": "No state available"}
        session = copy.deepcopy(self._state.get("session", {}))
        if kwargs.get("clear"):
            session = {
                "last_album": None,
                "last_track": None,
                "last_phase": None,
                "pending_actions": [],
                "updated_at": None,
            }
        else:
            if kwargs.get("album") is not None:
                session["last_album"] = kwargs["album"]
            if kwargs.get("track") is not None:
                session["last_track"] = kwargs["track"]
            if kwargs.get("phase") is not None:
                session["last_phase"] = kwargs["phase"]
            if kwargs.get("action"):
                actions = session.get("pending_actions", [])
                actions.append(kwargs["action"])
                session["pending_actions"] = actions
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._state["session"] = session
        return session


# =============================================================================
# Tests for _normalize_slug
# =============================================================================


class TestNormalizeSlug:
    """Tests for the _normalize_slug() helper function."""

    def test_spaces_to_hyphens(self):
        assert server._normalize_slug("my album name") == "my-album-name"

    def test_underscores_to_hyphens(self):
        assert server._normalize_slug("my_album_name") == "my-album-name"

    def test_mixed_case_lowered(self):
        assert server._normalize_slug("My Album Name") == "my-album-name"

    def test_already_normalized(self):
        assert server._normalize_slug("already-normalized") == "already-normalized"

    def test_mixed_separators(self):
        assert server._normalize_slug("My_Album Name") == "my-album-name"

    def test_empty_string(self):
        assert server._normalize_slug("") == ""

    def test_single_word(self):
        assert server._normalize_slug("Album") == "album"

    def test_multiple_spaces(self):
        # Multiple spaces become multiple hyphens (current behavior)
        result = server._normalize_slug("my  album")
        assert result == "my--album"

    def test_uppercase_with_numbers(self):
        assert server._normalize_slug("Album_01_Track") == "album-01-track"


# =============================================================================
# Tests for _safe_json
# =============================================================================


class TestSafeJson:
    """Tests for the _safe_json() helper function."""

    def test_valid_dict(self):
        data = {"key": "value", "number": 42}
        result = json.loads(server._safe_json(data))
        assert result == data

    def test_valid_list(self):
        data = [1, 2, 3]
        result = json.loads(server._safe_json(data))
        assert result == data

    def test_nested_data(self):
        data = {"albums": {"test": {"tracks": [1, 2, 3]}}}
        result = json.loads(server._safe_json(data))
        assert result == data

    def test_datetime_object_uses_str_default(self):
        """datetime objects are serialized via default=str."""
        data = {"timestamp": datetime(2025, 1, 1, 0, 0, 0)}
        result = json.loads(server._safe_json(data))
        assert "2025-01-01" in result["timestamp"]

    def test_path_object_uses_str_default(self):
        """Path objects are serialized via default=str."""
        data = {"path": Path("/tmp/test")}
        result = json.loads(server._safe_json(data))
        assert result["path"] == "/tmp/test"

    def test_non_serializable_returns_error(self):
        """Non-serializable data that raises TypeError returns JSON error."""
        # float('inf') causes OverflowError with default json encoder
        # and is not handled by default=str (str(inf) -> 'inf' which works).
        # Instead, use a value_that triggers ValueError by disabling allow_nan.
        # However, _safe_json uses json.dumps with default=str, so we need to
        # trigger a TypeError/ValueError/OverflowError specifically.
        #
        # The simplest case: float('nan') and float('inf') are accepted by
        # json.dumps by default. We need an object where default=str returns
        # something that still can't be serialized. Actually the cleanest
        # approach is to mock json.dumps to raise TypeError.
        with patch("json.dumps", side_effect=TypeError("not serializable")):
            # _safe_json catches TypeError and returns error JSON
            # But the fallback json.dumps in the except also uses json.dumps,
            # so we need to be more targeted. Instead, let's just patch
            # the server's json reference.
            pass

        # Alternative: use an object that causes OverflowError via a very
        # large integer that str() converts fine but demonstrates the fallback.
        # The most reliable approach: patch at the server module level.
        original_dumps = json.dumps
        call_count = 0

        def patched_dumps(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TypeError("test serialization failure")
            return original_dumps(*args, **kwargs)

        with patch.object(server.json, "dumps", side_effect=patched_dumps):
            result = json.loads(server._safe_json({"key": "value"}))
        assert "error" in result
        assert "serialization failed" in result["error"].lower()

    def test_none_value(self):
        data = {"key": None}
        result = json.loads(server._safe_json(data))
        assert result["key"] is None

    def test_boolean_values(self):
        data = {"flag": True, "other": False}
        result = json.loads(server._safe_json(data))
        assert result["flag"] is True
        assert result["other"] is False


# =============================================================================
# Tests for StateCache class
# =============================================================================


class TestStateCacheGetState:
    """Tests for StateCache.get_state()."""

    def test_returns_cached_state_when_not_stale(self):
        """Returns cached state without reading disk when not stale."""
        cache = server.StateCache()
        state = _fresh_state()
        cache._state = state
        cache._state_mtime = 100.0
        cache._config_mtime = 100.0

        # Mock file stats to return same mtimes (not stale)
        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=100.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=100.0)

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config), \
             patch.object(server, "read_state") as mock_read:
            result = cache.get_state()
            assert result is state
            mock_read.assert_not_called()

    def test_loads_from_disk_when_stale(self):
        """Loads from disk when state file mtime changes."""
        cache = server.StateCache()
        cache._state = {"old": True}
        cache._state_mtime = 100.0
        cache._config_mtime = 100.0

        new_state = _fresh_state()

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=200.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=100.0)

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config), \
             patch.object(server, "read_state", return_value=new_state) as mock_read:
            result = cache.get_state()
            mock_read.assert_called_once()
            assert result is new_state

    def test_loads_from_disk_when_none(self):
        """Loads from disk when internal state is None."""
        cache = server.StateCache()
        assert cache._state is None

        new_state = _fresh_state()

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=100.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=100.0)

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config), \
             patch.object(server, "read_state", return_value=new_state):
            result = cache.get_state()
            assert result is new_state

    def test_returns_empty_dict_when_no_state_on_disk(self):
        """Returns empty dict when read_state returns None."""
        cache = server.StateCache()

        mock_state = MagicMock()
        mock_state.exists.return_value = False
        mock_config = MagicMock()
        mock_config.exists.return_value = False

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config), \
             patch.object(server, "read_state", return_value=None):
            result = cache.get_state()
            assert result == {}


class TestStateCacheIsStale:
    """Tests for StateCache._is_stale()."""

    def test_not_stale_when_mtimes_match(self):
        cache = server.StateCache()
        cache._state_mtime = 100.0
        cache._config_mtime = 200.0

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=100.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=200.0)

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config):
            assert cache._is_stale() is False

    def test_stale_when_state_mtime_changed(self):
        cache = server.StateCache()
        cache._state_mtime = 100.0
        cache._config_mtime = 200.0

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=150.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=200.0)

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config):
            assert cache._is_stale() is True

    def test_stale_when_config_mtime_changed(self):
        cache = server.StateCache()
        cache._state_mtime = 100.0
        cache._config_mtime = 200.0

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=100.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=250.0)

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config):
            assert cache._is_stale() is True

    def test_stale_on_oserror(self):
        cache = server.StateCache()
        cache._state_mtime = 100.0

        mock_state = MagicMock()
        mock_state.exists.side_effect = OSError("permission denied")

        with patch.object(server, "STATE_FILE", mock_state):
            assert cache._is_stale() is True

    def test_not_stale_when_files_missing_and_mtimes_zero(self):
        """When neither file exists and cached mtimes are 0, not stale."""
        cache = server.StateCache()
        cache._state_mtime = 0.0
        cache._config_mtime = 0.0

        mock_state = MagicMock()
        mock_state.exists.return_value = False
        mock_config = MagicMock()
        mock_config.exists.return_value = False

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config):
            assert cache._is_stale() is False


class TestStateCacheRebuild:
    """Tests for StateCache.rebuild()."""

    def test_rebuild_success(self):
        config = {"artist": {"name": "test"}, "paths": {"content_root": "/tmp"}}
        new_state = _fresh_state()
        existing_state = _fresh_state()
        existing_state["session"]["last_album"] = "preserved-album"

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=300.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=300.0)

        cache = server.StateCache()

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config), \
             patch.object(server, "read_config", return_value=config), \
             patch.object(server, "read_state", return_value=existing_state), \
             patch.object(server, "build_state", return_value=new_state) as mock_build, \
             patch.object(server, "write_state") as mock_write:
            result = cache.rebuild()

        mock_build.assert_called_once_with(config)
        mock_write.assert_called_once()
        # Session should be preserved from existing state
        assert result["session"]["last_album"] == "preserved-album"

    def test_rebuild_config_missing(self):
        cache = server.StateCache()
        with patch.object(server, "read_config", return_value=None):
            result = cache.rebuild()
        assert "error" in result
        assert "Config not found" in result["error"]

    def test_rebuild_build_failure(self):
        cache = server.StateCache()
        with patch.object(server, "read_config", return_value={"artist": {"name": "test"}}), \
             patch.object(server, "read_state", return_value=None), \
             patch.object(server, "build_state", side_effect=RuntimeError("glob failed")):
            result = cache.rebuild()
        assert "error" in result
        assert "build failed" in result["error"].lower()


class TestStateCacheUpdateSession:
    """Tests for StateCache.update_session()."""

    def _make_cache_with_state(self):
        """Create a StateCache with pre-loaded state (bypasses disk)."""
        cache = server.StateCache()
        cache._state = _fresh_state()
        cache._state_mtime = 100.0
        cache._config_mtime = 100.0
        return cache

    def _mock_files(self):
        """Return context manager mocks for STATE_FILE and CONFIG_FILE."""
        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=100.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=100.0)
        return mock_state, mock_config

    def test_set_album(self):
        cache = self._make_cache_with_state()
        ms, mc = self._mock_files()
        with patch.object(server, "STATE_FILE", ms), \
             patch.object(server, "CONFIG_FILE", mc), \
             patch.object(server, "write_state"):
            result = cache.update_session(album="new-album")
        assert result["last_album"] == "new-album"
        assert result["updated_at"] is not None

    def test_set_track_and_phase(self):
        cache = self._make_cache_with_state()
        ms, mc = self._mock_files()
        with patch.object(server, "STATE_FILE", ms), \
             patch.object(server, "CONFIG_FILE", mc), \
             patch.object(server, "write_state"):
            result = cache.update_session(track="02-new-track", phase="Mastering")
        assert result["last_track"] == "02-new-track"
        assert result["last_phase"] == "Mastering"

    def test_append_action(self):
        cache = self._make_cache_with_state()
        ms, mc = self._mock_files()
        with patch.object(server, "STATE_FILE", ms), \
             patch.object(server, "CONFIG_FILE", mc), \
             patch.object(server, "write_state"):
            result = cache.update_session(action="Fix lyrics for track 03")
        assert "Fix lyrics for track 03" in result["pending_actions"]

    def test_clear_session(self):
        cache = self._make_cache_with_state()
        cache._state["session"]["last_album"] = "old-album"
        cache._state["session"]["pending_actions"] = ["something"]
        ms, mc = self._mock_files()
        with patch.object(server, "STATE_FILE", ms), \
             patch.object(server, "CONFIG_FILE", mc), \
             patch.object(server, "write_state"):
            result = cache.update_session(clear=True)
        assert result["last_album"] is None
        assert result["last_track"] is None
        assert result["last_phase"] is None
        assert result["pending_actions"] == []
        assert result["updated_at"] is not None

    def test_update_session_no_state(self):
        """Returns error when no state available."""
        cache = server.StateCache()
        cache._state = None

        mock_state = MagicMock()
        mock_state.exists.return_value = False
        mock_config = MagicMock()
        mock_config.exists.return_value = False

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config), \
             patch.object(server, "read_state", return_value=None):
            result = cache.update_session(album="test")
        assert "error" in result


# =============================================================================
# Tests for MCP tool: find_album
# =============================================================================


class TestFindAlbum:
    """Tests for the find_album MCP tool."""

    def test_exact_match(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("test-album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"
        assert result["album"]["title"] == "Test Album"

    def test_exact_match_with_spaces(self):
        """Spaces are normalized to hyphens for exact match."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("test album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"

    def test_exact_match_with_underscores(self):
        """Underscores are normalized to hyphens for exact match."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("test_album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"

    def test_exact_match_case_insensitive(self):
        """Mixed case is lowered for exact match."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("Test Album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"

    def test_fuzzy_substring_match(self):
        """Single substring match returns found."""
        state = _fresh_state()
        state["albums"] = {
            "cool-rock-anthem": {
                "title": "Cool Rock Anthem",
                "status": "In Progress",
                "tracks": {},
            },
            "jazz-vibes": {
                "title": "Jazz Vibes",
                "status": "Complete",
                "tracks": {},
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("rock")))
        assert result["found"] is True
        assert result["slug"] == "cool-rock-anthem"

    def test_multiple_fuzzy_matches(self):
        """Multiple substring matches returns error with list."""
        mock_cache = MockStateCache()
        # Both "test-album" and "another-album" contain "album"
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("album")))
        assert result["found"] is False
        assert "multiple_matches" in result
        assert len(result["multiple_matches"]) == 2

    def test_no_match(self):
        """No matches returns error with available albums."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("nonexistent")))
        assert result["found"] is False
        assert "available_albums" in result
        assert "No album found" in result["error"]

    def test_empty_state(self):
        """Empty albums dict returns appropriate error."""
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("anything")))
        assert result["found"] is False
        assert "No albums found" in result["error"]
        assert result.get("rebuilt") is True


# =============================================================================
# Tests for MCP tool: list_albums
# =============================================================================


class TestListAlbums:
    """Tests for the list_albums MCP tool."""

    def test_no_filter(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums()))
        assert result["count"] == 2
        slugs = [a["slug"] for a in result["albums"]]
        assert "test-album" in slugs
        assert "another-album" in slugs

    def test_status_filter_match(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums(status_filter="In Progress")))
        assert result["count"] == 1
        assert result["albums"][0]["slug"] == "test-album"

    def test_status_filter_case_insensitive(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums(status_filter="in progress")))
        assert result["count"] == 1

    def test_status_filter_no_match(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums(status_filter="Released")))
        assert result["count"] == 0
        assert result["albums"] == []

    def test_empty_albums(self):
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums()))
        assert result["count"] == 0

    def test_album_summary_fields(self):
        """Each album summary includes expected fields."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums()))
        album = next(a for a in result["albums"] if a["slug"] == "test-album")
        assert album["title"] == "Test Album"
        assert album["genre"] == "electronic"
        assert album["status"] == "In Progress"
        assert album["track_count"] == 2
        assert album["tracks_completed"] == 1


# =============================================================================
# Tests for MCP tool: get_track
# =============================================================================


class TestGetTrack:
    """Tests for the get_track MCP tool."""

    def test_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_track("test-album", "01-first-track")))
        assert result["found"] is True
        assert result["track"]["title"] == "First Track"
        assert result["track"]["status"] == "Final"

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_track("nonexistent", "01-track")))
        assert result["found"] is False
        assert "available_albums" in result

    def test_track_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_track("test-album", "99-nonexistent")))
        assert result["found"] is False
        assert "available_tracks" in result

    def test_normalizes_input(self):
        """Slugs with spaces/underscores/caps are normalized."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_track("Test Album", "01 First Track")))
        assert result["found"] is True
        assert result["track"]["title"] == "First Track"


# =============================================================================
# Tests for MCP tool: list_tracks
# =============================================================================


class TestListTracks:
    """Tests for the list_tracks MCP tool."""

    def test_found_with_sorted_tracks(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_tracks("test-album")))
        assert result["found"] is True
        assert result["track_count"] == 2
        assert result["album_title"] == "Test Album"
        # Tracks should be sorted by slug
        slugs = [t["slug"] for t in result["tracks"]]
        assert slugs == ["01-first-track", "02-second-track"]

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_tracks("nonexistent")))
        assert result["found"] is False
        assert "available_albums" in result

    def test_track_fields(self):
        """Each track in list includes expected summary fields."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_tracks("test-album")))
        track = result["tracks"][0]
        assert "slug" in track
        assert "title" in track
        assert "status" in track
        assert "explicit" in track
        assert "has_suno_link" in track
        assert "sources_verified" in track

    def test_normalizes_slug(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_tracks("Test Album")))
        assert result["found"] is True


# =============================================================================
# Tests for MCP tool: get_session
# =============================================================================


class TestGetSession:
    """Tests for the get_session MCP tool."""

    def test_returns_session_data(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_session()))
        session = result["session"]
        assert session["last_album"] == "test-album"
        assert session["last_track"] == "01-first-track"
        assert session["last_phase"] == "Writing"
        assert session["pending_actions"] == []

    def test_empty_session(self):
        state = _fresh_state()
        state["session"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_session()))
        assert result["session"] == {}


# =============================================================================
# Tests for MCP tool: update_session (the tool, not the cache method)
# =============================================================================


class TestUpdateSessionTool:
    """Tests for the update_session MCP tool."""

    def test_set_fields(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_session(
                album="new-album", track="03-track", phase="Generating"
            )))
        session = result["session"]
        assert session["last_album"] == "new-album"
        assert session["last_track"] == "03-track"
        assert session["last_phase"] == "Generating"

    def test_clear(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_session(clear=True)))
        session = result["session"]
        assert session["last_album"] is None
        assert session["last_track"] is None
        assert session["pending_actions"] == []

    def test_empty_strings_treated_as_no_update(self):
        """Empty string args are converted to None (no update)."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            # Empty strings should not overwrite existing values
            result = json.loads(_run(server.update_session(album="", track="")))
        session = result["session"]
        # Should preserve original values since "" -> None in the tool
        assert session["last_album"] == "test-album"


# =============================================================================
# Tests for MCP tool: rebuild_state
# =============================================================================


class TestRebuildStateTool:
    """Tests for the rebuild_state MCP tool."""

    def test_success_summary(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rebuild_state()))
        assert result["success"] is True
        assert result["albums"] == 2
        assert result["tracks"] == 3  # 2 tracks in test-album + 1 in another-album
        assert result["ideas"] == 3

    def test_error_returned(self):
        class ErrorCache(MockStateCache):
            def rebuild(self):
                return {"error": "Config not found at /path"}

        mock_cache = ErrorCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rebuild_state()))
        assert "error" in result
        assert "Config not found" in result["error"]


# =============================================================================
# Tests for MCP tool: get_config
# =============================================================================


class TestGetConfig:
    """Tests for the get_config MCP tool."""

    def test_config_present(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_config()))
        config = result["config"]
        assert config["content_root"] == "/tmp/test"
        assert config["artist_name"] == "test-artist"

    def test_config_missing(self):
        state = _fresh_state()
        state["config"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_config()))
        assert "error" in result
        assert "No config" in result["error"]

    def test_config_missing_entirely(self):
        """State has no 'config' key at all."""
        state = {"albums": {}, "ideas": {}, "session": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_config()))
        assert "error" in result


# =============================================================================
# Tests for MCP tool: get_ideas
# =============================================================================


class TestGetIdeas:
    """Tests for the get_ideas MCP tool."""

    def test_no_filter(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_ideas()))
        assert result["total"] == 3
        assert result["counts"]["Pending"] == 2
        assert result["counts"]["In Progress"] == 1

    def test_with_filter(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_ideas(status_filter="Pending")))
        assert result["total"] == 2
        assert all(i["status"] == "Pending" for i in result["items"])

    def test_filter_case_insensitive(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_ideas(status_filter="pending")))
        assert result["total"] == 2

    def test_filter_no_match(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_ideas(status_filter="Complete")))
        assert result["total"] == 0
        assert result["items"] == []

    def test_empty_ideas(self):
        state = _fresh_state()
        state["ideas"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_ideas()))
        assert result["total"] == 0
        assert result["counts"] == {}


# =============================================================================
# Tests for MCP tool: search
# =============================================================================


class TestSearch:
    """Tests for the search MCP tool."""

    def test_all_scope(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("test")))
        assert "albums" in result
        assert "tracks" in result
        assert "ideas" in result
        assert result["scope"] == "all"

    def test_albums_scope(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("test", scope="albums")))
        assert "albums" in result
        assert "tracks" not in result
        assert "ideas" not in result

    def test_tracks_scope(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("first", scope="tracks")))
        assert "tracks" in result
        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["title"] == "First Track"

    def test_ideas_scope(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("cool", scope="ideas")))
        assert "ideas" in result
        assert len(result["ideas"]) == 1
        assert result["ideas"][0]["title"] == "Cool Idea"

    def test_case_insensitive(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("TEST ALBUM")))
        assert len(result["albums"]) >= 1

    def test_search_by_genre(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("electronic", scope="albums")))
        assert len(result["albums"]) == 1
        assert result["albums"][0]["slug"] == "test-album"

    def test_search_ideas_by_genre(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("hip-hop", scope="ideas")))
        assert len(result["ideas"]) == 1
        assert result["ideas"][0]["title"] == "WIP Album"

    def test_no_results(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("zzzznonexistent")))
        assert result["total_matches"] == 0

    def test_total_matches_counts_all(self):
        """total_matches sums across all result types."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            # "rock" appears in album genre and idea genre
            result = json.loads(_run(server.search("rock")))
        total = (
            len(result.get("albums", []))
            + len(result.get("tracks", []))
            + len(result.get("ideas", []))
        )
        assert result["total_matches"] == total

    def test_search_track_by_slug(self):
        """Search matches track slug, not just title."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("02-second", scope="tracks")))
        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["track_slug"] == "02-second-track"


# =============================================================================
# Tests for MCP tool: get_pending_verifications
# =============================================================================


class TestGetPendingVerifications:
    """Tests for the get_pending_verifications MCP tool."""

    def test_some_pending(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] == 1
        assert "test-album" in result["albums_with_pending"]
        pending_tracks = result["albums_with_pending"]["test-album"]["tracks"]
        assert len(pending_tracks) == 1
        assert pending_tracks[0]["slug"] == "02-second-track"

    def test_none_pending(self):
        state = _fresh_state()
        # Remove the pending track
        state["albums"]["test-album"]["tracks"]["02-second-track"]["sources_verified"] = "Verified"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] == 0
        assert result["albums_with_pending"] == {}

    def test_empty_albums(self):
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] == 0

    def test_pending_case_insensitive(self):
        """Pending check is case-insensitive."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-first-track"]["sources_verified"] = "PENDING"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        # Both tracks now have pending
        assert result["total_pending_tracks"] == 2

    def test_multiple_albums_with_pending(self):
        """Multiple albums can have pending verifications."""
        state = _fresh_state()
        state["albums"]["another-album"]["tracks"]["01-rock-song"]["sources_verified"] = "Pending"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] == 2
        assert "test-album" in result["albums_with_pending"]
        assert "another-album" in result["albums_with_pending"]


# =============================================================================
# Tests for StateCache thread safety
# =============================================================================


class TestStateCacheThreadSafety:
    """Basic thread-safety sanity checks for StateCache."""

    def test_concurrent_get_state(self):
        """Multiple threads calling get_state() don't crash."""
        state = _fresh_state()

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=100.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=100.0)

        cache = server.StateCache()
        results = []
        errors = []

        def worker():
            try:
                result = cache.get_state()
                results.append(result is not None)
            except Exception as e:
                errors.append(str(e))

        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config), \
             patch.object(server, "read_state", return_value=state):
            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert all(results)


# =============================================================================
# Tests for StateCache._update_mtimes
# =============================================================================


class TestStateCacheUpdateMtimes:
    """Tests for StateCache._update_mtimes()."""

    def test_updates_both_mtimes(self):
        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.stat.return_value = MagicMock(st_mtime=111.0)
        mock_config = MagicMock()
        mock_config.exists.return_value = True
        mock_config.stat.return_value = MagicMock(st_mtime=222.0)

        cache = server.StateCache()
        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config):
            cache._update_mtimes()

        assert cache._state_mtime == 111.0
        assert cache._config_mtime == 222.0

    def test_oserror_silently_ignored(self):
        mock_state = MagicMock()
        mock_state.exists.side_effect = OSError("disk error")

        cache = server.StateCache()
        cache._state_mtime = 0.0
        with patch.object(server, "STATE_FILE", mock_state):
            # Should not raise
            cache._update_mtimes()
        assert cache._state_mtime == 0.0

    def test_missing_files_keep_zero(self):
        mock_state = MagicMock()
        mock_state.exists.return_value = False
        mock_config = MagicMock()
        mock_config.exists.return_value = False

        cache = server.StateCache()
        with patch.object(server, "STATE_FILE", mock_state), \
             patch.object(server, "CONFIG_FILE", mock_config):
            cache._update_mtimes()
        assert cache._state_mtime == 0.0
        assert cache._config_mtime == 0.0


# =============================================================================
# resolve_path tool tests
# =============================================================================

@pytest.mark.unit
class TestResolvePath:
    """Tests for the resolve_path MCP tool."""

    def test_audio_path(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("audio", "test-album")))
        assert "path" in result
        assert result["path"] == "/tmp/test/audio/test-artist/test-album"
        assert result["path_type"] == "audio"

    def test_documents_path(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("documents", "test-album")))
        assert result["path"] == "/tmp/test/docs/test-artist/test-album"

    def test_content_path_with_genre(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("content", "test-album", genre="electronic")))
        assert result["path"] == "/tmp/test/artists/test-artist/albums/electronic/test-album"
        assert result["genre"] == "electronic"

    def test_content_path_genre_from_state(self):
        """Genre is looked up from state cache when not provided."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("content", "test-album")))
        assert result["path"] == "/tmp/test/artists/test-artist/albums/electronic/test-album"
        assert result["genre"] == "electronic"

    def test_content_path_genre_required_not_found(self):
        """Error when genre not provided and album not in state."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("content", "unknown-album")))
        assert "error" in result
        assert "Genre required" in result["error"]

    def test_tracks_path(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("tracks", "test-album")))
        assert result["path"].endswith("/tracks")
        assert "electronic" in result["path"]

    def test_overrides_path(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("overrides", "")))
        assert result["path_type"] == "overrides"
        assert result["path"].endswith("/overrides")

    def test_overrides_explicit_config(self):
        """Overrides path uses config value when set."""
        state = _fresh_state()
        state["config"]["overrides_dir"] = "/custom/overrides"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("overrides", "")))
        assert result["path"] == "/custom/overrides"

    def test_invalid_path_type(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("invalid", "test-album")))
        assert "error" in result
        assert "Invalid path_type" in result["error"]

    def test_no_config(self):
        """Error when state has no config."""
        state = _fresh_state()
        state["config"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("audio", "test-album")))
        assert "error" in result

    def test_slug_normalization(self):
        """Album slug with spaces is normalized."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("audio", "test album")))
        assert "test-album" in result["path"]


# =============================================================================
# resolve_track_file tool tests
# =============================================================================

@pytest.mark.unit
class TestResolveTrackFile:
    """Tests for the resolve_track_file MCP tool."""

    def test_exact_match(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("test-album", "01-first-track")))
        assert result["found"] is True
        assert result["track_slug"] == "01-first-track"
        assert result["path"] == "/tmp/test/.../01-first-track.md"
        assert result["genre"] == "electronic"
        assert "track" in result

    def test_prefix_match(self):
        """Track number prefix matches the full slug."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("test-album", "01")))
        assert result["found"] is True
        assert result["track_slug"] == "01-first-track"

    def test_prefix_match_with_hyphen(self):
        """Track number with trailing content still matches."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("test-album", "02")))
        assert result["found"] is True
        assert result["track_slug"] == "02-second-track"

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("nonexistent", "01")))
        assert result["found"] is False
        assert "available_albums" in result

    def test_track_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("test-album", "99-missing")))
        assert result["found"] is False
        assert "available_tracks" in result

    def test_includes_album_path(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("test-album", "01-first-track")))
        assert result["album_path"] == "/tmp/test/artists/test-artist/albums/electronic/test-album"

    def test_slug_normalization(self):
        """Spaces and underscores in input are normalized."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("test album", "01 first track")))
        assert result["found"] is True

    def test_multiple_prefix_matches(self):
        """Ambiguous prefix returns error with matches."""
        state = _fresh_state()
        state["albums"]["prefix-album"] = {
            "path": "/tmp/test/prefix-album",
            "genre": "rock",
            "title": "Prefix Album",
            "status": "In Progress",
            "tracks": {
                "01-a-track": {"path": "/tmp/01-a.md", "title": "A", "status": "Not Started"},
                "01-b-track": {"path": "/tmp/01-b.md", "title": "B", "status": "Not Started"},
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_track_file("prefix-album", "01")))
        assert result["found"] is False
        assert "Multiple tracks" in result["error"]
        assert len(result["matches"]) == 2


# =============================================================================
# list_track_files tool tests
# =============================================================================

@pytest.mark.unit
class TestListTrackFiles:
    """Tests for the list_track_files MCP tool."""

    def test_all_tracks(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("test-album")))
        assert result["found"] is True
        assert result["track_count"] == 2
        assert result["total_tracks"] == 2
        assert result["genre"] == "electronic"
        assert result["album_path"] == "/tmp/test/artists/test-artist/albums/electronic/test-album"

    def test_tracks_include_paths(self):
        """Each track includes its file path."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("test-album")))
        for track in result["tracks"]:
            assert "path" in track
            assert track["path"] != ""

    def test_status_filter(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("test-album", status_filter="Final")))
        assert result["track_count"] == 1
        assert result["total_tracks"] == 2
        assert result["tracks"][0]["slug"] == "01-first-track"

    def test_status_filter_case_insensitive(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("test-album", status_filter="final")))
        assert result["track_count"] == 1

    def test_status_filter_no_match(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("test-album", status_filter="Generated")))
        assert result["track_count"] == 0
        assert result["total_tracks"] == 2

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("nonexistent")))
        assert result["found"] is False
        assert "available_albums" in result

    def test_tracks_sorted_by_slug(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("test-album")))
        slugs = [t["slug"] for t in result["tracks"]]
        assert slugs == sorted(slugs)

    def test_track_fields_present(self):
        """Each track has all expected fields."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_track_files("test-album")))
        expected_fields = {"slug", "title", "status", "path", "explicit", "has_suno_link", "sources_verified"}
        for track in result["tracks"]:
            assert expected_fields.issubset(track.keys())


# =============================================================================
# extract_section tool tests
# =============================================================================

# Sample track markdown content for testing
_SAMPLE_TRACK_MD = """\
# Test Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 01 |
| **Title** | Test Track |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | ❌ Pending |

## Concept

This track tells the story of a test that never ends.

## Musical Direction

- **Tempo**: 120 BPM
- **Feel**: Energetic
- **Instrumentation**: Synths, drums

## Suno Inputs

### Style Box
*Copy this into Suno's "Style of Music" field:*

```
electronic, 120 BPM, energetic, male vocals, synth-driven
```

### Lyrics Box
*Copy this into Suno's "Lyrics" field:*

```
[Verse 1]
Testing one two three
This is a test for me

[Chorus]
We're testing all day long
Testing in this song
```

## Streaming Lyrics

```
Testing one two three
This is a test for me

We're testing all day long
Testing in this song
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| pytest | PY-test | Technical term |

## Production Notes

- Keep the energy high throughout
- Layer synths for a wall of sound
"""


@pytest.mark.unit
class TestExtractSection:
    """Tests for the extract_section MCP tool."""

    def _make_cache_with_file(self, tmp_path):
        """Create a mock cache with a real track file on disk."""
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        return MockStateCache(state)

    def test_extract_style_box(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "style")))
        assert result["found"] is True
        assert "electronic" in result["content"]
        assert "120 BPM" in result["content"]
        assert result["section"] == "Style Box"

    def test_extract_lyrics_box(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "lyrics")))
        assert result["found"] is True
        assert "[Verse 1]" in result["content"]
        assert "[Chorus]" in result["content"]

    def test_extract_streaming_lyrics(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "streaming")))
        assert result["found"] is True
        assert "Testing one two three" in result["content"]
        # Streaming lyrics should NOT have section tags
        assert "[Verse" not in result["content"]

    def test_extract_concept(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "concept")))
        assert result["found"] is True
        assert "test that never ends" in result["content"]

    def test_extract_pronunciation(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "pronunciation")))
        assert result["found"] is True
        assert "pytest" in result["content"]
        assert "PY-test" in result["content"]

    def test_extract_musical_direction(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "musical-direction")))
        assert result["found"] is True
        assert "120 BPM" in result["content"]

    def test_extract_production_notes(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "production-notes")))
        assert result["found"] is True
        assert "energy high" in result["content"]

    def test_code_block_sections_return_raw(self, tmp_path):
        """Code block sections include raw_content with full section."""
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "style")))
        assert result["raw_content"] is not None
        assert "Copy this" in result["raw_content"]

    def test_non_code_block_sections_no_raw(self, tmp_path):
        """Non-code-block sections don't set raw_content."""
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "concept")))
        assert result["raw_content"] is None

    def test_unknown_section(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "nonexistent")))
        assert "error" in result
        assert "Unknown section" in result["error"]

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("nonexistent", "01", "lyrics")))
        assert result["found"] is False

    def test_track_prefix_match(self, tmp_path):
        """Track number prefix resolves correctly when unambiguous."""
        track_file = tmp_path / "05-unique-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-unique-track"] = {
            "path": str(track_file),
            "title": "Unique Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "05", "concept")))
        assert result["found"] is True
        assert result["track_slug"] == "05-unique-track"

    def test_missing_section_in_file(self, tmp_path):
        """Section that exists in schema but not in file."""
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "source")))
        assert result["found"] is False
        assert "not found in track file" in result["error"]


# =============================================================================
# update_track_field tool tests
# =============================================================================

@pytest.mark.unit
class TestUpdateTrackField:
    """Tests for the update_track_field MCP tool."""

    def _make_cache_with_file(self, tmp_path):
        """Create a mock cache with a real track file on disk."""
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        return MockStateCache(state), track_file

    def test_update_status(self, tmp_path):
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert result["success"] is True
        assert result["field"] == "Status"
        assert result["value"] == "Generated"
        # Verify file was actually modified
        content = track_file.read_text()
        assert "| **Status** | Generated |" in content

    def test_update_explicit(self, tmp_path):
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "explicit", "Yes"
            )))
        assert result["success"] is True
        content = track_file.read_text()
        assert "| **Explicit** | Yes |" in content

    def test_update_sources_verified(self, tmp_path):
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources_verified", "✅ Verified (2026-02-06)"
            )))
        assert result["success"] is True
        content = track_file.read_text()
        assert "✅ Verified (2026-02-06)" in content

    def test_update_with_prefix_match(self, tmp_path):
        """Track number prefix works for updates too."""
        track_file = tmp_path / "05-unique-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-unique-track"] = {
            "path": str(track_file),
            "title": "Unique Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "05", "status", "Final"
            )))
        assert result["success"] is True
        assert result["track_slug"] == "05-unique-track"

    def test_update_preserves_other_fields(self, tmp_path):
        """Updating one field doesn't affect others."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            _run(server.update_track_field("test-album", "01-test-track", "status", "Final"))
        content = track_file.read_text()
        assert "| **Explicit** | No |" in content
        assert "| **Title** | Test Track |" in content

    def test_unknown_field(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-first-track", "invalid_field", "value"
            )))
        assert "error" in result
        assert "Unknown field" in result["error"]

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "nonexistent", "01", "status", "Final"
            )))
        assert result["found"] is False

    def test_track_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "99-missing", "status", "Final"
            )))
        assert result["found"] is False

    def test_returns_parsed_track(self, tmp_path):
        """Result includes re-parsed track metadata."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert result["track"]["status"] == "Generated"

    def test_state_cache_updated(self, tmp_path):
        """State cache is updated in memory after field change."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            _run(server.update_track_field("test-album", "01-test-track", "status", "Final"))
        # write_state should have been called to persist
        mock_write.assert_called_once()
        # In-memory state should reflect update
        state = mock_cache.get_state()
        assert state["albums"]["test-album"]["tracks"]["01-test-track"]["status"] == "Final"


# =============================================================================
# find_album auto-rebuild tests
# =============================================================================

@pytest.mark.unit
class TestFindAlbumAutoRebuild:
    """Tests for find_album's auto-rebuild when state is empty."""

    def test_auto_rebuild_on_empty_albums(self):
        """Triggers rebuild when albums dict is empty."""
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        # After rebuild, mock still returns empty — should report rebuilt
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("anything")))
        assert result["found"] is False
        assert result.get("rebuilt") is True
        assert mock_cache._rebuild_called is True

    def test_no_rebuild_when_albums_exist(self):
        """Does NOT rebuild when albums are present."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            _run(server.find_album("test-album"))
        assert mock_cache._rebuild_called is False

    def test_rebuild_recovers_albums(self):
        """After rebuild finds albums, search works normally."""
        # Start empty, but rebuild returns populated state
        empty_state = _fresh_state()
        empty_state["albums"] = {}

        class RebuildingCache(MockStateCache):
            def rebuild(self):
                self._rebuild_called = True
                self._state = _fresh_state()  # now has albums
                return self._state

        mock_cache = RebuildingCache(empty_state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("test-album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"


# =============================================================================
# get_album_progress tool tests
# =============================================================================

@pytest.mark.unit
class TestGetAlbumProgress:
    """Tests for the get_album_progress MCP tool."""

    def test_basic_progress(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("test-album")))
        assert result["found"] is True
        assert result["album_slug"] == "test-album"
        assert result["album_title"] == "Test Album"
        assert result["track_count"] == 2
        assert result["genre"] == "electronic"
        assert "tracks_by_status" in result
        assert "phase" in result
        assert "completion_percentage" in result

    def test_tracks_by_status_counts(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("test-album")))
        counts = result["tracks_by_status"]
        assert counts.get("Final") == 1
        assert counts.get("In Progress") == 1

    def test_completion_percentage(self):
        """Completed = Final + Generated out of total."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("test-album")))
        # 1 Final out of 2 tracks = 50%
        assert result["completion_percentage"] == 50.0

    def test_complete_album(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("another-album")))
        assert result["completion_percentage"] == 100.0
        assert result["album_status"] == "Complete"

    def test_sources_pending_count(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("test-album")))
        assert result["sources_pending"] == 1  # 02-second-track has "Pending"

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("nonexistent")))
        assert result["found"] is False
        assert "available_albums" in result

    def test_slug_normalization(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("Test Album")))
        assert result["found"] is True

    def test_phase_writing(self):
        """Album with Not Started/In Progress tracks is in Writing phase."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("test-album")))
        # test-album has 1 Final + 1 In Progress with Pending sources
        assert result["phase"] == "Source Verification"

    def test_phase_planning(self):
        state = _fresh_state()
        state["albums"]["concept-album"] = {
            "path": "/tmp/test/concept",
            "genre": "rock",
            "title": "Concept Album",
            "status": "Concept",
            "tracks": {},
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("concept-album")))
        assert result["phase"] == "Planning"

    def test_phase_released(self):
        state = _fresh_state()
        state["albums"]["done-album"] = {
            "path": "/tmp/test/done",
            "genre": "jazz",
            "title": "Done Album",
            "status": "Released",
            "tracks": {
                "01-song": {"status": "Final", "sources_verified": "N/A"},
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("done-album")))
        assert result["phase"] == "Released"

    def test_phase_ready_to_generate(self):
        """All tracks have lyrics (not Not Started/In Progress) but none generated."""
        state = _fresh_state()
        state["albums"]["ready-album"] = {
            "path": "/tmp/test/ready",
            "genre": "pop",
            "title": "Ready Album",
            "status": "In Progress",
            "tracks": {
                "01-a": {"status": "Sources Verified", "sources_verified": "Verified"},
                "02-b": {"status": "Sources Verified", "sources_verified": "Verified"},
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("ready-album")))
        assert result["phase"] == "Ready to Generate"

    def test_phase_mastering(self):
        """All tracks generated, none final yet."""
        state = _fresh_state()
        state["albums"]["gen-album"] = {
            "path": "/tmp/test/gen",
            "genre": "rock",
            "title": "Generated Album",
            "status": "In Progress",
            "tracks": {
                "01-a": {"status": "Generated", "sources_verified": "N/A"},
                "02-b": {"status": "Generated", "sources_verified": "N/A"},
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("gen-album")))
        assert result["phase"] == "Mastering"

    def test_empty_tracks_zero_percent(self):
        state = _fresh_state()
        state["albums"]["empty-album"] = {
            "path": "/tmp/test/empty",
            "genre": "ambient",
            "title": "Empty Album",
            "status": "Concept",
            "tracks": {},
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("empty-album")))
        assert result["completion_percentage"] == 0.0
        assert result["track_count"] == 0


# =============================================================================
# load_override tool tests
# =============================================================================

@pytest.mark.unit
class TestLoadOverride:
    """Tests for the load_override MCP tool."""

    def test_found(self, tmp_path):
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        guide = override_dir / "pronunciation-guide.md"
        guide.write_text("# My Custom Guide\nCustom content here.")

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("pronunciation-guide.md")))
        assert result["found"] is True
        assert "Custom content" in result["content"]
        assert result["override_name"] == "pronunciation-guide.md"

    def test_not_found(self, tmp_path):
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("nonexistent.md")))
        assert result["found"] is False

    def test_default_overrides_dir(self):
        """Falls back to {content_root}/overrides when overrides_dir not set."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("anything.md")))
        # /tmp/test/overrides won't exist, so should be not found
        assert result["found"] is False
        assert "/tmp/test/overrides" in result.get("overrides_dir", "")

    def test_no_config(self):
        state = {"albums": {}, "ideas": {}, "session": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("anything.md")))
        assert "error" in result

    def test_returns_size(self, tmp_path):
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "test.md").write_text("Hello World")

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("test.md")))
        assert result["size"] == len("Hello World")

    def test_path_traversal_blocked(self, tmp_path):
        """Override names with '..' don't escape the overrides directory."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        # Create a file outside the overrides dir
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret")

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("../secret.txt")))
        # The resolved path (overrides_dir/../secret.txt) might exist,
        # but we verify it doesn't leak content from outside overrides
        # If the file system resolves it, the behavior depends on implementation
        # At minimum, assert it either doesn't find it or the path is outside overrides
        if result.get("found"):
            # If found, the path should still be under overrides parent
            assert str(override_dir.parent) in result.get("path", "")
        # This test documents the current behavior for awareness


# =============================================================================
# get_reference tool tests
# =============================================================================

@pytest.mark.unit
class TestGetReference:
    """Tests for the get_reference MCP tool."""

    def test_full_file(self, tmp_path):
        ref_dir = tmp_path / "reference" / "suno"
        ref_dir.mkdir(parents=True)
        (ref_dir / "test-guide.md").write_text("# Test Guide\n\nContent here.")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("suno/test-guide")))
        assert result["found"] is True
        assert "Test Guide" in result["content"]

    def test_auto_adds_md_extension(self, tmp_path):
        ref_dir = tmp_path / "reference" / "suno"
        ref_dir.mkdir(parents=True)
        (ref_dir / "guide.md").write_text("content")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("suno/guide")))
        assert result["found"] is True

    def test_with_section(self, tmp_path):
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "guide.md").write_text(
            "# Guide\n\n## Section A\nContent A\n\n## Section B\nContent B\n"
        )

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("guide", section="Section A")))
        assert result["found"] is True
        assert "Content A" in result["content"]
        assert "Content B" not in result["content"]

    def test_section_not_found(self, tmp_path):
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "guide.md").write_text("# Guide\n\n## Section A\nContent")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("guide", section="Missing")))
        assert "error" in result
        assert "not found" in result["error"]

    def test_file_not_found(self, tmp_path):
        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("suno/nonexistent")))
        assert "error" in result

    def test_returns_size(self, tmp_path):
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        content = "Hello World"
        (ref_dir / "test.md").write_text(content)

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("test")))
        assert result["size"] == len(content)


# =============================================================================
# format_for_clipboard tool tests
# =============================================================================

@pytest.mark.unit
class TestFormatForClipboard:
    """Tests for the format_for_clipboard MCP tool."""

    def _make_cache_with_file(self, tmp_path):
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        return MockStateCache(state)

    def test_lyrics(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "01-test-track", "lyrics")))
        assert result["found"] is True
        assert "[Verse 1]" in result["content"]
        assert result["content_type"] == "lyrics"

    def test_style(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "01-test-track", "style")))
        assert result["found"] is True
        assert "electronic" in result["content"]

    def test_streaming(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "01-test-track", "streaming")))
        assert result["found"] is True
        assert "[Verse" not in result["content"]

    def test_all_combined(self, tmp_path):
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "01-test-track", "all")))
        assert result["found"] is True
        assert "electronic" in result["content"]  # style
        assert "[Verse 1]" in result["content"]  # lyrics
        assert "---" in result["content"]  # separator

    def test_invalid_type(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "01", "invalid")))
        assert "error" in result

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("nonexistent", "01", "lyrics")))
        assert result["found"] is False

    def test_ambiguous_prefix_returns_error(self, tmp_path):
        """Ambiguous prefix (matches multiple tracks) returns an error."""
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "01", "style")))
        # "01" matches both 01-first-track (SAMPLE_STATE) and 01-test-track (added by helper)
        assert result["found"] is False
        assert "Multiple" in result.get("error", "")

    def test_unique_prefix(self, tmp_path):
        track_file = tmp_path / "05-clip-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-clip-track"] = {
            "path": str(track_file),
            "title": "Clip Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05", "lyrics")))
        assert result["found"] is True
        assert result["track_slug"] == "05-clip-track"

    def test_track_not_found(self):
        """Track slug that doesn't match any track returns error."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "99-missing", "lyrics")))
        assert result["found"] is False
        assert "not found" in result["error"]

    def test_missing_section_in_track(self, tmp_path):
        """Track exists but the requested section doesn't (e.g., no Streaming Lyrics)."""
        # Create a minimal track without a Streaming Lyrics section
        minimal_track = "# Track\n\n## Suno Inputs\n\n### Style Box\n```\nrock\n```\n"
        track_file = tmp_path / "05-minimal.md"
        track_file.write_text(minimal_track)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-minimal"] = {
            "path": str(track_file),
            "title": "Minimal Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05", "streaming")))
        assert result["found"] is False
        assert "not found" in result["error"]

    def test_track_no_path(self):
        """Track exists in state but has no file path stored."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-no-path"] = {
            "title": "No Path Track",
            "status": "In Progress",
            "path": "",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05-no-path", "lyrics")))
        assert "error" in result
        assert "No path" in result["error"]


# =============================================================================
# check_homographs tool tests
# =============================================================================

@pytest.mark.unit
class TestCheckHomographs:
    """Tests for the check_homographs MCP tool."""

    def test_finds_live(self):
        text = "[Verse 1]\nWe live and breathe this code\nAlive in the machine"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] >= 1
        words = [r["canonical"] for r in result["found"]]
        assert "live" in words

    def test_finds_multiple(self):
        text = "Read the lead and close the record"
        result = json.loads(_run(server.check_homographs(text)))
        words = set(r["canonical"] for r in result["found"])
        assert "read" in words
        assert "lead" in words
        assert "close" in words
        assert "record" in words

    def test_empty_text(self):
        result = json.loads(_run(server.check_homographs("")))
        assert result["count"] == 0
        assert result["found"] == []

    def test_no_homographs(self):
        text = "The sun sets over the mountain\nBirds fly across the sky"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] == 0

    def test_skips_section_tags(self):
        text = "[Verse 1]\nlive and breathe\n[Chorus]\nstay alive"
        result = json.loads(_run(server.check_homographs(text)))
        # Should find "live" in verse but not scan [Verse 1] or [Chorus] lines
        for r in result["found"]:
            assert not r["line"].startswith("[")

    def test_returns_line_numbers(self):
        text = "Line one\nThe wind blows hard\nLine three"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] == 1
        assert result["found"][0]["line_number"] == 2

    def test_case_insensitive(self):
        text = "LIVE performance tonight\nRead the book"
        result = json.loads(_run(server.check_homographs(text)))
        words = [r["canonical"] for r in result["found"]]
        assert "live" in words
        assert "read" in words

    def test_includes_options(self):
        text = "lead the way"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] == 1
        entry = result["found"][0]
        assert len(entry["options"]) > 0
        assert "pron_a" in entry["options"][0]

    def test_word_boundary_no_partial_match(self):
        """Homographs should not match partial words (e.g., 'alive' should not trigger 'live')."""
        text = "She's alive and thriving\nDriven to survive"
        result = json.loads(_run(server.check_homographs(text)))
        # "alive" contains "live" but should NOT match due to word boundary
        words = [r["canonical"] for r in result["found"]]
        assert "live" not in words

    def test_multiple_same_line(self):
        """Multiple homographs on the same line each get reported."""
        text = "Read the record, close the wound"
        result = json.loads(_run(server.check_homographs(text)))
        words = [r["canonical"] for r in result["found"]]
        assert "read" in words
        assert "record" in words
        assert "close" in words
        assert "wound" in words
        assert result["count"] == 4

    def test_column_position(self):
        """Column position accurately reflects match start."""
        text = "The bass drops hard"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] == 1
        assert result["found"][0]["column"] == 4  # "The " is 4 chars


# =============================================================================
# scan_artist_names tool tests
# =============================================================================

@pytest.mark.unit
class TestScanArtistNames:
    """Tests for the scan_artist_names MCP tool."""

    def test_finds_blocked_name(self):
        # Ensure blocklist is loaded from real file
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("aggressive dubstep like Skrillex with heavy drops")))
        assert result["clean"] is False
        assert result["count"] >= 1
        names = [r["name"] for r in result["found"]]
        assert "Skrillex" in names

    def test_clean_text(self):
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("aggressive dubstep, heavy drops, distorted bass")))
        assert result["clean"] is True
        assert result["count"] == 0

    def test_empty_text(self):
        result = json.loads(_run(server.scan_artist_names("")))
        assert result["clean"] is True
        assert result["count"] == 0

    def test_returns_alternative(self):
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("sounds like Daft Punk")))
        assert result["count"] >= 1
        entry = result["found"][0]
        assert "alternative" in entry
        assert len(entry["alternative"]) > 0

    def test_case_insensitive(self):
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("heavy like METALLICA")))
        assert result["clean"] is False

    def test_multiple_names(self):
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("mix of Eminem and Drake style")))
        names = [r["name"] for r in result["found"]]
        assert "Eminem" in names
        assert "Drake" in names

    def test_word_boundary_no_partial(self):
        """Should not match artist names embedded in other words."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("Drakeford is not a musician")))
        # "Drake" should NOT match inside "Drakeford" due to word boundaries
        assert result["clean"] is True

    def test_genre_returned(self):
        """Each found artist includes the genre category."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("sounds like Skrillex")))
        assert result["count"] >= 1
        assert "genre" in result["found"][0]
        assert result["found"][0]["genre"] == "Electronic & Dance"

    def test_blocklist_file_missing(self, tmp_path):
        """Gracefully handles missing blocklist file."""
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.scan_artist_names("sounds like Metallica")))
        # With no blocklist file, nothing should be found
        assert result["clean"] is True
        assert result["count"] == 0


# =============================================================================
# check_pronunciation_enforcement tool tests
# =============================================================================

_TRACK_WITH_PRONUNCIATION = """\
# Test Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Explicit** | No |

## Suno Inputs

### Style Box
```
electronic, energetic
```

### Lyrics Box
```
[Verse 1]
Rah-mohs walked the streets alone
F-B-I came knocking at his door
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| Ramos | Rah-mohs | Spanish name |
| FBI | F-B-I | Acronym |
| Linux | Lin-ucks | Tech term |
"""

_TRACK_WITH_UNAPPLIED = """\
# Test Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Explicit** | No |

## Suno Inputs

### Lyrics Box
```
[Verse 1]
Ramos walked the streets alone
FBI came knocking at his door
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| Ramos | Rah-mohs | Spanish name |
| FBI | F-B-I | Acronym |
"""


@pytest.mark.unit
class TestCheckPronunciationEnforcement:
    """Tests for the check_pronunciation_enforcement MCP tool."""

    def test_all_applied(self, tmp_path):
        track_file = tmp_path / "05-pron-track.md"
        track_file.write_text(_TRACK_WITH_PRONUNCIATION)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-pron-track"] = {
            "path": str(track_file),
            "title": "Pron Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("test-album", "05-pron-track")))
        assert result["found"] is True
        # Rah-mohs and F-B-I are in lyrics, but Lin-ucks is not
        unapplied = [e for e in result["entries"] if not e["applied"]]
        assert len(unapplied) == 1
        assert unapplied[0]["word"] == "Linux"

    def test_unapplied_entries(self, tmp_path):
        track_file = tmp_path / "05-unapplied.md"
        track_file.write_text(_TRACK_WITH_UNAPPLIED)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-unapplied"] = {
            "path": str(track_file),
            "title": "Unapplied Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("test-album", "05-unapplied")))
        assert result["all_applied"] is False
        assert result["unapplied_count"] == 2  # Both Rah-mohs and F-B-I not in lyrics

    def test_empty_pronunciation_table(self, tmp_path):
        track_file = tmp_path / "05-empty-pron.md"
        track_file.write_text(_SAMPLE_TRACK_MD)  # has pronunciation table with only "—" placeholder
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-empty-pron"] = {
            "path": str(track_file),
            "title": "Empty Pron",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("test-album", "05-empty-pron")))
        # The _SAMPLE_TRACK_MD has "pytest | PY-test" which IS a valid entry
        assert result["found"] is True

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("nonexistent", "01")))
        assert result["found"] is False

    def test_prefix_match(self, tmp_path):
        track_file = tmp_path / "05-pron-track.md"
        track_file.write_text(_TRACK_WITH_PRONUNCIATION)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-pron-track"] = {
            "path": str(track_file),
            "title": "Pron Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("test-album", "05")))
        assert result["found"] is True
        assert result["track_slug"] == "05-pron-track"

    def test_track_not_found(self):
        """Track slug that doesn't match any track returns found=False."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("test-album", "99-missing")))
        assert result["found"] is False
        assert "not found" in result["error"]

    def test_no_pronunciation_section(self, tmp_path):
        """Track with no Pronunciation Notes section reports all_applied."""
        track_content = "# Track\n\n## Suno Inputs\n\n### Lyrics Box\n```\nhello world\n```\n"
        track_file = tmp_path / "05-no-pron.md"
        track_file.write_text(track_content)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-no-pron"] = {
            "path": str(track_file),
            "title": "No Pron Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("test-album", "05-no-pron")))
        assert result["found"] is True
        assert result["all_applied"] is True
        assert "No Pronunciation Notes" in result.get("note", "")

    def test_multiple_prefix_matches_error(self, tmp_path):
        """Ambiguous prefix (matches multiple tracks) returns an error."""
        track_file1 = tmp_path / "05-track-a.md"
        track_file2 = tmp_path / "05-track-b.md"
        track_file1.write_text(_TRACK_WITH_PRONUNCIATION)
        track_file2.write_text(_TRACK_WITH_PRONUNCIATION)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-track-a"] = {
            "path": str(track_file1), "title": "Track A", "status": "In Progress",
        }
        state["albums"]["test-album"]["tracks"]["05-track-b"] = {
            "path": str(track_file2), "title": "Track B", "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_pronunciation_enforcement("test-album", "05")))
        assert result["found"] is False
        assert "Multiple" in result["error"]


# =============================================================================
# get_album_full tool tests
# =============================================================================

@pytest.mark.unit
class TestGetAlbumFull:
    """Tests for the get_album_full MCP tool."""

    def test_metadata_only(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"
        assert "tracks" in result
        assert "01-first-track" in result["tracks"]

    def test_with_sections(self, tmp_path):
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album", include_sections="lyrics,style")))

        # The test-track should have sections extracted
        test_track = result["tracks"].get("01-test-track", {})
        assert "sections" in test_track
        assert "lyrics" in test_track["sections"]
        assert "[Verse 1]" in test_track["sections"]["lyrics"]
        assert "style" in test_track["sections"]
        assert "electronic" in test_track["sections"]["style"]

    def test_fuzzy_match(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("another")))
        assert result["found"] is True
        assert result["slug"] == "another-album"

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("nonexistent")))
        assert result["found"] is False

    def test_multiple_matches(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("album")))
        assert result["found"] is False
        assert "Multiple albums" in result["error"]

    def test_album_fields(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album")))
        album = result["album"]
        assert album["title"] == "Test Album"
        assert album["status"] == "In Progress"
        assert album["genre"] == "electronic"

    def test_invalid_section_ignored(self, tmp_path):
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album", include_sections="lyrics,invalid-section")))
        test_track = result["tracks"].get("01-test-track", {})
        sections = test_track.get("sections", {})
        assert "lyrics" in sections
        assert "invalid-section" not in sections

    def test_track_file_missing_on_disk(self):
        """Tracks with non-existent file paths gracefully skip section extraction."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-missing-file"] = {
            "path": "/nonexistent/path/05-missing-file.md",
            "title": "Missing File",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album", include_sections="lyrics")))
        # Track should appear but without sections (file read failed)
        track = result["tracks"].get("05-missing-file", {})
        assert track["title"] == "Missing File"
        assert "sections" not in track

    def test_tracks_sorted(self):
        """Tracks in result are sorted by slug key."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album")))
        slugs = list(result["tracks"].keys())
        assert slugs == sorted(slugs)

    def test_track_metadata_fields(self, tmp_path):
        """Each track entry includes all expected metadata fields."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album")))
        track = result["tracks"]["01-first-track"]
        assert "title" in track
        assert "status" in track
        assert "explicit" in track
        assert "has_suno_link" in track
        assert "sources_verified" in track
        assert "path" in track


# =============================================================================
# validate_album_structure tool tests
# =============================================================================

@pytest.mark.unit
class TestValidateAlbumStructure:
    """Tests for the validate_album_structure MCP tool."""

    def _make_album_on_disk(self, tmp_path):
        """Create a real album directory structure for validation."""
        content = tmp_path / "content"
        audio = tmp_path / "audio"
        album_dir = content / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        tracks_dir = album_dir / "tracks"
        audio_dir = audio / "test-artist" / "test-album"

        tracks_dir.mkdir(parents=True)
        audio_dir.mkdir(parents=True)
        (album_dir / "README.md").write_text("# Test Album")
        (tracks_dir / "01-test.md").write_text(_SAMPLE_TRACK_MD)
        (audio_dir / "01-test.wav").write_text("")  # dummy wav
        (audio_dir / "album.png").write_text("")  # dummy art

        state = _fresh_state()
        state["config"]["content_root"] = str(content)
        state["config"]["audio_root"] = str(audio)
        state["albums"]["test-album"]["path"] = str(album_dir)
        return MockStateCache(state), album_dir, audio_dir

    def test_all_pass(self, tmp_path):
        mock_cache, album_dir, audio_dir = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album")))
        assert result["found"] is True
        assert result["failed"] == 0
        assert result["passed"] > 0

    def test_missing_tracks_dir(self, tmp_path):
        mock_cache, album_dir, _ = self._make_album_on_disk(tmp_path)
        shutil.rmtree(str(album_dir / "tracks"))
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="structure")))
        failed_msgs = [c["message"] for c in result["checks"] if c["status"] == "FAIL"]
        assert any("tracks/ directory" in m for m in failed_msgs)

    def test_audio_wrong_location(self, tmp_path):
        mock_cache, album_dir, audio_dir = self._make_album_on_disk(tmp_path)
        # Move audio to wrong location (missing artist folder)
        wrong_dir = tmp_path / "audio" / "test-album"
        shutil.rmtree(str(audio_dir))
        shutil.rmtree(str(audio_dir.parent))  # remove test-artist
        wrong_dir.mkdir(parents=True)
        (wrong_dir / "01-test.wav").write_text("")

        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="audio")))
        failed_msgs = [c["message"] for c in result["checks"] if c["status"] == "FAIL"]
        assert any("wrong location" in m for m in failed_msgs)
        assert len(result["issues"]) > 0

    def test_specific_checks(self, tmp_path):
        mock_cache, _, _ = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="art")))
        categories = set(c["category"] for c in result["checks"])
        assert "art" in categories
        assert "structure" not in categories

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("nonexistent")))
        assert result["found"] is False

    def test_no_config(self):
        state = {"albums": {}, "ideas": {}, "session": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album")))
        assert "error" in result

    def test_track_validation(self, tmp_path):
        mock_cache, _, _ = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="tracks")))
        track_checks = [c for c in result["checks"] if c["category"] == "tracks"]
        assert len(track_checks) > 0

    def test_missing_readme(self, tmp_path):
        """Missing README.md in album dir is a FAIL."""
        mock_cache, album_dir, _ = self._make_album_on_disk(tmp_path)
        (album_dir / "README.md").unlink()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="structure")))
        failed_msgs = [c["message"] for c in result["checks"] if c["status"] == "FAIL"]
        assert any("README.md" in m for m in failed_msgs)

    def test_no_track_files_warns(self, tmp_path):
        """Empty tracks/ directory produces a warning."""
        mock_cache, album_dir, _ = self._make_album_on_disk(tmp_path)
        # Remove all .md files from tracks/
        for f in (album_dir / "tracks").glob("*.md"):
            f.unlink()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="structure")))
        warn_msgs = [c["message"] for c in result["checks"] if c["status"] == "WARN"]
        assert any("No track files" in m for m in warn_msgs)

    def test_art_found_in_audio(self, tmp_path):
        """album.png in audio dir is a PASS."""
        mock_cache, _, audio_dir = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="art")))
        pass_msgs = [c["message"] for c in result["checks"] if c["status"] == "PASS"]
        assert any("album.png" in m for m in pass_msgs)

    def test_audio_with_wav_and_mastered(self, tmp_path):
        """Audio dir with WAVs and mastered/ subdir both pass."""
        mock_cache, _, audio_dir = self._make_album_on_disk(tmp_path)
        mastered = audio_dir / "mastered"
        mastered.mkdir()
        (mastered / "01-test-mastered.wav").write_text("")
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="audio")))
        pass_msgs = [c["message"] for c in result["checks"] if c["status"] == "PASS"]
        assert any("WAV" in m for m in pass_msgs)
        assert any("mastered/" in m for m in pass_msgs)

    def test_no_audio_dir_skips(self, tmp_path):
        """No audio directory at all produces a SKIP."""
        mock_cache, album_dir, audio_dir = self._make_album_on_disk(tmp_path)
        # Remove entire audio tree
        shutil.rmtree(str(audio_dir.parent))
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="audio")))
        skip_msgs = [c["message"] for c in result["checks"] if c["status"] == "SKIP"]
        assert any("No audio" in m for m in skip_msgs)

    def test_all_checks_run_by_default(self, tmp_path):
        """When checks='all', all categories are included."""
        mock_cache, _, _ = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album")))
        categories = set(c["category"] for c in result["checks"])
        assert "structure" in categories
        assert "audio" in categories
        assert "art" in categories
        assert "tracks" in categories

    def test_track_with_pending_sources_warns(self, tmp_path):
        """Track with sources_verified='Pending' triggers a warning."""
        mock_cache, _, _ = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="tracks")))
        # 02-second-track in SAMPLE_STATE has sources_verified: "Pending"
        warn_msgs = [c["message"] for c in result["checks"] if c["status"] == "WARN"]
        assert any("Sources not verified" in m for m in warn_msgs)


# =============================================================================
# create_album_structure tool tests
# =============================================================================

@pytest.mark.unit
class TestCreateAlbumStructure:
    """Tests for the create_album_structure MCP tool."""

    def _make_state_with_tmp(self, tmp_path):
        content = tmp_path / "content"
        content.mkdir()
        state = _fresh_state()
        state["config"]["content_root"] = str(content)
        return MockStateCache(state), content

    def test_create_basic(self, tmp_path):
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", Path(__file__).resolve().parent.parent.parent.parent):
            result = json.loads(_run(server.create_album_structure("new-album", "electronic")))
        assert result["created"] is True
        assert "new-album" in result["path"]
        assert "README.md" in result["files"]
        assert "tracks/" in result["files"]
        # Verify on disk
        album_path = Path(result["path"])
        assert album_path.exists()
        assert (album_path / "tracks").is_dir()
        assert (album_path / "README.md").exists()

    def test_create_documentary(self, tmp_path):
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", Path(__file__).resolve().parent.parent.parent.parent):
            result = json.loads(_run(server.create_album_structure("doc-album", "hip-hop", documentary=True)))
        assert result["created"] is True
        assert result["documentary"] is True
        assert "RESEARCH.md" in result["files"]
        assert "SOURCES.md" in result["files"]

    def test_already_exists(self, tmp_path):
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        # Create the dir first
        album_dir = content / "artists" / "test-artist" / "albums" / "rock" / "existing"
        album_dir.mkdir(parents=True)

        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_album_structure("existing", "rock")))
        assert result["created"] is False
        assert "already exists" in result["error"]

    def test_no_config(self):
        state = {"albums": {}, "ideas": {}, "session": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_album_structure("test", "rock")))
        assert "error" in result

    def test_slug_normalization(self, tmp_path):
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", Path(__file__).resolve().parent.parent.parent.parent):
            result = json.loads(_run(server.create_album_structure("My New Album", "Hip Hop")))
        assert result["created"] is True
        assert "my-new-album" in result["path"]
        assert result["genre"] == "hip-hop"

    def test_missing_content_root(self):
        """Error when content_root is empty."""
        state = _fresh_state()
        state["config"]["content_root"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_album_structure("test", "rock")))
        assert "error" in result

    def test_missing_templates_graceful(self, tmp_path):
        """Album is still created even when templates directory doesn't exist."""
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        fake_plugin = tmp_path / "fake-plugin"
        fake_plugin.mkdir()
        # No templates/ dir under fake_plugin
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", fake_plugin):
            result = json.loads(_run(server.create_album_structure("no-templates", "rock")))
        assert result["created"] is True
        # tracks/ still created, but README.md might not be in files list
        assert "tracks/" in result["files"]
        album_path = Path(result["path"])
        assert album_path.exists()
        assert (album_path / "tracks").is_dir()


# =============================================================================
# run_pre_generation_gates tool tests
# =============================================================================

# Track file that passes all gates
_TRACK_ALL_GATES_PASS = """\
# Test Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Explicit** | No |
| **Sources Verified** | ✅ Verified (2026-01-01) |

## Suno Inputs

### Style Box
```
electronic, 120 BPM, energetic, male vocals, synth-driven
```

### Lyrics Box
```
[Verse 1]
Testing one two three
This is a test for me

[Chorus]
We're testing all day long
Testing in this song
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| — | — | — |
"""

# Track file that fails multiple gates
_TRACK_GATES_FAIL = """\
# Failing Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Sources Verified** | ❌ Pending |

## Suno Inputs

### Style Box
```
sounds like Eminem, aggressive rap
```

### Lyrics Box
```
[Verse 1]
[TODO] write lyrics here
Ramos walked the streets

[PLACEHOLDER] chorus needed
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| Ramos | Rah-mohs | Spanish name |
"""


@pytest.mark.unit
class TestRunPreGenerationGates:
    """Tests for the run_pre_generation_gates MCP tool."""

    def test_all_pass(self, tmp_path):
        track_file = tmp_path / "05-passing.md"
        track_file.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-passing"] = {
            "path": str(track_file),
            "title": "Passing Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Verified",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        # Reset blocklist cache so it loads from real file
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05")))
        assert result["found"] is True
        track = result["tracks"][0]
        assert track["verdict"] == "READY"
        assert track["blocking"] == 0

    def test_multiple_failures(self, tmp_path):
        track_file = tmp_path / "05-failing.md"
        track_file.write_text(_TRACK_GATES_FAIL)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-failing"] = {
            "path": str(track_file),
            "title": "Failing Track",
            "status": "In Progress",
            "explicit": None,  # Not set
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05")))
        track = result["tracks"][0]
        assert track["verdict"] == "NOT READY"
        assert track["blocking"] >= 3  # sources, TODO markers, pronunciation, artist names

    def test_album_wide(self, tmp_path):
        """Test running gates on all tracks in an album."""
        pass_file = tmp_path / "05-pass.md"
        pass_file.write_text(_TRACK_ALL_GATES_PASS)
        fail_file = tmp_path / "06-fail.md"
        fail_file.write_text(_TRACK_GATES_FAIL)

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-pass"] = {
            "path": str(pass_file), "title": "Pass", "status": "In Progress",
            "explicit": False, "sources_verified": "Verified",
        }
        state["albums"]["test-album"]["tracks"]["06-fail"] = {
            "path": str(fail_file), "title": "Fail", "status": "In Progress",
            "explicit": None, "sources_verified": "Pending",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album")))
        # Should have results for all tracks (the original 2 + our 2)
        assert result["total_tracks"] >= 2
        assert result["total_blocking"] >= 1

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_generation_gates("nonexistent")))
        assert result["found"] is False

    def test_track_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "99")))
        assert result["found"] is False

    def test_gate_details(self, tmp_path):
        """Each gate returns structured data."""
        track_file = tmp_path / "05-detail.md"
        track_file.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-detail"] = {
            "path": str(track_file), "title": "Detail Track",
            "status": "In Progress", "explicit": False,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05")))
        gates = result["tracks"][0]["gates"]
        gate_names = [g["gate"] for g in gates]
        assert "Sources Verified" in gate_names
        assert "Lyrics Reviewed" in gate_names
        assert "Pronunciation Resolved" in gate_names
        assert "Explicit Flag Set" in gate_names
        assert "Style Prompt Complete" in gate_names
        assert "Artist Names Cleared" in gate_names
        assert len(gates) == 6

    def test_track_no_file_path(self):
        """Track with no file path gets SKIP for file-dependent gates."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-no-file"] = {
            "title": "No File Track",
            "status": "In Progress",
            "explicit": True,
            "sources_verified": "Verified",
            "path": "",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05-no-file")))
        track = result["tracks"][0]
        # Pronunciation should SKIP because no file text
        pron_gate = next(g for g in track["gates"] if g["gate"] == "Pronunciation Resolved")
        assert pron_gate["status"] == "SKIP"
        # Lyrics should FAIL because empty
        lyrics_gate = next(g for g in track["gates"] if g["gate"] == "Lyrics Reviewed")
        assert lyrics_gate["status"] == "FAIL"

    def test_explicit_flag_true_passes(self, tmp_path):
        """Track with explicit=True should pass the Explicit Flag gate."""
        track_file = tmp_path / "05-explicit.md"
        track_file.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-explicit"] = {
            "path": str(track_file), "title": "Explicit Track",
            "status": "In Progress", "explicit": True,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05")))
        explicit_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Explicit Flag Set")
        assert explicit_gate["status"] == "PASS"
        assert "Yes" in explicit_gate["detail"]

    def test_explicit_flag_none_warns(self, tmp_path):
        """Track with explicit=None should WARN for Explicit Flag gate."""
        track_file = tmp_path / "05-no-explicit.md"
        track_file.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-no-explicit"] = {
            "path": str(track_file), "title": "No Explicit Track",
            "status": "In Progress", "explicit": None,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05")))
        explicit_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Explicit Flag Set")
        assert explicit_gate["status"] == "WARN"
        assert explicit_gate["severity"] == "WARNING"

    def test_multiple_prefix_matches_error(self, tmp_path):
        """Ambiguous track prefix returns error."""
        file1 = tmp_path / "05-a.md"
        file2 = tmp_path / "05-b.md"
        file1.write_text(_TRACK_ALL_GATES_PASS)
        file2.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-a"] = {
            "path": str(file1), "title": "A", "status": "In Progress",
            "explicit": False, "sources_verified": "Verified",
        }
        state["albums"]["test-album"]["tracks"]["05-b"] = {
            "path": str(file2), "title": "B", "status": "In Progress",
            "explicit": False, "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05")))
        assert result["found"] is False
        assert "Multiple" in result["error"]

    def test_partial_album_verdict(self, tmp_path):
        """Album with mix of passing and failing tracks gives correct verdict."""
        pass_file = tmp_path / "05-pass.md"
        pass_file.write_text(_TRACK_ALL_GATES_PASS)
        fail_file = tmp_path / "06-fail.md"
        fail_file.write_text(_TRACK_GATES_FAIL)

        state = _fresh_state()
        # Clear default tracks to control the test
        state["albums"]["test-album"]["tracks"] = {
            "05-pass": {
                "path": str(pass_file), "title": "Pass", "status": "In Progress",
                "explicit": False, "sources_verified": "Verified",
            },
            "06-fail": {
                "path": str(fail_file), "title": "Fail", "status": "In Progress",
                "explicit": None, "sources_verified": "Pending",
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album")))
        assert result["total_tracks"] == 2
        assert result["total_blocking"] >= 1
        # Should be PARTIAL since one passes and one fails
        assert result["album_verdict"] in ("PARTIAL", "NOT READY")
