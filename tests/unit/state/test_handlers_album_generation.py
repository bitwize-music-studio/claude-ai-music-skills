#!/usr/bin/env python3
"""Unit tests for handlers/album_generation.py and handlers/suno_midi.py.

    get_album_generation_plan(album)   — which tracks can be generated now, and the cost
    get_suno_midi_plan(album, track)   — the keeper clip to transcribe and where the .mid goes

Usage:
    python -m pytest tests/unit/state/test_handlers_album_generation.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: F401  (album is a fixture)
    CLIP_A,
    CLIP_B,
    LEGACY_KEEPER_ROW,
    _row,
    _run,
    album,
    track_md,
)

from handlers import album_generation as _plan_mod  # noqa: E402
from handlers import suno_midi as _midi_mod  # noqa: E402

pytestmark = pytest.mark.unit

WORKSPACE_ID = "be7f57b5-0cef-4769-ab0e-44b4861bd895"


def _plan(album_slug="test-album"):
    return json.loads(_run(_plan_mod.get_album_generation_plan(album_slug)))


def _add(album, slug, title, status="In Progress", **track):  # noqa: F811
    path = album.path.parent / f"{slug}.md"
    path.write_text(track_md(title=title, status=status, **track), encoding="utf-8")
    album.state["albums"]["test-album"]["tracks"][slug] = {
        "title": title, "status": status, "path": str(path),
    }


@pytest.fixture
def batch(album, monkeypatch):  # noqa: F811
    """Five tracks: ready, ready with Max Mode off, gate-blocked, unsupported model, already generated."""
    tracks = album.state["albums"]["test-album"]["tracks"]
    del tracks["02-no-path"]
    _add(album, "02-second", "Second", settings={"Max Mode": "Off"})
    _add(album, "03-blocked", "Blocked")
    _add(album, "04-custom", "Custom", settings={"Model": "Custom: my-model"})
    _add(album, "05-done", "Done", status="Generated", log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)))

    def fake_gates(track, text, blocklist, max_lyric_words=800):
        if track.get("title") == "Blocked":
            return 2, 0, [
                {"gate": "Sources Verified", "status": "FAIL", "severity": "BLOCKING"},
                {"gate": "Homograph Check", "status": "FAIL", "severity": "BLOCKING"},
                {"gate": "Explicit Flag Set", "status": "PASS"},
            ]
        return 0, 0, []

    monkeypatch.setattr(_plan_mod, "_check_pre_gen_gates_for_track", fake_gates)
    monkeypatch.setattr(_plan_mod, "_load_artist_blocklist", lambda: [])
    return album


class TestGetAlbumGenerationPlan:
    def test_sorts_tracks_into_generate_blocked_and_skipped(self, batch):
        plan = _plan()
        assert plan["found"] is True
        assert plan["generate"] == ["01-first-track", "02-second"]
        assert plan["blocked"] == ["03-blocked", "04-custom"]
        assert plan["skipped"] == ["05-done"]
        by_slug = {t["track_slug"]: t for t in plan["tracks"]}
        assert by_slug["01-first-track"] == {
            "track_slug": "01-first-track", "title": "First Track", "status": "In Progress",
            "action": "generate", "reason": "", "max_mode": True, "credits": 20,
        }
        assert by_slug["02-second"]["credits"] == 10
        assert by_slug["03-blocked"]["action"] == "blocked"
        assert by_slug["03-blocked"]["reason"] == "gates: Sources Verified, Homograph Check"
        assert by_slug["04-custom"]["action"] == "blocked"
        assert "Custom Model" in by_slug["04-custom"]["reason"]
        assert by_slug["05-done"]["action"] == "skip"
        assert by_slug["05-done"]["reason"] == "already has takes"

    def test_totals(self, batch):
        plan = _plan()
        assert plan["calls"] == 2
        assert plan["takes"] == 4
        assert plan["estimated_credits"] == 30

    def test_final_track_without_a_log_is_skipped(self, batch):
        _add(batch, "06-final", "Final One", status="Final")
        entry = next(t for t in _plan()["tracks"] if t["track_slug"] == "06-final")
        assert (entry["action"], entry["reason"]) == ("skip", "status is Final")

    def test_workspace_and_suggested_name(self, batch):
        plan = _plan()
        assert plan["workspace"] is None
        assert plan["suggested_workspace_name"] == "Test Album"
        batch.state["albums"]["test-album"]["suno_workspace"] = {"id": WORKSPACE_ID, "name": "Test Album"}
        assert _plan()["workspace"] == {"id": WORKSPACE_ID, "name": "Test Album"}

    def test_nothing_to_generate(self, batch):
        tracks = batch.state["albums"]["test-album"]["tracks"]
        for slug in ("01-first-track", "02-second", "03-blocked", "04-custom"):
            del tracks[slug]
        plan = _plan()
        assert plan["generate"] == [] and plan["calls"] == 0 and plan["estimated_credits"] == 0

    def test_unknown_album(self, batch):
        assert _plan("nope")["found"] is False


# ===========================================================================
# get_suno_midi_plan
# ===========================================================================


def _midi(track_slug="01-first-track"):
    return json.loads(_run(_midi_mod.get_suno_midi_plan("test-album", track_slug)))


class TestGetSunoMidiPlan:
    def test_keeper_and_target_path(self, album):  # noqa: F811
        album(suno_link=f"[Listen](https://suno.com/song/{CLIP_A})", status="Final")
        plan = _midi()
        assert plan["found"] is True
        assert plan["clip_id"] == CLIP_A
        assert plan["problems"] == []
        target = album.audio_dir / "sheet-music" / "source" / "01-first-track.mid"
        assert plan["midi"] == {"path": str(target), "existing": False}
        assert plan["credits"] == 10

    def test_existing_file_is_reported(self, album):  # noqa: F811
        album(suno_link=f"https://suno.com/song/{CLIP_A}", status="Final")
        target = album.audio_dir / "sheet-music" / "source" / "01-first-track.mid"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"MThd")
        assert _midi()["midi"]["existing"] is True

    def test_no_keeper(self, album):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)))
        plan = _midi()
        assert plan["clip_id"] is None
        assert [p["code"] for p in plan["problems"]] == ["no_keeper"]

    def test_legacy_link(self, album):  # noqa: F811
        album(log_rows=(LEGACY_KEEPER_ROW,), suno_link="https://suno.com/s/4hZKwZySCc8Lc63Q")
        assert [p["code"] for p in _midi()["problems"]] == ["legacy_link"]

    def test_unknown_track(self, album):  # noqa: F811
        assert _midi("99-missing")["found"] is False
