#!/usr/bin/env python3
"""Tests for the MCP-wide slug-validation error boundary (issue #443).

#397/#442 caught the slug-``ValueError`` leak in three handlers at the call
site. #443 addresses the whole class: the shared helpers
``_find_album_or_error`` / ``_resolve_audio_dir`` / ``_find_track_or_error``
call ``_normalize_slug`` (which raises on path separators / null bytes /
traversal), and ~13 tool handlers call it directly. The fix:

  * the three shared helpers now convert the ValueError to their structured
    error tuple, and
  * ``install_error_boundary`` wraps every registered tool so any leaked
    ValueError becomes a ``{"error": ...}`` JSON response instead of an
    opaque MCP-layer crash.

Usage:
    python -m pytest tests/unit/state/test_slug_validation_boundary_443.py -v
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import core as _core_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


BAD_SLUGS = ["../evil", "a/b", "a\\b", "a\0b", "a..b"]


class MockStateCache:
    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state

    def rebuild(self) -> dict:
        return self._state


def _base_state() -> dict:
    return copy.deepcopy({
        "config": {"audio_root": "/tmp/audio", "artist_name": "test-artist"},
        "albums": {
            "test-album": {
                "genre": "electronic", "title": "Test Album",
                "status": "In Progress", "tracks": {"01-a": {"title": "A"}},
            },
        },
    })


# ===========================================================================
# _json_error_boundary — unit behavior
# ===========================================================================


@pytest.mark.unit
class TestJsonErrorBoundary:
    def test_value_error_becomes_json(self):
        async def handler(slug: str) -> str:
            raise ValueError("Invalid name: bad")

        wrapped = _shared_mod._json_error_boundary(handler)
        result = json.loads(_run(wrapped("../x")))
        assert result["error"] == "Invalid name: bad"

    def test_normal_return_passes_through(self):
        async def handler(slug: str) -> str:
            return json.dumps({"ok": slug})

        wrapped = _shared_mod._json_error_boundary(handler)
        assert json.loads(_run(wrapped("fine")))["ok"] == "fine"

    def test_non_value_error_still_propagates(self):
        """Only ValueError is caught — real bugs must not be masked."""
        async def handler(slug: str) -> str:
            raise KeyError("genuine bug")

        wrapped = _shared_mod._json_error_boundary(handler)
        with pytest.raises(KeyError):
            _run(wrapped("x"))

    def test_wrapped_handler_stays_a_coroutine_function(self):
        """FastMCP must still see an async tool (schema/dispatch depend on it)."""
        import inspect

        async def handler(slug: str) -> str:
            return "ok"

        wrapped = _shared_mod._json_error_boundary(handler)
        assert inspect.iscoroutinefunction(wrapped)
        # functools.wraps preserves the signature FastMCP introspects.
        assert list(inspect.signature(wrapped).parameters) == ["slug"]
        assert wrapped.__name__ == "handler"


# ===========================================================================
# End-to-end: a previously-unguarded direct-call handler via the boundary
# ===========================================================================


class _FakeMCP:
    """Minimal FastMCP stand-in that stores registered tools by name."""

    def __init__(self) -> None:
        self._tools: dict = {}

    def tool(self):
        def decorator(fn):
            self._tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.mark.unit
class TestBoundaryProtectsDirectCallHandlers:
    """find_album calls _normalize_slug directly — before #443 it raised.

    The boundary installed at registration must turn that into JSON.
    """

    def setup_method(self) -> None:
        self._orig = _shared_mod.cache
        _shared_mod.cache = MockStateCache(_base_state())

    def teardown_method(self) -> None:
        _shared_mod.cache = self._orig

    def _registered_find_album(self):
        mcp = _FakeMCP()
        _shared_mod.install_error_boundary(mcp)
        _core_mod.register(mcp)
        return mcp._tools["find_album"]

    @pytest.mark.parametrize("bad_slug", BAD_SLUGS)
    def test_bad_slug_returns_json_not_raise(self, bad_slug):
        find_album = self._registered_find_album()
        result = json.loads(_run(find_album(bad_slug)))
        assert "error" in result
        assert "Invalid name" in result["error"]

    def test_valid_name_unchanged_through_boundary(self):
        find_album = self._registered_find_album()
        result = json.loads(_run(find_album("test-album")))
        assert result.get("found") is True

    def test_direct_unwrapped_call_still_raises(self):
        """Sanity: the module-level fn is unguarded; the boundary is the fix."""
        with pytest.raises(ValueError):
            _run(_core_mod.find_album("../evil"))


# ===========================================================================
# Shared helpers convert the ValueError in-flow (contract-shaped errors)
# ===========================================================================


@pytest.mark.unit
class TestHelpersHardened:
    def setup_method(self) -> None:
        self._orig = _shared_mod.cache
        _shared_mod.cache = MockStateCache(_base_state())

    def teardown_method(self) -> None:
        _shared_mod.cache = self._orig

    @pytest.mark.parametrize("bad_slug", BAD_SLUGS)
    def test_find_album_or_error_returns_error_tuple(self, bad_slug):
        slug, album, err = _shared_mod._find_album_or_error(bad_slug)
        assert album is None
        assert err is not None
        assert "Invalid name" in json.loads(err)["error"]

    @pytest.mark.parametrize("bad_slug", BAD_SLUGS)
    def test_resolve_audio_dir_returns_error(self, bad_slug):
        err, path = _shared_mod._resolve_audio_dir(bad_slug)
        assert path is None
        assert err is not None
        assert "Invalid name" in json.loads(err)["error"]

    @pytest.mark.parametrize("bad_slug", BAD_SLUGS)
    def test_find_track_or_error_returns_error_tuple(self, bad_slug):
        tracks = {"01-a": {"title": "A"}}
        slug, data, err = _shared_mod._find_track_or_error(tracks, bad_slug)
        assert data is None
        assert err is not None
        assert "Invalid name" in json.loads(err)["error"]

    def test_valid_album_still_resolves(self):
        slug, album, err = _shared_mod._find_album_or_error("test-album")
        assert err is None
        assert album is not None
