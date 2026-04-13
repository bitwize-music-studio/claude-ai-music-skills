#!/usr/bin/env python3
"""
Unit tests verifying that formerly-silent exception handlers now log warnings.

These tests exercise the 5 handlers replaced in:
  - handlers/rename.py:~280
  - handlers/text_analysis.py:~404
  - handlers/processing/sheet_music.py:~281
  - handlers/processing/_helpers.py:~123 and ~148

Each test triggers the exception path and asserts a warning was emitted via
caplog rather than being swallowed silently.

Usage:
    python -m pytest tests/unit/state/test_silent_exceptions.py -v
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Stub MCP SDK if not installed
# ---------------------------------------------------------------------------

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
    spec = importlib.util.spec_from_file_location("state_server_silent_exc", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Import server once at module level to register all handlers
_import_server()

# ---------------------------------------------------------------------------
# Test 1: rename.py — re-parse after rename
# ---------------------------------------------------------------------------


class TestRenameReParseWarning:
    """Verify that a parse failure after rename logs a warning."""

    def test_reparse_failure_logs_warning(self, tmp_path, caplog):
        """When parse_track_file raises ValueError, a warning should be logged."""
        from handlers import rename as rename_mod

        # Create a minimal fake track file so stat() works
        fake_track = tmp_path / "01-renamed-track.md"
        fake_track.write_text("# Renamed Track\n")

        fake_state = {
            "version": 2,
            "config": {
                "content_root": str(tmp_path),
                "audio_root": str(tmp_path),
                "artist_name": "test-artist",
            },
            "albums": {
                "test-album": {
                    "title": "Test Album",
                    "status": "In Progress",
                    "genre": "electronic",
                    "path": str(tmp_path),
                    "track_count": 1,
                    "tracks_completed": 0,
                    "tracks": {
                        "01-old-track": {
                            "title": "Old Track",
                            "status": "In Progress",
                            "explicit": False,
                            "has_suno_link": False,
                            "sources_verified": "N/A",
                            "path": str(tmp_path / "01-old-track.md"),
                            "mtime": 0.0,
                        }
                    },
                }
            },
        }

        old_path = tmp_path / "01-old-track.md"
        old_path.write_text("# Old Track\n")

        with (
            patch.object(rename_mod._shared.cache, "get_state", return_value=fake_state),
            patch.object(rename_mod._shared.cache, "get_state_ref", return_value=fake_state),
            patch("tools.state.indexer.write_state"),
            patch(
                "tools.state.parsers.parse_track_file",
                side_effect=ValueError("bad markdown"),
            ),
            caplog.at_level("WARNING", logger="handlers.rename"),
        ):
            import asyncio
            result = asyncio.run(
                rename_mod.rename_track("test-album", "01-old-track", "01-renamed-track")
            )

        # The rename should succeed (track title updated) but log the parse warning
        assert any(
            "Could not re-parse track after rename" in r.message for r in caplog.records
        ), f"Expected re-parse warning in logs. Records: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Test 2: text_analysis.py — override path resolution
# ---------------------------------------------------------------------------


class TestTextAnalysisOverridePathWarning:
    """Verify that override path resolution failure logs a warning."""

    def test_override_path_failure_logs_warning(self, caplog):
        """When get_state raises RuntimeError, a warning should be logged."""
        from handlers import text_analysis as ta_mod

        # Reset the module-level cache so _load_explicit_words actually runs the
        # try/except block that resolves the override path.
        ta_mod._explicit_word_cache = None
        ta_mod._explicit_word_mtime = -1.0

        with (
            patch.object(
                ta_mod._shared.cache,
                "get_state",
                side_effect=RuntimeError("lock error"),
            ),
            caplog.at_level("WARNING", logger="bitwize-music-state"),
        ):
            # _load_explicit_words() is the function that resolves override_path
            # and contains the except handler we want to test.
            ta_mod._load_explicit_words()

        assert any(
            "Could not resolve override path" in r.message for r in caplog.records
        ), f"Expected override path warning. Records: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Test 3: sheet_music.py — config loading for page size
# ---------------------------------------------------------------------------


class TestSheetMusicConfigWarning:
    """Verify that sheet music config load failure logs a warning."""

    def test_config_load_failure_logs_warning(self, tmp_path, caplog):
        """When load_config raises ImportError inside prepare_singles, a warning is logged."""
        from handlers.processing import sheet_music as sm_mod

        # Set up minimal directory structure that prepare_singles needs
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        source_dir = audio_dir / "sheet-music" / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        fake_state = {
            "version": 2,
            "config": {
                "content_root": str(tmp_path),
                "audio_root": str(tmp_path),
                "artist_name": "test-artist",
            },
            "albums": {
                "test-album": {
                    "title": "Test Album",
                    "status": "Complete",
                    "genre": "electronic",
                    "path": str(tmp_path / "test-album"),
                    "track_count": 0,
                    "tracks": {},
                }
            },
        }

        # Stub out the prepare_singles and songbook imports from the sheet music tools
        fake_prepare_mod = MagicMock()
        fake_prepare_mod.prepare_singles.return_value = []
        fake_prepare_mod.find_musescore.return_value = None

        fake_songbook_mod = MagicMock()
        fake_songbook_mod.auto_detect_cover_art.return_value = None
        fake_songbook_mod.get_footer_url_from_config.return_value = ""

        with (
            patch.object(sm_mod._shared.cache, "get_state", return_value=fake_state),
            patch.object(
                sm_mod._helpers,
                "_resolve_audio_dir",
                return_value=(None, audio_dir),
            ),
            patch.object(
                sm_mod._helpers,
                "_import_sheet_music_module",
                side_effect=lambda name: fake_prepare_mod if name == "prepare_singles" else fake_songbook_mod,
            ),
            # Make tools.shared.config.load_config raise ImportError to trigger the handler
            patch.dict(
                "sys.modules",
                {"tools.shared.config": types.ModuleType("tools.shared.config")},
            ),
            caplog.at_level("WARNING", logger="bitwize-music-state"),
        ):
            stub = sys.modules["tools.shared.config"]
            stub.load_config = MagicMock(side_effect=ImportError("no module"))

            import asyncio
            try:
                asyncio.run(sm_mod.prepare_singles("test-album"))
            except Exception:
                pass  # We only care about the logged warning

        assert any(
            "Could not load sheet music config" in r.message for r in caplog.records
        ), f"Expected sheet music config warning. Records: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Test 4: _helpers.py — cloud config check
# ---------------------------------------------------------------------------


class TestHelpersCloudConfigWarning:
    """Verify that cloud config load failure logs a warning and returns error string."""

    def test_cloud_config_failure_logs_warning(self, caplog):
        """When load_config raises ImportError, a warning is logged and error string returned."""
        from handlers.processing import _helpers as helpers_mod

        with (
            patch.dict(
                "sys.modules",
                {"tools.shared.config": types.ModuleType("tools.shared.config")},
            ),
            caplog.at_level("WARNING", logger="handlers.processing._helpers"),
        ):
            stub = sys.modules["tools.shared.config"]
            stub.load_config = MagicMock(side_effect=ImportError("no module"))

            result = helpers_mod._check_cloud_enabled()

        assert result is not None
        assert "Could not load config" in result
        assert any(
            "Config load failed" in r.message for r in caplog.records
        ), f"Expected config load warning. Records: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Test 5: _helpers.py — AnthemScore check
# ---------------------------------------------------------------------------


class TestHelpersAnthemScoreWarning:
    """Verify that AnthemScore module check failure falls back to path search."""

    def test_anthemscore_module_failure_falls_back(self):
        """When _import_sheet_music_module returns None, fall back to path search."""
        from handlers.processing import _helpers as helpers_mod

        with (
            patch.object(
                helpers_mod,
                "_import_sheet_music_module",
                return_value=None,
            ),
            # Ensure no anthemscore binary found on this system either
            patch("shutil.which", return_value=None),
            patch.object(Path, "exists", return_value=False),
        ):
            result = helpers_mod._check_anthemscore()

        assert result is not None
        assert "AnthemScore not found" in result
