#!/usr/bin/env python3
"""A failed state rebuild is reported, never ignored or raised (#679 item 9, #676).

``StateCache.rebuild()`` reports a missing or unparseable config and a failed
build by *returning* ``{"error": ...}``, and raises only when writing state.json
fails. These tests use a real album built from the repo's templates, the real
indexer and a real ``StateCache`` wired into the server — then break the config
mid-session, the way a half-saved edit does — instead of a mock whose rebuild
raises.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest
import yaml

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
    spec = importlib.util.spec_from_file_location("state_server_rebuild_failures", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import album_ops, core, ideas, status  # noqa: E402
from tools.state import indexer  # noqa: E402

ARTIST = "bitwize"


def _run(coro):
    return json.loads(asyncio.run(coro))


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A real album from the templates, indexed by the real indexer, served by a
    real StateCache. Returns the config path and the album folder."""
    content = tmp_path / "content"
    cache_dir = tmp_path / "cache"
    album_dir = content / "artists" / ARTIST / "albums" / "electronic" / "night-shift"
    (album_dir / "tracks").mkdir(parents=True)
    (tmp_path / "audio").mkdir()
    cache_dir.mkdir()
    readme = (PROJECT_ROOT / "templates" / "album.md").read_text(encoding="utf-8")
    readme = readme.replace("[Album Title]", "Night Shift").replace(
        "genres: []", 'genres: ["electronic"]')
    (album_dir / "README.md").write_text(readme, encoding="utf-8")
    track = (PROJECT_ROOT / "templates" / "track.md").read_text(encoding="utf-8")
    (album_dir / "tracks" / "01-neon-wake.md").write_text(
        track.replace("[Track Title]", "Neon Wake"), encoding="utf-8")
    (content / "IDEAS.md").write_text(
        "# Album Ideas\n\n## Pending\n\n### Glass Harbor\n**Genre**: electronic\n"
        "**Type**: Thematic\n**Concept**: Night ferries.\n**Status**: Pending\n",
        encoding="utf-8",
    )

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump({
        "artist": {"name": ARTIST},
        "paths": {"content_root": str(content), "audio_root": str(tmp_path / "audio"),
                  "documents_root": str(tmp_path / "docs")},
    }), encoding="utf-8")
    for module in (indexer, server):
        monkeypatch.setattr(module, "CONFIG_FILE", cfg_path)
        monkeypatch.setattr(module, "STATE_FILE", cache_dir / "state.json")
    monkeypatch.setattr(indexer, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(indexer, "LOCK_FILE", cache_dir / "state.lock")
    monkeypatch.setattr(server, "PLUGIN_ROOT", PROJECT_ROOT)
    monkeypatch.setattr(_shared_mod, "PLUGIN_ROOT", PROJECT_ROOT)

    indexer.write_state(indexer.build_state(indexer.read_config(), plugin_root=PROJECT_ROOT))
    cache = server.StateCache()
    monkeypatch.setattr(_shared_mod, "cache", cache)
    assert "night-shift" in cache.get_state()["albums"]
    return types.SimpleNamespace(cfg=cfg_path, content=content, album_dir=album_dir, cache=cache)


def _break_config(cfg: Path) -> None:
    """A config that stops parsing mid-session (a stray tab, a half-saved edit)."""
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\n\tbroken: [\n", encoding="utf-8")


class TestRebuildErrorMessage:
    def test_unparseable_config_is_not_reported_as_missing(self, env):
        _break_config(env.cfg)
        result = env.cache.rebuild()
        assert "error" in result
        assert "Config not found" not in result["error"]
        assert "could not be read or parsed" in result["error"]
        assert str(env.cfg) in result["error"]

    def test_missing_config_still_says_not_found(self, env):
        env.cfg.unlink()
        assert "Config not found" in env.cache.rebuild()["error"]


class TestCreateAlbumStructure:
    def test_returned_rebuild_error_is_reported(self, env):
        """The #679 repro: created: True, album missing from state, nothing said."""
        _break_config(env.cfg)
        result = _run(album_ops.create_album_structure("glass-harbor", "electronic"))
        assert result["created"] is True
        assert Path(result["path"]).is_dir()
        assert result["indexed"] is False
        assert len(result["warnings"]) == 1
        warning = result["warnings"][0]
        assert "could not be read or parsed" in warning
        assert "rebuild_state" in warning
        assert "glass-harbor" not in env.cache.get_state()["albums"]

    def test_raised_rebuild_error_is_reported(self, env, monkeypatch):
        def fail(_state):
            raise OSError("state.json is read-only")

        monkeypatch.setattr(server, "write_state", fail)
        result = _run(album_ops.create_album_structure("glass-harbor", "electronic"))
        assert result["created"] is True
        assert result["indexed"] is False
        assert "state.json is read-only" in result["warnings"][0]

    def test_rebuild_ok_indexes_the_album(self, env):
        result = _run(album_ops.create_album_structure("glass-harbor", "electronic"))
        assert result["indexed"] is True
        assert "warnings" not in result
        assert "glass-harbor" in env.cache.get_state()["albums"]


class TestCreateTrack:
    def test_returned_rebuild_error_is_reported(self, env):
        _break_config(env.cfg)
        result = _run(status.create_track("night-shift", "02", "Static Hymn"))
        assert result["created"] is True
        assert Path(result["path"]).is_file()
        assert result["indexed"] is False
        assert "rebuild_state" in result["warnings"][0]


class TestIdeas:
    def test_create_idea_reports_returned_rebuild_error(self, env):
        _break_config(env.cfg)
        result = _run(ideas.create_idea("Paper Moons", genre="electronic"))
        assert result["created"] is True
        assert "rebuild_state" in result["warnings"][0]

    def test_update_idea_reports_returned_rebuild_error(self, env):
        _break_config(env.cfg)
        result = _run(ideas.update_idea("Glass Harbor", "genre", "ambient"))
        assert result["success"] is True
        assert "rebuild_state" in result["warnings"][0]

    def test_promote_idea_with_an_unparseable_config(self, env):
        """#676: the album is made, IDEAS.md is updated, and the failed rebuild
        is in the structured result — no raise, no silent half-made album."""
        _break_config(env.cfg)
        result = _run(ideas.promote_idea("Glass Harbor"))
        assert result["promoted"] is True
        assert Path(result["album_path"]).is_dir()
        assert result["idea_status_updated"] is True
        assert result["backlink_written"] is True
        assert result["indexed"] is False
        assert len(result["warnings"]) == 1
        assert "rebuild_state" in result["warnings"][0]
        ideas_md = (env.content / "IDEAS.md").read_text(encoding="utf-8")
        assert "**Status**: In Progress" in ideas_md
        assert "**Promoted To**: glass-harbor" in ideas_md


class TestCoreCallers:
    def test_rebuild_state_reports_a_raised_failure(self, env, monkeypatch):
        def fail(_state):
            raise OSError("disk full")

        monkeypatch.setattr(server, "write_state", fail)
        result = _run(core.rebuild_state())
        assert "disk full" in result["error"]

    def test_rebuild_state_reports_a_returned_failure(self, env):
        _break_config(env.cfg)
        result = _run(core.rebuild_state())
        assert "could not be read or parsed" in result["error"]

    def test_find_album_says_the_rebuild_failed(self, env, monkeypatch):
        """An empty cache triggers a rebuild; its failure is named, not hidden
        behind "state rebuilt but still empty"."""
        _break_config(env.cfg)
        env.cache.get_state()["albums"] = {}  # loaded after the edit, so not stale
        result = _run(core.find_album("night-shift"))
        assert result["found"] is False
        assert result["rebuilt"] is False
        assert "could not be read or parsed" in result["error"]
        assert "rebuild_state" in result["error"]
