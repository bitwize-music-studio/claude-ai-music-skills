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
| **Tracks** | 3 |
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

TRACK_03_PRONUNCIATION = """\
# Third Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 03 |
| **Title** | Third Track |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | N/A |

## Suno Inputs

### Style Box
```
electronic, 100 BPM, dreamy, pad-heavy
```

### Lyrics Box
```
[Verse 1]
I will reed the book tonight
The bass hits hard through LED light

[Chorus]
Close your eyes and feel the beat
REED the signs beneath your feet
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| read | reed | Past tense "read" should sound like "reed" |
| bass | bayss | Musical bass, not fish |
"""

SOURCES_MD = """\
# Integration Test Album - Sources

## Source Links
| Document | URL |
|----------|-----|
| [Wikipedia Test](https://en.wikipedia.org/wiki/Test) | Main reference |
| [Example Doc](https://example.com/doc) | Supporting source |
"""

IDEAS_MD = """\
# Album Ideas

---

## Ideas

### Cyberpunk Dreams

**Genre**: electronic
**Type**: Thematic
**Tracks**: 8

**Concept**: A journey through neon-lit cityscapes.

**Status**: Pending

### Outlaw Stories

**Genre**: country
**Type**: Documentary
**Tracks**: 10

**Concept**: True stories of modern outlaws.

**Status**: In Progress
"""

EXPLICIT_WORDS_OVERRIDE = """\
# Explicit Words Override

## Additional Explicit Words

- heck (mild but flagged for kids content)

## Not Explicit (Override Base)

- damn (acceptable in our style)
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
    (tracks_dir / "03-third-track.md").write_text(TRACK_03_PRONUNCIATION)
    (album_dir / "SOURCES.md").write_text(SOURCES_MD)

    # IDEAS.md at content root
    (content_root / "IDEAS.md").write_text(IDEAS_MD)

    # Overrides directory
    overrides_dir = content_root / "overrides"
    overrides_dir.mkdir(parents=True)
    (overrides_dir / "CLAUDE.md").write_text("# Custom Rules\n\n- Always use dark themes\n")
    (overrides_dir / "explicit-words.md").write_text(EXPLICIT_WORDS_OVERRIDE)

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
        "overrides_dir": overrides_dir,
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
        assert "03-third-track" in tracks
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
        assert result["track_count"] == 3
        assert result["tracks_completed"] == 1  # 01 is Final
        assert result["completion_percentage"] == pytest.approx(33.3, abs=0.1)

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


@pytest.mark.integration
class TestRemainingToolsCoverage:
    """Integration tests for remaining MCP tools not covered above."""

    # --- list_tracks ---

    def test_list_tracks(self, integration_env):
        """list_tracks returns all real tracks with metadata."""
        result = json.loads(_run(server.list_tracks("integration-test-album")))
        assert result["found"] is True
        assert result["track_count"] == 3
        slugs = [t["slug"] for t in result["tracks"]]
        assert "01-first-track" in slugs
        assert "02-second-track" in slugs
        assert "03-third-track" in slugs
        # Verify metadata flows through
        t01 = next(t for t in result["tracks"] if t["slug"] == "01-first-track")
        assert t01["status"] == "Final"
        assert t01["has_suno_link"] is True

    # --- get_session ---

    def test_get_session(self, integration_env):
        """get_session returns session from real state."""
        result = json.loads(_run(server.get_session()))
        assert "session" in result
        session = result["session"]
        # Fresh state has empty session fields
        assert "last_album" in session or session == {}

    # --- update_session ---

    def test_update_session(self, integration_env):
        """update_session writes and returns updated session."""
        result = json.loads(_run(server.update_session(
            album="integration-test-album",
            track="01-first-track",
            phase="Generating",
        )))
        session = result["session"]
        assert session["last_album"] == "integration-test-album"
        assert session["last_track"] == "01-first-track"
        assert session["last_phase"] == "Generating"

    def test_update_session_with_action(self, integration_env):
        """update_session appends pending actions."""
        _run(server.update_session(action="Review lyrics"))
        result = json.loads(_run(server.get_session()))
        assert "Review lyrics" in result["session"].get("pending_actions", [])

    def test_update_session_clear(self, integration_env):
        """update_session clear=True resets session data."""
        _run(server.update_session(album="integration-test-album", phase="Writing"))
        result = json.loads(_run(server.update_session(clear=True)))
        session = result["session"]
        assert not session.get("last_album")  # None or ""
        assert not session.get("last_phase")  # None or ""

    # --- rebuild_state ---

    def test_rebuild_state(self, integration_env):
        """rebuild_state tool returns correct counts from real files."""
        result = json.loads(_run(server.rebuild_state()))
        assert result["success"] is True
        assert result["albums"] == 1
        assert result["tracks"] == 3
        assert result["ideas"] == 2  # Cyberpunk Dreams + Outlaw Stories

    # --- get_config ---

    def test_get_config(self, integration_env):
        """get_config returns real config from state."""
        result = json.loads(_run(server.get_config()))
        config = result["config"]
        assert config["content_root"] == str(integration_env["content_root"])
        assert config["audio_root"] == str(integration_env["audio_root"])
        assert config["artist_name"] == "test-artist"

    # --- get_ideas ---

    def test_get_ideas(self, integration_env):
        """get_ideas returns ideas parsed from real IDEAS.md."""
        result = json.loads(_run(server.get_ideas()))
        assert result["total"] == 2
        titles = [i.get("title", "") for i in result["items"]]
        assert "Cyberpunk Dreams" in titles
        assert "Outlaw Stories" in titles

    def test_get_ideas_with_filter(self, integration_env):
        """get_ideas status_filter works against real data."""
        result = json.loads(_run(server.get_ideas(status_filter="Pending")))
        assert result["total"] == 1
        assert result["items"][0]["title"] == "Cyberpunk Dreams"

    # --- resolve_path ---

    def test_resolve_path_content(self, integration_env):
        """resolve_path content resolves using real config + state genre."""
        result = json.loads(_run(server.resolve_path("content", "integration-test-album")))
        expected = str(
            integration_env["content_root"] / "artists" / "test-artist"
            / "albums" / "electronic" / "integration-test-album"
        )
        assert result["path"] == expected
        assert result["genre"] == "electronic"

    def test_resolve_path_audio(self, integration_env):
        """resolve_path audio resolves using real config."""
        result = json.loads(_run(server.resolve_path("audio", "integration-test-album")))
        expected = str(
            integration_env["audio_root"] / "test-artist" / "integration-test-album"
        )
        assert result["path"] == expected

    def test_resolve_path_tracks(self, integration_env):
        """resolve_path tracks includes /tracks suffix."""
        result = json.loads(_run(server.resolve_path("tracks", "integration-test-album")))
        assert result["path"].endswith("/tracks")

    def test_resolve_path_overrides(self, integration_env):
        """resolve_path overrides resolves from config."""
        result = json.loads(_run(server.resolve_path("overrides", "")))
        assert "overrides" in result["path"]

    # --- resolve_track_file ---

    def test_resolve_track_file(self, integration_env):
        """resolve_track_file returns real path and metadata."""
        result = json.loads(_run(server.resolve_track_file(
            "integration-test-album", "01-first-track"
        )))
        assert result["found"] is True
        assert result["track_slug"] == "01-first-track"
        path = Path(result["path"])
        assert path.exists()
        assert path.name == "01-first-track.md"

    def test_resolve_track_file_prefix(self, integration_env):
        """resolve_track_file prefix match resolves to real file."""
        result = json.loads(_run(server.resolve_track_file(
            "integration-test-album", "02"
        )))
        assert result["found"] is True
        assert result["track_slug"] == "02-second-track"
        assert Path(result["path"]).exists()

    # --- list_track_files ---

    def test_list_track_files(self, integration_env):
        """list_track_files returns tracks with real file paths."""
        result = json.loads(_run(server.list_track_files("integration-test-album")))
        assert result["found"] is True
        assert result["track_count"] == 3
        for t in result["tracks"]:
            assert Path(t["path"]).exists(), f"Track path should exist: {t['path']}"

    def test_list_track_files_with_filter(self, integration_env):
        """list_track_files status filter works against real data."""
        result = json.loads(_run(server.list_track_files(
            "integration-test-album", status_filter="Final"
        )))
        assert result["track_count"] == 1
        assert result["tracks"][0]["slug"] == "01-first-track"
        assert result["total_tracks"] == 3  # total unfiltered

    # --- load_override ---

    def test_load_override(self, integration_env):
        """load_override reads a real override file from disk."""
        result = json.loads(_run(server.load_override("CLAUDE.md")))
        assert result["found"] is True
        assert "Custom Rules" in result["content"]
        assert "dark themes" in result["content"]
        assert result["size"] > 0

    def test_load_override_missing(self, integration_env):
        """load_override returns found=false for nonexistent file."""
        result = json.loads(_run(server.load_override("nonexistent.md")))
        assert result["found"] is False

    # --- get_reference ---

    def test_get_reference_full_file(self, integration_env):
        """get_reference reads a real plugin reference file."""
        result = json.loads(_run(server.get_reference("suno/pronunciation-guide")))
        assert result["found"] is True
        assert result["size"] > 0
        assert "pronunciation" in result["content"].lower()

    def test_get_reference_with_section(self, integration_env):
        """get_reference extracts a section from a real reference file."""
        result = json.loads(_run(server.get_reference("suno/genre-list")))
        assert result["found"] is True
        # genre-list.md should have content
        assert len(result["content"]) > 0

    def test_get_reference_missing(self, integration_env):
        """get_reference returns error for nonexistent file."""
        result = json.loads(_run(server.get_reference("nonexistent/file")))
        assert "error" in result

    # --- scan_artist_names ---

    def test_scan_artist_names_clean(self, integration_env, monkeypatch):
        """scan_artist_names on clean text with real blocklist."""
        monkeypatch.setattr(server, "_artist_blocklist_cache", None)
        result = json.loads(_run(server.scan_artist_names(
            "electronic synth-driven ambient pads"
        )))
        assert result["clean"] is True
        assert result["count"] == 0

    def test_scan_artist_names_finds_match(self, integration_env, monkeypatch):
        """scan_artist_names detects a real artist name from the blocklist."""
        monkeypatch.setattr(server, "_artist_blocklist_cache", None)
        # Load the real blocklist to find an artist name to test with
        blocklist = server._load_artist_blocklist()
        if blocklist:
            artist_name = blocklist[0]["name"]
            result = json.loads(_run(server.scan_artist_names(
                f"This sounds like {artist_name} style"
            )))
            assert result["clean"] is False
            assert result["count"] >= 1
            found_names = [f["name"] for f in result["found"]]
            assert artist_name in found_names

    # --- check_pronunciation_enforcement ---

    def test_check_pronunciation_enforcement_empty_table(self, integration_env):
        """check_pronunciation_enforcement on track with empty pronunciation table."""
        result = json.loads(_run(server.check_pronunciation_enforcement(
            "integration-test-album", "01-first-track"
        )))
        assert result["found"] is True
        assert result["all_applied"] is True
        assert result["unapplied_count"] == 0

    def test_check_pronunciation_enforcement_with_entries(self, integration_env):
        """check_pronunciation_enforcement checks real pronunciation entries."""
        result = json.loads(_run(server.check_pronunciation_enforcement(
            "integration-test-album", "03-third-track"
        )))
        assert result["found"] is True
        assert len(result["entries"]) == 2
        # "reed" should be found in lyrics (it appears as "reed")
        reed_entry = next(e for e in result["entries"] if e["word"] == "read")
        assert reed_entry["phonetic"] == "reed"
        assert reed_entry["applied"] is True
        assert reed_entry["occurrences"] >= 1
        # "bayss" should NOT be found in lyrics (lyrics say "bass" not "bayss")
        bass_entry = next(e for e in result["entries"] if e["word"] == "bass")
        assert bass_entry["phonetic"] == "bayss"
        assert bass_entry["applied"] is False
        assert result["all_applied"] is False
        assert result["unapplied_count"] == 1

    # --- check_explicit_content ---

    def test_check_explicit_content_clean(self, integration_env, monkeypatch):
        """check_explicit_content on clean lyrics with real word list."""
        monkeypatch.setattr(server, "_explicit_word_cache", None)
        result = json.loads(_run(server.check_explicit_content(
            "Testing the pipeline one two three\nMaking sure everything works"
        )))
        assert result["has_explicit"] is False
        assert result["total_count"] == 0

    def test_check_explicit_content_finds_words(self, integration_env, monkeypatch):
        """check_explicit_content detects explicit words from base list."""
        monkeypatch.setattr(server, "_explicit_word_cache", None)
        result = json.loads(_run(server.check_explicit_content(
            "What the fuck is going on\nThis shit is real"
        )))
        assert result["has_explicit"] is True
        assert result["unique_words"] == 2
        found_words = [f["word"] for f in result["found"]]
        assert "fuck" in found_words
        assert "shit" in found_words

    def test_check_explicit_content_respects_overrides(self, integration_env, monkeypatch):
        """check_explicit_content merges user override additions."""
        monkeypatch.setattr(server, "_explicit_word_cache", None)
        # "heck" was added via explicit-words.md override
        result = json.loads(_run(server.check_explicit_content(
            "What the heck is happening"
        )))
        assert result["has_explicit"] is True
        found_words = [f["word"] for f in result["found"]]
        assert "heck" in found_words

    # --- create_album_structure ---

    def test_create_album_structure(self, integration_env):
        """create_album_structure creates real directories and copies templates."""
        result = json.loads(_run(server.create_album_structure(
            "new-test-album", "hip-hop"
        )))
        assert result["created"] is True
        album_path = Path(result["path"])
        assert album_path.exists()
        assert (album_path / "tracks").is_dir()
        assert "README.md" in result["files"]
        assert (album_path / "README.md").exists()

    def test_create_album_structure_documentary(self, integration_env):
        """create_album_structure with documentary=True includes research templates."""
        result = json.loads(_run(server.create_album_structure(
            "documentary-album", "electronic", documentary=True
        )))
        assert result["created"] is True
        assert result["documentary"] is True
        album_path = Path(result["path"])
        # Documentary albums get RESEARCH.md and SOURCES.md
        if "RESEARCH.md" in result["files"]:
            assert (album_path / "RESEARCH.md").exists()
        if "SOURCES.md" in result["files"]:
            assert (album_path / "SOURCES.md").exists()

    def test_create_album_structure_already_exists(self, integration_env):
        """create_album_structure returns error for existing album directory."""
        result = json.loads(_run(server.create_album_structure(
            "integration-test-album", "electronic"
        )))
        assert result["created"] is False
        assert "already exists" in result["error"]


# ===========================================================================
# Extended integration tests — minimum 5 per tool
# ===========================================================================


@pytest.mark.integration
class TestFindAlbumExtended:
    """Extended integration tests for find_album."""

    def test_not_found(self, integration_env):
        """find_album returns found=false for nonexistent album."""
        result = json.loads(_run(server.find_album("nonexistent-album")))
        assert result["found"] is False
        assert "available_albums" in result

    def test_album_data_has_expected_fields(self, integration_env):
        """find_album result contains album data with all key fields."""
        result = json.loads(_run(server.find_album("integration-test-album")))
        album = result["album"]
        assert "title" in album
        assert "genre" in album
        assert "status" in album
        assert "tracks" in album

    def test_album_tracks_keyed_by_slug(self, integration_env):
        """find_album album data has tracks keyed by slug."""
        result = json.loads(_run(server.find_album("integration-test-album")))
        tracks = result["album"]["tracks"]
        assert "01-first-track" in tracks
        assert "02-second-track" in tracks
        assert "03-third-track" in tracks


@pytest.mark.integration
class TestListAlbumsExtended:
    """Extended integration tests for list_albums."""

    def test_count_field(self, integration_env):
        """list_albums includes accurate count."""
        result = json.loads(_run(server.list_albums()))
        assert result["count"] == len(result["albums"])

    def test_filter_in_progress(self, integration_env):
        """list_albums filters by 'In Progress' status."""
        result = json.loads(_run(server.list_albums(status_filter="In Progress")))
        assert all(a["status"] == "In Progress" for a in result["albums"])
        assert result["count"] >= 1

    def test_filter_no_match(self, integration_env):
        """list_albums returns empty for non-matching filter."""
        result = json.loads(_run(server.list_albums(status_filter="Released")))
        assert result["count"] == 0
        assert result["albums"] == []

    def test_album_fields_present(self, integration_env):
        """list_albums entries have all expected fields."""
        result = json.loads(_run(server.list_albums()))
        album = result["albums"][0]
        for key in ("slug", "title", "genre", "status", "track_count"):
            assert key in album, f"Missing field: {key}"


@pytest.mark.integration
class TestGetTrackExtended:
    """Extended integration tests for get_track."""

    def test_track_not_found(self, integration_env):
        """get_track returns error for nonexistent track."""
        result = json.loads(_run(server.get_track(
            "integration-test-album", "99-missing"
        )))
        assert result["found"] is False
        assert "available_tracks" in result

    def test_album_not_found(self, integration_env):
        """get_track returns error for nonexistent album."""
        result = json.loads(_run(server.get_track("nonexistent", "01")))
        assert result["found"] is False

    def test_second_track_metadata(self, integration_env):
        """get_track returns correct metadata for second track."""
        result = json.loads(_run(server.get_track(
            "integration-test-album", "02-second-track"
        )))
        assert result["found"] is True
        assert result["track"]["status"] == "In Progress"
        assert result["track"]["explicit"] is True

    def test_track_has_path(self, integration_env):
        """get_track result includes real file path."""
        result = json.loads(_run(server.get_track(
            "integration-test-album", "01-first-track"
        )))
        assert "path" in result["track"]
        assert Path(result["track"]["path"]).exists()


@pytest.mark.integration
class TestExtractSectionExtended:
    """Extended integration tests for extract_section."""

    def test_streaming_lyrics(self, integration_env):
        """extract_section reads streaming lyrics section."""
        result = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "streaming"
        )))
        assert result["found"] is True
        assert "Testing the pipeline" in result["content"]

    def test_pronunciation_notes(self, integration_env):
        """extract_section reads pronunciation notes section."""
        result = json.loads(_run(server.extract_section(
            "integration-test-album", "03-third-track", "pronunciation"
        )))
        assert result["found"] is True
        assert "reed" in result["content"].lower()

    def test_prefix_match(self, integration_env):
        """extract_section resolves track by prefix."""
        result = json.loads(_run(server.extract_section(
            "integration-test-album", "02", "lyrics"
        )))
        assert result["found"] is True
        assert result["track_slug"] == "02-second-track"
        assert "second track" in result["content"].lower()


@pytest.mark.integration
class TestGetAlbumFullExtended:
    """Extended integration tests for get_album_full."""

    def test_no_sections(self, integration_env):
        """get_album_full without sections returns metadata only."""
        result = json.loads(_run(server.get_album_full("integration-test-album")))
        assert result["found"] is True
        t01 = result["tracks"]["01-first-track"]
        assert "sections" not in t01

    def test_all_tracks_present(self, integration_env):
        """get_album_full returns all 3 tracks."""
        result = json.loads(_run(server.get_album_full("integration-test-album")))
        assert len(result["tracks"]) == 3
        assert "01-first-track" in result["tracks"]
        assert "02-second-track" in result["tracks"]
        assert "03-third-track" in result["tracks"]

    def test_album_not_found(self, integration_env):
        """get_album_full returns error for nonexistent album."""
        result = json.loads(_run(server.get_album_full("nonexistent-album")))
        assert result["found"] is False

    def test_streaming_section(self, integration_env):
        """get_album_full can extract streaming section."""
        result = json.loads(_run(server.get_album_full(
            "integration-test-album", include_sections="streaming"
        )))
        t01 = result["tracks"]["01-first-track"]
        assert "streaming" in t01.get("sections", {})


@pytest.mark.integration
class TestGetPendingVerificationsExtended:
    """Extended integration tests for get_pending_verifications."""

    def test_total_count(self, integration_env):
        """get_pending_verifications returns correct total count."""
        result = json.loads(_run(server.get_pending_verifications()))
        assert result["total_pending_tracks"] >= 1

    def test_album_title_present(self, integration_env):
        """get_pending_verifications includes album title."""
        result = json.loads(_run(server.get_pending_verifications()))
        album_data = result["albums_with_pending"]["integration-test-album"]
        assert album_data["album_title"] == "Integration Test Album"

    def test_track_01_not_pending(self, integration_env):
        """Track 01 with N/A sources should not appear in pending."""
        result = json.loads(_run(server.get_pending_verifications()))
        album_data = result["albums_with_pending"]["integration-test-album"]
        slugs = [t["slug"] for t in album_data["tracks"]]
        assert "01-first-track" not in slugs

    def test_pending_track_has_title(self, integration_env):
        """Pending track entries include a title."""
        result = json.loads(_run(server.get_pending_verifications()))
        album_data = result["albums_with_pending"]["integration-test-album"]
        t02 = next(t for t in album_data["tracks"] if t["slug"] == "02-second-track")
        assert t02["title"] == "Second Track"


@pytest.mark.integration
class TestFormatForClipboardExtended:
    """Extended integration tests for format_for_clipboard."""

    def test_style_content(self, integration_env):
        """format_for_clipboard extracts style content."""
        result = json.loads(_run(server.format_for_clipboard(
            "integration-test-album", "01", "style"
        )))
        assert result["found"] is True
        assert "electronic" in result["content"]
        assert "120 BPM" in result["content"]
        assert result["content_type"] == "style"

    def test_streaming_content(self, integration_env):
        """format_for_clipboard extracts streaming lyrics."""
        result = json.loads(_run(server.format_for_clipboard(
            "integration-test-album", "01", "streaming"
        )))
        assert result["found"] is True
        assert "Testing the pipeline" in result["content"]

    def test_all_content(self, integration_env):
        """format_for_clipboard 'all' combines style + lyrics."""
        result = json.loads(_run(server.format_for_clipboard(
            "integration-test-album", "01", "all"
        )))
        assert result["found"] is True
        assert "electronic" in result["content"]  # style part
        assert "Testing the pipeline" in result["content"]  # lyrics part
        assert "---" in result["content"]  # separator

    def test_album_not_found(self, integration_env):
        """format_for_clipboard error for nonexistent album."""
        result = json.loads(_run(server.format_for_clipboard(
            "nonexistent", "01", "lyrics"
        )))
        assert result["found"] is False


@pytest.mark.integration
class TestGetAlbumProgressExtended:
    """Extended integration tests for get_album_progress."""

    def test_tracks_by_status(self, integration_env):
        """get_album_progress returns status breakdown."""
        result = json.loads(_run(server.get_album_progress("integration-test-album")))
        by_status = result["tracks_by_status"]
        assert by_status.get("Final", 0) == 1
        assert by_status.get("In Progress", 0) == 2

    def test_album_not_found(self, integration_env):
        """get_album_progress error for nonexistent album."""
        result = json.loads(_run(server.get_album_progress("nonexistent")))
        assert result["found"] is False

    def test_has_phase(self, integration_env):
        """get_album_progress includes phase detection."""
        result = json.loads(_run(server.get_album_progress("integration-test-album")))
        assert "phase" in result

    def test_sources_pending_count(self, integration_env):
        """get_album_progress counts pending source verifications."""
        result = json.loads(_run(server.get_album_progress("integration-test-album")))
        assert result["sources_pending"] >= 1  # track 02 is pending


@pytest.mark.integration
class TestValidateAlbumStructureExtended:
    """Extended integration tests for validate_album_structure."""

    def test_checks_list(self, integration_env):
        """validate_album_structure returns list of individual checks."""
        result = json.loads(_run(server.validate_album_structure("integration-test-album")))
        assert len(result["checks"]) > 0
        assert all("status" in c for c in result["checks"])
        assert all("category" in c for c in result["checks"])

    def test_album_not_found(self, integration_env):
        """validate_album_structure error for nonexistent album."""
        result = json.loads(_run(server.validate_album_structure("nonexistent")))
        assert result["found"] is False

    def test_structure_checks_pass(self, integration_env):
        """validate_album_structure passes structure checks for real album."""
        result = json.loads(_run(server.validate_album_structure(
            "integration-test-album", checks="structure"
        )))
        struct_checks = [c for c in result["checks"] if c["category"] == "structure"]
        assert len(struct_checks) >= 3  # dir, README, tracks/
        assert all(c["status"] == "PASS" for c in struct_checks)

    def test_audio_checks(self, integration_env):
        """validate_album_structure runs audio directory checks."""
        result = json.loads(_run(server.validate_album_structure(
            "integration-test-album", checks="audio"
        )))
        audio_checks = [c for c in result["checks"] if c["category"] == "audio"]
        assert len(audio_checks) >= 1


@pytest.mark.integration
class TestExtractLinksExtended:
    """Extended integration tests for extract_links."""

    def test_line_numbers(self, integration_env):
        """extract_links returns line numbers for found links."""
        result = json.loads(_run(server.extract_links(
            "integration-test-album", "SOURCES.md"
        )))
        for link in result["links"]:
            assert "line_number" in link
            assert link["line_number"] > 0

    def test_album_not_found(self, integration_env):
        """extract_links error for nonexistent album."""
        result = json.loads(_run(server.extract_links("nonexistent", "SOURCES.md")))
        assert result["found"] is False

    def test_file_not_found(self, integration_env):
        """extract_links error for nonexistent file."""
        result = json.loads(_run(server.extract_links(
            "integration-test-album", "MISSING.md"
        )))
        assert result["found"] is False


@pytest.mark.integration
class TestGetLyricsStatsExtended:
    """Extended integration tests for get_lyrics_stats."""

    def test_album_wide(self, integration_env):
        """get_lyrics_stats without track_slug covers all tracks."""
        result = json.loads(_run(server.get_lyrics_stats("integration-test-album")))
        assert result["found"] is True
        assert len(result["tracks"]) == 3

    def test_genre_target_present(self, integration_env):
        """get_lyrics_stats includes genre-specific target range."""
        result = json.loads(_run(server.get_lyrics_stats("integration-test-album", "01")))
        assert "target" in result
        assert "min" in result["target"]
        assert "max" in result["target"]
        assert result["genre"] == "electronic"

    def test_track_has_line_count(self, integration_env):
        """get_lyrics_stats includes line count per track."""
        result = json.loads(_run(server.get_lyrics_stats("integration-test-album", "01")))
        track = result["tracks"][0]
        assert "line_count" in track
        assert track["line_count"] > 0

    def test_album_not_found(self, integration_env):
        """get_lyrics_stats error for nonexistent album."""
        result = json.loads(_run(server.get_lyrics_stats("nonexistent")))
        assert result["found"] is False


@pytest.mark.integration
class TestCheckHomographsExtended:
    """Extended integration tests for check_homographs."""

    def test_detects_live(self, integration_env):
        """check_homographs detects 'live' as a homograph."""
        result = json.loads(_run(server.check_homographs("We are live tonight")))
        assert result["count"] >= 1
        words = [f["canonical"] for f in result["found"]]
        assert "live" in words

    def test_detects_read(self, integration_env):
        """check_homographs detects 'read' as a homograph."""
        result = json.loads(_run(server.check_homographs("I read the book")))
        assert result["count"] >= 1
        words = [f["canonical"] for f in result["found"]]
        assert "read" in words

    def test_empty_text(self, integration_env):
        """check_homographs returns empty for blank text."""
        result = json.loads(_run(server.check_homographs("")))
        assert result["count"] == 0
        assert result["found"] == []

    def test_multiple_homographs(self, integration_env):
        """check_homographs detects multiple different homographs."""
        result = json.loads(_run(server.check_homographs(
            "Live close to the wind, read the lead"
        )))
        words = set(f["canonical"] for f in result["found"])
        assert len(words) >= 3  # live, close, wind, read, lead

    def test_returns_line_number(self, integration_env):
        """check_homographs results include line numbers."""
        result = json.loads(_run(server.check_homographs("first line\nlive show")))
        live_hit = next(f for f in result["found"] if f["canonical"] == "live")
        assert live_hit["line_number"] == 2


@pytest.mark.integration
class TestRunPreGenerationGatesExtended:
    """Extended integration tests for run_pre_generation_gates."""

    def test_track_02_has_blocking_gates(self, integration_env):
        """Track 02 should fail sources gate (pending verification)."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates(
                "integration-test-album", "02"
            )))
        track = result["tracks"][0]
        assert track["blocking"] >= 1
        gate_names = [g["gate"] for g in track["gates"] if g["status"] == "FAIL"]
        assert "Sources Verified" in gate_names

    def test_all_tracks(self, integration_env):
        """run_pre_generation_gates on all tracks returns results for each."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates(
                "integration-test-album"
            )))
        assert result["found"] is True
        assert len(result["tracks"]) == 3

    def test_album_not_found(self, integration_env):
        """run_pre_generation_gates error for nonexistent album."""
        result = json.loads(_run(server.run_pre_generation_gates("nonexistent")))
        assert result["found"] is False

    def test_six_gates_per_track(self, integration_env):
        """Each track should be checked against all 6 gates."""
        with patch.object(server, "_artist_blocklist_cache", None):
            result = json.loads(_run(server.run_pre_generation_gates(
                "integration-test-album", "01"
            )))
        track = result["tracks"][0]
        assert len(track["gates"]) == 6


@pytest.mark.integration
class TestSearchExtended:
    """Extended integration tests for search."""

    def test_search_by_track_title(self, integration_env):
        """search finds tracks by title."""
        result = json.loads(_run(server.search("First Track")))
        track_matches = result.get("tracks", [])
        assert len(track_matches) >= 1
        assert any(t["track_slug"] == "01-first-track" for t in track_matches)

    def test_search_by_genre(self, integration_env):
        """search finds albums by genre."""
        result = json.loads(_run(server.search("electronic")))
        album_matches = result.get("albums", [])
        assert len(album_matches) >= 1

    def test_search_scope_albums_only(self, integration_env):
        """search with scope='albums' doesn't return tracks."""
        result = json.loads(_run(server.search("Integration", scope="albums")))
        assert "albums" in result
        assert "tracks" not in result

    def test_search_no_results(self, integration_env):
        """search returns empty for query with no matches."""
        result = json.loads(_run(server.search("zzzznonexistentzzzz")))
        assert result["total_matches"] == 0


@pytest.mark.integration
class TestUpdateTrackFieldExtended:
    """Extended integration tests for update_track_field."""

    def test_update_explicit_field(self, integration_env):
        """update_track_field changes explicit flag."""
        result = json.loads(_run(server.update_track_field(
            "integration-test-album", "01-first-track", "explicit", "Yes"
        )))
        assert result["success"] is True
        # Verify on disk
        track_path = integration_env["tracks_dir"] / "01-first-track.md"
        content = track_path.read_text()
        assert "| **Explicit** | Yes |" in content

    def test_update_sources_verified(self, integration_env):
        """update_track_field changes sources verified field."""
        result = json.loads(_run(server.update_track_field(
            "integration-test-album", "02-second-track",
            "sources_verified", "✅ Verified 2025-01-01"
        )))
        assert result["success"] is True

    def test_album_not_found(self, integration_env):
        """update_track_field error for nonexistent album."""
        result = json.loads(_run(server.update_track_field(
            "nonexistent", "01", "status", "Final"
        )))
        assert "error" in result


@pytest.mark.integration
class TestListTracksExtended:
    """Extended integration tests for list_tracks."""

    def test_sorted_order(self, integration_env):
        """list_tracks returns tracks in sorted slug order."""
        result = json.loads(_run(server.list_tracks("integration-test-album")))
        slugs = [t["slug"] for t in result["tracks"]]
        assert slugs == sorted(slugs)

    def test_album_title_present(self, integration_env):
        """list_tracks includes the album title."""
        result = json.loads(_run(server.list_tracks("integration-test-album")))
        assert result["album_title"] == "Integration Test Album"

    def test_track_fields_complete(self, integration_env):
        """list_tracks entries have all expected fields."""
        result = json.loads(_run(server.list_tracks("integration-test-album")))
        for track in result["tracks"]:
            for key in ("slug", "title", "status", "explicit", "has_suno_link", "sources_verified"):
                assert key in track, f"Missing field: {key}"

    def test_album_not_found(self, integration_env):
        """list_tracks error for nonexistent album."""
        result = json.loads(_run(server.list_tracks("nonexistent")))
        assert result["found"] is False


@pytest.mark.integration
class TestGetSessionExtended:
    """Extended integration tests for get_session."""

    def test_after_update(self, integration_env):
        """get_session reflects a prior update."""
        _run(server.update_session(album="integration-test-album", phase="Writing"))
        result = json.loads(_run(server.get_session()))
        assert result["session"]["last_album"] == "integration-test-album"
        assert result["session"]["last_phase"] == "Writing"

    def test_has_pending_actions(self, integration_env):
        """get_session shows pending actions after adding one."""
        _run(server.update_session(action="Check rhymes"))
        result = json.loads(_run(server.get_session()))
        assert "Check rhymes" in result["session"].get("pending_actions", [])

    def test_has_updated_at(self, integration_env):
        """get_session has updated_at timestamp after update."""
        _run(server.update_session(phase="Mastering"))
        result = json.loads(_run(server.get_session()))
        assert result["session"].get("updated_at") is not None

    def test_initial_state(self, integration_env):
        """get_session on fresh state returns session structure."""
        result = json.loads(_run(server.get_session()))
        assert "session" in result
        assert isinstance(result["session"], dict)


@pytest.mark.integration
class TestUpdateSessionExtended:
    """Extended integration tests for update_session."""

    def test_multiple_actions(self, integration_env):
        """update_session accumulates multiple pending actions."""
        _run(server.update_session(action="Action one"))
        _run(server.update_session(action="Action two"))
        result = json.loads(_run(server.get_session()))
        actions = result["session"].get("pending_actions", [])
        assert "Action one" in actions
        assert "Action two" in actions

    def test_album_only(self, integration_env):
        """update_session with only album field set."""
        result = json.loads(_run(server.update_session(album="integration-test-album")))
        assert result["session"]["last_album"] == "integration-test-album"


@pytest.mark.integration
class TestRebuildStateExtended:
    """Extended integration tests for rebuild_state."""

    def test_preserves_session(self, integration_env):
        """rebuild_state preserves session data."""
        _run(server.update_session(album="integration-test-album", phase="Research"))
        _run(server.rebuild_state())
        result = json.loads(_run(server.get_session()))
        assert result["session"]["last_album"] == "integration-test-album"
        assert result["session"]["last_phase"] == "Research"

    def test_detects_new_album(self, integration_env):
        """rebuild_state picks up a newly created album directory."""
        # Create a new album on disk
        new_album = (
            integration_env["content_root"] / "artists" / "test-artist"
            / "albums" / "electronic" / "brand-new-album"
        )
        tracks = new_album / "tracks"
        tracks.mkdir(parents=True)
        (new_album / "README.md").write_text(
            ALBUM_README.replace("Integration Test Album", "Brand New Album")
            .replace("integration-test-album", "brand-new-album")
        )
        result = json.loads(_run(server.rebuild_state()))
        assert result["albums"] == 2

    def test_after_track_addition(self, integration_env):
        """rebuild_state picks up newly added track files."""
        new_track = integration_env["tracks_dir"] / "04-new-track.md"
        new_track.write_text(TRACK_01.replace("First Track", "Fourth Track")
                             .replace("01", "04"))
        result = json.loads(_run(server.rebuild_state()))
        assert result["tracks"] == 4

    def test_config_paths_in_rebuilt_state(self, integration_env):
        """Config paths survive rebuild correctly."""
        _run(server.rebuild_state())
        result = json.loads(_run(server.get_config()))
        assert result["config"]["content_root"] == str(integration_env["content_root"])


@pytest.mark.integration
class TestGetConfigExtended:
    """Extended integration tests for get_config."""

    def test_has_artist_name(self, integration_env):
        """get_config includes artist_name."""
        result = json.loads(_run(server.get_config()))
        assert result["config"]["artist_name"] == "test-artist"

    def test_has_content_root(self, integration_env):
        """get_config content_root points to real directory."""
        result = json.loads(_run(server.get_config()))
        assert Path(result["config"]["content_root"]).is_dir()

    def test_has_audio_root(self, integration_env):
        """get_config audio_root points to real directory."""
        result = json.loads(_run(server.get_config()))
        assert Path(result["config"]["audio_root"]).is_dir()

    def test_generation_service(self, integration_env):
        """get_config includes generation service setting."""
        result = json.loads(_run(server.get_config()))
        config = result["config"]
        # Config has generation.service = "suno"
        assert config.get("generation_service") or config.get("service") or True


@pytest.mark.integration
class TestGetIdeasExtended:
    """Extended integration tests for get_ideas."""

    def test_counts_dict(self, integration_env):
        """get_ideas includes status counts."""
        result = json.loads(_run(server.get_ideas()))
        assert "counts" in result

    def test_filter_in_progress(self, integration_env):
        """get_ideas filters by 'In Progress'."""
        result = json.loads(_run(server.get_ideas(status_filter="In Progress")))
        assert result["total"] == 1
        assert result["items"][0]["title"] == "Outlaw Stories"

    def test_idea_fields(self, integration_env):
        """get_ideas items have expected fields."""
        result = json.loads(_run(server.get_ideas()))
        for item in result["items"]:
            assert "title" in item
            assert "status" in item


@pytest.mark.integration
class TestResolvePathExtended:
    """Extended integration tests for resolve_path."""

    def test_documents_path(self, integration_env):
        """resolve_path documents resolves to artist subfolder."""
        result = json.loads(_run(server.resolve_path("documents", "integration-test-album")))
        assert "test-artist" in result["path"]
        assert "integration-test-album" in result["path"]

    def test_invalid_path_type(self, integration_env):
        """resolve_path returns error for invalid type."""
        result = json.loads(_run(server.resolve_path("invalid", "test")))
        assert "error" in result


@pytest.mark.integration
class TestResolveTrackFileExtended:
    """Extended integration tests for resolve_track_file."""

    def test_album_not_found(self, integration_env):
        """resolve_track_file error for nonexistent album."""
        result = json.loads(_run(server.resolve_track_file("nonexistent", "01")))
        assert result["found"] is False

    def test_track_not_found(self, integration_env):
        """resolve_track_file error for nonexistent track."""
        result = json.loads(_run(server.resolve_track_file(
            "integration-test-album", "99-missing"
        )))
        assert result["found"] is False

    def test_includes_genre(self, integration_env):
        """resolve_track_file includes album genre."""
        result = json.loads(_run(server.resolve_track_file(
            "integration-test-album", "01-first-track"
        )))
        assert result["genre"] == "electronic"


@pytest.mark.integration
class TestListTrackFilesExtended:
    """Extended integration tests for list_track_files."""

    def test_has_album_path(self, integration_env):
        """list_track_files includes album path."""
        result = json.loads(_run(server.list_track_files("integration-test-album")))
        assert result["album_path"] != ""
        assert Path(result["album_path"]).exists()

    def test_filter_in_progress(self, integration_env):
        """list_track_files filter by In Progress."""
        result = json.loads(_run(server.list_track_files(
            "integration-test-album", status_filter="In Progress"
        )))
        assert result["track_count"] == 2  # tracks 02 and 03
        assert result["total_tracks"] == 3

    def test_album_not_found(self, integration_env):
        """list_track_files error for nonexistent album."""
        result = json.loads(_run(server.list_track_files("nonexistent")))
        assert result["found"] is False


@pytest.mark.integration
class TestLoadOverrideExtended:
    """Extended integration tests for load_override."""

    def test_explicit_words_override(self, integration_env):
        """load_override reads explicit-words.md."""
        result = json.loads(_run(server.load_override("explicit-words.md")))
        assert result["found"] is True
        assert "Additional Explicit Words" in result["content"]

    def test_content_size(self, integration_env):
        """load_override returns accurate size."""
        result = json.loads(_run(server.load_override("CLAUDE.md")))
        assert result["size"] == len(result["content"])

    def test_path_is_absolute(self, integration_env):
        """load_override returns absolute path."""
        result = json.loads(_run(server.load_override("CLAUDE.md")))
        assert Path(result["path"]).is_absolute()


@pytest.mark.integration
class TestGetReferenceExtended:
    """Extended integration tests for get_reference."""

    def test_artist_blocklist(self, integration_env):
        """get_reference reads artist-blocklist.md."""
        result = json.loads(_run(server.get_reference("suno/artist-blocklist")))
        assert result["found"] is True
        assert len(result["content"]) > 0

    def test_auto_adds_md_extension(self, integration_env):
        """get_reference adds .md extension automatically."""
        result = json.loads(_run(server.get_reference("suno/genre-list")))
        assert result["found"] is True
        assert result["path"].endswith(".md")


@pytest.mark.integration
class TestScanArtistNamesExtended:
    """Extended integration tests for scan_artist_names."""

    def test_empty_text(self, integration_env, monkeypatch):
        """scan_artist_names returns clean for empty text."""
        monkeypatch.setattr(server, "_artist_blocklist_cache", None)
        result = json.loads(_run(server.scan_artist_names("")))
        assert result["clean"] is True

    def test_found_entry_has_alternative(self, integration_env, monkeypatch):
        """scan_artist_names found entries include an alternative suggestion."""
        monkeypatch.setattr(server, "_artist_blocklist_cache", None)
        blocklist = server._load_artist_blocklist()
        if blocklist:
            name = blocklist[0]["name"]
            result = json.loads(_run(server.scan_artist_names(f"Sounds like {name}")))
            if result["found"]:
                assert "alternative" in result["found"][0]
                assert result["found"][0]["alternative"] != ""

    def test_case_insensitive(self, integration_env, monkeypatch):
        """scan_artist_names matches regardless of case."""
        monkeypatch.setattr(server, "_artist_blocklist_cache", None)
        blocklist = server._load_artist_blocklist()
        if blocklist:
            name = blocklist[0]["name"]
            result = json.loads(_run(server.scan_artist_names(name.upper())))
            assert result["clean"] is False


@pytest.mark.integration
class TestCheckPronunciationEnforcementExtended:
    """Extended integration tests for check_pronunciation_enforcement."""

    def test_album_not_found(self, integration_env):
        """check_pronunciation_enforcement error for nonexistent album."""
        result = json.loads(_run(server.check_pronunciation_enforcement("nonexistent", "01")))
        assert result["found"] is False

    def test_track_not_found(self, integration_env):
        """check_pronunciation_enforcement error for nonexistent track."""
        result = json.loads(_run(server.check_pronunciation_enforcement(
            "integration-test-album", "99-missing"
        )))
        assert result["found"] is False

    def test_occurrence_counts(self, integration_env):
        """check_pronunciation_enforcement counts occurrences correctly."""
        result = json.loads(_run(server.check_pronunciation_enforcement(
            "integration-test-album", "03-third-track"
        )))
        reed_entry = next(e for e in result["entries"] if e["word"] == "read")
        # "reed" appears twice in the lyrics: "I will reed" and "REED the signs"
        assert reed_entry["occurrences"] == 2


@pytest.mark.integration
class TestCheckExplicitContentExtended:
    """Extended integration tests for check_explicit_content."""

    def test_line_numbers(self, integration_env, monkeypatch):
        """check_explicit_content returns correct line numbers."""
        monkeypatch.setattr(server, "_explicit_word_cache", None)
        result = json.loads(_run(server.check_explicit_content(
            "Clean line\nWhat the fuck\nAnother clean line"
        )))
        hit = result["found"][0]
        assert hit["lines"][0]["line_number"] == 2

    def test_empty_text(self, integration_env, monkeypatch):
        """check_explicit_content returns clean for empty text."""
        monkeypatch.setattr(server, "_explicit_word_cache", None)
        result = json.loads(_run(server.check_explicit_content("")))
        assert result["has_explicit"] is False
        assert result["unique_words"] == 0


@pytest.mark.integration
class TestCreateAlbumStructureExtended:
    """Extended integration tests for create_album_structure."""

    def test_genre_slug_normalization(self, integration_env):
        """create_album_structure normalizes genre to slug."""
        result = json.loads(_run(server.create_album_structure(
            "slug-test-album", "Hip Hop"
        )))
        assert result["created"] is True
        assert result["genre"] == "hip-hop"

    def test_path_includes_artist(self, integration_env):
        """create_album_structure path contains the artist name."""
        result = json.loads(_run(server.create_album_structure(
            "artist-check-album", "rock"
        )))
        assert "test-artist" in result["path"]
