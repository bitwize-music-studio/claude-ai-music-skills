#!/usr/bin/env python3
"""
Unit tests for v0.83.0 server features:
- Instrumental track support (gate skipping, field sync)
- Guided regeneration workflow (approval detection, status behavior)
- Album status management (auto-advancement, dual status flows)

Split from test_server.py due to file size limits.

Usage:
    python -m pytest tests/unit/state/test_server_features.py -v
"""

import asyncio
import contextlib
import copy
import importlib
import importlib.util
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Import server module from hyphenated directory via importlib.
# Same mock setup as test_server.py — the server requires mcp.server.fastmcp
# which may not be installed in the test environment.
# ---------------------------------------------------------------------------

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

try:
    import mcp.server.fastmcp  # noqa: F401
except ImportError:

    class _FakeFastMCP:
        def __init__(self, name="", **kwargs):
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
    """Import the server module from the hyphenated directory."""
    spec = importlib.util.spec_from_file_location("state_server_features", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

# Handler modules for mock targeting
from handlers import text_analysis as _text_analysis_mod
from handlers import _shared as _shared_mod
from handlers import status as _status_mod
from handlers import gates as _gates_mod
from handlers import generation as _generation_mod


@contextlib.contextmanager
def _patch_write_state(mock=None):
    """Patch write_state where the handlers look it up (#679 item 11).

    No handler calls ``server.write_state``: core, album_fields and generation
    bind ``tools.state.indexer.write_state`` when imported, and status,
    streaming, rename and the mastering stages import it from the indexer as
    they run, so ``patch.object(server, "write_state")`` intercepted none of
    them. This patches every name they use, with one mock.
    """
    import tools.state.indexer as indexer_mod
    from handlers import album_fields, core, generation

    mock = MagicMock() if mock is None else mock
    with patch.object(indexer_mod, "write_state", mock), \
         patch.object(core, "write_state", mock), \
         patch.object(album_fields, "write_state", mock), \
         patch.object(generation, "write_state", mock):
        yield mock


# ---------------------------------------------------------------------------
# Shared helpers (duplicated from test_server.py to keep files independent)
# ---------------------------------------------------------------------------

SAMPLE_STATE = {
    "version": 2,
    "generated_at": "2025-01-01T00:00:00Z",
    "config": {
        "content_root": "/tmp/test",
        "audio_root": "/tmp/test/audio",
        "documents_root": "/tmp/test/docs",
        "overrides_dir": "/tmp/test/overrides",
        "artist_name": "test-artist",
        "config_mtime": 1234567890.0,
    },
    "albums": {
        "test-album": {
            "path": "/tmp/test/artists/test-artist/albums/electronic/test-album",
            "genre": "electronic",
            "title": "Test Album",
            "status": "In Progress",
            "explicit": False,
            "release_date": None,
            "track_count": 2,
            "tracks_completed": 1,
            "readme_mtime": 1234567890.0,
            "tracks": {
                "01-first-track": {
                    "path": "/tmp/test/.../01-first-track.md",
                    "title": "First Track",
                    "status": "Final",
                    "explicit": False,
                    "has_suno_link": True,
                    "sources_verified": "N/A",
                    "mtime": 1234567890.0,
                },
                "02-second-track": {
                    "path": "/tmp/test/.../02-second-track.md",
                    "title": "Second Track",
                    "status": "In Progress",
                    "explicit": True,
                    "has_suno_link": False,
                    "sources_verified": "Pending",
                    "mtime": 1234567891.0,
                },
            },
        },
    },
    "ideas": {
        "file_mtime": 1234567890.0,
        "counts": {"Pending": 2, "In Progress": 1},
        "items": [
            {"title": "Cool Idea", "genre": "rock", "status": "Pending"},
        ],
    },
    "session": {
        "last_album": "test-album",
        "last_track": "01-first-track",
        "last_phase": "Writing",
        "pending_actions": [],
        "updated_at": "2025-01-01T00:00:00Z",
    },
}


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _fresh_state():
    """Return a deep copy of sample state so tests don't interfere."""
    return copy.deepcopy(SAMPLE_STATE)


class MockStateCache:
    """A mock StateCache that holds state in memory without filesystem I/O."""

    def __init__(self, state=None):
        self._state = state if state is not None else _fresh_state()
        self._rebuild_called = False

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}

    def rebuild(self):
        self._rebuild_called = True
        return self._state

    def update_session(self, **kwargs):
        if not self._state:
            return {"error": "No state available"}
        session = copy.deepcopy(self._state.get("session", {}))
        if kwargs.get("clear"):
            session = {
                "last_album": None,
                "last_track": None,
                "last_phase": None,
                "pending_actions": [],
                "updated_at": None,
            }
        else:
            if kwargs.get("album") is not None:
                session["last_album"] = kwargs["album"]
            if kwargs.get("track") is not None:
                session["last_track"] = kwargs["track"]
            if kwargs.get("phase") is not None:
                session["last_phase"] = kwargs["phase"]
            if kwargs.get("action"):
                actions = session.get("pending_actions", [])
                actions.append(kwargs["action"])
                session["pending_actions"] = actions
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._state["session"] = session
        return session


# ---------------------------------------------------------------------------
# Sample markdown content
# ---------------------------------------------------------------------------

_SAMPLE_ALBUM_README = """\
---
title: "Test Album"
genres: ["electronic"]
explicit: false
---

# Test Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Artist** | test-artist |
| **Album** | Test Album |
| **Genre** | Electronic |
| **Tracks** | 2 |
| **Status** | In Progress |
| **Explicit** | No |
| **Concept** | A concept album |

## Tracklist

| # | Title | Status |
|---|-------|--------|
| 1 | First | Final |
| 2 | Second | In Progress |
"""

# A track file that passes all 8 pre-generation gates
_TRACK_ALL_GATES_PASS = """\
# Test Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Explicit** | No |
| **Sources Verified** | Verified (2026-01-01) |

## Suno Inputs

### Style Box
```
electronic, 120 BPM, energetic, male vocals, synth-driven
```

### Exclude Styles
```
[exclusions, if any]
```

### Lyrics Box
```
[Verse 1]
Testing one two three
This is a test for me

[Chorus]
We're testing all day long
Testing in this song
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| — | — | — |
"""

# An instrumental track file — no lyrics, section tags only
_INSTRUMENTAL_TRACK = """\
---
title: "Ambient Flow"
track_number: 3
instrumental: true
explicit: false
suno_url: ""
---

# Ambient Flow

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 03 |
| **Title** | Ambient Flow |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
| **Instrumental** | Yes |
| **Sources Verified** | N/A |

## Suno Inputs

### Style Box
```
ambient electronic, 90 BPM, atmospheric, synth pads, ethereal
```

### Lyrics Box
```
[Intro]

[Main Theme]

[Bridge]

[Outro]

[End]
```

## Pronunciation Notes

| Word/Phrase | Pronunciation | Reason |
|-------------|---------------|--------|
| — | — | — |
"""

# Instrumental track with mismatched table value
_INSTRUMENTAL_MISMATCH_FM_TRUE_TABLE_NO = """\
---
title: "Mismatch Track"
track_number: 4
instrumental: true
explicit: false
---

# Mismatch Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 04 |
| **Title** | Mismatch Track |
| **Status** | In Progress |
| **Instrumental** | No |
| **Explicit** | No |
"""

_INSTRUMENTAL_MISMATCH_FM_FALSE_TABLE_YES = """\
---
title: "Mismatch Track 2"
track_number: 5
instrumental: false
explicit: false
---

# Mismatch Track 2

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 05 |
| **Title** | Mismatch Track 2 |
| **Status** | In Progress |
| **Instrumental** | Yes |
| **Explicit** | No |
"""

_INSTRUMENTAL_BOTH_AGREE_YES = """\
---
title: "Consistent Track"
track_number: 6
instrumental: true
explicit: false
---

# Consistent Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Track #** | 06 |
| **Title** | Consistent Track |
| **Status** | In Progress |
| **Instrumental** | Yes |
| **Explicit** | No |
"""

# Track file with a Generation Log section containing a checkmark
_TRACK_WITH_GENERATION_LOG_APPROVED = """\
# Approved Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Generated |
| **Explicit** | No |

## Generation Log

| # | Date | Model | Result | Notes | Rating |
|---|------|-------|--------|-------|--------|
| 1 | 2026-03-01 | v6 | [Listen](https://suno.com/song/8a7d6c5b-4e3f-4a2b-9c1d-0e9f8a7b6c5d) | Wrong tempo | — |
| 2 | 2026-03-02 | v6 | [Listen](https://suno.com/song/3f0e9a52-1c2b-4c1d-9a1e-2b5f7a1c9d00) | Perfect | ✓ |
"""

# Track file with a Generation Log section WITHOUT a checkmark
_TRACK_WITH_GENERATION_LOG_UNAPPROVED = """\
# Unapproved Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Generated |
| **Explicit** | No |

## Generation Log

| # | Date | Model | Result | Notes | Rating |
|---|------|-------|--------|-------|--------|
| 1 | 2026-03-01 | v6 | [Listen](https://suno.com/song/8a7d6c5b-4e3f-4a2b-9c1d-0e9f8a7b6c5d) | Wrong tempo | — |
| 2 | 2026-03-02 | v6 | [Listen](https://suno.com/song/3f0e9a52-1c2b-4c1d-9a1e-2b5f7a1c9d00) | Still not right | — |
"""


# =============================================================================
# TestInstrumentalGateSkipping
# =============================================================================


@pytest.mark.unit
class TestInstrumentalGateSkipping:
    """Tests for pre-generation gate behavior with instrumental tracks.

    Instrumental tracks (instrumental: true in frontmatter) should have
    lyrics-dependent gates (2, 3, 4) skipped since they have no sung lyrics.
    Gates 1 (Sources), 5 (Style), 6 (Artist Names) still apply.
    """

    def _make_cache_with_track(self, tmp_path, track_content, **overrides):
        """Create a mock cache with a track file."""
        track_file = tmp_path / "03-instrumental.md"
        track_file.write_text(track_content)
        track_data = {
            "path": str(track_file),
            "title": "Instrumental Track",
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "mtime": 1234567890.0,
        }
        track_data.update(overrides)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["03-instrumental"] = track_data
        return MockStateCache(state), track_file

    def test_all_gates_run_for_non_instrumental_track(self, tmp_path):
        """All 8 gates run for a non-instrumental track."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _TRACK_ALL_GATES_PASS, sources_verified="Verified"
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_text_analysis_mod, "_artist_blocklist_cache", None):
            result = json.loads(_run(
                server.run_pre_generation_gates("test-album", "03")
            ))
        assert result["found"] is True
        track = result["tracks"][0]
        gates = track["gates"]
        gate_names = [g["gate"] for g in gates]
        # 8 core gates + 3 advisory (Style Box Descriptor Count, Performance Cues, Generation Settings)
        assert len(gates) == 11
        assert "Sources Verified" in gate_names
        assert "Lyrics Reviewed" in gate_names
        assert "Pronunciation Resolved" in gate_names
        assert "Explicit Flag Set" in gate_names
        assert "Style Prompt Complete" in gate_names
        assert "Artist Names Cleared" in gate_names
        assert "Homograph Check" in gate_names
        assert "Lyric Length" in gate_names
        assert "Style Box Descriptor Count" in gate_names
        assert "Performance Cues" in gate_names

    def test_gates_run_for_instrumental_track(self, tmp_path):
        """Gates still run for instrumental tracks (current behavior).

        With the instrumental track's section-tag-only lyrics, certain gates
        may produce different results but should still execute.
        """
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _INSTRUMENTAL_TRACK, sources_verified="N/A"
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_text_analysis_mod, "_artist_blocklist_cache", None):
            result = json.loads(_run(
                server.run_pre_generation_gates("test-album", "03")
            ))
        assert result["found"] is True
        track = result["tracks"][0]
        gates = track["gates"]
        # All gates still run; Performance Cues SKIPs for instrumental tracks.
        # 8 core gates + 3 advisory (Style Box Descriptor Count, Performance Cues, Generation Settings)
        assert len(gates) == 11

    def test_instrumental_track_style_gate_still_runs(self, tmp_path):
        """Gate 5 (Style Prompt) still runs for instrumental tracks."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _INSTRUMENTAL_TRACK, sources_verified="N/A"
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_text_analysis_mod, "_artist_blocklist_cache", None):
            result = json.loads(_run(
                server.run_pre_generation_gates("test-album", "03")
            ))
        gates = {g["gate"]: g for g in result["tracks"][0]["gates"]}
        # Style Box has content, so gate 5 should PASS
        assert gates["Style Prompt Complete"]["status"] == "PASS"

    def test_instrumental_track_sources_gate_still_runs(self, tmp_path):
        """Gate 1 (Sources Verified) still runs for instrumental tracks."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _INSTRUMENTAL_TRACK, sources_verified="Pending"
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_text_analysis_mod, "_artist_blocklist_cache", None):
            result = json.loads(_run(
                server.run_pre_generation_gates("test-album", "03")
            ))
        gates = {g["gate"]: g for g in result["tracks"][0]["gates"]}
        # Sources Pending should FAIL gate 1
        assert gates["Sources Verified"]["status"] == "FAIL"

    def test_instrumental_track_artist_names_gate_still_runs(self, tmp_path):
        """Gate 6 (Artist Names Cleared) still runs for instrumental tracks."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _INSTRUMENTAL_TRACK, sources_verified="N/A"
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_text_analysis_mod, "_artist_blocklist_cache", None):
            result = json.loads(_run(
                server.run_pre_generation_gates("test-album", "03")
            ))
        gates = {g["gate"]: g for g in result["tracks"][0]["gates"]}
        assert gates["Artist Names Cleared"]["status"] == "PASS"

    def test_instrumental_track_lyrics_gate_on_section_tags(self, tmp_path):
        """Gate 2 (Lyrics Reviewed) evaluates instrumental section tags.

        Instrumental tracks have section-tag-only lyrics ([Intro], [Main Theme],
        etc.). Gate 2 should PASS since the Lyrics Box is not empty and has no
        [TODO]/[PLACEHOLDER] markers.
        """
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _INSTRUMENTAL_TRACK, sources_verified="N/A"
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_text_analysis_mod, "_artist_blocklist_cache", None):
            result = json.loads(_run(
                server.run_pre_generation_gates("test-album", "03")
            ))
        gates = {g["gate"]: g for g in result["tracks"][0]["gates"]}
        # Lyrics Box has section tags, so not empty => PASS
        assert gates["Lyrics Reviewed"]["status"] == "PASS"

    def test_instrumental_explicit_flag_gate(self, tmp_path):
        """Gate 4 (Explicit Flag) runs for instrumental tracks too."""
        mock_cache, _ = self._make_cache_with_track(
            tmp_path, _INSTRUMENTAL_TRACK, sources_verified="N/A",
            explicit=False
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_text_analysis_mod, "_artist_blocklist_cache", None):
            result = json.loads(_run(
                server.run_pre_generation_gates("test-album", "03")
            ))
        gates = {g["gate"]: g for g in result["tracks"][0]["gates"]}
        assert gates["Explicit Flag Set"]["status"] == "PASS"


# =============================================================================
# TestInstrumentalFieldSync
# =============================================================================


@pytest.mark.unit
class TestInstrumentalFieldSync:
    """The `instrumental` flag lives in two places — frontmatter `instrumental:`
    and the Track Details `| **Instrumental** |` row — and must agree.

    #679 item 11: these tests used to check a copy of the parsing written in
    the test file, and claimed the pre-generation gates block a mismatch,
    which they did not. They now test the production code: generation's
    ``_instrumental_state`` (what get_generation_request uses) and the real
    pre-generation gates, which now block a mismatch as the
    pre-generation-check skill says.
    """

    def test_mismatch_frontmatter_true_table_no(self):
        instrumental, problem = _generation_mod._instrumental_state(
            _INSTRUMENTAL_MISMATCH_FM_TRUE_TABLE_NO)
        assert instrumental is False
        assert problem is not None
        assert problem["code"] == "instrumental_mismatch"
        assert problem["severity"] == "blocking"

    def test_mismatch_frontmatter_false_table_yes(self):
        _, problem = _generation_mod._instrumental_state(
            _INSTRUMENTAL_MISMATCH_FM_FALSE_TABLE_YES)
        assert problem is not None
        assert problem["code"] == "instrumental_mismatch"

    def test_no_mismatch_both_agree_yes(self):
        assert _generation_mod._instrumental_state(_INSTRUMENTAL_BOTH_AGREE_YES) == (True, None)

    def test_no_mismatch_only_frontmatter(self):
        content = """\
---
title: "Test"
instrumental: true
---

# Test

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
"""
        assert _generation_mod._instrumental_state(content) == (True, None)

    @pytest.mark.parametrize("text", [
        _INSTRUMENTAL_MISMATCH_FM_TRUE_TABLE_NO, _INSTRUMENTAL_MISMATCH_FM_FALSE_TABLE_YES,
    ], ids=["fm-true-table-no", "fm-false-table-yes"])
    def test_mismatch_is_blocking_in_pre_gen_gates(self, text):
        """The real gates block a mismatch, and run the lyrics gates rather
        than skip them as for an instrumental (no gate fails open)."""
        t_data = {"sources_verified": "N/A", "explicit": False}
        blocking, _, gates = _gates_mod._check_pre_gen_gates_for_track(t_data, text, [])
        by_name = {g["gate"]: g for g in gates}
        assert by_name["Instrumental Flags Agree"]["status"] == "FAIL"
        assert by_name["Instrumental Flags Agree"]["severity"] == "BLOCKING"
        assert by_name["Lyrics Reviewed"]["status"] != "SKIP"
        assert blocking >= 1

    def test_agreeing_flags_add_no_gate(self):
        t_data = {"sources_verified": "N/A", "explicit": False}
        _, _, gates = _gates_mod._check_pre_gen_gates_for_track(
            t_data, _INSTRUMENTAL_BOTH_AGREE_YES, [])
        assert "Instrumental Flags Agree" not in {g["gate"] for g in gates}


# =============================================================================
# TestRegenerationWorkflow
# =============================================================================


@pytest.mark.unit
class TestRegenerationWorkflow:
    """Tests for the guided regeneration workflow.

    Key behaviors:
    - Generated tracks without checkmark in Generation Log Rating are unapproved
    - Generated tracks WITH checkmark are approved
    - Status stays Generated during regeneration (no backward transition)
    """

    # #679 item 11: these tests used their own Generation Log parser and a
    # column order the template never had. They now read the template's table
    # with production ``parse_generation_log`` (Rating is the last column).

    def test_detect_unapproved_generated_track(self):
        """Generated track without checkmark in Rating is detected as unapproved."""
        takes = _generation_mod.parse_generation_log(_TRACK_WITH_GENERATION_LOG_UNAPPROVED)
        assert [t["row"] for t in takes] == [1, 2]
        assert not any(t["approved"] for t in takes)

    def test_detect_approved_generated_track(self):
        """Generated track WITH checkmark in Rating is detected as approved."""
        takes = _generation_mod.parse_generation_log(_TRACK_WITH_GENERATION_LOG_APPROVED)
        assert [t["row"] for t in takes] == [1, 2]
        assert [t["approved"] for t in takes] == [False, True]
        assert takes[1]["clip_id"] == "3f0e9a52-1c2b-4c1d-9a1e-2b5f7a1c9d00"

    @pytest.mark.parametrize("fixture,allowed", [
        (_TRACK_WITH_GENERATION_LOG_APPROVED, True),
        (_TRACK_WITH_GENERATION_LOG_UNAPPROVED, False),
    ], ids=["approved", "unapproved"])
    def test_final_follows_the_keeper(self, tmp_path, fixture, allowed):
        """Generated → Final goes through only with a ✓ keeper (#679 item 3)."""
        track_file = tmp_path / "01-track.md"
        track_file.write_text(fixture)
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"]["01-track"] = {
            "path": str(track_file), "title": "Track", "status": "Generated",
            "explicit": False, "has_suno_link": True, "sources_verified": "N/A",
            "mtime": 1.0,
        }
        with patch.object(_shared_mod, "cache", MockStateCache(state)), \
             _patch_write_state():
            result = json.loads(_run(server.update_track_field(
                "test-album", "01-track", "status", "Final")))
        assert bool(result.get("success")) is allowed, result

    def test_status_stays_generated_during_regen_no_backward(self, tmp_path):
        """Status cannot go backward from Generated to In Progress.

        During regeneration, the status stays at Generated. The transition
        Generated -> In Progress is invalid (must use force to override).
        """
        err = _status_mod._validate_track_transition("Generated", "In Progress")
        assert err is not None
        assert "Invalid transition" in err

    def test_generated_to_final_is_valid(self):
        """Generated -> Final is the valid forward transition."""
        err = _status_mod._validate_track_transition("Generated", "Final")
        assert err is None

    def test_generated_to_not_started_blocked(self):
        """Generated -> Not Started is blocked (backward)."""
        err = _status_mod._validate_track_transition("Generated", "Not Started")
        assert err is not None
        assert "Invalid transition" in err

    def test_generated_to_sources_pending_blocked(self):
        """Generated -> Sources Pending is blocked (backward)."""
        err = _status_mod._validate_track_transition("Generated", "Sources Pending")
        assert err is not None

    def test_force_allows_backward_from_generated(self):
        """force=True allows backward transition from Generated."""
        err = _status_mod._validate_track_transition(
            "Generated", "In Progress", force=True
        )
        assert err is None

    def test_no_generation_log_means_not_approved(self):
        """Track without Generation Log section is not approved."""
        content = """\
# Track Without Log

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Generated |
"""
        assert _generation_mod.parse_generation_log(content) == []


# =============================================================================
# TestAlbumAutoAdvancement
# =============================================================================


@pytest.mark.unit
class TestAlbumAutoAdvancement:
    """Tests for album status auto-advancement logic.

    Key behaviors:
    - Album advances Research Complete -> Sources Verified when all tracks verified
    - Album does NOT advance when some tracks still pending
    - Non-documentary albums skip Research Complete and Sources Verified
    - Marking all Generated tracks as Final advances album to Complete
    """

    def _make_cache_with_album(self, tmp_path, album_status, track_statuses,
                               has_sources_md=False, sources=None, research_file=None):
        """Create a mock cache with specific album/track statuses.

        Each track's ``sources_verified`` comes from *sources* ({slug: value}),
        else N/A. It used to be derived from the track's status, which hid that
        the album gate read the status instead of the field (#679 item 6).
        """
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_SAMPLE_ALBUM_README.replace(
            "| **Status** | In Progress |", f"| **Status** | {album_status} |"
        ))
        if has_sources_md:
            (tmp_path / "SOURCES.md").write_text("# Sources\n")
        if research_file:
            (tmp_path / research_file).write_text("# Research\n")
        sources = sources or {}

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["status"] = album_status
        state["albums"]["test-album"]["tracks"] = {
            slug: {
                "path": "/tmp/test/track.md",
                "title": slug,
                "status": status,
                "explicit": False,
                "has_suno_link": status in ("Generated", "Final"),
                "sources_verified": sources.get(slug, "N/A"),
                "mtime": 1234567890.0,
            }
            for slug, status in track_statuses.items()
        }
        return MockStateCache(state), readme_path

    def test_research_complete_to_sources_verified_all_verified(self, tmp_path):
        """Album advances Research Complete -> Sources Verified when all tracks verified."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "Research Complete",
            {
                "01-track": "Sources Verified",
                "02-track": "Sources Verified",
            },
            sources={"01-track": "Verified (2026-01-01)", "02-track": "✅ Verified"},
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Sources Verified"
            )))
        assert result["success"] is True
        assert result["new_status"] == "Sources Verified"

    def test_verified_track_still_at_sources_pending_does_not_block(self, tmp_path):
        """#679 item 6: verify-sources sets the field; the track's status may
        still say Sources Pending. The album advances anyway."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "Research Complete",
            {"01-track": "Sources Pending", "02-track": "Sources Verified"},
            sources={"01-track": "Verified (2026-01-01)", "02-track": "Verified (2026-01-01)"},
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Sources Verified")))
        assert result["success"] is True

    def test_in_progress_track_with_pending_sources_blocks(self, tmp_path):
        """#679 item 6: an In Progress track whose sources are pending blocks."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "Research Complete",
            {"01-track": "In Progress", "02-track": "Sources Verified"},
            sources={"01-track": "❌ Pending", "02-track": "Verified (2026-01-01)"},
        )
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Sources Verified")))
        assert "still unverified" in result["error"]
        assert "01-track" in result["error"]

    def test_research_complete_to_sources_verified_blocked_pending(self, tmp_path):
        """Album does NOT advance when some tracks still pending verification."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "Research Complete",
            {
                "01-track": "Sources Verified",
                "02-track": "Sources Pending",
            }
        )
        # The field decides (#679 item 6): 01 verified, 02 pending.
        tracks = mock_cache._state["albums"]["test-album"]["tracks"]
        tracks["01-track"]["sources_verified"] = "Verified (2026-01-01)"
        tracks["02-track"]["sources_verified"] = "Pending"
        tracks["02-track"]["status"] = "Sources Pending"

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Sources Verified"
            )))
        assert "error" in result
        assert "still unverified" in result["error"]
        assert "02-track" in result["error"]

    def test_non_documentary_album_skips_research_statuses(self, tmp_path):
        """Non-documentary albums can go Concept -> In Progress directly."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "Concept",
            {
                "01-track": "In Progress",
                "02-track": "Not Started",
            },
            has_sources_md=False,  # No SOURCES.md = non-documentary
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "In Progress"
            )))
        assert result["success"] is True
        assert result["new_status"] == "In Progress"

    def test_documentary_album_cannot_skip_research_statuses(self, tmp_path):
        """Documentary albums (with SOURCES.md) cannot skip Concept -> In Progress."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "Concept",
            {
                "01-track": "In Progress",
            },
            has_sources_md=True,  # Has SOURCES.md = documentary
        )
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "In Progress"
            )))
        assert "error" in result
        assert "SOURCES.md" in result["error"]

    def test_album_with_only_research_md_is_documentary(self, tmp_path):
        """#679 item 6: RESEARCH.md alone makes an album documentary, the same
        test create_track uses (_album_keeps_research); it used to count only
        SOURCES.md."""
        mock_cache, readme = self._make_cache_with_album(
            tmp_path, "Concept", {"01-track": "In Progress"}, research_file="RESEARCH.md",
        )
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "In Progress")))
        assert "error" in result
        assert "keeps research" in result["error"]
        assert "| **Status** | Concept |" in readme.read_text()

    def test_batch_approve_all_final_advances_to_complete(self, tmp_path):
        """When all tracks are Final, album can advance to Complete."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "In Progress",
            {
                "01-track": "Final",
                "02-track": "Final",
                "03-track": "Final",
            }
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Complete"
            )))
        assert result["success"] is True

    def test_complete_blocked_while_a_track_is_generated(self, tmp_path):
        """#679 item 4: this test was named "all final" with a Generated track
        and passed; Complete means every track Final (status-tracking.md)."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "In Progress",
            {
                "01-track": "Final",
                "02-track": "Final",
                "03-track": "Generated",
            }
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Complete"
            )))
        assert "not Final" in result["error"]
        assert "03-track" in result["error"]

    def test_complete_blocked_when_track_below_generated(self, tmp_path):
        """Album cannot advance to Complete when any track is below Generated."""
        mock_cache, _ = self._make_cache_with_album(
            tmp_path, "In Progress",
            {
                "01-track": "Final",
                "02-track": "In Progress",
            }
        )
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Complete"
            )))
        assert "error" in result
        assert "not Final" in result["error"]  # #679 item 4

    def test_album_transition_validation_direct(self):
        """Test _validate_album_transition directly for transition rules."""
        # Valid transitions
        assert _status_mod._validate_album_transition("Concept", "Research Complete") is None
        assert _status_mod._validate_album_transition("Concept", "In Progress") is None
        assert _status_mod._validate_album_transition("Research Complete", "Sources Verified") is None
        assert _status_mod._validate_album_transition("Sources Verified", "In Progress") is None
        assert _status_mod._validate_album_transition("In Progress", "Complete") is None
        assert _status_mod._validate_album_transition("Complete", "Released") is None

        # Invalid transitions
        assert _status_mod._validate_album_transition("Concept", "Complete") is not None
        assert _status_mod._validate_album_transition("Concept", "Released") is not None
        assert _status_mod._validate_album_transition("In Progress", "Concept") is not None
        assert _status_mod._validate_album_transition("Released", "Concept") is not None

    def test_released_is_terminal(self):
        """Released is a terminal status — no further transitions allowed."""
        err = _status_mod._validate_album_transition("Released", "Complete")
        assert err is not None
        assert "none (terminal)" in err

    def test_consistency_check_in_progress_needs_active_track(self):
        """Album In Progress requires at least one track past Not Started."""
        album = {
            "tracks": {
                "01-track": {"status": "Not Started"},
                "02-track": {"status": "Not Started"},
            }
        }
        err = _status_mod._check_album_track_consistency(album, "In Progress")
        assert err is not None
        assert "all tracks are still" in err

    def test_consistency_check_complete_needs_all_final(self):
        """Album Complete requires all tracks Final (#679 item 4: was
        "Generated or Final")."""
        for other in ("In Progress", "Generated"):
            album = {
                "tracks": {
                    "01-track": {"status": "Final"},
                    "02-track": {"status": other},
                }
            }
            err = _status_mod._check_album_track_consistency(album, "Complete")
            assert err is not None, other
            assert "not Final" in err
        album = {"tracks": {"01-track": {"status": "Final"}, "02-track": {"status": "Final"}}}
        assert _status_mod._check_album_track_consistency(album, "Complete") is None

    def test_consistency_check_released_needs_all_final(self):
        """Album Released requires all tracks at Final."""
        album = {
            "tracks": {
                "01-track": {"status": "Final"},
                "02-track": {"status": "Generated"},
            }
        }
        err = _status_mod._check_album_track_consistency(album, "Released")
        assert err is not None
        assert "not Final" in err

    def test_consistency_check_passes_for_early_statuses(self):
        """Early statuses (Concept, Research Complete) have no track requirements."""
        album = {
            "tracks": {
                "01-track": {"status": "Not Started"},
            }
        }
        assert _status_mod._check_album_track_consistency(album, "Concept") is None
        assert _status_mod._check_album_track_consistency(album, "Research Complete") is None
        assert _status_mod._check_album_track_consistency(album, "Sources Verified") is None

    def test_consistency_check_empty_album_passes(self):
        """Empty albums (no tracks) pass consistency check at any level."""
        album = {"tracks": {}}
        assert _status_mod._check_album_track_consistency(album, "In Progress") is None
        assert _status_mod._check_album_track_consistency(album, "Complete") is None
        assert _status_mod._check_album_track_consistency(album, "Released") is None


# =============================================================================
# TestExplicitFlagSync
# =============================================================================


@pytest.mark.unit
class TestExplicitFlagSync:
    """Tests for explicit flag consistency at release.

    If any track is explicit, the album must be marked explicit.
    This is checked in the release readiness gate (update_album_status → Released).
    """

    def _make_release_ready_cache(self, tmp_path, album_explicit, track_explicit_flags):
        """Create a cache with a Complete album ready for release attempt.

        Args:
            album_explicit: Album-level explicit flag (bool)
            track_explicit_flags: Dict of {slug: bool} for track explicit flags
        """
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_SAMPLE_ALBUM_README.replace(
            "| **Status** | In Progress |", "| **Status** | Complete |"
        ))

        # Create track files with streaming lyrics so that gate passes
        tracks_dir = tmp_path / "tracks"
        tracks_dir.mkdir(exist_ok=True)

        state = _fresh_state()
        state["albums"]["test-album"]["path"] = str(tmp_path)
        state["albums"]["test-album"]["status"] = "Complete"
        state["albums"]["test-album"]["explicit"] = album_explicit
        # Released requires a release_date (#679 item 7)
        state["albums"]["test-album"]["release_date"] = "2026-03-01"
        state["config"]["audio_root"] = str(tmp_path / "audio")

        tracks = {}
        for slug, is_explicit in track_explicit_flags.items():
            track_path = tracks_dir / f"{slug}.md"
            track_path.write_text(
                f"---\ntitle: {slug}\nstatus: Final\nexplicit: {str(is_explicit).lower()}\n---\n\n"
                "## Streaming Lyrics\n\n```\nSome lyrics that are long enough to pass the word count "
                "check and have enough words in them for validation\n```\n"
            )
            tracks[slug] = {
                "path": str(track_path),
                "title": slug,
                "status": "Final",
                "explicit": is_explicit,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            }

        state["albums"]["test-album"]["tracks"] = tracks

        # Create audio dirs so audio/mastered checks pass
        audio_dir = (
            tmp_path / "audio" / "artists" / "test-artist" / "albums"
            / "electronic" / "test-album"
        )
        mastered_dir = audio_dir / "mastered"
        mastered_dir.mkdir(parents=True)
        # Dummy WAV files
        (audio_dir / "01-track.wav").write_bytes(b"\x00" * 100)
        (mastered_dir / "01-track.wav").write_bytes(b"\x00" * 100)
        # Album art
        (audio_dir / "album.png").write_bytes(b"\x00" * 100)

        return MockStateCache(state)

    def test_explicit_track_in_non_explicit_album_blocked(self, tmp_path):
        """Release blocked when track is explicit but album is not."""
        mock_cache = self._make_release_ready_cache(
            tmp_path,
            album_explicit=False,
            track_explicit_flags={"01-track": True, "02-track": False},
        )
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.update_album_status(
                "test-album", "Released"
            )))
        assert "error" in result
        assert any("explicit" in issue.lower() for issue in result["issues"])

    def test_all_explicit_tracks_in_explicit_album_passes(self, tmp_path):
        """Release allowed when album and tracks are both explicit."""
        mock_cache = self._make_release_ready_cache(
            tmp_path,
            album_explicit=True,
            track_explicit_flags={"01-track": True, "02-track": True},
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Released"
            )))
        assert "error" not in result

    def test_no_explicit_tracks_passes(self, tmp_path):
        """Release allowed when no tracks are explicit and album is not explicit."""
        mock_cache = self._make_release_ready_cache(
            tmp_path,
            album_explicit=False,
            track_explicit_flags={"01-track": False, "02-track": False},
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Released"
            )))
        assert "error" not in result

    def test_explicit_album_with_no_explicit_tracks_allowed(self, tmp_path):
        """Album marked explicit with no explicit tracks is allowed (conservative)."""
        mock_cache = self._make_release_ready_cache(
            tmp_path,
            album_explicit=True,
            track_explicit_flags={"01-track": False, "02-track": False},
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Released"
            )))
        assert "error" not in result

    def test_force_overrides_explicit_mismatch(self, tmp_path):
        """force=True bypasses explicit flag check."""
        mock_cache = self._make_release_ready_cache(
            tmp_path,
            album_explicit=False,
            track_explicit_flags={"01-track": True},
        )
        with patch.object(_shared_mod, "cache", mock_cache), \
             _patch_write_state():
            result = json.loads(_run(server.update_album_status(
                "test-album", "Released", force=True
            )))
        assert "error" not in result
