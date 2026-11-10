#!/usr/bin/env python3
"""check_album_lyrics: the lyric checks, across an album, in one call.

The six lyric checks (syllables, rhyme, structure, readability, homographs,
explicit words) each take pasted text, one track at a time. A ten-track album
needed about sixty calls per pass, each one pasting a lyric sheet, so a session
polishing an album ended up importing the handler functions from a script of
its own instead.

``check_album_lyrics`` reads each track's Lyrics Box itself, runs the same six
checks, and returns only what is wrong.

Usage:
    python -m pytest tests/unit/state/test_check_album_lyrics.py -v
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

try:
    import mcp.server.fastmcp  # noqa: F401
except ImportError:
    class _FakeFastMCP:
        def __init__(self, name: str = "", **kwargs: object) -> None:
            self.name = name
            self._tools: dict = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self, transport: str = "stdio") -> None:
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
    spec = importlib.util.spec_from_file_location("state_server_check_album_lyrics", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import lyrics_analysis as _lyrics_mod  # noqa: E402


def _run(coro):
    return json.loads(asyncio.run(coro))


class MockStateCache:
    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state

    def rebuild(self) -> dict:
        return self._state


# A sheet with the shape a normal song has: an instrumental intro, a chorus sung
# twice under the same tag, an instrumental break, and [End]. Every one of those
# used to be reported as a problem.
CLEAN_LYRICS = """\
[Intro - soft piano]

[Verse 1 - calm]
Morning light across the floor
Coffee waiting by the door
Every window open wide
Nothing left for us to hide

[Chorus - bright]
We are running to the sun
We have only just begun

[Break - baritone sax]

[Verse 2 - warm]
Evening settles on the town
Shadows slowly drifting down
Every street is glowing gold
Stories waiting to be told

[Chorus - bright]
We are running to the sun
We have only just begun

[End]"""

# One of everything: a homograph (live), a word rhymed with itself (night), an
# explicit word on a track flagged clean, a verse whose lines swing from one
# syllable to twenty, an empty chorus, and verses of four lines and one.
PROBLEM_LYRICS = """\
[Verse 1]
I want to live inside the night
We dance until the morning night
The shit we carried all the way from there to here and back again is heavy now
Go

[Chorus]

[Verse 2]
Another line to end it right"""

INSTRUMENTAL_LYRICS = "[Intro]\n\n[Main Theme]\n\n[End]"

TEMPLATE_LYRICS = "[Verse 1 - calm reflective]\n[Lyrics here...]\n\n[Chorus - big anthemic]\n[Lyrics here...]"


def _track_file(title: str, lyrics: str, *, instrumental: bool = False,
                frontmatter: bool = True) -> str:
    head = ""
    if frontmatter:
        head = (
            f'---\ntitle: "{title}"\ntrack_number: 1\n'
            f'instrumental: {"true" if instrumental else "false"}\nexplicit: false\n---\n\n'
        )
    return (
        f"{head}# {title}\n\n## Track Details\n\n"
        "| Attribute | Detail |\n|-----------|--------|\n"
        "| **Status** | In Progress |\n"
        f"| **Instrumental** | {'Yes' if instrumental else 'No'} |\n"
        "| **Explicit** | No |\n\n"
        "## Suno Inputs\n\n### Style Box\n\n```\nbright pop, 110 BPM\n```\n\n"
        f"### Lyrics Box\n\n```\n{lyrics}\n```\n"
    )


@pytest.fixture
def album(tmp_path: Path):
    """Write tracks to disk and install a cache that knows them.

    Call it with ``{slug: (lyrics, options)}``; options are passed to
    ``_track_file`` except ``explicit``, which sets the cached flag.
    """
    orig_cache = _shared_mod.cache

    def build(tracks: dict[str, tuple[str, dict]]) -> None:
        tracks_dir = tmp_path / "album" / "tracks"
        tracks_dir.mkdir(parents=True, exist_ok=True)
        state_tracks = {}
        for slug, (lyrics, options) in tracks.items():
            options = dict(options)
            explicit = options.pop("explicit", False)
            path = tracks_dir / f"{slug}.md"
            path.write_text(_track_file(slug, lyrics, **options), encoding="utf-8")
            state_tracks[slug] = {
                "path": str(path), "title": slug.split("-", 1)[1].replace("-", " ").title(),
                "status": "In Progress", "explicit": explicit,
            }
        state = {
            "version": 2,
            "config": {"content_root": str(tmp_path), "artist_name": "test-artist"},
            "albums": {"test-album": {
                "title": "Test Album", "status": "In Progress", "genre": "pop",
                "path": str(tmp_path / "album"), "tracks": state_tracks,
            }},
            "session": {},
        }
        _shared_mod.cache = MockStateCache(state)

    yield build

    _shared_mod.cache = orig_cache


def _by_slug(result: dict) -> dict:
    return {t["track_slug"]: t for t in result["tracks"]}


THREE_TRACKS = {
    "01-clean-song": (CLEAN_LYRICS, {}),
    "02-problem-song": (PROBLEM_LYRICS, {}),
    "03-theme": (INSTRUMENTAL_LYRICS, {"instrumental": True}),
}


# ===========================================================================
# One call, every vocal track
# ===========================================================================


class TestOneCallCoversTheAlbum:
    def test_every_track_is_listed_in_order(self, album):
        album(THREE_TRACKS)
        result = _run(_lyrics_mod.check_album_lyrics("test-album"))
        assert result["found"] is True
        assert result["album_slug"] == "test-album"
        assert [t["track_slug"] for t in result["tracks"]] == [
            "01-clean-song", "02-problem-song", "03-theme",
        ]

    def test_an_instrumental_track_is_skipped_not_reported(self, album):
        album(THREE_TRACKS)
        theme = _by_slug(_run(_lyrics_mod.check_album_lyrics("test-album")))["03-theme"]
        assert theme["checked"] is False
        assert theme["skipped"] == "instrumental"
        assert "structure" not in theme

    def test_an_instrumental_marked_only_in_the_table_is_skipped_too(self, album):
        """Older tracks have no frontmatter; the Track Details row says it."""
        album({"01-theme": (INSTRUMENTAL_LYRICS, {"instrumental": True, "frontmatter": False})})
        track = _run(_lyrics_mod.check_album_lyrics("test-album"))["tracks"][0]
        assert track["skipped"] == "instrumental"

    def test_an_unwritten_track_is_skipped(self, album):
        album({"01-new": (TEMPLATE_LYRICS, {})})
        track = _run(_lyrics_mod.check_album_lyrics("test-album"))["tracks"][0]
        assert track["checked"] is False
        assert track["skipped"] == "no lyrics"

    def test_the_summary_counts_them(self, album):
        album(THREE_TRACKS)
        summary = _run(_lyrics_mod.check_album_lyrics("test-album"))["summary"]
        assert summary["tracks"] == 3
        assert summary["checked"] == 2
        assert summary["skipped"] == 1
        assert summary["clean"] == 1
        assert summary["with_findings"] == 1

    def test_one_track_can_be_asked_for(self, album):
        album(THREE_TRACKS)
        result = _run(_lyrics_mod.check_album_lyrics("test-album", "02"))
        assert [t["track_slug"] for t in result["tracks"]] == ["02-problem-song"]

    def test_an_unknown_album_is_an_error_not_a_crash(self, album):
        album(THREE_TRACKS)
        result = _run(_lyrics_mod.check_album_lyrics("no-such-album"))
        assert result.get("found") is False or "error" in result

    def test_an_unknown_track_is_an_error_not_a_crash(self, album):
        album(THREE_TRACKS)
        result = _run(_lyrics_mod.check_album_lyrics("test-album", "99"))
        assert result.get("found") is False or "error" in result


# ===========================================================================
# Only what is wrong
# ===========================================================================


class TestACleanTrack:
    def test_a_normal_song_shape_is_clean(self, album):
        """Intro, repeated chorus, break and [End]: nothing to report."""
        album(THREE_TRACKS)
        clean = _by_slug(_run(_lyrics_mod.check_album_lyrics("test-album")))["01-clean-song"]
        assert clean["checked"] is True
        assert clean["clean"] is True
        assert clean["findings"] == 0

    def test_it_carries_no_check_blocks(self, album):
        album(THREE_TRACKS)
        clean = _by_slug(_run(_lyrics_mod.check_album_lyrics("test-album")))["01-clean-song"]
        for block in ("syllables", "rhyme", "structure", "homographs", "explicit", "readability"):
            assert block not in clean, block


class TestAProblemTrack:
    @pytest.fixture
    def problem(self, album):
        album(THREE_TRACKS)
        return _by_slug(_run(_lyrics_mod.check_album_lyrics("test-album")))["02-problem-song"]

    def test_it_is_not_clean(self, problem):
        assert problem["checked"] is True
        assert problem["clean"] is False
        assert problem["findings"] >= 5

    def test_the_homograph_is_named_with_its_line_and_options(self, problem):
        found = problem["homographs"]
        assert [h["word"] for h in found] == ["live"]
        assert found[0]["line_number"] == 2
        assert found[0]["line"] == "I want to live inside the night"
        assert found[0]["options"]

    def test_the_self_rhyme_is_reported(self, problem):
        issues = problem["rhyme"]["issues"]
        assert [(i["type"], i["word"], i["line_numbers"]) for i in issues] == [
            ("self_rhyme", "night", [2, 3]),
        ]

    def test_the_empty_chorus_and_the_lopsided_verses_are_reported(self, problem):
        kinds = sorted(i["type"] for i in problem["structure"]["issues"])
        assert kinds == ["empty_section", "unbalanced_sections"]
        assert problem["structure"]["section_balance"] == "UNBALANCED"

    def test_the_explicit_word_on_a_clean_track_is_a_mismatch(self, problem):
        explicit = problem["explicit"]
        assert explicit["flagged"] is False
        assert explicit["mismatch"] is True
        assert [w["word"] for w in explicit["words"]] == ["shit"]
        assert explicit["words"][0]["lines"][0]["line_number"] == 4

    def test_the_uneven_verse_is_reported_with_its_lines(self, problem):
        uneven = problem["syllables"]["uneven_sections"]
        assert [s["section"] for s in uneven] == ["Verse 1"]
        counts = [line["syllable_count"] for line in uneven[0]["lines"]]
        assert len(counts) == 4
        assert max(counts) - min(counts) > 10

    def test_the_summary_says_which_checks_fired(self, album):
        album(THREE_TRACKS)
        by_check = _run(_lyrics_mod.check_album_lyrics("test-album"))["summary"]["by_check"]
        assert by_check == {
            "syllables": 1, "rhyme": 1, "structure": 1,
            "homographs": 1, "explicit": 1, "readability": 0,
        }


class TestExplicitWordsAndTheFlag:
    def test_explicit_words_on_an_explicit_track_are_not_a_finding(self, album):
        album({"01-loud": (CLEAN_LYRICS.replace("Coffee waiting", "Shit is waiting"), {"explicit": True})})
        track = _run(_lyrics_mod.check_album_lyrics("test-album"))["tracks"][0]
        assert track["clean"] is True
        assert "explicit" not in track

    def test_verbose_shows_them_anyway(self, album):
        album({"01-loud": (CLEAN_LYRICS.replace("Coffee waiting", "Shit is waiting"), {"explicit": True})})
        track = _run(_lyrics_mod.check_album_lyrics("test-album", verbose=True))["tracks"][0]
        assert track["explicit"]["flagged"] is True
        assert track["explicit"]["mismatch"] is False
        assert [w["word"] for w in track["explicit"]["words"]] == ["shit"]


class TestVerbose:
    def test_a_clean_track_gets_its_full_readout(self, album):
        album(THREE_TRACKS)
        result = _run(_lyrics_mod.check_album_lyrics("test-album", verbose=True))
        clean = _by_slug(result)["01-clean-song"]
        assert clean["clean"] is True
        assert clean["syllables"]["consistency"] in ("CONSISTENT", "UNEVEN")
        assert clean["readability"]["grade_level"]
        schemes = clean["rhyme"]["schemes"]
        assert [(s["section"], s["occurrence"]) for s in schemes] == [
            ("Verse 1 - calm", 1), ("Chorus - bright", 1),
            ("Verse 2 - warm", 1), ("Chorus - bright", 2),
        ]
        assert "spelling" in clean["rhyme"]["note"].lower()

    def test_info_level_notes_only_appear_in_verbose(self, album):
        """A song with no chorus is a note, not a problem."""
        lyrics = CLEAN_LYRICS.replace("[Chorus - bright]", "[Bridge - bright]")
        album({"01-through-composed": (lyrics, {})})
        quiet = _run(_lyrics_mod.check_album_lyrics("test-album"))["tracks"][0]
        loud = _run(_lyrics_mod.check_album_lyrics("test-album", verbose=True))["tracks"][0]
        assert quiet["clean"] is True
        assert "structure" not in quiet
        assert [i["type"] for i in loud["structure"]["issues"]] == ["missing_chorus"]
        assert loud["clean"] is True


class TestItIsARegisteredTool:
    def test_the_server_exposes_it(self):
        assert callable(getattr(server, "check_album_lyrics", None))
