#!/usr/bin/env python3
"""Unit tests for the indexer CLI command layer.

The ``cmd_*`` argparse handlers in ``tools/state/indexer.py`` (rebuild, update,
validate, session, cleanup, show) were the second-largest uncovered block in
the repo — reachable only through the ``main()`` dispatcher, which is itself
excluded from coverage. These tests exercise each handler in-process by
constructing ``argparse.Namespace`` objects directly (the same pattern the
other unit tests use for handler functions), asserting the return code (0 on
success, non-zero on documented failure paths) and the meaningful side effect
(state written/updated, or the expected text printed to stdout).

Isolation: the autouse ``_isolate_state_cache`` fixture in tests/conftest.py
redirects ``indexer.STATE_FILE`` / ``CACHE_DIR`` / ``LOCK_FILE`` to a per-test
tmp dir, so ``read_state`` / ``write_state`` never touch the developer's real
~/.bitwize-music cache. ``read_config`` is NOT redirected by that fixture, so
tests that drive ``cmd_rebuild`` / ``cmd_update`` monkeypatch
``indexer.read_config`` explicitly rather than reading the real config.yaml.

Usage:
    python -m pytest tests/unit/state/test_indexer_cli.py -v
"""

import argparse
import logging
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tools.state.indexer as indexer

# Reuse the state-tree / minimal-state helpers the other indexer tests use.
from tests.unit.state.test_indexer import (
    _make_album_tree,
    _make_minimal_state,
    _make_track_content,
)
from tools.state.indexer import (
    CURRENT_VERSION,
    _validate_session_value,
    cmd_cleanup,
    cmd_rebuild,
    cmd_session,
    cmd_show,
    cmd_update,
    cmd_validate,
    main,
    read_state,
    write_state,
)

LOGGER_NAME = "tools.state.indexer"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _config(content_root, artist="testartist"):
    """Return the raw-config shape build_state expects."""
    return {"artist": {"name": artist}, "paths": {"content_root": str(content_root)}}


def _ns(**kwargs):
    """Construct an argparse.Namespace for a cmd_* handler."""
    return argparse.Namespace(**kwargs)


@pytest.fixture
def _plain_colors(monkeypatch):
    """Force plain (un-colored) output for deterministic stdout assertions.

    Also guarantees restoration: because monkeypatch snapshots each attribute
    before the test and restores it afterward, a handler (or ``main()``) that
    calls ``Colors.disable()`` mid-test cannot leak an emptied palette into
    later tests running in the same xdist worker process.
    """
    for attr in ("RED", "GREEN", "YELLOW", "BLUE", "CYAN", "BOLD", "NC"):
        monkeypatch.setattr(indexer.Colors, attr, "")


@pytest.fixture
def _stable_config_mtime(monkeypatch):
    """Avoid statting the real config file during build_state."""
    monkeypatch.setattr(indexer, "get_config_mtime", lambda: 0.0)


# ===========================================================================
# _validate_session_value  (already partially covered — a couple extra guards)
# ===========================================================================

@pytest.mark.unit
class TestValidateSessionValueContract:
    """The exact return contract used by cmd_session."""

    def test_valid_returns_none(self):
        # None == "no error", i.e. the value is accepted.
        assert _validate_session_value("my-album", "album") is None

    def test_exactly_at_max_len_ok(self):
        assert _validate_session_value("x" * 256, "album") is None

    def test_over_max_len_returns_error_string(self):
        err = _validate_session_value("x" * 257, "album")
        assert isinstance(err, str)
        assert "too long" in err
        assert "257" in err
        assert "256" in err

    def test_custom_max_len(self):
        assert _validate_session_value("abc", "field", max_len=3) is None
        err = _validate_session_value("abcd", "field", max_len=3)
        assert err is not None and "too long" in err

    def test_null_bytes_rejected(self):
        err = _validate_session_value("a\x00b", "track")
        assert err is not None and "null bytes" in err


# ===========================================================================
# cmd_rebuild
# ===========================================================================

@pytest.mark.unit
class TestCmdRebuild:
    def test_config_missing_returns_1(self, monkeypatch, caplog):
        monkeypatch.setattr(indexer, "read_config", lambda: None)
        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            rc = cmd_rebuild(_ns())
        assert rc == 1
        assert "Config not found" in caplog.text
        # No state file should have been written.
        assert read_state() is None

    def test_rebuild_writes_state_and_prints_summary(
        self, tmp_path, monkeypatch, capsys, _stable_config_mtime
    ):
        content_root = tmp_path / "content"
        _make_album_tree(
            content_root, "testartist", "rock", "my-album",
            tracks={"01-track.md": _make_track_content("Track One", "Final")},
        )
        monkeypatch.setattr(indexer, "read_config", lambda: _config(content_root))

        rc = cmd_rebuild(_ns())

        assert rc == 0
        out = capsys.readouterr().out
        assert "Albums: 1" in out
        assert "Tracks: 1" in out
        assert "Saved to:" in out
        # Side effect: state cache actually written with the album.
        state = read_state()
        assert state is not None
        assert "my-album" in state["albums"]

    def test_rebuild_preserves_existing_session(
        self, tmp_path, monkeypatch, _stable_config_mtime
    ):
        # Seed a prior state carrying session context.
        write_state(_make_minimal_state(session={
            "last_album": "kept-album",
            "last_track": "03-x",
            "last_phase": "Mastering",
            "pending_actions": ["ship it"],
            "updated_at": "2026-01-01T00:00:00+00:00",
        }))

        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "fresh-album")
        monkeypatch.setattr(indexer, "read_config", lambda: _config(content_root))

        rc = cmd_rebuild(_ns())

        assert rc == 0
        session = read_state()["session"]
        assert session["last_album"] == "kept-album"
        assert session["pending_actions"] == ["ship it"]

    def test_rebuild_reports_collisions(
        self, tmp_path, monkeypatch, capsys, caplog, _stable_config_mtime
    ):
        content_root = tmp_path / "content"
        # Same slug in two genres -> collision.
        _make_album_tree(content_root, "testartist", "rock", "midnight")
        _make_album_tree(content_root, "testartist", "jazz", "midnight")
        monkeypatch.setattr(indexer, "read_config", lambda: _config(content_root))

        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            rc = cmd_rebuild(_ns())

        assert rc == 0
        assert "Collisions: 1" in capsys.readouterr().out
        assert "collision" in caplog.text.lower()
        assert read_state()["album_collisions"]


# ===========================================================================
# cmd_update
# ===========================================================================

@pytest.mark.unit
class TestCmdUpdate:
    def test_config_missing_returns_1(self, monkeypatch, caplog):
        monkeypatch.setattr(indexer, "read_config", lambda: None)
        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            rc = cmd_update(_ns())
        assert rc == 1
        assert "Config not found" in caplog.text

    def test_no_existing_state_falls_back_to_rebuild(
        self, tmp_path, monkeypatch, capsys, _stable_config_mtime
    ):
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "my-album")
        monkeypatch.setattr(indexer, "read_config", lambda: _config(content_root))

        # No state written yet -> read_state() is None -> rebuild path.
        rc = cmd_update(_ns())

        assert rc == 0
        # cmd_rebuild prints the summary block.
        assert "Saved to:" in capsys.readouterr().out
        assert "my-album" in read_state()["albums"]

    def test_incompatible_version_triggers_rebuild(
        self, tmp_path, monkeypatch, capsys, _stable_config_mtime
    ):
        # A far-future version makes migrate_state() return None -> rebuild.
        write_state(_make_minimal_state(version="99.0.0"))
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "rebuilt-album")
        monkeypatch.setattr(indexer, "read_config", lambda: _config(content_root))

        rc = cmd_update(_ns())

        assert rc == 0
        assert "Saved to:" in capsys.readouterr().out
        state = read_state()
        assert state["version"] == CURRENT_VERSION
        assert "rebuilt-album" in state["albums"]

    def test_invalid_sections_trigger_rebuild(
        self, tmp_path, monkeypatch, capsys, _stable_config_mtime
    ):
        # A valid, current-version state passes migrate_state, but a stubbed
        # incremental_update returning None forces the full-rebuild fallback.
        write_state(_make_minimal_state())
        monkeypatch.setattr(indexer, "incremental_update", lambda *a, **k: None)

        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "recovered-album")
        monkeypatch.setattr(indexer, "read_config", lambda: _config(content_root))

        rc = cmd_update(_ns())

        assert rc == 0
        assert "Saved to:" in capsys.readouterr().out
        assert "recovered-album" in read_state()["albums"]

    def test_incremental_update_success(
        self, tmp_path, monkeypatch, _stable_config_mtime
    ):
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "steady-album")
        config = _config(content_root)
        monkeypatch.setattr(indexer, "read_config", lambda: config)

        # Seed a valid, current-version existing state built from the same tree.
        write_state(indexer.build_state(config))

        rc = cmd_update(_ns())

        assert rc == 0
        # Incremental update kept the album and wrote state.
        assert "steady-album" in read_state()["albums"]

    def test_incremental_update_warns_on_collisions(
        self, tmp_path, monkeypatch, caplog, _stable_config_mtime
    ):
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "midnight")
        _make_album_tree(content_root, "testartist", "jazz", "midnight")
        config = _config(content_root)
        monkeypatch.setattr(indexer, "read_config", lambda: config)
        write_state(indexer.build_state(config))

        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            rc = cmd_update(_ns())

        assert rc == 0
        assert "collision" in caplog.text.lower()
        assert read_state()["album_collisions"]


# ===========================================================================
# cmd_validate
# ===========================================================================

@pytest.mark.unit
class TestCmdValidate:
    def test_no_state_returns_1(self, caplog):
        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            rc = cmd_validate(_ns())
        assert rc == 1
        assert "No state file found" in caplog.text

    def test_valid_state_returns_0(self, caplog):
        write_state(_make_minimal_state())
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            rc = cmd_validate(_ns())
        assert rc == 0
        assert "State is valid" in caplog.text

    def test_schema_errors_return_1_and_print(self, capsys):
        # albums as a list fails the schema's dict check.
        write_state(_make_minimal_state(albums=[]))
        rc = cmd_validate(_ns())
        assert rc == 1
        out = capsys.readouterr().out
        assert "albums should be a dict" in out

    def test_version_mismatch_warns_but_passes(self, caplog):
        # A valid state whose schema version differs from CURRENT_VERSION
        # still validates, but logs a version-mismatch warning.
        write_state(_make_minimal_state(version="1.0.0"))
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            rc = cmd_validate(_ns())
        assert rc == 0
        assert "Version mismatch" in caplog.text


# ===========================================================================
# cmd_session
# ===========================================================================

@pytest.mark.unit
class TestCmdSession:
    def test_no_state_returns_1(self, caplog):
        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            rc = cmd_session(_ns(
                clear=False, album="a", track=None, phase=None, add_action=None,
            ))
        assert rc == 1
        assert "No state file found" in caplog.text

    def test_sets_fields_and_prints(self, capsys):
        write_state(_make_minimal_state())
        rc = cmd_session(_ns(
            clear=False, album="my-album", track="02-track",
            phase="Writing", add_action="finish hook",
        ))
        assert rc == 0
        out = capsys.readouterr().out
        assert "Album: my-album" in out
        assert "Phase: Writing" in out
        assert "Track: 02-track" in out
        assert "Pending actions: 1" in out

        session = read_state()["session"]
        assert session["last_album"] == "my-album"
        assert session["last_track"] == "02-track"
        assert session["last_phase"] == "Writing"
        assert session["pending_actions"] == ["finish hook"]
        assert session["updated_at"] is not None

    def test_clear_resets_session(self):
        write_state(_make_minimal_state(session={
            "last_album": "old",
            "last_track": "01-x",
            "last_phase": "Mixing",
            "pending_actions": ["a", "b"],
            "updated_at": "2026-01-01T00:00:00+00:00",
        }))
        rc = cmd_session(_ns(
            clear=True, album=None, track=None, phase=None, add_action=None,
        ))
        assert rc == 0
        session = read_state()["session"]
        assert session["last_album"] is None
        assert session["last_track"] is None
        assert session["last_phase"] is None
        assert session["pending_actions"] == []

    def test_invalid_value_returns_1(self, caplog):
        write_state(_make_minimal_state())
        rc = cmd_session(_ns(
            clear=False, album="x" * 257, track=None, phase=None, add_action=None,
        ))
        assert rc == 1
        assert "Invalid session value" in caplog.text
        assert "too long" in caplog.text

    def test_too_many_pending_actions_returns_1(self, caplog):
        write_state(_make_minimal_state(session={
            "last_album": None,
            "last_track": None,
            "last_phase": None,
            "pending_actions": ["x"] * 100,
            "updated_at": None,
        }))
        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            rc = cmd_session(_ns(
                clear=False, album=None, track=None, phase=None,
                add_action="one too many",
            ))
        assert rc == 1
        assert "Too many pending actions" in caplog.text
        # State unchanged (still exactly 100, not written over).
        assert len(read_state()["session"]["pending_actions"]) == 100


# ===========================================================================
# cmd_cleanup
# ===========================================================================

@pytest.mark.unit
class TestCmdCleanup:
    def test_no_state_returns_1(self, caplog):
        with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
            rc = cmd_cleanup(_ns(dry_run=False))
        assert rc == 1
        assert "No state file found" in caplog.text

    def test_no_albums_is_noop(self, caplog):
        write_state(_make_minimal_state(albums={}))
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            rc = cmd_cleanup(_ns(dry_run=False))
        assert rc == 0
        assert "nothing to clean up" in caplog.text

    def test_all_paths_exist_is_noop(self, tmp_path, caplog):
        existing_dir = tmp_path / "albums" / "live-album"
        existing_dir.mkdir(parents=True)
        write_state(_make_minimal_state(albums={
            "live-album": {"path": str(existing_dir), "tracks": {}},
        }))
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            rc = cmd_cleanup(_ns(dry_run=False))
        assert rc == 0
        assert "nothing to clean up" in caplog.text
        # Album preserved.
        assert "live-album" in read_state()["albums"]

    def test_stale_dry_run_reports_but_keeps(self, tmp_path, caplog):
        missing = tmp_path / "albums" / "ghost"
        write_state(_make_minimal_state(albums={
            "ghost": {"path": str(missing), "tracks": {}},
        }))
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            rc = cmd_cleanup(_ns(dry_run=True))
        assert rc == 0
        assert "[DRY RUN]" in caplog.text
        # Dry run does not mutate state.
        assert "ghost" in read_state()["albums"]

    def test_stale_removed_when_not_dry_run(self, tmp_path, caplog):
        missing = tmp_path / "albums" / "ghost"
        keep_dir = tmp_path / "albums" / "keep"
        keep_dir.mkdir(parents=True)
        write_state(_make_minimal_state(albums={
            "ghost": {"path": str(missing), "tracks": {}},
            "keep": {"path": str(keep_dir), "tracks": {}},
        }))
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            rc = cmd_cleanup(_ns(dry_run=False))
        assert rc == 0
        assert "Removing stale album" in caplog.text
        albums = read_state()["albums"]
        assert "ghost" not in albums
        assert "keep" in albums


# ===========================================================================
# cmd_show
# ===========================================================================

@pytest.mark.unit
class TestCmdShow:
    def test_no_state_returns_1(self, capsys):
        rc = cmd_show(_ns(verbose=False))
        assert rc == 1
        assert "No state file found" in capsys.readouterr().out

    def test_minimal_non_verbose(self, capsys, _plain_colors):
        write_state(_make_minimal_state())
        rc = cmd_show(_ns(verbose=False))
        assert rc == 0
        out = capsys.readouterr().out
        assert "State Cache Summary" in out
        assert "Albums (0):" in out
        # Empty ideas -> the "(none)" branch.
        assert "(none)" in out
        assert "Skills (0):" in out
        # Empty session -> no "Last Session:" block.
        assert "Last Session:" not in out

    def test_rich_verbose(self, capsys, _plain_colors):
        write_state(_make_minimal_state(
            albums={
                "my-album": {
                    "genre": "rock",
                    "status": "In Progress",
                    "tracks_completed": 1,
                    "tracks": {
                        "01-opener": {"status": "Final", "has_suno_link": True},
                    },
                },
            },
            album_collisions=[{
                "slug": "dup",
                "kept": {"genre": "rock", "path": "/a/rock/dup"},
                "shadowed": [{"genre": "jazz", "path": "/a/jazz/dup"}],
            }],
            ideas={"counts": {"Pending": 2}, "items": [], "file_mtime": 0.0},
            skills={
                "skills_root": "/s",
                "skills_root_mtime": 0.0,
                "count": 2,
                "model_counts": {"opus": 1, "haiku": 1},
                "items": {
                    "lyric-writer": {"model_tier": "opus", "user_invocable": True},
                    "internal-skill": {"model_tier": "haiku", "user_invocable": False},
                },
            },
            session={
                "last_album": "my-album",
                "last_track": "01-opener",
                "last_phase": "Writing",
                "pending_actions": ["finish bridge"],
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        ))

        rc = cmd_show(_ns(verbose=True))

        assert rc == 0
        out = capsys.readouterr().out
        # Albums + verbose per-track line + suno marker.
        assert "Albums (1):" in out
        assert "my-album (rock)" in out
        assert "[1/1 tracks]" in out
        assert "01-opener: Final [suno]" in out
        # Collisions block.
        assert "Album slug collisions (1):" in out
        assert "shadowed: jazz" in out
        # Ideas counts populated.
        assert "Pending: 2" in out
        # Skills: model breakdown + verbose per-skill lines incl. [internal].
        assert "Skills (2):" in out
        assert "By model:" in out
        assert "lyric-writer (opus)" in out
        assert "internal-skill (haiku) [internal]" in out
        # Session block.
        assert "Last Session:" in out
        assert "Album: my-album" in out
        assert "Track: 01-opener" in out
        assert "Phase: Writing" in out
        assert "- finish bridge" in out


# ===========================================================================
# main() dispatch  (main() itself is coverage-excluded; this just proves the
# argv -> handler wiring works end-to-end for a couple of subcommands)
# ===========================================================================

@pytest.mark.unit
class TestMainDispatch:
    def test_validate_no_state_returns_1(self, monkeypatch, _plain_colors):
        monkeypatch.setattr(sys, "argv", ["indexer.py", "validate"])
        assert main() == 1

    def test_show_success_returns_0(self, monkeypatch, _plain_colors):
        write_state(_make_minimal_state())
        monkeypatch.setattr(sys, "argv", ["indexer.py", "show"])
        assert main() == 0
