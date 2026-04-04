#!/usr/bin/env python3
"""
Unit tests for handlers/gates.py — pre-generation gate validation logic.

Tests the 8 individual gates, per-track gate evaluation, and the
run_pre_generation_gates MCP tool handler.

Usage:
    python -m pytest tests/unit/state/test_handlers_gates.py -v
"""

import asyncio
import copy
import importlib
import importlib.util
import json
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed
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
    spec = importlib.util.spec_from_file_location("state_server_gates", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import gates as _gates_mod
from handlers import text_analysis as _text_analysis_mod
from handlers import _shared as _shared_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


SAMPLE_STATE = {
    "version": 2,
    "config": {
        "content_root": "/tmp/test-content",
        "audio_root": "/tmp/test-audio",
        "documents_root": "/tmp/test-docs",
        "artist_name": "test-artist",
    },
    "albums": {
        "test-album": {
            "title": "Test Album",
            "status": "In Progress",
            "genre": "electronic",
            "path": "/tmp/test-content/artists/test-artist/albums/electronic/test-album",
            "track_count": 2,
            "tracks": {
                "01-first-track": {
                    "title": "First Track",
                    "status": "In Progress",
                    "explicit": False,
                    "has_suno_link": False,
                    "sources_verified": "N/A",
                    "path": "/tmp/tracks/01-first-track.md",
                    "mtime": 1234567890.0,
                },
                "02-second-track": {
                    "title": "Second Track",
                    "status": "In Progress",
                    "explicit": None,
                    "has_suno_link": False,
                    "sources_verified": "Pending",
                    "path": "/tmp/tracks/02-second-track.md",
                    "mtime": 1234567891.0,
                },
            },
        },
    },
    "ideas": {"total": 0, "by_status": {}, "items": []},
    "session": {
        "last_album": None,
        "last_track": None,
        "last_phase": None,
        "pending_actions": [],
        "updated_at": None,
    },
}


def _fresh_state():
    return copy.deepcopy(SAMPLE_STATE)


class MockStateCache:
    def __init__(self, state=None):
        self._state = state if state is not None else _fresh_state()

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}

    def rebuild(self):
        return self._state


# ---------------------------------------------------------------------------
# Track file templates for testing
# ---------------------------------------------------------------------------

TRACK_FILE_COMPLETE = """\
---
title: First Track
status: In Progress
explicit: false
---

## Lyrics Box

```
[Verse 1]
Walking down the road tonight
Stars are shining bright
Every step I take
Keeps me wide awake
```

## Style Box

```
upbeat electronic pop, synth-driven, 120 BPM
```

## Pronunciation Notes

| Word | Phonetic | Note |
| --- | --- | --- |
| — | — | — |

## Streaming Lyrics

```
Walking down the road tonight
Stars are shining bright
Every step I take
Keeps me wide awake
```
"""

TRACK_FILE_EMPTY_LYRICS = """\
---
title: Second Track
status: In Progress
explicit: false
---

## Lyrics Box

```
```

## Style Box

```
dark ambient electronic, 80 BPM
```
"""

TRACK_FILE_WITH_TODO = """\
---
title: Second Track
status: In Progress
explicit: false
---

## Lyrics Box

```
[Verse 1]
This is a line [TODO]
Another line here
```

## Style Box

```
dark ambient electronic, 80 BPM
```
"""

TRACK_FILE_WITH_PRONUNCIATION = """\
---
title: Track With Pronunciation
status: In Progress
explicit: false
---

## Lyrics Box

```
[Verse 1]
The LEE-ver was pulled hard
Walking down the road
```

## Style Box

```
rock ballad, 90 BPM
```

## Pronunciation Notes

| Word | Phonetic | Note |
| --- | --- | --- |
| lever | LEE-ver | British pronunciation |
"""

TRACK_FILE_UNAPPLIED_PRONUNCIATION = """\
---
title: Track With Unapplied Pronunciation
status: In Progress
explicit: false
---

## Lyrics Box

```
[Verse 1]
The lever was pulled hard
Walking down the road
```

## Style Box

```
rock ballad, 90 BPM
```

## Pronunciation Notes

| Word | Phonetic | Note |
| --- | --- | --- |
| lever | LEE-ver | British pronunciation |
"""

TRACK_FILE_WITH_HOMOGRAPH = """\
---
title: Track With Homograph
status: In Progress
explicit: false
---

## Lyrics Box

```
[Verse 1]
I read the book last night
Walking down the road
```

## Style Box

```
pop rock, 110 BPM
```
"""

TRACK_FILE_LONG_LYRICS = """\
---
title: Track With Long Lyrics
status: In Progress
explicit: false
---

## Lyrics Box

```
[Verse 1]
""" + "\n".join(f"Line number {i} with some extra words to pad it out more" for i in range(120)) + """
```

## Style Box

```
epic orchestral, 100 BPM
```
"""

TRACK_FILE_EMPTY_STYLE = """\
---
title: Track Empty Style
status: In Progress
explicit: false
---

## Lyrics Box

```
[Verse 1]
Walking down the road tonight
Stars are shining bright
```

## Style Box

```
```
"""


# =============================================================================
# Tests for _check_pre_gen_gates_for_track
# =============================================================================


class TestGate1SourcesVerified:
    """Gate 1: Sources Verified."""

    def test_sources_pending_fails(self):
        t_data = {"sources_verified": "Pending", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        source_gate = next(g for g in gates if g["gate"] == "Sources Verified")
        assert source_gate["status"] == "FAIL"
        assert source_gate["severity"] == "BLOCKING"
        assert blocking >= 1

    def test_sources_na_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        source_gate = next(g for g in gates if g["gate"] == "Sources Verified")
        assert source_gate["status"] == "PASS"

    def test_sources_verified_passes(self):
        t_data = {"sources_verified": "Verified (2025-05-01)", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        source_gate = next(g for g in gates if g["gate"] == "Sources Verified")
        assert source_gate["status"] == "PASS"


class TestGate2LyricsReviewed:
    """Gate 2: Lyrics Reviewed."""

    def test_empty_lyrics_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_EMPTY_LYRICS, blocklist=[],
        )
        lyrics_gate = next(g for g in gates if g["gate"] == "Lyrics Reviewed")
        assert lyrics_gate["status"] == "FAIL"
        assert "empty" in lyrics_gate["detail"].lower()

    def test_todo_in_lyrics_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_WITH_TODO, blocklist=[],
        )
        lyrics_gate = next(g for g in gates if g["gate"] == "Lyrics Reviewed")
        assert lyrics_gate["status"] == "FAIL"
        assert "TODO" in lyrics_gate["detail"] or "PLACEHOLDER" in lyrics_gate["detail"]

    def test_populated_lyrics_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        lyrics_gate = next(g for g in gates if g["gate"] == "Lyrics Reviewed")
        assert lyrics_gate["status"] == "PASS"

    def test_no_file_text_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, None, blocklist=[],
        )
        lyrics_gate = next(g for g in gates if g["gate"] == "Lyrics Reviewed")
        assert lyrics_gate["status"] == "FAIL"


class TestGate3PronunciationResolved:
    """Gate 3: Pronunciation Resolved."""

    def test_applied_pronunciation_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_WITH_PRONUNCIATION, blocklist=[],
        )
        pron_gate = next(g for g in gates if g["gate"] == "Pronunciation Resolved")
        assert pron_gate["status"] == "PASS"
        assert "1 entries applied" in pron_gate["detail"]

    def test_unapplied_pronunciation_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_UNAPPLIED_PRONUNCIATION, blocklist=[],
        )
        pron_gate = next(g for g in gates if g["gate"] == "Pronunciation Resolved")
        assert pron_gate["status"] == "FAIL"
        assert "lever" in pron_gate["detail"]

    def test_no_pronunciation_entries_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        pron_gate = next(g for g in gates if g["gate"] == "Pronunciation Resolved")
        assert pron_gate["status"] == "PASS"
        assert "No pronunciation entries" in pron_gate["detail"]

    def test_no_file_text_skips(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, None, blocklist=[],
        )
        pron_gate = next(g for g in gates if g["gate"] == "Pronunciation Resolved")
        assert pron_gate["status"] == "SKIP"


class TestGate4ExplicitFlagSet:
    """Gate 4: Explicit Flag Set."""

    def test_explicit_none_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": None}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        explicit_gate = next(g for g in gates if g["gate"] == "Explicit Flag Set")
        assert explicit_gate["status"] == "FAIL"
        assert explicit_gate["severity"] == "BLOCKING"

    def test_explicit_false_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        explicit_gate = next(g for g in gates if g["gate"] == "Explicit Flag Set")
        assert explicit_gate["status"] == "PASS"
        assert "No" in explicit_gate["detail"]

    def test_explicit_true_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": True}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        explicit_gate = next(g for g in gates if g["gate"] == "Explicit Flag Set")
        assert explicit_gate["status"] == "PASS"
        assert "Yes" in explicit_gate["detail"]


class TestGate5StylePromptComplete:
    """Gate 5: Style Prompt Complete."""

    def test_empty_style_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_EMPTY_STYLE, blocklist=[],
        )
        style_gate = next(g for g in gates if g["gate"] == "Style Prompt Complete")
        assert style_gate["status"] == "FAIL"
        assert "empty" in style_gate["detail"].lower()

    def test_populated_style_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        style_gate = next(g for g in gates if g["gate"] == "Style Prompt Complete")
        assert style_gate["status"] == "PASS"


class TestGate6ArtistNamesCleared:
    """Gate 6: Artist Names Cleared."""

    def test_no_blocklist_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        artist_gate = next(g for g in gates if g["gate"] == "Artist Names Cleared")
        assert artist_gate["status"] == "PASS"

    def test_blocked_artist_in_style_fails(self):
        """When a blocked artist name appears in the style prompt, gate fails."""
        t_data = {"sources_verified": "N/A", "explicit": False}

        # Build a track file with an artist name in the style box
        file_text = """\
## Lyrics Box

```
[Verse 1]
Hello world
```

## Style Box

```
in the style of Drake, upbeat hip-hop
```
"""
        # Set up the blocklist pattern cache manually
        blocklist = [{"name": "Drake", "alternative": "moody rap", "genre": "hip-hop"}]
        _text_analysis_mod._artist_blocklist_patterns = {
            "Drake": re.compile(r'\bDrake\b', re.IGNORECASE),
        }

        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, file_text, blocklist=blocklist,
        )
        artist_gate = next(g for g in gates if g["gate"] == "Artist Names Cleared")
        assert artist_gate["status"] == "FAIL"
        assert "Drake" in artist_gate["detail"]

    def test_no_blocked_artists_passes(self):
        """When style prompt has no blocked names, gate passes."""
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocklist = [{"name": "Drake", "alternative": "moody rap", "genre": "hip-hop"}]
        _text_analysis_mod._artist_blocklist_patterns = {
            "Drake": re.compile(r'\bDrake\b', re.IGNORECASE),
        }

        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=blocklist,
        )
        artist_gate = next(g for g in gates if g["gate"] == "Artist Names Cleared")
        assert artist_gate["status"] == "PASS"

    def test_no_style_content_skips(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_EMPTY_STYLE, blocklist=[],
        )
        artist_gate = next(g for g in gates if g["gate"] == "Artist Names Cleared")
        assert artist_gate["status"] == "SKIP"


class TestGate7HomographCheck:
    """Gate 7: Homograph Check."""

    def test_homograph_in_lyrics_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_WITH_HOMOGRAPH, blocklist=[],
        )
        homo_gate = next(g for g in gates if g["gate"] == "Homograph Check")
        assert homo_gate["status"] == "FAIL"
        assert "read" in homo_gate["detail"].lower()

    def test_no_homographs_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        homo_gate = next(g for g in gates if g["gate"] == "Homograph Check")
        assert homo_gate["status"] == "PASS"

    def test_no_lyrics_skips(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_EMPTY_LYRICS, blocklist=[],
        )
        homo_gate = next(g for g in gates if g["gate"] == "Homograph Check")
        assert homo_gate["status"] == "SKIP"


class TestGate8LyricLength:
    """Gate 8: Lyric Length."""

    def test_under_limit_passes(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        length_gate = next(g for g in gates if g["gate"] == "Lyric Length")
        assert length_gate["status"] == "PASS"

    def test_over_limit_fails(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_LONG_LYRICS, blocklist=[], max_lyric_words=100,
        )
        length_gate = next(g for g in gates if g["gate"] == "Lyric Length")
        assert length_gate["status"] == "FAIL"
        assert "limit" in length_gate["detail"].lower()

    def test_custom_limit(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[], max_lyric_words=5,
        )
        length_gate = next(g for g in gates if g["gate"] == "Lyric Length")
        assert length_gate["status"] == "FAIL"

    def test_no_lyrics_skips(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_EMPTY_LYRICS, blocklist=[],
        )
        length_gate = next(g for g in gates if g["gate"] == "Lyric Length")
        assert length_gate["status"] == "SKIP"


# =============================================================================
# Tests for blocking count aggregation
# =============================================================================


class TestBlockingAggregation:
    """Test that blocking counts are correct across all gates."""

    def test_all_gates_pass_zero_blocking(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        assert blocking == 0

    def test_multiple_failures_accumulate(self):
        """Track with sources pending + no explicit flag = at least 2 blocking."""
        t_data = {"sources_verified": "Pending", "explicit": None}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        assert blocking >= 2

    def test_returns_eight_gates(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, TRACK_FILE_COMPLETE, blocklist=[],
        )
        assert len(gates) == 8


# =============================================================================
# Tests for run_pre_generation_gates (MCP tool handler)
# =============================================================================


class TestRunPreGenerationGates:
    """Tests for the run_pre_generation_gates async handler."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        self._mock_cache = MockStateCache()
        _shared_mod.cache = self._mock_cache

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache

    def test_album_not_found(self):
        result = json.loads(_run(_gates_mod.run_pre_generation_gates("nonexistent")))
        assert result["found"] is False
        assert "not found" in result["error"].lower()

    def test_single_track_ready(self):
        """A track with all gates passing returns READY verdict."""
        with patch("pathlib.Path.read_text", return_value=TRACK_FILE_COMPLETE), \
             patch.object(_text_analysis_mod, "_load_artist_blocklist", return_value=[]):
            result = json.loads(_run(
                _gates_mod.run_pre_generation_gates("test-album", "01-first-track")
            ))
        assert result["found"] is True
        assert result["total_tracks"] == 1
        assert result["tracks"][0]["verdict"] == "READY"
        assert result["album_verdict"] == "READY"

    def test_single_track_not_ready(self):
        """A track with pending sources returns NOT READY."""
        with patch("pathlib.Path.read_text", return_value=TRACK_FILE_COMPLETE), \
             patch.object(_text_analysis_mod, "_load_artist_blocklist", return_value=[]):
            result = json.loads(_run(
                _gates_mod.run_pre_generation_gates("test-album", "02-second-track")
            ))
        assert result["found"] is True
        assert result["tracks"][0]["verdict"] == "NOT READY"
        assert result["total_blocking"] >= 1

    def test_all_tracks_mixed_verdict(self):
        """Album with mixed pass/fail tracks returns PARTIAL."""
        with patch("pathlib.Path.read_text", return_value=TRACK_FILE_COMPLETE), \
             patch.object(_text_analysis_mod, "_load_artist_blocklist", return_value=[]):
            result = json.loads(_run(
                _gates_mod.run_pre_generation_gates("test-album")
            ))
        assert result["found"] is True
        assert result["total_tracks"] == 2
        # Track 02 has sources_verified=Pending and explicit=None, so NOT READY
        # Track 01 should be READY
        verdicts = {t["track_slug"]: t["verdict"] for t in result["tracks"]}
        assert verdicts["01-first-track"] == "READY"
        assert verdicts["02-second-track"] == "NOT READY"
        assert result["album_verdict"] == "PARTIAL"

    def test_all_tracks_ready_verdict(self):
        """Album where all tracks pass returns ALL READY."""
        state = _fresh_state()
        # Make both tracks pass all gates
        for slug in state["albums"]["test-album"]["tracks"]:
            state["albums"]["test-album"]["tracks"][slug]["sources_verified"] = "N/A"
            state["albums"]["test-album"]["tracks"][slug]["explicit"] = False
        self._mock_cache._state = state

        with patch("pathlib.Path.read_text", return_value=TRACK_FILE_COMPLETE), \
             patch.object(_text_analysis_mod, "_load_artist_blocklist", return_value=[]):
            result = json.loads(_run(
                _gates_mod.run_pre_generation_gates("test-album")
            ))
        assert result["album_verdict"] == "ALL READY"

    def test_all_tracks_not_ready_verdict(self):
        """Album where all tracks fail returns NOT READY."""
        state = _fresh_state()
        for slug in state["albums"]["test-album"]["tracks"]:
            state["albums"]["test-album"]["tracks"][slug]["sources_verified"] = "Pending"
            state["albums"]["test-album"]["tracks"][slug]["explicit"] = None
        self._mock_cache._state = state

        with patch("pathlib.Path.read_text", return_value=TRACK_FILE_COMPLETE), \
             patch.object(_text_analysis_mod, "_load_artist_blocklist", return_value=[]):
            result = json.loads(_run(
                _gates_mod.run_pre_generation_gates("test-album")
            ))
        assert result["album_verdict"] == "NOT READY"

    def test_track_not_found(self):
        result = json.loads(_run(
            _gates_mod.run_pre_generation_gates("test-album", "99-nonexistent")
        ))
        assert result["found"] is False

    def test_configurable_max_lyric_words(self):
        """max_lyric_words from config.generation is respected."""
        state = _fresh_state()
        state["config"]["generation"] = {"max_lyric_words": 5}
        self._mock_cache._state = state

        with patch("pathlib.Path.read_text", return_value=TRACK_FILE_COMPLETE), \
             patch.object(_text_analysis_mod, "_load_artist_blocklist", return_value=[]):
            result = json.loads(_run(
                _gates_mod.run_pre_generation_gates("test-album", "01-first-track")
            ))
        # With max_lyric_words=5, the lyrics should exceed it
        gates = result["tracks"][0]["gates"]
        length_gate = next(g for g in gates if g["gate"] == "Lyric Length")
        assert length_gate["status"] == "FAIL"
