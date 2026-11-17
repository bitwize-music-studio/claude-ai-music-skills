#!/usr/bin/env python3
"""Regression tests: one-syllable consonant + 'y' end words rhyme.

_get_rhyme_tail found only the final 'y' as the vowel nucleus of "cry",
"sky", "why", "my", so it returned "i", a one-letter tail.
analyze_rhyme_scheme groups tails of two letters or more only, so every
such line got a new letter: a chorus ending cry / sky / why came back as
ABC, and two lines ending on the same word "cry" as AB. The plural
"cries" already keyed as "ie", so "cry" and "cries" did not match either.

Usage:
    python -m pytest tests/unit/state/test_rhyme_tail_consonant_y.py -v
"""

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Import server module from hyphenated directory via importlib. Executing the
# server puts ``servers/bitwize-music-server`` on sys.path so ``handlers`` is
# importable. Mirror the mcp mock used by the other lyrics tests so this file
# runs even when the real ``mcp`` package is not installed.
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
    spec = importlib.util.spec_from_file_location("state_server_rhyme_consonant_y", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_server = _import_server()
from handlers import lyrics_analysis as _lyrics_analysis_mod

_get_rhyme_tail = _lyrics_analysis_mod._get_rhyme_tail
analyze_rhyme_scheme = _lyrics_analysis_mod.analyze_rhyme_scheme


def _run(coro):
    return asyncio.run(coro)


class TestConsonantYTail:
    """One-syllable consonant + 'y' words key as "ie", the vowel of "lie"."""

    def test_cry_matches_its_plural(self):
        assert _get_rhyme_tail("cry") == _get_rhyme_tail("cries")

    def test_family_shares_one_tail(self):
        tails = {_get_rhyme_tail(w) for w in ("cry", "sky", "why", "my", "by", "fly", "try", "shy", "dry")}
        assert len(tails) == 1

    def test_matches_ie_spellings(self):
        assert _get_rhyme_tail("sky") == _get_rhyme_tail("lie")
        assert _get_rhyme_tail("why") == _get_rhyme_tail("eyes")

    def test_tail_is_groupable(self):
        # analyze_rhyme_scheme only groups tails of length >= 2.
        assert len(_get_rhyme_tail("cry")) >= 2

    def test_unstressed_y_left_alone(self):
        # "baby", "city": the final y sounds like "ee", not "eye", so it must not join
        # the cry/sky group.
        assert _get_rhyme_tail("baby") != _get_rhyme_tail("cry")
        assert _get_rhyme_tail("city") != _get_rhyme_tail("sky")

    def test_vowel_y_words_unchanged(self):
        # A vowel before the 'y' is a different nucleus.
        assert _get_rhyme_tail("away") == _get_rhyme_tail("day")
        assert _get_rhyme_tail("away") != _get_rhyme_tail("cry")


class TestAnalyzeRhymeSchemeConsonantY:
    """The scheme reports a consonant + 'y' rhyme as a rhyme."""

    STANZA = (
        "[Chorus]\n"
        "I watch the morning sky\n"
        "And never wonder why\n"
        "The stars refuse to cry\n"
        "Beneath the open sky\n"
    )

    def test_scheme_is_aaaa(self):
        result = json.loads(_run(analyze_rhyme_scheme(self.STANZA)))
        assert result["sections"][0]["scheme"] == "AAAA"

    def test_cry_and_lie_pair_up(self):
        stanza = (
            "[Verse]\n"
            "I hear the lonely cry\n"
            "I walk along the shore\n"
            "I will not tell a lie\n"
            "I could not ask for more\n"
        )
        result = json.loads(_run(analyze_rhyme_scheme(stanza)))
        assert result["sections"][0]["scheme"] == "ABAB"

    def test_short_tail_floor_still_holds(self):
        # "go" / "do" share the one-letter tail "o" but do not rhyme; the
        # length floor that keeps them apart must still apply.
        stanza = "[Verse]\nI have to go\nI know what to do\n"
        result = json.loads(_run(analyze_rhyme_scheme(stanza)))
        groups = [ln["rhyme_group"] for ln in result["sections"][0]["lines"]]
        assert groups[0] != groups[1]
