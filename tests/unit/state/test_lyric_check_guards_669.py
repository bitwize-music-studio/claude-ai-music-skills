#!/usr/bin/env python3
"""Regression tests: lyric checks that dropped common, valid input (#669).

A sweep of the lyric checks after #646 (cry / sky) found more guards that threw
away what they should have read, so ``check_album_lyrics`` could call a sheet
clean when it was not:

1. One-letter rhyme tails ("me", "go", "baby") never grouped, not even the
   same word twice.
2. The plural-s strip hit non-plurals: "this" keyed as "i", "yes" as "eyes".
3. End words "I" and "a" were skipped, so "...the open sky / ...you and I"
   compared "sky" with "and".
4. A typographic apostrophe or an accented letter split a word in two.
5. Homographs matched only the base word: "tears", "lives" passed, including
   the blocking pre-generation gate.
6. Explicit detection missed inflections: "fuckin'", "fucks", "shits".
8. The "e" of "-ed" / "-es" was counted as a syllable: "walked" was two.

Items 7 (BOM) and 9 (IDEAS bold colon) are in
``test_frontmatter_bom_ideas_669.py``.

Usage:
    python -m pytest tests/unit/state/test_lyric_check_guards_669.py -v
"""

import asyncio
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
# Import server module from hyphenated directory via importlib, with the same
# mcp mock the other lyrics tests use.
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
    spec = importlib.util.spec_from_file_location("state_server_lyric_guards_669", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_server = _import_server()
from handlers import _shared as _shared_mod
from handlers import gates as _gates_mod
from handlers import lyrics_analysis as _la
from handlers import text_analysis as _ta

_get_rhyme_tail = _la._get_rhyme_tail
_count_syllables_word = _la._count_syllables_word


def _run(coro):
    return asyncio.run(coro)


def _rhyme(lyrics: str) -> dict:
    return json.loads(_run(_la.analyze_rhyme_scheme(lyrics)))


def _scheme(lyrics: str) -> str:
    return _rhyme(lyrics)["sections"][0]["scheme"]


def _explicit(text: str) -> dict:
    with patch.object(_ta, "_explicit_word_cache", None):
        return json.loads(_run(_ta.check_explicit_content(text)))


# ===========================================================================
# 1. One-letter rhyme tails
# ===========================================================================


class TestOneLetterRhymeTails:
    """No common end word keys as a single letter, which never groups."""

    def test_same_word_twice_groups(self):
        assert _scheme("[Chorus]\nRun away with me\nCome on back to me\n") == "AA"

    @pytest.mark.parametrize("word", ["me", "be", "we", "he", "she"])
    def test_bare_e_words_rhyme_with_free(self, word):
        assert _get_rhyme_tail(word) == _get_rhyme_tail("free")

    @pytest.mark.parametrize("word", ["go", "no", "so"])
    def test_bare_o_words_rhyme_with_toe(self, word):
        assert _get_rhyme_tail(word) == _get_rhyme_tail("toe")

    @pytest.mark.parametrize("word", ["do", "to", "who", "two", "into"])
    def test_oo_words_rhyme_with_too(self, word):
        assert _get_rhyme_tail(word) == _get_rhyme_tail("too")

    @pytest.mark.parametrize("pair", [
        ("crazy", "lazy"), ("story", "glory"), ("hero", "zero"), ("city", "pity"),
    ])
    def test_final_vowel_words_reach_back(self, pair):
        a, b = pair
        assert len(_get_rhyme_tail(a)) >= 2
        assert _get_rhyme_tail(a) == _get_rhyme_tail(b)

    def test_chorus_scheme(self):
        stanza = (
            "[Chorus]\n"
            "Run away with me\n"
            "Baby, set me free\n"
            "You were driving me crazy\n"
            "Sunday mornings slow and lazy\n"
        )
        assert _scheme(stanza) == "AABB"

    def test_go_and_do_stay_apart(self):
        # Guard (passes before the fix too): sounding the bare words out must
        # not put go and do in one group.
        assert _get_rhyme_tail("go") != _get_rhyme_tail("do")

    def test_the_does_not_rhyme_with_me(self):
        # Guard: "the" keeps its own key.
        assert _get_rhyme_tail("the") != _get_rhyme_tail("me")

    def test_different_short_words_stay_apart(self):
        # Guard: "ma" and "spa" still key as one letter; only the same word
        # again joins such a line.
        groups = [ln["rhyme_group"] for ln in _rhyme("[Verse]\nCall your ma\nMeet me at the spa\n")
                  ["sections"][0]["lines"]]
        assert groups[0] != groups[1]

    def test_same_short_word_twice_groups(self):
        assert _scheme("[Verse]\nI called my ma\nShe is still my ma\n") == "AA"


# ===========================================================================
# 2. Plural-s strip on non-plurals
# ===========================================================================


class TestPluralStripOnNonPlurals:

    @pytest.mark.parametrize("word", ["this", "his", "was", "has", "thus", "plus", "bus", "christmas"])
    def test_non_plural_keeps_its_s(self, word):
        assert len(_get_rhyme_tail(word)) >= 2
        assert _get_rhyme_tail(word).endswith("s")

    def test_this_twice_groups(self):
        stanza = "[Verse]\nI never felt like this\nI only want your kiss\nThere's nothing that I miss\nIt always ends like this\n"
        assert _scheme(stanza) == "ABBA"

    def test_this_rhymes_with_his(self):
        assert len(_get_rhyme_tail("this")) >= 2
        assert _get_rhyme_tail("this") == _get_rhyme_tail("his")

    def test_yes_does_not_rhyme_with_eyes(self):
        assert _get_rhyme_tail("yes") != _get_rhyme_tail("eyes")
        assert _get_rhyme_tail("yes") == _get_rhyme_tail("less")

    def test_real_plurals_still_strip(self):
        # Guard: #396's eye/eyes and cry/cries keep matching.
        assert _get_rhyme_tail("eyes") == _get_rhyme_tail("eye")
        assert _get_rhyme_tail("cries") == _get_rhyme_tail("cry")
        assert _get_rhyme_tail("days") == _get_rhyme_tail("day")


# ===========================================================================
# 3. End words "I" and "a"
# ===========================================================================


class TestOneLetterEndWords:

    def test_line_ending_on_i_rhymes_with_sky(self):
        result = _rhyme("[Chorus]\nUnder the open sky\nIt's only you and I\n")
        lines = result["sections"][0]["lines"]
        assert [ln["end_word"] for ln in lines] == ["sky", "i"]
        assert result["sections"][0]["scheme"] == "AA"

    def test_who_i_am_is_not_a_self_rhyme(self):
        result = _rhyme("[Verse]\nI know exactly who I am\nBut tell me now, who am I\n")
        assert result["summary"]["self_rhymes"] == 0
        assert [ln["end_word"] for ln in result["sections"][0]["lines"]] == ["am", "i"]

    def test_repeat_marker_is_not_an_end_word(self):
        # Guard: "(x2)" leaves a lone "x"; it is not a word.
        result = _rhyme("[Chorus]\nWe carry on (x2)\n")
        assert result["sections"][0]["lines"][0]["end_word"] == "on"


# ===========================================================================
# 4. Curly apostrophes and accented letters
# ===========================================================================


class TestCurlyApostrophesAndAccents:

    STRAIGHT = "I don't know what it's like"
    CURLY = "I don\u2019t know what it\u2019s like"

    def test_curly_line_counts_like_straight(self):
        straight = json.loads(_run(_la.count_syllables(f"[Verse]\n{self.STRAIGHT}\n")))
        curly = json.loads(_run(_la.count_syllables(f"[Verse]\n{self.CURLY}\n")))
        s_line = straight["sections"][0]["lines"][0]
        c_line = curly["sections"][0]["lines"][0]
        assert (c_line["syllable_count"], c_line["word_count"]) == (6, 6)
        assert (s_line["syllable_count"], s_line["word_count"]) == (6, 6)

    def test_curly_tokens_match_straight(self):
        straight = _la._tokenize_lyrics_with_sections(f"[Verse]\n{self.STRAIGHT}\n")
        curly = _la._tokenize_lyrics_with_sections(f"[Verse]\n{self.CURLY}\n")
        assert curly[0]["words"] == straight[0]["words"]
        assert _ta._tokenize_lyrics_by_line(self.CURLY) == _ta._tokenize_lyrics_by_line(self.STRAIGHT)

    @pytest.mark.parametrize("line, end_word", [
        ("I know who you\u2019re", "you're"),
        ("I just can\u2019t", "can't"),
        ("Hasta ma\u00f1ana", "ma\u00f1ana"),
        ("Meet me at the caf\u00e9", "caf\u00e9"),
    ])
    def test_end_word_is_whole(self, line, end_word):
        result = _rhyme(f"[Verse]\n{line}\n")
        assert result["sections"][0]["lines"][0]["end_word"] == end_word

    def test_trailing_curly_apostrophe_stripped(self):
        # Guard: now that U+2019 is part of a token, a trailing one is still stripped.
        assert _la._tokenize_lyrics_with_sections("[Verse]\nnothin\u2019 at all\n")[0]["words"] == [
            "nothin", "at", "all",
        ]

    def test_times_and_divide_signs_are_not_letters(self):
        # Guard: the multiplication and division signs sit inside the accented-letter range and are left out.
        assert _shared_mod._WORD_TOKEN_RE.findall("a\u00d7b c\u00f7d") == ["a", "b", "c", "d"]


# ===========================================================================
# 5. Homograph -s forms
# ===========================================================================


class TestHomographSForms:

    @pytest.mark.parametrize("word", [
        "tear", "live", "wind", "lead", "bow", "row", "sow", "record", "present",
        "object", "project", "desert", "refuse", "resume",
    ])
    def test_s_form_is_flagged(self, word):
        result = json.loads(_run(_ta.check_homographs(f"All the {word}s we knew")))
        assert result["has_homographs"] is True
        assert result["matches"][0]["canonical"] == word
        assert result["matches"][0]["word"] == f"{word}s"

    @pytest.mark.parametrize("text", [
        "Just a few minutes more", "The shop closes at nine", "Old wounds heal",
        "She reads the letter", "The contents of the box",
    ])
    def test_unambiguous_s_forms_not_flagged(self, text):
        # Guard: only the listed words take the -s form.
        result = json.loads(_run(_ta.check_homographs(text)))
        assert result["has_homographs"] is False

    def test_blocking_gate_sees_s_form(self):
        track = (
            "---\ntitle: Tears\nstatus: In Progress\nexplicit: false\n---\n\n"
            "## Lyrics Box\n\n```\n[Verse 1]\nWipe away your tears\nWalking down the road\n```\n\n"
            "## Style Box\n\n```\npop rock, 110 BPM\n```\n"
        )
        _blocking, _warnings, gates = _gates_mod._check_pre_gen_gates_for_track(
            {"sources_verified": "N/A", "explicit": False}, track, blocklist=[],
        )
        gate = next(g for g in gates if g["gate"] == "Homograph Check")
        assert gate["status"] == "FAIL"
        assert gate["severity"] == "BLOCKING"
        assert "tear" in gate["detail"]


# ===========================================================================
# 6. Explicit inflections
# ===========================================================================


class TestExplicitInflections:

    @pytest.mark.parametrize("word", [
        "fuckin'", "fuckin\u2019", "motherfuckin'", "fucks", "fuckers",
        "motherfuckers", "shits", "sluts", "whores", "cunts", "bitchin'",
        "goddamned", "shittin'",
    ])
    def test_inflection_is_explicit(self, word):
        assert _explicit(f"I said {word} out loud")["has_explicit"] is True

    @pytest.mark.parametrize("text", [
        "Order a cocktail", "Reading Emily Dickinson", "He cocked the gun",
        "Shiitake on the grill", "Charles Dickens wrote it",
    ])
    def test_no_new_false_positives(self, text):
        # Guard: the suffixes stay whole-word.
        assert _explicit(text)["has_explicit"] is False

    def test_listed_word_counted_once(self):
        # Guard: "fucked" is listed and is also fuck + -ed: one hit, under
        # "fucked", not a second one under "fuck".
        result = _explicit("Everything is fucked")
        assert result["total_count"] == 1
        assert [m["word"] for m in result["matches"]] == ["fucked"]

    def test_issue_sheet_is_no_longer_clean(self):
        sheet = (
            "[Verse 1]\n"
            "I know exactly who I am\n"
            "I don\u2019t need your fuckin\u2019 plan\n"
            "Wipe away the tears you cried\n"
            "Every word you said, you lied\n"
            "\n"
            "[Chorus]\n"
            "Run away with me\n"
            "Baby, set me free\n"
            "Under the open sky\n"
            "It's only you and I\n"
        )
        with patch.object(_ta, "_explicit_word_cache", None):
            result = _run(_la._check_lyrics(sheet, flagged_explicit=False, verbose=True))
        assert "homographs" in result["fired"]
        assert "explicit" in result["fired"]
        chorus = next(s for s in result["blocks"]["rhyme"]["schemes"] if s["section"] == "Chorus")
        assert chorus["scheme"] == "AABB"


# ===========================================================================
# 8. "-ed" / "-es" syllables
# ===========================================================================


class TestEdEsSyllables:

    @pytest.mark.parametrize("word", [
        "walked", "talked", "hoped", "loved", "moved", "burned", "kissed",
        "times", "makes", "lives", "comes", "hopes", "smiles", "clothes",
    ])
    def test_silent_e_is_one_syllable(self, word):
        assert _count_syllables_word(word) == 1

    @pytest.mark.parametrize("word", [
        "wanted", "needed", "faded", "places", "chances", "roses", "boxes",
        "judges", "watches", "wishes", "bottles", "tables", "sacred", "hundred",
    ])
    def test_sounded_e_stays(self, word):
        # Guard: -ed after t/d, -es after a sibilant, consonant + le / re.
        assert _count_syllables_word(word) == 2

    def test_one_syllable_words_unchanged(self):
        # Guard: the count > 1 floor keeps "bed", "red", "yes" at one.
        for word in ("bed", "red", "yes", "shed"):
            assert _count_syllables_word(word) == 1

    def test_no_false_outlier_in_ed_verse(self):
        verse = (
            "[Verse 1]\n"
            "I walked and talked and hoped and prayed\n"
            "We loved, we moved, we burned, we turned, we learned\n"
            "I kept the light on in the hall\n"
            "I kept the door wide open too\n"
        )
        syllables = json.loads(_run(_la.count_syllables(verse)))
        assert _la._syllable_outliers(syllables, tolerance=2) == []
