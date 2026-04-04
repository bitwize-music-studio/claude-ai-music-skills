#!/usr/bin/env python3
"""
Unit tests for handlers/streaming.py — streaming URL management.

Tests get_streaming_urls, update_streaming_url, and verify_streaming_urls
MCP tool handlers.

Usage:
    python -m pytest tests/unit/state/test_handlers_streaming.py -v
"""

import asyncio
import copy
import importlib
import importlib.util
import json
import sys
import types
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

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
    spec = importlib.util.spec_from_file_location("state_server_streaming", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import streaming as _streaming_mod
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
    },
    "albums": {
        "test-album": {
            "title": "Test Album",
            "status": "Released",
            "genre": "electronic",
            "path": "/tmp/test-content/artists/test-artist/albums/electronic/test-album",
            "track_count": 1,
            "streaming_urls": {
                "soundcloud": "https://soundcloud.com/test/test-album",
                "spotify": "https://open.spotify.com/album/abc123",
                "apple_music": "",
                "youtube_music": "",
                "amazon_music": "",
            },
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
            },
        },
        "empty-urls-album": {
            "title": "Empty URLs Album",
            "status": "Released",
            "genre": "rock",
            "path": "/tmp/test-content/artists/test-artist/albums/rock/empty-urls-album",
            "track_count": 1,
            "streaming_urls": {},
            "tracks": {},
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

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}

    def rebuild(self):
        return self._state


# =============================================================================
# Tests for get_streaming_urls
# =============================================================================


class TestGetStreamingUrls:
    """Tests for the get_streaming_urls MCP tool handler."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        _shared_mod.cache = MockStateCache()

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache

    def test_album_not_found(self):
        result = json.loads(_run(_streaming_mod.get_streaming_urls("nonexistent")))
        assert result["found"] is False

    def test_returns_all_five_platforms(self):
        result = json.loads(_run(_streaming_mod.get_streaming_urls("test-album")))
        assert result["found"] is True
        assert result["total_platforms"] == 5
        assert "soundcloud" in result["urls"]
        assert "spotify" in result["urls"]
        assert "apple_music" in result["urls"]
        assert "youtube_music" in result["urls"]
        assert "amazon_music" in result["urls"]

    def test_filled_urls_counted(self):
        result = json.loads(_run(_streaming_mod.get_streaming_urls("test-album")))
        assert result["filled_count"] == 2  # soundcloud + spotify
        assert len(result["missing"]) == 3

    def test_missing_platforms_listed(self):
        result = json.loads(_run(_streaming_mod.get_streaming_urls("test-album")))
        assert "apple_music" in result["missing"]
        assert "youtube_music" in result["missing"]
        assert "amazon_music" in result["missing"]

    def test_all_empty_urls(self):
        result = json.loads(_run(_streaming_mod.get_streaming_urls("empty-urls-album")))
        assert result["found"] is True
        assert result["filled_count"] == 0
        assert len(result["missing"]) == 5

    def test_url_values_preserved(self):
        result = json.loads(_run(_streaming_mod.get_streaming_urls("test-album")))
        assert result["urls"]["soundcloud"] == "https://soundcloud.com/test/test-album"
        assert result["urls"]["spotify"] == "https://open.spotify.com/album/abc123"


# =============================================================================
# Tests for update_streaming_url
# =============================================================================


class TestUpdateStreamingUrl:
    """Tests for the update_streaming_url MCP tool handler."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        _shared_mod.cache = MockStateCache()

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache

    def test_invalid_platform_returns_error(self):
        result = json.loads(_run(
            _streaming_mod.update_streaming_url("test-album", "bandcamp", "https://example.com")
        ))
        assert "error" in result
        assert "unknown platform" in result["error"].lower()

    def test_invalid_url_returns_error(self):
        result = json.loads(_run(
            _streaming_mod.update_streaming_url("test-album", "spotify", "not-a-url")
        ))
        assert "error" in result
        assert "http" in result["error"].lower()

    def test_empty_url_allowed_for_clear(self):
        """Empty string URL is allowed (clears the value)."""
        readme_content = """\
---
title: Test Album
streaming:
  spotify: "https://old-url.com"
---

# Test Album
"""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=readme_content), \
             patch("pathlib.Path.write_text"), \
             patch("tools.state.indexer.write_state"), \
             patch("tools.state.parsers.parse_album_readme", return_value={"streaming_urls": {}}):
            result = json.loads(_run(
                _streaming_mod.update_streaming_url("test-album", "spotify", "")
            ))
        assert result["success"] is True
        assert result["url"] == ""

    def test_album_not_found(self):
        result = json.loads(_run(
            _streaming_mod.update_streaming_url("nonexistent", "spotify", "https://example.com")
        ))
        assert "found" in result and result["found"] is False

    def test_platform_alias_resolved(self):
        """Platform aliases like 'apple-music' resolve to 'apple_music'."""
        readme_content = """\
---
title: Test Album
streaming:
  apple_music: ""
---

# Test Album
"""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=readme_content), \
             patch("pathlib.Path.write_text"), \
             patch("tools.state.indexer.write_state"), \
             patch("tools.state.parsers.parse_album_readme", return_value={"streaming_urls": {}}):
            result = json.loads(_run(
                _streaming_mod.update_streaming_url(
                    "test-album", "apple-music", "https://music.apple.com/us/album/123",
                )
            ))
        assert result["success"] is True
        assert result["platform"] == "apple_music"

    def test_no_frontmatter_returns_error(self):
        """README without frontmatter returns error."""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="# No Frontmatter"):
            result = json.loads(_run(
                _streaming_mod.update_streaming_url(
                    "test-album", "spotify", "https://example.com",
                )
            ))
        assert "error" in result
        assert "frontmatter" in result["error"].lower()

    def test_no_closing_frontmatter_returns_error(self):
        """README with opening but no closing --- returns error."""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="---\ntitle: broken\n# Content"):
            result = json.loads(_run(
                _streaming_mod.update_streaming_url(
                    "test-album", "spotify", "https://example.com",
                )
            ))
        assert "error" in result

    def test_successful_update_with_existing_key(self):
        """Updating an existing platform key in frontmatter succeeds."""
        readme_content = """\
---
title: Test Album
streaming:
  spotify: "https://old-url.com"
  soundcloud: "https://soundcloud.com/test"
---

# Test Album
"""
        written_content = None

        def capture_write(content, *a, **kw):
            nonlocal written_content
            written_content = content

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=readme_content), \
             patch("pathlib.Path.write_text", side_effect=capture_write), \
             patch("tools.state.indexer.write_state"), \
             patch("tools.state.parsers.parse_album_readme", return_value={"streaming_urls": {}}):
            result = json.loads(_run(
                _streaming_mod.update_streaming_url(
                    "test-album", "spotify", "https://new-url.com",
                )
            ))
        assert result["success"] is True
        assert result["platform"] == "spotify"
        assert result["url"] == "https://new-url.com"
        # Verify the new URL was written
        assert "https://new-url.com" in written_content

    def test_no_path_returns_error(self):
        """If album has no stored path, return error."""
        state = _fresh_state()
        state["albums"]["test-album"]["path"] = ""
        _shared_mod.cache = MockStateCache(state)

        result = json.loads(_run(
            _streaming_mod.update_streaming_url(
                "test-album", "spotify", "https://example.com",
            )
        ))
        assert "error" in result

    def test_readme_not_found_returns_error(self):
        with patch("pathlib.Path.exists", return_value=False):
            result = json.loads(_run(
                _streaming_mod.update_streaming_url(
                    "test-album", "spotify", "https://example.com",
                )
            ))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_db_sync_failure_nonfatal(self):
        """DB sync failure should not prevent the update from succeeding."""
        readme_content = """\
---
title: Test Album
streaming:
  spotify: ""
---

# Test Album
"""
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=readme_content), \
             patch("pathlib.Path.write_text"), \
             patch("tools.state.indexer.write_state"), \
             patch("tools.state.parsers.parse_album_readme", return_value={"streaming_urls": {}}), \
             patch("handlers.database._check_db_deps", side_effect=ImportError("no db")):
            result = json.loads(_run(
                _streaming_mod.update_streaming_url(
                    "test-album", "spotify", "https://example.com",
                )
            ))
        assert result["success"] is True
        assert result["db_synced"] is False


# =============================================================================
# Tests for verify_streaming_urls
# =============================================================================


class TestVerifyStreamingUrls:
    """Tests for the verify_streaming_urls MCP tool handler."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        _shared_mod.cache = MockStateCache()

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache

    def test_album_not_found(self):
        result = json.loads(_run(_streaming_mod.verify_streaming_urls("nonexistent")))
        assert result["found"] is False

    def test_all_empty_urls_returns_not_set(self):
        result = json.loads(_run(
            _streaming_mod.verify_streaming_urls("empty-urls-album")
        ))
        assert result["found"] is True
        assert result["not_set_count"] == 5
        assert result["reachable_count"] == 0
        assert result["all_reachable"] is False

    def test_reachable_url_counted(self):
        """When HTTP requests succeed, URLs are counted as reachable."""
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = "https://soundcloud.com/test/test-album"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = json.loads(_run(
                _streaming_mod.verify_streaming_urls("test-album")
            ))
        assert result["found"] is True
        assert result["reachable_count"] == 2  # soundcloud + spotify
        assert result["not_set_count"] == 3

    def test_unreachable_url_counted(self):
        """When HTTP requests fail, URLs are counted as unreachable."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            result = json.loads(_run(
                _streaming_mod.verify_streaming_urls("test-album")
            ))
        assert result["found"] is True
        assert result["unreachable_count"] == 2
        assert result["all_reachable"] is False

    def test_http_error_405_falls_back_to_get(self):
        """HEAD returning 405 should fall back to GET."""
        call_count = 0

        def mock_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            if req.method == "HEAD":
                raise urllib.error.HTTPError(
                    req.full_url, 405, "Method Not Allowed", {}, None,
                )
            # GET succeeds
            resp = MagicMock()
            resp.getcode.return_value = 200
            resp.geturl.return_value = req.full_url
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            result = json.loads(_run(
                _streaming_mod.verify_streaming_urls("test-album")
            ))
        assert result["reachable_count"] == 2

    def test_redirect_recorded(self):
        """When a URL redirects, the redirect URL is recorded."""
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = "https://new-location.com/redirected"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = json.loads(_run(
                _streaming_mod.verify_streaming_urls("test-album")
            ))
        # At least one URL should have a redirect recorded
        has_redirect = any(
            "redirect_url" in v
            for v in result["results"].values()
            if isinstance(v, dict)
        )
        assert has_redirect

    def test_all_reachable_flag(self):
        """all_reachable is True only when all platforms are set and reachable."""
        # Set all URLs
        state = _fresh_state()
        state["albums"]["test-album"]["streaming_urls"] = {
            "soundcloud": "https://soundcloud.com/test",
            "spotify": "https://spotify.com/test",
            "apple_music": "https://music.apple.com/test",
            "youtube_music": "https://music.youtube.com/test",
            "amazon_music": "https://music.amazon.com/test",
        }
        _shared_mod.cache = MockStateCache(state)

        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.geturl.return_value = "https://example.com"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = json.loads(_run(
                _streaming_mod.verify_streaming_urls("test-album")
            ))
        assert result["all_reachable"] is True
        assert result["reachable_count"] == 5
        assert result["not_set_count"] == 0

    def test_unsupported_url_scheme_rejected(self):
        """URLs with non-http(s) schemes should fail validation."""
        state = _fresh_state()
        state["albums"]["test-album"]["streaming_urls"] = {
            "soundcloud": "file:///etc/passwd",
            "spotify": "",
            "apple_music": "",
            "youtube_music": "",
            "amazon_music": "",
        }
        _shared_mod.cache = MockStateCache(state)

        result = json.loads(_run(
            _streaming_mod.verify_streaming_urls("test-album")
        ))
        sc_result = result["results"]["soundcloud"]
        assert sc_result["reachable"] is False
        assert "scheme" in sc_result.get("error", "").lower()
