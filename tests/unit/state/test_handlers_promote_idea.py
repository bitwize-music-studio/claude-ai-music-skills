#!/usr/bin/env python3
"""Unit tests for handlers/ideas.py — promote_idea MCP tool.

Tests the promotion workflow: find idea → create album → inject concept →
update idea status + promoted_to link. Uses a real temp content_root and
the real templates/ directory from the project so we test end-to-end behavior.

Usage:
    python -m pytest tests/unit/state/test_handlers_promote_idea.py -v
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import logging
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# Mock the MCP SDK if not installed
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
    spec = importlib.util.spec_from_file_location("state_server_ideas", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import ideas as _ideas_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_state(content_root: Path, items: list[dict]) -> dict:
    """Build a minimal state dict for ideas-handler tests."""
    counts: dict[str, int] = {}
    for item in items:
        status = item.get("status", "Pending")
        counts[status] = counts.get(status, 0) + 1
    return {
        "version": 2,
        "config": {
            "content_root": str(content_root),
            "artist_name": "test-artist",
            "generation": {},
        },
        "albums": {},
        "ideas": {
            "counts": counts,
            "items": items,
            "total": len(items),
        },
        "session": {},
    }


class MockStateCache:
    def __init__(self, state: dict) -> None:
        self._state = state
        self.rebuild_called = 0

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state

    def rebuild(self):
        self.rebuild_called += 1
        return self._state


def _write_ideas_md(content_root: Path, body: str) -> Path:
    """Write an IDEAS.md file to the content root."""
    ideas_path = content_root / "IDEAS.md"
    ideas_path.parent.mkdir(parents=True, exist_ok=True)
    ideas_path.write_text(body, encoding="utf-8")
    return ideas_path


def _standard_ideas_md(title: str, genre: str, concept: str, status: str = "Pending") -> str:
    return f"""# Album Ideas

## Pending

### {title}
**Genre**: {genre}
**Type**: Thematic
**Concept**: {concept}
**Status**: {status}
"""


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    """Temp content root with an empty artist directory."""
    root = tmp_path / "content"
    (root / "artists" / "test-artist").mkdir(parents=True)
    return root


@pytest.fixture
def setup_handler(content_root: Path):
    """Set up _shared.cache and PLUGIN_ROOT, restore afterwards."""
    orig_cache = _shared_mod.cache
    orig_plugin_root = _shared_mod.PLUGIN_ROOT
    _shared_mod.PLUGIN_ROOT = PROJECT_ROOT

    def _configure(items: list[dict]) -> MockStateCache:
        state = _make_state(content_root, items)
        cache = MockStateCache(state)
        _shared_mod.cache = cache
        return cache

    yield _configure

    _shared_mod.cache = orig_cache
    _shared_mod.PLUGIN_ROOT = orig_plugin_root


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestPromoteIdeaHappyPath:
    def test_creates_album_and_returns_path(self, content_root: Path, setup_handler):
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "A minimalist journey through inner landscapes.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic",
                               "A minimalist journey through inner landscapes."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert result["promoted"] is True
        assert result["slug"] == "kleine-welt"
        assert result["genre"] == "electronic"
        album_path = Path(result["album_path"])
        assert album_path.exists()
        assert (album_path / "README.md").exists()
        assert (album_path / "tracks").is_dir()

    def test_status_transitions_to_in_progress(self, content_root: Path, setup_handler):
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Minimalist journey.",
            "status": "Pending",
        }])
        ideas_path = _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Minimalist journey."),
        )

        _run(_ideas_mod.promote_idea("Kleine Welt"))

        text = ideas_path.read_text(encoding="utf-8")
        assert "**Status**: In Progress" in text

    def test_promoted_to_link_is_recorded(self, content_root: Path, setup_handler):
        """After promotion, IDEAS.md carries a promoted_to pointer to the album slug."""
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Minimalist journey.",
            "status": "Pending",
        }])
        ideas_path = _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Minimalist journey."),
        )

        _run(_ideas_mod.promote_idea("Kleine Welt"))

        text = ideas_path.read_text(encoding="utf-8")
        assert "**Promoted To**: kleine-welt" in text

    def test_concept_injected_into_readme(self, content_root: Path, setup_handler):
        concept = "A minimalist journey through inner landscapes of the self."
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": concept,
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", concept),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        readme = (Path(result["album_path"]) / "README.md").read_text(encoding="utf-8")
        assert concept in readme


# ---------------------------------------------------------------------------
# Slug derivation
# ---------------------------------------------------------------------------


class TestPromoteIdeaSlugDerivation:
    def test_auto_derives_slug_from_simple_title(self, content_root: Path, setup_handler):
        setup_handler([{
            "title": "Midnight Drive",
            "genre": "electronic",
            "concept": "Neon-lit highway tales.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Midnight Drive", "electronic", "Neon-lit highway tales."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Midnight Drive")))

        assert result["slug"] == "midnight-drive"

    def test_strips_diacritics(self, content_root: Path, setup_handler):
        """Diacritics should be stripped, not replaced with hyphens."""
        setup_handler([{
            "title": "Ängstliche Kätzchen",
            "genre": "folk",
            "concept": "Scared kittens, gentle folk.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Ängstliche Kätzchen", "folk", "Scared kittens, gentle folk."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Ängstliche Kätzchen")))

        assert result["slug"] == "angstliche-katzchen"

    def test_strips_punctuation(self, content_root: Path, setup_handler):
        setup_handler([{
            "title": "Who's Next? The Reckoning!",
            "genre": "rock",
            "concept": "Punctuation torture test.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Who's Next? The Reckoning!", "rock",
                               "Punctuation torture test."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Who's Next? The Reckoning!")))

        assert result["slug"] == "whos-next-the-reckoning"

    def test_explicit_slug_overrides_auto(self, content_root: Path, setup_handler):
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Inner journey.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Inner journey."),
        )

        result = json.loads(_run(
            _ideas_mod.promote_idea("Kleine Welt", album_slug="custom-slug")
        ))

        assert result["slug"] == "custom-slug"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestPromoteIdeaErrors:
    def test_missing_idea_returns_error(self, content_root: Path, setup_handler):
        setup_handler([])
        _write_ideas_md(content_root, "# Album Ideas\n\n## Pending\n")

        result = json.loads(_run(_ideas_mod.promote_idea("Nonexistent Idea")))

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_idea_without_genre_returns_error(self, content_root: Path, setup_handler):
        """Idea without a genre cannot be promoted — create_album needs a genre."""
        setup_handler([{
            "title": "No Genre",
            "genre": "",
            "concept": "Something.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            "# Album Ideas\n\n## Pending\n\n### No Genre\n**Concept**: Something.\n**Status**: Pending\n",
        )

        result = json.loads(_run(_ideas_mod.promote_idea("No Genre")))

        assert "error" in result
        assert "genre" in result["error"].lower()

    def test_invalid_genre_returns_error(self, content_root: Path, setup_handler):
        """Invalid genre on the idea surfaces the create_album_structure error."""
        setup_handler([{
            "title": "Bad Genre",
            "genre": "not-a-real-genre",
            "concept": "Something.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Bad Genre", "not-a-real-genre", "Something."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Bad Genre")))

        assert "error" in result
        assert "genre" in result["error"].lower()

    def test_already_promoted_idea_returns_error(self, content_root: Path, setup_handler):
        """An idea already In Progress should not be promoted again."""
        setup_handler([{
            "title": "Already Active",
            "genre": "electronic",
            "concept": "Already working on it.",
            "status": "In Progress",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Already Active", "electronic", "Already working on it.",
                               status="In Progress"),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Already Active")))

        assert "error" in result
        assert "already" in result["error"].lower()

    def test_duplicate_slug_returns_error(self, content_root: Path, setup_handler):
        """If album directory already exists, surface the distinct error from create_album."""
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Inner journey.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Inner journey."),
        )
        # Pre-create the album directory to simulate duplicate slug
        existing = (content_root / "artists" / "test-artist" / "albums"
                    / "electronic" / "kleine-welt")
        existing.mkdir(parents=True)

        result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert "error" in result
        assert "exists" in result["error"].lower()

    def test_cross_genre_duplicate_slug_returns_error(self, content_root: Path, setup_handler):
        """Slug already used under a DIFFERENT genre blocks promotion (#392)."""
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Inner journey.",
            "status": "Pending",
        }])
        ideas_path = _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Inner journey."),
        )
        # Same slug exists under another genre
        existing = (content_root / "artists" / "test-artist" / "albums"
                    / "rock" / "kleine-welt")
        existing.mkdir(parents=True)

        result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert "error" in result
        assert "exists" in result["error"].lower()
        assert "rock" in result["error"]
        # No twin created under the idea's genre
        twin = (content_root / "artists" / "test-artist" / "albums"
                / "electronic" / "kleine-welt")
        assert not twin.exists()
        # Idea must not be marked promoted
        text = ideas_path.read_text(encoding="utf-8")
        assert "**Status**: Pending" in text
        assert "**Promoted To**" not in text


# ---------------------------------------------------------------------------
# Documentary flag
# ---------------------------------------------------------------------------


class TestPromoteIdeaDocumentary:
    def test_documentary_creates_research_files(self, content_root: Path, setup_handler):
        setup_handler([{
            "title": "The Heist",
            "genre": "hip-hop",
            "concept": "True crime narrative.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("The Heist", "hip-hop", "True crime narrative."),
        )

        result = json.loads(_run(
            _ideas_mod.promote_idea("The Heist", documentary=True)
        ))

        assert result["promoted"] is True
        album_path = Path(result["album_path"])
        assert (album_path / "RESEARCH.md").exists()
        assert (album_path / "SOURCES.md").exists()

    def test_standard_omits_research_files(self, content_root: Path, setup_handler):
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Inner journey.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Inner journey."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        album_path = Path(result["album_path"])
        assert not (album_path / "RESEARCH.md").exists()
        assert not (album_path / "SOURCES.md").exists()


# ---------------------------------------------------------------------------
# Review-driven coverage (#328 review I1/I2)
# ---------------------------------------------------------------------------


class TestPromoteIdeaMaliciousSlug:
    """I1: explicit album_slug with path-traversal chars must return a
    structured error, not raise ValueError from _normalize_slug."""

    @pytest.mark.parametrize("bad_slug", [
        "../../../etc/passwd",
        "../escaped",
        "evil/subdir",
        "evil\\subdir",
        "null\x00byte",
    ])
    def test_rejects_path_traversal_slug(
        self, content_root: Path, setup_handler, bad_slug: str,
    ):
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Inner journey.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Inner journey."),
        )

        # Must not raise — must return {"error": ...}.
        result = json.loads(_run(
            _ideas_mod.promote_idea("Kleine Welt", album_slug=bad_slug)
        ))

        assert "error" in result
        assert "invalid album_slug" in result["error"].lower()


class TestPromoteIdeaCaseMismatch:
    """I2: the cache lookup is case-insensitive, but update_idea and
    _set_promoted_to_field match the file case-sensitively. Use the canonical
    title from the cache for downstream mutators so a lowercase call against
    a title-case idea doesn't silently half-promote."""

    def test_lowercase_call_against_titlecase_idea_updates_ideas_md(
        self, content_root: Path, setup_handler,
    ):
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Inner journey.",
            "status": "Pending",
        }])
        ideas_path = _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Inner journey."),
        )

        # Caller passes lowercase even though IDEAS.md has title case.
        result = json.loads(_run(_ideas_mod.promote_idea("kleine welt")))

        assert result["promoted"] is True
        # Canonical title from cache is returned, not the lowercase input.
        assert result["idea_title"] == "Kleine Welt"

        # IDEAS.md must reflect both mutations — silent half-promotion
        # before the fix left both of these as no-ops.
        text = ideas_path.read_text(encoding="utf-8")
        assert "**Status**: In Progress" in text
        assert "**Promoted To**: kleine-welt" in text

    def test_uppercase_call_against_titlecase_idea_also_works(
        self, content_root: Path, setup_handler,
    ):
        setup_handler([{
            "title": "Kleine Welt",
            "genre": "electronic",
            "concept": "Inner journey.",
            "status": "Pending",
        }])
        ideas_path = _write_ideas_md(
            content_root,
            _standard_ideas_md("Kleine Welt", "electronic", "Inner journey."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea("KLEINE WELT")))

        assert result["promoted"] is True
        assert result["idea_title"] == "Kleine Welt"
        text = ideas_path.read_text(encoding="utf-8")
        assert "**Status**: In Progress" in text
        assert "**Promoted To**: kleine-welt" in text


class TestPromoteIdeaEmptyDerivedSlug:
    """Titles that reduce to nothing after NFKD-ASCII + punctuation-stripping
    must surface an explicit error rather than create an album at a slug that
    consists entirely of dashes (or nothing)."""

    @pytest.mark.parametrize("title", [
        "!!!",            # pure punctuation
        "???",            # pure punctuation
        "…",              # single non-ASCII char
        "   ",            # whitespace only after strip
    ])
    def test_empty_derived_slug_returns_error(
        self, content_root: Path, setup_handler, title: str,
    ):
        setup_handler([{
            "title": title,
            "genre": "electronic",
            "concept": "Edge case.",
            "status": "Pending",
        }])
        _write_ideas_md(
            content_root,
            _standard_ideas_md(title, "electronic", "Edge case."),
        )

        result = json.loads(_run(_ideas_mod.promote_idea(title)))

        # Either the lookup fails (title didn't round-trip) or the slug
        # derivation fails — both are acceptable, but never a silent success.
        assert "error" in result


# ---------------------------------------------------------------------------
# Follow-up failures after the album is created (#675)
# ---------------------------------------------------------------------------


_IDEA = {
    "title": "Kleine Welt",
    "genre": "electronic",
    "concept": "A minimalist journey.",
    "status": "Pending",
}


def _fail_writes_to(monkeypatch, name: str) -> None:
    """Make the ideas handler's atomic writes to files called *name* fail."""
    real = _ideas_mod.atomic_write_text

    def write(path, text):
        if Path(path).name == name:
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(_ideas_mod, "atomic_write_text", write)


class TestPromoteIdeaFollowUpFailures:
    """The album exists once created; a later step that fails is reported, never raised,
    and leaves the file it could not change as it was."""

    def test_readme_write_failure_reports_the_concept_not_injected(
        self, content_root: Path, setup_handler, monkeypatch,
    ):
        setup_handler([dict(_IDEA)])
        ideas_path = _write_ideas_md(
            content_root, _standard_ideas_md("Kleine Welt", "electronic", "A minimalist journey."),
        )
        _fail_writes_to(monkeypatch, "README.md")

        result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert result["promoted"] is True
        assert result["concept_injected"] is False
        readme = (Path(result["album_path"]) / "README.md").read_text(encoding="utf-8")
        assert "_Promoted from idea" not in readme
        # The rest of the promotion still happens.
        ideas = ideas_path.read_text(encoding="utf-8")
        assert "**Status**: In Progress" in ideas
        assert "**Promoted To**: kleine-welt" in ideas

    def test_ideas_md_write_failure_is_logged_and_leaves_it_intact(
        self, content_root: Path, setup_handler, monkeypatch, caplog,
    ):
        setup_handler([dict(_IDEA)])
        original = _standard_ideas_md("Kleine Welt", "electronic", "A minimalist journey.")
        ideas_path = _write_ideas_md(content_root, original)
        _fail_writes_to(monkeypatch, "IDEAS.md")

        with caplog.at_level(logging.WARNING, logger="handlers.ideas"):
            result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert result["promoted"] is True
        assert result["concept_injected"] is True
        assert ideas_path.read_text(encoding="utf-8") == original
        assert "status update failed for 'Kleine Welt': Cannot write IDEAS.md: disk full" in caplog.text
        assert "Promoted To back-link in IDEAS.md could not be written" in caplog.text

    def test_missing_ideas_md_is_logged_not_recreated(
        self, content_root: Path, setup_handler, caplog,
    ):
        """The cache still lists the idea but IDEAS.md is gone."""
        setup_handler([dict(_IDEA)])

        with caplog.at_level(logging.WARNING, logger="handlers.ideas"):
            result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert result["promoted"] is True
        assert Path(result["album_path"]).is_dir()
        assert not (content_root / "IDEAS.md").exists()
        assert "status update failed for 'Kleine Welt': IDEAS.md not found" in caplog.text
        assert "Promoted To back-link in IDEAS.md could not be written" in caplog.text

    def test_unreadable_ideas_md_is_logged_and_left_intact(
        self, content_root: Path, setup_handler, caplog,
    ):
        setup_handler([dict(_IDEA)])
        broken = _standard_ideas_md("Kleine Welt", "electronic", "A caf\xe9 journey.").encode("latin-1")
        ideas_path = content_root / "IDEAS.md"
        ideas_path.write_bytes(broken)

        with caplog.at_level(logging.WARNING, logger="handlers.ideas"):
            result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert result["promoted"] is True
        assert ideas_path.read_bytes() == broken
        assert "status update failed for 'Kleine Welt': Cannot read IDEAS.md" in caplog.text
        assert "Promoted To back-link in IDEAS.md could not be written" in caplog.text

    def test_cache_rebuild_failure_still_reports_the_promotion(
        self, content_root: Path, setup_handler, caplog,
    ):
        cache = setup_handler([dict(_IDEA)])
        ideas_path = _write_ideas_md(
            content_root, _standard_ideas_md("Kleine Welt", "electronic", "A minimalist journey."),
        )

        calls = []

        def rebuild_then_fail():
            # create_album_structure's own rebuild succeeds; the follow-up ones fail.
            calls.append(1)
            if len(calls) > 1:
                raise RuntimeError("state.json locked")
            return cache.get_state()

        cache.rebuild = rebuild_then_fail
        with caplog.at_level(logging.WARNING, logger="handlers.ideas"):
            result = json.loads(_run(_ideas_mod.promote_idea("Kleine Welt")))

        assert result["promoted"] is True
        assert "**Promoted To**: kleine-welt" in ideas_path.read_text(encoding="utf-8")
        assert "promote_idea: cache rebuild failed: state.json locked" in caplog.text
        assert len(calls) == 3  # album creation, the status update, the promotion


class TestPromotionHelpersRefuseCleanly:
    """The two IDEAS.md / README helpers return False and change nothing on failure."""

    def test_inject_concept_missing_or_unreadable_readme(self, tmp_path: Path):
        readme = tmp_path / "README.md"
        assert _ideas_mod._inject_concept_into_readme(readme, "T", "C") is False
        assert not readme.exists()
        readme.write_bytes(b"# Caf\xe9\n")
        assert _ideas_mod._inject_concept_into_readme(readme, "T", "C") is False
        assert readme.read_bytes() == b"# Caf\xe9\n"

    def test_inject_concept_write_failure(self, tmp_path: Path, monkeypatch):
        readme = tmp_path / "README.md"
        readme.write_text("# Album\n", encoding="utf-8")
        _fail_writes_to(monkeypatch, "README.md")
        assert _ideas_mod._inject_concept_into_readme(readme, "T", "C") is False
        assert readme.read_text(encoding="utf-8") == "# Album\n"

    def test_promoted_to_needs_the_idea_heading(
        self, content_root: Path, setup_handler,
    ):
        setup_handler([dict(_IDEA)])
        original = _standard_ideas_md("Other Idea", "electronic", "Something else.")
        ideas_path = _write_ideas_md(content_root, original)
        assert _ideas_mod._set_promoted_to_field("Kleine Welt", "kleine-welt") is False
        assert ideas_path.read_text(encoding="utf-8") == original

    def test_promoted_to_write_failure(
        self, content_root: Path, setup_handler, monkeypatch,
    ):
        setup_handler([dict(_IDEA)])
        original = _standard_ideas_md("Kleine Welt", "electronic", "A minimalist journey.")
        ideas_path = _write_ideas_md(content_root, original)
        _fail_writes_to(monkeypatch, "IDEAS.md")
        assert _ideas_mod._set_promoted_to_field("Kleine Welt", "kleine-welt") is False
        assert ideas_path.read_text(encoding="utf-8") == original
