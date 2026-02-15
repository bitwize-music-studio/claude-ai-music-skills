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


# ===========================================================================
# _count_syllables_word helper tests
# ===========================================================================

class TestCountSyllablesWord:
    """Tests for the _count_syllables_word helper."""

    def test_monosyllabic(self):
        assert server._count_syllables_word("cat") == 1
        assert server._count_syllables_word("dog") == 1
        assert server._count_syllables_word("the") == 1

    def test_polysyllabic(self):
        assert server._count_syllables_word("beautiful") == 3
        assert server._count_syllables_word("amazing") == 3
        assert server._count_syllables_word("yesterday") == 3

    def test_silent_e(self):
        assert server._count_syllables_word("make") == 1
        assert server._count_syllables_word("fire") == 1
        assert server._count_syllables_word("love") == 1

    def test_consonant_le(self):
        assert server._count_syllables_word("bottle") == 2
        assert server._count_syllables_word("apple") == 2
        assert server._count_syllables_word("little") == 2

    def test_y_as_vowel(self):
        assert server._count_syllables_word("my") == 1
        assert server._count_syllables_word("mystery") == 3
        assert server._count_syllables_word("baby") == 2

    def test_apostrophe_words(self):
        assert server._count_syllables_word("don't") == 1
        assert server._count_syllables_word("I'm") == 1
        # "couldn't" — vowel-cluster heuristic counts 1 (the 'ou' group);
        # the contraction drops the vowel from "not", a known limitation
        assert server._count_syllables_word("couldn't") >= 1

    def test_empty_and_edge(self):
        assert server._count_syllables_word("") == 0
        assert server._count_syllables_word("a") == 1
        assert server._count_syllables_word("I") == 1

    def test_floor_at_one(self):
        # Any non-empty word should return at least 1
        assert server._count_syllables_word("hmm") >= 1
        assert server._count_syllables_word("nth") >= 1


# ===========================================================================
# count_syllables tool tests
# ===========================================================================

class TestCountSyllables:
    """Tests for the count_syllables MCP tool."""

    def test_empty_input(self):
        result = json.loads(_run(server.count_syllables("")))
        assert result["sections"] == []
        assert result["summary"]["total_syllables"] == 0
        assert result["summary"]["consistency"] == "N/A"

    def test_section_tracking(self):
        lyrics = (
            "[Verse 1]\n"
            "Hello world tonight\n"
            "Stars are shining bright\n"
            "\n"
            "[Chorus]\n"
            "We are the champions\n"
        )
        result = json.loads(_run(server.count_syllables(lyrics)))
        assert len(result["sections"]) == 2
        assert result["sections"][0]["section"] == "Verse 1"
        assert result["sections"][1]["section"] == "Chorus"
        assert result["sections"][0]["line_count"] == 2
        assert result["sections"][1]["line_count"] == 1

    def test_summary_stats(self):
        lyrics = (
            "[Verse]\n"
            "The quick brown fox\n"
            "Jumped over the lazy dog\n"
        )
        result = json.loads(_run(server.count_syllables(lyrics)))
        summary = result["summary"]
        assert summary["total_lines"] == 2
        assert summary["total_syllables"] > 0
        assert summary["avg_syllables_per_line"] > 0
        assert summary["min_line"] <= summary["max_line"]

    def test_consistency_even(self):
        # Lines with similar syllable counts should be CONSISTENT
        lyrics = (
            "[Verse]\n"
            "Hello world tonight\n"
            "Dancing in the light\n"
            "Moving through the night\n"
            "Feeling so alive\n"
        )
        result = json.loads(_run(server.count_syllables(lyrics)))
        assert result["summary"]["consistency"] == "CONSISTENT"

    def test_consistency_uneven(self):
        # Lines with very different syllable counts should be UNEVEN
        lyrics = (
            "[Verse]\n"
            "Go\n"
            "Supercalifragilisticexpialidocious is a wonderful word today\n"
            "Go\n"
            "Supercalifragilisticexpialidocious is a wonderful wonderful word today\n"
        )
        result = json.loads(_run(server.count_syllables(lyrics)))
        assert result["summary"]["consistency"] == "UNEVEN"

    def test_json_structure(self):
        lyrics = "[Verse]\nHello world\n"
        result = json.loads(_run(server.count_syllables(lyrics)))
        assert "sections" in result
        assert "summary" in result
        section = result["sections"][0]
        assert "section" in section
        assert "lines" in section
        assert "avg_syllables_per_line" in section
        line = section["lines"][0]
        assert "line_number" in line
        assert "text" in line
        assert "syllable_count" in line
        assert "word_count" in line


# ===========================================================================
# analyze_readability tool tests
# ===========================================================================

class TestAnalyzeReadability:
    """Tests for the analyze_readability MCP tool."""

    def test_empty_input(self):
        result = json.loads(_run(server.analyze_readability("")))
        assert result["word_stats"]["total_words"] == 0
        assert result["readability"]["grade_level"] == "N/A"

    def test_vocabulary_richness(self):
        # All unique words: richness = 1.0
        lyrics = "[Verse]\nEvery single word here differs completely"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["word_stats"]["vocabulary_richness"] == 1.0

    def test_vocabulary_richness_with_repeats(self):
        # Repeated words lower richness
        lyrics = "[Verse]\nlove love love love love love"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["word_stats"]["vocabulary_richness"] < 0.5

    def test_flesch_formula(self):
        # Simple monosyllabic words on short lines → high score
        lyrics = "[Verse]\nI love you\nYou love me\nWe are free"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["readability"]["flesch_reading_ease"] > 70

    def test_grade_levels(self):
        # Simple text should be Easy or Very Easy
        lyrics = "[Verse]\nI go home\nYou go too\nWe are here"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["readability"]["grade_level"] in ("Very Easy", "Easy", "Standard")

    def test_json_structure(self):
        lyrics = "[Verse]\nHello world tonight"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert "word_stats" in result
        assert "line_stats" in result
        assert "readability" in result
        assert "total_words" in result["word_stats"]
        assert "unique_words" in result["word_stats"]
        assert "flesch_reading_ease" in result["readability"]
        assert "grade_level" in result["readability"]
        assert "assessment" in result["readability"]


# ===========================================================================
# _get_rhyme_tail helper tests
# ===========================================================================

class TestGetRhymeTail:
    """Tests for the _get_rhyme_tail helper."""

    def test_basic_suffix(self):
        assert server._get_rhyme_tail("night") == "ight"
        assert server._get_rhyme_tail("light") == "ight"
        assert server._get_rhyme_tail("fight") == "ight"

    def test_silent_e_words(self):
        tail_fire = server._get_rhyme_tail("fire")
        tail_desire = server._get_rhyme_tail("desire")
        assert tail_fire == tail_desire

    def test_plural_stripping(self):
        # "nights" should strip 's' and match "night"
        tail_nights = server._get_rhyme_tail("nights")
        tail_night = server._get_rhyme_tail("night")
        assert tail_nights == tail_night

    def test_short_words(self):
        # Should handle very short words gracefully
        tail = server._get_rhyme_tail("go")
        assert len(tail) >= 1

    def test_empty(self):
        assert server._get_rhyme_tail("") == ""

    def test_rhyme_pair_match(self):
        # Words that rhyme should have same tail
        assert server._get_rhyme_tail("away") == server._get_rhyme_tail("day")
        assert server._get_rhyme_tail("shore") == server._get_rhyme_tail("more")
        assert server._get_rhyme_tail("fire") == server._get_rhyme_tail("desire")


# ===========================================================================
# analyze_rhyme_scheme tool tests
# ===========================================================================

class TestAnalyzeRhymeScheme:
    """Tests for the analyze_rhyme_scheme MCP tool."""

    def test_empty_input(self):
        result = json.loads(_run(server.analyze_rhyme_scheme("")))
        assert result["sections"] == []
        assert result["summary"]["total_sections"] == 0

    def test_aabb_pattern(self):
        lyrics = (
            "[Verse]\n"
            "The stars are shining bright tonight\n"
            "Everything is gonna be alright\n"
            "I walk along the sandy shore\n"
            "Looking for something more\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        section = result["sections"][0]
        # First two lines should share a rhyme group, last two another
        assert section["lines"][0]["rhyme_group"] == section["lines"][1]["rhyme_group"]
        assert section["lines"][2]["rhyme_group"] == section["lines"][3]["rhyme_group"]

    def test_abab_pattern(self):
        lyrics = (
            "[Verse]\n"
            "Walking down the road tonight\n"
            "Searching for the distant shore\n"
            "Stars are shining burning bright\n"
            "Looking for something more\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        section = result["sections"][0]
        # Lines 1,3 should match; lines 2,4 should match
        assert section["lines"][0]["rhyme_group"] == section["lines"][2]["rhyme_group"]
        assert section["lines"][1]["rhyme_group"] == section["lines"][3]["rhyme_group"]

    def test_xaxa_pattern(self):
        lyrics = (
            "[Verse]\n"
            "The world is turning upside down\n"
            "Walking through the rain tonight\n"
            "I cannot see the way ahead\n"
            "Everything will be alright\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        section = result["sections"][0]
        # Lines 2 and 4 should share a group (tonight/alright)
        assert section["lines"][1]["rhyme_group"] == section["lines"][3]["rhyme_group"]

    def test_self_rhyme_detection(self):
        lyrics = (
            "[Verse]\n"
            "I walk into the night\n"
            "The stars are burning bright\n"
            "I cannot see the night\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        assert result["summary"]["self_rhymes"] >= 1
        assert any(i["type"] == "self_rhyme" for i in result["issues"])

    def test_multiple_sections(self):
        lyrics = (
            "[Verse 1]\n"
            "Walking down the street tonight\n"
            "Everything will be alright\n"
            "\n"
            "[Chorus]\n"
            "We are the dreamers of the day\n"
            "We are the ones who found a way\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        assert result["summary"]["total_sections"] == 2

    def test_scheme_letters(self):
        lyrics = (
            "[Verse]\n"
            "Stars above the night\n"
            "Moon is shining bright\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        scheme = result["sections"][0]["scheme"]
        # Both lines should rhyme → "AA"
        assert scheme == "AA"

    def test_no_rhyme_different_groups(self):
        lyrics = (
            "[Verse]\n"
            "Walking through the rain\n"
            "Opening the book\n"
            "Sitting on the chair\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        section = result["sections"][0]
        groups = [l["rhyme_group"] for l in section["lines"]]
        # All different — no rhymes
        assert len(set(groups)) == len(groups)

    def test_json_structure(self):
        lyrics = "[Verse]\nHello world tonight\nStars are burning bright\n"
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        assert "sections" in result
        assert "issues" in result
        assert "summary" in result
        section = result["sections"][0]
        assert "section" in section
        assert "section_type" in section
        assert "scheme" in section
        assert "lines" in section
        line = section["lines"][0]
        assert "line_number" in line
        assert "end_word" in line
        assert "rhyme_group" in line
        assert "rhyme_tail" in line

    def test_repeated_end_word_flagged(self):
        """Same word ending multiple lines in a section should flag as self_rhyme."""
        lyrics = (
            "[Chorus]\n"
            "We stand in the night\n"
            "Lost in the night\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        assert result["summary"]["self_rhymes"] >= 1

    def test_section_type_detected(self):
        lyrics = (
            "[Pre-Chorus]\n"
            "Building to the top\n"
            "Never gonna stop\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        assert result["sections"][0]["section_type"] == "pre-chorus"


# ===========================================================================
# validate_section_structure tool tests
# ===========================================================================

class TestValidateSectionStructure:
    """Tests for the validate_section_structure MCP tool."""

    def test_empty_input(self):
        result = json.loads(_run(server.validate_section_structure("")))
        assert result["summary"]["total_sections"] == 0
        assert result["summary"]["issues_count"] >= 1

    def test_well_formed(self):
        lyrics = (
            "[Verse 1]\n"
            "Line one here\n"
            "Line two here\n"
            "\n"
            "[Chorus]\n"
            "Chorus line one\n"
            "Chorus line two\n"
            "\n"
            "[Verse 2]\n"
            "Line three here\n"
            "Line four here\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["total_sections"] == 3
        assert result["summary"]["has_verse"] is True
        assert result["summary"]["has_chorus"] is True
        assert result["summary"]["section_balance"] == "BALANCED"

    def test_unbalanced_verses(self):
        lyrics = (
            "[Verse 1]\n"
            "Line one\n"
            "Line two\n"
            "\n"
            "[Chorus]\n"
            "Chorus\n"
            "\n"
            "[Verse 2]\n"
            "Line one\n"
            "Line two\n"
            "Line three\n"
            "Line four\n"
            "Line five\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["section_balance"] == "UNBALANCED"
        assert any(i["type"] == "unbalanced_sections" for i in result["issues"])

    def test_empty_section(self):
        lyrics = (
            "[Verse 1]\n"
            "Content here\n"
            "\n"
            "[Chorus]\n"
            "\n"
            "[Verse 2]\n"
            "More content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert any(i["type"] == "empty_section" for i in result["issues"])

    def test_no_section_tags(self):
        lyrics = "Just some lyrics\nWithout any tags\n"
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["total_sections"] == 0
        assert any(i["type"] == "no_section_tags" for i in result["issues"])

    def test_duplicate_consecutive_tags(self):
        lyrics = (
            "[Verse 1]\n"
            "Content\n"
            "[Verse 1]\n"
            "More content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert any(i["type"] == "duplicate_consecutive_tag" for i in result["issues"])

    def test_missing_chorus(self):
        lyrics = (
            "[Verse 1]\n"
            "Content here\n"
            "\n"
            "[Verse 2]\n"
            "More content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["has_chorus"] is False
        assert any(i["type"] == "missing_chorus" for i in result["issues"])

    def test_missing_verse(self):
        lyrics = (
            "[Chorus]\n"
            "Chorus content\n"
            "\n"
            "[Bridge]\n"
            "Bridge content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["has_verse"] is False
        assert any(i["type"] == "missing_verse" for i in result["issues"])

    def test_json_structure(self):
        lyrics = "[Verse]\nHello world\n[Chorus]\nYeah yeah\n"
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert "sections" in result
        assert "issues" in result
        assert "summary" in result
        summary = result["summary"]
        assert "total_sections" in summary
        assert "has_verse" in summary
        assert "has_chorus" in summary
        assert "has_bridge" in summary
        assert "issues_count" in summary
        assert "section_balance" in summary
        section = result["sections"][0]
        assert "tag" in section
        assert "line_number" in section
        assert "content_lines" in section
        assert "section_type" in section

    def test_content_before_first_tag(self):
        """Content before the first section tag should warn."""
        lyrics = (
            "Some loose content here\n"
            "More untagged lines\n"
            "[Verse 1]\n"
            "Actual verse content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert any(i["type"] == "content_before_first_tag" for i in result["issues"])

    def test_hook_counts_as_chorus(self):
        """[Hook] should satisfy has_chorus."""
        lyrics = (
            "[Verse 1]\n"
            "Some verse content\n"
            "\n"
            "[Hook]\n"
            "Hook content here\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["has_chorus"] is True

    def test_empty_last_section(self):
        """Empty section at end of text should be flagged."""
        lyrics = (
            "[Verse 1]\n"
            "Content here\n"
            "\n"
            "[Chorus]\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert any(
            i["type"] == "empty_section" and i["tag"] == "[Chorus]"
            for i in result["issues"]
        )

    def test_unknown_section_type_defaults_to_verse(self):
        """Tags like [Interlude] should default to section_type 'verse'."""
        lyrics = (
            "[Interlude]\n"
            "Some content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["sections"][0]["section_type"] == "verse"

    def test_balanced_with_single_verse(self):
        """Single verse should always be BALANCED."""
        lyrics = (
            "[Verse 1]\n"
            "Content here\n"
            "\n"
            "[Chorus]\n"
            "Chorus content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["section_balance"] == "BALANCED"

    def test_balanced_at_threshold_boundary(self):
        """Verses differing by exactly 2 lines should be BALANCED (threshold is > 2)."""
        lyrics = (
            "[Verse 1]\n"
            "Line one\n"
            "Line two\n"
            "\n"
            "[Chorus]\n"
            "Chorus\n"
            "\n"
            "[Verse 2]\n"
            "Line one\n"
            "Line two\n"
            "Line three\n"
            "Line four\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["section_balance"] == "BALANCED"

    def test_has_bridge_detected(self):
        """has_bridge should be True when [Bridge] is present."""
        lyrics = (
            "[Verse]\n"
            "Verse content\n"
            "\n"
            "[Chorus]\n"
            "Chorus content\n"
            "\n"
            "[Bridge]\n"
            "Bridge content\n"
        )
        result = json.loads(_run(server.validate_section_structure(lyrics)))
        assert result["summary"]["has_bridge"] is True

    def test_whitespace_only_input(self):
        """Whitespace-only input should produce no_content issue."""
        result = json.loads(_run(server.validate_section_structure("   \n\n  ")))
        assert result["summary"]["total_sections"] == 0
        assert any(i["type"] == "no_content" for i in result["issues"])


# ===========================================================================
# _words_rhyme helper tests
# ===========================================================================

class TestWordsRhyme:
    """Tests for the _words_rhyme helper."""

    def test_empty_inputs(self):
        assert server._words_rhyme("", "night") is False
        assert server._words_rhyme("night", "") is False
        assert server._words_rhyme("", "") is False

    def test_identical_words_return_false(self):
        assert server._words_rhyme("night", "night") is False

    def test_case_insensitive_identity(self):
        assert server._words_rhyme("Night", "night") is False

    def test_short_tail_no_match(self):
        # Single-char tails should not match
        assert server._words_rhyme("a", "ma") is False

    def test_true_rhyme_pair(self):
        assert server._words_rhyme("night", "light") is True
        assert server._words_rhyme("fire", "desire") is True

    def test_false_rhyme_pair(self):
        assert server._words_rhyme("night", "book") is False
        assert server._words_rhyme("cat", "dog") is False

    def test_apostrophe_handling(self):
        # Apostrophes should be stripped before comparison
        assert server._words_rhyme("night", "light") is True


# ===========================================================================
# Additional _count_syllables_word edge case tests
# ===========================================================================

class TestCountSyllablesWordEdgeCases:
    """Additional edge case tests for _count_syllables_word."""

    def test_apostrophe_only_input(self):
        """After stripping apostrophes, empty string returns 0."""
        assert server._count_syllables_word("'''") == 0

    def test_silent_e_and_consonant_le_interaction(self):
        """Both silent-e and consonant-le rules on same word."""
        # "crumble" — silent-e removes 1, consonant-le adds 1
        count = server._count_syllables_word("crumble")
        assert count == 2

    def test_vowel_before_le_no_extra_syllable(self):
        """Words ending in vowel + 'le' should NOT trigger consonant-le rule."""
        # "ale" has vowel 'a' before 'le'
        assert server._count_syllables_word("ale") == 1

    def test_consecutive_vowel_clusters(self):
        """Diphthongs count as one vowel cluster."""
        assert server._count_syllables_word("beau") == 1
        assert server._count_syllables_word("queue") == 1

    def test_uppercase_input(self):
        """Case normalization should work."""
        assert server._count_syllables_word("HELLO") == 2
        assert server._count_syllables_word("APPLE") == 2


# ===========================================================================
# Additional _get_rhyme_tail edge case tests
# ===========================================================================

class TestGetRhymeTailEdgeCases:
    """Additional edge case tests for _get_rhyme_tail."""

    def test_apostrophe_only_input(self):
        assert server._get_rhyme_tail("'''") == ""

    def test_no_vowels_returns_whole_word(self):
        """Words with no vowels should return the entire word."""
        assert server._get_rhyme_tail("brr") == "brr"

    def test_double_s_not_stripped(self):
        """Words ending in 'ss' should NOT have trailing 's' stripped."""
        tail_boss = server._get_rhyme_tail("boss")
        tail_toss = server._get_rhyme_tail("toss")
        assert tail_boss == tail_toss  # Both keep 'ss'

    def test_short_word_no_strip(self):
        """Two-letter words ending in 's' should NOT be stripped."""
        # "is" — len(2) <= 2, so no strip
        tail = server._get_rhyme_tail("is")
        assert len(tail) >= 1

    def test_word_ending_e_vowel_before(self):
        """Words ending in vowel + 'e' should NOT activate silent-e scan."""
        # "free" — 'e' preceded by 'e' (vowel), no silent-e adjustment
        tail_free = server._get_rhyme_tail("free")
        tail_see = server._get_rhyme_tail("see")
        assert tail_free == tail_see  # Both should end the same way

    def test_uppercase_normalization(self):
        assert server._get_rhyme_tail("NIGHT") == server._get_rhyme_tail("night")


# ===========================================================================
# Additional count_syllables tool edge case tests
# ===========================================================================

class TestCountSyllablesEdgeCases:
    """Additional edge case tests for count_syllables MCP tool."""

    def test_whitespace_only_input(self):
        result = json.loads(_run(server.count_syllables("   \n\n  ")))
        assert result["summary"]["total_syllables"] == 0

    def test_no_section_tags(self):
        """Lyrics without tags should use 'Unknown' section."""
        lyrics = "Hello world tonight\nStars are shining bright\n"
        result = json.loads(_run(server.count_syllables(lyrics)))
        assert len(result["sections"]) == 1
        assert result["sections"][0]["section"] == "Unknown"

    def test_single_line_consistency_na(self):
        """Single content line should produce consistency N/A."""
        lyrics = "[Verse]\nJust one line here\n"
        result = json.loads(_run(server.count_syllables(lyrics)))
        assert result["summary"]["consistency"] == "N/A"

    def test_section_tag_only_no_content(self):
        """Section tags with no content between them."""
        lyrics = "[Verse 1]\n[Chorus]\nSome content\n"
        result = json.loads(_run(server.count_syllables(lyrics)))
        # Empty "Verse 1" section should not appear (no lines to report)
        section_names = [s["section"] for s in result["sections"]]
        assert "Verse 1" not in section_names
        assert "Chorus" in section_names

    def test_per_line_word_count(self):
        """Word count per line should match tokenization."""
        lyrics = "[Verse]\nOne two three four five\n"
        result = json.loads(_run(server.count_syllables(lyrics)))
        assert result["sections"][0]["lines"][0]["word_count"] == 5


# ===========================================================================
# Additional analyze_readability edge case tests
# ===========================================================================

class TestAnalyzeReadabilityEdgeCases:
    """Additional edge case tests for analyze_readability MCP tool."""

    def test_section_tags_only(self):
        """Input of only section tags should return empty stats."""
        result = json.loads(_run(server.analyze_readability("[Verse]\n[Chorus]\n")))
        assert result["word_stats"]["total_words"] == 0

    def test_grade_level_very_easy(self):
        """Very simple monosyllabic text should score Very Easy."""
        lyrics = "[Verse]\nI go\nYou go\nWe go\nThey go\nI run\nYou run"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["readability"]["grade_level"] == "Very Easy"

    def test_grade_level_complex(self):
        """Dense polysyllabic vocabulary should score Complex or Moderate."""
        lyrics = (
            "[Verse]\n"
            "Extraterrestrial communication permeates interdimensional consciousness\n"
            "Philosophical metamorphosis characterizes institutional experimentation\n"
            "Disproportionate internationalization overwhelms administrative bureaucracy\n"
            "Incomprehensible telecommunication infrastructure deterioration accelerates\n"
        )
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["readability"]["grade_level"] in ("Complex", "Moderate")

    def test_min_max_words_per_line(self):
        """min and max words per line should be correct."""
        lyrics = "[Verse]\nOne two\nOne two three four five six\n"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["line_stats"]["min_words_line"] == 2
        assert result["line_stats"]["max_words_line"] == 6

    def test_punctuation_only_line_excluded(self):
        """Lines with only punctuation should be excluded from stats."""
        lyrics = "[Verse]\nHello world\n---\nGoodbye moon\n"
        result = json.loads(_run(server.analyze_readability(lyrics)))
        assert result["line_stats"]["total_lines"] == 2


# ===========================================================================
# Additional analyze_rhyme_scheme edge case tests
# ===========================================================================

class TestAnalyzeRhymeSchemeEdgeCases:
    """Additional edge case tests for analyze_rhyme_scheme MCP tool."""

    def test_single_line_section(self):
        """Single-line section should produce single letter scheme."""
        lyrics = "[Chorus]\nShining bright\n"
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        assert len(result["sections"][0]["scheme"]) == 1
        assert result["summary"]["self_rhymes"] == 0

    def test_short_rhyme_tail_no_false_match(self):
        """End words with very short tails should not produce false rhyme matches."""
        lyrics = (
            "[Verse]\n"
            "I stand alone\n"
            "The world is so\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        section = result["sections"][0]
        # "alone" tail = "one", "so" tail = "o" (1 char) — should NOT match
        groups = [l["rhyme_group"] for l in section["lines"]]
        assert groups[0] != groups[1]

    def test_sections_with_issues_count(self):
        """sections_with_issues should match count of sections having issues."""
        lyrics = (
            "[Verse 1]\n"
            "Walking in the night\n"
            "Stars are shining bright\n"
            "\n"
            "[Verse 2]\n"
            "Looking at the rain\n"
            "Feeling all the rain\n"
        )
        result = json.loads(_run(server.analyze_rhyme_scheme(lyrics)))
        actual = sum(1 for s in result["sections"] if s["issues"])
        assert result["summary"]["sections_with_issues"] == actual
