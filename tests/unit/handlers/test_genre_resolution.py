"""Tests for per-track genre resolution in get_lyrics_stats.

An album whose directory is one genre may deliberately span several — a
sung-through musical, a soundtrack, a compilation. The word-count target should
follow the track rather than the folder it was filed under.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as _shared_mod
from handlers import text_analysis
from tools.state.parsers import parse_track_file


class _FakeCache:
    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return self._state


def _write_track(path: Path, words: int, genre: str | None = None) -> None:
    fm = 'title: "T"\n' + (f'genre: "{genre}"\n' if genre else "")
    lyrics = " ".join(["word"] * words)
    path.write_text(
        f"---\n{fm}---\n\n# T\n\n## Lyrics Box\n\n```\n[Verse 1]\n{lyrics}\n```\n",
        encoding="utf-8",
    )


def _run(coro):
    import asyncio
    return json.loads(asyncio.run(coro))


@pytest.fixture
def album(tmp_path, monkeypatch):
    """An album filed under one genre with tracks declaring another."""
    def build(album_genre: str, tracks: dict[str, tuple[int, str | None]]):
        state_tracks = {}
        for slug, (words, track_genre) in tracks.items():
            f = tmp_path / f"{slug}.md"
            _write_track(f, words, track_genre)
            state_tracks[slug] = {
                "path": str(f), "title": slug,
                "genre": track_genre or "",
            }
        cache = _FakeCache({
            "config": {},
            "albums": {"a": {"genre": album_genre, "tracks": state_tracks}},
        })
        monkeypatch.setattr(_shared_mod, "cache", cache)
        return _run(text_analysis.get_lyrics_stats("a"))
    return build


class TestPrecedence:
    def test_track_genre_wins_over_album_genre(self, album):
        """A rap track on a pop album is judged as rap."""
        result = album("pop", {"t1": (400, "hip-hop")})
        row = result["tracks"][0]
        assert row["genre"] == "hip-hop"
        assert row["target"] == {"min": 300, "max": 500}
        assert row["status"] == "OK"

    def test_same_track_is_over_target_without_its_own_genre(self, album):
        """400 words is OVER on pop (150-250) — this is what the fix changes."""
        result = album("pop", {"t1": (400, None)})
        row = result["tracks"][0]
        assert row["genre"] == "pop"
        assert row["status"] == "OVER"

    def test_album_genre_used_when_track_declares_none(self, album):
        result = album("ambient", {"t1": (100, None)})
        assert result["tracks"][0]["target"] == {"min": 50, "max": 150}

    def test_unknown_genres_fall_back_to_the_default(self, album):
        result = album("cinematic", {"t1": (200, None)})
        row = result["tracks"][0]
        assert row["target"] == {"min": 150, "max": 350}
        assert row["genre"] == "cinematic"

    def test_note_names_the_genre_the_target_came_from(self, album):
        """Not the album's — that was the misleading part."""
        result = album("pop", {"t1": (400, "hip-hop")})
        assert "hip-hop" in result["tracks"][0]["note"]
        assert "pop" not in result["tracks"][0]["note"]

    def test_tracks_in_one_album_can_resolve_differently(self, album):
        result = album("pop", {
            "t1": (100, "ambient"),
            "t2": (400, "hip-hop"),
        })
        by_slug = {r["track_slug"]: r for r in result["tracks"]}
        assert by_slug["t1"]["status"] == "OK"
        assert by_slug["t2"]["status"] == "OK"
        assert by_slug["t1"]["genre"] != by_slug["t2"]["genre"]


class TestSummaryUnchanged:
    def test_album_target_is_the_albums_not_the_last_tracks(self, album):
        """The summary keeps its old meaning even when tracks differ."""
        result = album("pop", {"t1": (400, "hip-hop")})
        assert result["genre"] == "pop"
        assert result["target"] == {"min": 150, "max": 250}


class TestTrackFrontmatter:
    def test_parse_track_file_reads_genre(self, tmp_path):
        f = tmp_path / "01-x.md"
        _write_track(f, 10, "doom-metal")
        assert parse_track_file(f).get("genre") == "doom-metal"

    def test_genre_absent_when_not_declared(self, tmp_path):
        f = tmp_path / "01-x.md"
        _write_track(f, 10, None)
        assert "genre" not in parse_track_file(f)

    def test_blank_genre_is_ignored(self, tmp_path):
        f = tmp_path / "01-x.md"
        f.write_text('---\ntitle: "T"\ngenre: "   "\n---\n\n# T\n', encoding="utf-8")
        assert "genre" not in parse_track_file(f)
