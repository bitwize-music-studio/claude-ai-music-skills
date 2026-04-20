#!/usr/bin/env python3
"""Unit tests for handlers/rename.py — album and track renaming.

Tests rename_album and rename_track MCP tool handlers. Uses a real temp
filesystem (``tmp_path``) because both handlers perform real ``shutil.move``
on content / audio / documents directories, so mocks would hide the actual
file-move behavior we care about most (destructive, hard to undo).

Usage:
    python -m pytest tests/unit/state/test_handlers_rename.py -v
"""

from __future__ import annotations

import asyncio
import copy
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed (same pattern as test_handlers_album_ops.py)
# ---------------------------------------------------------------------------

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
    spec = importlib.util.spec_from_file_location("state_server_rename", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import rename as _rename_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures: realistic filesystem layout + mock cache
# ---------------------------------------------------------------------------


class MockStateCache:
    def __init__(self, state: dict) -> None:
        self._state = state
        self.write_calls = 0

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _make_album_on_disk(
    content_root: Path,
    audio_root: Path,
    documents_root: Path,
    artist: str,
    genre: str,
    slug: str,
    title: str,
    tracks: list[tuple[str, str]],  # [(track_slug, track_title), ...]
    make_audio_dir: bool = True,
    make_documents_dir: bool = True,
) -> dict:
    """Write album + track files to disk and return the state-cache album dict."""
    content_dir = content_root / "artists" / artist / "albums" / genre / slug
    tracks_dir = content_dir / "tracks"
    tracks_dir.mkdir(parents=True)

    readme = content_dir / "README.md"
    readme.write_text(
        f"# {title}\n\n## Album Details\n\n| **Title** | {title} |\n",
        encoding="utf-8",
    )

    track_map: dict = {}
    for tslug, ttitle in tracks:
        track_path = tracks_dir / f"{tslug}.md"
        track_path.write_text(
            f"""---
title: "{ttitle}"
status: "In Progress"
---

# {ttitle}

## Track Details

| **Title** | {ttitle} |
| **Status** | In Progress |
""",
            encoding="utf-8",
        )
        track_map[tslug] = {
            "title": ttitle,
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "path": str(track_path),
            "mtime": track_path.stat().st_mtime,
        }

    if make_audio_dir:
        audio_dir = audio_root / "artists" / artist / "albums" / genre / slug
        audio_dir.mkdir(parents=True)
        (audio_dir / "placeholder.wav").write_bytes(b"RIFF0000WAVE")

    if make_documents_dir:
        docs_dir = documents_root / "artists" / artist / "albums" / genre / slug
        docs_dir.mkdir(parents=True)
        (docs_dir / "placeholder.pdf").write_bytes(b"%PDF-1.4")

    return {
        "title": title,
        "status": "In Progress",
        "genre": genre,
        "path": str(content_dir),
        "track_count": len(tracks),
        "tracks_completed": 0,
        "tracks": track_map,
    }


@pytest.fixture
def filesystem(tmp_path: Path):
    """Three mirrored roots used throughout: content, audio, documents."""
    content_root = tmp_path / "content"
    audio_root = tmp_path / "audio"
    documents_root = tmp_path / "documents"
    for root in (content_root, audio_root, documents_root):
        root.mkdir()
    return content_root, audio_root, documents_root


@pytest.fixture
def cache_with_album(filesystem):
    """Install a mock cache populated with a single album plus two tracks."""
    content_root, audio_root, documents_root = filesystem

    album_data = _make_album_on_disk(
        content_root, audio_root, documents_root,
        artist="test-artist", genre="electronic", slug="original-album",
        title="Original Album",
        tracks=[("01-first-track", "First Track"), ("02-second-track", "Second Track")],
    )

    state = {
        "version": 2,
        "config": {
            "content_root": str(content_root),
            "audio_root": str(audio_root),
            "documents_root": str(documents_root),
            "artist_name": "test-artist",
            "generation": {},
        },
        "albums": {"original-album": album_data},
        "session": {},
    }

    orig_cache = _shared_mod.cache
    orig_plugin_root = _shared_mod.PLUGIN_ROOT
    _shared_mod.cache = MockStateCache(state)
    _shared_mod.PLUGIN_ROOT = PROJECT_ROOT

    yield state, content_root, audio_root, documents_root

    _shared_mod.cache = orig_cache
    _shared_mod.PLUGIN_ROOT = orig_plugin_root


@pytest.fixture(autouse=True)
def _silence_state_write(monkeypatch):
    """Prevent write_state from hitting the real user cache during tests.

    rename.py imports ``write_state`` lazily at call time via
    ``from tools.state.indexer import write_state``, so patching the indexer's
    attribute is enough — the test doesn't care about on-disk cache.json.
    """
    import tools.state.indexer as indexer_mod
    monkeypatch.setattr(indexer_mod, "write_state", lambda _state: None)


# ===========================================================================
# rename_album — happy paths
# ===========================================================================


class TestRenameAlbumSuccess:
    def test_renames_content_directory(self, cache_with_album):
        _state, content_root, _audio, _docs = cache_with_album

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert result["success"] is True
        assert result["old_slug"] == "original-album"
        assert result["new_slug"] == "new-album"
        assert result["content_moved"] is True

        old_dir = content_root / "artists" / "test-artist" / "albums" / "electronic" / "original-album"
        new_dir = content_root / "artists" / "test-artist" / "albums" / "electronic" / "new-album"
        assert not old_dir.exists()
        assert new_dir.is_dir()
        assert (new_dir / "README.md").exists()
        assert (new_dir / "tracks" / "01-first-track.md").exists()

    def test_renames_audio_and_documents_directories(self, cache_with_album):
        _state, _content, audio_root, documents_root = cache_with_album

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert result["audio_moved"] is True
        assert result["documents_moved"] is True

        audio_base = audio_root / "artists" / "test-artist" / "albums" / "electronic"
        docs_base = documents_root / "artists" / "test-artist" / "albums" / "electronic"
        assert not (audio_base / "original-album").exists()
        assert (audio_base / "new-album" / "placeholder.wav").exists()
        assert not (docs_base / "original-album").exists()
        assert (docs_base / "new-album" / "placeholder.pdf").exists()

    def test_derives_title_from_new_slug_when_no_title_given(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album-name")
        ))

        assert result["title"] == "New Album Name"

    def test_uses_explicit_new_title_when_given(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-slug", new_title="Completely Different")
        ))

        assert result["title"] == "Completely Different"

    def test_updates_readme_h1_heading(self, cache_with_album):
        _state, content_root, _audio, _docs = cache_with_album

        _run(_rename_mod.rename_album("original-album", "new-album", new_title="Shiny New Album"))

        readme = (
            content_root / "artists" / "test-artist" / "albums" / "electronic"
            / "new-album" / "README.md"
        )
        assert "# Shiny New Album" in readme.read_text(encoding="utf-8")

    def test_state_cache_is_updated(self, cache_with_album):
        state, _content, _audio, _docs = cache_with_album

        _run(_rename_mod.rename_album("original-album", "new-album"))

        albums = state["albums"]
        assert "original-album" not in albums
        assert "new-album" in albums
        assert albums["new-album"]["title"] == "New Album"
        # Track paths rewritten to new album dir
        for track_data in albums["new-album"]["tracks"].values():
            assert "new-album" in track_data["path"]
            assert "original-album" not in track_data["path"]

    def test_tracks_updated_counter_reflects_moved_tracks(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert result["tracks_updated"] == 2


# ===========================================================================
# rename_album — error paths
# ===========================================================================


class TestRenameAlbumErrors:
    def test_missing_album_returns_error(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("does-not-exist", "new-album")
        ))

        assert "error" in result
        assert "not found" in result["error"].lower()
        assert "available_albums" in result

    def test_new_slug_collision_returns_error(self, cache_with_album):
        state, *_ = cache_with_album

        # Pre-seed a second album with the target slug
        second = _make_album_on_disk(
            content_root=Path(state["config"]["content_root"]),
            audio_root=Path(state["config"]["audio_root"]),
            documents_root=Path(state["config"]["documents_root"]),
            artist="test-artist",
            genre="electronic",
            slug="existing-album",
            title="Existing Album",
            tracks=[],
        )
        state["albums"]["existing-album"] = second

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "existing-album")
        ))

        assert "error" in result
        assert "already exists" in result["error"].lower()

    def test_same_slug_after_normalization_returns_error(self, cache_with_album):
        # "Original-Album" normalizes to "original-album" which equals the source
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "Original-Album")
        ))

        assert "error" in result
        assert "same" in result["error"].lower()

    def test_missing_content_directory_returns_error(self, cache_with_album):
        state, content_root, _audio, _docs = cache_with_album
        # Wipe the on-disk album dir but keep it in cache — simulates stale state
        import shutil as _shutil
        _shutil.rmtree(
            content_root / "artists" / "test-artist" / "albums" / "electronic"
            / "original-album"
        )

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert "error" in result
        assert "content directory not found" in result["error"].lower()

    def test_missing_artist_in_config_returns_error(self, cache_with_album):
        state, *_ = cache_with_album
        state["config"]["artist_name"] = ""

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert "error" in result
        assert "artist" in result["error"].lower()

    def test_empty_config_returns_error(self, cache_with_album):
        state, *_ = cache_with_album
        state["config"] = {}

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert "error" in result


class TestRenameAlbumPathTraversal:
    def test_rejects_slug_with_slash(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "evil/slug")
        ))
        assert "error" in result

    def test_rejects_slug_with_parent_traversal(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "..")
        ))
        assert "error" in result

    def test_rejects_backslash_separator(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "evil\\slug")
        ))
        assert "error" in result

    def test_rejects_null_byte(self, cache_with_album):
        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "evil\x00slug")
        ))
        assert "error" in result


class TestRenameAlbumMissingAuxDirs:
    """Audio / documents directories are optional — missing ones should not fail the rename."""

    def test_missing_audio_dir_still_succeeds(self, cache_with_album):
        _state, _content, audio_root, _docs = cache_with_album
        import shutil as _shutil
        _shutil.rmtree(audio_root / "artists")

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert result["success"] is True
        assert result["content_moved"] is True
        assert result["audio_moved"] is False

    def test_missing_documents_dir_still_succeeds(self, cache_with_album):
        _state, _content, _audio, documents_root = cache_with_album
        import shutil as _shutil
        _shutil.rmtree(documents_root / "artists")

        result = json.loads(_run(
            _rename_mod.rename_album("original-album", "new-album")
        ))

        assert result["success"] is True
        assert result["documents_moved"] is False


# ===========================================================================
# rename_track — happy paths
# ===========================================================================


class TestRenameTrackSuccess:
    def test_renames_track_file(self, cache_with_album):
        _state, content_root, _audio, _docs = cache_with_album

        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01-renamed-track"
        )))

        assert result["success"] is True
        assert result["new_slug"] == "01-renamed-track"

        tracks_dir = (
            content_root / "artists" / "test-artist" / "albums" / "electronic"
            / "original-album" / "tracks"
        )
        assert not (tracks_dir / "01-first-track.md").exists()
        assert (tracks_dir / "01-renamed-track.md").exists()

    def test_derives_title_from_new_slug(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01-brand-new-name"
        )))

        assert result["title"] == "Brand New Name"

    def test_explicit_title_overrides_derivation(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01-renamed", new_title="Custom Title"
        )))

        assert result["title"] == "Custom Title"

    def test_zero_padded_prefix_match_works(self, cache_with_album):
        """Passing just '01' should match '01-first-track' via prefix."""
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01", "01-matched-by-prefix"
        )))

        assert result["success"] is True
        assert result["old_slug"] == "01-first-track"
        assert result["new_slug"] == "01-matched-by-prefix"

    def test_title_row_in_metadata_table_is_updated(self, cache_with_album):
        _state, content_root, _audio, _docs = cache_with_album

        _run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01-new-name", new_title="Shiny New"
        ))

        new_path = (
            content_root / "artists" / "test-artist" / "albums" / "electronic"
            / "original-album" / "tracks" / "01-new-name.md"
        )
        text = new_path.read_text(encoding="utf-8")
        assert "**Title** | Shiny New" in text
        assert "# Shiny New" in text

    def test_state_cache_is_updated(self, cache_with_album):
        state, *_ = cache_with_album

        _run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01-renamed"
        ))

        tracks = state["albums"]["original-album"]["tracks"]
        assert "01-first-track" not in tracks
        assert "01-renamed" in tracks
        assert tracks["01-renamed"]["title"] == "Renamed"


# ===========================================================================
# rename_track — error paths
# ===========================================================================


class TestRenameTrackErrors:
    def test_missing_album_returns_error(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "no-such-album", "01-first-track", "01-renamed"
        )))

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_missing_track_returns_error(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "99-ghost-track", "99-renamed"
        )))

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_ambiguous_prefix_match_returns_error(self, cache_with_album):
        """If a prefix matches multiple tracks, rename fails cleanly."""
        state, *_ = cache_with_album
        # Add a track with a slug that also starts with "01"
        tracks = state["albums"]["original-album"]["tracks"]
        tracks["01-duplicate-prefix"] = copy.deepcopy(tracks["01-first-track"])
        tracks["01-duplicate-prefix"]["title"] = "Duplicate Prefix"

        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01", "01-renamed"
        )))

        assert "error" in result
        assert "multiple tracks match" in result["error"].lower()

    def test_new_slug_collision_returns_error(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "02-second-track"
        )))

        assert "error" in result
        assert "already exists" in result["error"].lower()

    def test_same_slug_after_normalization_returns_error(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01-First-Track"
        )))

        assert "error" in result
        assert "same" in result["error"].lower()

    def test_missing_file_on_disk_returns_error(self, cache_with_album):
        state, content_root, _audio, _docs = cache_with_album
        # Cache says the track exists but we delete the file underneath
        tracks_dir = (
            content_root / "artists" / "test-artist" / "albums" / "electronic"
            / "original-album" / "tracks"
        )
        (tracks_dir / "01-first-track.md").unlink()

        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01-renamed"
        )))

        assert "error" in result
        assert "not found on disk" in result["error"].lower()


class TestRenameTrackPathTraversal:
    def test_rejects_slug_with_slash(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01/evil"
        )))
        assert "error" in result

    def test_rejects_slug_with_parent_traversal(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", ".."
        )))
        assert "error" in result

    def test_rejects_backslash_separator(self, cache_with_album):
        result = json.loads(_run(_rename_mod.rename_track(
            "original-album", "01-first-track", "01\\evil"
        )))
        assert "error" in result
