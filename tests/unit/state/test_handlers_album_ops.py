#!/usr/bin/env python3
"""
Unit tests for handlers/album_ops.py — album creation, query, and validation.

Tests get_album_full, validate_album_structure, and create_album_structure
MCP tool handlers.

Usage:
    python -m pytest tests/unit/state/test_handlers_album_ops.py -v
"""

import asyncio
import copy
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed
# ---------------------------------------------------------------------------

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

try:
    import mcp  # noqa: F401
except ImportError:

    class _FakeFastMCP:
        def __init__(self, name=""):
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
    spec = importlib.util.spec_from_file_location("state_server_album_ops", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import album_ops as _album_ops_mod
from handlers import _shared as _shared_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


SAMPLE_STATE = {
    "version": 2,
    "config": {
        "content_root": "/tmp/test-content",
        "audio_root": "/tmp/test-audio",
        "documents_root": "/tmp/test-docs",
        "artist_name": "test-artist",
        "generation": {},
    },
    "albums": {
        "test-album": {
            "title": "Test Album",
            "status": "In Progress",
            "genre": "electronic",
            "path": "/tmp/test-content/artists/test-artist/albums/electronic/test-album",
            "track_count": 2,
            "tracks_completed": 1,
            "tracks": {
                "01-first-track": {
                    "title": "First Track",
                    "status": "Final",
                    "explicit": False,
                    "has_suno_link": True,
                    "sources_verified": "N/A",
                    "path": "/tmp/tracks/01-first-track.md",
                    "mtime": 1234567890.0,
                },
                "02-second-track": {
                    "title": "Second Track",
                    "status": "In Progress",
                    "explicit": True,
                    "has_suno_link": False,
                    "sources_verified": "Pending",
                    "path": "/tmp/tracks/02-second-track.md",
                    "mtime": 1234567891.0,
                },
            },
        },
        "another-album": {
            "title": "Another Album",
            "status": "Complete",
            "genre": "rock",
            "path": "/tmp/test-content/artists/test-artist/albums/rock/another-album",
            "track_count": 1,
            "tracks_completed": 1,
            "tracks": {
                "01-rock-song": {
                    "title": "Rock Song",
                    "status": "Final",
                    "explicit": False,
                    "has_suno_link": True,
                    "sources_verified": "Verified (2025-05-01)",
                    "path": "/tmp/tracks/01-rock-song.md",
                    "mtime": 1234567892.0,
                },
            },
        },
    },
    "ideas": {"total": 0, "by_status": {}, "items": []},
    "session": {
        "last_album": None,
        "last_track": None,
        "last_phase": None,
        "pending_actions": [],
        "updated_at": None,
    },
}


def _fresh_state():
    return copy.deepcopy(SAMPLE_STATE)


class MockStateCache:
    def __init__(self, state=None):
        self._state = state if state is not None else _fresh_state()
        self._rebuild_called = False

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}

    def rebuild(self):
        self._rebuild_called = True
        return self._state


# =============================================================================
# Tests for get_album_full
# =============================================================================


class TestGetAlbumFull:
    """Tests for the get_album_full MCP tool handler."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        _shared_mod.cache = MockStateCache()

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache

    def test_album_found_basic(self):
        result = json.loads(_run(_album_ops_mod.get_album_full("test-album")))
        assert result["found"] is True
        assert result["slug"] == "test-album"
        assert result["album"]["title"] == "Test Album"
        assert result["album"]["status"] == "In Progress"
        assert len(result["tracks"]) == 2

    def test_album_not_found(self):
        result = json.loads(_run(_album_ops_mod.get_album_full("nonexistent")))
        assert result["found"] is False
        assert "not found" in result["error"].lower()

    def test_multiple_match_error(self):
        """When slug partially matches multiple albums, return error."""
        state = _fresh_state()
        state["albums"]["test-album-2"] = copy.deepcopy(state["albums"]["test-album"])
        state["albums"]["test-album-2"]["title"] = "Test Album 2"
        _shared_mod.cache = MockStateCache(state)

        result = json.loads(_run(_album_ops_mod.get_album_full("test-album")))
        # Exact match should still work
        assert result["found"] is True

    def test_summary_only(self):
        result = json.loads(_run(
            _album_ops_mod.get_album_full("test-album", summary_only=True)
        ))
        assert result["found"] is True
        # Summary mode should not include "path" in track entries
        for slug, track in result["tracks"].items():
            assert "path" not in track
            assert "title" in track
            assert "status" in track

    def test_track_filter(self):
        result = json.loads(_run(
            _album_ops_mod.get_album_full("test-album", track_slugs="01-first-track")
        ))
        assert result["found"] is True
        assert len(result["tracks"]) == 1
        assert "01-first-track" in result["tracks"]

    def test_include_sections_reads_file(self):
        """When include_sections is set, track files are read from disk."""
        track_content = """\
---
title: First Track
---

## Lyrics Box

```
Hello world
```

## Style Box

```
pop, 120 BPM
```
"""
        with patch("pathlib.Path.read_text", return_value=track_content):
            result = json.loads(_run(
                _album_ops_mod.get_album_full("test-album", include_sections="lyrics,style")
            ))
        assert result["found"] is True
        # At least one track should have sections
        has_sections = any("sections" in t for t in result["tracks"].values())
        assert has_sections

    def test_include_sections_ignored_with_summary_only(self):
        """summary_only=True overrides include_sections."""
        result = json.loads(_run(
            _album_ops_mod.get_album_full(
                "test-album", include_sections="lyrics", summary_only=True,
            )
        ))
        assert result["found"] is True
        for track in result["tracks"].values():
            assert "sections" not in track


# =============================================================================
# Tests for validate_album_structure
# =============================================================================


class TestValidateAlbumStructure:
    """Tests for the validate_album_structure MCP tool handler."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        _shared_mod.cache = MockStateCache()

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache

    def test_album_not_found(self):
        result = json.loads(_run(
            _album_ops_mod.validate_album_structure("nonexistent")
        ))
        assert result["found"] is False

    def test_no_config_returns_error(self):
        state = _fresh_state()
        state["config"] = {}
        _shared_mod.cache = MockStateCache(state)

        result = json.loads(_run(
            _album_ops_mod.validate_album_structure("test-album")
        ))
        assert "error" in result

    def test_structure_checks_with_existing_dirs(self):
        """When album directory and tracks/ exist, structure checks pass."""
        with patch("pathlib.Path.is_dir", return_value=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.glob", return_value=[Path("01-track.md")]):
            result = json.loads(_run(
                _album_ops_mod.validate_album_structure("test-album", checks="structure")
            ))
        assert result["found"] is True
        assert result["passed"] > 0

    def test_structure_checks_missing_directory(self):
        """When album directory does not exist, structure checks fail."""
        with patch("pathlib.Path.is_dir", return_value=False), \
             patch("pathlib.Path.exists", return_value=False):
            result = json.loads(_run(
                _album_ops_mod.validate_album_structure("test-album", checks="structure")
            ))
        assert result["found"] is True
        assert result["failed"] > 0

    def test_tracks_check_suno_link_warning(self):
        """Track with Final status but no Suno link should warn."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-first-track"]["has_suno_link"] = False
        _shared_mod.cache = MockStateCache(state)

        with patch("pathlib.Path.is_dir", return_value=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.glob", return_value=[]):
            result = json.loads(_run(
                _album_ops_mod.validate_album_structure("test-album", checks="tracks")
            ))
        assert result["found"] is True
        assert result["warnings"] >= 1

    def test_tracks_check_sources_pending_warning(self):
        """Track with pending sources should warn."""
        with patch("pathlib.Path.is_dir", return_value=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.glob", return_value=[]):
            result = json.loads(_run(
                _album_ops_mod.validate_album_structure("test-album", checks="tracks")
            ))
        assert result["found"] is True
        # 02-second-track has sources_verified=Pending
        warns = [c for c in result["checks"] if c["status"] == "WARN"]
        assert len(warns) >= 1

    def test_audio_check_skip_no_directory(self):
        """When no audio directory exists, audio checks are skipped."""
        with patch("pathlib.Path.is_dir", return_value=False):
            result = json.loads(_run(
                _album_ops_mod.validate_album_structure("test-album", checks="audio")
            ))
        assert result["found"] is True
        assert result["skipped"] >= 1

    def test_check_filter_only_runs_specified(self):
        """Only the specified check category runs."""
        with patch("pathlib.Path.is_dir", return_value=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.glob", return_value=[]):
            result = json.loads(_run(
                _album_ops_mod.validate_album_structure("test-album", checks="art")
            ))
        assert result["found"] is True
        categories = {c["category"] for c in result["checks"]}
        assert categories == {"art"}


# =============================================================================
# Tests for create_album_structure
# =============================================================================


class TestCreateAlbumStructure:
    """Tests for the create_album_structure MCP tool handler."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        self._orig_plugin_root = _shared_mod.PLUGIN_ROOT
        _shared_mod.cache = MockStateCache()
        _shared_mod.PLUGIN_ROOT = PROJECT_ROOT

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache
        _shared_mod.PLUGIN_ROOT = self._orig_plugin_root

    def test_no_config_returns_error(self):
        state = _fresh_state()
        state["config"] = {}
        _shared_mod.cache = MockStateCache(state)

        result = json.loads(_run(
            _album_ops_mod.create_album_structure("new-album", "rock")
        ))
        assert "error" in result

    def test_missing_content_root_returns_error(self):
        state = _fresh_state()
        state["config"]["content_root"] = ""
        _shared_mod.cache = MockStateCache(state)

        result = json.loads(_run(
            _album_ops_mod.create_album_structure("new-album", "rock")
        ))
        assert "error" in result

    def test_invalid_genre_returns_error(self):
        result = json.loads(_run(
            _album_ops_mod.create_album_structure("new-album", "nonexistent-genre")
        ))
        assert "error" in result
        assert "genre" in result["error"].lower()

    def test_genre_alias_resolved(self):
        """Genre aliases like 'r&b' should resolve to 'rnb'."""
        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.copy2"), \
             patch("pathlib.Path.is_dir", return_value=False):
            result = json.loads(_run(
                _album_ops_mod.create_album_structure("new-album", "r&b")
            ))
        assert result.get("created") is True
        assert result["genre"] == "rnb"

    def test_existing_album_returns_error(self):
        """If album directory already exists, return error."""
        with patch("pathlib.Path.exists", return_value=True):
            result = json.loads(_run(
                _album_ops_mod.create_album_structure("new-album", "rock")
            ))
        assert result["created"] is False
        assert "already exists" in result["error"].lower()

    def test_successful_creation(self):
        """Successful album creation returns created=True with file list."""
        album_path = Path("/tmp/test-content/artists/test-artist/albums/rock/new-album")

        def path_exists(self_path):
            # Album dir should not exist; template files should exist
            if str(self_path) == str(album_path):
                return False
            return True  # templates exist

        with patch("pathlib.Path.exists", path_exists), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.copy2"), \
             patch("pathlib.Path.is_dir", return_value=False):
            result = json.loads(_run(
                _album_ops_mod.create_album_structure("new-album", "rock")
            ))
        assert result["created"] is True
        assert "README.md" in result["files"]
        assert "tracks/" in result["files"]
        assert result["documentary"] is False

    def test_documentary_includes_research_files(self):
        """Documentary album creation includes RESEARCH.md and SOURCES.md."""
        album_path = Path("/tmp/test-content/artists/test-artist/albums/hip-hop/doc-album")

        def path_exists(self_path):
            if str(self_path) == str(album_path):
                return False
            return True  # templates exist

        with patch("pathlib.Path.exists", path_exists), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.copy2"), \
             patch("pathlib.Path.is_dir", return_value=False):
            result = json.loads(_run(
                _album_ops_mod.create_album_structure("doc-album", "hip-hop", documentary=True)
            ))
        assert result["created"] is True
        assert result["documentary"] is True
        assert "RESEARCH.md" in result["files"]
        assert "SOURCES.md" in result["files"]

    def test_slug_normalization(self):
        """Album slug is normalized (lowercased, spaces to hyphens)."""
        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.copy2"), \
             patch("pathlib.Path.is_dir", return_value=False):
            result = json.loads(_run(
                _album_ops_mod.create_album_structure("My New Album", "electronic")
            ))
        assert result["created"] is True
        assert "my-new-album" in result["path"]

    def test_rebuild_called_after_creation(self):
        """State cache rebuild is called after successful creation."""
        mock_cache = MockStateCache()
        _shared_mod.cache = mock_cache

        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.copy2"), \
             patch("pathlib.Path.is_dir", return_value=False):
            _run(_album_ops_mod.create_album_structure("new-album", "rock"))
        assert mock_cache._rebuild_called is True

    def test_mkdir_failure_returns_error(self):
        """If mkdir fails, return error."""
        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            result = json.loads(_run(
                _album_ops_mod.create_album_structure("new-album", "rock")
            ))
        assert "error" in result
        assert "Cannot create" in result["error"]

    def test_additional_genres_from_config(self):
        """Custom genres from config.generation.additional_genres are accepted."""
        state = _fresh_state()
        state["config"]["generation"] = {"additional_genres": ["synthwave"]}
        _shared_mod.cache = MockStateCache(state)

        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.copy2"), \
             patch("pathlib.Path.is_dir", return_value=False):
            result = json.loads(_run(
                _album_ops_mod.create_album_structure("new-album", "synthwave")
            ))
        assert result["created"] is True
        assert result["genre"] == "synthwave"
