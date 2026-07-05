#!/usr/bin/env python3
"""Regression tests for handlers/ideas.py — create_idea duplicate guard (#395).

create_idea's duplicate check must be case-insensitive to match the readers
(_find_idea_in_state / get_ideas / promote_idea), which compare titles via
``title.strip().lower()``. Before the fix the guard did an exact-case
substring match (``f"### {title.strip()}\n" in text``), so "cyberpunk dreams"
could be created alongside an existing "Cyberpunk Dreams", producing two
entries the readers then treat as the same idea.

Usage:
    python -m pytest tests/unit/state/test_create_idea_dup_395.py -v
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# Mock the MCP SDK if not installed
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
    spec = importlib.util.spec_from_file_location("state_server_dup395", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import ideas as _ideas_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockStateCache:
    """In-memory state cache; rebuild() is a no-op that records calls."""

    def __init__(self, state: dict) -> None:
        self._state = state
        self.rebuild_called = 0

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state

    def rebuild(self):
        self.rebuild_called += 1
        return self._state


def _make_state(content_root: Path) -> dict:
    return {
        "version": 2,
        "config": {"content_root": str(content_root), "artist_name": "test-artist"},
        "albums": {},
        "ideas": {"counts": {}, "items": [], "total": 0},
        "session": {},
    }


def _count_headers(text: str) -> int:
    """Count '### <title>' idea headers in IDEAS.md text."""
    return len(re.findall(r'^###\s+', text, re.MULTILINE))


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir(parents=True)
    return root


@pytest.fixture
def use_cache(content_root: Path):
    """Install a MockStateCache pointing at content_root; restore afterward."""
    orig_cache = _shared_mod.cache
    cache = MockStateCache(_make_state(content_root))
    _shared_mod.cache = cache
    yield cache
    _shared_mod.cache = orig_cache


def _write_ideas_md(content_root: Path, body: str) -> Path:
    ideas_path = content_root / "IDEAS.md"
    ideas_path.write_text(body, encoding="utf-8")
    return ideas_path


# ---------------------------------------------------------------------------
# Case-insensitive duplicate guard (#395)
# ---------------------------------------------------------------------------


class TestCreateIdeaCaseInsensitiveDuplicate:
    def test_lowercase_dup_of_titlecase_rejected(self, content_root, use_cache):
        """"cyberpunk dreams" is a duplicate of an existing "Cyberpunk Dreams"."""
        ideas_path = _write_ideas_md(
            content_root,
            "# Album Ideas\n\n## Ideas\n\n### Cyberpunk Dreams\n"
            "**Genre**: electronic\n**Status**: Pending\n",
        )

        result = json.loads(_run(_ideas_mod.create_idea("cyberpunk dreams")))

        assert result["created"] is False
        assert "already exists" in result["error"]
        # No second section was written.
        text = ideas_path.read_text(encoding="utf-8")
        assert _count_headers(text) == 1
        assert "### cyberpunk dreams" not in text

    def test_uppercase_dup_of_titlecase_rejected(self, content_root, use_cache):
        """Uppercasing an existing title is still a duplicate."""
        ideas_path = _write_ideas_md(
            content_root,
            "# Album Ideas\n\n## Ideas\n\n### Cyberpunk Dreams\n**Status**: Pending\n",
        )

        result = json.loads(_run(_ideas_mod.create_idea("CYBERPUNK DREAMS")))

        assert result["created"] is False
        assert "already exists" in result["error"]
        assert _count_headers(ideas_path.read_text(encoding="utf-8")) == 1

    def test_exact_case_dup_still_rejected(self, content_root, use_cache):
        """Existing exact-case behavior is preserved."""
        ideas_path = _write_ideas_md(
            content_root,
            "# Album Ideas\n\n## Ideas\n\n### Cyberpunk Dreams\n**Status**: Pending\n",
        )

        result = json.loads(_run(_ideas_mod.create_idea("Cyberpunk Dreams")))

        assert result["created"] is False
        assert "already exists" in result["error"]
        assert _count_headers(ideas_path.read_text(encoding="utf-8")) == 1


class TestCreateIdeaGenuinelyNew:
    def test_new_distinct_title_still_created(self, content_root, use_cache):
        """A title that isn't a case-variant of any existing idea is created."""
        ideas_path = _write_ideas_md(
            content_root,
            "# Album Ideas\n\n## Ideas\n\n### Cyberpunk Dreams\n**Status**: Pending\n",
        )

        result = json.loads(_run(_ideas_mod.create_idea("Synthwave Nights")))

        assert result["created"] is True
        assert result["title"] == "Synthwave Nights"
        text = ideas_path.read_text(encoding="utf-8")
        # Both the original and the new idea are present.
        assert "### Cyberpunk Dreams" in text
        assert "### Synthwave Nights" in text
        assert _count_headers(text) == 2

    def test_new_title_created_into_empty_ideas(self, content_root, use_cache):
        """Sanity: a first idea into a fresh file is created."""
        ideas_path = _write_ideas_md(content_root, "# Album Ideas\n\n## Ideas\n")

        result = json.loads(_run(_ideas_mod.create_idea("Cyberpunk Dreams")))

        assert result["created"] is True
        assert _count_headers(ideas_path.read_text(encoding="utf-8")) == 1
