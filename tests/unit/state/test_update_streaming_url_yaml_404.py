#!/usr/bin/env python3
"""
Regression tests for issue #404 — update_streaming_url YAML escaping.

The in-place frontmatter edit path in update_streaming_url must YAML-escape
the URL before writing it into a double-quoted scalar. A URL containing a
double-quote or backslash previously produced malformed YAML, which the
immediate re-parse then dropped (silently losing the URL from the state
cache while leaving the README file corrupt).

These tests drive a real README.md through the handler and the real
parse_album_readme parser to prove the written frontmatter stays valid and
the URL round-trips.

Usage:
    python -m pytest tests/unit/state/test_update_streaming_url_yaml_404.py -v
"""

import asyncio
import copy
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import yaml

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed (mirrors test_handlers_streaming.py)
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
    spec = importlib.util.spec_from_file_location("state_server_streaming_404", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import streaming as _streaming_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


class MockStateCache:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}

    def rebuild(self):
        return self._state


def _state_for(album_path: str) -> dict:
    return {
        "version": 2,
        "albums": {
            "test-album": {
                "title": "Test Album",
                "status": "Released",
                "genre": "electronic",
                "path": album_path,
                "streaming_urls": {
                    "spotify": "https://old-url.com",
                },
                "tracks": {},
            },
        },
    }


# Existing streaming block so the in-place edit path (the buggy one) is taken
# instead of the yaml.dump fallback.
_README_TEMPLATE = """\
---
title: Test Album
streaming:
  spotify: "https://old-url.com"
---

# Test Album

| **Status** | Released |
"""


def _write_readme(tmp_path: Path) -> Path:
    readme = tmp_path / "README.md"
    readme.write_text(_README_TEMPLATE, encoding="utf-8")
    return readme


def _do_update(tmp_path: Path, platform: str, url: str) -> dict:
    """Run update_streaming_url against a real README, real parser.

    write_state and the DB sync are stubbed out; everything else (file I/O,
    parse_album_readme) is exercised for real so the round-trip is genuine.
    """
    readme = _write_readme(tmp_path)
    state = _state_for(str(tmp_path))
    orig_cache = _shared_mod.cache
    _shared_mod.cache = MockStateCache(state)
    try:
        with patch("tools.state.indexer.write_state"), \
             patch("handlers.database._check_db_deps",
                   side_effect=ImportError("no db")):
            result = json.loads(
                _run(_streaming_mod.update_streaming_url("test-album", platform, url))
            )
    finally:
        _shared_mod.cache = orig_cache
    result["_readme_text"] = readme.read_text(encoding="utf-8")
    result["_state_streaming"] = copy.deepcopy(
        state["albums"]["test-album"]["streaming_urls"]
    )
    return result


def _reparse_streaming(readme_text: str) -> dict:
    """Parse the streaming block back out of the written README frontmatter.

    Raises yaml.YAMLError if the frontmatter is malformed — which is exactly
    the failure mode issue #404 describes.
    """
    lines = readme_text.split("\n")
    end = next(i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---")
    fm = yaml.safe_load("\n".join(lines[1:end])) or {}
    return fm.get("streaming", {}) or {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateStreamingUrlYamlEscaping:
    """Issue #404: in-place frontmatter edit must YAML-escape the URL."""

    def test_url_with_double_quote_stays_valid_yaml(self, tmp_path):
        """A URL containing a double-quote must not corrupt the frontmatter."""
        url = 'https://example.com/track?ref="promo"&id=5'
        result = _do_update(tmp_path, "spotify", url)

        assert result["success"] is True
        assert result["url"] == url

        # Frontmatter must still be valid YAML and round-trip the exact URL.
        streaming = _reparse_streaming(result["_readme_text"])
        assert streaming.get("spotify") == url

        # And the state cache re-parse must have kept the URL (not silently
        # dropped it because the frontmatter went malformed).
        assert result["_state_streaming"].get("spotify") == url

    def test_url_with_backslash_stays_valid_yaml(self, tmp_path):
        """A URL containing a backslash must not corrupt the frontmatter."""
        url = 'https://example.com/track\\weird?q="x"'
        result = _do_update(tmp_path, "spotify", url)

        assert result["success"] is True
        streaming = _reparse_streaming(result["_readme_text"])
        assert streaming.get("spotify") == url
        assert result["_state_streaming"].get("spotify") == url

    def test_normal_url_still_round_trips(self, tmp_path):
        """Regression guard: an ordinary URL keeps working after the fix."""
        url = "https://open.spotify.com/album/abc123"
        result = _do_update(tmp_path, "spotify", url)

        assert result["success"] is True
        assert result["url"] == url

        # Written frontmatter should not contain JSON-escape artifacts for a
        # URL that needs no escaping.
        assert f'spotify: "{url}"' in result["_readme_text"]

        streaming = _reparse_streaming(result["_readme_text"])
        assert streaming.get("spotify") == url
        assert result["_state_streaming"].get("spotify") == url
