#!/usr/bin/env python3
"""Unit tests for slug-validation error handling in MCP handlers (issue #397).

``_normalize_slug`` raises ValueError on path separators, null bytes, and
traversal sequences. The handler-level call sites in ``handlers/maintenance.py``
(migrate_audio_layout, reset_mastering via _resolve_audio_dir) and
``handlers/skills.py`` (get_skill) must catch that ValueError and return the
module's structured JSON error (``{"error": ...}``) instead of letting the
exception propagate to the FastMCP layer as an opaque tool error.

Usage:
    python -m pytest tests/unit/state/test_slug_validation_handlers.py -v
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root and server directory are on sys.path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import maintenance as _maintenance_mod  # noqa: E402
from handlers import skills as _skills_mod  # noqa: E402

# Slugs that _normalize_slug rejects with ValueError. The first three hit
# the separator/null-byte branch via '/' or '\\'; "a\0b" hits the same
# branch via a null byte alone; "a..b" has no separator, so it reaches and
# exercises the second ('..' traversal) raise branch.
BAD_SLUGS = ["../evil", "a/b", "a\\b", "a\0b", "a..b"]


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class MockStateCache:
    """In-memory StateCache stand-in (no filesystem I/O)."""

    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _base_state(audio_root: str = "/tmp/test/audio") -> dict:
    """Minimal state with config, one album, and one skill."""
    return copy.deepcopy({
        "config": {
            "audio_root": audio_root,
            "artist_name": "test-artist",
        },
        "albums": {
            "test-album": {
                "genre": "electronic",
                "title": "Test Album",
                "status": "In Progress",
                "tracks": {},
            },
        },
        "skills": {
            "count": 1,
            "model_counts": {"opus": 1},
            "items": {
                "lyric-writer": {
                    "description": "Writes or reviews lyrics.",
                    "model": "claude-opus-4-6",
                    "model_tier": "opus",
                    "user_invocable": True,
                    "argument_hint": None,
                },
            },
        },
    })


# =============================================================================
# migrate_audio_layout — invalid slugs return structured error JSON
# =============================================================================


@pytest.mark.unit
class TestMigrateAudioLayoutSlugValidation:
    """migrate_audio_layout must reject bad slugs with a JSON error, not raise."""

    @pytest.mark.parametrize("bad_slug", BAD_SLUGS)
    def test_bad_slug_returns_structured_error(self, bad_slug):
        mock_cache = MockStateCache(_base_state())
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout(album_slug=bad_slug, dry_run=True)
            ))
        assert "error" in result
        assert "Invalid name" in result["error"]

    def test_valid_slug_behavior_unchanged(self):
        """A valid slug with no audio dir on disk is skipped, not errored."""
        mock_cache = MockStateCache(_base_state(audio_root="/nonexistent/audio"))
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout(album_slug="test-album", dry_run=True)
            ))
        assert "error" not in result
        assert result["summary"]["total_albums"] == 1
        assert result["albums"][0]["slug"] == "test-album"
        assert result["albums"][0]["status"] == "skipped"
        assert result["albums"][0]["skip_reason"] == "no audio dir"

    def test_valid_slug_not_in_state_returns_not_found(self):
        """A well-formed but unknown slug still gets the not-found error."""
        mock_cache = MockStateCache(_base_state())
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout(album_slug="no-such-album", dry_run=True)
            ))
        assert "error" in result
        assert "not found" in result["error"]


# =============================================================================
# reset_mastering — invalid slugs return structured error JSON
# =============================================================================


@pytest.mark.unit
class TestResetMasteringSlugValidation:
    """reset_mastering must reject bad slugs with a JSON error, not raise."""

    @pytest.mark.parametrize("bad_slug", BAD_SLUGS)
    def test_bad_slug_returns_structured_error(self, bad_slug):
        mock_cache = MockStateCache(_base_state())
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                _maintenance_mod.reset_mastering(album_slug=bad_slug, dry_run=True)
            ))
        assert "error" in result
        assert "Invalid name" in result["error"]

    def test_valid_slug_behavior_unchanged(self, tmp_path):
        """A valid slug with a real audio dir still runs the dry-run report."""
        audio_root = tmp_path / "audio"
        album_dir = (
            audio_root / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        )
        mastered = album_dir / "mastered"
        mastered.mkdir(parents=True)
        (mastered / "01-track.wav").write_bytes(b"\x00" * 16)

        mock_cache = MockStateCache(_base_state(audio_root=str(audio_root)))
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                _maintenance_mod.reset_mastering(album_slug="test-album", dry_run=True)
            ))
        assert "error" not in result
        assert result["dry_run"] is True
        assert result["results"]["mastered"]["status"] == "would_delete"
        assert result["results"]["mastered"]["file_count"] == 1
        # Dry run must not delete anything
        assert mastered.is_dir()


# =============================================================================
# get_skill — invalid names return structured error JSON
# =============================================================================


@pytest.mark.unit
class TestGetSkillSlugValidation:
    """get_skill must reject bad names with a JSON error, not raise."""

    @pytest.mark.parametrize("bad_slug", BAD_SLUGS)
    def test_bad_name_returns_structured_error(self, bad_slug):
        mock_cache = MockStateCache(_base_state())
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(_skills_mod.get_skill(name=bad_slug)))
        assert "error" in result
        assert "Invalid name" in result["error"]

    def test_valid_name_behavior_unchanged(self):
        """An exact skill name still resolves to found=True."""
        mock_cache = MockStateCache(_base_state())
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(_skills_mod.get_skill(name="lyric-writer")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"

    def test_valid_name_normalization_unchanged(self):
        """Names with spaces/case still normalize to the slug and match."""
        mock_cache = MockStateCache(_base_state())
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(_skills_mod.get_skill(name="Lyric Writer")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"
