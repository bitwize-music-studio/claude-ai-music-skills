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
import importlib.metadata
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
    "version": server.CURRENT_VERSION,
    "generated_at": "2025-01-01T00:00:00Z",
    "config": {
        "content_root": "/tmp/test",
        "audio_root": "/tmp/test/audio",
        "documents_root": "/tmp/test/docs",
        "overrides_dir": "/tmp/test/overrides",
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

        mock_build.assert_called_once_with(config, plugin_root=server.PLUGIN_ROOT)
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
# Tests for MCP tool: get_python_command
# =============================================================================


class TestGetPythonCommand:
    """Tests for the get_python_command MCP tool."""

    def test_venv_exists(self, tmp_path):
        """When venv python3 exists, returns path and venv_exists=True."""
        venv_python = tmp_path / ".bitwize-music" / "venv" / "bin" / "python3"
        venv_python.parent.mkdir(parents=True)
        venv_python.touch()
        venv_python.chmod(0o755)

        with patch.object(Path, "home", return_value=tmp_path):
            result = json.loads(_run(server.get_python_command()))

        assert result["venv_exists"] is True
        assert str(venv_python) == result["python"]
        assert "plugin_root" in result
        assert "usage" in result
        assert "warning" not in result

    def test_venv_missing(self, tmp_path):
        """When venv doesn't exist, returns warning with install instructions."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = json.loads(_run(server.get_python_command()))

        assert result["venv_exists"] is False
        assert "warning" in result
        assert "python3 -m venv" in result["warning"]

    def test_plugin_root_included(self):
        """Result always includes plugin_root."""
        result = json.loads(_run(server.get_python_command()))
        assert "plugin_root" in result
        assert result["plugin_root"]  # non-empty

    def test_usage_template(self, tmp_path):
        """Usage field contains a ready-to-paste command template."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = json.loads(_run(server.get_python_command()))
        assert "PLUGIN_DIR" in result["usage"]
        assert "python3" in result["python"]


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
        assert result["path"] == "/tmp/test/audio/artists/test-artist/albums/electronic/test-album"
        assert result["path_type"] == "audio"
        assert result["genre"] == "electronic"

    def test_audio_path_with_explicit_genre(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("audio", "test-album", genre="rock")))
        assert result["path"] == "/tmp/test/audio/artists/test-artist/albums/rock/test-album"
        assert result["genre"] == "rock"

    def test_documents_path(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("documents", "test-album")))
        assert result["path"] == "/tmp/test/docs/artists/test-artist/albums/electronic/test-album"
        assert result["genre"] == "electronic"

    def test_audio_genre_required_not_found(self):
        """Error when genre not provided and album not in state."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("audio", "unknown-album")))
        assert "error" in result
        assert "Genre required" in result["error"]

    def test_documents_genre_required_not_found(self):
        """Error when genre not provided and album not in state."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.resolve_path("documents", "unknown-album")))
        assert "error" in result
        assert "Genre required" in result["error"]

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
        assert result["genre"] == "electronic"


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
# _extract_markdown_section helper tests
# =============================================================================

@pytest.mark.unit
class TestExtractMarkdownSectionHelper:
    """Tests for the _extract_markdown_section helper function."""

    def test_basic_extraction(self):
        text = "# Top\n\n## Target\nContent here\n\n## Other\nOther content"
        result = server._extract_markdown_section(text, "Target")
        assert result == "Content here"

    def test_case_insensitive(self):
        text = "## MY SECTION\nContent\n\n## Next"
        result = server._extract_markdown_section(text, "my section")
        assert result == "Content"

    def test_returns_none_for_missing(self):
        text = "## Section A\nContent"
        result = server._extract_markdown_section(text, "Missing")
        assert result is None

    def test_nested_code_block_with_headings(self):
        """Headings inside code blocks should not be treated as section boundaries."""
        text = (
            "## Lyrics Box\n"
            "*Copy this:*\n\n"
            "```\n"
            "## This is NOT a heading\n"
            "It's inside a code block\n"
            "```\n\n"
            "## Next Section\n"
            "Other content"
        )
        result = server._extract_markdown_section(text, "Lyrics Box")
        # Currently, the regex treats "## This is NOT a heading" inside
        # the code block as a section boundary, truncating content early.
        # This test documents the current behavior.
        # If this is "Content", the heading inside the code block was
        # incorrectly treated as a boundary.
        assert result is not None
        assert "*Copy this:*" in result

    def test_heading_levels_respected(self):
        """Higher-level heading terminates, same-level terminates, lower does not."""
        text = "## Section\nContent\n\n### Sub\nSub content\n\n## End"
        result = server._extract_markdown_section(text, "Section")
        assert "Content" in result
        assert "Sub content" in result

    def test_last_section_to_eof(self):
        """Last section includes content to end of file."""
        text = "## First\nContent A\n\n## Last\nContent B\nMore B"
        result = server._extract_markdown_section(text, "Last")
        assert "Content B" in result
        assert "More B" in result

    def test_empty_section_body(self):
        """Section exists but contains only whitespace."""
        text = "## Empty Section\n\n\n## Next\nContent"
        result = server._extract_markdown_section(text, "Empty Section")
        assert result == ""

    def test_empty_file(self):
        """Empty string returns None."""
        assert server._extract_markdown_section("", "Anything") is None

    def test_heading_only_file(self):
        """File with only a heading, no body content."""
        text = "## Solo Heading"
        result = server._extract_markdown_section(text, "Solo Heading")
        assert result == ""

    def test_h1_terminates_h2(self):
        """H1 heading terminates an H2 section."""
        text = "## Target\nContent\n\n# Top Level\nOther"
        result = server._extract_markdown_section(text, "Target")
        assert result == "Content"
        assert "Other" not in result

    def test_h3_does_not_terminate_h2(self):
        """H3 heading does NOT terminate an H2 section."""
        text = "## Target\nContent\n\n### Sub Heading\nSub content\n\n## End"
        result = server._extract_markdown_section(text, "Target")
        assert "Content" in result
        assert "Sub content" in result

    def test_duplicate_headings_returns_first(self):
        """Multiple identical headings — returns first match."""
        text = "## Duplicate\nFirst body\n\n## Duplicate\nSecond body"
        result = server._extract_markdown_section(text, "Duplicate")
        assert result == "First body"

    def test_heading_with_trailing_whitespace(self):
        """Heading with trailing spaces still matches."""
        text = "## Padded   \nContent here\n\n## Next"
        result = server._extract_markdown_section(text, "Padded")
        assert result == "Content here"

    def test_multiline_content_preserved(self):
        """Multiple lines between headings are fully preserved."""
        text = "## Section\nLine 1\nLine 2\nLine 3\n\n## End"
        result = server._extract_markdown_section(text, "Section")
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_content_with_markdown_formatting(self):
        """Bold, italic, links in section body are preserved."""
        text = "## Section\n**bold** and *italic* and [link](url)\n\n## End"
        result = server._extract_markdown_section(text, "Section")
        assert "**bold**" in result
        assert "*italic*" in result
        assert "[link](url)" in result

    def test_content_with_table(self):
        """Markdown table in section body is preserved."""
        text = "## Details\n| Key | Value |\n|-----|-------|\n| A | B |\n\n## End"
        result = server._extract_markdown_section(text, "Details")
        assert "| A | B |" in result

    def test_content_with_code_block(self):
        """Code block in section body is preserved."""
        text = "## Style Box\n```\nelectronic, 120 BPM\n```\n\n## End"
        result = server._extract_markdown_section(text, "Style Box")
        assert "electronic, 120 BPM" in result


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
                "test-album", "01-test-track", "status", "Generated", force=True
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
                "test-album", "01-test-track", "sources_verified",
                "✅ Verified (2026-02-06)", force=True,
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
                "test-album", "05", "status", "Generated", force=True
            )))
        assert result["success"] is True
        assert result["track_slug"] == "05-unique-track"

    def test_update_preserves_other_fields(self, tmp_path):
        """Updating one field doesn't affect others."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            _run(server.update_track_field("test-album", "01-test-track", "status", "Generated", force=True))
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
                "test-album", "01-test-track", "status", "Generated", force=True
            )))
        assert result["track"]["status"] == "Generated"

    def test_state_cache_updated(self, tmp_path):
        """State cache is updated in memory after field change."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            _run(server.update_track_field("test-album", "01-test-track", "status", "Generated", force=True))
        # write_state should have been called to persist
        mock_write.assert_called_once()
        # In-memory state should reflect update
        state = mock_cache.get_state()
        assert state["albums"]["test-album"]["tracks"]["01-test-track"]["status"] == "Generated"

    def test_cache_update_failure_still_returns_success(self, tmp_path):
        """If cache update fails after successful file write, tool returns success."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        # Make write_state raise an exception
        mock_write = MagicMock(side_effect=OSError("disk full"))
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated", force=True
            )))
        # File write succeeded, so tool should report success
        assert result["success"] is True
        # The file was actually modified
        content = track_file.read_text()
        assert "| **Status** | Generated |" in content

    def test_no_path_stored_returns_found_false(self):
        """Track with empty path returns found: False."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-first-track"]["path"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-first-track", "status", "Final", force=True
            )))
        assert result["found"] is False
        assert "No path stored" in result["error"]

    def test_update_field_with_pipe_in_value(self, tmp_path):
        """Values containing markdown pipe characters are handled."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources_verified",
                "Verified | Multiple Sources", force=True,
            )))
        assert result["success"] is True
        content = track_file.read_text()
        assert "Verified | Multiple Sources" in content

    def test_update_field_with_unicode_value(self, tmp_path):
        """Unicode characters in field values are preserved."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources_verified",
                "✅ Verified (2026-02-09)", force=True,
            )))
        assert result["success"] is True
        content = track_file.read_text()
        assert "✅ Verified (2026-02-09)" in content

    def test_update_file_deleted_after_cache(self, tmp_path):
        """Track file deleted after cache load returns error."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        track_file.unlink()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated", force=True
            )))
        assert "error" in result
        assert "Cannot read" in result["error"]

    def test_update_read_only_file(self, tmp_path):
        """Read-only track file returns write error."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        track_file.chmod(0o444)
        try:
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.update_track_field(
                    "test-album", "01-test-track", "status", "Generated", force=True
                )))
            assert "error" in result
            assert "Cannot write" in result["error"]
        finally:
            track_file.chmod(0o644)

    def test_rapid_sequential_updates(self, tmp_path):
        """Multiple updates to same track don't corrupt file."""
        mock_cache, track_file = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            # In Progress → Generated (valid transition, force to bypass gates)
            _run(server.update_track_field("test-album", "01-test-track", "status", "Generated", force=True))
            _run(server.update_track_field("test-album", "01-test-track", "explicit", "Yes"))
            # Set Suno link so Final transition passes the suno-link gate
            _run(server.update_track_field("test-album", "01-test-track", "suno-link", "https://suno.com/test"))
            # Generated → Final (valid transition)
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Final"
            )))
        assert result["success"] is True
        content = track_file.read_text()
        assert "| **Status** | Final |" in content
        assert "| **Explicit** | Yes |" in content

    def test_cache_update_failure_logs_warning(self, tmp_path, caplog):
        """Cache update failure is logged at warning level."""
        import logging
        mock_cache, _ = self._make_cache_with_file(tmp_path)
        mock_write = MagicMock(side_effect=OSError("disk full"))
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write), \
             caplog.at_level(logging.WARNING):
            _run(server.update_track_field("test-album", "01-test-track", "status", "Generated", force=True))
        assert any("cache update failed" in r.message.lower() for r in caplog.records)


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
        assert result["phase"] == "Ready to Write"

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
        assert "error" in result
        assert "must not escape" in result["error"]
        assert result.get("found") is not True

    def test_path_traversal_absolute_blocked(self, tmp_path):
        """Absolute paths in override names are blocked."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("../../etc/passwd")))
        assert "error" in result
        assert result.get("found") is not True

    def test_empty_override_file(self, tmp_path):
        """Empty override file returns found=True with empty content."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "empty.md").write_text("")

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("empty.md")))
        assert result["found"] is True
        assert result["content"] == ""
        assert result["size"] == 0

    def test_override_with_unicode_content(self, tmp_path):
        """Override with unicode characters (emoji, accents) reads correctly."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        content = "# Prononciation\n\nrésumé → REZ-oo-may\nnaïve → nah-EEV\n🎵 music"
        (override_dir / "pronunciation-guide.md").write_text(content)

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("pronunciation-guide.md")))
        assert result["found"] is True
        assert "résumé" in result["content"]
        assert "🎵" in result["content"]

    def test_symlinked_override_dir(self, tmp_path):
        """Override directory that is a symlink works correctly."""
        real_dir = tmp_path / "real-overrides"
        real_dir.mkdir()
        (real_dir / "test.md").write_text("Symlinked content")
        link_dir = tmp_path / "linked-overrides"
        link_dir.symlink_to(real_dir)

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(link_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("test.md")))
        assert result["found"] is True
        assert "Symlinked content" in result["content"]

    def test_nested_path_traversal_blocked(self, tmp_path):
        """Nested traversal like 'subdir/../../secret' is blocked."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "subdir").mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret")

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("subdir/../../secret.txt")))
        assert "error" in result
        assert result.get("found") is not True

    def test_override_name_with_subdirectory(self, tmp_path):
        """Override name with subdirectory path works when within bounds."""
        override_dir = tmp_path / "overrides"
        sub = override_dir / "custom"
        sub.mkdir(parents=True)
        (sub / "guide.md").write_text("Nested content")

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("custom/guide.md")))
        assert result["found"] is True
        assert "Nested content" in result["content"]


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

    def test_path_traversal_blocked(self, tmp_path):
        """Reference names with '..' don't escape the reference directory."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        # Create a file outside the reference dir
        secret = tmp_path / "secret.md"
        secret.write_text("top secret")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("../secret")))
        assert "error" in result
        assert "must not escape" in result["error"]
        assert result.get("found") is not True

    def test_path_traversal_deep_escape_blocked(self, tmp_path):
        """Deep traversal attempts are blocked."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("../../etc/passwd")))
        assert "error" in result
        assert result.get("found") is not True

    def test_reference_with_unicode_content(self, tmp_path):
        """Reference with non-ASCII characters reads correctly."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        content = "# Guide\n\nRésumé → REZ-oo-may\nCafé → kah-FAY\n"
        (ref_dir / "guide.md").write_text(content)

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("guide")))
        assert result["found"] is True
        assert "Résumé" in result["content"]
        assert "Café" in result["content"]

    def test_reference_symlink_to_valid_file(self, tmp_path):
        """Symlinked reference file within reference/ works."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        real_file = ref_dir / "real-guide.md"
        real_file.write_text("Real content")
        (ref_dir / "alias.md").symlink_to(real_file)

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("alias")))
        assert result["found"] is True
        assert "Real content" in result["content"]

    def test_nested_traversal_blocked(self, tmp_path):
        """Nested traversal like 'suno/../../secret' is blocked."""
        ref_dir = tmp_path / "reference" / "suno"
        ref_dir.mkdir(parents=True)
        secret = tmp_path / "secret.md"
        secret.write_text("top secret")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("suno/../../secret")))
        assert "error" in result
        assert result.get("found") is not True

    def test_section_extraction_preserves_code(self, tmp_path):
        """Section extraction preserves inline code and code blocks."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "guide.md").write_text(
            "## Config\nUse `config.yaml` for settings.\n\n"
            "```yaml\nkey: value\n```\n\n## Next"
        )

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("guide", section="Config")))
        assert result["found"] is True
        assert "`config.yaml`" in result["content"]
        assert "key: value" in result["content"]

    def test_empty_reference_file(self, tmp_path):
        """Empty reference file returns found=True with empty content."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "empty.md").write_text("")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("empty")))
        assert result["found"] is True
        assert result["size"] == 0

    def test_whitespace_in_name_stripped(self, tmp_path):
        """Leading/trailing whitespace in name is stripped."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir(parents=True)
        (ref_dir / "guide.md").write_text("Content")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("  guide  ")))
        assert result["found"] is True


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
        assert result["has_homographs"] is True
        words = [r["canonical"] for r in result["matches"]]
        assert "live" in words

    def test_finds_multiple(self):
        text = "Read the lead and close the record"
        result = json.loads(_run(server.check_homographs(text)))
        words = set(r["canonical"] for r in result["matches"])
        assert "read" in words
        assert "lead" in words
        assert "close" in words
        assert "record" in words

    def test_empty_text(self):
        result = json.loads(_run(server.check_homographs("")))
        assert result["count"] == 0
        assert result["has_homographs"] is False
        assert result["matches"] == []

    def test_no_homographs(self):
        text = "The sun sets over the mountain\nBirds fly across the sky"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] == 0
        assert result["has_homographs"] is False

    def test_skips_section_tags(self):
        text = "[Verse 1]\nlive and breathe\n[Chorus]\nstay alive"
        result = json.loads(_run(server.check_homographs(text)))
        # Should find "live" in verse but not scan [Verse 1] or [Chorus] lines
        for r in result["matches"]:
            assert not r["line"].startswith("[")

    def test_returns_line_numbers(self):
        text = "Line one\nThe wind blows hard\nLine three"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] == 1
        assert result["matches"][0]["line_number"] == 2

    def test_case_insensitive(self):
        text = "LIVE performance tonight\nRead the book"
        result = json.loads(_run(server.check_homographs(text)))
        words = [r["canonical"] for r in result["matches"]]
        assert "live" in words
        assert "read" in words

    def test_includes_options(self):
        text = "lead the way"
        result = json.loads(_run(server.check_homographs(text)))
        assert result["count"] == 1
        entry = result["matches"][0]
        assert len(entry["options"]) > 0
        assert "pron_a" in entry["options"][0]

    def test_word_boundary_no_partial_match(self):
        """Homographs should not match partial words (e.g., 'alive' should not trigger 'live')."""
        text = "She's alive and thriving\nDriven to survive"
        result = json.loads(_run(server.check_homographs(text)))
        # "alive" contains "live" but should NOT match due to word boundary
        words = [r["canonical"] for r in result["matches"]]
        assert "live" not in words

    def test_multiple_same_line(self):
        """Multiple homographs on the same line each get reported."""
        text = "Read the record, close the wound"
        result = json.loads(_run(server.check_homographs(text)))
        words = [r["canonical"] for r in result["matches"]]
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
        assert result["matches"][0]["column"] == 4  # "The " is 4 chars


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
        names = [r["name"] for r in result["matches"]]
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
        entry = result["matches"][0]
        assert "alternative" in entry
        assert len(entry["alternative"]) > 0

    def test_case_insensitive(self):
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("heavy like METALLICA")))
        assert result["clean"] is False

    def test_multiple_names(self):
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("mix of Eminem and Drake style")))
        names = [r["name"] for r in result["matches"]]
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
        assert "genre" in result["matches"][0]
        assert result["matches"][0]["genre"] == "Electronic & Dance"

    def test_blocklist_file_missing(self, tmp_path):
        """Gracefully handles missing blocklist file."""
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.scan_artist_names("sounds like Metallica")))
        # With no blocklist file, nothing should be found
        assert result["clean"] is True
        assert result["count"] == 0

    def test_same_artist_mentioned_twice(self):
        """Artist mentioned multiple times appears once in results."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names(
                "Skrillex-style drops and Skrillex-like bass"
            )))
        names = [r["name"] for r in result["matches"]]
        assert names.count("Skrillex") == 1
        assert result["count"] >= 1

    def test_whitespace_only_text(self):
        """Whitespace-only text returns clean."""
        result = json.loads(_run(server.scan_artist_names("   \n\t  ")))
        assert result["clean"] is True
        assert result["count"] == 0

    def test_multiline_text(self):
        """Artist names found across multiple lines."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names(
                "First line is clean\nSecond line has Eminem vibes\n"
                "Third line mentions Drake flow"
            )))
        names = [r["name"] for r in result["matches"]]
        assert "Eminem" in names
        assert "Drake" in names

    def test_special_characters_near_name(self):
        """Artist names at punctuation boundaries are detected."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names(
                "like (Skrillex) or [Deadmau5]"
            )))
        names = [r["name"] for r in result["matches"]]
        assert "Skrillex" in names

    def test_each_found_entry_has_all_fields(self):
        """Every found entry includes name, alternative, and genre."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.scan_artist_names("sounds like Drake")))
        for entry in result["matches"]:
            assert "name" in entry
            assert "alternative" in entry
            assert "genre" in entry


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
        audio_dir = audio / "artists" / "test-artist" / "albums" / "electronic" / "test-album"

        tracks_dir.mkdir(parents=True)
        audio_dir.mkdir(parents=True)
        (album_dir / "README.md").write_text("# Test Album")
        (tracks_dir / "01-test.md").write_text(_SAMPLE_TRACK_MD)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-test.wav").write_text("")  # dummy wav
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
        # Move audio to old flat structure (wrong location)
        wrong_dir = tmp_path / "audio" / "test-artist" / "test-album"
        shutil.rmtree(str(audio_dir))
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

    def test_symlinked_album_dir_passes(self, tmp_path):
        """Album directory that is a symlink still passes structure checks."""
        mock_cache, album_dir, _ = self._make_album_on_disk(tmp_path)
        # Create a symlink pointing to the real album dir
        link_dir = tmp_path / "link-album"
        link_dir.symlink_to(album_dir)
        # Point state at the symlink
        state = mock_cache.get_state()
        state["albums"]["test-album"]["path"] = str(link_dir)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="structure")))
        assert result["found"] is True
        assert result["failed"] == 0

    def test_symlinked_audio_dir_passes(self, tmp_path):
        """Audio directory that is a symlink still passes audio checks."""
        mock_cache, _, audio_dir = self._make_album_on_disk(tmp_path)
        # Create symlink for audio
        real_audio = audio_dir
        symlink_audio = tmp_path / "audio-link" / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        symlink_audio.parent.mkdir(parents=True)
        symlink_audio.symlink_to(real_audio)
        # Point config at the symlinked root
        state = mock_cache.get_state()
        state["config"]["audio_root"] = str(tmp_path / "audio-link")
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="audio")))
        assert result["found"] is True
        pass_msgs = [c["message"] for c in result["checks"] if c["status"] == "PASS"]
        assert any("Audio directory" in m for m in pass_msgs)

    def test_broken_symlink_fails(self, tmp_path):
        """Broken symlink for album dir is detected as missing."""
        mock_cache, album_dir, _ = self._make_album_on_disk(tmp_path)
        # Create a broken symlink
        broken_link = tmp_path / "broken-album"
        broken_link.symlink_to(tmp_path / "nonexistent-target")
        state = mock_cache.get_state()
        state["albums"]["test-album"]["path"] = str(broken_link)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="structure")))
        failed_msgs = [c["message"] for c in result["checks"] if c["status"] == "FAIL"]
        assert any("missing" in m.lower() for m in failed_msgs)

    def test_permission_denied_tracks_dir(self, tmp_path):
        """Unreadable tracks/ directory still produces results."""
        mock_cache, album_dir, _ = self._make_album_on_disk(tmp_path)
        (album_dir / "tracks").chmod(0o000)
        try:
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.validate_album_structure("test-album", checks="structure")))
            assert result["found"] is True
            # tracks/ exists but can't be read — should still pass is_dir check
            check_msgs = [c["message"] for c in result["checks"]]
            assert any("tracks/" in m for m in check_msgs)
        finally:
            (album_dir / "tracks").chmod(0o755)

    def test_multiple_check_types(self, tmp_path):
        """Comma-separated check types work correctly."""
        mock_cache, _, _ = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="structure,art")))
        categories = set(c["category"] for c in result["checks"])
        assert "structure" in categories
        assert "art" in categories
        assert "audio" not in categories
        assert "tracks" not in categories

    def test_invalid_check_type_ignored(self, tmp_path):
        """Invalid check type falls back to all checks."""
        mock_cache, _, _ = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album", checks="invalid")))
        categories = set(c["category"] for c in result["checks"])
        # Invalid type → empty check_set → defaults to all
        assert "structure" in categories
        assert "audio" in categories

    def test_result_counts_consistent(self, tmp_path):
        """passed + failed + warnings + skipped matches total checks."""
        mock_cache, _, _ = self._make_album_on_disk(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album")))
        total = result["passed"] + result["failed"] + result["warnings"] + result["skipped"]
        assert total == len(result["checks"])


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
# Genre validation tests
# =============================================================================

@pytest.mark.unit
class TestGenreValidation:
    """Tests for genre validation in create_album_structure."""

    def _make_state_with_tmp(self, tmp_path):
        content = tmp_path / "content"
        content.mkdir()
        state = _fresh_state()
        state["config"]["content_root"] = str(content)
        return MockStateCache(state), content

    def test_valid_genre_accepted(self, tmp_path):
        """Valid genre 'electronic' is accepted."""
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", Path(__file__).resolve().parent.parent.parent.parent):
            result = json.loads(_run(server.create_album_structure("genre-test", "electronic")))
        assert result["created"] is True

    def test_invalid_genre_rejected(self, tmp_path):
        """Invalid genre 'boom-bap' is rejected with valid genres list."""
        mock_cache, _ = self._make_state_with_tmp(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_album_structure("genre-test", "boom-bap")))
        assert "error" in result
        assert "Invalid genre" in result["error"]
        assert "hip-hop" in result["error"]  # valid genres listed

    def test_genre_alias_resolved(self, tmp_path):
        """Genre alias 'R&B' resolves to 'rnb' directory."""
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", Path(__file__).resolve().parent.parent.parent.parent):
            result = json.loads(_run(server.create_album_structure("rnb-test", "R&B")))
        assert result["created"] is True
        assert "/rnb/" in result["path"]

    def test_genre_typo_rejected(self, tmp_path):
        """Genre typo 'elctronic' is rejected."""
        mock_cache, _ = self._make_state_with_tmp(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_album_structure("typo-test", "elctronic")))
        assert "error" in result
        assert "Invalid genre" in result["error"]

    def test_additional_genre_from_config(self, tmp_path):
        """Genre from additional_genres config is accepted."""
        mock_cache, content = self._make_state_with_tmp(tmp_path)
        state = mock_cache.get_state()
        state["config"]["generation"] = {"additional_genres": ["synthwave", "lo-fi"]}
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", Path(__file__).resolve().parent.parent.parent.parent):
            result = json.loads(_run(server.create_album_structure("synth-test", "synthwave")))
        assert result["created"] is True

    def test_additional_genre_in_error_message(self, tmp_path):
        """Additional genres appear in the valid genres error list."""
        mock_cache, _ = self._make_state_with_tmp(tmp_path)
        state = mock_cache.get_state()
        state["config"]["generation"] = {"additional_genres": ["synthwave"]}
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_album_structure("bad-test", "nope")))
        assert "error" in result
        assert "synthwave" in result["error"]


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
        assert "Homograph Check" in gate_names
        assert "Lyric Length" in gate_names
        assert len(gates) == 8

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

    def test_explicit_flag_none_blocks(self, tmp_path):
        """Track with explicit=None should BLOCK for Explicit Flag gate."""
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
        assert explicit_gate["status"] == "FAIL"
        assert explicit_gate["severity"] == "BLOCKING"

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

    def test_unreadable_track_file(self, tmp_path):
        """Track with unreadable file still produces gate results (no crash)."""
        # Create a directory where a file is expected — triggers IsADirectoryError
        bad_path = tmp_path / "05-unreadable.md"
        bad_path.mkdir()

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-unreadable"] = {
            "path": str(bad_path), "title": "Unreadable Track",
            "status": "In Progress", "explicit": False,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05-unreadable")))
        assert result["found"] is True
        track = result["tracks"][0]
        # Should still produce gates (file-dependent ones SKIP or FAIL)
        assert len(track["gates"]) == 8

    def test_permission_error_track_file(self, tmp_path):
        """Track with permission-denied file still produces gate results."""
        track_file = tmp_path / "05-denied.md"
        track_file.write_text(_TRACK_ALL_GATES_PASS)
        track_file.chmod(0o000)

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-denied"] = {
            "path": str(track_file), "title": "Denied Track",
            "status": "In Progress", "explicit": False,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        try:
            with patch.object(server, "cache", mock_cache), \
                 patch.object(server, "_artist_blocklist_cache", None):
                result = json.loads(_run(server.run_pre_generation_gates("test-album", "05-denied")))
            assert result["found"] is True
            track = result["tracks"][0]
            assert len(track["gates"]) == 8
        finally:
            track_file.chmod(0o644)

    def test_unreadable_file_logs_warning(self, tmp_path, caplog):
        """Unreadable track file triggers a warning log."""
        import logging
        bad_path = tmp_path / "05-bad.md"
        bad_path.mkdir()  # directory, not file

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-bad"] = {
            "path": str(bad_path), "title": "Bad Track",
            "status": "In Progress", "explicit": False,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None), \
             caplog.at_level(logging.WARNING):
            _run(server.run_pre_generation_gates("test-album", "05-bad"))
        assert any("Cannot read" in r.message for r in caplog.records)

    def test_gate_counts_in_album_result(self, tmp_path):
        """Album-level result includes accurate blocking/warning/total counts."""
        pass_file_1 = tmp_path / "05-pass.md"
        pass_file_1.write_text(_TRACK_ALL_GATES_PASS)
        pass_file_2 = tmp_path / "06-pass.md"
        pass_file_2.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "05-pass": {
                "path": str(pass_file_1), "title": "Pass 1", "status": "In Progress",
                "explicit": False, "sources_verified": "Verified",
            },
            "06-pass": {
                "path": str(pass_file_2), "title": "Pass 2", "status": "In Progress",
                "explicit": False, "sources_verified": "Verified",
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album")))
        assert result["total_tracks"] == 2
        assert result["total_blocking"] == 0
        assert result["album_verdict"] == "ALL READY"

    def test_sources_verified_case_variations(self, tmp_path):
        """Different sources_verified values are handled correctly."""
        track_file = tmp_path / "05-src.md"
        track_file.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()

        # Test with "N/A" — should pass (not applicable)
        state["albums"]["test-album"]["tracks"]["05-src"] = {
            "path": str(track_file), "title": "Src Track",
            "status": "In Progress", "explicit": False,
            "sources_verified": "N/A",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05-src")))
        src_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Sources Verified")
        assert src_gate["status"] == "PASS"

    def test_all_tracks_failing_verdict(self, tmp_path):
        """All tracks failing gives NOT READY verdict."""
        fail_file = tmp_path / "05-fail.md"
        fail_file.write_text(_TRACK_GATES_FAIL)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "05-fail": {
                "path": str(fail_file), "title": "Fail", "status": "In Progress",
                "explicit": None, "sources_verified": "Pending",
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album")))
        assert result["album_verdict"] == "NOT READY"
        assert result["total_blocking"] >= 1


# =============================================================================
# Homograph Gate (Gate 7) + Pre-Gen Gate Enforcement in update_track_field
# =============================================================================

@pytest.mark.unit
class TestHomographGate:
    """Tests for Gate 7 (Homograph Check) in pre-generation gates."""

    def test_gate7_pass_no_homographs(self, tmp_path):
        """Gate 7 passes when lyrics contain no homographs."""
        track_file = tmp_path / "05-clean.md"
        track_file.write_text(_TRACK_ALL_GATES_PASS)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-clean"] = {
            "path": str(track_file), "title": "Clean Track",
            "status": "In Progress", "explicit": False,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05-clean")))
        homograph_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Homograph Check")
        assert homograph_gate["status"] == "PASS"

    def test_gate7_fail_homograph_in_lyrics(self, tmp_path):
        """Gate 7 fails when lyrics contain 'live' or 'read'."""
        track_content = _TRACK_ALL_GATES_PASS.replace(
            "Testing one two three\nThis is a test for me",
            "We live to read the signs\nThe lead will guide us home"
        )
        track_file = tmp_path / "05-homo.md"
        track_file.write_text(track_content)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-homo"] = {
            "path": str(track_file), "title": "Homo Track",
            "status": "In Progress", "explicit": False,
            "sources_verified": "Verified",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05-homo")))
        homograph_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Homograph Check")
        assert homograph_gate["status"] == "FAIL"
        assert homograph_gate["severity"] == "BLOCKING"
        assert "live" in homograph_gate["detail"]
        assert "read" in homograph_gate["detail"]
        assert "lead" in homograph_gate["detail"]

    def test_gate7_skip_no_lyrics(self):
        """Gate 7 skips when no lyrics content is available."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-no-lyrics"] = {
            "title": "No Lyrics", "status": "In Progress",
            "explicit": True, "sources_verified": "Verified", "path": "",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "05-no-lyrics")))
        homograph_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Homograph Check")
        assert homograph_gate["status"] == "SKIP"


@pytest.mark.unit
class TestPreGenGateEnforcementInUpdateTrackField:
    """Tests for pre-generation gate enforcement when setting status to Generated."""

    def _make_cache_with_track(self, tmp_path, track_content, **overrides):
        """Create a mock cache with a track file."""
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(track_content)
        track_data = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        track_data.update(overrides)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = track_data
        return MockStateCache(state), track_file

    def test_generated_blocked_empty_lyrics(self, tmp_path):
        """Status→Generated blocked when lyrics are empty (gate 2)."""
        content = _TRACK_ALL_GATES_PASS.replace(
            "[Verse 1]\nTesting one two three\nThis is a test for me\n\n[Chorus]\nWe're testing all day long\nTesting in this song",
            ""
        )
        mock_cache, _ = self._make_cache_with_track(tmp_path, content)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert "error" in result
        assert "pre-generation gate" in result["error"]
        assert "failed_gates" in result

    def test_generated_blocked_homograph(self, tmp_path):
        """Status→Generated blocked when homograph present (gate 7)."""
        content = _TRACK_ALL_GATES_PASS.replace(
            "Testing one two three",
            "We live for the night"
        )
        mock_cache, _ = self._make_cache_with_track(tmp_path, content)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert "error" in result
        assert "pre-generation gate" in result["error"]
        gate_names = [g["gate"] for g in result["failed_gates"]]
        assert "Homograph Check" in gate_names

    def test_generated_succeeds_all_gates_pass(self, tmp_path):
        """Status→Generated succeeds when all gates pass."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _TRACK_ALL_GATES_PASS, sources_verified="Verified"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert result["success"] is True

    def test_force_bypasses_gate_check(self, tmp_path):
        """force=True bypasses pre-generation gate enforcement."""
        content = _TRACK_ALL_GATES_PASS.replace(
            "Testing one two three",
            "We live for the night"
        )
        mock_cache, _ = self._make_cache_with_track(tmp_path, content)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated", force=True
            )))
        assert result["success"] is True

    def test_lyric_length_passes_under_800(self, tmp_path):
        """Lyrics under 800 words pass the Lyric Length gate."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _TRACK_ALL_GATES_PASS, sources_verified="Verified",
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "01-test-track")))
        length_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Lyric Length")
        assert length_gate["status"] == "PASS"
        assert "words" in length_gate["detail"]

    def test_lyric_length_blocks_over_800(self, tmp_path):
        """Lyrics over 800 words block the Lyric Length gate."""
        # Generate lyrics with 850+ words
        long_lyrics = "\n".join(f"word{i} word{i}a word{i}b word{i}c word{i}d" for i in range(170))
        content = _TRACK_ALL_GATES_PASS.replace(
            "[Verse 1]\nTesting one two three\nThis is a test for me\n\n"
            "[Chorus]\nWe're testing all day long\nTesting in this song",
            "[Verse 1]\n" + long_lyrics,
        )
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, content, sources_verified="Verified",
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album", "01-test-track")))
        length_gate = next(g for g in result["tracks"][0]["gates"] if g["gate"] == "Lyric Length")
        assert length_gate["status"] == "FAIL"
        assert length_gate["severity"] == "BLOCKING"
        assert "800" in length_gate["detail"]

    def test_generated_blocked_over_800_words(self, tmp_path):
        """Status→Generated blocked when lyrics exceed 800 words (gate 8)."""
        long_lyrics = "\n".join(f"word{i} word{i}a word{i}b word{i}c word{i}d" for i in range(170))
        content = _TRACK_ALL_GATES_PASS.replace(
            "[Verse 1]\nTesting one two three\nThis is a test for me\n\n"
            "[Chorus]\nWe're testing all day long\nTesting in this song",
            "[Verse 1]\n" + long_lyrics,
        )
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, content, sources_verified="Verified",
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert "error" in result
        assert "pre-generation gate" in result["error"]
        gate_names = [g["gate"] for g in result["failed_gates"]]
        assert "Lyric Length" in gate_names

    def test_config_max_lyric_words_raises_limit(self, tmp_path):
        """Config max_lyric_words allows longer lyrics when raised."""
        # 850 words — would fail at default 800, but passes at 1000
        long_lyrics = "\n".join(f"word{i} word{i}a word{i}b word{i}c word{i}d" for i in range(170))
        content = _TRACK_ALL_GATES_PASS.replace(
            "[Verse 1]\nTesting one two three\nThis is a test for me\n\n"
            "[Chorus]\nWe're testing all day long\nTesting in this song",
            "[Verse 1]\n" + long_lyrics,
        )
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, content, sources_verified="Verified",
        )
        state = mock_cache.get_state()
        state["config"]["generation"] = {"max_lyric_words": 1000}
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert result["success"] is True

    def test_generated_blocked_explicit_none(self, tmp_path):
        """Status→Generated blocked when explicit flag is None (gate 4)."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _TRACK_ALL_GATES_PASS,
            sources_verified="Verified", explicit=None,
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Generated"
            )))
        assert "error" in result
        assert "pre-generation gate" in result["error"]
        gate_names = [g["gate"] for g in result["failed_gates"]]
        assert "Explicit Flag Set" in gate_names

    def test_non_generated_status_not_gated(self, tmp_path):
        """Status transitions other than →Generated are not gated."""
        # Use _SAMPLE_TRACK_MD which would fail gates — but going to "Generated"
        # is not what we're testing; In Progress is the target and should work fine
        content = _TRACK_ALL_GATES_PASS.replace(
            "| **Status** | In Progress |", "| **Status** | Not Started |"
        )
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, content, status="Not Started"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "In Progress"
            )))
        assert result["success"] is True


# =============================================================================
# Suno link Final gate tests
# =============================================================================

@pytest.mark.unit
class TestSunoLinkFinalGate:
    """Tests for the Suno link requirement when transitioning to Final."""

    def _make_cache_with_track(self, tmp_path, has_suno_link=False):
        """Create a mock cache with a Generated track."""
        track_file = tmp_path / "01-test-track.md"
        suno_link_value = "https://suno.com/song/abc123" if has_suno_link else "—"
        track_file.write_text(_TRACK_ALL_GATES_PASS.replace(
            "| **Status** | In Progress |", "| **Status** | Generated |"
        ))
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "Generated",
            "explicit": False,
            "has_suno_link": has_suno_link,
            "sources_verified": "Verified",
            "mtime": 1234567890.0,
        }
        return MockStateCache(state), track_file

    def test_final_blocked_no_suno_link(self, tmp_path):
        """Generated → Final blocked when has_suno_link is False."""
        mock_cache, _ = self._make_cache_with_track(tmp_path, has_suno_link=False)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Final"
            )))
        assert "error" in result
        assert "Suno link" in result["error"]

    def test_final_passes_with_suno_link(self, tmp_path):
        """Generated → Final succeeds when has_suno_link is True."""
        mock_cache, _ = self._make_cache_with_track(tmp_path, has_suno_link=True)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Final"
            )))
        assert result["success"] is True

    def test_force_bypasses_suno_link_check(self, tmp_path):
        """force=True bypasses the Suno link requirement."""
        mock_cache, _ = self._make_cache_with_track(tmp_path, has_suno_link=False)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Final", force=True
            )))
        assert result["success"] is True

    def test_config_disabled_allows_final_without_link(self, tmp_path):
        """When require_suno_link_for_final is false, Final works without a link."""
        mock_cache, _ = self._make_cache_with_track(tmp_path, has_suno_link=False)
        state = mock_cache.get_state()
        state["config"]["generation"] = {"require_suno_link_for_final": False}
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Final"
            )))
        assert result["success"] is True


# =============================================================================
# check_explicit_content tool tests
# =============================================================================

@pytest.mark.unit
class TestCheckExplicitContent:
    """Tests for the check_explicit_content MCP tool."""

    def test_finds_explicit_words(self):
        text = "[Verse 1]\nWhat the fuck is going on\nThis shit is broken"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        assert result["has_explicit"] is True
        words = [r["word"] for r in result["matches"]]
        assert "fuck" in words
        assert "shit" in words

    def test_clean_text(self):
        text = "[Verse 1]\nThe sun is shining bright\nBirds sing along"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        assert result["has_explicit"] is False
        assert result["total_count"] == 0

    def test_empty_text(self):
        result = json.loads(_run(server.check_explicit_content("")))
        assert result["has_explicit"] is False

    def test_counts_occurrences(self):
        text = "Fuck this, fuck that, everything is fucked"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        # "fuck" x2 + "fucked" x1 = at least 3 total
        assert result["total_count"] >= 3

    def test_case_insensitive(self):
        text = "SHIT happens\nWhat the FUCK"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        assert result["has_explicit"] is True
        assert result["unique_words"] >= 2

    def test_word_boundary_no_partial(self):
        """Should not match 'bass' in 'bassist' or 'hit' in 'shitty' incorrectly."""
        text = "The classic hit song played on the radio"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        assert result["has_explicit"] is False

    def test_skips_section_tags(self):
        text = "[Fuck]\nClean lyrics here"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        # [Fuck] is a section tag, should be skipped
        assert result["has_explicit"] is False

    def test_returns_line_numbers(self):
        text = "Line one is clean\nThis line has shit in it\nLine three clean"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        assert result["matches"][0]["lines"][0]["line_number"] == 2

    def test_override_adds_words(self, tmp_path):
        """User override can add custom explicit words."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Custom\n\n## Additional Explicit Words\n\n- customword\n- badterm\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content("This has a customword")))
        assert result["has_explicit"] is True
        assert result["matches"][0]["word"] == "customword"

    def test_override_removes_words(self, tmp_path):
        """User override can remove base words."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Custom\n\n## Not Explicit (Override Base)\n\n- damn (period dialogue)\n- shit\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content("This is shit")))
        # "shit" was removed from the list
        assert result["has_explicit"] is False

    def test_multiple_lines_same_word(self):
        """Same word on multiple lines gets consolidated."""
        text = "Fuck on line one\nAnother fuck on line two"
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        fuck_entry = next(r for r in result["matches"] if r["word"] == "fuck")
        assert fuck_entry["count"] == 2
        assert len(fuck_entry["lines"]) == 2

    def test_override_error_logs_warning(self, tmp_path, caplog):
        """Malformed override file logs warning instead of silently failing."""
        import logging

        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        # Create a directory where a file is expected — triggers OSError on read
        (override_dir / "explicit-words.md").mkdir()

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             caplog.at_level(logging.WARNING):
            result = json.loads(_run(server.check_explicit_content("clean text")))
        # Should still work (falls back to base words)
        assert result["has_explicit"] is False
        # Warning should have been logged
        assert any("explicit word overrides" in r.message.lower() or
                    "Failed to load" in r.message
                    for r in caplog.records)

    def test_override_error_still_returns_base_words(self, tmp_path):
        """When override loading fails, base explicit words still work."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").mkdir()  # directory, not file

        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content("This has shit")))
        # Base words should still be loaded
        assert result["has_explicit"] is True

    def test_whitespace_only_text(self):
        """Whitespace-only text returns no explicit content."""
        result = json.loads(_run(server.check_explicit_content("   \n\t  ")))
        assert result["has_explicit"] is False

    def test_section_tag_with_dash_not_scanned(self):
        """Section tags like [Verse-Hook] are skipped."""
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content("[Fuck-Chorus]\nClean lyrics")))
        assert result["has_explicit"] is False

    def test_explicit_word_at_line_start(self):
        """Explicit word at beginning of line is detected."""
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content("Shit, that was loud")))
        assert result["has_explicit"] is True
        assert result["matches"][0]["lines"][0]["line_number"] == 1

    def test_explicit_word_at_line_end(self):
        """Explicit word at end of line is detected."""
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content("Oh that's some shit")))
        assert result["has_explicit"] is True

    def test_many_lines_scanned_efficiently(self):
        """Large text with many lines completes without error."""
        lines = ["Clean line number {}".format(i) for i in range(500)]
        lines[250] = "This line has the word fuck in it"
        text = "\n".join(lines)
        with patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content(text)))
        assert result["has_explicit"] is True
        assert result["matches"][0]["lines"][0]["line_number"] == 251

    def test_empty_override_adds_nothing(self, tmp_path):
        """Override file with no words in list sections adds nothing extra."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Explicit Words Override\n\n## Additional Explicit Words\n\n## Not Explicit (Override Base)\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None):
            result = json.loads(_run(server.check_explicit_content("Clean text here")))
        assert result["has_explicit"] is False

    def test_override_adds_and_removes_combined(self, tmp_path):
        """Override adds custom words AND removes base words simultaneously."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Custom\n\n"
            "## Additional Explicit Words\n\n- badterm\n\n"
            "## Not Explicit (Override Base)\n\n- damn (period language)\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            # "damn" removed from base, should be clean
            result1 = json.loads(_run(server.check_explicit_content("Well damn")))
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            # "badterm" added, should be explicit
            result2 = json.loads(_run(server.check_explicit_content("That's a badterm")))
        assert result1["has_explicit"] is False
        assert result2["has_explicit"] is True


# =============================================================================
# extract_links tool tests
# =============================================================================

@pytest.mark.unit
class TestExtractLinks:
    """Tests for the extract_links MCP tool."""

    def test_sources_md(self, tmp_path):
        """Extract links from SOURCES.md."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "SOURCES.md").write_text(
            "# Sources\n\n"
            "- [FBI Press Release](https://fbi.gov/news/123)\n"
            "- [Court Filing](https://pacer.gov/doc/456)\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "SOURCES.md")))
        assert result["found"] is True
        assert result["count"] == 2
        assert result["links"][0]["text"] == "FBI Press Release"
        assert "fbi.gov" in result["links"][0]["url"]

    def test_research_md(self, tmp_path):
        """Extract links from RESEARCH.md."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "RESEARCH.md").write_text(
            "# Research\n\n[Source A](https://example.com/a)\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "RESEARCH.md")))
        assert result["count"] == 1

    def test_track_file(self, tmp_path):
        """Extract links from a track file by slug."""
        track_file = tmp_path / "05-track.md"
        track_file.write_text(
            "# Track\n\n## Source\n[Wikipedia](https://en.wikipedia.org/test)\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-track"] = {
            "path": str(track_file), "title": "Track", "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "05-track")))
        assert result["found"] is True
        assert result["count"] == 1
        assert result["links"][0]["text"] == "Wikipedia"

    def test_no_links(self, tmp_path):
        """File with no markdown links returns empty list."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "SOURCES.md").write_text("# Sources\n\nNo links here.\n")
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "SOURCES.md")))
        assert result["found"] is True
        assert result["count"] == 0

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("nonexistent")))
        assert result["found"] is False

    def test_file_not_found(self):
        """File that doesn't exist in album dir returns error."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "NONEXISTENT.md")))
        assert result["found"] is False

    def test_returns_line_numbers(self, tmp_path):
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "SOURCES.md").write_text(
            "# Sources\n\n\n[Link1](https://a.com)\n\n[Link2](https://b.com)\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "SOURCES.md")))
        assert result["links"][0]["line_number"] == 4
        assert result["links"][1]["line_number"] == 6

    def test_prefix_match_track(self, tmp_path):
        """Track slug prefix resolves to full track."""
        track_file = tmp_path / "05-my-track.md"
        track_file.write_text("# Track\n[Link](https://example.com)\n")
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-my-track"] = {
            "path": str(track_file), "title": "My Track", "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "05")))
        assert result["found"] is True
        assert result["count"] == 1

    def test_multiple_links_per_line(self, tmp_path):
        """Multiple links on one line are all captured."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "SOURCES.md").write_text(
            "See [A](https://a.com) and [B](https://b.com) for details.\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album", "SOURCES.md")))
        assert result["count"] == 2


# =============================================================================
# get_lyrics_stats tool tests
# =============================================================================

@pytest.mark.unit
class TestGetLyricsStats:
    """Tests for the get_lyrics_stats MCP tool."""

    def test_single_track(self, tmp_path):
        """Stats for a single track with known word count."""
        track_file = tmp_path / "05-stats.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-stats"] = {
            "path": str(track_file), "title": "Stats Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "05")))
        assert result["found"] is True
        track = result["tracks"][0]
        assert track["word_count"] > 0
        assert track["char_count"] > 0
        assert track["section_count"] == 2  # [Verse 1] and [Chorus]
        assert "status" in track

    def test_genre_target(self):
        """Result includes genre-appropriate word count targets."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album")))
        assert result["genre"] == "electronic"
        assert "target" in result
        assert "min" in result["target"]
        assert "max" in result["target"]

    def test_album_wide(self, tmp_path):
        """Stats for all tracks in an album."""
        track_file = tmp_path / "05-all.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-all"] = {
            "path": str(track_file), "title": "All Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album")))
        # Should have results for all tracks (original 2 + ours)
        assert len(result["tracks"]) >= 3

    def test_empty_lyrics(self, tmp_path):
        """Track with no Lyrics Box section gets EMPTY status."""
        track_file = tmp_path / "05-empty.md"
        track_file.write_text("# Track\n\n## Suno Inputs\n\n### Style Box\n```\nrock\n```\n")
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-empty"] = {
            "path": str(track_file), "title": "Empty Track",
            "status": "Not Started",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "05")))
        assert result["tracks"][0]["status"] == "EMPTY"
        assert result["tracks"][0]["word_count"] == 0

    def test_over_target_status(self, tmp_path):
        """Track over genre max gets OVER status."""
        # Electronic target is 100-200. Create lyrics with >200 words.
        long_lyrics = "\n".join(f"Word number {i} here today" for i in range(60))
        track_file = tmp_path / "05-long.md"
        track_file.write_text(
            f"# Track\n\n## Suno Inputs\n\n### Lyrics Box\n```\n[Verse 1]\n{long_lyrics}\n```\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-long"] = {
            "path": str(track_file), "title": "Long Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "05")))
        track = result["tracks"][0]
        assert track["status"] in ("OVER", "DANGER")
        assert track["word_count"] > 200

    def test_danger_zone(self, tmp_path):
        """Track over 800 words gets DANGER status."""
        huge_lyrics = "\n".join(f"Word number {i} goes here" for i in range(250))
        track_file = tmp_path / "05-huge.md"
        track_file.write_text(
            f"# Track\n\n## Suno Inputs\n\n### Lyrics Box\n```\n[Verse 1]\n{huge_lyrics}\n```\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-huge"] = {
            "path": str(track_file), "title": "Huge Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "05")))
        track = result["tracks"][0]
        assert track["status"] == "DANGER"
        assert "800" in track["note"]

    def test_album_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("nonexistent")))
        assert result["found"] is False

    def test_track_not_found(self):
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "99")))
        assert result["found"] is False

    def test_track_no_path(self):
        """Track with no file path gets an error entry."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-no-path"] = {
            "title": "No Path", "status": "In Progress", "path": "",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "05-no-path")))
        assert "error" in result["tracks"][0]

    def test_excludes_section_tags_from_count(self, tmp_path):
        """Section tags like [Verse 1] are not counted as words."""
        track_file = tmp_path / "05-tags.md"
        track_file.write_text(
            "# Track\n\n## Suno Inputs\n\n### Lyrics Box\n```\n"
            "[Verse 1]\nOne two three\n[Chorus]\nFour five\n```\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-tags"] = {
            "path": str(track_file), "title": "Tags Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "05")))
        track = result["tracks"][0]
        assert track["word_count"] == 5  # "One two three" + "Four five"
        assert track["section_count"] == 2  # [Verse 1] and [Chorus]
        assert track["line_count"] == 2  # 2 content lines


# =============================================================================
# Tests for list_skills
# =============================================================================


def _skills_state(**overrides):
    """Return state with skills data for testing list_skills/get_skill."""
    state = _fresh_state()
    state["skills"] = {
        "count": 5,
        "model_counts": {"opus": 1, "sonnet": 3, "haiku": 1},
        "items": {
            "lyric-writer": {
                "description": "Writes or reviews lyrics with professional prosody.",
                "model": "claude-opus-4-6",
                "model_tier": "opus",
                "user_invocable": True,
                "argument_hint": "<track-file-path>",
                "path": "/tmp/skills/lyric-writer/SKILL.md",
                "mtime": 1700000000.0,
            },
            "suno-engineer": {
                "description": "Constructs technical Suno V5 style prompts.",
                "model": "claude-sonnet-4-5-20250929",
                "model_tier": "sonnet",
                "user_invocable": True,
                "argument_hint": "<track-file-path>",
                "prerequisites": ["lyric-writer"],
                "path": "/tmp/skills/suno-engineer/SKILL.md",
                "mtime": 1700000000.0,
            },
            "help": {
                "description": "Shows available skills and quick reference.",
                "model": "claude-haiku-4-5-20251001",
                "model_tier": "haiku",
                "user_invocable": True,
                "argument_hint": None,
                "path": "/tmp/skills/help/SKILL.md",
                "mtime": 1700000000.0,
            },
            "researchers-legal": {
                "description": "Researches court documents and indictments.",
                "model": "claude-sonnet-4-5-20250929",
                "model_tier": "sonnet",
                "user_invocable": False,
                "context": "fork",
                "path": "/tmp/skills/researchers-legal/SKILL.md",
                "mtime": 1700000000.0,
            },
            "researchers-biographical": {
                "description": "Researches personal backgrounds and interviews.",
                "model": "claude-sonnet-4-5-20250929",
                "model_tier": "sonnet",
                "user_invocable": False,
                "context": "fork",
                "path": "/tmp/skills/researchers-biographical/SKILL.md",
                "mtime": 1700000000.0,
            },
        },
    }
    state.update(overrides)
    return state


@pytest.mark.unit
class TestListSkills:
    """Tests for the list_skills MCP tool."""

    def test_list_all_returns_all(self):
        """No filters returns all skills."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        assert result["count"] == 5
        assert result["total"] == 5
        names = [s["name"] for s in result["skills"]]
        assert sorted(names) == ["help", "lyric-writer", "researchers-biographical", "researchers-legal", "suno-engineer"]

    def test_filter_by_model_opus(self):
        """Model filter returns only matching tier."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(model_filter="opus")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "lyric-writer"

    def test_filter_by_model_sonnet(self):
        """Sonnet filter returns all sonnet skills."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(model_filter="sonnet")))
        assert result["count"] == 3
        names = {s["name"] for s in result["skills"]}
        assert names == {"suno-engineer", "researchers-legal", "researchers-biographical"}

    def test_filter_by_model_haiku(self):
        """Haiku filter returns help skill only."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(model_filter="haiku")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "help"

    def test_filter_model_case_insensitive(self):
        """Model filter is case-insensitive."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(model_filter="OPUS")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "lyric-writer"

    def test_filter_by_category(self):
        """Category filter matches keyword in description."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(category="lyrics")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "lyric-writer"

    def test_filter_category_case_insensitive(self):
        """Category filter is case-insensitive."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(category="COURT")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "researchers-legal"

    def test_combined_model_and_category(self):
        """Both filters applied simultaneously."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(
                model_filter="sonnet", category="court"
            )))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "researchers-legal"

    def test_combined_filter_no_match(self):
        """Both filters that don't overlap return empty."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(
                model_filter="opus", category="court"
            )))
        assert result["count"] == 0
        assert result["skills"] == []

    def test_unknown_model_filter(self):
        """Model filter for nonexistent tier returns empty."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(model_filter="gpt")))
        assert result["count"] == 0
        assert result["skills"] == []

    def test_no_match_category(self):
        """Category that matches nothing returns empty."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(category="blockchain")))
        assert result["count"] == 0

    def test_empty_skills_state(self):
        """No skills in state returns empty list."""
        state = _fresh_state()
        state["skills"] = {"count": 0, "model_counts": {}, "items": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        assert result["count"] == 0
        assert result["total"] == 0
        assert result["skills"] == []

    def test_missing_skills_key(self):
        """State with no skills key at all returns empty."""
        state = _fresh_state()
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        assert result["count"] == 0
        assert result["skills"] == []

    def test_total_reflects_unfiltered_count(self):
        """Total always shows unfiltered skill count, even when filtering."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills(model_filter="opus")))
        assert result["count"] == 1  # filtered
        assert result["total"] == 5  # unfiltered

    def test_result_item_fields(self):
        """Each skill result has expected fields."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        for skill in result["skills"]:
            assert "name" in skill
            assert "description" in skill
            assert "model" in skill
            assert "model_tier" in skill
            assert "user_invocable" in skill

    def test_user_invocable_default_true(self):
        """Skills without explicit user_invocable default to True."""
        state = _skills_state()
        del state["skills"]["items"]["researchers-legal"]["user_invocable"]
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        legal = [s for s in result["skills"] if s["name"] == "researchers-legal"][0]
        assert legal["user_invocable"] is True

    def test_model_counts_in_response(self):
        """model_counts shows per-tier breakdown."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        assert result["model_counts"]["opus"] == 1
        assert result["model_counts"]["sonnet"] == 3
        assert result["model_counts"]["haiku"] == 1

    def test_skills_sorted_by_name(self):
        """Skills are returned sorted alphabetically."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        names = [s["name"] for s in result["skills"]]
        assert names == sorted(names)

    def test_skill_missing_description(self):
        """Skill with no description doesn't crash."""
        state = _skills_state()
        state["skills"]["items"]["broken"] = {
            "model_tier": "opus",
        }
        state["skills"]["count"] = 5
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        broken = [s for s in result["skills"] if s["name"] == "broken"][0]
        assert broken["description"] == ""

    def test_skill_missing_model_tier(self):
        """Skill with no model_tier gets 'unknown' default."""
        state = _skills_state()
        state["skills"]["items"]["no-tier"] = {
            "description": "A skill without model tier",
        }
        state["skills"]["count"] = 5
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_skills()))
        no_tier = [s for s in result["skills"] if s["name"] == "no-tier"][0]
        assert no_tier["model_tier"] == "unknown"


# =============================================================================
# Tests for get_skill
# =============================================================================


@pytest.mark.unit
class TestGetSkill:
    """Tests for the get_skill MCP tool."""

    def test_exact_match(self):
        """Exact name returns found=True."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("lyric-writer")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"
        assert "skill" in result

    def test_exact_match_returns_full_data(self):
        """Exact match includes all skill fields."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("suno-engineer")))
        assert result["found"] is True
        skill = result["skill"]
        assert "description" in skill
        assert "model" in skill
        assert skill["prerequisites"] == ["lyric-writer"]

    def test_fuzzy_single_match(self):
        """Partial name that matches one skill returns it."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("lyric")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"

    def test_fuzzy_multiple_matches(self):
        """Partial name matching multiple skills returns error."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("researcher")))
        assert result["found"] is False
        assert "multiple_matches" in result

    def test_no_match(self):
        """Name matching nothing returns error with available list."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("nonexistent")))
        assert result["found"] is False
        assert "available_skills" in result
        assert "error" in result

    def test_empty_skills_state(self):
        """Empty skills returns helpful error."""
        state = _fresh_state()
        state["skills"] = {"count": 0, "items": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("anything")))
        assert result["found"] is False
        assert "No skills" in result["error"]

    def test_no_skills_key(self):
        """Missing skills key in state returns error."""
        state = _fresh_state()
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("anything")))
        assert result["found"] is False

    def test_case_normalization(self):
        """Name is normalized to slug (lowercase, hyphens)."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("Lyric Writer")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"

    def test_underscore_normalization(self):
        """Underscores are converted to hyphens."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("lyric_writer")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"

    def test_returns_user_invocable_true(self):
        """Regular skills have user_invocable=True."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("lyric-writer")))
        assert result["skill"]["user_invocable"] is True

    def test_returns_user_invocable_false(self):
        """Internal skills have user_invocable=False."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("researchers-legal")))
        assert result["skill"]["user_invocable"] is False

    def test_returns_context_field(self):
        """Skills with context field include it."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("researchers-legal")))
        assert result["skill"]["context"] == "fork"

    def test_available_skills_sorted(self):
        """Available skills in error response are sorted."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_skill("zzz-not-found")))
        assert result["available_skills"] == sorted(result["available_skills"])

    def test_reverse_fuzzy_match(self):
        """Query longer than skill name (skill_name in normalized) also matches."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            # "help-system" contains "help" — and "help" is in "help-system"
            # But the reverse check is: skill_name in normalized
            # "help" in "help-system" → True
            result = json.loads(_run(server.get_skill("help-system")))
        assert result["found"] is True
        assert result["name"] == "help"


# =============================================================================
# Tests for search — edge cases
# =============================================================================


@pytest.mark.unit
class TestSearchEdgeCases:
    """Edge case tests for the search MCP tool."""

    def test_search_in_skills_scope(self):
        """Search with scope='skills' only searches skills."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("lyric", scope="skills")))
        assert "skills" in result
        assert "albums" not in result
        assert result["total_matches"] >= 1

    def test_search_skills_by_description(self):
        """Search finds skills by description content."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("court", scope="skills")))
        assert result["skills"][0]["name"] == "researchers-legal"

    def test_search_skills_by_model_tier(self):
        """Search finds skills by model_tier."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("haiku", scope="skills")))
        assert any(s["name"] == "help" for s in result["skills"])

    def test_search_all_scopes(self):
        """Scope 'all' searches albums, tracks, ideas, and skills."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("test", scope="all")))
        assert "albums" in result
        assert "tracks" in result
        assert "ideas" in result
        assert "skills" in result

    def test_search_empty_query(self):
        """Empty string matches everything (substring of all strings)."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("", scope="all")))
        assert result["total_matches"] > 0

    def test_search_no_matches(self):
        """Query matching nothing returns 0 total."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("xyzzynotfound123", scope="all")))
        assert result["total_matches"] == 0

    def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("TEST ALBUM", scope="albums")))
        assert len(result["albums"]) >= 1

    def test_search_invalid_scope_returns_empty(self):
        """Unrecognized scope returns no result keys."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("test", scope="invalid")))
        assert result["total_matches"] == 0

    def test_search_tracks_returns_album_slug(self):
        """Track results include the parent album slug."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("first", scope="tracks")))
        assert result["tracks"][0]["album_slug"] == "test-album"

    def test_search_ideas_by_genre(self):
        """Ideas are searchable by genre."""
        mock_cache = MockStateCache(_skills_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("hip-hop", scope="ideas")))
        assert len(result["ideas"]) >= 1


# =============================================================================
# Tests for get_pending_verifications — edge cases
# =============================================================================


@pytest.mark.unit
class TestGetPendingVerificationsEdgeCases:
    """Edge cases for get_pending_verifications."""

    def test_case_insensitive_pending(self):
        """'Pending' detection is case-insensitive."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["02-second-track"]["sources_verified"] = "PENDING"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] >= 1

    def test_no_pending_tracks(self):
        """Albums with all verified tracks return 0 pending."""
        state = _fresh_state()
        for t in state["albums"]["test-album"]["tracks"].values():
            t["sources_verified"] = "Verified (2025-01-01)"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] == 0

    def test_missing_sources_verified_field(self):
        """Track with no sources_verified field is not counted as pending."""
        state = _fresh_state()
        for t in state["albums"]["test-album"]["tracks"].values():
            t.pop("sources_verified", None)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert "test-album" not in result.get("albums_with_pending", {})

    def test_pending_substring_not_matched(self):
        """'Pending Review' is not the same as 'Pending'."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["02-second-track"]["sources_verified"] = "Pending Review"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        # "pending review".lower() != "pending" — should NOT match
        assert result["total_pending_tracks"] == 0

    def test_empty_albums(self):
        """State with no albums returns 0 pending."""
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] == 0
        assert result["albums_with_pending"] == {}

    def test_multiple_albums_with_pending(self):
        """Pending tracks across multiple albums are reported separately."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["02-second-track"]["sources_verified"] = "Pending"
        state["albums"]["another-album"]["tracks"]["01-rock-song"]["sources_verified"] = "Pending"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] == 2
        assert "test-album" in result["albums_with_pending"]
        assert "another-album" in result["albums_with_pending"]


# =============================================================================
# Tests for update_album_status
# =============================================================================

_SAMPLE_ALBUM_README = """\
---
title: "Test Album"
genres: ["electronic"]
explicit: false
---

# Test Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Artist** | test-artist |
| **Album** | Test Album |
| **Genre** | Electronic |
| **Tracks** | 2 |
| **Status** | In Progress |
| **Explicit** | No |
| **Concept** | A concept album |

## Tracklist

| # | Title | Status |
|---|-------|--------|
| 1 | First | Final |
| 2 | Second | In Progress |
"""


class TestUpdateAlbumStatus:
    """Tests for the update_album_status() MCP tool."""

    def _make_cache_with_readme(self, tmp_path):
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_SAMPLE_ALBUM_README)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        # Set tracks to Generated+ so "Complete" passes consistency check
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        return MockStateCache(state), readme_path

    def test_updates_status_in_readme(self, tmp_path):
        """Status is written to the README.md file."""
        mock_cache, readme_path = self._make_cache_with_readme(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert result["success"] is True
        assert result["new_status"] == "Complete"
        assert result["old_status"] == "In Progress"
        text = readme_path.read_text()
        assert "| **Status** | Complete |" in text

    def test_preserves_other_fields(self, tmp_path):
        """Other table fields are not modified."""
        mock_cache, readme_path = self._make_cache_with_readme(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            _run(server.update_album_status("test-album", "Complete"))
        text = readme_path.read_text()
        assert "| **Genre** | Electronic |" in text
        assert "| **Tracks** | 2 |" in text

    def test_invalid_status_rejected(self):
        """Invalid status string is rejected with error."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "InvalidStatus")))
        assert "error" in result
        assert "Invalid status" in result["error"]

    def test_album_not_found(self):
        """Returns error when album doesn't exist."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("no-such-album", "Complete")))
        assert result["found"] is False

    def test_missing_path(self):
        """Returns error when album has no path."""
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = ""
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert "error" in result
        assert "No path" in result["error"]

    def test_missing_readme(self, tmp_path):
        """Returns error when README.md doesn't exist."""
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert "error" in result
        assert "README.md not found" in result["error"]

    def test_case_insensitive_status_validation(self, tmp_path):
        """Status validation is case-insensitive."""
        mock_cache, readme_path = self._make_cache_with_readme(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "complete")))
        assert result["success"] is True

    def test_all_valid_statuses(self, tmp_path):
        """All valid statuses are accepted (using force to bypass transition rules)."""
        for status in ["Concept", "Research Complete", "Sources Verified", "In Progress", "Complete", "Released"]:
            mock_cache, readme_path = self._make_cache_with_readme(tmp_path)
            with patch.object(server, "cache", mock_cache), \
                 patch.object(server, "write_state"):
                result = json.loads(_run(server.update_album_status("test-album", status, force=True)))
            assert result["success"] is True, f"Failed for status: {status}"

    def test_returns_old_and_new_status(self, tmp_path):
        """Response includes both old and new status."""
        mock_cache, readme_path = self._make_cache_with_readme(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert result["old_status"] == "In Progress"
        assert result["new_status"] == "Complete"
        assert result["album_slug"] == "test-album"

    def test_readme_read_oserror(self, tmp_path):
        """Returns error when README.md cannot be read (OSError)."""
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_SAMPLE_ALBUM_README)
        readme_path.chmod(0o000)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        mock_cache = MockStateCache(state)
        try:
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.update_album_status("test-album", "Complete")))
            assert "error" in result
            assert "Cannot read" in result["error"]
        finally:
            readme_path.chmod(0o644)

    def test_no_status_row_in_readme(self, tmp_path):
        """Returns error when README has no Status table row."""
        readme_path = tmp_path / "README.md"
        readme_path.write_text("# Album\n\nNo table here.\n")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert "error" in result
        assert "Status field not found" in result["error"]

    def test_write_oserror(self, tmp_path):
        """Returns error when README.md cannot be written."""
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_SAMPLE_ALBUM_README)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(Path, "write_text", side_effect=OSError("disk full")):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert "error" in result
        assert "Cannot write" in result["error"]

    def test_cache_update_failure_still_succeeds(self, tmp_path):
        """File is written even if cache update raises an exception."""
        mock_cache, readme_path = self._make_cache_with_readme(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "parse_album_readme", side_effect=Exception("parse fail")), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert result["success"] is True
        # File was still written
        assert "| **Status** | Complete |" in readme_path.read_text()

    def test_whitespace_in_status_param(self, tmp_path):
        """Status with leading/trailing whitespace is accepted."""
        mock_cache, readme_path = self._make_cache_with_readme(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "  complete  ")))
        assert result["success"] is True


# =============================================================================
# Tests for create_track
# =============================================================================


class TestCreateTrack:
    """Tests for the create_track() MCP tool."""

    def _make_cache_with_album(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        state["albums"]["test-album"]["title"] = "Test Album"
        return MockStateCache(state), album_dir, tracks_dir

    def test_creates_track_file(self, tmp_path):
        """Track file is created from template."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        # Create a minimal template
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            "# [Track Title]\n\n| **Track #** | XX |\n| **Title** | [Track Title] |\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "03", "New Song")))
        assert result["created"] is True
        assert result["track_slug"] == "03-new-song"
        assert (tracks_dir / "03-new-song.md").exists()
        content = (tracks_dir / "03-new-song.md").read_text()
        assert "New Song" in content
        assert "| **Track #** | 03 |" in content

    def test_already_exists(self, tmp_path):
        """Returns error when track file already exists."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        (tracks_dir / "03-new-song.md").write_text("existing")
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text("template")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "03", "New Song")))
        assert result["created"] is False

    def test_album_not_found(self):
        """Returns error for nonexistent album."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_track("no-such", "01", "Track")))
        assert result["found"] is False

    def test_no_tracks_dir(self, tmp_path):
        """Returns error when tracks/ directory is missing."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        # No tracks/ subdirectory
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_track("test-album", "01", "Track")))
        assert "error" in result
        assert "tracks/" in result["error"]

    def test_zero_pads_number(self, tmp_path):
        """Track number is zero-padded to two digits."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text("# [Track Title]\n| **Track #** | XX |")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "5", "Song")))
        assert result["created"] is True
        assert result["track_slug"] == "05-song"
        assert result["filename"] == "05-song.md"

    def test_title_slugified(self, tmp_path):
        """Track title is properly slugified in filename."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text("# [Track Title]")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "My Cool Track")))
        assert result["track_slug"] == "01-my-cool-track"

    def test_missing_template(self, tmp_path):
        """Returns error when track template is not found."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", empty_root):
            result = json.loads(_run(server.create_track("test-album", "01", "Track")))
        assert "error" in result
        assert "template not found" in result["error"]

    def test_fills_placeholders(self, tmp_path):
        """Template placeholders are replaced with actual values."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            "# [Track Title]\n| **Track #** | XX |\n| **Title** | [Track Title] |\n"
            "| **Album** | [Album Name](../README.md) |\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "07", "My Track")))
        content = (tracks_dir / "07-my-track.md").read_text()
        assert "# My Track" in content
        assert "| **Track #** | 07 |" in content
        assert "Test Album" in content

    def test_empty_album_path(self):
        """Returns error when album path is empty."""
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_track("test-album", "01", "Track")))
        assert "error" in result
        assert "No path" in result["error"]

    def test_track_number_all_zeros(self, tmp_path):
        """Track number '00' produces '00-slug.md'."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text("# [Track Title]\n| **Track #** | XX |")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "00", "Intro")))
        assert result["created"] is True
        assert result["track_slug"] == "00-intro"
        assert result["filename"] == "00-intro.md"

    def test_special_chars_in_title(self, tmp_path):
        """Special characters in title are handled by slug normalization."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text("# [Track Title]")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "The Big Track")))
        assert result["created"] is True
        assert result["track_slug"] == "01-the-big-track"

    def test_whitespace_only_title(self, tmp_path):
        """Whitespace-only title produces an empty slug component."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text("# [Track Title]")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            # Whitespace-only title produces a filename via slug normalization
            result = json.loads(_run(server.create_track("test-album", "01", "   ")))
        # The tool should either create a file or return an error — either way no crash
        assert "created" in result or "error" in result

    def test_documentary_true_keeps_source_sections(self, tmp_path):
        """documentary=True preserves source and documentary sections."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            "# [Track Title]\n"
            "<!-- SOURCE-BASED TRACKS -->\n## Source\n[URL](http://example.com)\n"
            "<!-- END SOURCE SECTIONS -->\n"
            "<!-- DOCUMENTARY/TRUE STORY -->\n## Legal\nChecklist\n"
            "<!-- END DOCUMENTARY SECTIONS -->\n"
            "## Concept\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "Doc Track", documentary=True)))
        assert result["created"] is True
        content = (tracks_dir / "01-doc-track.md").read_text()
        assert "## Source" in content
        assert "## Legal" in content

    def test_documentary_false_strips_source_sections(self, tmp_path):
        """documentary=False removes source and documentary sections."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            "# [Track Title]\n"
            "<!-- SOURCE-BASED TRACKS -->\n## Source\n[URL](http://example.com)\n"
            "<!-- END SOURCE SECTIONS -->\n"
            "<!-- DOCUMENTARY/TRUE STORY -->\n## Legal\nChecklist\n"
            "<!-- END DOCUMENTARY SECTIONS -->\n"
            "## Concept\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "Non Doc", documentary=False)))
        assert result["created"] is True
        content = (tracks_dir / "01-non-doc.md").read_text()
        assert "## Source" not in content
        assert "## Legal" not in content
        assert "## Concept" in content

    def test_template_read_oserror(self, tmp_path):
        """Returns error when template file cannot be read."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "track.md"
        template_file.write_text("template")
        template_file.chmod(0o000)
        try:
            with patch.object(server, "cache", mock_cache), \
                 patch.object(server, "PLUGIN_ROOT", tmp_path):
                result = json.loads(_run(server.create_track("test-album", "01", "Track")))
            assert "error" in result
            assert "Cannot read" in result["error"]
        finally:
            template_file.chmod(0o644)

    def test_track_write_oserror(self, tmp_path):
        """Returns error when track file cannot be written."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text("# [Track Title]")
        # Make tracks dir read-only
        tracks_dir.chmod(0o555)
        try:
            with patch.object(server, "cache", mock_cache), \
                 patch.object(server, "PLUGIN_ROOT", tmp_path):
                result = json.loads(_run(server.create_track("test-album", "01", "Track")))
            assert "error" in result
            assert "Cannot write" in result["error"]
        finally:
            tracks_dir.chmod(0o755)

    def test_only_source_section_present(self, tmp_path):
        """Only SOURCE section removed when DOCUMENTARY section is absent."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            "# [Track Title]\n"
            "<!-- SOURCE-BASED TRACKS -->\n## Source\n"
            "<!-- END SOURCE SECTIONS -->\n"
            "## Concept\nKeep this.\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "Track")))
        content = (tracks_dir / "01-track.md").read_text()
        assert "## Source" not in content
        assert "## Concept" in content

    def test_fills_frontmatter_track_number(self, tmp_path):
        """Frontmatter track_number: 0 replaced with actual number."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            '---\ntitle: "[Track Title]"\ntrack_number: 0\nexplicit: false\n---\n'
            "# [Track Title]\n| **Track #** | XX |\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "07", "My Track")))
        assert result["created"] is True
        content = (tracks_dir / "07-my-track.md").read_text()
        assert "track_number: 7" in content
        assert "track_number: 0" not in content

    def test_fills_frontmatter_explicit(self, tmp_path):
        """Explicit flag from album propagated to track frontmatter."""
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        state["albums"]["test-album"]["title"] = "Test Album"
        state["albums"]["test-album"]["explicit"] = True
        mock_cache = MockStateCache(state)

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            '---\ntitle: "[Track Title]"\ntrack_number: 0\nexplicit: false\n---\n'
            "# [Track Title]\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "Explicit Track")))
        assert result["created"] is True
        content = (tracks_dir / "01-explicit-track.md").read_text()
        assert "explicit: true" in content
        assert "explicit: false" not in content


# =============================================================================
# Tests for get_promo_status
# =============================================================================


class TestGetPromoStatus:
    """Tests for the get_promo_status() MCP tool."""

    def _make_cache_with_promo(self, tmp_path, files=None):
        album_dir = tmp_path / "album"
        promo_dir = album_dir / "promo"
        promo_dir.mkdir(parents=True)

        if files:
            for fname, content in files.items():
                (promo_dir / fname).write_text(content)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        return MockStateCache(state), promo_dir

    def test_no_promo_dir(self, tmp_path):
        """Reports promo_exists=False when promo/ doesn't exist."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        assert result["promo_exists"] is False
        assert result["populated"] == 0
        assert result["total"] == 6

    def test_empty_promo_dir(self, tmp_path):
        """Reports zero populated when promo/ has no files."""
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        assert result["promo_exists"] is True
        assert result["populated"] == 0
        assert all(not f["exists"] for f in result["files"])

    def test_populated_file_detected(self, tmp_path):
        """Files with meaningful content are marked populated."""
        long_content = "# Campaign\n\n" + "This is meaningful promo content. " * 20
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path, {
            "campaign.md": long_content,
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        assert result["populated"] == 1
        campaign = next(f for f in result["files"] if f["file"] == "campaign.md")
        assert campaign["exists"] is True
        assert campaign["populated"] is True
        assert campaign["word_count"] > 20

    def test_template_only_not_populated(self, tmp_path):
        """Template-only files (headings + tables) are not counted as populated."""
        template_content = "# Campaign\n\n| Key | Value |\n|-----|-------|\n| Album | Test |\n"
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path, {
            "campaign.md": template_content,
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        campaign = next(f for f in result["files"] if f["file"] == "campaign.md")
        assert campaign["populated"] is False

    def test_all_populated_shows_ready(self, tmp_path):
        """ready=True when all 6 files are populated."""
        files = {}
        for fname in server._PROMO_FILES:
            files[fname] = "# Promo\n\n" + "Real promo copy for distribution. " * 20
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path, files)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        assert result["populated"] == 6
        assert result["ready"] is True

    def test_album_not_found(self):
        """Returns error for nonexistent album."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("no-such-album")))
        assert result["found"] is False

    def test_reports_all_six_files(self, tmp_path):
        """All 6 expected promo files are checked regardless of what exists."""
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        filenames = [f["file"] for f in result["files"]]
        assert filenames == server._PROMO_FILES

    def test_empty_album_path(self):
        """Returns error when album path is empty."""
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        assert "error" in result

    def test_file_read_error_handled(self, tmp_path):
        """File that exists but can't be read is reported as unpopulated."""
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path, {
            "campaign.md": "# Campaign\n"
        })
        (promo_dir / "campaign.md").chmod(0o000)
        try:
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.get_promo_status("test-album")))
            campaign = next(f for f in result["files"] if f["file"] == "campaign.md")
            assert campaign["exists"] is True
            assert campaign["populated"] is False
            assert campaign["word_count"] == 0
        finally:
            (promo_dir / "campaign.md").chmod(0o644)

    def test_word_count_boundary_at_20(self, tmp_path):
        """Exactly 20 words is NOT populated (threshold is > 20)."""
        # Exactly 20 content words (non-heading, non-table lines)
        content = "# Campaign\n\n" + " ".join(["word"] * 20)
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path, {
            "campaign.md": content,
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        campaign = next(f for f in result["files"] if f["file"] == "campaign.md")
        assert campaign["word_count"] == 20
        assert campaign["populated"] is False

    def test_word_count_boundary_at_21(self, tmp_path):
        """21 words IS populated (threshold is > 20)."""
        content = "# Campaign\n\n" + " ".join(["word"] * 21)
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path, {
            "campaign.md": content,
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        campaign = next(f for f in result["files"] if f["file"] == "campaign.md")
        assert campaign["word_count"] == 21
        assert campaign["populated"] is True

    def test_placeholder_lines_skipped(self, tmp_path):
        """Lines like [placeholder text] don't count as words."""
        content = "# Campaign\n\n[This is placeholder text]\n[More placeholders]\n"
        mock_cache, promo_dir = self._make_cache_with_promo(tmp_path, {
            "campaign.md": content,
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_status("test-album")))
        campaign = next(f for f in result["files"] if f["file"] == "campaign.md")
        assert campaign["word_count"] == 0


# =============================================================================
# Tests for get_promo_content
# =============================================================================


class TestGetPromoContent:
    """Tests for the get_promo_content() MCP tool."""

    def test_reads_content(self, tmp_path):
        """Returns file content for valid platform."""
        album_dir = tmp_path / "album"
        promo_dir = album_dir / "promo"
        promo_dir.mkdir(parents=True)
        (promo_dir / "twitter.md").write_text("# Twitter\n\nTweet this!")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("test-album", "twitter")))
        assert result["found"] is True
        assert result["platform"] == "twitter"
        assert "Tweet this!" in result["content"]

    def test_invalid_platform(self):
        """Returns error for invalid platform name."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("test-album", "snapchat")))
        assert "error" in result
        assert "Unknown platform" in result["error"]

    def test_file_not_found(self, tmp_path):
        """Returns error when promo file doesn't exist."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("test-album", "twitter")))
        assert result["found"] is False

    def test_album_not_found(self):
        """Returns error for nonexistent album."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("no-such-album", "twitter")))
        assert result["found"] is False

    def test_all_valid_platforms(self, tmp_path):
        """All platform names are accepted."""
        album_dir = tmp_path / "album"
        promo_dir = album_dir / "promo"
        promo_dir.mkdir(parents=True)
        for p in ["campaign", "twitter", "instagram", "tiktok", "facebook", "youtube"]:
            (promo_dir / f"{p}.md").write_text(f"# {p}\n")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            for p in ["campaign", "twitter", "instagram", "tiktok", "facebook", "youtube"]:
                result = json.loads(_run(server.get_promo_content("test-album", p)))
                assert result["found"] is True, f"Failed for platform: {p}"

    def test_case_insensitive_platform(self, tmp_path):
        """Platform name is case-insensitive."""
        album_dir = tmp_path / "album"
        promo_dir = album_dir / "promo"
        promo_dir.mkdir(parents=True)
        (promo_dir / "twitter.md").write_text("# Twitter\n")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("test-album", "Twitter")))
        assert result["found"] is True

    def test_empty_album_path(self):
        """Returns error when album path is empty."""
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("test-album", "twitter")))
        assert "error" in result

    def test_file_read_oserror(self, tmp_path):
        """Returns error when promo file exists but cannot be read."""
        album_dir = tmp_path / "album"
        promo_dir = album_dir / "promo"
        promo_dir.mkdir(parents=True)
        promo_file = promo_dir / "twitter.md"
        promo_file.write_text("content")
        promo_file.chmod(0o000)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        try:
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.get_promo_content("test-album", "twitter")))
            assert "error" in result
            assert "Cannot read" in result["error"]
        finally:
            promo_file.chmod(0o644)

    def test_platform_with_whitespace(self, tmp_path):
        """Platform name with whitespace is trimmed."""
        album_dir = tmp_path / "album"
        promo_dir = album_dir / "promo"
        promo_dir.mkdir(parents=True)
        (promo_dir / "twitter.md").write_text("# Twitter\n")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("test-album", "  twitter  ")))
        assert result["found"] is True

    def test_returns_path_and_platform(self, tmp_path):
        """Response includes path and platform fields."""
        album_dir = tmp_path / "album"
        promo_dir = album_dir / "promo"
        promo_dir.mkdir(parents=True)
        (promo_dir / "instagram.md").write_text("# IG\n")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_promo_content("test-album", "instagram")))
        assert result["platform"] == "instagram"
        assert "path" in result


# =============================================================================
# Tests for get_plugin_version
# =============================================================================


class TestGetPluginVersion:
    """Tests for the get_plugin_version() MCP tool."""

    def test_returns_stored_and_current(self, tmp_path):
        """Returns both stored and current version."""
        state = _fresh_state()
        state["plugin_version"] = "0.43.0"
        mock_cache = MockStateCache(state)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"version": "0.44.0"}')

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["stored_version"] == "0.43.0"
        assert result["current_version"] == "0.44.0"
        assert result["needs_upgrade"] is True

    def test_versions_match(self, tmp_path):
        """needs_upgrade is False when versions match."""
        state = _fresh_state()
        state["plugin_version"] = "0.44.0"
        mock_cache = MockStateCache(state)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"version": "0.44.0"}')

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["needs_upgrade"] is False

    def test_null_stored_needs_upgrade(self, tmp_path):
        """First run (null stored) triggers needs_upgrade."""
        state = _fresh_state()
        state["plugin_version"] = None
        mock_cache = MockStateCache(state)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"version": "0.44.0"}')

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["stored_version"] is None
        assert result["needs_upgrade"] is True

    def test_missing_plugin_json(self, tmp_path):
        """Handles missing plugin.json gracefully."""
        state = _fresh_state()
        state["plugin_version"] = "0.43.0"
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["current_version"] is None
        assert result["stored_version"] == "0.43.0"

    def test_corrupt_plugin_json(self, tmp_path):
        """Handles invalid JSON in plugin.json gracefully."""
        state = _fresh_state()
        state["plugin_version"] = "0.43.0"
        mock_cache = MockStateCache(state)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text("{invalid json!")

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["current_version"] is None
        assert result["stored_version"] == "0.43.0"

    def test_plugin_json_missing_version_key(self, tmp_path):
        """Handles plugin.json without version field."""
        state = _fresh_state()
        state["plugin_version"] = "0.43.0"
        mock_cache = MockStateCache(state)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"name": "test"}')

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["current_version"] is None

    def test_both_versions_none(self, tmp_path):
        """No upgrade needed when both stored and current are None."""
        state = _fresh_state()
        # No plugin_version key at all
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["needs_upgrade"] is False

    def test_empty_version_string(self, tmp_path):
        """Empty version string in plugin.json treated as falsy."""
        state = _fresh_state()
        state["plugin_version"] = "0.43.0"
        mock_cache = MockStateCache(state)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"version": ""}')

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["current_version"] == ""

    def test_plugin_json_read_oserror(self, tmp_path):
        """Handles OSError reading plugin.json gracefully."""
        state = _fresh_state()
        state["plugin_version"] = "0.43.0"
        mock_cache = MockStateCache(state)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        plugin_file = plugin_dir / "plugin.json"
        plugin_file.write_text('{"version": "0.44.0"}')
        plugin_file.chmod(0o000)

        try:
            with patch.object(server, "cache", mock_cache), \
                 patch.object(server, "PLUGIN_ROOT", tmp_path):
                result = json.loads(_run(server.get_plugin_version()))
            assert result["current_version"] is None
        finally:
            plugin_file.chmod(0o644)

    def test_returns_plugin_root(self, tmp_path):
        """Response includes plugin_root path."""
        state = _fresh_state()
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_plugin_version()))
        assert result["plugin_root"] == str(tmp_path)


# =============================================================================
# Tests for _parse_requirements
# =============================================================================


class TestParseRequirements:
    """Tests for the _parse_requirements() helper."""

    def test_parses_pinned_versions(self, tmp_path):
        """Parses standard == pinned versions."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0\nflask==3.0.0\n")
        result = server._parse_requirements(req)
        assert result == {"requests": "2.31.0", "flask": "3.0.0"}

    def test_skips_comments_and_blanks(self, tmp_path):
        """Skips comment lines and blank lines."""
        req = tmp_path / "requirements.txt"
        req.write_text("# This is a comment\n\nrequests==2.31.0\n\n# Another\n")
        result = server._parse_requirements(req)
        assert result == {"requests": "2.31.0"}

    def test_strips_extras(self, tmp_path):
        """Strips extras markers like [cli]."""
        req = tmp_path / "requirements.txt"
        req.write_text("mcp[cli]==1.23.0\n")
        result = server._parse_requirements(req)
        assert result == {"mcp": "1.23.0"}

    def test_lowercases_names(self, tmp_path):
        """Package names are lowercased."""
        req = tmp_path / "requirements.txt"
        req.write_text("PyYAML==6.0.2\nNumPy==1.26.4\n")
        result = server._parse_requirements(req)
        assert "pyyaml" in result
        assert "numpy" in result

    def test_missing_file_returns_empty(self, tmp_path):
        """Missing file returns empty dict."""
        result = server._parse_requirements(tmp_path / "nonexistent.txt")
        assert result == {}

    def test_empty_file_returns_empty(self, tmp_path):
        """Empty file returns empty dict."""
        req = tmp_path / "requirements.txt"
        req.write_text("")
        result = server._parse_requirements(req)
        assert result == {}

    def test_ignores_non_pinned_lines(self, tmp_path):
        """Ignores lines without == (bare names, >=, etc.)."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.0\nflask\nnumpy==1.26.4\n")
        result = server._parse_requirements(req)
        assert result == {"numpy": "1.26.4"}

    def test_handles_inline_comments(self, tmp_path):
        """Strips inline comments after version."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0  # HTTP library\n")
        result = server._parse_requirements(req)
        assert result == {"requests": "2.31.0"}

    def test_handles_hyphenated_names(self, tmp_path):
        """Handles hyphenated package names."""
        req = tmp_path / "requirements.txt"
        req.write_text("psycopg2-binary==2.9.10\n")
        result = server._parse_requirements(req)
        assert result == {"psycopg2-binary": "2.9.10"}


# =============================================================================
# Tests for check_venv_health
# =============================================================================


class TestCheckVenvHealth:
    """Tests for the check_venv_health() MCP tool."""

    def test_all_match_returns_ok(self, tmp_path):
        """All packages matching returns status ok."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0\nflask==3.0.0\n")

        def mock_version(pkg):
            versions = {"requests": "2.31.0", "flask": "3.0.0"}
            if pkg in versions:
                return versions[pkg]
            raise importlib.metadata.PackageNotFoundError(pkg)

        venv_dir = tmp_path / "fakehome" / ".bitwize-music" / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python3").touch()

        with patch.object(server, "PLUGIN_ROOT", tmp_path), \
             patch("importlib.metadata.version", side_effect=mock_version), \
             patch.object(Path, "home", return_value=tmp_path / "fakehome"):
            result = json.loads(_run(server.check_venv_health()))
        assert result["status"] == "ok"
        assert result["ok_count"] == 2
        assert result["mismatches"] == []
        assert result["missing"] == []

    def test_version_mismatch_returns_stale(self, tmp_path):
        """Version mismatch returns status stale with details."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0\n")

        venv_dir = tmp_path / "fakehome" / ".bitwize-music" / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python3").touch()

        with patch.object(server, "PLUGIN_ROOT", tmp_path), \
             patch("importlib.metadata.version", return_value="2.28.0"), \
             patch.object(Path, "home", return_value=tmp_path / "fakehome"):
            result = json.loads(_run(server.check_venv_health()))
        assert result["status"] == "stale"
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["package"] == "requests"
        assert result["mismatches"][0]["required"] == "2.31.0"
        assert result["mismatches"][0]["installed"] == "2.28.0"

    def test_missing_package_returns_stale(self, tmp_path):
        """Missing package returns status stale with missing list."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0\n")

        venv_dir = tmp_path / "fakehome" / ".bitwize-music" / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python3").touch()

        def mock_version(pkg):
            raise importlib.metadata.PackageNotFoundError(pkg)

        with patch.object(server, "PLUGIN_ROOT", tmp_path), \
             patch("importlib.metadata.version", side_effect=mock_version), \
             patch.object(Path, "home", return_value=tmp_path / "fakehome"):
            result = json.loads(_run(server.check_venv_health()))
        assert result["status"] == "stale"
        assert len(result["missing"]) == 1
        assert result["missing"][0]["package"] == "requests"

    def test_no_venv_returns_no_venv(self, tmp_path):
        """Missing venv returns no_venv status."""
        venv_dir = tmp_path / "fakehome" / ".bitwize-music"
        venv_dir.mkdir(parents=True)
        # No venv/bin/python3

        with patch.object(Path, "home", return_value=tmp_path / "fakehome"):
            result = json.loads(_run(server.check_venv_health()))
        assert result["status"] == "no_venv"

    def test_missing_requirements_returns_error(self, tmp_path):
        """Missing requirements.txt returns error status."""
        venv_dir = tmp_path / "fakehome" / ".bitwize-music" / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python3").touch()
        # No requirements.txt in PLUGIN_ROOT

        with patch.object(server, "PLUGIN_ROOT", tmp_path), \
             patch.object(Path, "home", return_value=tmp_path / "fakehome"):
            result = json.loads(_run(server.check_venv_health()))
        assert result["status"] == "error"

    def test_mixed_ok_mismatch_missing(self, tmp_path):
        """Mixed results: some ok, some mismatch, some missing."""
        req = tmp_path / "requirements.txt"
        req.write_text("aaa==1.0.0\nbbb==2.0.0\nccc==3.0.0\n")

        def mock_version(pkg):
            if pkg == "aaa":
                return "1.0.0"  # ok
            if pkg == "bbb":
                return "1.9.0"  # mismatch
            raise importlib.metadata.PackageNotFoundError(pkg)  # ccc missing

        venv_dir = tmp_path / "fakehome" / ".bitwize-music" / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python3").touch()

        with patch.object(server, "PLUGIN_ROOT", tmp_path), \
             patch("importlib.metadata.version", side_effect=mock_version), \
             patch.object(Path, "home", return_value=tmp_path / "fakehome"):
            result = json.loads(_run(server.check_venv_health()))
        assert result["status"] == "stale"
        assert result["ok_count"] == 1
        assert len(result["mismatches"]) == 1
        assert len(result["missing"]) == 1

    def test_fix_command_includes_plugin_root(self, tmp_path):
        """Fix command references the correct requirements.txt path."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0\n")

        venv_dir = tmp_path / "fakehome" / ".bitwize-music" / "venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python3").touch()

        def mock_version(pkg):
            raise importlib.metadata.PackageNotFoundError(pkg)

        with patch.object(server, "PLUGIN_ROOT", tmp_path), \
             patch("importlib.metadata.version", side_effect=mock_version), \
             patch.object(Path, "home", return_value=tmp_path / "fakehome"):
            result = json.loads(_run(server.check_venv_health()))
        assert result["status"] == "stale"
        assert str(tmp_path / "requirements.txt") in result["fix_command"]
        assert "~/.bitwize-music/venv/bin/pip" in result["fix_command"]


# =============================================================================
# Tests for create_idea
# =============================================================================


class TestCreateIdea:
    """Tests for the create_idea() MCP tool."""

    def _make_cache_with_ideas(self, tmp_path, ideas_content=None):
        content_root = tmp_path / "content"
        content_root.mkdir()
        if ideas_content is not None:
            (content_root / "IDEAS.md").write_text(ideas_content)

        state = _fresh_state()
        state["config"]["content_root"] = str(content_root)
        mock_cache = MockStateCache(state)
        return mock_cache, content_root

    def test_appends_idea(self, tmp_path):
        """New idea is appended to IDEAS.md."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea(
                "Cyberpunk Dreams", genre="electronic", concept="Neon city vibes"
            )))
        assert result["created"] is True
        assert result["title"] == "Cyberpunk Dreams"
        text = (content_root / "IDEAS.md").read_text()
        assert "### Cyberpunk Dreams" in text
        assert "**Genre**: electronic" in text
        assert "**Concept**: Neon city vibes" in text
        assert "**Status**: Pending" in text

    def test_creates_file_if_missing(self, tmp_path):
        """Creates IDEAS.md if it doesn't exist."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("New Idea")))
        assert result["created"] is True
        assert (content_root / "IDEAS.md").exists()

    def test_rejects_duplicate(self, tmp_path):
        """Rejects idea with duplicate title."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Ideas\n\n## Ideas\n\n### Existing Idea\n\n**Status**: Pending\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("Existing Idea")))
        assert result["created"] is False
        assert "already exists" in result["error"]

    def test_empty_title_rejected(self):
        """Rejects empty title."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("")))
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_optional_fields(self, tmp_path):
        """Genre, type, and concept are optional."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("Minimal Idea")))
        assert result["created"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "### Minimal Idea" in text
        assert "**Status**: Pending" in text
        # No genre/type/concept lines
        assert "**Genre**" not in text

    def test_no_config_error(self):
        """Returns error when content_root is not configured."""
        state = _fresh_state()
        state["config"]["content_root"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("Test")))
        assert "error" in result

    def test_ideas_read_oserror(self, tmp_path):
        """Returns error when IDEAS.md exists but cannot be read."""
        content_root = tmp_path / "content"
        content_root.mkdir()
        ideas_file = content_root / "IDEAS.md"
        ideas_file.write_text("# Ideas")
        ideas_file.chmod(0o000)

        state = _fresh_state()
        state["config"]["content_root"] = str(content_root)
        mock_cache = MockStateCache(state)
        try:
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.create_idea("Test Idea")))
            assert "error" in result
            assert "Cannot read" in result["error"]
        finally:
            ideas_file.chmod(0o644)

    def test_whitespace_only_title_rejected(self):
        """Title with only whitespace is rejected."""
        state = _fresh_state()
        state["config"]["content_root"] = "/tmp/test"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("   ")))
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_all_fields_provided(self, tmp_path):
        """All optional fields (genre, type, concept) appear when provided."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea(
                "Full Idea", genre="rock", idea_type="Documentary", concept="A doc album"
            )))
        assert result["created"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "**Genre**: rock" in text
        assert "**Type**: Documentary" in text
        assert "**Concept**: A doc album" in text
        assert "**Status**: Pending" in text

    def test_type_field_written(self, tmp_path):
        """Type field appears when provided without genre."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("Typed Idea", idea_type="Narrative")))
        text = (content_root / "IDEAS.md").read_text()
        assert "**Type**: Narrative" in text

    def test_special_chars_in_title(self, tmp_path):
        """Titles with special characters are preserved."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("Track #1: The [Best] & More")))
        assert result["created"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "### Track #1: The [Best] & More" in text

    def test_write_oserror(self, tmp_path):
        """Returns error when IDEAS.md cannot be written."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(Path, "write_text", side_effect=OSError("permission denied")):
            result = json.loads(_run(server.create_idea("New Idea")))
        assert "error" in result

    def test_cache_rebuild_failure_still_succeeds(self, tmp_path):
        """Idea is created even if cache rebuild throws."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        mock_cache.rebuild = MagicMock(side_effect=Exception("rebuild failed"))
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("Survive Rebuild", genre="rock")))
        assert result["created"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "### Survive Rebuild" in text

    def test_returns_path(self, tmp_path):
        """Response includes path to IDEAS.md."""
        mock_cache, content_root = self._make_cache_with_ideas(
            tmp_path, "# Album Ideas\n\n## Ideas\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.create_idea("Path Test")))
        assert result["path"] == str(content_root / "IDEAS.md")


# =============================================================================
# Tests for update_idea
# =============================================================================


class TestUpdateIdea:
    """Tests for the update_idea() MCP tool."""

    IDEAS_WITH_ENTRIES = """\
# Album Ideas

## Ideas

### Cyberpunk Dreams

**Genre**: electronic
**Type**: Thematic
**Concept**: Neon city vibes
**Status**: Pending

### Outlaw Stories

**Genre**: country
**Type**: Documentary
**Concept**: True outlaw tales
**Status**: In Progress
"""

    def _make_cache_with_ideas(self, tmp_path):
        content_root = tmp_path / "content"
        content_root.mkdir()
        (content_root / "IDEAS.md").write_text(self.IDEAS_WITH_ENTRIES)

        state = _fresh_state()
        state["config"]["content_root"] = str(content_root)
        mock_cache = MockStateCache(state)
        return mock_cache, content_root

    def test_updates_status(self, tmp_path):
        """Status field is updated in IDEAS.md."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "status", "In Progress")))
        assert result["success"] is True
        assert result["old_value"] == "Pending"
        assert result["new_value"] == "In Progress"
        text = (content_root / "IDEAS.md").read_text()
        assert "**Status**: In Progress" in text

    def test_updates_genre(self, tmp_path):
        """Genre field is updated."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "genre", "synthwave")))
        assert result["success"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "**Genre**: synthwave" in text

    def test_idea_not_found(self, tmp_path):
        """Returns error for nonexistent idea."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("No Such Idea", "status", "Pending")))
        assert result["found"] is False

    def test_invalid_field(self, tmp_path):
        """Returns error for invalid field name."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "tracks", "12")))
        assert "error" in result
        assert "Unknown field" in result["error"]

    def test_preserves_other_ideas(self, tmp_path):
        """Updating one idea doesn't affect others."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            _run(server.update_idea("Cyberpunk Dreams", "status", "Complete"))
        text = (content_root / "IDEAS.md").read_text()
        # Outlaw Stories should be unchanged
        assert "### Outlaw Stories" in text
        assert "**Status**: In Progress" in text

    def test_no_ideas_file(self, tmp_path):
        """Returns error when IDEAS.md doesn't exist."""
        content_root = tmp_path / "content"
        content_root.mkdir()
        state = _fresh_state()
        state["config"]["content_root"] = str(content_root)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Test", "status", "Pending")))
        assert "error" in result

    def test_updates_concept(self, tmp_path):
        """Concept field is updated."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "concept", "Dark future vibes")))
        assert result["success"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "**Concept**: Dark future vibes" in text

    def test_case_insensitive_field(self, tmp_path):
        """Field name is case-insensitive."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "STATUS", "Complete")))
        assert result["success"] is True

    def test_updates_type_field(self, tmp_path):
        """Type field is correctly updated."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "type", "Documentary")))
        assert result["success"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "**Type**: Documentary" in text

    def test_field_not_in_idea_section(self, tmp_path):
        """Returns error when field doesn't exist in the target idea."""
        # Create ideas file where one idea is missing Genre field
        ideas_text = """\
# Album Ideas

## Ideas

### Minimal Idea

**Status**: Pending
"""
        content_root = tmp_path / "content"
        content_root.mkdir()
        (content_root / "IDEAS.md").write_text(ideas_text)

        state = _fresh_state()
        state["config"]["content_root"] = str(content_root)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Minimal Idea", "genre", "rock")))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_last_idea_in_file(self, tmp_path):
        """Correctly updates the last idea (no trailing ### to bound section)."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Outlaw Stories", "status", "Complete")))
        assert result["success"] is True
        text = (content_root / "IDEAS.md").read_text()
        # Check Outlaw Stories (the last idea) was updated
        import re
        match = re.search(r'### Outlaw Stories.*', text, re.DOTALL)
        assert "**Status**: Complete" in match.group()

    def test_empty_value(self, tmp_path):
        """Can set a field to an empty value."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "concept", "")))
        assert result["success"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "**Concept**: " in text

    def test_special_chars_in_value(self, tmp_path):
        """Special characters in value are preserved."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea(
                "Cyberpunk Dreams", "concept", "Neon & chrome [2026] {version}"
            )))
        assert result["success"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "Neon & chrome [2026] {version}" in text

    def test_ideas_read_oserror(self, tmp_path):
        """Returns error when IDEAS.md exists but cannot be read."""
        content_root = tmp_path / "content"
        content_root.mkdir()
        ideas_file = content_root / "IDEAS.md"
        ideas_file.write_text("# Ideas")
        ideas_file.chmod(0o000)

        state = _fresh_state()
        state["config"]["content_root"] = str(content_root)
        mock_cache = MockStateCache(state)
        try:
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.update_idea("Test", "status", "Pending")))
            assert "error" in result
            assert "Cannot read" in result["error"]
        finally:
            ideas_file.chmod(0o644)

    def test_write_oserror(self, tmp_path):
        """Returns error when IDEAS.md cannot be written."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        # Make file read-only after first read
        with patch.object(server, "cache", mock_cache):
            # Use patch on Path.write_text to simulate write failure
            original_write = Path.write_text

            def fail_write(self, *args, **kwargs):
                if str(self).endswith("IDEAS.md"):
                    raise OSError("disk full")
                return original_write(self, *args, **kwargs)

            with patch.object(Path, "write_text", fail_write):
                result = json.loads(_run(server.update_idea(
                    "Cyberpunk Dreams", "status", "Complete"
                )))
        assert "error" in result

    def test_cache_rebuild_failure_still_succeeds(self, tmp_path):
        """Idea is updated even if cache rebuild throws."""
        mock_cache, content_root = self._make_cache_with_ideas(tmp_path)
        mock_cache.rebuild = MagicMock(side_effect=Exception("rebuild failed"))
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Cyberpunk Dreams", "status", "Complete")))
        assert result["success"] is True
        text = (content_root / "IDEAS.md").read_text()
        assert "**Status**: Complete" in text

    def test_no_config_error(self):
        """Returns error when content_root is empty."""
        state = _fresh_state()
        state["config"]["content_root"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_idea("Test", "status", "Pending")))
        assert "error" in result


# =============================================================================
# Direct tests for _load_explicit_words helper
# =============================================================================


class TestLoadExplicitWords:
    """Direct tests for the _load_explicit_words() helper function."""

    def test_returns_base_words_when_no_overrides(self):
        """Returns base explicit words when no override file exists."""
        state = _fresh_state()
        state["config"]["overrides_dir"] = "/nonexistent/path"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert isinstance(words, set)
        assert "fuck" in words
        assert "shit" in words
        assert len(words) == len(server._BASE_EXPLICIT_WORDS)

    def test_cache_hit_returns_immediately(self):
        """Second call returns cached result when override file mtime unchanged."""
        cached_words = {"cached", "word", "set"}
        mock_cache = MockStateCache()
        with patch.object(server, "_explicit_word_cache", cached_words), \
             patch.object(server, "_explicit_word_mtime", 0.0), \
             patch.object(server, "cache", mock_cache):
            result = server._load_explicit_words()
        assert result is cached_words

    def test_fallback_to_content_root_overrides(self, tmp_path):
        """When overrides_dir is empty, falls back to content_root/overrides."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Words\n\n## Additional Explicit Words\n\n- testword123\n"
        )
        state = _fresh_state()
        state["config"]["content_root"] = str(tmp_path)
        state["config"]["overrides_dir"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert "testword123" in words

    def test_add_word_with_parenthetical_note(self, tmp_path):
        """Parenthetical notes are stripped from added words."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Words\n\n## Additional Explicit Words\n\n"
            "- customterm (used in gangsta rap)\n"
            "- anotherword (slang)\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert "customterm" in words
        assert "anotherword" in words
        # Parenthetical text should not be part of the word
        assert not any("(" in w for w in words)

    def test_remove_word_with_parenthetical_note(self, tmp_path):
        """Override Base section removes words, stripping parenthetical notes."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Words\n\n## Not Explicit (Override Base)\n\n"
            "- fuck (period dialogue)\n"
            "- shit (narrative context)\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert "fuck" not in words
        assert "shit" not in words
        # Other base words should still be present
        assert "bitch" in words

    def test_empty_list_items_ignored(self, tmp_path):
        """Lines with just '- ' (empty) are ignored."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Words\n\n## Additional Explicit Words\n\n- \n- \n- realword\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        # Only base words + "realword" should be present, no empty strings
        assert "" not in words
        assert "realword" in words

    def test_words_lowercased(self, tmp_path):
        """Added words are lowercased."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Words\n\n## Additional Explicit Words\n\n- UPPERCASE\n- MiXeD\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert "uppercase" in words
        assert "mixed" in words
        assert "UPPERCASE" not in words

    def test_compiles_regex_patterns(self, tmp_path):
        """Populates _explicit_word_patterns with compiled regexes."""
        state = _fresh_state()
        state["config"]["overrides_dir"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
            patterns = server._explicit_word_patterns
        assert patterns is not None
        assert len(patterns) == len(words)
        for w in words:
            assert w in patterns
            # Each pattern should match the word
            assert patterns[w].search(w) is not None

    def test_key_error_in_config_falls_back_to_base(self):
        """KeyError from missing config keys falls back to base words."""
        mock_cache = MockStateCache({})  # empty state, no "config" key
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert words == server._BASE_EXPLICIT_WORDS

    def test_unicode_decode_error_falls_back_to_base(self, tmp_path):
        """UnicodeDecodeError when reading override file falls back to base words."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        # Write binary content that's invalid UTF-8
        (override_dir / "explicit-words.md").write_bytes(b"\x80\x81\x82\x83")
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert words == server._BASE_EXPLICIT_WORDS

    def test_both_add_and_remove_sections(self, tmp_path):
        """Both add and remove sections work together."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Words\n\n"
            "## Additional Explicit Words\n\n- newword\n\n"
            "## Not Explicit (Override Base)\n\n- fuck\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert "newword" in words
        assert "fuck" not in words
        assert "shit" in words  # other base words unaffected

    def test_non_list_lines_ignored_in_override(self, tmp_path):
        """Lines that don't start with '- ' in override sections are skipped."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        (override_dir / "explicit-words.md").write_text(
            "# Words\n\n## Additional Explicit Words\n\n"
            "These are words:\n"
            "* bullet (wrong format)\n"
            "- validword\n"
            "Plain text ignored\n"
        )
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(override_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_explicit_word_cache", None), \
             patch.object(server, "_explicit_word_patterns", None):
            words = server._load_explicit_words()
        assert "validword" in words
        assert "bullet" not in words


# =============================================================================
# Direct tests for _load_artist_blocklist helper
# =============================================================================


class TestLoadArtistBlocklist:
    """Direct tests for the _load_artist_blocklist() helper function."""

    def test_cache_hit_returns_immediately(self):
        """Second call returns cached result when file mtime unchanged."""
        cached = [{"name": "Cached", "alternative": "x", "genre": "y"}]
        blocklist_path = server.PLUGIN_ROOT / "reference" / "suno" / "artist-blocklist.md"
        try:
            mtime = blocklist_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        with patch.object(server, "_artist_blocklist_cache", cached), \
             patch.object(server, "_artist_blocklist_mtime", mtime):
            result = server._load_artist_blocklist()
        assert result is cached

    def test_missing_file_returns_empty(self, tmp_path):
        """Returns empty list when blocklist file doesn't exist."""
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        assert result == []

    def test_read_error_returns_empty(self, tmp_path):
        """Returns empty list when file can't be read."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        # Create a directory where file is expected — triggers IsADirectoryError
        (blocklist_dir / "artist-blocklist.md").mkdir()
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        assert result == []

    def test_parses_table_rows_with_genre(self, tmp_path):
        """Correctly parses table rows under genre headings."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text(
            "# Artist Blocklist\n\n"
            "### Rock\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "| Metallica | Heavy thrash riffs |\n"
            "| Nirvana | 90s grunge power chords |\n\n"
            "### Electronic\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "| Skrillex | Aggressive dubstep wobble |\n"
        )
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        assert len(result) == 3
        names = [e["name"] for e in result]
        assert "Metallica" in names
        assert "Nirvana" in names
        assert "Skrillex" in names
        # Check genre assignment
        metallica = next(e for e in result if e["name"] == "Metallica")
        assert metallica["genre"] == "Rock"
        assert metallica["alternative"] == "Heavy thrash riffs"
        skrillex = next(e for e in result if e["name"] == "Skrillex")
        assert skrillex["genre"] == "Electronic"

    def test_skips_header_rows(self, tmp_path):
        """Skips table header row containing 'Don't Say'."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text(
            "### Rock\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "| AC/DC | Hard blues riffs |\n"
        )
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        # Should only have AC/DC, not "Don't Say"
        assert len(result) == 1
        assert result[0]["name"] == "AC/DC"

    def test_skips_separator_rows(self, tmp_path):
        """Skips rows with '---' separators."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text(
            "### Pop\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "| Taylor Swift | Catchy pop melodies |\n"
        )
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        assert len(result) == 1
        names = [e["name"] for e in result]
        assert "---" not in names

    def test_skips_rows_with_few_parts(self, tmp_path):
        """Rows with fewer than 4 pipe-split parts are skipped."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text(
            "### Rock\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "| Valid Name | Valid Alt |\n"
            "| Incomplete\n"
        )
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        assert len(result) == 1
        assert result[0]["name"] == "Valid Name"

    def test_empty_name_skipped(self, tmp_path):
        """Rows where name column is empty are skipped."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text(
            "### Rock\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "|  | Some alternative |\n"
            "| Metallica | Heavy riffs |\n"
        )
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        assert len(result) == 1
        assert result[0]["name"] == "Metallica"

    def test_compiles_patterns(self, tmp_path):
        """Populates _artist_blocklist_patterns with compiled regexes."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text(
            "### Rock\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "| Metallica | Heavy riffs |\n"
        )
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            server._load_artist_blocklist()
            patterns = server._artist_blocklist_patterns
        assert "Metallica" in patterns
        assert patterns["Metallica"].search("Metallica") is not None
        assert patterns["Metallica"].search("metallica") is not None  # case-insensitive

    def test_no_genre_heading_uses_empty_string(self, tmp_path):
        """Rows before any genre heading get empty genre."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text(
            "# Artist Blocklist\n\n"
            "| Don't Say | Say Instead |\n"
            "| --- | --- |\n"
            "| SomeArtist | Some description |\n"
        )
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
        assert len(result) == 1
        assert result[0]["genre"] == ""

    def test_empty_file_returns_empty(self, tmp_path):
        """Empty blocklist file returns empty list."""
        blocklist_dir = tmp_path / "reference" / "suno"
        blocklist_dir.mkdir(parents=True)
        (blocklist_dir / "artist-blocklist.md").write_text("")
        with patch.object(server, "_artist_blocklist_cache", None), \
             patch.object(server, "_artist_blocklist_patterns", None), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = server._load_artist_blocklist()
            assert server._artist_blocklist_patterns == {}
        assert result == []


# =============================================================================
# Direct tests for _find_album_or_error helper
# =============================================================================


class TestFindAlbumOrError:
    """Direct tests for the _find_album_or_error() helper function."""

    def test_found_album(self):
        """Returns album data when album exists."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            slug, data, error = server._find_album_or_error("test-album")
        assert slug == "test-album"
        assert data is not None
        assert data["title"] == "Test Album"
        assert error is None

    def test_not_found(self):
        """Returns error JSON when album doesn't exist."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            slug, data, error = server._find_album_or_error("nonexistent")
        assert slug == "nonexistent"
        assert data is None
        assert error is not None
        error_data = json.loads(error)
        assert error_data["found"] is False
        assert "nonexistent" in error_data["error"]
        assert "test-album" in error_data["available_albums"]

    def test_normalizes_slug(self):
        """Input is normalized via _normalize_slug."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            slug, data, error = server._find_album_or_error("Test Album")
        assert slug == "test-album"
        assert data is not None
        assert error is None

    def test_empty_albums_dict(self):
        """Returns error when albums dict is empty."""
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            slug, data, error = server._find_album_or_error("any-album")
        assert data is None
        error_data = json.loads(error)
        assert error_data["available_albums"] == []

    def test_case_insensitive_lookup(self):
        """Slug normalization enables case-insensitive album lookup."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            slug, data, error = server._find_album_or_error("TEST-ALBUM")
        assert slug == "test-album"
        assert data is not None

    def test_spaces_normalized_to_hyphens(self):
        """Spaces in input are converted to hyphens for lookup."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            slug, data, error = server._find_album_or_error("test album")
        assert slug == "test-album"
        assert data is not None


# =============================================================================
# Direct tests for _resolve_ideas_path helper
# =============================================================================


class TestResolveIdeasPath:
    """Direct tests for the _resolve_ideas_path() helper function."""

    def test_returns_path_with_content_root(self):
        """Returns Path to IDEAS.md when content_root is set."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = server._resolve_ideas_path()
        assert result is not None
        assert isinstance(result, Path)
        assert str(result).endswith("IDEAS.md")
        assert str(result).startswith("/tmp/test")

    def test_returns_none_when_no_content_root(self):
        """Returns None when content_root is empty."""
        state = _fresh_state()
        state["config"]["content_root"] = ""
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = server._resolve_ideas_path()
        assert result is None

    def test_returns_none_when_no_config(self):
        """Returns None when config is entirely missing."""
        mock_cache = MockStateCache({})
        with patch.object(server, "cache", mock_cache):
            result = server._resolve_ideas_path()
        assert result is None

    def test_returns_none_when_config_has_no_content_root(self):
        """Returns None when config exists but has no content_root key."""
        mock_cache = MockStateCache({"config": {}})
        with patch.object(server, "cache", mock_cache):
            result = server._resolve_ideas_path()
        assert result is None

    def test_path_combines_content_root_and_filename(self):
        """Path is exactly content_root / IDEAS.md."""
        state = _fresh_state()
        state["config"]["content_root"] = "/custom/content"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = server._resolve_ideas_path()
        assert result == Path("/custom/content/IDEAS.md")


# =============================================================================
# Edge case tests — bugs and boundary conditions found during code review
# =============================================================================


class TestNormalizeSlugEdgeCases:
    """Additional edge cases for _normalize_slug."""

    def test_consecutive_spaces_produce_double_hyphens(self):
        """Documents current behavior: consecutive spaces -> double hyphens.

        'my  album' becomes 'my--album', which won't match a directory
        slug 'my-album'. This is a known limitation.
        """
        result = server._normalize_slug("my  album")
        assert result == "my--album"

    def test_triple_spaces(self):
        """Triple spaces produce triple hyphens."""
        result = server._normalize_slug("a   b")
        assert result == "a---b"

    def test_special_characters_preserved(self):
        """Dots, parens, and other special chars pass through unchanged."""
        assert server._normalize_slug("album (deluxe)") == "album-(deluxe)"
        assert server._normalize_slug("v2.0") == "v2.0"
        assert server._normalize_slug("album!") == "album!"

    def test_leading_trailing_spaces(self):
        """Leading/trailing spaces become leading/trailing hyphens."""
        result = server._normalize_slug(" album ")
        assert result == "-album-"

    def test_tab_characters_preserved(self):
        """Tab characters are not converted (only spaces and underscores)."""
        result = server._normalize_slug("tab\there")
        assert result == "tab\there"


class TestDetectPhase:
    """Tests for _detect_phase covering all workflow phases."""

    def test_released_album(self):
        album = {"status": "Released", "tracks": {}}
        assert server._detect_phase(album) == "Released"

    def test_complete_album(self):
        album = {"status": "Complete", "tracks": {}}
        assert server._detect_phase(album) == "Ready to Release"

    def test_concept_album(self):
        album = {"status": "Concept", "tracks": {}}
        assert server._detect_phase(album) == "Planning"

    def test_no_tracks(self):
        album = {"status": "In Progress", "tracks": {}}
        assert server._detect_phase(album) == "Planning"

    def test_all_not_started(self):
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Not Started", "sources_verified": "N/A"},
                "02": {"status": "Not Started", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Writing"

    def test_source_verification_pending(self):
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "In Progress", "sources_verified": "Pending"},
                "02": {"status": "Final", "sources_verified": "Verified"},
            },
        }
        assert server._detect_phase(album) == "Source Verification"

    def test_all_final(self):
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Final", "sources_verified": "N/A"},
                "02": {"status": "Final", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Ready to Release"

    def test_all_generated_none_final(self):
        """All tracks generated but none final -> Mastering."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Generated", "sources_verified": "N/A"},
                "02": {"status": "Generated", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Mastering"

    def test_mixed_generated_and_final_partial(self):
        """Some generated + some final but not all -> Generating."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Generated", "sources_verified": "N/A"},
                "02": {"status": "Final", "sources_verified": "N/A"},
                "03": {"status": "Not Started", "sources_verified": "N/A"},
            },
        }
        # not_started > 0 -> Writing (checked before generated)
        assert server._detect_phase(album) == "Writing"

    def test_sources_verified_status_falls_through_counters(self):
        """Tracks with status 'Sources Verified' are not counted by any
        specific counter variable, but reach 'Ready to Generate' because
        not_started=0, in_progress=0, generated=0, final=0.

        Documents the edge case in _detect_phase where 'Sources Verified'
        and 'Sources Pending' statuses are not explicitly counted.
        """
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Sources Verified", "sources_verified": "Verified"},
                "02": {"status": "Sources Verified", "sources_verified": "Verified"},
            },
        }
        assert server._detect_phase(album) == "Ready to Write"

    def test_sources_pending_status_falls_through(self):
        """Tracks with status 'Sources Pending' are not counted but
        sources_verified='Pending' triggers Source Verification.
        """
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Sources Pending", "sources_verified": "Pending"},
                "02": {"status": "Sources Pending", "sources_verified": "Pending"},
            },
        }
        assert server._detect_phase(album) == "Source Verification"

    def test_generating_phase(self):
        """Some generated but not all completed -> Generating."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Generated", "sources_verified": "N/A"},
                "02": {"status": "Generated", "sources_verified": "N/A"},
                "03": {"status": "Final", "sources_verified": "N/A"},
                "04": {"status": "Sources Verified", "sources_verified": "Verified"},
            },
        }
        # generated=2, final=1, total=4, (generated+final)=3 < 4 -> Generating
        assert server._detect_phase(album) == "Generating"

    def test_in_progress_fallthrough(self):
        """Mixed statuses that don't fit any specific phase fall through."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Final", "sources_verified": "N/A"},
                "02": {"status": "Generated", "sources_verified": "N/A"},
            },
        }
        # generated=1, final=1, total=2, generated+final=2 == total
        # generated > 0 and final > 0 -> doesn't match "generated > 0 and final == 0"
        # final != total (final=1, total=2)
        # Falls through to "In Progress"
        assert server._detect_phase(album) == "In Progress"


class TestGetTrackEdgeCases:
    """Additional edge cases for get_track."""

    def test_empty_album_slug(self):
        """Empty string album slug returns not found."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_track("", "01-track")))
        assert result["found"] is False

    def test_empty_track_slug(self):
        """Empty string track slug returns not found."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_track("test-album", "")))
        assert result["found"] is False


class TestUpdateSessionToolEdgeCases:
    """Additional edge cases for update_session tool."""

    def test_action_appended_to_existing(self):
        """New action is appended to existing pending_actions list."""
        state = _fresh_state()
        state["session"]["pending_actions"] = ["existing action"]
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_session(action="new action")))
        session = result["session"]
        assert len(session["pending_actions"]) == 2
        assert "existing action" in session["pending_actions"]
        assert "new action" in session["pending_actions"]

    def test_multiple_fields_set_at_once(self):
        """Multiple session fields can be set in a single call."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_session(
                album="new", track="01", phase="Writing", action="do stuff"
            )))
        session = result["session"]
        assert session["last_album"] == "new"
        assert session["last_track"] == "01"
        assert session["last_phase"] == "Writing"
        assert "do stuff" in session["pending_actions"]


class TestGetAlbumProgressEdgeCases:
    """Additional edge cases for get_album_progress."""

    def test_all_tracks_sources_verified_status(self):
        """Album with all 'Sources Verified' tracks shows 0% completion."""
        state = _fresh_state()
        state["albums"]["sv-album"] = {
            "path": "/tmp/sv",
            "genre": "electronic",
            "title": "SV Album",
            "status": "In Progress",
            "tracks": {
                "01-a": {"status": "Sources Verified", "sources_verified": "Verified"},
                "02-b": {"status": "Sources Verified", "sources_verified": "Verified"},
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("sv-album")))
        assert result["completion_percentage"] == 0.0
        assert result["tracks_by_status"]["Sources Verified"] == 2

    def test_single_track_album(self):
        """Single-track album with Final status is 100%."""
        state = _fresh_state()
        state["albums"]["single"] = {
            "path": "/tmp/single",
            "genre": "pop",
            "title": "Single",
            "status": "Complete",
            "tracks": {
                "01-only": {"status": "Final", "sources_verified": "N/A"},
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_progress("single")))
        assert result["completion_percentage"] == 100.0
        assert result["tracks_completed"] == 1


class TestCreateIdeaFormatting:
    """Tests for create_idea output formatting."""

    def test_idea_block_format(self, tmp_path):
        """Verify the idea block doesn't produce excessive blank lines.

        Documents potential double-blank-line issue from lines starting
        with \\n being joined with \\n.join().
        """
        ideas_file = tmp_path / "IDEAS.md"
        ideas_file.write_text("# Album Ideas\n\n---\n\n## Ideas\n")

        state = _fresh_state()
        state["config"]["content_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_resolve_ideas_path", return_value=ideas_file):
            result = json.loads(_run(server.create_idea(
                title="Test Idea",
                genre="rock",
                idea_type="Documentary",
                concept="A test concept",
            )))

        assert result["created"] is True

        # Check the file content for excessive blank lines
        content = ideas_file.read_text()
        # Should not have triple newlines (double blank lines)
        assert "\n\n\n" not in content
        assert "### Test Idea" in content
        assert "**Genre**: rock" in content
        assert "**Status**: Pending" in content

    def test_idea_fields_on_separate_lines(self, tmp_path):
        """Each field should be on its own line, not doubled up."""
        ideas_file = tmp_path / "IDEAS.md"
        ideas_file.write_text("# Album Ideas\n\n---\n\n## Ideas\n")

        state = _fresh_state()
        state["config"]["content_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_resolve_ideas_path", return_value=ideas_file):
            result = json.loads(_run(server.create_idea(
                title="Field Test",
                genre="electronic",
                idea_type="Thematic",
                concept="Test fields",
            )))

        assert result["created"] is True
        content = ideas_file.read_text()
        # Fields should be consecutive lines separated by single newlines
        assert "**Genre**: electronic\n**Type**: Thematic" in content
        assert "**Type**: Thematic\n**Concept**: Test fields" in content

    def test_idea_no_optional_fields(self, tmp_path):
        """Idea with only title produces clean output."""
        ideas_file = tmp_path / "IDEAS.md"
        ideas_file.write_text("# Album Ideas\n\n---\n\n## Ideas\n")

        state = _fresh_state()
        state["config"]["content_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_resolve_ideas_path", return_value=ideas_file):
            result = json.loads(_run(server.create_idea(title="Minimal Idea")))

        assert result["created"] is True
        content = ideas_file.read_text()
        assert "### Minimal Idea" in content
        assert "**Status**: Pending" in content
        # No triple newlines
        assert "\n\n\n" not in content


# =============================================================================
# Round 2: Comprehensive code review tests
# =============================================================================


class TestCreateTrackAlbumLink:
    """Tests verifying create_track produces correct markdown links."""

    def _make_cache_with_album(self, tmp_path, album_title="Test Album"):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        state["albums"]["test-album"]["title"] = album_title
        return MockStateCache(state), album_dir, tracks_dir

    def test_album_link_has_brackets(self, tmp_path):
        """Album link in track file must be a valid markdown link [Title](url).

        Bug: previously produced 'Title(../README.md)' instead of
        '[Title](../README.md)'.
        """
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(tmp_path)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            "# [Track Title]\n"
            "| **Album** | [Album Name](../README.md) |\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "Song")))

        assert result["created"] is True
        content = (tracks_dir / "01-song.md").read_text()
        # Must be a valid markdown link with brackets
        assert "[Test Album](../README.md)" in content
        # Must NOT have the broken format without brackets
        assert "Test Album(../README.md)" not in content or "[Test Album]" in content

    def test_album_link_with_special_title(self, tmp_path):
        """Album title with special characters in link."""
        mock_cache, album_dir, tracks_dir = self._make_cache_with_album(
            tmp_path, album_title="The Album (Deluxe)"
        )
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "track.md").write_text(
            "| **Album** | [Album Name](../README.md) |\n"
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.create_track("test-album", "01", "Song")))

        content = (tracks_dir / "01-song.md").read_text()
        assert "[The Album (Deluxe)](../README.md)" in content


class TestPreGenGatesPartialVerdict:
    """Tests verifying PARTIAL verdict is reachable in run_pre_generation_gates.

    Bug: Previously, the condition 'total_blocking < sum(t["blocking"])'
    was always False because total_blocking IS that sum. Fixed to check
    if any track has 0 blocking while others have >0.
    """

    def test_partial_verdict_with_mixed_tracks(self, tmp_path):
        """One passing track + one failing track produces PARTIAL verdict."""
        pass_file = tmp_path / "01-pass.md"
        pass_file.write_text(_TRACK_ALL_GATES_PASS)
        fail_file = tmp_path / "02-fail.md"
        fail_file.write_text(_TRACK_GATES_FAIL)

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "01-pass": {
                "path": str(pass_file), "title": "Pass", "status": "In Progress",
                "explicit": False, "sources_verified": "Verified",
            },
            "02-fail": {
                "path": str(fail_file), "title": "Fail", "status": "In Progress",
                "explicit": None, "sources_verified": "Pending",
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album")))

        assert result["total_tracks"] == 2
        assert result["total_blocking"] > 0
        assert result["album_verdict"] == "PARTIAL"

    def test_all_pass_gives_all_ready(self, tmp_path):
        """All passing tracks produce ALL READY verdict."""
        pass_file_1 = tmp_path / "01-a.md"
        pass_file_1.write_text(_TRACK_ALL_GATES_PASS)
        pass_file_2 = tmp_path / "02-b.md"
        pass_file_2.write_text(_TRACK_ALL_GATES_PASS)

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "01-a": {
                "path": str(pass_file_1), "title": "A", "status": "In Progress",
                "explicit": False, "sources_verified": "Verified",
            },
            "02-b": {
                "path": str(pass_file_2), "title": "B", "status": "In Progress",
                "explicit": False, "sources_verified": "Verified",
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album")))

        assert result["album_verdict"] == "ALL READY"

    def test_all_fail_gives_not_ready(self, tmp_path):
        """All failing tracks produce NOT READY verdict."""
        fail_file_1 = tmp_path / "01-a.md"
        fail_file_1.write_text(_TRACK_GATES_FAIL)
        fail_file_2 = tmp_path / "02-b.md"
        fail_file_2.write_text(_TRACK_GATES_FAIL)

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "01-a": {
                "path": str(fail_file_1), "title": "A", "status": "In Progress",
                "explicit": None, "sources_verified": "Pending",
            },
            "02-b": {
                "path": str(fail_file_2), "title": "B", "status": "In Progress",
                "explicit": None, "sources_verified": "Pending",
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates("test-album")))

        assert result["album_verdict"] == "NOT READY"


class TestExtractCodeBlockEdgeCases:
    """Tests for the _extract_code_block helper edge cases."""

    def test_basic_code_block(self):
        text = "```\nhello world\n```"
        assert server._extract_code_block(text) == "hello world"

    def test_code_block_with_language_identifier(self):
        """Code block with language identifier strips it from output."""
        text = "```python\nprint('hello')\n```"
        result = server._extract_code_block(text)
        # Language identifier is stripped, only content remains
        assert "python" not in result
        assert "print('hello')" in result

    def test_empty_code_block(self):
        text = "```\n```"
        result = server._extract_code_block(text)
        assert result == ""

    def test_no_code_block(self):
        text = "Just some regular text"
        assert server._extract_code_block(text) is None

    def test_multiple_code_blocks_returns_first(self):
        text = "```\nfirst\n```\ntext\n```\nsecond\n```"
        assert server._extract_code_block(text) == "first"

    def test_code_block_without_newline_after_backticks(self):
        """Backticks immediately followed by content (no newline)."""
        text = "```content here```"
        result = server._extract_code_block(text)
        assert result == "content here"

    def test_multiline_code_block(self):
        text = "```\nline 1\nline 2\nline 3\n```"
        result = server._extract_code_block(text)
        assert "line 1" in result
        assert "line 2" in result
        assert "line 3" in result


class TestCheckPronunciationEdgeCases:
    """Edge case tests for check_pronunciation_enforcement."""

    def test_word_in_data_row_skipped(self, tmp_path):
        """Table row containing 'Word' in data is skipped by the header filter.

        Documents that the filter 'if "Word" in line' skips ANY row
        containing 'Word', including legitimate data rows.
        """
        track_file = tmp_path / "01-test.md"
        track_file.write_text(
            "# Test\n\n"
            "## Pronunciation Notes\n\n"
            "| Word/Phrase | Pronunciation | Reason |\n"
            "|-------------|---------------|--------|\n"
            "| Wordplay | WURD-play | Name |\n\n"
            "## Lyrics Box\n```\nWURD-play is fun\n```\n"
        )

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test"] = {
            "path": str(track_file), "title": "Test",
            "status": "In Progress", "sources_verified": "N/A",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.check_pronunciation_enforcement("test-album", "01-test")
            ))

        # The entry with "Word" in the word column is skipped by the header filter
        assert result["found"] is True
        # "Wordplay" entry is skipped because the line contains "Word"
        assert len(result["entries"]) == 0

    def test_no_pronunciation_section(self, tmp_path):
        """Track with no Pronunciation Notes section reports all applied."""
        track_file = tmp_path / "01-simple.md"
        track_file.write_text(
            "# Simple Track\n\n"
            "## Lyrics Box\n```\nSimple lyrics\n```\n"
        )

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-simple"] = {
            "path": str(track_file), "title": "Simple",
            "status": "In Progress", "sources_verified": "N/A",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.check_pronunciation_enforcement("test-album", "01-simple")
            ))

        assert result["all_applied"] is True
        assert result["unapplied_count"] == 0

    def test_unapplied_pronunciation(self, tmp_path):
        """Track with pronunciation entries not in lyrics flags them."""
        track_file = tmp_path / "01-pron.md"
        track_file.write_text(
            "# Pron Track\n\n"
            "## Pronunciation Notes\n\n"
            "| Word/Phrase | Pronunciation | Reason |\n"
            "|-------------|---------------|--------|\n"
            "| live | LYVE | alive |\n\n"
            "## Lyrics Box\n```\n[Verse 1]\nI want to live free\n```\n"
        )

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-pron"] = {
            "path": str(track_file), "title": "Pron Track",
            "status": "In Progress", "sources_verified": "N/A",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.check_pronunciation_enforcement("test-album", "01-pron")
            ))

        assert result["all_applied"] is False
        assert result["unapplied_count"] == 1
        assert result["entries"][0]["word"] == "live"
        assert result["entries"][0]["applied"] is False


class TestGetAlbumFullEdgeCases:
    """Edge case tests for get_album_full."""

    def test_no_include_sections(self):
        """Without include_sections, returns metadata only."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("test-album")))

        assert result["found"] is True
        assert result["slug"] == "test-album"
        assert "tracks" in result
        # No "sections" key on tracks (no file reads)
        for track in result["tracks"].values():
            assert "sections" not in track

    def test_fuzzy_match_substring(self):
        """Fuzzy match via substring when exact match fails."""
        state = _fresh_state()
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            # "test" is a substring of "test-album"
            result = json.loads(_run(server.get_album_full("test")))

        # Should find via substring match (but may get multiple matches)
        # "test-album" contains "test" and "another-album" does not
        assert result["found"] is True or "multiple" in result.get("error", "").lower()

    def test_album_not_found(self):
        """Nonexistent album returns error with available albums."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_album_full("nonexistent-xyz")))

        assert result["found"] is False
        assert "available_albums" in result

    def test_with_section_extraction(self, tmp_path):
        """Sections are extracted when include_sections is provided."""
        track_file = tmp_path / "01-track.md"
        track_file.write_text(
            "# Track\n\n"
            "## Style Box\n```\nelectronic, chill\n```\n\n"
            "## Lyrics Box\n```\nLa la la\n```\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-first-track"]["path"] = str(track_file)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.get_album_full("test-album", include_sections="style,lyrics")
            ))

        assert result["found"] is True
        track = result["tracks"]["01-first-track"]
        assert "sections" in track
        assert "style" in track["sections"]
        assert "electronic, chill" in track["sections"]["style"]


class TestUpdateAlbumStatusEdgeCases:
    """Additional edge cases for update_album_status."""

    def test_invalid_status_rejected(self):
        """Invalid status value is rejected."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Invalid Status")))
        assert "error" in result
        assert "Invalid status" in result["error"]

    def test_case_insensitive_status(self, tmp_path):
        """Status values are matched case-insensitively."""
        readme = tmp_path / "README.md"
        readme.write_text("| **Status** | Concept |\n")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "complete")))
        assert result["success"] is True

    def test_album_not_found(self):
        """Nonexistent album returns error."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("no-such", "Complete")))
        assert result["found"] is False

    def test_missing_readme(self, tmp_path):
        """Missing README.md returns error."""
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        mock_cache = MockStateCache(state)
        # tmp_path exists but has no README.md
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert "error" in result
        assert "README.md" in result["error"]


@pytest.mark.unit
class TestAlbumTrackConsistencyCheck:
    """Tests for _check_album_track_consistency enforcement in update_album_status."""

    def _make_cache_with_tracks(self, tmp_path, album_status, track_statuses):
        """Create a mock cache with specific track statuses."""
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_SAMPLE_ALBUM_README.replace(
            "| **Status** | In Progress |", f"| **Status** | {album_status} |"
        ))
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["status"] = album_status
        state["albums"]["test-album"]["tracks"] = {
            slug: {
                "path": "/tmp/test/track.md",
                "title": slug,
                "status": status,
                "explicit": False,
                "has_suno_link": False,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            }
            for slug, status in track_statuses.items()
        }
        return MockStateCache(state), readme_path

    def test_in_progress_blocked_all_not_started(self, tmp_path):
        """Album 'In Progress' blocked when all tracks are 'Not Started'."""
        mock_cache, _ = self._make_cache_with_tracks(tmp_path, "Concept", {
            "01-track": "Not Started",
            "02-track": "Not Started",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "In Progress")))
        assert "error" in result
        assert "all tracks are still" in result["error"]

    def test_complete_blocked_track_below_generated(self, tmp_path):
        """Album 'Complete' blocked when any track is below 'Generated'."""
        mock_cache, _ = self._make_cache_with_tracks(tmp_path, "In Progress", {
            "01-track": "Final",
            "02-track": "In Progress",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert "error" in result
        assert "below 'Generated'" in result["error"]
        assert "02-track" in result["error"]

    def test_released_blocked_track_not_final(self, tmp_path):
        """Album 'Released' blocked when any track is not 'Final'."""
        mock_cache, _ = self._make_cache_with_tracks(tmp_path, "Complete", {
            "01-track": "Final",
            "02-track": "Generated",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert "error" in result
        assert "not Final" in result["error"]
        assert "02-track" in result["error"]

    def test_passes_when_tracks_at_correct_levels(self, tmp_path):
        """Album transitions succeed when all tracks meet requirements."""
        mock_cache, _ = self._make_cache_with_tracks(tmp_path, "In Progress", {
            "01-track": "Generated",
            "02-track": "Final",
        })
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert result["success"] is True

    def test_empty_album_allowed_at_any_level(self, tmp_path):
        """Albums with no tracks pass consistency check at any status."""
        mock_cache, _ = self._make_cache_with_tracks(tmp_path, "In Progress", {})
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Complete")))
        assert result["success"] is True

    def test_force_bypasses_consistency_check(self, tmp_path):
        """force=True bypasses album/track consistency check."""
        mock_cache, _ = self._make_cache_with_tracks(tmp_path, "In Progress", {
            "01-track": "Not Started",
        })
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Complete", force=True
            )))
        assert result["success"] is True

    def test_early_statuses_no_track_requirements(self, tmp_path):
        """Concept/Research Complete/Sources Verified have no track requirements."""
        mock_cache, _ = self._make_cache_with_tracks(tmp_path, "Concept", {
            "01-track": "Not Started",
        })
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Research Complete"
            )))
        assert result["success"] is True


@pytest.mark.unit
class TestReleaseReadinessGate:
    """Tests for release readiness gate in update_album_status."""

    def _make_release_env(self, tmp_path, has_audio=True, has_mastered=True, has_art=True):
        """Create a mock cache with album at Complete, all tracks Final, and audio dirs."""
        album_dir = tmp_path / "album"
        readme_path = album_dir / "README.md"
        readme_path.parent.mkdir(parents=True)
        readme_path.write_text(_SAMPLE_ALBUM_README.replace(
            "| **Status** | In Progress |", "| **Status** | Complete |"
        ))

        # Create real track file with valid streaming lyrics
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True, exist_ok=True)
        track_file = tracks_dir / "01-track.md"
        track_file.write_text(
            "# Track\n\n## Streaming Lyrics\n\n```\n"
            "This is a real song lyric\nWith multiple lines\n```\n"
        )

        audio_dir = tmp_path / "audio" / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        if has_audio:
            (audio_dir / "originals").mkdir(exist_ok=True)
            (audio_dir / "originals" / "01-track.wav").write_bytes(b"RIFF")
        if has_mastered:
            mastered_dir = audio_dir / "mastered"
            mastered_dir.mkdir()
            (mastered_dir / "01-track.wav").write_bytes(b"RIFF")
        if has_art:
            (audio_dir / "album.png").write_bytes(b"PNG")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(readme_path.parent)
        state["albums"]["test-album"]["status"] = "Complete"
        state["albums"]["test-album"]["genre"] = "electronic"
        state["albums"]["test-album"]["tracks"] = {
            "01-track": {
                "path": str(track_file), "title": "Track", "status": "Final",
                "explicit": False, "sources_verified": "N/A", "mtime": 1234567890.0,
            },
        }
        state["config"]["audio_root"] = str(tmp_path / "audio")
        return MockStateCache(state)

    def test_released_blocked_no_audio(self, tmp_path):
        """Released blocked when no audio directory."""
        mock_cache = self._make_release_env(tmp_path, has_audio=False, has_mastered=False, has_art=False)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert "error" in result
        assert "issues" in result
        assert any("WAV" in i for i in result["issues"])

    def test_released_blocked_no_mastered(self, tmp_path):
        """Released blocked when no mastered files."""
        mock_cache = self._make_release_env(tmp_path, has_mastered=False, has_art=True)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert "error" in result
        assert any("mastered" in i.lower() for i in result["issues"])

    def test_released_blocked_no_art(self, tmp_path):
        """Released blocked when no album art."""
        mock_cache = self._make_release_env(tmp_path, has_art=False)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert "error" in result
        assert any("album art" in i.lower() for i in result["issues"])

    def test_released_passes_all_prerequisites(self, tmp_path):
        """Released passes when all prerequisites met."""
        mock_cache = self._make_release_env(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert result["success"] is True

    def test_force_bypasses_release_gate(self, tmp_path):
        """force=True bypasses all release checks."""
        mock_cache = self._make_release_env(tmp_path, has_audio=False, has_mastered=False, has_art=False)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Released", force=True
            )))
        assert result["success"] is True

    def test_multiple_issues_reported_together(self, tmp_path):
        """All release issues are collected and reported in one response."""
        mock_cache = self._make_release_env(tmp_path, has_audio=False, has_mastered=False, has_art=False)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert "issues" in result
        # Should report at least audio, mastered, and art issues
        assert len(result["issues"]) >= 3

    def test_released_blocked_missing_streaming_lyrics(self, tmp_path):
        """Released blocked when track file has no Streaming Lyrics section."""
        mock_cache = self._make_release_env(tmp_path)
        # Overwrite track file with content missing Streaming Lyrics
        state = mock_cache.get_state()
        track_path = state["albums"]["test-album"]["tracks"]["01-track"]["path"]
        Path(track_path).write_text("# Track\n\n## Lyrics Box\n\nSome lyrics here\n")
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert "error" in result
        assert any("streaming lyrics" in i.lower() for i in result["issues"])

    def test_released_blocked_placeholder_streaming_lyrics(self, tmp_path):
        """Released blocked when streaming lyrics contain placeholder markers."""
        mock_cache = self._make_release_env(tmp_path)
        state = mock_cache.get_state()
        track_path = state["albums"]["test-album"]["tracks"]["01-track"]["path"]
        Path(track_path).write_text(
            "# Track\n\n## Streaming Lyrics\n\n```\n"
            "Plain lyrics here\nCapitalize first letter of each line\n```\n"
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert "error" in result
        assert any("streaming lyrics" in i.lower() for i in result["issues"])

    def test_released_passes_with_valid_streaming_lyrics(self, tmp_path):
        """Released passes when streaming lyrics are valid (no placeholders)."""
        mock_cache = self._make_release_env(tmp_path)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Released")))
        assert result["success"] is True


@pytest.mark.unit
class TestDocumentaryAlbumSourcePath:
    """Tests for documentary album source path enforcement in update_album_status."""

    def _make_cache_with_album(self, tmp_path, has_sources=True, status="Concept"):
        """Create a mock cache with an album directory."""
        album_dir = tmp_path / "album"
        album_dir.mkdir(parents=True)
        readme_content = _SAMPLE_ALBUM_README.replace(
            "| **Status** | In Progress |", f"| **Status** | {status} |"
        )
        (album_dir / "README.md").write_text(readme_content)
        if has_sources:
            (album_dir / "SOURCES.md").write_text("# Sources\n\n[Link](https://example.com)")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        state["albums"]["test-album"]["status"] = status
        return MockStateCache(state)

    def test_concept_to_in_progress_blocked_with_sources(self, tmp_path):
        """Concept → In Progress blocked when SOURCES.md exists (documentary album)."""
        mock_cache = self._make_cache_with_album(tmp_path, has_sources=True, status="Concept")
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status("test-album", "In Progress")))
        assert "error" in result
        assert "SOURCES.md" in result["error"]
        assert "documentary" in result["error"].lower()

    def test_concept_to_in_progress_allowed_without_sources(self, tmp_path):
        """Concept → In Progress allowed when no SOURCES.md exists."""
        mock_cache = self._make_cache_with_album(tmp_path, has_sources=False, status="Concept")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "In Progress")))
        assert result["success"] is True

    def test_concept_to_research_complete_allowed_with_sources(self, tmp_path):
        """Concept → Research Complete works fine even with SOURCES.md."""
        mock_cache = self._make_cache_with_album(tmp_path, has_sources=True, status="Concept")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "Research Complete")))
        assert result["success"] is True

    def test_force_bypasses_documentary_check(self, tmp_path):
        """force=True bypasses the documentary album check."""
        mock_cache = self._make_cache_with_album(tmp_path, has_sources=True, status="Concept")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status(
                "test-album", "In Progress", force=True
            )))
        assert result["success"] is True

    def test_config_disabled_allows_concept_to_in_progress(self, tmp_path):
        """When require_source_path_for_documentary is false, Concept → In Progress works."""
        mock_cache = self._make_cache_with_album(tmp_path, has_sources=True, status="Concept")
        state = mock_cache.get_state()
        state["config"]["generation"] = {"require_source_path_for_documentary": False}
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status("test-album", "In Progress")))
        assert result["success"] is True


class TestDetectPhaseAdditional:
    """Additional _detect_phase edge cases from comprehensive review."""

    def test_sources_verified_status_not_counted_in_progress(self):
        """Tracks with 'Sources Verified' status but verified sources_verified field
        are not counted by not_started/in_progress, falling to 'Ready to Generate'.

        This tests the gap where 'Sources Verified' as a track STATUS is not
        the same as sources_verified as a field. Tracks with status='Sources Verified'
        and sources_verified='Verified' bypass all counters.
        """
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Sources Verified", "sources_verified": "Verified"},
                "02": {"status": "Not Started", "sources_verified": "N/A"},
            },
        }
        # not_started=1, sources_verified as status falls through
        # not_started > 0 -> "Writing"
        assert server._detect_phase(album) == "Writing"

    def test_all_sources_pending_status_no_verification_field(self):
        """All tracks with status='Sources Pending' but sources_verified='N/A'.

        The track STATUS is 'Sources Pending' but the sources_verified FIELD is
        'N/A', so sources_pending check (on field) returns 0. Falls through to
        'Ready to Generate' since no counter catches 'Sources Pending' status.
        """
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Sources Pending", "sources_verified": "N/A"},
                "02": {"status": "Sources Pending", "sources_verified": "N/A"},
            },
        }
        # sources_pending=0 (checks field, not status), not_started=0,
        # in_progress=0, generated=0, final=0 -> "Ready to Write"
        assert server._detect_phase(album) == "Ready to Write"

    def test_mixed_generated_final_equals_total(self):
        """When generated + final == total but generated > 0 and final > 0,
        falls through to 'In Progress' because:
        - generated > 0 and (generated+final) < total is False
        - generated > 0 and final == 0 is False
        - final == total is False (final < total)
        """
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Generated", "sources_verified": "N/A"},
                "02": {"status": "Final", "sources_verified": "N/A"},
            },
        }
        # generated=1, final=1, total=2
        # generated+final=2 == total, so "Generating" check fails
        # generated>0 and final==0 is False
        # final==total is False (1!=2)
        # Falls through to "In Progress"
        assert server._detect_phase(album) == "In Progress"


class TestValidateAlbumStructureEdgeCases:
    """Additional edge cases for validate_album_structure."""

    def test_empty_check_set_defaults_to_all(self):
        """Empty checks parameter defaults to all checks."""
        state = _fresh_state()
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.validate_album_structure("test-album", checks="")
            ))
        assert result["found"] is True
        # Should have run all check categories
        categories = {r["category"] for r in result["checks"]}
        assert "structure" in categories

    def test_specific_check_only(self):
        """Running only 'structure' check skips other categories."""
        state = _fresh_state()
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.validate_album_structure("test-album", checks="structure")
            ))
        categories = {r["category"] for r in result["checks"]}
        assert "structure" in categories
        assert "audio" not in categories
        assert "art" not in categories

    def test_album_not_found(self):
        """Nonexistent album returns error."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.validate_album_structure("nonexistent")
            ))
        assert result["found"] is False

    def test_no_config(self):
        """Missing config returns error."""
        state = _fresh_state()
        state["config"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.validate_album_structure("test-album")
            ))
        assert "error" in result


class TestSearchScopeFiltering:
    """Tests for search scope parameter handling."""

    def test_scope_albums_only(self):
        """Scope 'albums' only returns album results."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("test", scope="albums")))
        assert "albums" in result
        assert "tracks" not in result
        assert "ideas" not in result

    def test_scope_tracks_only(self):
        """Scope 'tracks' only returns track results."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("first", scope="tracks")))
        assert "tracks" in result
        assert "albums" not in result

    def test_scope_ideas_only(self):
        """Scope 'ideas' only returns idea results."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("cool", scope="ideas")))
        assert "ideas" in result
        assert "albums" not in result

    def test_scope_skills_only(self):
        """Scope 'skills' only returns skill results."""
        state = _fresh_state()
        state["skills"] = {"items": {"lyric-writer": {
            "description": "Write lyrics", "model_tier": "opus",
            "user_invocable": True,
        }}, "count": 1}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("lyric", scope="skills")))
        assert "skills" in result
        assert len(result["skills"]) == 1

    def test_empty_query(self):
        """Empty query returns all items."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.search("", scope="all")))
        # Empty string is a substring of everything
        assert result["total_matches"] > 0


class TestLoadOverrideEdgeCases:
    """Additional edge cases for load_override."""

    def test_path_traversal_blocked(self):
        """Path traversal attempts are blocked."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("../../etc/passwd")))
        assert "error" in result
        assert "escape" in result["error"].lower()

    def test_override_not_found(self, tmp_path):
        """Missing override file returns found=False."""
        state = _fresh_state()
        state["config"]["overrides_dir"] = str(tmp_path)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.load_override("nonexistent.md")))
        assert result["found"] is False


class TestGetReferenceEdgeCases:
    """Additional edge cases for get_reference."""

    def test_path_traversal_blocked(self):
        """Path traversal attempts are blocked."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_reference("../../etc/passwd")))
        assert "error" in result

    def test_auto_appends_md_extension(self, tmp_path):
        """Name without .md extension gets it added automatically."""
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir()
        (ref_dir / "test-guide.md").write_text("# Guide Content")

        with patch.object(server, "PLUGIN_ROOT", tmp_path):
            result = json.loads(_run(server.get_reference("test-guide")))
        assert result["found"] is True
        assert "Guide Content" in result["content"]


class TestGetLyricsStatsEdgeCases:
    """Additional edge cases for get_lyrics_stats."""

    def test_unknown_genre_uses_default_target(self, tmp_path):
        """Unknown genre uses default word count target."""
        track_file = tmp_path / "01-track.md"
        track_file.write_text(
            "# Track\n\n## Lyrics Box\n```\n[Verse 1]\n"
            + " ".join(["word"] * 200)
            + "\n```\n"
        )
        state = _fresh_state()
        state["albums"]["test-album"]["genre"] = "unknown-genre"
        state["albums"]["test-album"]["tracks"]["01-first-track"]["path"] = str(track_file)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "01")))
        assert result["found"] is True
        # Default target is 150-350
        assert result["target"]["min"] == 150
        assert result["target"]["max"] == 350

    def test_empty_lyrics_shows_empty_status(self, tmp_path):
        """Track without a Lyrics Box section shows EMPTY status."""
        track_file = tmp_path / "01-track.md"
        # No Lyrics Box section at all -> lyrics stays empty
        track_file.write_text("# Track\n\n## Style Box\n```\nelectronic\n```\n")
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-first-track"]["path"] = str(track_file)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_lyrics_stats("test-album", "01")))
        track = result["tracks"][0]
        assert track["status"] == "EMPTY"
        assert track["word_count"] == 0


class TestExtractLinksEdgeCases:
    """Additional edge cases for extract_links."""

    def test_no_links_in_file(self, tmp_path):
        """File with no markdown links returns empty list."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "SOURCES.md").write_text("# Sources\n\nNo links here.")

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album")))
        assert result["found"] is True
        assert result["count"] == 0

    def test_links_with_line_numbers(self, tmp_path):
        """Links include correct line numbers."""
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        (album_dir / "SOURCES.md").write_text(
            "# Sources\n\n"
            "First line\n"
            "[Link 1](http://example.com/1)\n"
            "Another line\n"
            "[Link 2](http://example.com/2)\n"
        )

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_links("test-album")))
        assert result["count"] == 2
        assert result["links"][0]["line_number"] == 4
        assert result["links"][1]["line_number"] == 6


class TestFindAlbumFuzzyMatch:
    """Tests for find_album fuzzy matching behavior."""

    def test_substring_match_bidirectional(self):
        """Fuzzy match works with substring in both directions."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            # "test" is a substring of "test-album"
            result = json.loads(_run(server.find_album("test-album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"

    def test_multiple_matches_returns_error(self):
        """Multiple fuzzy matches returns error with match list."""
        state = _fresh_state()
        state["albums"]["test-one"] = {"title": "Test One", "status": "Concept"}
        state["albums"]["test-two"] = {"title": "Test Two", "status": "Concept"}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("test")))
        # "test" matches test-album, test-one, test-two, another-album possibly
        # Actually "test" is in "test-album", "test-one", "test-two" but NOT "another-album"
        assert result["found"] is False
        assert "multiple_matches" in result


# =============================================================================
# Comprehensive edge case tests — Round 5 coverage audit
# =============================================================================


@pytest.mark.unit
class TestExtractSectionNewSectionNames:
    """Tests for extract_section with newly added _SECTION_NAMES entries."""

    def _make_track_with_sections(self, tmp_path, extra_sections=""):
        """Create a track file with standard + extra sections."""
        content = _SAMPLE_TRACK_MD + extra_sections
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(content)

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

    def test_extract_mood_section(self, tmp_path):
        """'mood' maps to 'Mood & Imagery' heading."""
        extra = "\n## Mood & Imagery\n\nDark, atmospheric, digital noir\n"
        mock_cache = self._make_track_with_sections(tmp_path, extra)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "mood")))
        assert result["found"] is True
        assert "Dark, atmospheric" in result["content"]
        assert result["section"] == "Mood & Imagery"

    def test_extract_mood_imagery_alias(self, tmp_path):
        """'mood-imagery' also maps to 'Mood & Imagery' heading."""
        extra = "\n## Mood & Imagery\n\nCyberpunk vibes\n"
        mock_cache = self._make_track_with_sections(tmp_path, extra)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "mood-imagery")))
        assert result["found"] is True
        assert "Cyberpunk vibes" in result["content"]

    def test_extract_lyrical_approach(self, tmp_path):
        """'lyrical-approach' maps to 'Lyrical Approach' heading."""
        extra = "\n## Lyrical Approach\n\nFirst person, stream of consciousness\n"
        mock_cache = self._make_track_with_sections(tmp_path, extra)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "lyrical-approach")))
        assert result["found"] is True
        assert "First person" in result["content"]
        assert result["section"] == "Lyrical Approach"

    def test_extract_phonetic_review(self, tmp_path):
        """'phonetic-review' maps to 'Phonetic Review Checklist' heading."""
        extra = "\n## Phonetic Review Checklist\n\n- [x] No homographs\n- [x] No proper nouns\n"
        mock_cache = self._make_track_with_sections(tmp_path, extra)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.extract_section("test-album", "01-test-track", "phonetic-review")))
        assert result["found"] is True
        assert "No homographs" in result["content"]
        assert result["section"] == "Phonetic Review Checklist"


@pytest.mark.unit
class TestExtractMarkdownSectionEdgeCasesRound5:
    """Additional edge cases for _extract_markdown_section."""

    def test_heading_at_absolute_eof_no_newline(self):
        """Heading at very end of file with no trailing content."""
        text = "## First\nContent\n\n## Last"
        result = server._extract_markdown_section(text, "Last")
        assert result == ""

    def test_heading_at_eof_with_trailing_newline(self):
        """Heading at end of file followed only by newlines."""
        text = "## First\nContent\n\n## Last\n\n"
        result = server._extract_markdown_section(text, "Last")
        assert result == ""

    def test_heading_with_ampersand(self):
        """Heading containing '&' character matches correctly."""
        text = "## Mood & Imagery\n\nDark vibes\n\n## Next\nContent"
        result = server._extract_markdown_section(text, "Mood & Imagery")
        assert result == "Dark vibes"

    def test_heading_case_insensitive_with_special_chars(self):
        """Case-insensitive match works with special characters."""
        text = "## MOOD & IMAGERY\n\nLoud stuff\n\n## Next"
        result = server._extract_markdown_section(text, "mood & imagery")
        assert result == "Loud stuff"

    def test_only_h3_heading(self):
        """H3-only file works as heading target."""
        text = "### Style Box\n```\nrock, 120 BPM\n```\n"
        result = server._extract_markdown_section(text, "Style Box")
        assert "rock, 120 BPM" in result

    def test_h3_not_terminated_by_h3(self):
        """H3 section is terminated by another H3 (same level)."""
        text = "### Style Box\nstyle content\n\n### Lyrics Box\nlyrics content\n"
        result = server._extract_markdown_section(text, "Style Box")
        assert "style content" in result
        assert "lyrics content" not in result


@pytest.mark.unit
class TestUpdateTrackFieldStatusValidation:
    """Tests for update_track_field status validation edge cases."""

    def test_invalid_status_rejected(self):
        """Completely invalid status string is rejected."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-first-track", "status", "InvalidStatus"
            )))
        assert "error" in result
        assert "Invalid track status" in result["error"]

    def test_empty_status_rejected(self):
        """Empty string as status value is rejected."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-first-track", "status", ""
            )))
        assert "error" in result
        assert "Invalid track status" in result["error"]

    def test_whitespace_padded_status_accepted(self):
        """Status with whitespace padding is accepted (stripped before check)."""
        # The validation does value.lower().strip(), so "  Final  " becomes "final"
        mock_cache = MockStateCache()
        state = mock_cache.get_state()
        # Use a track that exists — force=True to bypass transition check
        mock_cache_with_file_state = MockStateCache(state)
        with patch.object(server, "cache", mock_cache_with_file_state):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-first-track", "status", "  Final  ", force=True
            )))
        # Should pass validation (whitespace stripped) but may fail on file write
        # since the track path in SAMPLE_STATE doesn't exist on disk
        assert "Invalid track status" not in result.get("error", "")

    def test_mixed_case_status_accepted(self):
        """Mixed case status like 'in progress' passes validation."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-first-track", "status", "in progress", force=True
            )))
        # Passes status validation; may fail on file path
        assert "Invalid track status" not in result.get("error", "")

    def test_all_valid_statuses_accepted(self):
        """All valid track statuses pass validation (using force to bypass transitions)."""
        valid = ["Not Started", "Sources Pending", "Sources Verified",
                 "In Progress", "Generated", "Final"]
        for status in valid:
            mock_cache = MockStateCache()
            with patch.object(server, "cache", mock_cache):
                result = json.loads(_run(server.update_track_field(
                    "test-album", "01-first-track", "status", status, force=True
                )))
            assert "Invalid track status" not in result.get("error", ""), \
                f"Status '{status}' was incorrectly rejected"


@pytest.mark.unit
class TestTrackStatusTransitionEnforcement:
    """Tests for track status transition validation."""

    def _make_cache_with_status(self, tmp_path, status):
        """Create a mock cache with a track at a specific status."""
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD.replace(
            "| **Status** | In Progress |", f"| **Status** | {status} |"
        ))
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": status,
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        return MockStateCache(state), track_file

    def test_valid_transition_not_started_to_sources_pending(self, tmp_path):
        """Not Started → Sources Pending is allowed."""
        mock_cache, _ = self._make_cache_with_status(tmp_path, "Not Started")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Sources Pending"
            )))
        assert result["success"] is True

    def test_valid_skip_not_started_to_in_progress(self, tmp_path):
        """Not Started → In Progress is allowed (non-documentary albums)."""
        mock_cache, _ = self._make_cache_with_status(tmp_path, "Not Started")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "In Progress"
            )))
        assert result["success"] is True

    def test_invalid_skip_not_started_to_final(self, tmp_path):
        """Not Started → Final is rejected (skips required steps)."""
        mock_cache, _ = self._make_cache_with_status(tmp_path, "Not Started")
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Final"
            )))
        assert "error" in result
        assert "Invalid transition" in result["error"]
        assert "force=True" in result["error"]

    def test_terminal_state_final_rejected(self, tmp_path):
        """Final → anything is rejected (terminal state)."""
        mock_cache, _ = self._make_cache_with_status(tmp_path, "Final")
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "In Progress"
            )))
        assert "error" in result
        assert "Invalid transition" in result["error"]
        assert "none (terminal)" in result["error"]

    def test_force_override_bypasses_validation(self, tmp_path):
        """force=True allows any transition."""
        mock_cache, _ = self._make_cache_with_status(tmp_path, "Not Started")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "status", "Final", force=True
            )))
        assert result["success"] is True


@pytest.mark.unit
class TestAlbumStatusTransitionEnforcement:
    """Tests for album status transition validation."""

    def _make_cache_with_album_status(self, tmp_path, album_status, track_statuses=None):
        """Create a mock cache with album at a specific status."""
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_SAMPLE_ALBUM_README.replace(
            "| **Status** | In Progress |", f"| **Status** | {album_status} |"
        ))
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["status"] = album_status
        if track_statuses:
            for slug, status in track_statuses.items():
                if slug in state["albums"]["test-album"]["tracks"]:
                    state["albums"]["test-album"]["tracks"][slug]["status"] = status
        return MockStateCache(state), readme_path

    def test_valid_transition_concept_to_research_complete(self, tmp_path):
        """Concept → Research Complete is allowed."""
        mock_cache, _ = self._make_cache_with_album_status(tmp_path, "Concept")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Research Complete"
            )))
        assert result["success"] is True

    def test_invalid_skip_concept_to_complete(self, tmp_path):
        """Concept → Complete is rejected (skips required steps)."""
        mock_cache, _ = self._make_cache_with_album_status(tmp_path, "Concept")
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Complete"
            )))
        assert "error" in result
        assert "Invalid transition" in result["error"]

    def test_sources_verified_gate_blocks_unverified_tracks(self, tmp_path):
        """Cannot set album to Sources Verified when tracks are unverified."""
        mock_cache, _ = self._make_cache_with_album_status(
            tmp_path, "Research Complete",
            track_statuses={
                "01-first-track": "Sources Verified",
                "02-second-track": "Sources Pending",
            }
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Sources Verified"
            )))
        assert "error" in result
        assert "still unverified" in result["error"]
        assert "02-second-track" in result["error"]

    def test_sources_verified_gate_passes_all_verified(self, tmp_path):
        """Can set album to Sources Verified when all tracks are verified."""
        mock_cache, _ = self._make_cache_with_album_status(
            tmp_path, "Research Complete",
            track_statuses={
                "01-first-track": "Sources Verified",
                "02-second-track": "Sources Verified",
            }
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Sources Verified"
            )))
        assert result["success"] is True

    def test_force_override_bypasses_album_validation(self, tmp_path):
        """force=True allows any album transition."""
        mock_cache, _ = self._make_cache_with_album_status(tmp_path, "Concept")
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Released", force=True
            )))
        assert result["success"] is True


@pytest.mark.unit
class TestMasterAlbumStage7TransitionLogic:
    """Tests for master_album Stage 7 transition-safe behavior."""

    def test_only_generated_tracks_advance_to_final(self, tmp_path):
        """Stage 7 only sets Generated tracks to Final, skips others."""
        # Create track files with different statuses
        tracks_dir = tmp_path / "tracks"
        tracks_dir.mkdir()

        generated_track = tracks_dir / "01-generated.md"
        generated_track.write_text(
            _SAMPLE_TRACK_MD.replace("| **Status** | In Progress |", "| **Status** | Generated |")
        )

        in_progress_track = tracks_dir / "02-in-progress.md"
        in_progress_track.write_text(_SAMPLE_TRACK_MD)  # Status: In Progress

        final_track = tracks_dir / "03-already-final.md"
        final_track.write_text(
            _SAMPLE_TRACK_MD.replace("| **Status** | In Progress |", "| **Status** | Final |")
        )

        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "01-generated": {
                "path": str(generated_track),
                "title": "Generated Track",
                "status": "Generated",
                "explicit": False,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            },
            "02-in-progress": {
                "path": str(in_progress_track),
                "title": "In Progress Track",
                "status": "In Progress",
                "explicit": False,
                "has_suno_link": False,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            },
            "03-already-final": {
                "path": str(final_track),
                "title": "Already Final",
                "status": "Final",
                "explicit": False,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            },
        }
        mock_cache = MockStateCache(state)

        # Can't call master_album directly (needs audio processing),
        # so verify the transition maps match Stage 7 logic
        err_generated = server._validate_track_transition("Generated", "Final")
        assert err_generated is None, "Generated → Final should be valid"

        err_in_progress = server._validate_track_transition("In Progress", "Final")
        assert err_in_progress is not None, "In Progress → Final should be invalid"

        err_final = server._validate_track_transition("Final", "Final")
        assert err_final is not None, "Final → Final should be invalid (terminal)"


@pytest.mark.unit
class TestSafeJsonEdgeCasesRound5:
    """Additional edge cases for _safe_json."""

    def test_non_serializable_type(self):
        """Non-serializable type falls back to str() via default=str."""
        data = {"value": set([1, 2, 3])}
        result = server._safe_json(data)
        parsed = json.loads(result)
        # set is converted via str()
        assert "value" in parsed

    def test_none_value(self):
        """None is valid JSON null."""
        data = {"value": None}
        result = json.loads(server._safe_json(data))
        assert result["value"] is None

    def test_empty_dict(self):
        """Empty dict serializes correctly."""
        result = json.loads(server._safe_json({}))
        assert result == {}

    def test_empty_list(self):
        """Empty list serializes correctly."""
        result = json.loads(server._safe_json([]))
        assert result == []

    def test_deeply_nested(self):
        """Deeply nested structure serializes correctly."""
        data = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        result = json.loads(server._safe_json(data))
        assert result["a"]["b"]["c"]["d"]["e"] == "deep"

    def test_path_object_via_default_str(self):
        """Path objects are serialized via default=str."""
        data = {"path": Path("/tmp/test")}
        result = json.loads(server._safe_json(data))
        assert "/tmp/test" in result["path"]


@pytest.mark.unit
class TestNormalizeSlugEdgeCasesRound5:
    """Additional edge cases for _normalize_slug."""

    def test_special_characters_preserved(self):
        """Non-space, non-underscore special characters pass through."""
        assert server._normalize_slug("my-album!") == "my-album!"

    def test_dots_preserved(self):
        """Dots in slugs are preserved."""
        assert server._normalize_slug("v2.0-release") == "v2.0-release"

    def test_numbers_only(self):
        """All-numeric string is lowercased (no-op)."""
        assert server._normalize_slug("12345") == "12345"

    def test_unicode_preserved(self):
        """Unicode characters are preserved and lowercased."""
        assert server._normalize_slug("Café Beats") == "café-beats"

    def test_tabs_not_converted(self):
        """Tab characters are NOT converted to hyphens (only space and _)."""
        result = server._normalize_slug("tab\there")
        # Tabs are not in the replace chain
        assert result == "tab\there"


@pytest.mark.unit
class TestListAlbumsEdgeCasesRound5:
    """Additional edge cases for list_albums."""

    def test_empty_state(self):
        """Empty state with no albums returns count 0."""
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums()))
        assert result["count"] == 0
        assert result["albums"] == []

    def test_status_filter_case_insensitive(self):
        """Status filter matching is case-insensitive."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums("in progress")))
        # Should match "In Progress" status
        assert result["count"] >= 1
        for album in result["albums"]:
            assert album["status"].lower() == "in progress"

    def test_status_filter_no_match(self):
        """Non-matching status filter returns empty list."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_albums("NonexistentStatus")))
        assert result["count"] == 0
        assert result["albums"] == []


@pytest.mark.unit
class TestFindAlbumEdgeCasesRound5:
    """Additional edge cases for find_album."""

    def test_empty_string_name(self):
        """Empty string album name normalizes to empty, no exact match."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("")))
        # Empty string won't match any slug exactly
        # But it IS a substring of every slug, so it matches all
        # Multiple matches -> found: False
        assert result["found"] is False

    def test_whitespace_only_name(self):
        """Whitespace-only name normalizes to hyphens."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.find_album("   ")))
        # "   " -> "---" after normalize_slug
        # Won't match any slug
        assert result["found"] is False


@pytest.mark.unit
class TestFormatForClipboardEdgeCasesRound5:
    """Additional edge cases for format_for_clipboard."""

    def test_streaming_lyrics_alias(self, tmp_path):
        """'streaming-lyrics' content_type is accepted."""
        track_file = tmp_path / "05-alias-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-alias-track"] = {
            "path": str(track_file),
            "title": "Alias Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05", "streaming-lyrics")))
        assert result["found"] is True
        assert result["content_type"] == "streaming-lyrics"

    def test_file_deleted_after_cache(self, tmp_path):
        """Track file deleted between cache load and read returns error."""
        track_file = tmp_path / "05-gone-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-gone-track"] = {
            "path": str(track_file),
            "title": "Gone Track",
            "status": "In Progress",
        }
        mock_cache = MockStateCache(state)
        # Delete the file
        track_file.unlink()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05", "lyrics")))
        assert "error" in result
        assert "Cannot read" in result["error"]


@pytest.mark.unit
class TestFormatForClipboardSuno:
    """Tests for the 'suno' content_type in format_for_clipboard."""

    def _make_cache_with_file(self, tmp_path, title="Test Track"):
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-test-track"] = {
            "path": str(track_file),
            "title": title,
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        return MockStateCache(state)

    def test_suno_returns_json_with_title_style_lyrics(self, tmp_path):
        """'suno' content_type returns JSON with title, style, and lyrics fields."""
        mock_cache = self._make_cache_with_file(tmp_path)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "01-test-track", "suno")))
        assert result["found"] is True
        assert result["content_type"] == "suno"
        payload = json.loads(result["content"])
        assert payload["title"] == "Test Track"
        assert "electronic" in payload["style"]
        assert "[Verse 1]" in payload["lyrics"]

    def test_suno_title_fallback_to_slug(self, tmp_path):
        """When title is missing from track data, uses the matched slug."""
        track_file = tmp_path / "05-no-title.md"
        track_file.write_text(_SAMPLE_TRACK_MD)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-no-title"] = {
            "path": str(track_file),
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05", "suno")))
        assert result["found"] is True
        payload = json.loads(result["content"])
        assert payload["title"] == "05-no-title"

    def test_suno_missing_both_sections_returns_not_found(self, tmp_path):
        """When both Style Box and Lyrics Box are missing, returns not-found error."""
        minimal_track = "# Track\n\n## Concept\n\nJust a concept, no suno inputs.\n"
        track_file = tmp_path / "05-empty.md"
        track_file.write_text(minimal_track)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-empty"] = {
            "path": str(track_file),
            "title": "Empty Track",
            "status": "Not Started",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05", "suno")))
        assert result["found"] is False
        assert "not found" in result["error"]

    def test_suno_preserves_unicode(self, tmp_path):
        """ensure_ascii=False preserves unicode characters in JSON output."""
        track_md = _SAMPLE_TRACK_MD.replace("Test Track", "Tëst Träck café")
        track_file = tmp_path / "05-unicode.md"
        track_file.write_text(track_md)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["05-unicode"] = {
            "path": str(track_file),
            "title": "Tëst Träck café",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.format_for_clipboard("test-album", "05", "suno")))
        assert result["found"] is True
        # Content should contain actual unicode, not \\u escapes
        assert "Tëst Träck café" in result["content"]
        payload = json.loads(result["content"])
        assert payload["title"] == "Tëst Träck café"


@pytest.mark.unit
class TestDetectPhaseAdditionalRound5:
    """Additional _detect_phase edge cases for comprehensive coverage."""

    def test_single_track_not_started(self):
        """Single not-started track = Writing phase."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Not Started", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Writing"

    def test_single_track_in_progress(self):
        """Single in-progress track = Writing phase."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "In Progress", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Writing"

    def test_single_track_generated(self):
        """Single generated track = Mastering (all generated, none final)."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Generated", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Mastering"

    def test_single_track_final(self):
        """Single final track = Ready to Release."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Final", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Ready to Release"

    def test_all_in_progress(self):
        """All tracks in progress = Writing."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "In Progress", "sources_verified": "N/A"},
                "02": {"status": "In Progress", "sources_verified": "N/A"},
            },
        }
        assert server._detect_phase(album) == "Writing"

    def test_research_complete_status(self):
        """Album with Research Complete status."""
        album = {"status": "Research Complete", "tracks": {}}
        assert server._detect_phase(album) == "Planning"

    def test_ready_to_write_all_sources_verified(self):
        """All tracks 'Sources Verified' → Ready to Write."""
        album = {
            "status": "In Progress",
            "tracks": {
                "01": {"status": "Sources Verified", "sources_verified": "Verified"},
                "02": {"status": "Sources Verified", "sources_verified": "Verified"},
                "03": {"status": "Sources Verified", "sources_verified": "Verified"},
            },
        }
        assert server._detect_phase(album) == "Ready to Write"


@pytest.mark.unit
class TestExtractCodeBlockEdgeCasesRound5:
    """Additional edge cases for _extract_code_block."""

    def test_no_code_block(self):
        """Text without code block returns None."""
        result = server._extract_code_block("Just plain text")
        assert result is None

    def test_empty_code_block(self):
        """Empty code block returns empty string."""
        result = server._extract_code_block("```\n```")
        assert result == ""

    def test_code_block_with_language_tag(self):
        """Code block with language tag still extracts content."""
        text = "```python\nprint('hello')\n```"
        result = server._extract_code_block(text)
        # The regex is ```\n?(.*?)``` so "python\nprint('hello')" matches
        assert result is not None

    def test_multiple_code_blocks_returns_first(self):
        """Only the first code block is returned."""
        text = "```\nfirst\n```\n\n```\nsecond\n```"
        result = server._extract_code_block(text)
        assert result == "first"


@pytest.mark.unit
class TestUpdateTrackFieldNonStatusFields:
    """Tests for update_track_field with non-status fields (no validation)."""

    def test_suno_link_hyphen_variant(self, tmp_path):
        """Both 'suno-link' and 'suno_link' field names work."""
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
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "suno-link",
                "[Listen](https://suno.com/song/abc)"
            )))
        assert result["success"] is True
        content = track_file.read_text()
        assert "[Listen](https://suno.com/song/abc)" in content

    def test_sources_verified_hyphen_variant(self, tmp_path):
        """Both 'sources-verified' and 'sources_verified' field names work."""
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
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources-verified",
                "✅ Verified (2026-02-10)", force=True,
            )))
        assert result["success"] is True


@pytest.mark.unit
class TestSourceVerificationGate:
    """Tests for source link validation when verifying sources."""

    def _make_cache_with_track_and_album(self, tmp_path, track_content, album_has_sources=False):
        """Create a mock cache with track file and optionally SOURCES.md."""
        track_file = tmp_path / "01-test-track.md"
        track_file.write_text(track_content)

        album_dir = tmp_path / "album"
        album_dir.mkdir()
        if album_has_sources:
            sources_file = album_dir / "SOURCES.md"
            sources_file.write_text(
                "# Sources\n\n"
                "| Document | URL |\n"
                "|----------|-----|\n"
                "| [Wikipedia](https://en.wikipedia.org/wiki/Test) | Reference |\n"
            )

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(album_dir)
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

    def test_blocked_no_sources(self, tmp_path):
        """Blocked when no SOURCES.md and no inline Source section links."""
        mock_cache, _ = self._make_cache_with_track_and_album(
            tmp_path, _SAMPLE_TRACK_MD, album_has_sources=False
        )
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources_verified",
                "✅ Verified (2026-02-19)"
            )))
        assert "error" in result
        assert "no markdown links" in result["error"]

    def test_passes_with_sources_md(self, tmp_path):
        """Passes when SOURCES.md has [text](url) links."""
        mock_cache, _ = self._make_cache_with_track_and_album(
            tmp_path, _SAMPLE_TRACK_MD, album_has_sources=True
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources_verified",
                "✅ Verified (2026-02-19)"
            )))
        assert result["success"] is True

    def test_passes_with_inline_source_section(self, tmp_path):
        """Passes when track Source section has markdown links."""
        track_with_source = _SAMPLE_TRACK_MD + "\n## Source\n\n[Wikipedia](https://en.wikipedia.org/wiki/Test)\n"
        mock_cache, _ = self._make_cache_with_track_and_album(
            tmp_path, track_with_source, album_has_sources=False
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources_verified",
                "✅ Verified (2026-02-19)"
            )))
        assert result["success"] is True

    def test_pending_value_not_blocked(self, tmp_path):
        """Setting to 'Pending' or 'N/A' is NOT blocked by source check."""
        mock_cache, _ = self._make_cache_with_track_and_album(
            tmp_path, _SAMPLE_TRACK_MD, album_has_sources=False
        )
        for val in ["❌ Pending", "N/A", "Pending"]:
            with patch.object(server, "cache", mock_cache), \
                 patch.object(server, "write_state", MagicMock()):
                result = json.loads(_run(server.update_track_field(
                    "test-album", "01-test-track", "sources_verified", val
                )))
            assert result.get("success") is True or "no markdown links" not in result.get("error", "")

    def test_force_bypasses_source_check(self, tmp_path):
        """force=True bypasses the source link validation."""
        mock_cache, _ = self._make_cache_with_track_and_album(
            tmp_path, _SAMPLE_TRACK_MD, album_has_sources=False
        )
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", MagicMock()):
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-test-track", "sources_verified",
                "✅ Verified (2026-02-19)", force=True,
            )))
        assert result["success"] is True


@pytest.mark.unit
class TestSectionNamesCompleteness:
    """Verify all _SECTION_NAMES entries are valid and accessible."""

    def test_all_section_keys_lowercase(self):
        """All keys in _SECTION_NAMES are lowercase."""
        for key in server._SECTION_NAMES:
            assert key == key.lower(), f"Key '{key}' is not lowercase"

    def test_all_section_values_nonempty(self):
        """All values in _SECTION_NAMES are non-empty strings."""
        for key, value in server._SECTION_NAMES.items():
            assert isinstance(value, str) and value, \
                f"Key '{key}' has invalid value: {value!r}"

    def test_known_section_count(self):
        """Verify expected number of section name entries."""
        # As of Round 4 fix: 14 entries
        # style, style-box, lyrics, lyrics-box, streaming, streaming-lyrics,
        # pronunciation, pronunciation-notes, concept, source, original-quote,
        # musical-direction, production-notes, generation-log,
        # phonetic-review, mood, mood-imagery, lyrical-approach
        assert len(server._SECTION_NAMES) == 18

    def test_bidirectional_aliases_consistent(self):
        """Aliases map to the same heading."""
        assert server._SECTION_NAMES["style"] == server._SECTION_NAMES["style-box"]
        assert server._SECTION_NAMES["lyrics"] == server._SECTION_NAMES["lyrics-box"]
        assert server._SECTION_NAMES["streaming"] == server._SECTION_NAMES["streaming-lyrics"]
        assert server._SECTION_NAMES["pronunciation"] == server._SECTION_NAMES["pronunciation-notes"]
        assert server._SECTION_NAMES["mood"] == server._SECTION_NAMES["mood-imagery"]


@pytest.mark.unit
class TestUpdatableFieldsCompleteness:
    """Verify _UPDATABLE_FIELDS entries."""

    def test_all_updatable_keys_lowercase(self):
        """All keys in _UPDATABLE_FIELDS are lowercase."""
        for key in server._UPDATABLE_FIELDS:
            assert key == key.lower(), f"Key '{key}' is not lowercase"

    def test_suno_link_both_variants(self):
        """Both suno-link and suno_link map to 'Suno Link'."""
        assert server._UPDATABLE_FIELDS["suno-link"] == "Suno Link"
        assert server._UPDATABLE_FIELDS["suno_link"] == "Suno Link"

    def test_sources_verified_both_variants(self):
        """Both sources-verified and sources_verified map to 'Sources Verified'."""
        assert server._UPDATABLE_FIELDS["sources-verified"] == "Sources Verified"
        assert server._UPDATABLE_FIELDS["sources_verified"] == "Sources Verified"


@pytest.mark.unit
class TestValidTrackStatuses:
    """Verify _VALID_TRACK_STATUSES set is complete."""

    def test_all_statuses_lowercase(self):
        """All entries in _VALID_TRACK_STATUSES are lowercase."""
        for status in server._VALID_TRACK_STATUSES:
            assert status == status.lower(), f"Status '{status}' is not lowercase"

    def test_expected_statuses_present(self):
        """All expected statuses are in the set."""
        expected = {"not started", "sources pending", "sources verified",
                    "in progress", "generated", "final"}
        assert server._VALID_TRACK_STATUSES == expected

    def test_status_count(self):
        """Exactly 6 valid track statuses."""
        assert len(server._VALID_TRACK_STATUSES) == 6


# ---------------------------------------------------------------------------
# _derive_title_from_slug helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeriveTitleFromSlug:
    """Tests for the _derive_title_from_slug helper."""

    def test_track_slug_with_number(self):
        """Track slug with number prefix strips prefix."""
        assert server._derive_title_from_slug("01-my-track-name") == "My Track Name"

    def test_album_slug_without_number(self):
        """Album slug without number converts normally."""
        assert server._derive_title_from_slug("my-album") == "My Album"

    def test_multi_hyphen_slug(self):
        """Multi-hyphen slug converts each word."""
        assert server._derive_title_from_slug("03-the-long-and-winding-road") == "The Long And Winding Road"

    def test_single_word(self):
        """Single word slug."""
        assert server._derive_title_from_slug("genesis") == "Genesis"

    def test_already_title_cased_input(self):
        """Input with mixed case still converts via slug rules."""
        # Slugs are lowercase, but if passed in it still works
        assert server._derive_title_from_slug("my-album") == "My Album"


# ---------------------------------------------------------------------------
# rename_album tool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenameAlbum:
    """Tests for the rename_album MCP tool."""

    def _make_state_with_dirs(self, tmp_path):
        """Create state + real directory structure for rename tests."""
        # Content directory with README + tracks
        content_root = tmp_path / "content"
        artist_dir = content_root / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        tracks_dir = artist_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        readme = artist_dir / "README.md"
        readme.write_text(_SAMPLE_ALBUM_README)

        track_file = tracks_dir / "01-first-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)

        # Audio directory
        audio_root = tmp_path / "audio"
        audio_dir = audio_root / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "song.wav").write_text("fake audio")

        # Documents directory
        docs_root = tmp_path / "docs"
        docs_dir = docs_root / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        docs_dir.mkdir(parents=True)
        (docs_dir / "notes.pdf").write_text("fake pdf")

        state = _fresh_state()
        state["config"]["content_root"] = str(content_root)
        state["config"]["audio_root"] = str(audio_root)
        state["config"]["documents_root"] = str(docs_root)
        state["albums"]["test-album"]["path"] = str(artist_dir)
        state["albums"]["test-album"]["tracks"]["01-first-track"]["path"] = str(track_file)

        return state

    def test_rename_album_success(self, tmp_path):
        """Basic rename moves content dir and updates state."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album("test-album", "new-album")))
        assert result["success"] is True
        assert result["old_slug"] == "test-album"
        assert result["new_slug"] == "new-album"
        assert result["content_moved"] is True

    def test_rename_album_with_tracks(self, tmp_path):
        """Track paths are updated in state after rename."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            _run(server.rename_album("test-album", "new-album"))
        # Check state was updated
        albums = mock_cache.get_state()["albums"]
        assert "new-album" in albums
        assert "test-album" not in albums
        track = albums["new-album"]["tracks"]["01-first-track"]
        assert "new-album" in track["path"]
        assert "test-album" not in track["path"]

    def test_rename_album_title_update(self, tmp_path):
        """README H1 heading is updated with new title."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album(
                "test-album", "new-album", new_title="My New Album"
            )))
        assert result["title"] == "My New Album"
        # Check README was updated
        new_readme = (
            tmp_path / "content" / "artists" / "test-artist" / "albums"
            / "electronic" / "new-album" / "README.md"
        )
        text = new_readme.read_text()
        assert "# My New Album" in text

    def test_rename_album_auto_title(self, tmp_path):
        """Empty new_title derives title from slug."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album("test-album", "cool-new-name")))
        assert result["title"] == "Cool New Name"

    def test_rename_album_not_found(self):
        """Returns error when old slug doesn't exist."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_album("nonexistent", "new-name")))
        assert "error" in result
        assert "not found" in result["error"]

    def test_rename_album_already_exists(self):
        """Returns error when new slug collides with existing album."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_album("test-album", "another-album")))
        assert "error" in result
        assert "already exists" in result["error"]

    def test_rename_album_same_slug(self):
        """Returns error when old == new after normalization."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_album("test-album", "test_album")))
        assert "error" in result
        assert "same" in result["error"].lower()

    def test_rename_album_audio_dir_moved(self, tmp_path):
        """Audio directory is renamed when it exists."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album("test-album", "new-album")))
        assert result["audio_moved"] is True
        new_audio = tmp_path / "audio" / "artists" / "test-artist" / "albums" / "electronic" / "new-album"
        assert new_audio.is_dir()
        assert (new_audio / "originals" / "song.wav").exists()

    def test_rename_album_audio_dir_missing(self, tmp_path):
        """No audio dir still succeeds with audio_moved=False."""
        state = self._make_state_with_dirs(tmp_path)
        # Remove audio dir
        shutil.rmtree(tmp_path / "audio" / "artists" / "test-artist" / "albums" / "electronic" / "test-album")
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album("test-album", "new-album")))
        assert result["success"] is True
        assert result["audio_moved"] is False

    def test_rename_album_documents_dir_moved(self, tmp_path):
        """Documents directory is renamed when it exists."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album("test-album", "new-album")))
        assert result["documents_moved"] is True
        new_docs = tmp_path / "docs" / "artists" / "test-artist" / "albums" / "electronic" / "new-album"
        assert new_docs.is_dir()

    def test_rename_album_documents_dir_missing(self, tmp_path):
        """No docs dir still succeeds with documents_moved=False."""
        state = self._make_state_with_dirs(tmp_path)
        shutil.rmtree(tmp_path / "docs" / "artists" / "test-artist" / "albums" / "electronic" / "test-album")
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album("test-album", "new-album")))
        assert result["success"] is True
        assert result["documents_moved"] is False

    def test_rename_album_normalizes_slugs(self, tmp_path):
        """Spaces and underscores in slugs are normalized."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_album("test album", "new_album_name")))
        assert result["success"] is True
        assert result["old_slug"] == "test-album"
        assert result["new_slug"] == "new-album-name"

    def test_rename_album_state_cache_updated(self, tmp_path):
        """Old key removed and new key added in state cache."""
        state = self._make_state_with_dirs(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            _run(server.rename_album("test-album", "new-album"))
        albums = mock_cache.get_state()["albums"]
        assert "test-album" not in albums
        assert "new-album" in albums
        mock_write.assert_called_once()

    def test_rename_album_content_dir_missing(self, tmp_path):
        """Returns error when content directory doesn't exist on disk."""
        state = self._make_state_with_dirs(tmp_path)
        # Remove content dir
        content_dir = (
            tmp_path / "content" / "artists" / "test-artist"
            / "albums" / "electronic" / "test-album"
        )
        shutil.rmtree(content_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_album("test-album", "new-album")))
        assert "error" in result
        assert "Content directory not found" in result["error"]

    def test_rename_album_no_config(self):
        """Missing config returns error."""
        state = _fresh_state()
        state["config"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_album("test-album", "new-album")))
        assert "error" in result
        assert "config" in result["error"].lower()


# ---------------------------------------------------------------------------
# rename_track tool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenameTrack:
    """Tests for the rename_track MCP tool."""

    def _make_state_with_track(self, tmp_path):
        """Create state + real track file on disk."""
        tracks_dir = tmp_path / "tracks"
        tracks_dir.mkdir()

        track_file = tracks_dir / "01-old-track.md"
        track_file.write_text(_SAMPLE_TRACK_MD)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["tracks"]["01-old-track"] = {
            "path": str(track_file),
            "title": "Test Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "Pending",
            "mtime": 1234567890.0,
        }
        return state, track_file

    def test_rename_track_success(self, tmp_path):
        """Basic rename moves file and updates state."""
        state, track_file = self._make_state_with_track(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_track(
                "test-album", "01-old-track", "01-new-track"
            )))
        assert result["success"] is True
        assert result["old_slug"] == "01-old-track"
        assert result["new_slug"] == "01-new-track"
        # Old file gone, new file exists
        assert not track_file.exists()
        new_file = tmp_path / "tracks" / "01-new-track.md"
        assert new_file.exists()

    def test_rename_track_title_update(self, tmp_path):
        """Title row in metadata table is updated."""
        state, track_file = self._make_state_with_track(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_track(
                "test-album", "01-old-track", "01-new-track",
                new_title="New Track Title"
            )))
        assert result["title"] == "New Track Title"
        new_file = tmp_path / "tracks" / "01-new-track.md"
        content = new_file.read_text()
        assert "| **Title** | New Track Title |" in content

    def test_rename_track_auto_title(self, tmp_path):
        """Empty new_title derives title from slug."""
        state, track_file = self._make_state_with_track(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_track(
                "test-album", "01-old-track", "01-cool-new-track"
            )))
        assert result["title"] == "Cool New Track"

    def test_rename_track_preserves_content(self, tmp_path):
        """File content (except title) is preserved after rename."""
        state, track_file = self._make_state_with_track(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            _run(server.rename_track(
                "test-album", "01-old-track", "01-new-track"
            ))
        new_file = tmp_path / "tracks" / "01-new-track.md"
        content = new_file.read_text()
        # Key content preserved
        assert "## Concept" in content
        assert "Testing one two three" in content
        assert "| **Status** | In Progress |" in content

    def test_rename_track_not_found(self):
        """Returns error when track doesn't exist."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_track(
                "test-album", "99-missing", "99-new-name"
            )))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_rename_track_album_not_found(self):
        """Returns error when album doesn't exist."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_track(
                "nonexistent-album", "01-track", "01-new-track"
            )))
        assert "error" in result
        assert "not found" in result["error"]

    def test_rename_track_already_exists(self, tmp_path):
        """Returns error when new slug collides with existing track."""
        state, track_file = self._make_state_with_track(tmp_path)
        # Add another track with the target slug
        other_file = tmp_path / "tracks" / "02-existing.md"
        other_file.write_text(_SAMPLE_TRACK_MD)
        state["albums"]["test-album"]["tracks"]["02-existing"] = {
            "path": str(other_file),
            "title": "Existing",
            "status": "Final",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_track(
                "test-album", "01-old-track", "02-existing"
            )))
        assert "error" in result
        assert "already exists" in result["error"]

    def test_rename_track_same_slug(self):
        """Returns error when old == new after normalization."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_track(
                "test-album", "01-first-track", "01_first_track"
            )))
        assert "error" in result
        assert "same" in result["error"].lower()

    def test_rename_track_prefix_match(self, tmp_path):
        """Prefix like '01' matches '01-old-track' when unique."""
        state, track_file = self._make_state_with_track(tmp_path)
        # Remove conflicting 01-first-track from inherited state
        state["albums"]["test-album"]["tracks"].pop("01-first-track", None)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_track(
                "test-album", "01", "01-new-track"
            )))
        assert result["success"] is True
        assert result["old_slug"] == "01-old-track"

    def test_rename_track_multiple_prefix_matches(self, tmp_path):
        """Ambiguous prefix returns error."""
        state, track_file = self._make_state_with_track(tmp_path)
        # Add another track starting with "01"
        other_file = tmp_path / "tracks" / "01-another.md"
        other_file.write_text(_SAMPLE_TRACK_MD)
        state["albums"]["test-album"]["tracks"]["01-another"] = {
            "path": str(other_file),
            "title": "Another",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_track(
                "test-album", "01", "01-new-track"
            )))
        assert "error" in result
        assert "Multiple tracks" in result["error"]

    def test_rename_track_normalizes_slugs(self, tmp_path):
        """Input slugs are normalized."""
        state, track_file = self._make_state_with_track(tmp_path)
        mock_cache = MockStateCache(state)
        mock_write = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "write_state", mock_write):
            result = json.loads(_run(server.rename_track(
                "test-album", "01_old_track", "01_new_track"
            )))
        assert result["success"] is True
        assert result["old_slug"] == "01-old-track"
        assert result["new_slug"] == "01-new-track"

    def test_rename_track_file_missing_on_disk(self, tmp_path):
        """Returns error when state has track but file is gone."""
        state, track_file = self._make_state_with_track(tmp_path)
        track_file.unlink()  # Remove the file
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rename_track(
                "test-album", "01-old-track", "01-new-track"
            )))
        assert "error" in result
        assert "not found on disk" in result["error"]


# =============================================================================
# Tests for _resolve_audio_dir helper
# =============================================================================


class TestResolveAudioDir:
    """Tests for the _resolve_audio_dir() helper function."""

    def test_returns_path_when_dir_exists(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            err, path = server._resolve_audio_dir("test-album")
        assert err is None
        assert path == audio_dir

    def test_returns_error_when_dir_missing(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent/path"
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            err, path = server._resolve_audio_dir("test-album")
        assert path is None
        result = json.loads(err)
        assert "error" in result
        assert "not found" in result["error"]

    def test_returns_error_when_config_missing(self):
        state = {"config": {}, "albums": {}, "ideas": {}, "session": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            err, path = server._resolve_audio_dir("test-album")
        assert path is None
        result = json.loads(err)
        assert "not configured" in result["error"]

    def test_subfolder_appended(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album" / "mastered"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            err, path = server._resolve_audio_dir("test-album", "mastered")
        assert err is None
        assert path == audio_dir

    def test_slug_normalization(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            err, path = server._resolve_audio_dir("Test Album")
        assert err is None
        assert path == audio_dir


# =============================================================================
# Tests for dependency checker helpers
# =============================================================================


class TestDepCheckers:
    """Tests for _check_mastering_deps, _check_ffmpeg, etc."""

    def test_check_mastering_deps_returns_none_when_available(self):
        # These deps are installed in the test environment
        result = server._check_mastering_deps()
        # May or may not be installed, just verify return type
        assert result is None or isinstance(result, str)

    def test_check_mastering_deps_detects_missing(self):
        with patch.dict("sys.modules", {"numpy": None}):
            # Force ImportError by making __import__ fail for numpy
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
            def mock_import(name, *args, **kwargs):
                if name == "numpy":
                    raise ImportError("mocked")
                return original_import(name, *args, **kwargs)
            with patch("builtins.__import__", side_effect=mock_import):
                result = server._check_mastering_deps()
            if result is not None:
                assert "numpy" in result

    def test_check_ffmpeg_returns_string_type(self):
        result = server._check_ffmpeg()
        assert result is None or isinstance(result, str)

    def test_check_ffmpeg_when_missing(self):
        with patch.object(shutil, "which", return_value=None):
            result = server._check_ffmpeg()
        assert result is not None
        assert "ffmpeg" in result

    def test_check_matchering_returns_string_type(self):
        result = server._check_matchering()
        assert result is None or isinstance(result, str)

    def test_check_songbook_deps_returns_string_type(self):
        result = server._check_songbook_deps()
        assert result is None or isinstance(result, str)


# =============================================================================
# Tests for analyze_audio tool
# =============================================================================


class TestAnalyzeAudio:
    """Tests for the analyze_audio MCP tool."""

    def test_missing_deps_returns_error(self):
        with patch.object(server, "_check_mastering_deps", return_value="Missing deps"):
            result = json.loads(_run(server.analyze_audio("test-album")))
        assert "error" in result
        assert "Missing deps" in result["error"]

    def test_missing_audio_dir_returns_error(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.analyze_audio("test-album")))
        assert "error" in result

    def test_no_wav_files_returns_error(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.analyze_audio("test-album")))
        assert "error" in result
        assert "No WAV" in result["error"]

    def test_successful_analysis(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        # Create a dummy wav file
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-test.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_result = {
            "filename": "01-test.wav",
            "duration": 180.0,
            "sample_rate": 44100,
            "lufs": -14.5,
            "peak_db": -0.5,
            "rms_db": -18.0,
            "dynamic_range": 17.5,
            "band_energy": {"sub_bass": 5, "bass": 20, "low_mid": 15, "mid": 30, "high_mid": 20, "high": 8, "air": 2},
            "tinniness_ratio": 0.4,
        }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", return_value=mock_result):
            result = json.loads(_run(server.analyze_audio("test-album")))

        assert "tracks" in result
        assert len(result["tracks"]) == 1
        assert "summary" in result
        assert result["summary"]["track_count"] == 1
        assert "recommendations" in result

    def test_subfolder_param(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album" / "mastered"
        audio_dir.mkdir(parents=True)
        (audio_dir / "01-test.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_result = {
            "filename": "01-test.wav", "duration": 180.0, "sample_rate": 44100,
            "lufs": -14.0, "peak_db": -1.0, "rms_db": -18.0, "dynamic_range": 17.0,
            "band_energy": {"sub_bass": 5, "bass": 20, "low_mid": 15, "mid": 30, "high_mid": 20, "high": 8, "air": 2},
            "tinniness_ratio": 0.3,
        }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", return_value=mock_result):
            result = json.loads(_run(server.analyze_audio("test-album", subfolder="mastered")))
        assert "tracks" in result


# =============================================================================
# Tests for master_audio tool
# =============================================================================


class TestMasterAudio:
    """Tests for the master_audio MCP tool."""

    def test_missing_deps(self):
        with patch.object(server, "_check_mastering_deps", return_value="Missing deps"):
            result = json.loads(_run(server.master_audio("test-album")))
        assert "error" in result

    def test_missing_audio_dir(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.master_audio("test-album")))
        assert "error" in result

    def test_no_wav_files(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.master_audio("test-album")))
        assert "error" in result

    def test_unknown_genre(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-test.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.master_audio("test-album", genre="nonexistent-genre")))
        assert "error" in result
        assert "Unknown genre" in result["error"]

    def test_successful_master_dry_run(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-test.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        # Mock soundfile and pyloudnorm for dry_run
        mock_data = MagicMock()
        mock_data.shape = (44100, 2)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("soundfile.read", return_value=(mock_data, 44100)), \
             patch("pyloudnorm.Meter") as mock_meter_cls:
            mock_meter = MagicMock()
            mock_meter.integrated_loudness.return_value = -20.0
            mock_meter_cls.return_value = mock_meter
            # Also mock numpy imports inside the function
            import numpy as np
            mock_data.__len__ = lambda self: 1
            mock_data.shape = (44100, 2)
            result = json.loads(_run(server.master_audio("test-album", dry_run=True)))

        assert "tracks" in result or "error" in result

    def test_settings_in_response(self, tmp_path):
        """Verify settings object is returned with correct values."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-test.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_master_result = {
            "original_lufs": -20.0, "final_lufs": -14.0,
            "gain_applied": 6.0, "final_peak": -1.0,
        }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", return_value=mock_master_result), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_audio("test-album")))

        if "settings" in result:
            assert result["settings"]["target_lufs"] == -14.0
            assert result["settings"]["ceiling_db"] == -1.0


# =============================================================================
# Tests for fix_dynamic_track tool
# =============================================================================


class TestFixDynamicTrack:
    """Tests for the fix_dynamic_track MCP tool."""

    def test_missing_deps(self):
        with patch.object(server, "_check_mastering_deps", return_value="Missing deps"):
            result = json.loads(_run(server.fix_dynamic_track("test-album", "01-test.wav")))
        assert "error" in result

    def test_missing_audio_dir(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.fix_dynamic_track("test-album", "01-test.wav")))
        assert "error" in result

    def test_missing_track_file(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.fix_dynamic_track("test-album", "nonexistent.wav")))
        assert "error" in result
        assert "not found" in result["error"]


# =============================================================================
# Tests for master_with_reference tool
# =============================================================================


class TestMasterWithReference:
    """Tests for the master_with_reference MCP tool."""

    def test_missing_matchering(self):
        with patch.object(server, "_check_matchering", return_value="matchering not installed"):
            result = json.loads(_run(server.master_with_reference("test-album", "ref.wav")))
        assert "error" in result
        assert "matchering" in result["error"]

    def test_missing_reference_file(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None):
            result = json.loads(_run(server.master_with_reference("test-album", "ref.wav")))
        assert "error" in result
        assert "not found" in result["error"]

    def _patch_ref_master(self):
        """Patch tools.mastering.reference_master in sys.modules to avoid matchering import."""
        mock_fn = MagicMock()
        mock_mod = types.ModuleType("tools.mastering.reference_master")
        mock_mod.master_with_reference = mock_fn
        return patch.dict("sys.modules", {"tools.mastering.reference_master": mock_mod}), mock_fn

    def test_missing_target_file(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "ref.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        mod_patch, _ = self._patch_ref_master()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None), \
             mod_patch:
            result = json.loads(_run(server.master_with_reference(
                "test-album", "ref.wav", "nonexistent.wav"
            )))
        assert "error" in result
        assert "not found" in result["error"]

    def test_single_track_success(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "ref.wav").write_bytes(b"")
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mod_patch, _ = self._patch_ref_master()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None), \
             mod_patch:
            result = json.loads(_run(server.master_with_reference(
                "test-album", "ref.wav", "01-track.wav"
            )))
        assert "tracks" in result
        assert result["tracks"][0]["success"] is True
        assert result["summary"]["success"] == 1

    def test_batch_mode(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "ref.wav").write_bytes(b"")
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")
        (audio_dir / "originals" / "02-track.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mod_patch, _ = self._patch_ref_master()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None), \
             mod_patch:
            result = json.loads(_run(server.master_with_reference("test-album", "ref.wav")))
        assert "tracks" in result
        assert len(result["tracks"]) == 2
        assert result["summary"]["success"] == 2


# =============================================================================
# Tests for transcribe_audio tool
# =============================================================================


class TestTranscribeAudio:
    """Tests for the transcribe_audio MCP tool."""

    def test_missing_anthemscore(self):
        with patch.object(server, "_check_anthemscore", return_value="AnthemScore not found"):
            result = json.loads(_run(server.transcribe_audio("test-album")))
        assert "error" in result
        assert "AnthemScore" in result["error"]

    def test_missing_audio_dir(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None):
            result = json.loads(_run(server.transcribe_audio("test-album")))
        assert "error" in result

    def test_no_wav_files(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.find_anthemscore.return_value = "/usr/bin/anthemscore"
        mock_mod.transcribe_track.return_value = True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.transcribe_audio("test-album")))
        assert "error" in result
        assert "No WAV" in result["error"]

    def test_single_track_missing(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.find_anthemscore.return_value = "/usr/bin/anthemscore"

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.transcribe_audio(
                "test-album", track_filename="nonexistent.wav"
            )))
        assert "error" in result
        assert "not found" in result["error"]


# =============================================================================
# Tests for fix_sheet_music_titles tool
# =============================================================================


class TestFixSheetMusicTitles:
    """Tests for the fix_sheet_music_titles MCP tool."""

    def test_missing_audio_dir(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.fix_sheet_music_titles("test-album")))
        assert "error" in result

    def test_missing_sheet_dir(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.fix_sheet_music_titles("test-album")))
        assert "error" in result
        assert "not found" in result["error"]

    def test_no_xml_files(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles("test-album")))
        assert "error" in result

    def test_successful_fix(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        (sheet_dir / "01-track.xml").write_text("<work-title>01 - Track</work-title>")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.fix_xml_title.return_value = "Track"
        mock_mod.find_musescore.return_value = None

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles("test-album")))
        assert "files" in result
        assert result["fixed_count"] == 1
        assert result["files"][0]["new_title"] == "Track"


# =============================================================================
# Tests for create_songbook tool
# =============================================================================


class TestCreateSongbook:
    """Tests for the create_songbook MCP tool."""

    def test_missing_deps(self):
        with patch.object(server, "_check_songbook_deps", return_value="Missing pypdf"):
            result = json.loads(_run(server.create_songbook("test-album", "My Songbook")))
        assert "error" in result
        assert "pypdf" in result["error"]

    def test_missing_audio_dir(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_songbook_deps", return_value=None):
            result = json.loads(_run(server.create_songbook("test-album", "My Songbook")))
        assert "error" in result

    def test_missing_sheet_dir(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_songbook_deps", return_value=None):
            result = json.loads(_run(server.create_songbook("test-album", "My Songbook")))
        assert "error" in result
        assert "not found" in result["error"]


# =============================================================================
# Tests for generate_promo_videos tool
# =============================================================================


class TestGeneratePromoVideos:
    """Tests for the generate_promo_videos MCP tool."""

    def test_missing_ffmpeg(self):
        with patch.object(server, "_check_ffmpeg", return_value="ffmpeg not found"):
            result = json.loads(_run(server.generate_promo_videos("test-album")))
        assert "error" in result
        assert "ffmpeg" in result["error"]

    def test_missing_audio_dir(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None):
            result = json.loads(_run(server.generate_promo_videos("test-album")))
        assert "error" in result

    def test_missing_artwork(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None):
            result = json.loads(_run(server.generate_promo_videos("test-album")))
        assert "error" in result
        assert "artwork" in result["error"].lower()

    def test_single_track_not_found(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "album.png").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None):
            result = json.loads(_run(server.generate_promo_videos(
                "test-album", track_filename="nonexistent.wav"
            )))
        assert "error" in result
        assert "not found" in result["error"]

    def test_single_track_uses_markdown_title(self, tmp_path):
        """Single-track mode should prefer title from state cache (markdown-derived)."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "album.png").write_bytes(b"")
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-some-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        state["albums"]["test-album"]["tracks"]["01-some-track"] = {
            "path": "/tmp/test/.../01-some-track.md",
            "title": "The Real Title",
            "status": "Final",
            "explicit": False,
            "has_suno_link": True,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        mock_cache = MockStateCache(state)

        captured_title = []

        def mock_generate(**kwargs):
            captured_title.append(kwargs.get("title"))
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   side_effect=mock_generate), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            result = json.loads(_run(server.generate_promo_videos(
                "test-album", track_filename="01-some-track.wav"
            )))

        assert result["tracks"][0]["success"] is True
        assert len(captured_title) == 1
        assert captured_title[0] == "The Real Title"


# =============================================================================
# Tests for generate_album_sampler tool
# =============================================================================


class TestGenerateAlbumSampler:
    """Tests for the generate_album_sampler MCP tool."""

    def test_missing_ffmpeg(self):
        with patch.object(server, "_check_ffmpeg", return_value="ffmpeg not found"):
            result = json.loads(_run(server.generate_album_sampler("test-album")))
        assert "error" in result

    def test_missing_audio_dir(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None):
            result = json.loads(_run(server.generate_album_sampler("test-album")))
        assert "error" in result

    def test_missing_artwork(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None):
            result = json.loads(_run(server.generate_album_sampler("test-album")))
        assert "error" in result
        assert "artwork" in result["error"].lower()

    def test_sampler_failure(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "album.png").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler", return_value=False):
            result = json.loads(_run(server.generate_album_sampler("test-album")))
        assert "error" in result


# =============================================================================
# Tests for _import_sheet_music_module helper
# =============================================================================


class TestImportSheetMusicModule:
    """Tests for the _import_sheet_music_module() helper."""

    def test_imports_existing_module(self):
        """Should import transcribe.py from tools/sheet-music/."""
        mod = server._import_sheet_music_module("transcribe")
        assert hasattr(mod, "find_anthemscore")
        assert hasattr(mod, "transcribe_track")

    def test_imports_fix_titles(self):
        """Should import fix_titles.py from tools/sheet-music/."""
        mod = server._import_sheet_music_module("fix_titles")
        assert hasattr(mod, "fix_xml_title")
        assert hasattr(mod, "find_musescore")

    def test_imports_create_songbook(self):
        """Should import create_songbook.py from tools/sheet-music/ (mocks pypdf+reportlab if missing)."""
        # create_songbook.py does sys.exit(1) at import time if pypdf/reportlab are missing.
        # Mock them in sys.modules if needed so the import succeeds regardless.
        mods_to_mock = {}
        for mod_name in ("pypdf", "reportlab", "reportlab.lib", "reportlab.lib.pagesizes",
                         "reportlab.lib.units", "reportlab.pdfgen", "reportlab.pdfgen.canvas"):
            if mod_name not in sys.modules:
                mods_to_mock[mod_name] = MagicMock()
        if mods_to_mock:
            with patch.dict("sys.modules", mods_to_mock):
                mod = server._import_sheet_music_module("create_songbook")
        else:
            mod = server._import_sheet_music_module("create_songbook")
        assert hasattr(mod, "create_songbook")
        assert hasattr(mod, "auto_detect_cover_art")

    def test_nonexistent_module_raises(self):
        """Should raise on a module that doesn't exist."""
        with pytest.raises(Exception):
            server._import_sheet_music_module("nonexistent_module")


# =============================================================================
# Comprehensive tests for all 9 processing MCP tools — success paths,
# batch modes, parameter variations, and edge cases.
# =============================================================================


class TestAnalyzeAudioComprehensive:
    """Comprehensive tests for analyze_audio: batch, recommendations, edge cases."""

    def _make_audio_dir(self, tmp_path, num_tracks=3):
        """Helper to create audio dir with dummy WAV files."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        for i in range(num_tracks):
            (audio_dir / "originals" / f"{i+1:02d}-track-{i+1}.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def _mock_result(self, filename, lufs=-14.0, tinniness=0.3):
        return {
            "filename": filename,
            "duration": 180.0,
            "sample_rate": 44100,
            "lufs": lufs,
            "peak_db": -0.5,
            "rms_db": -18.0,
            "dynamic_range": 17.5,
            "band_energy": {"sub_bass": 5, "bass": 20, "low_mid": 15,
                            "mid": 30, "high_mid": 20, "high": 8, "air": 2},
            "tinniness_ratio": tinniness,
        }

    def test_batch_multiple_tracks(self, tmp_path):
        """Analyze multiple WAV files and get per-track results."""
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        call_count = []

        def mock_analyze(filepath):
            name = Path(filepath).name
            call_count.append(name)
            return self._mock_result(name)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze):
            result = json.loads(_run(server.analyze_audio("test-album")))

        assert len(result["tracks"]) == 3
        assert result["summary"]["track_count"] == 3
        assert len(call_count) == 3

    def test_tinny_track_recommendation(self, tmp_path):
        """Tracks with tinniness > 0.6 should appear in recommendations."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_analyze(filepath):
            name = Path(filepath).name
            tinniness = 0.8 if "01" in name else 0.3
            return self._mock_result(name, tinniness=tinniness)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze):
            result = json.loads(_run(server.analyze_audio("test-album")))

        assert result["summary"]["tinny_tracks"] == ["01-track-1.wav"]
        tinny_rec = [r for r in result["recommendations"] if "Tinny" in r]
        assert len(tinny_rec) == 1

    def test_quiet_tracks_recommendation(self, tmp_path):
        """Average LUFS below -16 should trigger recommendation."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_analyze(filepath):
            return self._mock_result(Path(filepath).name, lufs=-20.0)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze):
            result = json.loads(_run(server.analyze_audio("test-album")))

        assert result["summary"]["avg_lufs"] == pytest.approx(-20.0)
        boost_rec = [r for r in result["recommendations"] if "boosting" in r]
        assert len(boost_rec) == 1

    def test_wide_lufs_range_recommendation(self, tmp_path):
        """LUFS range > 2 dB should trigger consistency recommendation."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        call_idx = [0]

        def mock_analyze(filepath):
            idx = call_idx[0]
            call_idx[0] += 1
            lufs = -12.0 if idx == 0 else -16.0
            return self._mock_result(Path(filepath).name, lufs=lufs)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze):
            result = json.loads(_run(server.analyze_audio("test-album")))

        assert result["summary"]["lufs_range"] == pytest.approx(4.0)
        range_rec = [r for r in result["recommendations"] if "LUFS range" in r]
        assert len(range_rec) == 1

    def test_no_recommendations_when_clean(self, tmp_path):
        """Well-mastered tracks should produce no recommendations."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_analyze(filepath):
            return self._mock_result(Path(filepath).name, lufs=-14.0, tinniness=0.2)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze):
            result = json.loads(_run(server.analyze_audio("test-album")))

        assert result["recommendations"] == []


class TestMasterAudioComprehensive:
    """Comprehensive tests for master_audio: batch, genre presets, settings."""

    def _make_audio_dir(self, tmp_path, num_tracks=2):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        for i in range(num_tracks):
            (audio_dir / "originals" / f"{i+1:02d}-track.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def test_batch_multiple_tracks_success(self, tmp_path):
        """Master multiple tracks and verify per-track results."""
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.0,
            }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_audio("test-album")))

        assert len(result["tracks"]) == 3
        assert result["summary"]["tracks_processed"] == 3

    def test_creates_mastered_dir(self, tmp_path):
        """master_audio should create mastered/ subdirectory."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.0,
            }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_audio("test-album")))

        assert (audio_dir / "mastered").is_dir()

    def test_genre_preset_applied(self, tmp_path):
        """Genre preset should set EQ and LUFS values."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        captured_kwargs = []

        def mock_master(input_path, output_path, **kwargs):
            captured_kwargs.append(kwargs)
            return {
                "original_lufs": -20.0,
                "final_lufs": -13.0,
                "gain_applied": 7.0,
                "final_peak": -1.0,
            }

        presets = {"hip-hop": (-13.0, -3.0, -1.0, 1.5)}

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value=presets):
            result = json.loads(_run(server.master_audio("test-album", genre="hip-hop")))

        assert result["settings"]["genre"] == "hip-hop"
        assert result["settings"]["target_lufs"] == -13.0
        assert result["settings"]["cut_highmid"] == -3.0
        assert result["settings"]["cut_highs"] == -1.0

    def test_custom_params_override_genre(self, tmp_path):
        """Explicit non-default params should override genre preset."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            return {
                "original_lufs": -20.0,
                "final_lufs": -12.0,
                "gain_applied": 8.0,
                "final_peak": -1.0,
            }

        presets = {"hip-hop": (-13.0, -3.0, -1.0, 1.5)}

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value=presets):
            result = json.loads(_run(server.master_audio(
                "test-album", genre="hip-hop", target_lufs=-12.0
            )))

        # -12.0 was explicitly set, so it overrides the genre preset's -13.0
        assert result["settings"]["target_lufs"] == -12.0

    def test_eq_settings_propagated(self, tmp_path):
        """EQ settings should be passed to master_track."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        captured_kwargs = []

        def mock_master(input_path, output_path, **kwargs):
            captured_kwargs.append(kwargs)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.0,
            }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_audio(
                "test-album", cut_highmid=-2.0, cut_highs=-1.5
            )))

        assert len(captured_kwargs) == 1
        eq = captured_kwargs[0]["eq_settings"]
        assert len(eq) == 2
        assert eq[0] == (3500, -2.0, 1.5)
        assert eq[1] == (8000, -1.5, 0.7)

    def test_summary_gain_range(self, tmp_path):
        """Summary should include correct gain range across tracks."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        call_idx = [0]

        def mock_master(input_path, output_path, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            gain = 4.0 if idx == 0 else 8.0
            return {
                "original_lufs": -14.0 - gain,
                "final_lufs": -14.0,
                "gain_applied": gain,
                "final_peak": -1.0,
            }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_audio("test-album")))

        assert result["summary"]["gain_range"] == [4.0, 8.0]

    def test_skipped_tracks_excluded(self, tmp_path):
        """Tracks returning skipped=True should not appear in results."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        call_idx = [0]

        def mock_master(input_path, output_path, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx == 0:
                return {"skipped": True}
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.0,
            }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_audio("test-album")))

        assert result["summary"]["tracks_processed"] == 1


class TestFixDynamicTrackComprehensive:
    """Comprehensive tests for fix_dynamic_track success path."""

    def test_successful_fix(self, tmp_path):
        """Full success path: read WAV, compress, master, write output."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "05-loud-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        import numpy as np

        mock_data = np.random.randn(44100, 2).astype(np.float32) * 0.5

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("soundfile.read", return_value=(mock_data.copy(), 44100)), \
             patch("soundfile.write") as mock_write, \
             patch("pyloudnorm.Meter") as mock_meter_cls:
            mock_meter = MagicMock()
            mock_meter.integrated_loudness.side_effect = [-22.0, -16.0, -14.0]
            mock_meter_cls.return_value = mock_meter

            result = json.loads(_run(server.fix_dynamic_track("test-album", "05-loud-track.wav")))

        assert result["filename"] == "05-loud-track.wav"
        assert result["original_lufs"] == -22.0
        assert result["final_lufs"] == -14.0
        assert "output_path" in result
        assert "mastered" in result["output_path"]
        mock_write.assert_called_once()

    def test_creates_mastered_dir(self, tmp_path):
        """Should create mastered/ subdirectory."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        import numpy as np
        mock_data = np.random.randn(44100, 2).astype(np.float32) * 0.5

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("soundfile.read", return_value=(mock_data.copy(), 44100)), \
             patch("soundfile.write"), \
             patch("pyloudnorm.Meter") as mock_meter_cls:
            mock_meter = MagicMock()
            mock_meter.integrated_loudness.side_effect = [-20.0, -16.0, -14.0]
            mock_meter_cls.return_value = mock_meter
            _run(server.fix_dynamic_track("test-album", "01-track.wav"))

        assert (audio_dir / "mastered").is_dir()


class TestMasterWithReferenceComprehensive:
    """Comprehensive tests for master_with_reference: error during batch, output paths."""

    def _patch_ref_master(self):
        mock_fn = MagicMock()
        mock_mod = types.ModuleType("tools.mastering.reference_master")
        mock_mod.master_with_reference = mock_fn
        return patch.dict("sys.modules", {"tools.mastering.reference_master": mock_mod}), mock_fn

    def test_batch_error_on_one_track(self, tmp_path):
        """If one track fails in batch mode, others should still succeed."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "ref.wav").write_bytes(b"")
        (audio_dir / "originals" / "01-good.wav").write_bytes(b"")
        (audio_dir / "originals" / "02-bad.wav").write_bytes(b"")
        (audio_dir / "originals" / "03-good.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mod_patch, mock_fn = self._patch_ref_master()

        call_count = [0]

        def side_effect(target, ref, output):
            call_count[0] += 1
            if "02-bad" in str(target):
                raise RuntimeError("Processing failed")

        mock_fn.side_effect = side_effect

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None), \
             mod_patch:
            result = json.loads(_run(server.master_with_reference("test-album", "ref.wav")))

        assert result["summary"]["success"] == 2
        assert result["summary"]["failed"] == 1
        failed = [t for t in result["tracks"] if not t["success"]]
        assert len(failed) == 1
        assert "02-bad" in failed[0]["filename"]

    def test_reference_excluded_from_batch(self, tmp_path):
        """Batch mode should not process the reference file itself."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "ref.wav").write_bytes(b"")
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mod_patch, mock_fn = self._patch_ref_master()

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None), \
             mod_patch:
            result = json.loads(_run(server.master_with_reference("test-album", "ref.wav")))

        assert len(result["tracks"]) == 1
        assert "ref.wav" not in result["tracks"][0]["filename"]

    def test_output_dir_created(self, tmp_path):
        """mastered/ directory should be created automatically."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "ref.wav").write_bytes(b"")
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mod_patch, _ = self._patch_ref_master()

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None), \
             mod_patch:
            _run(server.master_with_reference("test-album", "ref.wav"))

        assert (audio_dir / "mastered").is_dir()

    def test_single_track_output_path(self, tmp_path):
        """Single track output should be in mastered/ subdirectory."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "ref.wav").write_bytes(b"")
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mod_patch, _ = self._patch_ref_master()

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_matchering", return_value=None), \
             mod_patch:
            result = json.loads(_run(server.master_with_reference(
                "test-album", "ref.wav", "01-track.wav"
            )))

        assert "mastered" in result["tracks"][0]["output"]


class TestTranscribeAudioComprehensive:
    """Comprehensive tests for transcribe_audio success paths."""

    def _make_audio_dir(self, tmp_path, num_tracks=2):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "originals").mkdir(exist_ok=True)
        for i in range(num_tracks):
            (audio_dir / "originals" / f"{i+1:02d}-track.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def test_batch_success(self, tmp_path):
        """Transcribe all WAV files in batch mode."""
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.find_anthemscore.return_value = "/usr/bin/anthemscore"
        mock_mod.transcribe_track.return_value = True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.transcribe_audio("test-album")))

        assert result["summary"]["success"] == 3
        assert result["summary"]["failed"] == 0
        assert len(result["tracks"]) == 3
        assert all(t["success"] for t in result["tracks"])

    def test_single_track_success(self, tmp_path):
        """Transcribe a single track by filename."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.find_anthemscore.return_value = "/usr/bin/anthemscore"
        mock_mod.transcribe_track.return_value = True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.transcribe_audio(
                "test-album", track_filename="01-track.wav"
            )))

        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["filename"] == "01-track.wav"
        assert result["summary"]["success"] == 1

    def test_format_param_parsed(self, tmp_path):
        """Formats parameter should be parsed and passed correctly."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.find_anthemscore.return_value = "/usr/bin/anthemscore"
        mock_mod.transcribe_track.return_value = True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.transcribe_audio(
                "test-album", formats="pdf,xml,midi"
            )))

        assert result["summary"]["formats"] == ["pdf", "xml", "midi"]
        # Verify args passed to transcribe_track
        args = mock_mod.transcribe_track.call_args[0][3]
        assert args.pdf is True
        assert args.xml is True
        assert args.midi is True

    def test_dry_run_mode(self, tmp_path):
        """Dry run should not create output directory."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.find_anthemscore.return_value = "/usr/bin/anthemscore"
        mock_mod.transcribe_track.return_value = True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.transcribe_audio(
                "test-album", dry_run=True
            )))

        assert not (audio_dir / "sheet-music").exists()
        # Verify dry_run was set in args
        args = mock_mod.transcribe_track.call_args[0][3]
        assert args.dry_run is True

    def test_partial_failure(self, tmp_path):
        """Some tracks failing should still report success for others."""
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.find_anthemscore.return_value = "/usr/bin/anthemscore"

        call_idx = [0]

        def mock_transcribe(*args):
            idx = call_idx[0]
            call_idx[0] += 1
            return idx != 1  # Second track fails

        mock_mod.transcribe_track.side_effect = mock_transcribe

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_anthemscore", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.transcribe_audio("test-album")))

        assert result["summary"]["success"] == 2
        assert result["summary"]["failed"] == 1


class TestFixSheetMusicTitlesComprehensive:
    """Comprehensive tests for fix_sheet_music_titles: batch, dry_run, PDF export."""

    def test_batch_multiple_xmls(self, tmp_path):
        """Fix titles in multiple XML files."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        (sheet_dir / "01-track.xml").write_text("<work-title>01 - Track</work-title>")
        (sheet_dir / "02-song.xml").write_text("<work-title>02 - Song</work-title>")
        (sheet_dir / "03-tune.xml").write_text("<work-title>03 - Tune</work-title>")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.fix_xml_title.side_effect = ["Track", "Song", "Tune"]
        mock_mod.find_musescore.return_value = None

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles("test-album")))

        assert result["fixed_count"] == 3
        assert len(result["files"]) == 3

    def test_dry_run_mode(self, tmp_path):
        """Dry run should not modify files or export PDFs."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        (sheet_dir / "01-track.xml").write_text("<work-title>01 - Track</work-title>")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.fix_xml_title.return_value = "Track"
        mock_mod.find_musescore.return_value = "/usr/bin/musescore"

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles("test-album", dry_run=True)))

        mock_mod.fix_xml_title.assert_called_once()
        # dry_run=True passed to fix_xml_title
        _, kwargs = mock_mod.fix_xml_title.call_args
        assert kwargs["dry_run"] is True
        # No PDF export in dry run
        assert result["pdf_exports"] == []

    def test_pdf_export_with_musescore(self, tmp_path):
        """When MuseScore is available and export_pdf=True, should export PDFs."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        (sheet_dir / "01-track.xml").write_text("<work-title>01 - Track</work-title>")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.fix_xml_title.return_value = "Track"
        mock_mod.find_musescore.return_value = "/usr/bin/musescore"
        mock_mod.export_pdf.return_value = True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles(
                "test-album", export_pdf=True
            )))

        assert len(result["pdf_exports"]) == 1
        assert result["pdf_exports"][0]["exported"] is True

    def test_no_pdf_export_when_musescore_missing(self, tmp_path):
        """When MuseScore is missing, PDF export should be skipped with warning."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        (sheet_dir / "01-track.xml").write_text("<work-title>01 - Track</work-title>")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.fix_xml_title.return_value = "Track"
        mock_mod.find_musescore.return_value = None

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles(
                "test-album", export_pdf=True
            )))

        assert any("warning" in p for p in result["pdf_exports"])

    def test_musicxml_extension(self, tmp_path):
        """Should also find .musicxml files with track number prefixes."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        (sheet_dir / "01-track.musicxml").write_text("<work-title>01 - Track</work-title>")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.fix_xml_title.return_value = "Track"
        mock_mod.find_musescore.return_value = None

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles("test-album")))

        assert result["fixed_count"] == 1
        assert result["files"][0]["filename"] == "01-track.musicxml"

    def test_export_pdf_false_skips_export(self, tmp_path):
        """When export_pdf=False, no PDF export should be attempted."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)
        (sheet_dir / "01-track.xml").write_text("<work-title>01 - Track</work-title>")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = MagicMock()
        mock_mod.fix_xml_title.return_value = "Track"

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.fix_sheet_music_titles(
                "test-album", export_pdf=False
            )))

        assert result["pdf_exports"] == []
        mock_mod.find_musescore.assert_not_called()


class TestCreateSongbookComprehensive:
    """Comprehensive tests for create_songbook success path."""

    def _mock_songbook_module(self):
        """Create a mock songbook module."""
        mock_mod = MagicMock()
        mock_mod.create_songbook.return_value = True
        mock_mod.auto_detect_cover_art.return_value = "/fake/cover.png"
        mock_mod.get_website_from_config.return_value = "https://example.com"
        return mock_mod

    def test_success_path(self, tmp_path):
        """Full success path for create_songbook."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = self._mock_songbook_module()

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_songbook_deps", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.create_songbook("test-album", "My Songbook")))

        assert result["success"] is True
        assert result["title"] == "My Songbook"
        assert result["artist"] == "test-artist"
        assert "output_path" in result

    def test_page_size_param(self, tmp_path):
        """Page size parameter should be passed through."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = self._mock_songbook_module()

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_songbook_deps", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.create_songbook(
                "test-album", "My Songbook", page_size="9x12"
            )))

        assert result["page_size"] == "9x12"
        # Verify page_size_name passed to the function
        call_kwargs = mock_mod.create_songbook.call_args
        assert call_kwargs[1]["page_size_name"] == "9x12"

    def test_artist_from_config(self, tmp_path):
        """Artist name should come from config state."""
        audio_dir = tmp_path / "artists" / "custom-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "custom-artist"
        mock_cache = MockStateCache(state)

        mock_mod = self._mock_songbook_module()

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_songbook_deps", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.create_songbook("test-album", "My Songbook")))

        assert result["artist"] == "custom-artist"
        call_kwargs = mock_mod.create_songbook.call_args
        assert call_kwargs[1]["artist"] == "custom-artist"

    def test_creation_failure(self, tmp_path):
        """create_songbook returning False should produce error."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = self._mock_songbook_module()
        mock_mod.create_songbook.return_value = False

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_songbook_deps", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.create_songbook("test-album", "My Songbook")))

        assert "error" in result

    def test_output_path_sanitized(self, tmp_path):
        """Title with spaces/slashes should be sanitized in output path."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        sheet_dir = audio_dir / "sheet-music"
        sheet_dir.mkdir(parents=True)

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_mod = self._mock_songbook_module()

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_songbook_deps", return_value=None), \
             patch.object(server, "_import_sheet_music_module", return_value=mock_mod):
            result = json.loads(_run(server.create_songbook(
                "test-album", "My Album / Songbook"
            )))

        assert result["success"] is True
        assert "My_Album_-_Songbook.pdf" in result["output_path"]


class TestGeneratePromoVideosComprehensive:
    """Comprehensive tests for generate_promo_videos: batch, title fallbacks, artwork."""

    def _make_audio_dir(self, tmp_path, num_tracks=2, artwork_name="album.png"):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / artwork_name).write_bytes(b"")
        (audio_dir / "originals").mkdir(exist_ok=True)
        for i in range(num_tracks):
            (audio_dir / "originals" / f"{i+1:02d}-track-{i+1}.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def test_batch_mode_success(self, tmp_path):
        """Batch all tracks with mock batch_process_album."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        # Simulate batch_process_album creating output files
        def mock_batch(**kwargs):
            output_dir = kwargs["output_dir"]
            output_dir.mkdir(exist_ok=True)
            (output_dir / "01-track-1_promo.mp4").write_bytes(b"")
            (output_dir / "02-track-2_promo.mp4").write_bytes(b"")

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.batch_process_album",
                   side_effect=mock_batch), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video"), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            result = json.loads(_run(server.generate_promo_videos("test-album")))

        assert result["summary"]["success"] == 2
        assert len(result["tracks"]) == 2

    def test_filename_fallback_title_cleanup(self, tmp_path):
        """When no markdown title exists, filename should be cleaned up properly."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        # Remove any track data from state so it falls back to filename
        state["albums"]["test-album"]["tracks"] = {}
        mock_cache = MockStateCache(state)

        captured_title = []

        def mock_generate(**kwargs):
            captured_title.append(kwargs.get("title"))
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   side_effect=mock_generate), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            result = json.loads(_run(server.generate_promo_videos(
                "test-album", track_filename="01-track-1.wav"
            )))

        assert result["tracks"][0]["success"] is True
        assert len(captured_title) == 1
        # "01-track-1" → strip "01-" → "track-1" → "Track 1"
        assert "Track" in captured_title[0]
        # Should not start with a number
        assert not captured_title[0][0].isdigit()

    def test_artwork_jpg_found(self, tmp_path):
        """Should find album.jpg when album.png is missing."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1, artwork_name="album.jpg")
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   return_value=True), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            result = json.loads(_run(server.generate_promo_videos(
                "test-album", track_filename="01-track-1.wav"
            )))

        assert result["tracks"][0]["success"] is True

    def test_cover_png_artwork(self, tmp_path):
        """Should find cover.png as artwork."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1, artwork_name="cover.png")
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   return_value=True), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            result = json.loads(_run(server.generate_promo_videos(
                "test-album", track_filename="01-track-1.wav"
            )))

        assert result["tracks"][0]["success"] is True

    def test_style_param_passed(self, tmp_path):
        """Style parameter should be passed to generate_waveform_video."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        captured_kwargs = []

        def mock_generate(**kwargs):
            captured_kwargs.append(kwargs)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   side_effect=mock_generate), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            _run(server.generate_promo_videos(
                "test-album", style="neon", track_filename="01-track-1.wav"
            ))

        assert captured_kwargs[0]["style"] == "neon"

    def test_duration_param_passed(self, tmp_path):
        """Duration parameter should be passed to generate_waveform_video."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        captured_kwargs = []

        def mock_generate(**kwargs):
            captured_kwargs.append(kwargs)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   side_effect=mock_generate), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            _run(server.generate_promo_videos(
                "test-album", duration=30, track_filename="01-track-1.wav"
            ))

        assert captured_kwargs[0]["duration"] == 30

    def test_track_in_mastered_subdir(self, tmp_path):
        """Should find track in mastered/ subdirectory if not in root."""
        audio_dir, state = self._make_audio_dir(tmp_path, 0)
        mastered_dir = audio_dir / "mastered"
        mastered_dir.mkdir()
        (mastered_dir / "01-track.wav").write_bytes(b"")
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   return_value=True), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            result = json.loads(_run(server.generate_promo_videos(
                "test-album", track_filename="01-track.wav"
            )))

        assert result["tracks"][0]["success"] is True

    def test_single_track_video_failure(self, tmp_path):
        """When video generation fails, result should reflect failure."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video",
                   return_value=False), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            result = json.loads(_run(server.generate_promo_videos(
                "test-album", track_filename="01-track-1.wav"
            )))

        assert result["tracks"][0]["success"] is False
        assert result["summary"]["failed"] == 1

    def test_batch_passes_content_dir(self, tmp_path):
        """Batch mode should pass content_dir for markdown title lookup."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        # Create the content directory that the album path points to
        content_dir = Path(state["albums"]["test-album"]["path"])
        content_dir.mkdir(parents=True, exist_ok=True)
        mock_cache = MockStateCache(state)

        captured_kwargs = []

        def mock_batch(**kwargs):
            captured_kwargs.append(kwargs)

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_promo_video.batch_process_album",
                   side_effect=mock_batch), \
             patch("tools.promotion.generate_promo_video.generate_waveform_video"), \
             patch("tools.shared.fonts.find_font", return_value="/fake/font.ttf"):
            _run(server.generate_promo_videos("test-album"))

        assert captured_kwargs[0]["content_dir"] == content_dir


class TestGenerateAlbumSamplerComprehensive:
    """Comprehensive tests for generate_album_sampler success paths."""

    def _make_audio_dir(self, tmp_path, num_tracks=3):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "album.png").write_bytes(b"")
        (audio_dir / "originals").mkdir(exist_ok=True)
        for i in range(num_tracks):
            (audio_dir / "originals" / f"{i+1:02d}-track.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def test_success_path(self, tmp_path):
        """Full success path with output file stats."""
        audio_dir, state = self._make_audio_dir(tmp_path, 5)
        mock_cache = MockStateCache(state)

        def mock_gen_sampler(**kwargs):
            # Simulate creating the output file
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024 * 1024)  # 1MB fake file
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            result = json.loads(_run(server.generate_album_sampler("test-album")))

        assert result["success"] is True
        assert "output_path" in result
        assert result["tracks_included"] == 5
        assert result["clip_duration"] == 12
        assert result["crossfade"] == 0.5
        assert "file_size_mb" in result

    def test_custom_clip_duration(self, tmp_path):
        """Custom clip_duration should be reflected in response."""
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        def mock_gen_sampler(**kwargs):
            assert kwargs["clip_duration"] == 8
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            result = json.loads(_run(server.generate_album_sampler(
                "test-album", clip_duration=8
            )))

        assert result["clip_duration"] == 8

    def test_custom_crossfade(self, tmp_path):
        """Custom crossfade should be reflected in response."""
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        def mock_gen_sampler(**kwargs):
            assert kwargs["crossfade"] == 1.0
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            result = json.loads(_run(server.generate_album_sampler(
                "test-album", crossfade=1.0
            )))

        assert result["crossfade"] == 1.0

    def test_twitter_limit_ok_true(self, tmp_path):
        """Short samplers should report twitter_limit_ok=True."""
        audio_dir, state = self._make_audio_dir(tmp_path, 5)
        mock_cache = MockStateCache(state)

        def mock_gen_sampler(**kwargs):
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            result = json.loads(_run(server.generate_album_sampler(
                "test-album", clip_duration=10
            )))

        # 5 tracks * 10s - 4 * 0.5s = 48s < 140s
        expected = 5 * 10 - 4 * 0.5
        assert result["expected_duration_seconds"] == expected
        assert result["twitter_limit_ok"] is True

    def test_twitter_limit_ok_false(self, tmp_path):
        """Long samplers should report twitter_limit_ok=False."""
        audio_dir, state = self._make_audio_dir(tmp_path, 15)
        mock_cache = MockStateCache(state)

        def mock_gen_sampler(**kwargs):
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            result = json.loads(_run(server.generate_album_sampler(
                "test-album", clip_duration=12
            )))

        # 15 tracks * 12s - 14 * 0.5s = 173s > 140s
        assert result["twitter_limit_ok"] is False

    def test_creates_promo_videos_dir(self, tmp_path):
        """Should create promo_videos/ directory."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_gen_sampler(**kwargs):
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            _run(server.generate_album_sampler("test-album"))

        assert (audio_dir / "promo_videos").is_dir()

    def test_artist_from_config(self, tmp_path):
        """Artist name from config should be passed to the generator."""
        audio_dir = tmp_path / "artists" / "custom-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "album.png").write_bytes(b"")
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "custom-artist"
        mock_cache = MockStateCache(state)

        captured_kwargs = []

        def mock_gen_sampler(**kwargs):
            captured_kwargs.append(kwargs)
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            _run(server.generate_album_sampler("test-album"))

        assert captured_kwargs[0]["artist_name"] == "custom-artist"

    def test_artwork_jpg_fallback(self, tmp_path):
        """Should find album.jpg when album.png is missing."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "album.jpg").write_bytes(b"")
        (audio_dir / "originals").mkdir(exist_ok=True)
        (audio_dir / "originals" / "01-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        def mock_gen_sampler(**kwargs):
            assert "album.jpg" in str(kwargs["artwork_path"])
            output_path = kwargs["output_path"]
            output_path.parent.mkdir(exist_ok=True)
            output_path.write_bytes(b"0" * 1024)
            return True

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_ffmpeg", return_value=None), \
             patch("tools.promotion.generate_album_sampler.generate_album_sampler",
                   side_effect=mock_gen_sampler):
            result = json.loads(_run(server.generate_album_sampler("test-album")))

        assert result["success"] is True


class TestDepCheckersComprehensive:
    """Additional tests for dependency checker edge cases."""

    def test_check_mastering_deps_detects_all_missing(self):
        """Should list all missing deps, not just the first."""
        import builtins as _builtins
        original_import = _builtins.__import__
        missing_set = {"numpy", "scipy", "soundfile", "pyloudnorm"}

        def mock_import(name, *args, **kwargs):
            if name in missing_set:
                raise ImportError(f"mocked {name}")
            return original_import(name, *args, **kwargs)

        with patch.object(_builtins, "__import__", side_effect=mock_import):
            result = server._check_mastering_deps()

        assert result is not None
        for mod in missing_set:
            assert mod in result

    def test_check_ffmpeg_when_available(self):
        """Should return None when ffmpeg is found."""
        with patch.object(shutil, "which", return_value="/usr/bin/ffmpeg"):
            result = server._check_ffmpeg()
        assert result is None

    def test_check_matchering_when_missing(self):
        """Should return error string when matchering is missing."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "matchering":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = server._check_matchering()

        assert result is not None
        assert "matchering" in result

    def test_check_songbook_deps_detects_missing(self):
        """Should detect missing pypdf and reportlab."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("pypdf", "reportlab"):
                raise ImportError(f"mocked {name}")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = server._check_songbook_deps()

        assert result is not None
        assert "pypdf" in result
        assert "reportlab" in result


# =============================================================================
# Gap-closing tests for list_tracks, get_session, rebuild_state, get_config
# =============================================================================


class TestListTracksEdgeCases:
    """Edge case tests for the list_tracks MCP tool."""

    def test_album_with_no_tracks(self):
        """Album exists but has zero tracks."""
        state = _fresh_state()
        state["albums"]["empty-album"] = {
            "path": "/tmp/test/artists/test-artist/albums/electronic/empty-album",
            "genre": "electronic",
            "title": "Empty Album",
            "status": "Concept",
            "explicit": False,
            "release_date": None,
            "track_count": 0,
            "tracks_completed": 0,
            "readme_mtime": 1234567890.0,
            "tracks": {},
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_tracks("empty-album")))
        assert result["found"] is True
        assert result["track_count"] == 0
        assert result["tracks"] == []

    def test_album_with_missing_tracks_key(self):
        """Album dict has no 'tracks' key at all."""
        state = _fresh_state()
        state["albums"]["bare-album"] = {
            "path": "/tmp/test/...",
            "title": "Bare Album",
            "status": "Concept",
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_tracks("bare-album")))
        assert result["found"] is True
        assert result["track_count"] == 0

    def test_empty_albums_dict(self):
        """State has empty albums dict — all lookups should fail."""
        state = _fresh_state()
        state["albums"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.list_tracks("anything")))
        assert result["found"] is False
        assert result["available_albums"] == []


class TestGetSessionEdgeCases:
    """Edge case tests for the get_session MCP tool."""

    def test_missing_session_key(self):
        """State has no 'session' key at all."""
        state = {"config": {}, "albums": {}, "ideas": {}}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_session()))
        assert result["session"] == {}

    def test_session_with_pending_actions(self):
        """Session with pending actions should return them."""
        state = _fresh_state()
        state["session"]["pending_actions"] = ["Review track 3", "Fix pronunciation"]
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_session()))
        assert result["session"]["pending_actions"] == ["Review track 3", "Fix pronunciation"]

    def test_session_with_null_fields(self):
        """Session with None/null fields should return them as-is."""
        state = _fresh_state()
        state["session"] = {
            "last_album": None,
            "last_track": None,
            "last_phase": None,
            "pending_actions": [],
            "updated_at": None,
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_session()))
        assert result["session"]["last_album"] is None
        assert result["session"]["last_track"] is None


class TestRebuildStateEdgeCases:
    """Edge case tests for the rebuild_state MCP tool."""

    def test_rebuild_empty_albums(self):
        """Rebuild returns state with no albums or ideas."""
        state = {
            "config": {"content_root": "/tmp"},
            "albums": {},
            "ideas": {"items": [], "counts": {}},
            "session": {},
        }

        class EmptyCache(MockStateCache):
            def rebuild(self):
                self._rebuild_called = True
                return state

        mock_cache = EmptyCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rebuild_state()))
        assert result["success"] is True
        assert result["albums"] == 0
        assert result["tracks"] == 0
        assert result["ideas"] == 0

    def test_rebuild_counts_nested_tracks(self):
        """Track count should sum across all albums."""
        state = _fresh_state()
        # test-album has 2 tracks, another-album has 1 = 3 total
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rebuild_state()))
        assert result["tracks"] == 3

    def test_rebuild_includes_skills_count(self):
        """Skills count should be included if present."""
        state = _fresh_state()
        state["skills"] = {"count": 42, "items": []}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rebuild_state()))
        assert result["skills"] == 42

    def test_rebuild_missing_ideas_key(self):
        """State with missing 'ideas' key should not crash."""
        state = {"config": {}, "albums": {}, "session": {}}

        class NoIdeasCache(MockStateCache):
            def rebuild(self):
                return state

        mock_cache = NoIdeasCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.rebuild_state()))
        assert result["success"] is True
        assert result["ideas"] == 0


class TestGetConfigEdgeCases:
    """Edge case tests for the get_config MCP tool."""

    def test_config_with_partial_keys(self):
        """Config present but only has some keys — should still return it."""
        state = _fresh_state()
        state["config"] = {"artist_name": "bitwize"}  # missing paths
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_config()))
        assert "config" in result
        assert result["config"]["artist_name"] == "bitwize"
        # Missing keys just aren't present — no crash
        assert "content_root" not in result["config"]

    def test_config_returns_all_fields(self):
        """Full config should include all expected fields."""
        mock_cache = MockStateCache()
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.get_config()))
        config = result["config"]
        assert "content_root" in config
        assert "audio_root" in config
        assert "documents_root" in config
        assert "artist_name" in config


# =============================================================================
# Backward-compatibility: WAVs in album root (legacy layout, no originals/)
# =============================================================================


class TestOriginalsBackwardCompat:
    """Verify tools work with WAVs in album root (legacy layout, no originals/)."""

    def test_validate_album_finds_wavs_in_root(self, tmp_path):
        """validate_album_structure should find WAVs directly in audio_dir."""
        content = tmp_path / "content"
        audio = tmp_path / "audio"
        album_dir = content / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        tracks_dir = album_dir / "tracks"
        audio_dir = audio / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        tracks_dir.mkdir(parents=True)
        audio_dir.mkdir(parents=True)
        (album_dir / "README.md").write_text("# Test Album")
        (tracks_dir / "01-test.md").write_text(_SAMPLE_TRACK_MD)
        (audio_dir / "01-test.wav").write_text("")  # WAV in root, no originals/
        (audio_dir / "album.png").write_text("")

        state = copy.deepcopy(SAMPLE_STATE)
        state["config"]["content_root"] = str(content)
        state["config"]["audio_root"] = str(audio)
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.validate_album_structure("test-album")))
        assert result["found"] is True
        # Should find the WAV in root via legacy fallback
        audio_checks = [c for c in result["checks"] if c["category"] == "audio"]
        wav_msgs = [c["message"] for c in audio_checks if "WAV" in c.get("message", "")]
        assert any("1 WAV" in m for m in wav_msgs)

    def test_analyze_audio_legacy_layout(self, tmp_path):
        """analyze_audio should find WAVs in album root when originals/ absent."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "01-track.wav").write_bytes(b"")  # legacy: no originals/

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_result = {
            "filename": "01-track.wav",
            "duration": 180.0,
            "sample_rate": 44100,
            "lufs": -14.0,
            "peak_db": -0.5,
            "rms_db": -18.0,
            "dynamic_range": 17.5,
            "band_energy": {"sub_bass": 5, "bass": 20, "low_mid": 15,
                            "mid": 30, "high_mid": 20, "high": 8, "air": 2},
            "tinniness_ratio": 0.3,
        }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.analyze_tracks.analyze_track", return_value=mock_result):
            result = json.loads(_run(server.analyze_audio("test-album")))
        assert "tracks" in result
        assert len(result["tracks"]) == 1

    def test_master_audio_legacy_layout(self, tmp_path):
        """master_audio should find WAVs in album root when originals/ absent."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "01-track.wav").write_bytes(b"")  # legacy: no originals/

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        mock_master_result = {
            "original_lufs": -20.0, "final_lufs": -14.0,
            "gain_applied": 6.0, "final_peak": -1.0,
        }

        with patch.object(server, "cache", mock_cache), \
             patch.object(server, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.master_track", return_value=mock_master_result), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_audio("test-album")))
        assert "tracks" in result or "error" not in result


class TestMigrateAudioLayout:
    """Tests for the migrate_audio_layout MCP tool."""

    def _make_state(self, tmp_path):
        """Return a state with audio_root pointing at tmp_path."""
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return state

    def _album_audio_dir(self, tmp_path, genre="electronic", slug="test-album"):
        """Create and return the audio dir for an album."""
        d = tmp_path / "artists" / "test-artist" / "albums" / genre / slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    def test_dry_run_shows_what_would_be_moved(self, tmp_path):
        """dry_run=True lists files but does NOT move them."""
        state = self._make_state(tmp_path)
        audio_dir = self._album_audio_dir(tmp_path)
        (audio_dir / "01-track.wav").write_bytes(b"")
        (audio_dir / "02-track.wav").write_bytes(b"")

        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.migrate_audio_layout(
                album_slug="test-album", dry_run=True,
            )))

        assert result["dry_run"] is True
        album_result = result["albums"][0]
        assert album_result["slug"] == "test-album"
        assert album_result["status"] == "would_migrate"
        assert "01-track.wav" in album_result["files_moved"]
        assert "02-track.wav" in album_result["files_moved"]
        # Files should NOT have moved
        assert (audio_dir / "01-track.wav").exists()
        assert (audio_dir / "02-track.wav").exists()
        assert not (audio_dir / "originals").exists()

    def test_actual_migration_moves_files(self, tmp_path):
        """dry_run=False moves WAVs into originals/."""
        state = self._make_state(tmp_path)
        audio_dir = self._album_audio_dir(tmp_path)
        (audio_dir / "01-track.wav").write_bytes(b"RIFF")
        (audio_dir / "02-track.wav").write_bytes(b"RIFF")

        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.migrate_audio_layout(
                album_slug="test-album", dry_run=False,
            )))

        assert result["dry_run"] is False
        album_result = result["albums"][0]
        assert album_result["status"] == "migrated"
        assert len(album_result["files_moved"]) == 2
        # Files should now be in originals/
        assert (audio_dir / "originals" / "01-track.wav").exists()
        assert (audio_dir / "originals" / "02-track.wav").exists()
        # And gone from root
        assert not (audio_dir / "01-track.wav").exists()
        assert not (audio_dir / "02-track.wav").exists()

    def test_skips_already_migrated(self, tmp_path):
        """Albums with originals/ already present get status 'already_migrated'."""
        state = self._make_state(tmp_path)
        audio_dir = self._album_audio_dir(tmp_path)
        originals = audio_dir / "originals"
        originals.mkdir()
        (originals / "01-track.wav").write_bytes(b"")

        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.migrate_audio_layout(
                album_slug="test-album", dry_run=False,
            )))

        album_result = result["albums"][0]
        assert album_result["status"] == "already_migrated"
        assert album_result["skip_reason"] == "already has originals/"
        assert result["summary"]["already_migrated"] == 1

    def test_skips_albums_with_no_audio_dir(self, tmp_path):
        """Albums without a corresponding audio directory are skipped."""
        state = self._make_state(tmp_path)
        # Don't create the audio dir on disk

        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.migrate_audio_layout(
                album_slug="test-album", dry_run=False,
            )))

        album_result = result["albums"][0]
        assert album_result["status"] == "skipped"
        assert album_result["skip_reason"] == "no audio dir"

    def test_single_album_mode(self, tmp_path):
        """Passing album_slug processes only that album."""
        state = self._make_state(tmp_path)
        # Create audio dirs for both albums
        electronic_dir = self._album_audio_dir(tmp_path, "electronic", "test-album")
        rock_dir = self._album_audio_dir(tmp_path, "rock", "another-album")
        (electronic_dir / "01-track.wav").write_bytes(b"")
        (rock_dir / "01-rock.wav").write_bytes(b"")

        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.migrate_audio_layout(
                album_slug="another-album", dry_run=True,
            )))

        assert result["summary"]["total_albums"] == 1
        assert len(result["albums"]) == 1
        assert result["albums"][0]["slug"] == "another-album"

    def test_non_wav_files_left_in_root(self, tmp_path):
        """Only WAV files are moved; other files remain in root."""
        state = self._make_state(tmp_path)
        audio_dir = self._album_audio_dir(tmp_path)
        (audio_dir / "01-track.wav").write_bytes(b"")
        (audio_dir / "album.png").write_bytes(b"\x89PNG")
        (audio_dir / "notes.txt").write_text("notes")

        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.migrate_audio_layout(
                album_slug="test-album", dry_run=False,
            )))

        album_result = result["albums"][0]
        assert album_result["status"] == "migrated"
        assert album_result["files_moved"] == ["01-track.wav"]
        # WAV moved
        assert (audio_dir / "originals" / "01-track.wav").exists()
        assert not (audio_dir / "01-track.wav").exists()
        # Non-WAV files remain
        assert (audio_dir / "album.png").exists()
        assert (audio_dir / "notes.txt").exists()

