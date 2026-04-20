"""Unit tests for _stage_status_update — master_album track/album status promotion.

Covers the #335 brittleness fix: previously the stage only promoted tracks from
``Generated → Final`` and skipped (with an error) any other starting status —
including ``Not Started``, ``In Progress``, ``Sources Pending``, ``Sources
Verified``, and already-``Released`` tracks. On a re-master of any album whose
track READMEs aren't pinned at exactly ``Generated``, this silently no-ops the
entire stage while still reporting ``status: "pass"``.

The fix:

1. Promote any non-terminal status (anything ``!= Final && != Released``) to
   ``Final`` — the mastered WAV is real, so the status should follow.
2. Leave ``Released`` tracks alone (terminal state, never demote).
3. Classify the stage outcome: ``pass`` when updates succeeded cleanly or
   everything was already terminal; ``partial`` when some updated and some
   were skipped with errors; ``skipped`` when zero updates and errors exist.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import sys
import types
from dataclasses import asdict
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path and MCP SDK stub is available
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

try:
    import mcp  # noqa: F401
except ImportError:
    class _FakeFastMCP:
        def __init__(self, name: str = "") -> None:
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


from handlers import _shared as _shared_mod  # noqa: E402
from handlers.processing._album_stages import (  # noqa: E402
    MasterAlbumCtx,
    _stage_status_update,
)
from tools.mastering.signature_persistence import SIGNATURE_FILENAME  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockCache:
    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state

    def get_state_ref(self) -> dict:
        return self._state


def _write_track_file(tracks_dir: Path, slug: str, title: str, status: str) -> Path:
    """Write a minimal track README whose **Status** row matches the given status."""
    tracks_dir.mkdir(parents=True, exist_ok=True)
    path = tracks_dir / f"{slug}.md"
    path.write_text(
        f"""---
title: "{title}"
---

# {title}

## Track Details

| **Title** | {title} |
| **Status** | {status} |
""",
        encoding="utf-8",
    )
    return path


def _build_state(
    content_root: Path,
    audio_root: Path,
    artist: str,
    genre: str,
    album_slug: str,
    album_title: str,
    album_status: str,
    tracks: list[tuple[str, str, str]],  # [(slug, title, status), ...]
) -> tuple[dict, Path, Path, Path]:
    """Create on-disk content + audio layouts, return state dict + audio_dir."""
    album_content = content_root / "artists" / artist / "albums" / genre / album_slug
    tracks_dir = album_content / "tracks"
    album_content.mkdir(parents=True)
    # Minimal album README — includes a Status row so the stage's regex matches.
    (album_content / "README.md").write_text(
        f"""# {album_title}

## Album Details

| **Title** | {album_title} |
| **Status** | {album_status} |
""",
        encoding="utf-8",
    )
    audio_dir = audio_root / "artists" / artist / "albums" / genre / album_slug
    audio_dir.mkdir(parents=True)

    track_map: dict = {}
    for slug, title, status in tracks:
        path = _write_track_file(tracks_dir, slug, title, status)
        track_map[slug] = {
            "title": title,
            "status": status,
            "explicit": False,
            "has_suno_link": True,
            "sources_verified": "N/A",
            "path": str(path),
            "mtime": path.stat().st_mtime,
        }

    state = {
        "version": 2,
        "config": {
            "content_root": str(content_root),
            "audio_root": str(audio_root),
            "artist_name": artist,
        },
        "albums": {
            album_slug: {
                "title": album_title,
                "status": album_status,
                "genre": genre,
                "path": str(album_content),
                "track_count": len(tracks),
                "tracks_completed": 0,
                "tracks": track_map,
            },
        },
        "session": {},
    }
    return state, album_content, tracks_dir, audio_dir


def _make_ctx(album_slug: str, audio_dir: Path) -> MasterAlbumCtx:
    loop = asyncio.new_event_loop()
    ctx = MasterAlbumCtx(
        album_slug=album_slug, genre="electronic",
        target_lufs=-14.0, ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
        source_subfolder="", freeze_signature=False, new_anchor=False,
        loop=loop,
    )
    ctx.audio_dir = audio_dir
    return ctx


@pytest.fixture
def filesystem(tmp_path: Path):
    content_root = tmp_path / "content"
    audio_root = tmp_path / "audio"
    content_root.mkdir()
    audio_root.mkdir()
    return content_root, audio_root


@pytest.fixture(autouse=True)
def _install_cache(monkeypatch):
    """Each test installs its own cache via install_cache()."""
    orig_cache = _shared_mod.cache

    def install_cache(state: dict) -> MockCache:
        cache = MockCache(state)
        _shared_mod.cache = cache
        return cache

    yield install_cache

    _shared_mod.cache = orig_cache


@pytest.fixture(autouse=True)
def _silence_state_write(monkeypatch):
    import tools.state.indexer as indexer_mod
    monkeypatch.setattr(indexer_mod, "write_state", lambda _state: None)


def _run(coro):
    return asyncio.run(coro)


def _setup(
    filesystem,
    install_cache,
    album_status: str,
    tracks: list[tuple[str, str, str]],
    create_signature: bool = True,
):
    """Wire up filesystem, cache, ctx, and (by default) the signature file."""
    content_root, audio_root = filesystem
    state, _album_content, _tracks_dir, audio_dir = _build_state(
        content_root=content_root, audio_root=audio_root,
        artist="test-artist", genre="electronic",
        album_slug="test-album", album_title="Test Album",
        album_status=album_status,
        tracks=tracks,
    )
    install_cache(state)
    if create_signature:
        (audio_dir / SIGNATURE_FILENAME).write_text("# stub\n", encoding="utf-8")
    ctx = _make_ctx("test-album", audio_dir)
    return state, ctx, audio_dir


# ===========================================================================
# Non-terminal statuses should be promoted to Final (the #335 core fix)
# ===========================================================================


class TestPromotesNonTerminalStatuses:
    @pytest.mark.parametrize("starting_status", [
        "Not Started",
        "Sources Pending",
        "Sources Verified",
        "In Progress",
        "Generated",
    ])
    def test_promotes_track_to_final(self, filesystem, _install_cache, starting_status):
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="In Progress",
            tracks=[("01-track-one", "Track One", starting_status)],
        )

        _run(_stage_status_update(ctx))

        track_info = state["albums"]["test-album"]["tracks"]["01-track-one"]
        assert track_info["status"] == "Final", (
            f"Expected promotion from '{starting_status}' to 'Final'"
        )
        assert ctx.stages["status_update"]["tracks_updated"] == 1

    def test_updates_status_row_in_track_file(
        self, filesystem, _install_cache,
    ):
        _state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="In Progress",
            tracks=[("01-track-one", "Track One", "Not Started")],
        )

        _run(_stage_status_update(ctx))

        track_md = Path(
            ctx.audio_dir.parent.parent.parent.parent.parent.parent
            # Shortcut via state — the disk path is stored in track_info
        )
        # Pull the actual path from state and verify file contents
        content_path = Path(
            _shared_mod.cache.get_state_ref()["albums"]["test-album"]
            ["tracks"]["01-track-one"]["path"]
        )
        text = content_path.read_text(encoding="utf-8")
        assert "**Status** | Final |" in text


# ===========================================================================
# Terminal statuses are left alone (Final and Released)
# ===========================================================================


class TestTerminalStatusesLeftAlone:
    def test_final_track_is_not_re_promoted(self, filesystem, _install_cache):
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="Complete",
            tracks=[("01-track-one", "Track One", "Final")],
        )

        _run(_stage_status_update(ctx))

        assert state["albums"]["test-album"]["tracks"]["01-track-one"]["status"] == "Final"
        assert ctx.stages["status_update"]["tracks_updated"] == 0
        # Should NOT be reported as an error — already at terminal state
        assert not ctx.stages["status_update"].get("errors")

    def test_released_track_is_not_demoted(self, filesystem, _install_cache):
        """Re-mastering a Released album must not demote tracks back to Final."""
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="Released",
            tracks=[("01-track-one", "Track One", "Released")],
        )

        _run(_stage_status_update(ctx))

        assert state["albums"]["test-album"]["tracks"]["01-track-one"]["status"] == "Released"
        assert ctx.stages["status_update"]["tracks_updated"] == 0
        # Released is a terminal, expected state on re-master — no errors
        assert not ctx.stages["status_update"].get("errors")


# ===========================================================================
# Stage outcome classification — #335 "At minimum, don't report pass when
# tracks_updated == 0 and errors is non-empty"
# ===========================================================================


class TestStageOutcomeClassification:
    def test_clean_run_reports_pass(self, filesystem, _install_cache):
        _state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="In Progress",
            tracks=[
                ("01-a", "A", "Generated"),
                ("02-b", "B", "Generated"),
            ],
        )

        _run(_stage_status_update(ctx))

        assert ctx.stages["status_update"]["status"] == "pass"
        assert ctx.stages["status_update"]["tracks_updated"] == 2
        assert not ctx.stages["status_update"].get("errors")

    def test_all_already_final_reports_pass(self, filesystem, _install_cache):
        """Idempotent re-run: nothing to do, nothing broken → still a pass."""
        _state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="Complete",
            tracks=[
                ("01-a", "A", "Final"),
                ("02-b", "B", "Final"),
            ],
        )

        _run(_stage_status_update(ctx))

        assert ctx.stages["status_update"]["status"] == "pass"
        assert ctx.stages["status_update"]["tracks_updated"] == 0

    def test_partial_success_is_reported(self, filesystem, _install_cache):
        """Some tracks update, some fail → status 'partial' (not 'pass')."""
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="In Progress",
            tracks=[
                ("01-a", "A", "Generated"),
                ("02-b", "B", "Not Started"),
            ],
        )
        # Sabotage one track's file so the rewrite fails
        bad_path = Path(state["albums"]["test-album"]["tracks"]["02-b"]["path"])
        bad_path.unlink()
        # But leave it in the cache so the stage still tries to process it

        _run(_stage_status_update(ctx))

        # Track one should still be promoted; track two should fail
        assert state["albums"]["test-album"]["tracks"]["01-a"]["status"] == "Final"
        assert ctx.stages["status_update"]["tracks_updated"] == 1
        assert ctx.stages["status_update"]["status"] == "partial"
        assert ctx.stages["status_update"].get("errors")

    def test_zero_updates_with_errors_is_not_pass(self, filesystem, _install_cache):
        """#335 core: the stage must not report 'pass' when nothing updated AND errors exist."""
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="In Progress",
            tracks=[("01-a", "A", "Not Started")],
        )
        # Delete the track file — so the stage can't rewrite it
        Path(state["albums"]["test-album"]["tracks"]["01-a"]["path"]).unlink()

        _run(_stage_status_update(ctx))

        stage_result = ctx.stages["status_update"]
        assert stage_result["tracks_updated"] == 0
        assert stage_result.get("errors")
        assert stage_result["status"] != "pass"


# ===========================================================================
# Album status transitions still work
# ===========================================================================


class TestAlbumStatusTransition:
    def test_all_final_advances_album_to_complete(self, filesystem, _install_cache):
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="In Progress",
            tracks=[
                ("01-a", "A", "Generated"),
                ("02-b", "B", "Not Started"),  # non-terminal now promotable
            ],
        )

        _run(_stage_status_update(ctx))

        album_data = state["albums"]["test-album"]
        assert album_data["status"] == "Complete"
        assert ctx.stages["status_update"]["album_status"] == "Complete"

    def test_released_album_stays_released(self, filesystem, _install_cache):
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="Released",
            tracks=[("01-a", "A", "Released")],
        )

        _run(_stage_status_update(ctx))

        # Re-mastering a Released album must not demote the album status
        assert state["albums"]["test-album"]["status"] == "Released"

    def test_missing_signature_blocks_album_advance(self, filesystem, _install_cache):
        """Existing guard: no ALBUM_SIGNATURE.yaml → don't advance album even if all tracks final."""
        state, ctx, _audio_dir = _setup(
            filesystem, _install_cache, album_status="In Progress",
            tracks=[("01-a", "A", "Generated")],
            create_signature=False,
        )

        _run(_stage_status_update(ctx))

        # Track should still be promoted
        assert state["albums"]["test-album"]["tracks"]["01-a"]["status"] == "Final"
        # But album stays In Progress because signature is missing
        assert state["albums"]["test-album"]["status"] == "In Progress"
        # Warning / error recorded
        assert ctx.stages["status_update"].get("errors")
