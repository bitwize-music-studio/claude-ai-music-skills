#!/usr/bin/env python3
"""Regression tests for issue #396 — rhyme-tail spelling normalization.

_get_rhyme_tail derived a rhyme key from spelling, but the plural-strip
(dropping a trailing 's') ran before the vowel-cluster logic, so clearly
rhyming end-word pairs landed in different tails:

    "eyes"  -> "eye"  vs "cries" -> "ie"    (no match)
    "times" -> "ime"  vs "rhymes" -> "yme"  (no match)

These tests pin the fix: rhyming pairs must share a tail (and a rhyme
group), while genuinely non-rhyming pairs must stay distinct.

Usage:
    python -m pytest tests/unit/state/test_rhyme_tail_396.py -v
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
    spec = importlib.util.spec_from_file_location("state_server_rhyme396", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_server = _import_server()
from handlers import lyrics_analysis as _lyrics_analysis_mod

_get_rhyme_tail = _lyrics_analysis_mod._get_rhyme_tail
analyze_rhyme_scheme = _lyrics_analysis_mod.analyze_rhyme_scheme


def _run(coro):
    return asyncio.run(coro)


class TestRhymeTailNormalization396:
    """_get_rhyme_tail must fold spelling variants of the same rhyme sound."""

    def test_eyes_cries_share_tail(self):
        # Both /aɪz/ — the plural-strip must not split "eye" from "ie".
        assert _get_rhyme_tail("eyes") == _get_rhyme_tail("cries")

    def test_times_rhymes_share_tail(self):
        # Both /aɪmz/ — the y/i spelling difference must not split them.
        assert _get_rhyme_tail("times") == _get_rhyme_tail("rhymes")

    def test_non_rhyme_pair_stays_distinct(self):
        # "eyes" and "cat" do not rhyme — the fix must not over-broaden.
        assert _get_rhyme_tail("eyes") != _get_rhyme_tail("cat")

    def test_tails_have_groupable_length(self):
        # analyze_rhyme_scheme only groups tails of length >= 2, so the
        # normalized tails for these pairs must clear that bar.
        assert len(_get_rhyme_tail("eyes")) >= 2
        assert len(_get_rhyme_tail("times")) >= 2


class TestAnalyzeRhymeScheme396:
    """analyze_rhyme_scheme must report the corrected scheme for #396 pairs."""

    STANZA = (
        "[Verse]\n"
        "I cannot hide behind my eyes\n"
        "The lonely stranger softly cries\n"
        "I've heard this melody a thousand times\n"
        "The quiet poet speaks in rhymes\n"
    )

    def test_scheme_is_aabb(self):
        result = json.loads(_run(analyze_rhyme_scheme(self.STANZA)))
        section = result["sections"][0]
        assert section["scheme"] == "AABB"

    def test_rhyming_pairs_grouped(self):
        result = json.loads(_run(analyze_rhyme_scheme(self.STANZA)))
        lines = result["sections"][0]["lines"]
        # eyes/cries share a group; times/rhymes share a group...
        assert lines[0]["rhyme_group"] == lines[1]["rhyme_group"]
        assert lines[2]["rhyme_group"] == lines[3]["rhyme_group"]
        # ...and the two pairs are distinct groups.
        assert lines[0]["rhyme_group"] != lines[2]["rhyme_group"]

    def test_end_words_captured(self):
        result = json.loads(_run(analyze_rhyme_scheme(self.STANZA)))
        end_words = [ld["end_word"] for ld in result["sections"][0]["lines"]]
        assert end_words == ["eyes", "cries", "times", "rhymes"]
