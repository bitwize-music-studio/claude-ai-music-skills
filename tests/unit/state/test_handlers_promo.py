#!/usr/bin/env python3
"""Unit tests for handlers/promo.py — promo directory status and content.

Covers the two public MCP tools:

    get_promo_status(album_slug)            — per-file promo/ population report
    get_promo_content(album_slug, platform) — single promo file read

Each tool gets a happy path plus album-not-found and a malformed-slug case;
get_promo_content also gets the unknown-platform case. Follows the fixture/mocking style of
test_handlers_streaming.py: mock StateCache via ``_shared.cache``, an
``asyncio.run`` helper, and structured-JSON assertions. Real files on disk are
used because both handlers do genuine filesystem reads and word counting.

Usage:
    python -m pytest tests/unit/state/test_handlers_promo.py -v
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
# Ensure project root is on sys.path for imports
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed (same pattern as test_handlers_streaming.py)
# ---------------------------------------------------------------------------

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
    spec = importlib.util.spec_from_file_location("state_server_promo", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import promo as _promo_mod  # noqa: E402
from handlers.status import _PROMO_FILES  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Mock cache
# ---------------------------------------------------------------------------


class MockStateCache:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}


# A block of real prose that clears the handler's >20-word "populated" threshold.
_POPULATED_TEXT = (
    "The record drops this Friday and it is the loudest, most honest set of "
    "songs we have ever committed to tape, so turn it up and tell a friend "
    "because this one is going to move you all the way through the night."
)


def _install_cache(album_dir: Path):
    state = {
        "config": {"content_root": str(album_dir.parent)},
        "albums": {
            "test-album": {
                "title": "Test Album",
                "genre": "electronic",
                "path": str(album_dir),
                "tracks": {},
            },
        },
    }
    orig = _shared_mod.cache
    _shared_mod.cache = MockStateCache(state)
    return orig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def album_no_promo(tmp_path):
    """Album directory that exists but has no promo/ subdirectory."""
    album_dir = tmp_path / "album"
    album_dir.mkdir()
    orig = _install_cache(album_dir)
    yield album_dir
    _shared_mod.cache = orig


@pytest.fixture
def album_full_promo(tmp_path):
    """Album with every promo file populated with real prose."""
    album_dir = tmp_path / "album"
    promo_dir = album_dir / "promo"
    promo_dir.mkdir(parents=True)
    for fname in _PROMO_FILES:
        (promo_dir / fname).write_text(
            f"# {fname}\n\n{_POPULATED_TEXT}\n", encoding="utf-8",
        )
    orig = _install_cache(album_dir)
    yield album_dir, promo_dir
    _shared_mod.cache = orig


@pytest.fixture
def album_partial_promo(tmp_path):
    """Album where only one promo file has real content; the rest are placeholders."""
    album_dir = tmp_path / "album"
    promo_dir = album_dir / "promo"
    promo_dir.mkdir(parents=True)
    for i, fname in enumerate(_PROMO_FILES):
        if i == 0:
            body = _POPULATED_TEXT
        else:
            # Heading + a bracketed placeholder line — counts as zero real words.
            body = "[replace this with your copy]"
        (promo_dir / fname).write_text(f"# {fname}\n\n{body}\n", encoding="utf-8")
    orig = _install_cache(album_dir)
    yield album_dir, promo_dir
    _shared_mod.cache = orig


# ===========================================================================
# get_promo_status
# ===========================================================================


class TestGetPromoStatus:
    def test_all_populated_is_ready(self, album_full_promo):
        _album_dir, _promo_dir = album_full_promo
        result = json.loads(_run(_promo_mod.get_promo_status("test-album")))
        assert result["found"] is True
        assert result["promo_exists"] is True
        assert result["total"] == len(_PROMO_FILES)
        assert result["populated"] == len(_PROMO_FILES)
        assert result["ready"] is True
        assert len(result["files"]) == len(_PROMO_FILES)
        assert all(f["populated"] for f in result["files"])

    def test_partial_population_not_ready(self, album_partial_promo):
        _album_dir, _promo_dir = album_partial_promo
        result = json.loads(_run(_promo_mod.get_promo_status("test-album")))
        assert result["found"] is True
        assert result["populated"] == 1
        assert result["ready"] is False
        placeholder_files = [f for f in result["files"] if not f["populated"]]
        assert len(placeholder_files) == len(_PROMO_FILES) - 1
        # Bracketed placeholder lines are excluded from the word count.
        assert all(f["word_count"] == 0 for f in placeholder_files)

    def test_no_promo_directory(self, album_no_promo):
        result = json.loads(_run(_promo_mod.get_promo_status("test-album")))
        assert result["found"] is True
        assert result["promo_exists"] is False
        assert result["files"] == []
        assert result["populated"] == 0
        assert result["total"] == len(_PROMO_FILES)

    def test_album_not_found(self, album_full_promo):
        result = json.loads(_run(_promo_mod.get_promo_status("no-such-album")))
        assert result["found"] is False
        assert "not found" in result["error"].lower()

    # BAD_SLUGS mirrors test_slug_validation_handlers.py: the first three hit
    # the separator/null-byte raise branch via '/' or '\\', "a\0b" via a null
    # byte, and "a..b" (no separator) exercises the '..' traversal branch.
    @pytest.mark.parametrize("bad_slug", ["../evil", "a/b", "a\\b", "a\0b", "a..b"])
    def test_malformed_slug_returns_structured_error(self, album_full_promo, bad_slug):
        """A slug with a path separator, null byte, or traversal sequence is
        rejected with a structured JSON error, not an escaped ValueError."""
        result = json.loads(_run(_promo_mod.get_promo_status(bad_slug)))
        assert result["found"] is False
        assert "Invalid name" in result["error"]


# ===========================================================================
# get_promo_content
# ===========================================================================


class TestGetPromoContent:
    def test_reads_platform_file(self, album_full_promo):
        _album_dir, _promo_dir = album_full_promo
        result = json.loads(_run(_promo_mod.get_promo_content("test-album", "twitter")))
        assert result["found"] is True
        assert result["platform"] == "twitter"
        assert _POPULATED_TEXT in result["content"]
        assert result["path"].endswith("twitter.md")

    def test_platform_name_is_normalized(self, album_full_promo):
        """Mixed case and surrounding whitespace resolve to the canonical file."""
        _album_dir, _promo_dir = album_full_promo
        result = json.loads(_run(_promo_mod.get_promo_content("test-album", "  Twitter  ")))
        assert result["found"] is True
        assert result["platform"] == "twitter"

    def test_unknown_platform_returns_error(self, album_full_promo):
        result = json.loads(_run(_promo_mod.get_promo_content("test-album", "snapchat")))
        assert "error" in result
        assert "unknown platform" in result["error"].lower()

    def test_album_not_found(self, album_full_promo):
        result = json.loads(_run(_promo_mod.get_promo_content("no-such-album", "twitter")))
        assert result["found"] is False
        assert "not found" in result["error"].lower()

    def test_promo_file_missing_on_disk(self, album_no_promo):
        """Valid platform but the file does not exist under promo/."""
        result = json.loads(_run(_promo_mod.get_promo_content("test-album", "twitter")))
        assert result["found"] is False
        assert "not found" in result["error"].lower()
        assert result["platform"] == "twitter"
