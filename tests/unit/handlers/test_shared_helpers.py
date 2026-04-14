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


def test_is_album_released_true_when_status_is_released(monkeypatch):
    _shared.cache = _FakeCache({"albums": {"my-album": {"status": "Released"}}})
    assert _shared.is_album_released("my-album") is True


def test_is_album_released_false_when_status_is_in_progress(monkeypatch):
    _shared.cache = _FakeCache({"albums": {"my-album": {"status": "In Progress"}}})
    assert _shared.is_album_released("my-album") is False


def test_is_album_released_false_when_album_missing(monkeypatch):
    _shared.cache = _FakeCache({"albums": {}})
    assert _shared.is_album_released("my-album") is False


def test_is_album_released_false_when_cache_not_ready(monkeypatch):
    _shared.cache = None
    assert _shared.is_album_released("my-album") is False
