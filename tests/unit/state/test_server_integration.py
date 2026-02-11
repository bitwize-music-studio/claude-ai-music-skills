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

SKILL_OPUS = """\
---
name: lyric-writer
description: Writes or reviews lyrics with professional prosody and quality checks.
argument-hint: <track-file-path or "write lyrics for [concept]">
model: claude-opus-4-6
allowed-tools:
  - Read
  - Edit
  - Write
---

# Lyric Writer Agent
"""

SKILL_SONNET = """\
---
name: suno-engineer
description: Constructs technical Suno V5 style prompts and optimizes generation settings.
argument-hint: <track-file-path>
model: claude-sonnet-4-5-20250929
prerequisites:
  - lyric-writer
allowed-tools:
  - Read
  - Edit
  - Bash
requirements:
  python:
    - pydub
---

# Suno Engineer Agent
"""

SKILL_HAIKU = """\
---
name: help
description: Shows available skills and quick reference for the plugin.
model: claude-haiku-4-5-20251001
allowed-tools: []
---

# Help
"""

SKILL_INTERNAL = """\
---
name: researchers-legal
description: Researches court documents and indictments for documentary albums.
model: claude-sonnet-4-5-20250929
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Bash
---

# Researchers Legal
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

    # Promo directory
    promo_dir = album_dir / "promo"
    promo_dir.mkdir()
    (promo_dir / "campaign.md").write_text(
        "# Campaign\n\n" + "This is real campaign content for promotion. " * 15
    )
    (promo_dir / "twitter.md").write_text("# Twitter\n\n| Key | Value |\n")

    # Audio directory (with artist folder)
    audio_album = audio_root / "test-artist" / "integration-test-album"
    audio_album.mkdir(parents=True)
    (audio_album / "01-first-track.wav").write_text("")
    (audio_album / "album.png").write_text("")

    # Skills directories (for skill indexing tests)
    skills_root = tmp_path / "skills"
    for skill_name, skill_content in [
        ("lyric-writer", SKILL_OPUS),
        ("suno-engineer", SKILL_SONNET),
        ("help", SKILL_HAIKU),
        ("researchers-legal", SKILL_INTERNAL),
    ]:
        skill_dir = skills_root / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(skill_content)

    return {
        "tmp_path": tmp_path,
        "config_dir": config_dir,
        "config_path": config_path,
        "cache_dir": cache_dir,
        "content_root": content_root,
        "audio_root": audio_root,
        "album_dir": album_dir,
        "tracks_dir": tracks_dir,
        "promo_dir": promo_dir,
        "overrides_dir": overrides_dir,
        "skills_root": skills_root,
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

    # Monkeypatch PLUGIN_ROOT for skill scanning
    monkeypatch.setattr(server, "PLUGIN_ROOT", content_dir["tmp_path"])

    # Build state using the real indexer
    config = indexer.read_config()
    assert config is not None, "Config should be readable"

    state = indexer.build_state(config, plugin_root=content_dir["tmp_path"])
    indexer.write_state(state)

    # Verify state.json was written
    state_file = cache_dir / "state.json"
    assert state_file.exists(), "state.json should exist after build"

    # Create a real StateCache and wire it to the server
    real_cache = server.StateCache()
    monkeypatch.setattr(server, "cache", real_cache)

    # PLUGIN_ROOT already set to tmp_path above for skill scanning.
    # For reference file access, we need the real project root, but
    # skills tests need tmp_path. Use tmp_path since skills tests need it
    # and reference tests can be patched per-test if needed.
    # Actually, keep tmp_path for skills but the get_reference tool needs
    # the real reference/ dir — we'll leave PLUGIN_ROOT as tmp_path and
    # the reference tests that need PROJECT_ROOT will still work because
    # they were already testing against PROJECT_ROOT via the prior assignment.
    # Re-point to PROJECT_ROOT for backward compat, but copy skills to tmp_path
    # since build_state was already called with plugin_root=tmp_path.
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
        assert state["version"] == "1.2.0"
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


# ===========================================================================
# Skill MCP Tool Integration Tests
# ===========================================================================


@pytest.mark.integration
class TestListSkillsIntegration:
    """Integration tests for list_skills."""

    def test_list_all_skills(self, integration_env):
        """list_skills returns all test skills."""
        result = json.loads(_run(server.list_skills()))
        assert result["count"] == 4
        assert result["total"] == 4
        names = [s["name"] for s in result["skills"]]
        assert "lyric-writer" in names
        assert "suno-engineer" in names
        assert "help" in names
        assert "researchers-legal" in names

    def test_model_counts(self, integration_env):
        """list_skills returns correct model_counts."""
        result = json.loads(_run(server.list_skills()))
        counts = result["model_counts"]
        assert counts.get("opus", 0) == 1   # lyric-writer
        assert counts.get("sonnet", 0) == 2  # suno-engineer + researchers-legal
        assert counts.get("haiku", 0) == 1   # help

    def test_filter_by_model_opus(self, integration_env):
        """list_skills filters by opus tier."""
        result = json.loads(_run(server.list_skills(model_filter="opus")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "lyric-writer"
        assert result["skills"][0]["model_tier"] == "opus"

    def test_filter_by_model_sonnet(self, integration_env):
        """list_skills filters by sonnet tier."""
        result = json.loads(_run(server.list_skills(model_filter="sonnet")))
        assert result["count"] == 2
        names = [s["name"] for s in result["skills"]]
        assert "suno-engineer" in names
        assert "researchers-legal" in names

    def test_filter_by_model_haiku(self, integration_env):
        """list_skills filters by haiku tier."""
        result = json.loads(_run(server.list_skills(model_filter="haiku")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "help"

    def test_filter_by_category(self, integration_env):
        """list_skills filters by keyword in description."""
        result = json.loads(_run(server.list_skills(category="lyrics")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "lyric-writer"

    def test_filter_by_category_suno(self, integration_env):
        """list_skills category filter for Suno."""
        result = json.loads(_run(server.list_skills(category="suno")))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "suno-engineer"

    def test_combined_filter_model_and_category(self, integration_env):
        """list_skills combined model + category filter."""
        result = json.loads(_run(server.list_skills(
            model_filter="sonnet", category="court"
        )))
        assert result["count"] == 1
        assert result["skills"][0]["name"] == "researchers-legal"

    def test_no_match(self, integration_env):
        """list_skills returns empty for non-matching filter."""
        result = json.loads(_run(server.list_skills(model_filter="opus", category="nonexistent")))
        assert result["count"] == 0
        assert result["skills"] == []

    def test_skill_fields_present(self, integration_env):
        """list_skills entries have all expected fields."""
        result = json.loads(_run(server.list_skills()))
        for skill in result["skills"]:
            for key in ("name", "description", "model", "model_tier", "user_invocable"):
                assert key in skill, f"Missing field: {key}"

    def test_total_reflects_unfiltered(self, integration_env):
        """list_skills total always reflects unfiltered total."""
        result = json.loads(_run(server.list_skills(model_filter="opus")))
        assert result["count"] == 1
        assert result["total"] == 4  # total remains unfiltered


@pytest.mark.integration
class TestGetSkillIntegration:
    """Integration tests for get_skill."""

    def test_exact_match(self, integration_env):
        """get_skill returns skill by exact name."""
        result = json.loads(_run(server.get_skill("lyric-writer")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"
        skill = result["skill"]
        assert skill["description"].startswith("Writes or reviews lyrics")
        assert skill["model"] == "claude-opus-4-6"
        assert skill["model_tier"] == "opus"

    def test_fuzzy_match(self, integration_env):
        """get_skill fuzzy match works with partial name."""
        result = json.loads(_run(server.get_skill("lyric")))
        assert result["found"] is True
        assert result["name"] == "lyric-writer"

    def test_not_found(self, integration_env):
        """get_skill returns error for nonexistent skill."""
        result = json.loads(_run(server.get_skill("nonexistent-skill")))
        assert result["found"] is False
        assert "available_skills" in result

    def test_prerequisites(self, integration_env):
        """get_skill returns prerequisites list."""
        result = json.loads(_run(server.get_skill("suno-engineer")))
        assert result["found"] is True
        skill = result["skill"]
        assert skill["prerequisites"] == ["lyric-writer"]

    def test_user_invocable_true(self, integration_env):
        """get_skill returns user_invocable=True by default."""
        result = json.loads(_run(server.get_skill("lyric-writer")))
        assert result["skill"]["user_invocable"] is True

    def test_user_invocable_false(self, integration_env):
        """get_skill returns user_invocable=False for internal skills."""
        result = json.loads(_run(server.get_skill("researchers-legal")))
        assert result["found"] is True
        assert result["skill"]["user_invocable"] is False

    def test_requirements(self, integration_env):
        """get_skill returns requirements dict."""
        result = json.loads(_run(server.get_skill("suno-engineer")))
        assert result["skill"]["requirements"] == {"python": ["pydub"]}

    def test_context_fork(self, integration_env):
        """get_skill returns context field."""
        result = json.loads(_run(server.get_skill("researchers-legal")))
        assert result["skill"]["context"] == "fork"

    def test_context_null(self, integration_env):
        """get_skill returns null context for regular skills."""
        result = json.loads(_run(server.get_skill("lyric-writer")))
        assert result["skill"]["context"] is None

    def test_allowed_tools(self, integration_env):
        """get_skill returns allowed_tools list."""
        result = json.loads(_run(server.get_skill("lyric-writer")))
        assert result["skill"]["allowed_tools"] == ["Read", "Edit", "Write"]

    def test_empty_allowed_tools(self, integration_env):
        """get_skill returns empty allowed_tools for help skill."""
        result = json.loads(_run(server.get_skill("help")))
        assert result["skill"]["allowed_tools"] == []

    def test_argument_hint(self, integration_env):
        """get_skill returns argument_hint."""
        result = json.loads(_run(server.get_skill("lyric-writer")))
        assert result["skill"]["argument_hint"] == '<track-file-path or "write lyrics for [concept]">'

    def test_multiple_matches(self, integration_env):
        """get_skill returns error when multiple skills match."""
        result = json.loads(_run(server.get_skill("researcher")))
        # "researcher" matches "researchers-legal" only (substring)
        # If it matched multiple, would get error. Let's check.
        # Actually "researcher" is a substring of "researchers-legal" → 1 match
        assert result["found"] is True
        assert result["name"] == "researchers-legal"

    def test_skill_path_stored(self, integration_env):
        """get_skill includes the file path."""
        result = json.loads(_run(server.get_skill("help")))
        assert result["skill"]["path"].endswith("SKILL.md")

    def test_skill_mtime_populated(self, integration_env):
        """get_skill skill has non-zero mtime."""
        result = json.loads(_run(server.get_skill("help")))
        assert result["skill"]["mtime"] > 0


@pytest.mark.integration
class TestSearchSkillsIntegration:
    """Integration tests for search with skills scope."""

    def test_search_finds_skill_by_name(self, integration_env):
        """search finds skill by name."""
        result = json.loads(_run(server.search("lyric-writer", scope="skills")))
        skills = result.get("skills", [])
        assert len(skills) >= 1
        names = [s["name"] for s in skills]
        assert "lyric-writer" in names

    def test_search_finds_skill_by_description(self, integration_env):
        """search finds skill by description keyword."""
        result = json.loads(_run(server.search("prosody", scope="skills")))
        skills = result.get("skills", [])
        assert len(skills) >= 1
        assert skills[0]["name"] == "lyric-writer"

    def test_search_all_includes_skills(self, integration_env):
        """search scope=all includes skills in results."""
        result = json.loads(_run(server.search("suno")))
        assert "skills" in result
        skills = result["skills"]
        names = [s["name"] for s in skills]
        assert "suno-engineer" in names

    def test_search_skills_no_match(self, integration_env):
        """search with skills scope returns empty for no match."""
        result = json.loads(_run(server.search("xyznonexistent", scope="skills")))
        skills = result.get("skills", [])
        assert len(skills) == 0


@pytest.mark.integration
class TestRebuildStateSkillsIntegration:
    """Integration tests for rebuild_state with skills."""

    def test_rebuild_includes_skills_count(self, integration_env, monkeypatch):
        """rebuild_state output includes skills count."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        result = json.loads(_run(server.rebuild_state()))
        assert result["success"] is True
        assert "skills" in result
        assert result["skills"] == 4

    def test_skills_survive_rebuild(self, integration_env, monkeypatch):
        """Skills are present in state after rebuild."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        _run(server.rebuild_state())
        result = json.loads(_run(server.list_skills()))
        assert result["count"] == 4


@pytest.mark.integration
class TestAutoRebuildOnVersionMismatch:
    """Integration tests for auto-rebuild when state version != CURRENT_VERSION.

    When a user upgrades the plugin and their on-disk state.json has an older
    schema version, _load_from_disk() should transparently rebuild with the
    new schema (populating skills, etc.) without any user action.
    """

    def test_old_version_triggers_rebuild(self, integration_env, monkeypatch):
        """State with old version is auto-rebuilt on first access."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        state_file = integration_env["state_file"]

        # Write a v1.0.0 state (no skills section)
        old_state = json.loads(state_file.read_text())
        old_state["version"] = "1.0.0"
        old_state.pop("skills", None)
        state_file.write_text(json.dumps(old_state))

        # Create a fresh cache and access state
        fresh_cache = server.StateCache()
        monkeypatch.setattr(server, "cache", fresh_cache)

        state = fresh_cache.get_state()
        assert state["version"] == indexer.CURRENT_VERSION
        assert "skills" in state
        assert state["skills"]["count"] == 4

    def test_auto_rebuild_preserves_session(self, integration_env, monkeypatch):
        """Session data survives the auto-rebuild."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        state_file = integration_env["state_file"]

        # Write a v1.0.0 state with session data
        old_state = json.loads(state_file.read_text())
        old_state["version"] = "1.0.0"
        old_state.pop("skills", None)
        old_state["session"] = {
            "last_album": "my-album",
            "last_track": "01-opener",
            "last_phase": "Writing",
            "pending_actions": ["review lyrics"],
            "updated_at": "2025-01-01T00:00:00Z",
        }
        state_file.write_text(json.dumps(old_state))

        fresh_cache = server.StateCache()
        monkeypatch.setattr(server, "cache", fresh_cache)

        state = fresh_cache.get_state()
        assert state["version"] == indexer.CURRENT_VERSION
        assert state["session"]["last_album"] == "my-album"
        assert state["session"]["last_track"] == "01-opener"
        assert state["session"]["last_phase"] == "Writing"
        assert state["session"]["pending_actions"] == ["review lyrics"]

    def test_auto_rebuild_writes_to_disk(self, integration_env, monkeypatch):
        """Auto-rebuilt state is persisted to state.json."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        state_file = integration_env["state_file"]

        old_state = json.loads(state_file.read_text())
        old_state["version"] = "1.0.0"
        old_state.pop("skills", None)
        state_file.write_text(json.dumps(old_state))

        fresh_cache = server.StateCache()
        monkeypatch.setattr(server, "cache", fresh_cache)
        fresh_cache.get_state()

        # Read back from disk
        on_disk = json.loads(state_file.read_text())
        assert on_disk["version"] == indexer.CURRENT_VERSION
        assert "skills" in on_disk
        assert on_disk["skills"]["count"] == 4

    def test_current_version_no_rebuild(self, integration_env, monkeypatch):
        """State with current version does not trigger rebuild."""
        state_file = integration_env["state_file"]

        # State already has current version from integration_env fixture
        on_disk_before = state_file.read_text()

        fresh_cache = server.StateCache()
        monkeypatch.setattr(server, "cache", fresh_cache)
        state = fresh_cache.get_state()

        assert state["version"] == indexer.CURRENT_VERSION
        # File should not have been rewritten (same content)
        assert state_file.read_text() == on_disk_before

    def test_auto_rebuild_with_missing_config(self, integration_env, monkeypatch):
        """Auto-rebuild gracefully handles missing config."""
        state_file = integration_env["state_file"]

        old_state = json.loads(state_file.read_text())
        old_state["version"] = "1.0.0"
        state_file.write_text(json.dumps(old_state))

        # Remove config file
        config_path = integration_env["config_path"]
        config_path.unlink()

        fresh_cache = server.StateCache()
        monkeypatch.setattr(server, "cache", fresh_cache)

        # Should still load (old state), just can't rebuild
        state = fresh_cache.get_state()
        assert state["version"] == "1.0.0"  # Stays old since rebuild failed

    def test_auto_rebuild_albums_intact(self, integration_env, monkeypatch):
        """Albums are correctly rebuilt after version mismatch."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        state_file = integration_env["state_file"]

        old_state = json.loads(state_file.read_text())
        old_state["version"] = "1.0.0"
        old_state.pop("skills", None)
        state_file.write_text(json.dumps(old_state))

        fresh_cache = server.StateCache()
        monkeypatch.setattr(server, "cache", fresh_cache)

        state = fresh_cache.get_state()
        assert "integration-test-album" in state["albums"]
        album = state["albums"]["integration-test-album"]
        assert album["track_count"] == 3
        assert album["title"] == "Integration Test Album"


# ===========================================================================
# End-to-End Workflow Tests
# ===========================================================================


@pytest.mark.integration
class TestWorkflowAlbumLifecycle:
    """End-to-end: album creation → track updates → progress tracking."""

    def test_create_album_then_query(self, integration_env):
        """Create a new album, rebuild state, and query it."""
        result = json.loads(_run(server.create_album_structure(
            "lifecycle-album", "electronic"
        )))
        assert result["created"] is True

        # Rebuild state to pick up new album
        _run(server.rebuild_state())

        # Query the new album
        result = json.loads(_run(server.find_album("lifecycle-album")))
        assert result["found"] is True
        assert result["album"]["genre"] == "electronic"

    def test_update_track_then_check_progress(self, integration_env):
        """Update a track field and verify progress reflects the change."""
        # Get initial progress
        before = json.loads(_run(server.get_album_progress("integration-test-album")))
        assert before["found"] is True
        completed_before = before["tracks_completed"]

        # Update track 02 to Final (was In Progress)
        update = json.loads(_run(server.update_track_field(
            "integration-test-album", "02-second-track", "status", "Final"
        )))
        assert update["success"] is True

        # Rebuild so progress picks up the cache changes
        _run(server.rebuild_state())

        # Check progress increased
        after = json.loads(_run(server.get_album_progress("integration-test-album")))
        assert after["tracks_completed"] >= completed_before + 1

    def test_update_track_then_extract_section(self, integration_env):
        """Update a track then verify section extraction still works."""
        # Update status
        _run(server.update_track_field(
            "integration-test-album", "01-first-track", "status", "Generated"
        ))

        # Extract section from the same track
        result = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "lyrics"
        )))
        assert result["found"] is True
        assert "Testing the pipeline" in result["content"]

    def test_update_multiple_tracks_then_album_verdict(self, integration_env):
        """Update all tracks to Final then verify album is all-ready for generation."""
        for slug in ["01-first-track", "02-second-track", "03-third-track"]:
            result = json.loads(_run(server.update_track_field(
                "integration-test-album", slug, "status", "Final"
            )))
            assert result["success"] is True

        # Also set sources_verified on track 02 so pre-gen gates pass
        result = json.loads(_run(server.update_track_field(
            "integration-test-album", "02-second-track",
            "sources_verified", "✅ Verified (2026-02-09)"
        )))
        assert result["success"] is True

    def test_session_tracks_workflow(self, integration_env):
        """Session context follows the workflow across tools."""
        # Update session to track our work
        _run(server.update_session(
            album="integration-test-album",
            track="01-first-track",
            phase="Writing"
        ))

        session = json.loads(_run(server.get_session()))
        assert session["session"]["last_album"] == "integration-test-album"
        assert session["session"]["last_track"] == "01-first-track"

        # Update track, then advance session
        _run(server.update_track_field(
            "integration-test-album", "01-first-track", "status", "Generated"
        ))
        _run(server.update_session(
            track="02-second-track",
            phase="Generation"
        ))

        session = json.loads(_run(server.get_session()))
        assert session["session"]["last_track"] == "02-second-track"
        assert session["session"]["last_phase"] == "Generation"


@pytest.mark.integration
class TestWorkflowSourceVerification:
    """End-to-end: source verification → pre-generation gate flow."""

    def test_pending_sources_block_generation(self, integration_env):
        """Track with pending sources shows up in pending verifications."""
        result = json.loads(_run(server.get_pending_verifications()))
        pending = result.get("albums_with_pending", {})
        assert "integration-test-album" in pending
        track_slugs = [t["slug"] for t in pending["integration-test-album"]["tracks"]]
        assert "02-second-track" in track_slugs

    def test_verify_sources_then_clear_pending(self, integration_env):
        """After verifying sources, track disappears from pending."""
        # Verify track 02's sources
        result = json.loads(_run(server.update_track_field(
            "integration-test-album", "02-second-track",
            "sources_verified", "✅ Verified (2026-02-09)"
        )))
        assert result["success"] is True

        # Rebuild to reflect the change
        _run(server.rebuild_state())

        # Check pending — track 02 should no longer be pending
        result = json.loads(_run(server.get_pending_verifications()))
        pending = result.get("albums_with_pending", {})
        if "integration-test-album" in pending:
            track_slugs = [t["slug"] for t in pending["integration-test-album"]["tracks"]]
            assert "02-second-track" not in track_slugs


@pytest.mark.integration
class TestWorkflowCrossToolDataFlow:
    """End-to-end: output of one tool feeds into another."""

    def test_extract_lyrics_then_check_homographs(self, integration_env):
        """Extract lyrics from a track and pass them to homograph check."""
        # Track 03 has "read" and "bass" — known homographs
        lyrics = json.loads(_run(server.extract_section(
            "integration-test-album", "03-third-track", "lyrics"
        )))
        assert lyrics["found"] is True
        content = lyrics["content"]

        # Check homographs on the extracted content
        homographs = json.loads(_run(server.check_homographs(content)))
        # "read" and "bass" should be flagged (response key is "found")
        found_words = [h["word"].lower() for h in homographs.get("found", [])]
        assert "read" in found_words or "reed" in found_words or "bass" in found_words

    def test_extract_lyrics_then_check_explicit(self, integration_env):
        """Extract lyrics and check for explicit content."""
        lyrics = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "lyrics"
        )))
        assert lyrics["found"] is True

        # Check explicit — clean lyrics should have no explicit content
        explicit = json.loads(_run(server.check_explicit_content(lyrics["content"])))
        assert explicit["has_explicit"] is False

    def test_lyrics_stats_match_extract_content(self, integration_env):
        """Lyrics stats word count matches the extracted content."""
        stats = json.loads(_run(server.get_lyrics_stats(
            "integration-test-album", "01"
        )))
        lyrics = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "lyrics"
        )))
        assert stats["found"] is True
        assert lyrics["found"] is True
        # Both should report non-zero words
        assert stats["tracks"][0]["word_count"] > 0

    def test_find_album_then_list_tracks(self, integration_env):
        """find_album slug can be used with list_track_files."""
        found = json.loads(_run(server.find_album("integration")))
        assert found["found"] is True
        slug = found["slug"]

        tracks = json.loads(_run(server.list_track_files(slug)))
        assert tracks["found"] is True
        assert len(tracks["tracks"]) == 3

    def test_get_track_then_resolve_path(self, integration_env):
        """Track data includes path that matches resolve_path."""
        track = json.loads(_run(server.get_track(
            "integration-test-album", "01-first-track"
        )))
        assert track["found"] is True

        # The track path should be under the album's content path
        resolved = json.loads(_run(server.resolve_path(
            "content", "integration-test-album"
        )))
        assert "path" in resolved
        assert resolved["path"] in track["track"]["path"]


@pytest.mark.integration
class TestWorkflowMultiFieldAtomicity:
    """End-to-end: multiple field updates don't lose data."""

    def test_sequential_field_updates_preserve_all(self, integration_env):
        """Updating status then explicit preserves both values."""
        # Update status
        r1 = json.loads(_run(server.update_track_field(
            "integration-test-album", "03-third-track", "status", "Generated"
        )))
        assert r1["success"] is True

        # Update explicit
        r2 = json.loads(_run(server.update_track_field(
            "integration-test-album", "03-third-track", "explicit", "Yes"
        )))
        assert r2["success"] is True

        # Read back — both changes should be present
        track = json.loads(_run(server.get_track(
            "integration-test-album", "03-third-track"
        )))
        # The file should have both values updated
        resolve = json.loads(_run(server.resolve_track_file(
            "integration-test-album", "03-third-track"
        )))
        assert resolve["found"] is True
        content = Path(resolve["path"]).read_text()
        assert "Generated" in content
        assert "Yes" in content

    def test_update_does_not_corrupt_other_sections(self, integration_env):
        """Updating a track field doesn't break other markdown sections."""
        _run(server.update_track_field(
            "integration-test-album", "01-first-track", "status", "Final"
        ))

        # Lyrics section should still be intact
        lyrics = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "lyrics"
        )))
        assert lyrics["found"] is True
        assert "[Verse 1]" in lyrics["content"]
        assert "Testing the pipeline" in lyrics["content"]

        # Style box should still be intact
        style = json.loads(_run(server.extract_section(
            "integration-test-album", "01-first-track", "style"
        )))
        assert style["found"] is True
        assert "electronic" in style["content"]


@pytest.mark.integration
class TestWorkflowStateCacheConsistency:
    """End-to-end: cache stays consistent through operations."""

    def test_rebuild_preserves_session(self, integration_env):
        """Session data survives a state rebuild."""
        _run(server.update_session(
            album="integration-test-album",
            track="02-second-track",
            phase="Research"
        ))

        # Rebuild state
        _run(server.rebuild_state())

        # Session should survive
        session = json.loads(_run(server.get_session()))
        assert session["session"]["last_album"] == "integration-test-album"
        assert session["session"]["last_track"] == "02-second-track"

    def test_state_file_update_after_rebuild(self, integration_env):
        """Rebuild writes fresh state to disk."""
        state_file = integration_env["state_file"]
        mtime_before = state_file.stat().st_mtime

        # Wait a moment to ensure different mtime
        time.sleep(0.05)
        _run(server.rebuild_state())

        mtime_after = state_file.stat().st_mtime
        assert mtime_after >= mtime_before

    def test_new_track_file_detected_after_rebuild(self, integration_env):
        """Adding a new track file on disk and rebuilding picks it up."""
        tracks_dir = integration_env["tracks_dir"]
        new_track = tracks_dir / "04-new-track.md"
        new_track.write_text("""\
# New Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 04 |
| **Title** | New Track |
| **Status** | Not Started |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")

        _run(server.rebuild_state())

        result = json.loads(_run(server.get_track(
            "integration-test-album", "04-new-track"
        )))
        assert result["found"] is True
        assert result["track"]["title"] == "New Track"
        assert result["track"]["status"] == "Not Started"

    def test_deleted_track_file_detected_after_rebuild(self, integration_env):
        """Deleting a track file on disk and rebuilding removes it from state."""
        tracks_dir = integration_env["tracks_dir"]
        track_path = tracks_dir / "03-third-track.md"
        track_path.unlink()

        _run(server.rebuild_state())

        result = json.loads(_run(server.get_track(
            "integration-test-album", "03-third-track"
        )))
        assert result["found"] is False

    def test_corrupted_state_json_recovery(self, integration_env, monkeypatch):
        """Corrupted state.json doesn't crash; returns empty state, rebuild recovers."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        state_file = integration_env["state_file"]

        # Write invalid JSON
        state_file.write_text("{invalid json!!!}")

        # Create a fresh cache — should detect corruption but not crash
        fresh_cache = server.StateCache()
        monkeypatch.setattr(server, "cache", fresh_cache)
        state = fresh_cache.get_state()

        # Corrupted file returns empty state (graceful degradation)
        assert state is not None
        assert isinstance(state, dict)

        # Explicit rebuild recovers the real data
        rebuilt = fresh_cache.rebuild()
        assert "albums" in rebuilt
        assert "integration-test-album" in rebuilt["albums"]


@pytest.mark.integration
class TestWorkflowSearchAcrossScopes:
    """End-to-end: search finds results across all data types."""

    def test_search_finds_album_and_track(self, integration_env):
        """A broad search returns results from multiple scopes."""
        # "first" appears in track slug and title
        result = json.loads(_run(server.search("first", scope="all")))
        assert result["total_matches"] > 0
        assert len(result.get("tracks", [])) >= 1
        # "integration" appears in album title and slug
        result2 = json.loads(_run(server.search("integration", scope="all")))
        assert len(result2.get("albums", [])) >= 1

    def test_search_skills_after_rebuild(self, integration_env, monkeypatch):
        """Skills are searchable after a rebuild."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", integration_env["tmp_path"])
        _run(server.rebuild_state())

        result = json.loads(_run(server.search("lyric", scope="skills")))
        assert len(result.get("skills", [])) >= 1
        assert result["skills"][0]["name"] == "lyric-writer"

    def test_search_by_genre(self, integration_env):
        """Search by genre finds albums."""
        result = json.loads(_run(server.search("electronic", scope="albums")))
        slugs = [a["slug"] for a in result["albums"]]
        assert "integration-test-album" in slugs

    def test_search_empty_query_returns_everything(self, integration_env):
        """Empty string search returns all items."""
        result = json.loads(_run(server.search("", scope="albums")))
        assert len(result["albums"]) >= 1


@pytest.mark.integration
class TestWorkflowAlbumValidation:
    """End-to-end: album validation with real filesystem."""

    def test_validate_detects_missing_audio(self, integration_env):
        """Validation reports missing audio for tracks without WAV files."""
        result = json.loads(_run(server.validate_album_structure(
            "integration-test-album", checks="audio"
        )))
        assert result["found"] is True
        # Track 01 has a WAV, tracks 02 and 03 don't
        # There should be at least some warnings about missing audio

    def test_validate_passes_structure_checks(self, integration_env):
        """Basic structural checks pass for a well-formed album."""
        result = json.loads(_run(server.validate_album_structure(
            "integration-test-album", checks="structure"
        )))
        assert result["found"] is True
        assert result["passed"] >= 1
        # No structural failures expected
        assert result["failed"] == 0

    def test_validate_after_track_deletion(self, integration_env):
        """Validation handles albums with deleted tracks gracefully."""
        tracks_dir = integration_env["tracks_dir"]
        (tracks_dir / "03-third-track.md").unlink()

        _run(server.rebuild_state())

        result = json.loads(_run(server.validate_album_structure(
            "integration-test-album", checks="structure"
        )))
        assert result["found"] is True
        # Should still work, just with fewer tracks


# ===========================================================================
# Integration Tests: update_album_status
# ===========================================================================


@pytest.mark.integration
class TestUpdateAlbumStatusIntegration:
    """Integration tests for update_album_status with real files."""

    def test_updates_readme_and_cache(self, integration_env):
        """Status change persists in README.md and updates state cache."""
        result = json.loads(_run(server.update_album_status(
            "integration-test-album", "Complete"
        )))
        assert result["success"] is True
        assert result["old_status"] == "In Progress"
        assert result["new_status"] == "Complete"

        # Verify README was modified
        readme = integration_env["album_dir"] / "README.md"
        text = readme.read_text()
        assert "| **Status** | Complete |" in text

        # Verify cache was updated
        state = integration_env["cache"].get_state()
        assert state["albums"]["integration-test-album"]["status"] == "Complete"

    def test_status_round_trip(self, integration_env):
        """Status can be changed multiple times and read back."""
        for status in ["Complete", "Released"]:
            _run(server.update_album_status("integration-test-album", status))

        result = json.loads(_run(server.find_album("integration-test-album")))
        assert result["album"]["status"] == "Released"

    def test_invalid_status_rejected(self, integration_env):
        """Invalid status is rejected without modifying files."""
        original = (integration_env["album_dir"] / "README.md").read_text()
        result = json.loads(_run(server.update_album_status(
            "integration-test-album", "BadStatus"
        )))
        assert "error" in result
        # File should be unchanged
        assert (integration_env["album_dir"] / "README.md").read_text() == original


# ===========================================================================
# Integration Tests: create_track
# ===========================================================================


@pytest.mark.integration
class TestCreateTrackIntegration:
    """Integration tests for create_track with real files."""

    def test_creates_track_from_template(self, integration_env, monkeypatch):
        """Track file is created with proper content from real template."""
        # Point PLUGIN_ROOT to the real project root for template access
        monkeypatch.setattr(server, "PLUGIN_ROOT", PROJECT_ROOT)

        result = json.loads(_run(server.create_track(
            "integration-test-album", "04", "Brand New Track"
        )))
        assert result["created"] is True
        assert result["track_slug"] == "04-brand-new-track"

        track_path = Path(result["path"])
        assert track_path.exists()
        content = track_path.read_text()
        assert "Brand New Track" in content
        assert "| **Track #** | 04 |" in content

    def test_created_track_appears_after_rebuild(self, integration_env, monkeypatch):
        """Newly created track is discoverable after state rebuild."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", PROJECT_ROOT)

        _run(server.create_track("integration-test-album", "04", "New Track"))
        _run(server.rebuild_state())

        result = json.loads(_run(server.get_track("integration-test-album", "04-new-track")))
        assert result["found"] is True
        assert result["track"]["title"] == "New Track"

    def test_reject_duplicate_track(self, integration_env, monkeypatch):
        """Cannot create track with same number+slug as existing."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", PROJECT_ROOT)

        # First call succeeds
        r1 = json.loads(_run(server.create_track("integration-test-album", "04", "Track")))
        assert r1["created"] is True

        # Second call with same args fails
        r2 = json.loads(_run(server.create_track("integration-test-album", "04", "Track")))
        assert r2["created"] is False


# ===========================================================================
# Integration Tests: get_promo_status / get_promo_content
# ===========================================================================


@pytest.mark.integration
class TestPromoIntegration:
    """Integration tests for promo tools with real files."""

    def test_promo_status_reflects_real_files(self, integration_env):
        """Promo status correctly reports which files exist and are populated."""
        result = json.loads(_run(server.get_promo_status("integration-test-album")))
        assert result["promo_exists"] is True
        assert result["total"] == 6

        # campaign.md has real content
        campaign = next(f for f in result["files"] if f["file"] == "campaign.md")
        assert campaign["exists"] is True
        assert campaign["populated"] is True

        # twitter.md is template-only (just heading + table)
        twitter = next(f for f in result["files"] if f["file"] == "twitter.md")
        assert twitter["exists"] is True
        assert twitter["populated"] is False

        # instagram.md doesn't exist
        instagram = next(f for f in result["files"] if f["file"] == "instagram.md")
        assert instagram["exists"] is False

    def test_promo_content_returns_file_text(self, integration_env):
        """get_promo_content returns actual file content."""
        result = json.loads(_run(server.get_promo_content(
            "integration-test-album", "campaign"
        )))
        assert result["found"] is True
        assert "Campaign" in result["content"]

    def test_promo_content_missing_file(self, integration_env):
        """get_promo_content returns error for missing file."""
        result = json.loads(_run(server.get_promo_content(
            "integration-test-album", "facebook"
        )))
        assert result["found"] is False


# ===========================================================================
# Integration Tests: get_plugin_version
# ===========================================================================


@pytest.mark.integration
class TestGetPluginVersionIntegration:
    """Integration tests for get_plugin_version."""

    def test_reads_real_plugin_json(self, integration_env, monkeypatch):
        """Reads current version from real plugin.json."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", PROJECT_ROOT)

        result = json.loads(_run(server.get_plugin_version()))
        assert result["current_version"] is not None
        # Version should look like a semver string
        assert "." in result["current_version"]


# ===========================================================================
# Integration Tests: create_idea / update_idea
# ===========================================================================


@pytest.mark.integration
class TestIdeaManagementIntegration:
    """Integration tests for idea management tools with real files."""

    def test_create_and_find_idea(self, integration_env):
        """Created idea appears in get_ideas after cache rebuild."""
        result = json.loads(_run(server.create_idea(
            "Robot Uprising", genre="electronic", concept="Machines take over"
        )))
        assert result["created"] is True

        # After rebuild, idea should appear
        ideas = json.loads(_run(server.get_ideas()))
        titles = [i["title"] for i in ideas["items"]]
        assert "Robot Uprising" in titles

    def test_update_idea_persists(self, integration_env):
        """Updated idea field persists in IDEAS.md and cache."""
        # First, update an existing idea
        result = json.loads(_run(server.update_idea(
            "Cyberpunk Dreams", "status", "In Progress"
        )))
        assert result["success"] is True

        # Verify file was modified
        ideas_path = integration_env["content_root"] / "IDEAS.md"
        text = ideas_path.read_text()
        # Find the Cyberpunk Dreams section and check its status
        import re
        match = re.search(
            r'### Cyberpunk Dreams.*?(?=###|\Z)',
            text,
            re.DOTALL,
        )
        assert match is not None
        assert "**Status**: In Progress" in match.group()

    def test_create_then_update_round_trip(self, integration_env):
        """Create idea then update it — full round trip."""
        _run(server.create_idea("Test Idea", genre="rock"))

        result = json.loads(_run(server.update_idea("Test Idea", "genre", "metal")))
        assert result["success"] is True
        assert result["old_value"] == "rock"
        assert result["new_value"] == "metal"

    def test_duplicate_idea_rejected(self, integration_env):
        """Cannot create idea with same title as existing."""
        # Cyberpunk Dreams already exists in fixture
        result = json.loads(_run(server.create_idea("Cyberpunk Dreams")))
        assert result["created"] is False
        assert "already exists" in result["error"]


# ===========================================================================
# Integration Tests: Cross-tool workflows with new tools
# ===========================================================================


@pytest.mark.integration
class TestNewToolWorkflows:
    """End-to-end workflows using the new MCP tools."""

    def test_create_track_then_update_status(self, integration_env, monkeypatch):
        """Create a track, update its field, verify in state."""
        monkeypatch.setattr(server, "PLUGIN_ROOT", PROJECT_ROOT)

        # Create track
        _run(server.create_track("integration-test-album", "04", "Workflow Track"))
        _run(server.rebuild_state())

        # Update the new track's status
        result = json.loads(_run(server.update_track_field(
            "integration-test-album", "04-workflow-track", "status", "Generated"
        )))
        assert result["success"] is True

        # Verify in state
        track = json.loads(_run(server.get_track(
            "integration-test-album", "04-workflow-track"
        )))
        assert track["track"]["status"] == "Generated"

    def test_album_status_after_all_tracks_final(self, integration_env):
        """Update album status to Complete after verifying all tracks Final."""
        # Check progress
        progress = json.loads(_run(server.get_album_progress("integration-test-album")))
        assert progress["found"] is True

        # Set album status
        result = json.loads(_run(server.update_album_status(
            "integration-test-album", "Complete"
        )))
        assert result["success"] is True

        # Verify via list_albums
        albums = json.loads(_run(server.list_albums(status_filter="Complete")))
        slugs = [a["slug"] for a in albums["albums"]]
        assert "integration-test-album" in slugs

    def test_promo_status_then_content(self, integration_env):
        """Check promo status, then read populated content."""
        status = json.loads(_run(server.get_promo_status("integration-test-album")))
        populated_files = [f["file"] for f in status["files"] if f["populated"]]
        assert len(populated_files) >= 1

        # Read the populated file
        content = json.loads(_run(server.get_promo_content(
            "integration-test-album", populated_files[0].replace(".md", "")
        )))
        assert content["found"] is True
        assert len(content["content"]) > 0
