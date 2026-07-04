#!/usr/bin/env python3
"""Unit tests for handlers/content.py — overrides, reference files, clipboard.

Covers the three public MCP tools:

    load_override(override_name)          — user override file loading
    get_reference(name, section)          — plugin reference file reads
    format_for_clipboard(album, track, …) — track section extraction/format

Each tool gets a happy path plus a missing-file / unknown-name error and a
malformed-input case (path traversal or invalid content-type). Follows the
fixture/mocking style of test_handlers_streaming.py: mock StateCache via
``_shared.cache``, an ``asyncio.run`` helper, and structured-JSON assertions.

Usage:
    python -m pytest tests/unit/state/test_handlers_content.py -v
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
    spec = importlib.util.spec_from_file_location("state_server_content", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import content as _content_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Mock cache + sample track content
# ---------------------------------------------------------------------------


class MockStateCache:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}


# A full track file with every section format_for_clipboard understands.
FULL_TRACK_MD = """# First Track

## Style Box

```
synthwave, retro, 118 BPM, driving bassline
```

## Exclude Styles

```
country, banjo, twang
```

## Lyrics Box

```
[Verse 1]
Neon rain on the boulevard tonight
```

## Streaming Lyrics

```
Neon rain on the boulevard tonight
```
"""

# A bare track file with only a Lyrics Box — used for "section missing" cases.
BARE_TRACK_MD = """# Bare Track

## Lyrics Box

```
[Verse 1]
Just the words, nothing else here
```
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def override_env(tmp_path):
    """Overrides directory on disk + a mock cache pointing config at it."""
    overrides_dir = tmp_path / "overrides"
    overrides_dir.mkdir()
    (overrides_dir / "pronunciation-guide.md").write_text(
        "# Pronunciation\n\nbitwize -> bit-wize\n", encoding="utf-8",
    )

    state = {"config": {"overrides_dir": str(overrides_dir)}}
    orig_cache = _shared_mod.cache
    _shared_mod.cache = MockStateCache(state)
    yield overrides_dir
    _shared_mod.cache = orig_cache


@pytest.fixture
def reference_env(tmp_path):
    """Temp plugin root with a reference/ tree; installs into _shared.PLUGIN_ROOT."""
    ref_dir = tmp_path / "reference" / "suno"
    ref_dir.mkdir(parents=True)
    (ref_dir / "test-guide.md").write_text(
        "# Test Guide\n\nIntro line.\n\n"
        "## Section A\n\nAlpha content here.\n\n"
        "## Section B\n\nBeta content here.\n",
        encoding="utf-8",
    )

    orig_root = _shared_mod.PLUGIN_ROOT
    _shared_mod.PLUGIN_ROOT = tmp_path
    yield tmp_path
    _shared_mod.PLUGIN_ROOT = orig_root


@pytest.fixture
def clipboard_env(tmp_path):
    """Album with three tracks (full / bare / no-path) plus a mock cache."""
    album_dir = tmp_path / "album"
    tracks_dir = album_dir / "tracks"
    tracks_dir.mkdir(parents=True)

    full_path = tracks_dir / "01-first-track.md"
    full_path.write_text(FULL_TRACK_MD, encoding="utf-8")
    bare_path = tracks_dir / "02-bare-track.md"
    bare_path.write_text(BARE_TRACK_MD, encoding="utf-8")

    state = {
        "config": {"content_root": str(tmp_path)},
        "albums": {
            "test-album": {
                "title": "Test Album",
                "genre": "electronic",
                "path": str(album_dir),
                "tracks": {
                    "01-first-track": {"title": "First Track", "path": str(full_path)},
                    "02-bare-track": {"title": "Bare Track", "path": str(bare_path)},
                    "03-no-path": {"title": "No Path", "path": ""},
                },
            },
        },
    }
    orig_cache = _shared_mod.cache
    _shared_mod.cache = MockStateCache(state)
    yield album_dir
    _shared_mod.cache = orig_cache


# ===========================================================================
# load_override
# ===========================================================================


class TestLoadOverride:
    def test_existing_override_returns_content(self, override_env):
        result = json.loads(_run(_content_mod.load_override("pronunciation-guide.md")))
        assert result["found"] is True
        assert result["override_name"] == "pronunciation-guide.md"
        assert "bit-wize" in result["content"]
        assert result["size"] == len(result["content"])

    def test_missing_override_returns_not_found(self, override_env):
        result = json.loads(_run(_content_mod.load_override("does-not-exist.md")))
        assert result["found"] is False
        assert result["override_name"] == "does-not-exist.md"

    def test_path_traversal_is_rejected(self, override_env):
        result = json.loads(_run(_content_mod.load_override("../secret.txt")))
        assert "error" in result
        assert "escape" in result["error"].lower()

    def test_no_config_returns_error(self):
        orig = _shared_mod.cache
        _shared_mod.cache = MockStateCache({})
        try:
            result = json.loads(_run(_content_mod.load_override("anything.md")))
        finally:
            _shared_mod.cache = orig
        assert "error" in result
        assert "config" in result["error"].lower()

    def test_falls_back_to_content_root_overrides(self, tmp_path):
        """With no overrides_dir set, config.content_root/overrides is used."""
        overrides_dir = tmp_path / "overrides"
        overrides_dir.mkdir()
        (overrides_dir / "CLAUDE.md").write_text("custom rules", encoding="utf-8")

        orig = _shared_mod.cache
        _shared_mod.cache = MockStateCache({"config": {"content_root": str(tmp_path)}})
        try:
            result = json.loads(_run(_content_mod.load_override("CLAUDE.md")))
        finally:
            _shared_mod.cache = orig
        assert result["found"] is True
        assert result["content"] == "custom rules"


# ===========================================================================
# get_reference
# ===========================================================================


class TestGetReference:
    def test_full_file_returned(self, reference_env):
        result = json.loads(_run(_content_mod.get_reference("suno/test-guide")))
        assert result["found"] is True
        assert "Alpha content here." in result["content"]
        assert "Beta content here." in result["content"]
        assert result["size"] == len(result["content"])

    def test_missing_md_extension_is_added(self, reference_env):
        """A name without a .md suffix still resolves the .md file."""
        with_ext = json.loads(_run(_content_mod.get_reference("suno/test-guide.md")))
        without_ext = json.loads(_run(_content_mod.get_reference("suno/test-guide")))
        assert with_ext["content"] == without_ext["content"]

    def test_section_extracted(self, reference_env):
        result = json.loads(
            _run(_content_mod.get_reference("suno/test-guide", section="Section A"))
        )
        assert result["found"] is True
        assert result["section"] == "Section A"
        assert result["content"] == "Alpha content here."
        assert "Beta" not in result["content"]

    def test_unknown_section_returns_error(self, reference_env):
        result = json.loads(
            _run(_content_mod.get_reference("suno/test-guide", section="Nowhere"))
        )
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_missing_reference_returns_error(self, reference_env):
        result = json.loads(_run(_content_mod.get_reference("suno/nonexistent")))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_path_traversal_is_rejected(self, reference_env):
        result = json.loads(_run(_content_mod.get_reference("../secret")))
        assert "error" in result
        assert "escape" in result["error"].lower()


# ===========================================================================
# format_for_clipboard
# ===========================================================================


class TestFormatForClipboard:
    def test_lyrics_extracted(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "01-first-track", "lyrics"))
        )
        assert result["found"] is True
        assert result["content_type"] == "lyrics"
        assert "Neon rain on the boulevard" in result["content"]

    def test_style_includes_exclude(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "01-first-track", "style"))
        )
        assert result["found"] is True
        # Style Box + Exclude Styles are joined when both are present.
        assert "synthwave" in result["content"]
        assert "country" in result["content"]

    def test_all_combines_sections(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "01-first-track", "all"))
        )
        assert result["found"] is True
        assert "synthwave" in result["content"]
        assert "Exclude:" in result["content"]
        assert "Neon rain on the boulevard" in result["content"]

    def test_suno_returns_json_object(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "01-first-track", "suno"))
        )
        assert result["found"] is True
        payload = json.loads(result["content"])
        assert payload["title"] == "First Track"
        assert "synthwave" in payload["style"]
        assert "country" in payload["exclude_styles"]
        assert "Neon rain on the boulevard" in payload["lyrics"]

    def test_prefix_track_match_works(self, clipboard_env):
        """A bare track number resolves via prefix match."""
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "01", "lyrics"))
        )
        assert result["found"] is True
        assert result["track_slug"] == "01-first-track"

    def test_invalid_content_type_returns_error(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "01-first-track", "bogus"))
        )
        assert "error" in result
        assert "invalid content_type" in result["error"].lower()

    def test_album_not_found(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("nonexistent", "01-first-track", "lyrics"))
        )
        assert result["found"] is False

    def test_track_not_found(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "99-ghost", "lyrics"))
        )
        assert result["found"] is False

    def test_missing_section_returns_not_found(self, clipboard_env):
        """The bare track has no Style Box, so a 'style' request finds nothing."""
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "02-bare-track", "style"))
        )
        assert result["found"] is False
        assert "not found" in result["error"].lower()

    def test_track_without_path_returns_not_found(self, clipboard_env):
        result = json.loads(
            _run(_content_mod.format_for_clipboard("test-album", "03-no-path", "lyrics"))
        )
        assert result["found"] is False
        assert "no path" in result["error"].lower()
