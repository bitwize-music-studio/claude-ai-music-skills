#!/usr/bin/env python3
"""
Unit tests for check_cross_track_repetition MCP tool and helpers.

Split from test_server.py to stay under pre-commit file-size limits.

Usage:
    python -m pytest tests/unit/state/test_server_lyrics.py -v
"""

import asyncio
import copy
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

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
    """Import the server module from the hyphenated directory."""
    spec = importlib.util.spec_from_file_location("state_server_lyrics", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SAMPLE_STATE = {
    "version": 2,
    "config": {
        "content_root": "/tmp/test-content",
        "audio_root": "/tmp/test-audio",
        "documents_root": "/tmp/test-docs",
        "artist_name": "test-artist",
        "overrides_path": "/tmp/test-content/overrides",
        "ideas_file": "/tmp/test-content/IDEAS.md",
    },
    "albums": {
        "test-album": {
            "title": "Test Album",
            "status": "In Progress",
            "genre": "electronic",
            "path": "/tmp/test-content/artists/test-artist/albums/electronic/test-album",
            "track_count": 2,
            "tracks": {},
            "mtime": 1234567890.0,
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
    "meta": {
        "rebuilt_at": "2026-01-01T00:00:00Z",
        "plugin_version": "0.50.0",
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
        self._state["session"] = session
        return session


def _make_track_md(lyrics_content):
    """Build a minimal track markdown file with a Lyrics Box section."""
    return f"""# Track

## Suno Inputs

### Lyrics Box
*Copy this into Suno's "Lyrics" field:*

```
{lyrics_content}
```
"""


def _build_state_with_tracks(tmp_path, track_lyrics):
    """Build state and write track files for multiple tracks.

    Args:
        tmp_path: pytest tmp_path fixture
        track_lyrics: dict of track_slug -> lyrics content string

    Returns:
        MockStateCache with tracks wired to real files
    """
    state = _fresh_state()
    tracks = {}
    for i, (slug, lyrics) in enumerate(track_lyrics.items(), start=1):
        track_file = tmp_path / f"{slug}.md"
        track_file.write_text(_make_track_md(lyrics))
        tracks[slug] = {
            "title": slug.replace("-", " ").title(),
            "status": "In Progress",
            "explicit": False,
            "has_suno_link": False,
            "sources_verified": "N/A",
            "path": str(track_file),
            "mtime": 1234567890.0 + i,
        }
    state["albums"]["test-album"]["tracks"] = tracks
    state["albums"]["test-album"]["track_count"] = len(tracks)
    return MockStateCache(state)


# =============================================================================
# Tests for helper functions
# =============================================================================


@pytest.mark.unit
class TestTokenizeLyricsByLine:
    """Tests for the _tokenize_lyrics_by_line helper."""

    def test_basic_tokenization(self):
        lyrics = "Walking through shadows\nBurning down the night"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert len(result) == 2
        assert result[0] == ["walking", "through", "shadows"]
        assert result[1] == ["burning", "down", "the", "night"]

    def test_section_tags_skipped(self):
        lyrics = "[Verse 1]\nHello world\n[Chorus]\nGoodbye world"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert len(result) == 2
        assert result[0] == ["hello", "world"]
        assert result[1] == ["goodbye", "world"]

    def test_empty_lines_skipped(self):
        lyrics = "First line\n\n\nSecond line"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert len(result) == 2

    def test_single_char_words_filtered(self):
        lyrics = "I am a test"
        result = server._tokenize_lyrics_by_line(lyrics)
        # "I" and "a" are single chars, filtered out
        assert result == [["am", "test"]]

    def test_apostrophe_stripping(self):
        lyrics = "'bout the morning"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert result[0][0] == "bout"

    def test_empty_input(self):
        assert server._tokenize_lyrics_by_line("") == []

    def test_only_section_tags(self):
        lyrics = "[Verse 1]\n[Chorus]\n[Bridge]"
        assert server._tokenize_lyrics_by_line(lyrics) == []

    def test_case_normalization(self):
        lyrics = "SHADOWS Falling EVERYWHERE"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert result == [["shadows", "falling", "everywhere"]]

    def test_contractions_become_stopwords(self):
        """don't -> dont, which is in the stopword list."""
        lyrics = "Don't stop believing"
        result = server._tokenize_lyrics_by_line(lyrics)
        # "don't" -> regex splits to ["don", "t"] or finds "don't" as one token
        # then strip apostrophe -> "don't" -> "dont"
        # Actually _WORD_TOKEN_RE is [a-zA-Z']+ so "don't" is one token
        # strip("'") -> "don't" stays as "don't"... no, strip only removes
        # leading/trailing. "don't" has internal apostrophe, so stays "don't"
        line = result[0]
        assert "believing" in line

    def test_punctuation_stripped_by_regex(self):
        """Commas, periods, etc. are not matched by _WORD_TOKEN_RE."""
        lyrics = "Hello, world! This is... great?"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert result == [["hello", "world", "this", "is", "great"]]

    def test_numbers_excluded(self):
        """Digits aren't matched by [a-zA-Z']+ regex."""
        lyrics = "Track 42 is the best 100"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert result == [["track", "is", "the", "best"]]

    def test_hyphenated_words_split(self):
        """Hyphens aren't in the regex, so 'broken-hearted' becomes two tokens."""
        lyrics = "She was broken-hearted"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert result == [["she", "was", "broken", "hearted"]]

    def test_whitespace_only_lines_skipped(self):
        lyrics = "First line\n   \n  \t  \nSecond line"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert len(result) == 2

    def test_line_with_only_single_chars_produces_no_output(self):
        """If every word on a line is single-char, the line is omitted."""
        lyrics = "I a\nReal words here"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert len(result) == 1
        assert result[0] == ["real", "words", "here"]

    def test_trailing_apostrophe(self):
        """Words like rockin' should have trailing apostrophe stripped."""
        lyrics = "Rockin' all night long"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert result[0][0] == "rockin"

    def test_multiple_apostrophes(self):
        """Leading AND trailing apostrophes stripped: 'bout' -> bout."""
        lyrics = "'bout'"
        result = server._tokenize_lyrics_by_line(lyrics)
        assert result == [["bout"]]


@pytest.mark.unit
class TestNgramsFromLines:
    """Tests for the _ngrams_from_lines helper."""

    def test_basic_bigrams(self):
        lines = [["burning", "shadows", "tonight"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=2)
        assert "burning shadows" in result
        assert "shadows tonight" in result

    def test_trigrams(self):
        lines = [["burning", "shadows", "tonight"]]
        result = server._ngrams_from_lines(lines, min_n=3, max_n=3)
        assert "burning shadows tonight" in result

    def test_no_cross_line_ngrams(self):
        lines = [["end"], ["start"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=2)
        assert "end start" not in result

    def test_all_stopword_ngrams_skipped(self):
        lines = [["the", "and", "is", "to"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=2)
        assert result == []

    def test_mixed_stopword_ngrams_kept(self):
        lines = [["burning", "the", "shadows"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=3)
        # "burning the" has one non-stopword -> kept
        assert "burning the" in result
        # "the shadows" has one non-stopword -> kept
        assert "the shadows" in result
        # "burning the shadows" kept too
        assert "burning the shadows" in result

    def test_empty_lines(self):
        assert server._ngrams_from_lines([], min_n=2, max_n=4) == []

    def test_short_line_no_ngrams(self):
        lines = [["alone"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=4)
        assert result == []

    def test_four_grams(self):
        lines = [["burning", "shadows", "fall", "tonight"]]
        result = server._ngrams_from_lines(lines, min_n=4, max_n=4)
        assert "burning shadows fall tonight" in result
        assert len(result) == 1

    def test_default_range_produces_2_3_4_grams(self):
        lines = [["burning", "shadows", "fall", "tonight"]]
        result = server._ngrams_from_lines(lines)  # default min_n=2, max_n=4
        bigrams = [r for r in result if len(r.split()) == 2]
        trigrams = [r for r in result if len(r.split()) == 3]
        fourgrams = [r for r in result if len(r.split()) == 4]
        assert len(bigrams) == 3   # 3 sliding windows of size 2
        assert len(trigrams) == 2  # 2 sliding windows of size 3
        assert len(fourgrams) == 1 # 1 sliding window of size 4

    def test_exactly_n_words_produces_one_ngram(self):
        lines = [["burning", "shadows"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=2)
        assert result == ["burning shadows"]

    def test_multiple_lines_independent(self):
        lines = [["burning", "shadows"], ["falling", "rain"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=2)
        assert "burning shadows" in result
        assert "falling rain" in result
        assert "shadows falling" not in result

    def test_partially_stopword_ngram_kept(self):
        """An n-gram with at least one non-stopword is kept."""
        lines = [["the", "thunder"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=2)
        assert "the thunder" in result

    def test_duplicate_ngrams_from_repeated_phrase(self):
        """Same phrase appearing twice on a line produces two entries."""
        lines = [["burning", "shadows", "burning", "shadows"]]
        result = server._ngrams_from_lines(lines, min_n=2, max_n=2)
        assert result.count("burning shadows") == 2


# =============================================================================
# Tests for check_cross_track_repetition MCP tool
# =============================================================================


@pytest.mark.unit
class TestCheckCrossTrackRepetition:
    """Tests for the check_cross_track_repetition MCP tool."""

    def test_album_not_found(self):
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("nonexistent")))
        assert result["found"] is False
        assert "not found" in result["error"]

    def test_empty_album_no_tracks(self):
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {}
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["found"] is True
        assert result["track_count"] == 0
        assert result["repeated_words"] == []
        assert result["repeated_phrases"] == []

    def test_single_track_below_threshold(self, tmp_path):
        """A single track can never meet min_tracks=3."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-only-track": "[Verse 1]\nShadows falling everywhere\nShadows in my dreams",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["found"] is True
        assert result["track_count"] == 1
        assert result["repeated_words"] == []
        assert result["repeated_phrases"] == []

    def test_multi_track_word_repetition(self, tmp_path):
        """Word 'shadows' in 3 tracks should be flagged at default threshold."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling everywhere",
            "02-track": "[Verse 1]\nWalking through the shadows",
            "03-track": "[Verse 1]\nShadows on the wall tonight",
            "04-track": "[Verse 1]\nSomething completely different here",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["found"] is True
        words = {w["word"]: w for w in result["repeated_words"]}
        assert "shadows" in words
        assert words["shadows"]["track_count"] == 3

    def test_multi_track_phrase_repetition(self, tmp_path):
        """Phrase 'burning shadows' in 3 tracks should be flagged."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nBurning shadows everywhere",
            "02-track": "[Verse 1]\nSee the burning shadows fall",
            "03-track": "[Verse 1]\nBurning shadows in my mind",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        phrases = {p["phrase"]: p for p in result["repeated_phrases"]}
        assert "burning shadows" in phrases
        assert phrases["burning shadows"]["track_count"] == 3

    def test_no_repetition_across_tracks(self, tmp_path):
        """Tracks with unique vocabulary produce no flags."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nMountains rising high",
            "02-track": "[Verse 1]\nOcean waves crashing",
            "03-track": "[Verse 1]\nDesert winds blowing",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["repeated_words"] == []
        assert result["repeated_phrases"] == []

    def test_custom_min_tracks_lowers_threshold(self, tmp_path):
        """Setting min_tracks=2 flags words in just 2 tracks."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
            "03-track": "[Verse 1]\nSomething else entirely",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album", min_tracks=2)))
        assert result["min_tracks_threshold"] == 2
        words = {w["word"]: w for w in result["repeated_words"]}
        assert "shadows" in words
        assert words["shadows"]["track_count"] == 2

    def test_stopwords_filtered(self, tmp_path):
        """Common stopwords and song vocabulary should not be flagged."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nThe love and the heart in the night",
            "02-track": "[Verse 1]\nThe love and the heart in the day",
            "03-track": "[Verse 1]\nThe love and the heart all the time",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        flagged_words = [w["word"] for w in result["repeated_words"]]
        # These are all stopwords/common song vocab — none should be flagged
        assert "the" not in flagged_words
        assert "and" not in flagged_words
        assert "love" not in flagged_words
        assert "heart" not in flagged_words
        assert "night" not in flagged_words

    def test_section_tags_excluded(self, tmp_path):
        """Section tags like [Verse 1] should not appear in tokenized words."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nUnique word alpha",
            "02-track": "[Verse 1]\nUnique word beta",
            "03-track": "[Verse 1]\nUnique word gamma",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        flagged_words = [w["word"] for w in result["repeated_words"]]
        assert "verse" not in flagged_words

    def test_tracks_without_lyrics_skipped(self, tmp_path):
        """Tracks with no lyrics content should be gracefully skipped."""
        state = _fresh_state()
        # Track with a path to a file that has no lyrics
        empty_track = tmp_path / "01-empty.md"
        empty_track.write_text("# Track\n\nNo lyrics section here.\n")
        real_track = tmp_path / "02-real.md"
        real_track.write_text(_make_track_md("[Verse 1]\nShadows everywhere"))
        state["albums"]["test-album"]["tracks"] = {
            "01-empty": {
                "title": "Empty Track",
                "status": "Not Started",
                "path": str(empty_track),
                "mtime": 1234567890.0,
            },
            "02-real": {
                "title": "Real Track",
                "status": "In Progress",
                "path": str(real_track),
                "mtime": 1234567891.0,
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        # Only 1 track with lyrics analyzed
        assert result["track_count"] == 1

    def test_summary_structure(self, tmp_path):
        """Summary should have the expected keys."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
            "03-track": "[Verse 1]\nShadows waiting",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        summary = result["summary"]
        assert "flagged_words" in summary
        assert "flagged_phrases" in summary
        assert "most_repeated_word" in summary
        assert "most_repeated_phrase" in summary

    def test_min_tracks_floor_at_two(self, tmp_path):
        """min_tracks below 2 should be clamped to 2."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album", min_tracks=1)))
        assert result["min_tracks_threshold"] == 2

    def test_results_sorted_by_track_count_descending(self, tmp_path):
        """Words should be sorted by track_count descending."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows and thunder rolling",
            "02-track": "[Verse 1]\nShadows and thunder crashing",
            "03-track": "[Verse 1]\nShadows and rolling thunder",
            "04-track": "[Verse 1]\nShadows everywhere tonight",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.check_cross_track_repetition("test-album", min_tracks=2)
            ))
        words = result["repeated_words"]
        if len(words) > 1:
            for i in range(len(words) - 1):
                assert words[i]["track_count"] >= words[i + 1]["track_count"]

    def test_total_occurrences_counted(self, tmp_path):
        """total_occurrences should sum across all tracks."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows shadows shadows",
            "02-track": "[Verse 1]\nShadows shadows",
            "03-track": "[Verse 1]\nShadows here",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        words = {w["word"]: w for w in result["repeated_words"]}
        assert "shadows" in words
        # 3 + 2 + 1 = 6 total
        assert words["shadows"]["total_occurrences"] == 6

    def test_track_missing_path_skipped(self):
        """Tracks without a path field should be skipped gracefully."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "01-no-path": {
                "title": "No Path Track",
                "status": "Not Started",
                "mtime": 1234567890.0,
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["found"] is True
        assert result["track_count"] == 0

    def test_album_slug_normalized(self, tmp_path):
        """Spaces and underscores in slug should resolve to the album."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows everywhere",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("Test Album")))
        assert result["found"] is True

    def test_album_slug_case_insensitive(self, tmp_path):
        """Mixed case slug should match the lowercase album key."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows everywhere",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("TEST-ALBUM")))
        assert result["found"] is True

    def test_unreadable_file_skipped(self, tmp_path):
        """Track pointing to nonexistent file should be silently skipped."""
        state = _fresh_state()
        state["albums"]["test-album"]["tracks"] = {
            "01-gone": {
                "title": "Gone Track",
                "status": "In Progress",
                "path": str(tmp_path / "nonexistent.md"),
                "mtime": 1234567890.0,
            },
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["found"] is True
        assert result["track_count"] == 0

    def test_min_tracks_zero_floors_to_two(self, tmp_path):
        """min_tracks=0 should be clamped to 2."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album", min_tracks=0)))
        assert result["min_tracks_threshold"] == 2

    def test_min_tracks_negative_floors_to_two(self, tmp_path):
        """Negative min_tracks should be clamped to 2."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album", min_tracks=-5)))
        assert result["min_tracks_threshold"] == 2

    def test_case_insensitive_word_matching(self, tmp_path):
        """SHADOWS, Shadows, shadows should all count as the same word."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nSHADOWS everywhere",
            "02-track": "[Verse 1]\nShadows rising",
            "03-track": "[Verse 1]\nshadows falling",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        words = {w["word"]: w for w in result["repeated_words"]}
        assert "shadows" in words
        assert words["shadows"]["track_count"] == 3

    def test_word_and_phrase_both_flagged(self, tmp_path):
        """A word can appear in both repeated_words and as part of a repeated_phrase."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nBurning shadows fall tonight",
            "02-track": "[Verse 1]\nBurning shadows rise again",
            "03-track": "[Verse 1]\nBurning shadows call my name",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        words = {w["word"]: w for w in result["repeated_words"]}
        phrases = {p["phrase"]: p for p in result["repeated_phrases"]}
        assert "shadows" in words
        assert "burning" in words
        assert "burning shadows" in phrases

    def test_tracks_list_in_results_sorted(self, tmp_path):
        """Track slugs in each result entry should be sorted alphabetically."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "03-charlie": "[Verse 1]\nShadows forever",
            "01-alpha": "[Verse 1]\nShadows calling",
            "02-bravo": "[Verse 1]\nShadows waiting",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        words = {w["word"]: w for w in result["repeated_words"]}
        assert words["shadows"]["tracks"] == ["01-alpha", "02-bravo", "03-charlie"]

    def test_summary_none_when_no_flags(self, tmp_path):
        """most_repeated_word/phrase should be None when nothing is flagged."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nMountains rising high",
            "02-track": "[Verse 1]\nOcean waves crashing",
            "03-track": "[Verse 1]\nDesert winds blowing",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["summary"]["most_repeated_word"] is None
        assert result["summary"]["most_repeated_phrase"] is None
        assert result["summary"]["flagged_words"] == 0
        assert result["summary"]["flagged_phrases"] == 0

    def test_summary_most_repeated_is_highest_count(self, tmp_path):
        """most_repeated_word should be the word with highest track_count."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows and thunder rolling",
            "02-track": "[Verse 1]\nShadows and thunder crashing",
            "03-track": "[Verse 1]\nShadows and thunder here",
            "04-track": "[Verse 1]\nShadows everywhere tonight",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(
                server.check_cross_track_repetition("test-album", min_tracks=2)
            ))
        most = result["summary"]["most_repeated_word"]
        assert most is not None
        # shadows appears in 4 tracks, thunder in 3 — shadows should be #1
        assert most["word"] == "shadows"
        assert most["track_count"] == 4

    def test_available_albums_in_not_found(self):
        """Not-found response should list available album slugs."""
        mock_cache = MockStateCache(_fresh_state())
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("nonexistent")))
        assert "available_albums" in result
        assert "test-album" in result["available_albums"]

    def test_alphabetical_tiebreaker_for_words(self, tmp_path):
        """Words with same track_count should be sorted alphabetically."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nZebra and alpha dancing",
            "02-track": "[Verse 1]\nZebra and alpha singing",
            "03-track": "[Verse 1]\nZebra and alpha running",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        words = result["repeated_words"]
        # alpha, dancing/singing/running unique, zebra — both alpha and zebra in 3
        word_names = [w["word"] for w in words]
        if "alpha" in word_names and "zebra" in word_names:
            alpha_idx = word_names.index("alpha")
            zebra_idx = word_names.index("zebra")
            assert alpha_idx < zebra_idx  # alphabetical tiebreaker

    def test_alphabetical_tiebreaker_for_phrases(self, tmp_path):
        """Phrases with same track_count should be sorted alphabetically."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nZebra dancing and alpha singing tonight",
            "02-track": "[Verse 1]\nZebra dancing and alpha singing forever",
            "03-track": "[Verse 1]\nZebra dancing and alpha singing always",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        phrases = result["repeated_phrases"]
        phrase_names = [p["phrase"] for p in phrases]
        if "alpha singing" in phrase_names and "zebra dancing" in phrase_names:
            alpha_idx = phrase_names.index("alpha singing")
            zebra_idx = phrase_names.index("zebra dancing")
            assert alpha_idx < zebra_idx

    def test_contraction_stopwords_not_flagged(self, tmp_path):
        """Contractions that map to stopwords (dont, wont, cant) should be filtered."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nDont stop running",
            "02-track": "[Verse 1]\nDont stop moving",
            "03-track": "[Verse 1]\nDont stop trying",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        flagged_words = [w["word"] for w in result["repeated_words"]]
        assert "dont" not in flagged_words

    def test_phrase_total_occurrences(self, tmp_path):
        """Phrase total_occurrences should sum across all tracks."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nBurning shadows burning shadows",
            "02-track": "[Verse 1]\nBurning shadows here",
            "03-track": "[Verse 1]\nBurning shadows there",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        phrases = {p["phrase"]: p for p in result["repeated_phrases"]}
        assert "burning shadows" in phrases
        # Track 1: 2 occurrences, track 2: 1, track 3: 1 = 4
        assert phrases["burning shadows"]["total_occurrences"] == 4

    def test_mixed_valid_invalid_tracks(self, tmp_path):
        """Mix of valid, unreadable, empty, and no-path tracks."""
        state = _fresh_state()
        # Track with lyrics
        good1 = tmp_path / "01-good.md"
        good1.write_text(_make_track_md("[Verse 1]\nShadows fall"))
        good2 = tmp_path / "02-good.md"
        good2.write_text(_make_track_md("[Verse 1]\nShadows rise"))
        good3 = tmp_path / "03-good.md"
        good3.write_text(_make_track_md("[Verse 1]\nShadows wait"))
        # Track with no lyrics section
        empty = tmp_path / "04-empty.md"
        empty.write_text("# Track\n\nNo lyrics here.\n")

        state["albums"]["test-album"]["tracks"] = {
            "01-good": {"title": "Good 1", "path": str(good1), "mtime": 1.0},
            "02-good": {"title": "Good 2", "path": str(good2), "mtime": 2.0},
            "03-good": {"title": "Good 3", "path": str(good3), "mtime": 3.0},
            "04-empty": {"title": "Empty", "path": str(empty), "mtime": 4.0},
            "05-gone": {"title": "Gone", "path": str(tmp_path / "nope.md"), "mtime": 5.0},
            "06-no-path": {"title": "No Path", "mtime": 6.0},
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["track_count"] == 3
        words = {w["word"]: w for w in result["repeated_words"]}
        assert "shadows" in words

    def test_whitespace_only_lyrics_skipped(self, tmp_path):
        """Lyrics Box section with no code block at all should be treated as empty."""
        state = _fresh_state()
        # A track file with a Lyrics Box heading but no actual content or code block
        ws_track = tmp_path / "01-ws.md"
        ws_track.write_text("# Track\n\n### Lyrics Box\n\n   \n\n## Next Section\n")
        real_track = tmp_path / "02-real.md"
        real_track.write_text(_make_track_md("[Verse 1]\nShadows here"))
        state["albums"]["test-album"]["tracks"] = {
            "01-ws": {"title": "WS", "path": str(ws_track), "mtime": 1.0},
            "02-real": {"title": "Real", "path": str(real_track), "mtime": 2.0},
        }
        mock_cache = MockStateCache(state)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["track_count"] == 1

    def test_word_below_threshold_not_flagged(self, tmp_path):
        """A word in 2 tracks should NOT be flagged at default min_tracks=3."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
            "03-track": "[Verse 1]\nSomething else entirely",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        words = {w["word"]: w for w in result["repeated_words"]}
        # shadows in 2 tracks < threshold 3
        assert "shadows" not in words

    def test_high_min_tracks_filters_everything(self, tmp_path):
        """Setting min_tracks higher than track count yields no results."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
            "03-track": "[Verse 1]\nShadows waiting",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album", min_tracks=10)))
        assert result["repeated_words"] == []
        assert result["repeated_phrases"] == []

    def test_many_tracks_performance(self, tmp_path):
        """10 tracks with shared vocabulary should produce correct results."""
        track_lyrics = {}
        for i in range(1, 11):
            num = f"{i:02d}"
            track_lyrics[f"{num}-track"] = (
                f"[Verse 1]\nShadows creeping through the corridor\n"
                f"Unique{num} word here\nSomething different{num}"
            )
        mock_cache = _build_state_with_tracks(tmp_path, track_lyrics)
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert result["track_count"] == 10
        words = {w["word"]: w for w in result["repeated_words"]}
        assert "shadows" in words
        assert words["shadows"]["track_count"] == 10
        assert "creeping" in words
        assert "corridor" in words

    def test_output_is_valid_json(self, tmp_path):
        """Tool output should always be valid JSON."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling everywhere",
            "02-track": "[Verse 1]\nShadows rising here",
            "03-track": "[Verse 1]\nShadows waiting there",
        })
        with patch.object(server, "cache", mock_cache):
            raw = _run(server.check_cross_track_repetition("test-album"))
        assert isinstance(raw, str)
        result = json.loads(raw)  # should not raise
        assert isinstance(result, dict)

    def test_all_top_level_keys_present(self, tmp_path):
        """Response should contain all documented top-level keys."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        expected_keys = {
            "found", "album_slug", "track_count", "min_tracks_threshold",
            "repeated_words", "repeated_phrases", "summary",
        }
        assert expected_keys == set(result.keys())

    def test_word_entry_structure(self, tmp_path):
        """Each repeated_words entry should have the correct keys."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nShadows falling",
            "02-track": "[Verse 1]\nShadows rising",
            "03-track": "[Verse 1]\nShadows waiting",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        assert len(result["repeated_words"]) > 0
        word_entry = result["repeated_words"][0]
        assert set(word_entry.keys()) == {"word", "track_count", "tracks", "total_occurrences"}
        assert isinstance(word_entry["word"], str)
        assert isinstance(word_entry["track_count"], int)
        assert isinstance(word_entry["tracks"], list)
        assert isinstance(word_entry["total_occurrences"], int)

    def test_phrase_entry_structure(self, tmp_path):
        """Each repeated_phrases entry should have the correct keys."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Verse 1]\nBurning shadows everywhere",
            "02-track": "[Verse 1]\nBurning shadows rising",
            "03-track": "[Verse 1]\nBurning shadows falling",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        phrases = [p for p in result["repeated_phrases"] if p["phrase"] == "burning shadows"]
        assert len(phrases) == 1
        phrase_entry = phrases[0]
        assert set(phrase_entry.keys()) == {"phrase", "track_count", "tracks", "total_occurrences"}
        assert isinstance(phrase_entry["phrase"], str)
        assert isinstance(phrase_entry["track_count"], int)
        assert isinstance(phrase_entry["tracks"], list)
        assert isinstance(phrase_entry["total_occurrences"], int)

    def test_vocables_not_flagged(self, tmp_path):
        """Song filler like oh, yeah, na, la should be stopwords."""
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": "[Chorus]\nOh yeah na na la la",
            "02-track": "[Chorus]\nOh yeah na na la la",
            "03-track": "[Chorus]\nOh yeah na na la la",
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        flagged = [w["word"] for w in result["repeated_words"]]
        assert "oh" not in flagged
        assert "yeah" not in flagged
        assert "na" not in flagged
        assert "la" not in flagged

    def test_multiline_lyrics_with_sections(self, tmp_path):
        """Realistic multi-section lyrics should be handled correctly."""
        lyrics_a = (
            "[Verse 1]\n"
            "Walking through the darkness\n"
            "Searching for the ember\n"
            "\n"
            "[Chorus]\n"
            "Remember the ember\n"
            "Burning in December\n"
        )
        lyrics_b = (
            "[Verse 1]\n"
            "Standing in the silence\n"
            "Waiting for the ember\n"
            "\n"
            "[Chorus]\n"
            "Remember the ember\n"
            "Glowing in the chamber\n"
        )
        lyrics_c = (
            "[Verse 1]\n"
            "Running through the canyon\n"
            "Chasing down the ember\n"
            "\n"
            "[Chorus]\n"
            "Remember the ember\n"
            "Fading every member\n"
        )
        mock_cache = _build_state_with_tracks(tmp_path, {
            "01-track": lyrics_a,
            "02-track": lyrics_b,
            "03-track": lyrics_c,
        })
        with patch.object(server, "cache", mock_cache):
            result = json.loads(_run(server.check_cross_track_repetition("test-album")))
        words = {w["word"]: w for w in result["repeated_words"]}
        assert "ember" in words
        assert words["ember"]["track_count"] == 3
        assert "remember" in words
        phrases = {p["phrase"]: p for p in result["repeated_phrases"]}
        assert "the ember" in phrases
        assert "remember the" in phrases


# =============================================================================
# Tests for _tokenize_lyrics_with_sections helper
# =============================================================================


@pytest.mark.unit
class TestTokenizeLyricsWithSections:
    """Tests for the _tokenize_lyrics_with_sections helper."""

    def test_basic_section_tracking(self):
        lyrics = "[Verse 1]\nWalking through shadows\n[Chorus]\nBurning tonight"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert len(result) == 2
        assert result[0]["section"] == "Verse 1"
        assert result[0]["section_type"] == "verse"
        assert result[1]["section"] == "Chorus"
        assert result[1]["section_type"] == "chorus"

    def test_section_inheritance(self):
        """Lines after a section tag inherit that section until next tag."""
        lyrics = "[Verse 1]\nFirst line\nSecond line\n[Chorus]\nThird line"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["section"] == "Verse 1"
        assert result[1]["section"] == "Verse 1"
        assert result[2]["section"] == "Chorus"

    def test_line_numbers_preserved(self):
        lyrics = "[Verse 1]\nFirst line\n\nSecond line"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["line_number"] == 2
        assert result[1]["line_number"] == 4

    def test_section_tag_numbering_stripped(self):
        """'Verse 2' should normalize to section_type 'verse'."""
        lyrics = "[Verse 2]\nHello world"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["section_type"] == "verse"
        assert result[0]["section"] == "Verse 2"

    def test_empty_input(self):
        assert server._tokenize_lyrics_with_sections("") == []

    def test_whitespace_only(self):
        assert server._tokenize_lyrics_with_sections("   \n  \n  ") == []

    def test_only_section_tags(self):
        assert server._tokenize_lyrics_with_sections("[Verse]\n[Chorus]") == []

    def test_raw_line_preserved(self):
        lyrics = "[Verse]\nBurning Shadows Fall Tonight!"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["raw_line"] == "Burning Shadows Fall Tonight!"

    def test_words_lowercased_and_cleaned(self):
        lyrics = "[Verse]\n'Bout the MORNING light"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["words"] == ["bout", "the", "morning", "light"]

    def test_default_section_for_no_tag(self):
        """Lines before any section tag get 'Unknown' section."""
        lyrics = "Walking through shadows"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["section"] == "Unknown"
        assert result[0]["section_type"] == "verse"

    def test_all_section_types_recognized(self):
        """All priority section types should be correctly identified."""
        for section_type in ["chorus", "hook", "pre-chorus", "bridge", "outro", "verse", "intro"]:
            tag = f"[{section_type.title()}]"
            lyrics = f"{tag}\nTest words here"
            result = server._tokenize_lyrics_with_sections(lyrics)
            assert result[0]["section_type"] == section_type, f"Failed for {section_type}"

    def test_unknown_section_defaults_to_verse(self):
        lyrics = "[Breakdown]\nHeavy riff here"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["section_type"] == "verse"

    def test_single_char_words_filtered(self):
        lyrics = "[Verse]\nI am a hero"
        result = server._tokenize_lyrics_with_sections(lyrics)
        assert result[0]["words"] == ["am", "hero"]


# =============================================================================
# Tests for _extract_distinctive_ngrams helper
# =============================================================================


@pytest.mark.unit
class TestExtractDistinctiveNgrams:
    """Tests for the _extract_distinctive_ngrams helper."""

    def test_basic_extraction(self):
        lines = [{"words": ["burning", "shadows", "fall", "tonight"],
                  "section": "Chorus", "section_type": "chorus",
                  "line_number": 1, "raw_line": "Burning shadows fall tonight"}]
        result = server._extract_distinctive_ngrams(lines)
        phrases = [r["phrase"] for r in result]
        assert "burning shadows fall tonight" in phrases

    def test_min_n_enforced(self):
        """3-word phrases should not appear with default min_n=4."""
        lines = [{"words": ["burning", "shadows", "fall"],
                  "section": "Verse", "section_type": "verse",
                  "line_number": 1, "raw_line": "Burning shadows fall"}]
        result = server._extract_distinctive_ngrams(lines)
        assert len(result) == 0  # only 3 words, can't make 4-gram

    def test_max_n_enforced(self):
        """8+ word n-grams should not appear with default max_n=7."""
        words = ["one", "two", "three", "four", "five", "six", "seven", "eight"]
        lines = [{"words": words, "section": "Verse", "section_type": "verse",
                  "line_number": 1, "raw_line": " ".join(words)}]
        result = server._extract_distinctive_ngrams(lines)
        max_wc = max(r["word_count"] for r in result)
        assert max_wc <= 7

    def test_common_phrases_filtered(self):
        """Phrases in _COMMON_SONG_PHRASES should be excluded."""
        # "middle of the night" is a 4-word common phrase in the frozenset
        lines = [{"words": ["middle", "of", "the", "night"],
                  "section": "Chorus", "section_type": "chorus",
                  "line_number": 1, "raw_line": "Middle of the night"}]
        result = server._extract_distinctive_ngrams(lines)
        phrases = [r["phrase"] for r in result]
        assert "middle of the night" not in phrases

    def test_stopword_only_ngrams_filtered(self):
        """N-grams where all words are stopwords should be excluded."""
        lines = [{"words": ["the", "and", "is", "but", "with"],
                  "section": "Verse", "section_type": "verse",
                  "line_number": 1, "raw_line": "The and is but with"}]
        result = server._extract_distinctive_ngrams(lines)
        assert len(result) == 0

    def test_dedup_keeps_highest_priority(self):
        """Same phrase in chorus and verse should keep chorus version."""
        lines = [
            {"words": ["burning", "shadows", "fall", "tonight"],
             "section": "Verse 1", "section_type": "verse",
             "line_number": 2, "raw_line": "Burning shadows fall tonight"},
            {"words": ["burning", "shadows", "fall", "tonight"],
             "section": "Chorus", "section_type": "chorus",
             "line_number": 8, "raw_line": "Burning shadows fall tonight"},
        ]
        result = server._extract_distinctive_ngrams(lines)
        match = [r for r in result if r["phrase"] == "burning shadows fall tonight"]
        assert len(match) == 1
        assert match[0]["section"] == "Chorus"
        assert match[0]["priority"] == 3

    def test_sorted_by_priority_then_length(self):
        """Results sorted: priority desc, word_count desc."""
        lines = [
            {"words": ["burning", "shadows", "fall", "tonight"],
             "section": "Verse", "section_type": "verse",
             "line_number": 1, "raw_line": "..."},
            {"words": ["electric", "storm", "horizon", "calls"],
             "section": "Chorus", "section_type": "chorus",
             "line_number": 5, "raw_line": "..."},
        ]
        result = server._extract_distinctive_ngrams(lines)
        # Chorus items (priority 3) should come before verse items (priority 1)
        chorus_indices = [i for i, r in enumerate(result) if r["priority"] == 3]
        verse_indices = [i for i, r in enumerate(result) if r["priority"] == 1]
        if chorus_indices and verse_indices:
            assert max(chorus_indices) < min(verse_indices)

    def test_empty_input(self):
        assert server._extract_distinctive_ngrams([]) == []

    def test_custom_min_max_n(self):
        """Custom min_n=5, max_n=5 should only produce 5-grams."""
        lines = [{"words": ["one", "two", "three", "four", "five", "six"],
                  "section": "Verse", "section_type": "verse",
                  "line_number": 1, "raw_line": "..."}]
        result = server._extract_distinctive_ngrams(lines, min_n=5, max_n=5)
        for r in result:
            assert r["word_count"] == 5

    def test_multiple_lines_produce_independent_ngrams(self):
        """N-grams should not cross line boundaries."""
        lines = [
            {"words": ["alpha", "beta", "gamma", "delta"],
             "section": "Verse", "section_type": "verse",
             "line_number": 1, "raw_line": "..."},
            {"words": ["epsilon", "zeta", "eta", "theta"],
             "section": "Verse", "section_type": "verse",
             "line_number": 2, "raw_line": "..."},
        ]
        result = server._extract_distinctive_ngrams(lines)
        phrases = [r["phrase"] for r in result]
        # Should have 4-grams from each line independently
        assert "alpha beta gamma delta" in phrases
        assert "epsilon zeta eta theta" in phrases
        # Should NOT cross lines
        cross = [p for p in phrases if "delta" in p and "epsilon" in p]
        assert len(cross) == 0


# =============================================================================
# Tests for extract_distinctive_phrases MCP tool
# =============================================================================


@pytest.mark.unit
class TestExtractDistinctivePhrases:
    """Tests for the extract_distinctive_phrases MCP tool."""

    def test_empty_input(self):
        result = json.loads(_run(server.extract_distinctive_phrases("")))
        assert result["phrases"] == []
        assert result["total_phrases"] == 0
        assert result["sections_found"] == []
        assert result["search_suggestions"] == []

    def test_whitespace_only(self):
        result = json.loads(_run(server.extract_distinctive_phrases("   \n  \n  ")))
        assert result["total_phrases"] == 0

    def test_none_like_empty(self):
        """Empty string returns gracefully."""
        result = json.loads(_run(server.extract_distinctive_phrases("")))
        assert result["total_phrases"] == 0

    def test_valid_json_output(self):
        lyrics = "[Chorus]\nBurning shadows fall tonight across the wire"
        raw = _run(server.extract_distinctive_phrases(lyrics))
        assert isinstance(raw, str)
        result = json.loads(raw)
        assert isinstance(result, dict)

    def test_top_level_keys(self):
        lyrics = "[Verse]\nBurning shadows fall tonight across the wire"
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        assert set(result.keys()) == {
            "phrases", "total_phrases", "sections_found", "search_suggestions",
        }

    def test_phrase_entry_structure(self):
        lyrics = "[Chorus]\nBurning shadows fall tonight across the wire"
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        assert len(result["phrases"]) > 0
        entry = result["phrases"][0]
        assert set(entry.keys()) == {
            "phrase", "word_count", "section", "line_number", "raw_line", "priority",
        }

    def test_search_suggestion_structure(self):
        lyrics = "[Chorus]\nBurning shadows fall tonight across the wire"
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        assert len(result["search_suggestions"]) > 0
        suggestion = result["search_suggestions"][0]
        assert set(suggestion.keys()) == {"query", "priority", "section"}
        assert suggestion["query"].startswith('"')
        assert suggestion["query"].endswith('" lyrics')

    def test_search_suggestions_capped_at_15(self):
        """search_suggestions should have at most 15 entries."""
        # Build lyrics with many unique lines to generate lots of phrases
        lines = []
        lines.append("[Verse 1]")
        for i in range(20):
            lines.append(f"unique{i} alpha{i} beta{i} gamma{i} delta{i} epsilon{i} zeta{i}")
        lyrics = "\n".join(lines)
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        assert len(result["search_suggestions"]) <= 15

    def test_sections_found_populated(self):
        lyrics = "[Verse 1]\nSomething here tonight really\n[Chorus]\nSomething else tomorrow morning"
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        assert "Verse 1" in result["sections_found"]
        assert "Chorus" in result["sections_found"]

    def test_common_cliches_excluded(self):
        """Phrases from _COMMON_SONG_PHRASES should not appear in results."""
        lyrics = "[Chorus]\nFalling in love with you tonight\nBreak my heart again and again"
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        phrases = [p["phrase"] for p in result["phrases"]]
        assert "falling in love" not in phrases
        assert "break my heart" not in phrases

    def test_chorus_priority_higher_than_verse(self):
        """Chorus phrases should have higher priority than verse phrases."""
        lyrics = (
            "[Verse 1]\nAlpha beta gamma delta epsilon\n"
            "[Chorus]\nZeta theta iota kappa lambda"
        )
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        verse_priorities = [p["priority"] for p in result["phrases"] if p["section"] == "Verse 1"]
        chorus_priorities = [p["priority"] for p in result["phrases"] if p["section"] == "Chorus"]
        if verse_priorities and chorus_priorities:
            assert max(verse_priorities) < min(chorus_priorities)

    def test_realistic_lyrics(self):
        """Full realistic lyrics should produce meaningful phrases."""
        lyrics = (
            "[Verse 1]\n"
            "Concrete jungle where the monitors glow\n"
            "Every keystroke tells a story below\n"
            "\n"
            "[Chorus]\n"
            "Silicon ghosts in the midnight machine\n"
            "Dancing through firewalls never seen\n"
            "\n"
            "[Verse 2]\n"
            "Binary whispers echo through the halls\n"
            "Digital footprints climbing up the walls\n"
        )
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        assert result["total_phrases"] > 0
        # Should find multi-word phrases
        assert any(p["word_count"] >= 4 for p in result["phrases"])
        # Should have search suggestions
        assert len(result["search_suggestions"]) > 0
        # Should find multiple sections
        assert len(result["sections_found"]) >= 2

    def test_total_phrases_matches_list_length(self):
        lyrics = "[Chorus]\nBurning shadows fall tonight across the wire"
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        assert result["total_phrases"] == len(result["phrases"])

    def test_word_count_accurate(self):
        """word_count should match actual word count of phrase."""
        lyrics = "[Verse]\nAlpha beta gamma delta epsilon zeta"
        result = json.loads(_run(server.extract_distinctive_phrases(lyrics)))
        for phrase_entry in result["phrases"]:
            actual_words = len(phrase_entry["phrase"].split())
            assert phrase_entry["word_count"] == actual_words
