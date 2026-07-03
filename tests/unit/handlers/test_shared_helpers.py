"""Tests for handlers/_shared.py helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared  # noqa: E402


class _FakeCache:
    def __init__(self, state: dict) -> None:
        self._state = state
    def get_state(self) -> dict:
        return self._state


@pytest.fixture(autouse=True)
def _restore_cache(monkeypatch):
    """Keep the module-level ``cache`` attribute isolated between tests."""
    original = _shared.cache
    yield
    _shared.cache = original


def test_is_album_released_true_when_status_is_released():
    _shared.cache = _FakeCache({"albums": {"my-album": {"status": "Released"}}})
    assert _shared.is_album_released("my-album") is True


def test_is_album_released_false_when_status_is_in_progress():
    _shared.cache = _FakeCache({"albums": {"my-album": {"status": "In Progress"}}})
    assert _shared.is_album_released("my-album") is False


def test_is_album_released_false_when_album_missing():
    _shared.cache = _FakeCache({"albums": {}})
    assert _shared.is_album_released("my-album") is False


def test_is_album_released_false_when_cache_not_ready():
    _shared.cache = None
    assert _shared.is_album_released("my-album") is False


def test_is_album_released_false_on_invalid_slug():
    """_normalize_slug raises ValueError on path separators etc."""
    _shared.cache = _FakeCache({"albums": {"my-album": {"status": "Released"}}})
    # Path traversal in slug → normalized lookup raises → False
    assert _shared.is_album_released("../my-album") is False
    assert _shared.is_album_released("my/album") is False


def test_is_album_released_false_when_cache_raises():
    """Corrupt state / filesystem error during get_state → False."""
    class _RaisingCache:
        def get_state(self):
            raise OSError("simulated disk failure")
    _shared.cache = _RaisingCache()
    assert _shared.is_album_released("my-album") is False


class TestGetValidGenresCachePoisoning:
    """A degenerate genre scan must not poison the process-wide cache.

    Regression for the xdist flake where a test patching PLUGIN_ROOT (or
    blanket-mocking Path.exists) primed _VALID_GENRES with an empty set,
    making every later create_album_structure reject valid genres.
    """

    @pytest.fixture(autouse=True)
    def _reset_genre_cache(self):
        original = _shared._VALID_GENRES
        _shared._VALID_GENRES = None
        yield
        _shared._VALID_GENRES = original

    def _real_plugin_root(self):
        return PROJECT_ROOT

    def test_fake_plugin_root_does_not_poison_cache(self, tmp_path, monkeypatch):
        fake_root = tmp_path / "fake-plugin"
        fake_root.mkdir()
        monkeypatch.setattr(_shared, "PLUGIN_ROOT", fake_root)
        assert _shared._get_valid_genres() == frozenset()

        monkeypatch.setattr(_shared, "PLUGIN_ROOT", self._real_plugin_root())
        assert "rock" in _shared._get_valid_genres()

    def test_cache_rekeys_when_plugin_root_changes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_shared, "PLUGIN_ROOT", self._real_plugin_root())
        real_genres = _shared._get_valid_genres()
        assert real_genres  # non-empty and now cached

        other_root = tmp_path / "other-plugin"
        (other_root / "genres" / "onlygenre").mkdir(parents=True)
        (other_root / "genres" / "onlygenre" / "README.md").write_text("# g")
        monkeypatch.setattr(_shared, "PLUGIN_ROOT", other_root)
        assert _shared._get_valid_genres() == frozenset({"onlygenre"})

    def test_empty_scan_is_not_cached(self, tmp_path, monkeypatch):
        fake_root = tmp_path / "fake-plugin"
        fake_root.mkdir()
        monkeypatch.setattr(_shared, "PLUGIN_ROOT", fake_root)
        _shared._get_valid_genres()
        assert _shared._VALID_GENRES is None  # degenerate result not stored
