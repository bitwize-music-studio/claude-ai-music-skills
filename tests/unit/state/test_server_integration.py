#!/usr/bin/env python3
"""
Integration tests for MCP server — real files, real indexer, real StateCache.

Unlike test_server.py (which mocks StateCache), these tests:
  1. Create real config.yaml + album/track markdown files on disk
  2. Run the real indexer (build_state) to produce state.json
  3. Load into a real StateCache
  4. Call MCP tool handlers end-to-end
  5. Verify results against the actual filesystem

This catches integration bugs that unit tests with mocks cannot:
  - Path resolution mismatches
  - Parser → indexer → cache schema drift
  - Staleness detection with real mtimes
  - Session persistence round-trips

Usage:
    python3 -m pytest tests/unit/state/test_server_integration.py -v
"""

import asyncio
import importlib
import importlib.util
import json
import os
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock MCP SDK if not installed (same strategy as test_server.py)
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

# Import modules
import tools.state.indexer as indexer

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"


def _import_server():
    spec = importlib.util.spec_from_file_location("state_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixture: create a fully populated content directory on disk
# ---------------------------------------------------------------------------

ALBUM_README = """\
---
title: "Integration Test Album"
release_date: ""
genres: ["electronic"]
tags: ["test"]
explicit: false
---

# Integration Test Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Artist** | test-artist |
| **Album** | Integration Test Album |
| **Genre** | Electronic |
| **Tracks** | 2 |
| **Status** | In Progress |
| **Explicit** | No |
| **Concept** | Testing the full pipeline |
"""

TRACK_01 = """\
# First Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 01 |
| **Title** | First Track |
| **Status** | Final |
| **Suno Link** | https://suno.com/song/abc123 |
| **Explicit** | No |
| **Sources Verified** | N/A |

## Suno Inputs

### Style Box
```
electronic, 120 BPM, energetic, synth-driven
```

### Lyrics Box
```
[Verse 1]
Testing the pipeline one two three
Making sure everything works for me

[Chorus]
Integration test all day
Running checks the proper way
```

## Streaming Lyrics

```
Testing the pipeline one two three
Making sure everything works for me

Integration test all day
Running checks the proper way
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| — | — | — |
"""

TRACK_02 = """\
# Second Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 02 |
| **Title** | Second Track |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | Yes |
| **Sources Verified** | ❌ Pending |

## Source

[Wikipedia Article](https://en.wikipedia.org/wiki/Test)

## Suno Inputs

### Style Box
```
electronic, 90 BPM, chill, ambient pads
```

### Lyrics Box
```
[Verse 1]
This is the second track for testing
Sources are pending and need verifying

[Chorus]
Verify the sources before we go
Make sure every link is right you know
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| — | — | — |
"""

SOURCES_MD = """\
# Integration Test Album - Sources

## Source Links
| Document | URL |
|----------|-----|
| [Wikipedia Test](https://en.wikipedia.org/wiki/Test) | Main reference |
| [Example Doc](https://example.com/doc) | Supporting source |
"""


@pytest.fixture
def content_dir(tmp_path):
    """Create a fully populated content directory with config, album, and tracks."""
    # Config
    config_dir = tmp_path / ".bitwize-music"
    config_dir.mkdir()
    cache_dir = config_dir / "cache"
    cache_dir.mkdir()

    content_root = tmp_path / "content"
    audio_root = tmp_path / "audio"

    config = {
        "artist": {"name": "test-artist"},
        "paths": {
            "content_root": str(content_root),
            "audio_root": str(audio_root),
        },
        "generation": {"service": "suno"},
    }
    config_path = config_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    # Album directory
    album_dir = content_root / "artists" / "test-artist" / "albums" / "electronic" / "integration-test-album"
    tracks_dir = album_dir / "tracks"
    tracks_dir.mkdir(parents=True)

    # Write files
    (album_dir / "README.md").write_text(ALBUM_README)
    (tracks_dir / "01-first-track.md").write_text(TRACK_01)
    (tracks_dir / "02-second-track.md").write_text(TRACK_02)
    (album_dir / "SOURCES.md").write_text(SOURCES_MD)

    # Audio directory (with artist folder)
    audio_album = audio_root / "test-artist" / "integration-test-album"
    audio_album.mkdir(parents=True)
    (audio_album / "01-first-track.wav").write_text("")
    (audio_album / "album.png").write_text("")

    return {
        "tmp_path": tmp_path,
        "config_dir": config_dir,
        "config_path": config_path,
        "cache_dir": cache_dir,
        "content_root": content_root,
        "audio_root": audio_root,
        "album_dir": album_dir,
        "tracks_dir": tracks_dir,
    }


@pytest.fixture
def integration_env(content_dir, monkeypatch):
    """Set up the full integration environment: real indexer + real StateCache."""
    cache_dir = content_dir["cache_dir"]
    config_path = content_dir["config_path"]

    # Monkeypatch indexer paths to our temp dir
    monkeypatch.setattr(indexer, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(indexer, "STATE_FILE", cache_dir / "state.json")
    monkeypatch.setattr(indexer, "LOCK_FILE", cache_dir / "state.lock")
    monkeypatch.setattr(indexer, "CONFIG_FILE", config_path)

    # Also patch the server's imported references to these constants
    monkeypatch.setattr(server, "STATE_FILE", cache_dir / "state.json")
    monkeypatch.setattr(server, "CONFIG_FILE", config_path)

    # Build state using the real indexer
    config = indexer.read_config()
    assert config is not None, "Config should be readable"

    state = indexer.build_state(config)
    indexer.write_state(state)

    # Verify state.json was written
    state_file = cache_dir / "state.json"
    assert state_file.exists(), "state.json should exist after build"

    # Create a real StateCache and wire it to the server
    real_cache = server.StateCache()
    monkeypatch.setattr(server, "cache", real_cache)

    # Point PLUGIN_ROOT to project root for reference file access
    monkeypatch.setattr(server, "PLUGIN_ROOT", PROJECT_ROOT)

    return {
        **content_dir,
        "cache": real_cache,
        "state": state,
        "state_file": state_file,
    }


# ===========================================================================
# Integration Tests
# ===========================================================================


@pytest.mark.integration
class TestStateRebuildPipeline:
    """Test the full markdown → indexer → state.json → StateCache pipeline."""

    def test_state_json_has_correct_structure(self, integration_env):
        """state.json built from real files has all expected fields."""
        state = json.loads(integration_env["state_file"].read_text())
        assert state["version"] == "1.0.0"
        assert "config" in state
        assert "albums" in state
        assert "session" in state
        assert "ideas" in state

    def test_album_discovered(self, integration_env):
        """Real album directory is discovered and indexed."""
        state = integration_env["cache"].get_state()
        assert "integration-test-album" in state["albums"]
        album = state["albums"]["integration-test-album"]
        assert album["title"] == "Integration Test Album"
        assert album["genre"] == "electronic"
        assert album["status"] == "In Progress"

    def test_tracks_discovered(self, integration_env):
        """Real track files are discovered with correct metadata."""
        state = integration_env["cache"].get_state()
        tracks = state["albums"]["integration-test-album"]["tracks"]
        assert "01-first-track" in tracks
        assert "02-second-track" in tracks
        assert tracks["01-first-track"]["status"] == "Final"
        assert tracks["01-first-track"]["has_suno_link"] is True
        assert tracks["02-second-track"]["status"] == "In Progress"
        assert tracks["02-second-track"]["explicit"] is True

    def test_config_paths_resolved(self, integration_env):
        """Config paths are correctly resolved and stored in state."""
        state = integration_env["cache"].get_state()
        config = state["config"]
        assert config["content_root"] == str(integration_env["content_root"])
        assert config["audio_root"] == str(integration_env["audio_root"])
        assert config["artist_name"] == "test-artist"

    def test_track_file_paths_are_absolute(self, integration_env):
        """Track paths in state point to real files on disk."""
        state = integration_env["cache"].get_state()
        tracks = state["albums"]["integration-test-album"]["tracks"]
        for slug, track in tracks.items():
            path = Path(track["path"])
            assert path.is_absolute(), f"Track path should be absolute: {path}"
            assert path.exists(), f"Track file should exist: {path}"


@pytest.mark.integration
class TestToolsWithRealState:
    """Test MCP tool handlers against real state from real files."""

    def test_find_album(self, integration_env):
        """find_album returns the real album."""
        result = json.loads(_run(server.find_album("integration-test-album")))
        assert result["found"] is True
        assert result["slug"] == "integration-test-album"
        assert result["album"]["title"] == "Integration Test Album"

    def test_find_album_fuzzy(self, integration_env):
        """find_album fuzzy match works against real state."""
        result = json.loads(_run(server.find_album("integration-test")))
        assert result["found"] is True
        assert result["slug"] == "integration-test-album"

    def test_list_albums(self, integration_env):
        """list_albums returns the real album."""
        result = json.loads(_run(server.list_albums()))
        albums = result["albums"]
        slugs = [a["slug"] for a in albums]
        assert "integration-test-album" in slugs

    def test_get_track(self, integration_env):
        """get_track returns real track data."""
        result = json.loads(_run(server.get_track(
            "integration-test-album", "01-first-track"
        )))
        assert result["found"] is True
        assert result["track"]["title"] == "First Track"
        assert result["track"]["status"] == "Final"

    def test_extract_section_lyrics(self, integration_env):
        """extract_section reads real lyrics from disk."""
        result = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "lyrics"
        )))
        assert result["found"] is True
        assert "[Verse 1]" in result["content"]
        assert "Testing the pipeline" in result["content"]

    def test_extract_section_style(self, integration_env):
        """extract_section reads real style prompt from disk."""
        result = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "style"
        )))
        assert result["found"] is True
        assert "electronic" in result["content"]
        assert "120 BPM" in result["content"]

    def test_get_album_full_with_sections(self, integration_env):
        """get_album_full returns album + sections from real files."""
        result = json.loads(_run(server.get_album_full(
            "integration-test-album", include_sections="lyrics,style"
        )))
        assert result["found"] is True
        tracks = result["tracks"]
        # Track 01 should have both sections
        t01 = tracks["01-first-track"]
        assert "sections" in t01
        assert "lyrics" in t01["sections"]
        assert "style" in t01["sections"]
        assert "Testing the pipeline" in t01["sections"]["lyrics"]

    def test_get_pending_verifications(self, integration_env):
        """Pending verifications detected from real track metadata."""
        result = json.loads(_run(server.get_pending_verifications()))
        # Track 02 has sources_verified: "❌ Pending" → parser normalizes to "Pending"
        pending = result.get("albums_with_pending", {})
        assert "integration-test-album" in pending, (
            f"integration-test-album should have pending tracks, got: {list(pending.keys())}"
        )
        track_slugs = [t["slug"] for t in pending["integration-test-album"]["tracks"]]
        assert "02-second-track" in track_slugs

    def test_format_for_clipboard(self, integration_env):
        """format_for_clipboard extracts real content from real files."""
        result = json.loads(_run(server.format_for_clipboard(
            "integration-test-album", "01", "lyrics"
        )))
        assert result["found"] is True
        assert "Testing the pipeline" in result["content"]
        assert result["track_slug"] == "01-first-track"

    def test_get_album_progress(self, integration_env):
        """Progress calculation against real track statuses."""
        result = json.loads(_run(server.get_album_progress("integration-test-album")))
        assert result["found"] is True
        assert result["track_count"] == 2
        assert result["tracks_completed"] == 1  # 01 is Final
        assert result["completion_percentage"] == 50

    def test_validate_album_structure(self, integration_env):
        """Structural validation against real directories."""
        result = json.loads(_run(server.validate_album_structure("integration-test-album")))
        assert result["found"] is True
        # Should pass: album dir, README, tracks/, track files, audio dir, art
        assert result["passed"] >= 5
        assert result["failed"] == 0

    def test_extract_links_from_sources(self, integration_env):
        """extract_links reads real SOURCES.md."""
        result = json.loads(_run(server.extract_links(
            "integration-test-album", "SOURCES.md"
        )))
        assert result["found"] is True
        assert result["count"] == 2
        urls = [link["url"] for link in result["links"]]
        assert "https://en.wikipedia.org/wiki/Test" in urls

    def test_extract_links_from_track(self, integration_env):
        """extract_links reads links from a real track file."""
        result = json.loads(_run(server.extract_links(
            "integration-test-album", "02-second-track"
        )))
        assert result["found"] is True
        assert result["count"] >= 1
        urls = [link["url"] for link in result["links"]]
        assert "https://en.wikipedia.org/wiki/Test" in urls

    def test_get_lyrics_stats(self, integration_env):
        """Lyrics stats calculated from real track content."""
        result = json.loads(_run(server.get_lyrics_stats(
            "integration-test-album", "01"
        )))
        assert result["found"] is True
        track = result["tracks"][0]
        assert track["word_count"] > 0
        assert track["section_count"] == 2  # [Verse 1] and [Chorus]
        assert result["genre"] == "electronic"

    def test_check_homographs_on_real_lyrics(self, integration_env):
        """Homograph check on real extracted lyrics."""
        # First extract lyrics, then scan them
        extract = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "lyrics"
        )))
        result = json.loads(_run(server.check_homographs(extract["content"])))
        # Our test lyrics don't contain homographs
        assert result["count"] == 0

    def test_run_pre_generation_gates(self, integration_env):
        """Pre-generation gates against real track content."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates(
                "integration-test-album", "01"
            )))
        assert result["found"] is True
        track = result["tracks"][0]
        # Track 01 should be READY (Final status, clean lyrics, no artist names)
        assert track["verdict"] == "READY"
        assert track["blocking"] == 0

    def test_search_finds_album(self, integration_env):
        """search finds the real album by title."""
        result = json.loads(_run(server.search("Integration Test")))
        album_matches = result.get("albums", [])
        assert len(album_matches) >= 1
        found_slugs = [a["slug"] for a in album_matches]
        assert "integration-test-album" in found_slugs


@pytest.mark.integration
class TestStalenessDetection:
    """Test that StateCache detects real file changes."""

    def test_cache_detects_state_file_change(self, integration_env):
        """Modifying state.json triggers reload on next get_state()."""
        cache = integration_env["cache"]

        # First load
        state1 = cache.get_state()
        assert "integration-test-album" in state1["albums"]

        # Wait for mtime resolution, then modify state.json directly
        time.sleep(0.05)
        state_file = integration_env["state_file"]
        raw = json.loads(state_file.read_text())
        raw["albums"]["integration-test-album"]["status"] = "Complete"
        state_file.write_text(json.dumps(raw, indent=2))

        # Next get_state should detect staleness and reload
        state2 = cache.get_state()
        assert state2["albums"]["integration-test-album"]["status"] == "Complete"

    def test_session_persists_to_disk(self, integration_env):
        """Session updates write through to state.json on disk."""
        cache = integration_env["cache"]

        # Update session
        cache.update_session(
            album="integration-test-album",
            track="01-first-track",
            phase="Writing",
        )

        # Read state.json directly from disk
        raw = json.loads(integration_env["state_file"].read_text())
        session = raw["session"]
        assert session["last_album"] == "integration-test-album"
        assert session["last_track"] == "01-first-track"
        assert session["last_phase"] == "Writing"
        assert session["updated_at"] is not None

    def test_session_survives_rebuild(self, integration_env, monkeypatch):
        """Rebuild preserves the existing session data."""
        cache = integration_env["cache"]

        # Set session
        cache.update_session(album="integration-test-album", phase="Mastering")

        # Force rebuild
        cache.rebuild()

        # Session should be preserved
        state = cache.get_state()
        assert state["session"]["last_album"] == "integration-test-album"
        assert state["session"]["last_phase"] == "Mastering"


@pytest.mark.integration
class TestUpdateTrackFieldEndToEnd:
    """Test update_track_field writes to real files and state stays consistent."""

    def test_update_status_persists(self, integration_env):
        """Changing a track status writes to the real markdown file."""
        result = json.loads(_run(server.update_track_field(
            "integration-test-album", "02-second-track", "status", "Generated"
        )))
        assert result["success"] is True

        # Verify the file on disk was actually modified
        track_path = integration_env["tracks_dir"] / "02-second-track.md"
        content = track_path.read_text()
        assert "Generated" in content

    def test_state_reflects_file_update(self, integration_env):
        """After field update, state cache returns the new value."""
        _run(server.update_track_field(
            "integration-test-album", "02-second-track", "status", "Final"
        ))

        # get_track should reflect the update
        result = json.loads(_run(server.get_track(
            "integration-test-album", "02-second-track"
        )))
        assert result["track"]["status"] == "Final"
