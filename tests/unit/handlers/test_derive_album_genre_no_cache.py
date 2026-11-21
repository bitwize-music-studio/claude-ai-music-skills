"""``_derive_album_genre`` keeps its "never raises" promise without a state cache (#670)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for path in (PROJECT_ROOT, SERVER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from handlers import _shared
from handlers.processing import _helpers


def test_no_cache_means_no_genre(monkeypatch):
    monkeypatch.setattr(_shared, "cache", None)
    assert _helpers._derive_album_genre("my-album") == ""


def test_a_cached_album_gives_its_genre(monkeypatch):
    class _Cache:
        def get_state(self):
            return {"albums": {"my-album": {"genre": "synthwave"}}}

    monkeypatch.setattr(_shared, "cache", _Cache())
    assert _helpers._derive_album_genre("my-album") == "synthwave"
