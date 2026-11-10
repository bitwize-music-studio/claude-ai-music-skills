#!/usr/bin/env python3
"""What create_track leaves behind on a brand-new track.

A track made by ``create_track`` used to need three rows edited by hand before
the plugin's own checks would accept it, and a title with punctuation produced
a filename with the punctuation still in it (``04-it's-a-bicycle.md``):

* ``| **Sources Verified** | ❌ Pending |`` blocked the Sources gate on an
  album with no sources at all.
* ``| **Explicit** | Yes / No |`` stayed a placeholder while the frontmatter
  two lines above it had already been given the album's value.
* ``| **Album** | [[Album Title]](../README.md) |`` copied the album README's
  own unfilled template title.

The acceptance test is the one at the bottom: on a non-documentary album the
only gates a new track fails are the two about lyrics and style that nobody
has written yet.

Usage:
    python -m pytest tests/unit/state/test_create_track_scaffold.py -v
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

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed (same pattern as test_create_track_validation.py)
# ---------------------------------------------------------------------------

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
    spec = importlib.util.spec_from_file_location("state_server_create_track_scaffold", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import gates as _gates_mod  # noqa: E402
from handlers import status as _status_mod  # noqa: E402
from tools.state.parsers import parse_track_file  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


class MockStateCache:
    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state

    def rebuild(self) -> dict:
        return self._state


@pytest.fixture
def make_album(tmp_path: Path):
    """Build one album on disk and install a mock cache that knows it.

    Returns a factory so each test states only what matters to it: the album's
    title, its explicit flag, and whether it carries a SOURCES.md.
    """
    orig_cache = _shared_mod.cache
    orig_plugin_root = _shared_mod.PLUGIN_ROOT

    def factory(*, title: str = "Test Album", explicit: bool = False,
                sources: bool = False, extra: tuple[str, ...] = ()) -> Path:
        album_dir = (
            tmp_path / "content" / "artists" / "test-artist" / "albums" / "pop" / "test-album"
        )
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)
        (album_dir / "README.md").write_text(f"# {title}\n", encoding="utf-8")
        if sources:
            (album_dir / "SOURCES.md").write_text("# Sources\n", encoding="utf-8")
        for name in extra:  # a name with a suffix is a file, without one a folder
            if Path(name).suffix:
                (album_dir / name).write_text("notes\n", encoding="utf-8")
            else:
                (album_dir / name).mkdir()
        state = {
            "version": 2,
            "config": {
                "content_root": str(tmp_path / "content"),
                "artist_name": "test-artist",
                "generation": {},
            },
            "albums": {
                "test-album": {
                    "title": title,
                    "status": "In Progress",
                    "genre": "pop",
                    "explicit": explicit,
                    "path": str(album_dir),
                    "track_count": 0,
                    "tracks_completed": 0,
                    "tracks": {},
                },
            },
            "session": {},
        }
        _shared_mod.cache = MockStateCache(state)
        _shared_mod.PLUGIN_ROOT = PROJECT_ROOT  # the real templates/track.md
        return tracks_dir

    yield factory

    _shared_mod.cache = orig_cache
    _shared_mod.PLUGIN_ROOT = orig_plugin_root


def _create(title: str = "My New Track", number: int = 1, documentary: bool = False) -> dict:
    return json.loads(_run(
        _status_mod.create_track("test-album", number, title, documentary=documentary)
    ))


def _row(content: str, key: str) -> str:
    """The Track Details row for *key*, e.g. ``| **Explicit** | No |``."""
    return next(line for line in content.splitlines() if line.startswith(f"| **{key}** |"))


def _created_text(result: dict) -> str:
    assert result.get("created") is True, result
    return Path(result["path"]).read_text(encoding="utf-8")


# ===========================================================================
# Sources Verified
# ===========================================================================


class TestSourcesVerifiedRow:
    def test_na_on_an_album_with_no_sources(self, make_album):
        make_album()
        content = _created_text(_create())
        assert _row(content, "Sources Verified") == "| **Sources Verified** | N/A |"

    def test_pending_on_a_documentary_track(self, make_album):
        make_album(sources=True)
        content = _created_text(_create(documentary=True))
        assert _row(content, "Sources Verified") == "| **Sources Verified** | ❌ Pending |"

    def test_pending_when_the_album_has_a_sources_file(self, make_album):
        """documentary=False on an album that keeps sources still waits for a human."""
        make_album(sources=True)
        content = _created_text(_create(documentary=False))
        assert _row(content, "Sources Verified") == "| **Sources Verified** | ❌ Pending |"

    def test_pending_when_documentary_is_asked_for_without_a_sources_file(self, make_album):
        make_album(sources=False)
        content = _created_text(_create(documentary=True))
        assert _row(content, "Sources Verified") == "| **Sources Verified** | ❌ Pending |"

    @pytest.mark.parametrize("kept", [
        "RESEARCH.md", "research", "primary-sources", "marriott-breach-sources.md",
        "DEFENDANTS-RESEARCH.md", "Sources.md",
    ])
    def test_pending_when_the_album_keeps_research_under_another_name(self, make_album, kept):
        """Most research-backed albums have a RESEARCH.md or research/ and no SOURCES.md.

        Writing N/A there would let a new track through the source-verification
        gate, and keep it off the list of pending verifications, without a human
        ever looking at it.
        """
        make_album(extra=(kept,))
        content = _created_text(_create(documentary=False))
        assert _row(content, "Sources Verified") == "| **Sources Verified** | ❌ Pending |"

    def test_other_files_in_the_album_do_not_count_as_research(self, make_album):
        make_album(extra=("promo", "notes.md", "album-art.png"))
        content = _created_text(_create(documentary=False))
        assert _row(content, "Sources Verified") == "| **Sources Verified** | N/A |"


# ===========================================================================
# Explicit
# ===========================================================================


class TestExplicitRow:
    def test_no_on_a_clean_album(self, make_album):
        make_album(explicit=False)
        content = _created_text(_create())
        assert _row(content, "Explicit") == "| **Explicit** | No |"
        assert "explicit: false" in content

    def test_yes_on_an_explicit_album(self, make_album):
        make_album(explicit=True)
        content = _created_text(_create())
        assert _row(content, "Explicit") == "| **Explicit** | Yes |"
        assert "explicit: true" in content

    def test_the_placeholder_is_gone(self, make_album):
        make_album()
        assert "Yes / No" not in _row(_created_text(_create()), "Explicit")


# ===========================================================================
# Album
# ===========================================================================


class TestAlbumRow:
    def test_links_the_album_title(self, make_album):
        make_album(title="A Very Vulnerable Christmas")
        content = _created_text(_create())
        assert _row(content, "Album") == "| **Album** | [A Very Vulnerable Christmas](../README.md) |"

    @pytest.mark.parametrize("unset", ["[Album Title]", "", "   "])
    def test_falls_back_to_the_slug_while_the_album_is_untitled(self, make_album, unset):
        """A README that is still templates/album.md has the title "[Album Title]"."""
        make_album(title=unset)
        content = _created_text(_create())
        assert _row(content, "Album") == "| **Album** | [test-album](../README.md) |"
        assert "[[" not in content


# ===========================================================================
# Filename
# ===========================================================================


class TestFilenameFromTitle:
    @pytest.mark.parametrize("title, slug", [
        ("It's a Bicycle", "its-a-bicycle"),
        ("Don’t Stop", "dont-stop"),                 # typographic apostrophe
        ("Everybody's Nice", "everybodys-nice"),
        ("Part 2: The Return", "part-2-the-return"),
        ('Say "Goodbye"', "say-goodbye"),
        ("“Quoted” Title", "quoted-title"),      # typographic quotes
        ("Why?", "why"),
        ("Rock & Roll, Baby!", "rock-roll-baby"),
        ("Either/Or", "either-or"),
        ("Back\\Slash", "back-slash"),
        ("snake_case title", "snake-case-title"),
        ("  Padded   Title  ", "padded-title"),
        ("Wait... What", "wait-what"),
        ("My New Track", "my-new-track"),
    ])
    def test_punctuation_never_reaches_the_filename(self, make_album, title, slug):
        tracks_dir = make_album()
        result = _create(title, number=4)
        assert result.get("created") is True, result
        assert result["filename"] == f"04-{slug}.md"
        assert result["track_slug"] == f"04-{slug}"
        assert (tracks_dir / f"04-{slug}.md").exists()

    @pytest.mark.parametrize("title, slug", [
        ("Café del Mar", "café-del-mar"),
        ("Über Alles", "über-alles"),
        ("한국어 제목", "한국어-제목"),
        ("夜に駆ける", "夜に駆ける"),
        ("हिंदी गीत", "हिंदी-गीत"),                       # combining vowel signs stay attached
    ])
    def test_letters_of_any_script_are_kept(self, make_album, title, slug):
        make_album()
        result = _create(title, number=2)
        assert result.get("created") is True, result
        assert result["filename"] == f"02-{slug}.md"

    def test_the_title_itself_is_untouched(self, make_album):
        """Only the filename is cleaned; the heading and frontmatter keep the title."""
        make_album()
        content = _created_text(_create("It's a Bicycle"))
        assert content.splitlines()[1] == 'title: "It\'s a Bicycle"'
        assert "# It's a Bicycle" in content
        assert _row(content, "Title") == "| **Title** | It's a Bicycle |"

    @pytest.mark.parametrize("title", ["???", "...", "   ", "!!!", "’’"])
    def test_a_title_with_no_letters_or_digits_is_refused(self, make_album, title):
        tracks_dir = make_album()
        result = _create(title)
        assert "error" in result
        assert "title" in result["error"].lower()
        assert list(tracks_dir.iterdir()) == []

    def test_a_track_filed_under_the_old_spelling_still_counts_as_existing(self, make_album):
        """Tracks made before this change kept their punctuation in the name."""
        tracks_dir = make_album()
        (tracks_dir / "04-it's-a-bicycle.md").write_text("stub", encoding="utf-8")
        result = _create("It's a Bicycle", number=4)
        assert result["created"] is False
        assert "already exists" in result["error"]
        assert sorted(p.name for p in tracks_dir.iterdir()) == ["04-it's-a-bicycle.md"]

    def test_invisible_joiners_do_not_split_a_word(self, make_album):
        """A Persian title's zero-width non-joiner is dropped, not hyphenated."""
        make_album()
        result = _create("\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645", number=2)
        assert result.get("created") is True, result
        assert result["filename"] == "02-\u0645\u06cc\u062e\u0648\u0627\u0647\u0645.md"

    def test_a_traversal_attempt_cannot_leave_the_tracks_folder(self, make_album):
        tracks_dir = make_album()
        result = _create("../../etc/passwd")
        assert result.get("created") is True, result
        assert Path(result["path"]).parent == tracks_dir
        assert result["filename"] == "01-etc-passwd.md"


# ===========================================================================
# Acceptance: what a new track fails
# ===========================================================================


class TestANewTrackAtTheGates:
    def _gates(self, result: dict) -> dict:
        path = Path(result["path"])
        text = path.read_text(encoding="utf-8")
        _, _, gates = _gates_mod._check_pre_gen_gates_for_track(
            parse_track_file(path), text, blocklist=[],
        )
        return {g["gate"]: g["status"] for g in gates}

    def test_only_the_unwritten_lyrics_and_style_block_it(self, make_album):
        make_album()
        gates = self._gates(_create("It's a Bicycle", number=4))
        failing = sorted(name for name, status in gates.items() if status == "FAIL")
        assert failing == ["Lyrics Reviewed", "Style Prompt Complete"]

    def test_a_documentary_track_also_waits_for_its_sources(self, make_album):
        make_album(sources=True)
        gates = self._gates(_create(documentary=True))
        assert gates["Sources Verified"] == "FAIL"


class TestANewTrackAtTheHook:
    """Writing the file back unchanged must not trip the plugin's own hook."""

    def test_a_verbatim_write_passes_validate_track(self, make_album):
        hook_path = PROJECT_ROOT / "hooks" / "validate_track.py"
        spec = importlib.util.spec_from_file_location("validate_track_hook_scaffold", hook_path)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)

        make_album()
        result = _create("It's a Bicycle", number=4)
        event = {
            "tool_name": "Write",
            "tool_input": {"file_path": result["path"], "content": _created_text(result)},
        }
        assert hook.is_track_file(result["path"]) is True
        assert hook.validate(event) == []
