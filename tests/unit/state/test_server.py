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

SERVER_PATH = PROJECT_ROOT / "servers" / "state-server" / "server.py"

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
        assert "No albums in state cache" in result["error"]


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
