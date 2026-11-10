#!/usr/bin/env python3
"""Unit tests for handlers/playback.py — auditioning tools.

    get_listen_plan(album, track)  — takes, local files and the default target
    play_audio(path, ...)          — start a local player (detached)
    stop_audio()                   — stop it
    open_song_page(urls)           — open Suno song pages in the browser

The player and the browser are faked; nothing here makes sound or opens a
window. Reuses the track-file builder from test_handlers_generation.py.

Usage:
    python -m pytest tests/unit/state/test_handlers_playback.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.state.test_handlers_generation import (  # noqa: E402
    CLIP_A,
    CLIP_B,
    LEGACY_KEEPER_ROW,
    _row,
    _run,
    album,  # noqa: F401 - pytest fixture
)

from handlers import playback as _playback_mod  # noqa: E402
from tools.playback import player  # noqa: E402

CLIP_C = "5f044d3b-fa97-4ace-b9f8-d9aa99933230"


def _listen_plan(track_slug="01-first-track"):
    return json.loads(_run(_playback_mod.get_listen_plan("test-album", track_slug)))


def _stage_file(album, stage, name="01-first-track.wav"):  # noqa: F811
    directory = album.audio_dir if stage == "original" else album.audio_dir / stage
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"RIFF")
    return path


# ===========================================================================
# get_listen_plan
# ===========================================================================


class TestGetListenPlan:
    def test_fresh_generation_defaults_to_auditioning_both_takes(self, album, monkeypatch):  # noqa: F811
        monkeypatch.setattr(player.shutil, "which", lambda name: "/usr/bin/mpv" if name == "mpv" else None)
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)), status="Generated")
        plan = _listen_plan()

        assert plan["found"] is True
        assert plan["track_slug"] == "01-first-track"
        assert plan["title"] == "First Track"
        assert plan["mode"] == "browser"
        assert plan["confirm_download"] is True
        assert plan["player"] == "mpv"
        assert plan["default"] == {"kind": "takes", "rows": [1, 2]}
        assert plan["takes"][0] == {
            "row": 1,
            "date": "2026-06-15",
            "model": "v6",
            "url": f"https://suno.com/song/{CLIP_A}",
            "clip_id": CLIP_A,
            "rating": "—",
            "approved": False,
            "is_keeper": False,
            "duration_s": None,
            "credits": None,
            "version": "",
            "cache_path": str(player.takes_cache_dir() / f"{CLIP_A}.mp3"),
            "cached": False,
        }

    def test_takes_carry_their_logged_length_and_cost(self, album):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A, notes="0:52, via MCP, 10 credits"),))
        take = _listen_plan()["takes"][0]
        assert (take["duration_s"], take["credits"]) == (52, 10)

    def test_cached_take_is_flagged(self, album):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)))
        cache = player.takes_cache_dir()
        cache.mkdir(parents=True)
        (cache / f"{CLIP_B}.mp3").write_bytes(b"ID3")
        cached = {t["row"]: t["cached"] for t in _listen_plan()["takes"]}
        assert cached == {1: False, 2: True}

    def test_only_the_newest_two_pending_takes_are_the_default(self, album):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B), _row(3, CLIP_C), _row(4, CLIP_A)))
        assert _listen_plan()["default"] == {"kind": "takes", "rows": [3, 4]}

    def test_legacy_share_link_can_only_be_opened_in_the_browser(self, album):  # noqa: F811
        album(log_rows=(LEGACY_KEEPER_ROW,), suno_link="https://suno.com/s/4hZKwZySCc8Lc63Q")
        take = _listen_plan()["takes"][0]
        assert take["clip_id"] is None
        assert take["cache_path"] is None
        assert take["cached"] is False
        assert take["is_keeper"] is True

    def test_rows_without_a_link_are_left_out(self, album):  # noqa: F811
        album(log_rows=(
            "| 1 | 2026-06-15 | v6 | Failed | error: moderation | — |",
            _row(2, CLIP_A),
        ))
        assert [t["row"] for t in _listen_plan()["takes"]] == [2]

    def test_keeper_is_the_take_in_the_suno_link(self, album):  # noqa: F811
        album(
            log_rows=(_row(1, CLIP_A), _row(2, CLIP_B, "✓")),
            suno_link=f"[Listen](https://suno.com/song/{CLIP_B})",
            status="Final",
        )
        plan = _listen_plan()
        assert [t["is_keeper"] for t in plan["takes"]] == [False, True]
        assert plan["default"] == {"kind": "takes", "rows": [2]}

    @pytest.mark.parametrize(
        "stages,expected",
        [
            (("original",), "original"),
            (("original", "polished"), "polished"),
            (("original", "polished", "mastered"), "mastered"),
        ],
    )
    def test_approved_track_defaults_to_the_newest_local_stage(self, album, stages, expected):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A, "✓"),), suno_link=f"https://suno.com/song/{CLIP_A}")
        paths = {stage: _stage_file(album, stage) for stage in stages}
        plan = _listen_plan()
        assert plan["default"] == {"kind": "local", "stage": expected, "path": str(paths[expected])}
        for stage in ("original", "polished", "mastered"):
            assert plan["local"][stage] == (str(paths[stage]) if stage in paths else None)

    def test_originals_directory_is_the_original_stage_when_present(self, album):  # noqa: F811
        original = _stage_file(album, "originals")
        assert _listen_plan()["local"]["original"] == str(original)

    def test_pending_takes_win_over_local_files(self, album):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)))
        _stage_file(album, "original")
        assert _listen_plan()["default"]["kind"] == "takes"

    def test_nothing_to_play(self, album):  # noqa: F811
        plan = _listen_plan()
        assert plan["takes"] == []
        assert plan["default"] == {"kind": "none"}

    def test_config_overrides(self, album):  # noqa: F811
        album.state["config"]["generation"] = {
            "listen_mode": "terminal", "listen_confirm_download": False,
        }
        plan = _listen_plan()
        assert plan["mode"] == "terminal"
        assert plan["confirm_download"] is False

    def test_no_player_installed(self, album, monkeypatch):  # noqa: F811
        monkeypatch.setattr(player.shutil, "which", lambda name: None)
        assert _listen_plan()["player"] is None

    def test_missing_audio_config_still_lists_takes(self, album):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A),))
        album.state["config"]["audio_root"] = ""
        plan = _listen_plan()
        assert [t["row"] for t in plan["takes"]] == [1]
        assert plan["local"] == {"original": None, "polished": None, "mastered": None}

    def test_like_keeper_follows_the_config(self, album):  # noqa: F811
        assert _listen_plan()["like_keeper"] is True
        album.state["config"]["generation"] = {"like_keeper": False}
        assert _listen_plan()["like_keeper"] is False

    def test_iterm_mode_from_config(self, album):  # noqa: F811
        album.state["config"]["generation"] = {"listen_mode": "iterm2_browser"}
        assert _listen_plan()["mode"] == "iterm2_browser"

    def test_reports_whether_iterm_panes_can_be_used(self, album, monkeypatch):  # noqa: F811
        monkeypatch.setattr(_playback_mod._iterm, "unavailable_reason", lambda: None)
        assert _listen_plan()["iterm2"] == {"available": True, "reason": None}

        reason = "this session is not running inside iTerm2"
        monkeypatch.setattr(_playback_mod._iterm, "unavailable_reason", lambda: reason)
        assert _listen_plan()["iterm2"] == {"available": False, "reason": reason}

    def test_unknown_track(self, album):  # noqa: F811
        assert _listen_plan(track_slug="99-missing")["found"] is False


# ===========================================================================
# play_audio / stop_audio
# ===========================================================================


class TestPlayAndStop:
    def test_play_passes_the_allowed_roots_and_times(self, album, monkeypatch):  # noqa: F811
        calls = {}

        def fake_play(path, roots, start_s=0.0, length_s=None):
            calls.update(path=path, roots=roots, start_s=start_s, length_s=length_s)
            return {"playing": True, "player": "mpv", "pid": 1, "path": path, "start_s": start_s,
                    "command": "mpv -- x"}

        monkeypatch.setattr(player, "play", fake_play)
        monkeypatch.setattr(player, "audio_duration", lambda path: 193.5)

        result = json.loads(_run(_playback_mod.play_audio("/x/01.wav", start_s=90, length_s=30)))
        assert result["playing"] is True
        assert result["duration_s"] == 193.5
        assert calls["path"] == "/x/01.wav"
        assert calls["start_s"] == 90
        assert calls["length_s"] == 30
        assert calls["roots"] == [
            Path(album.state["config"]["audio_root"]), player.takes_cache_dir(),
        ]

    def test_zero_length_means_play_to_the_end(self, album, monkeypatch):  # noqa: F811
        calls = {}

        def fake_play(path, roots, start_s=0.0, length_s=None):
            calls["length_s"] = length_s
            return {"playing": True, "path": path}

        monkeypatch.setattr(player, "play", fake_play)
        monkeypatch.setattr(player, "audio_duration", lambda path: None)
        _run(_playback_mod.play_audio("/x/01.wav"))
        assert calls["length_s"] is None

    def test_playback_error_is_reported_not_raised(self, album):  # noqa: F811
        result = json.loads(_run(_playback_mod.play_audio("https://suno.com/song/x.mp3")))
        assert result["playing"] is False
        assert "local files" in result["error"]

    def test_player_that_fails_to_start_is_reported(self, album, monkeypatch):  # noqa: F811
        def boom(*args, **kwargs):
            raise OSError("exec format error")

        monkeypatch.setattr(player, "play", boom)
        result = json.loads(_run(_playback_mod.play_audio("/x/01.wav")))
        assert result["playing"] is False
        assert "exec format error" in result["error"]

    def test_stop(self, album, monkeypatch):  # noqa: F811
        monkeypatch.setattr(
            player, "stop", lambda: {"stopped": True, "path": "/x/01.wav", "position_s": 42.5},
        )
        assert json.loads(_run(_playback_mod.stop_audio())) == {
            "stopped": True, "path": "/x/01.wav", "position_s": 42.5,
        }


# ===========================================================================
# open_song_page
# ===========================================================================


@pytest.fixture
def browser(monkeypatch):
    opened = []

    def fake_open(url):
        opened.append(url)
        return True

    monkeypatch.setattr(_playback_mod.webbrowser, "open_new_tab", fake_open)
    return opened


@pytest.fixture(autouse=True)
def not_in_iterm(monkeypatch):
    """The same answers on every machine: by default iTerm2 panes are not on offer."""
    monkeypatch.setattr(
        _playback_mod._iterm, "unavailable_reason", lambda: "iTerm2 panes need macOS"
    )


def _open(urls, where=None):
    if where is None:
        return json.loads(_run(_playback_mod.open_song_page(urls)))
    return json.loads(_run(_playback_mod.open_song_page(urls, where)))


class TestOpenSongPage:
    def test_opens_each_song_page(self, browser):
        urls = [f"https://suno.com/song/{CLIP_A}", f"https://suno.com/song/{CLIP_B}"]
        assert _open(urls) == {"opened": urls, "failed": [], "where": "browser"}
        assert browser == urls

    def test_legacy_share_link_is_allowed(self, browser):
        url = "https://suno.com/s/4hZKwZySCc8Lc63Q"
        assert _open([url])["opened"] == [url]

    @pytest.mark.parametrize(
        "url",
        [
            "http://suno.com/song/4ef71736-b95e-489b-b5ac-1a41badceb08",
            "https://evil.example/song/4ef71736-b95e-489b-b5ac-1a41badceb08",
            "https://suno.com.evil.example/song/4ef71736-b95e-489b-b5ac-1a41badceb08",
            "https://suno.com/song/4ef71736-b95e-489b-b5ac-1a41badceb08/../../account",
            "https://suno.com/song/4ef71736-b95e-489b-b5ac-1a41badceb08?next=https://evil.example",
            "https://suno.com/account",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "",
        ],
    )
    def test_anything_but_a_song_page_is_refused(self, browser, url):
        result = _open([f"https://suno.com/song/{CLIP_A}", url])
        assert "error" in result
        assert browser == []

    def test_no_urls(self, browser):
        assert "error" in _open([])

    def test_too_many_urls(self, browser):
        assert "error" in _open([f"https://suno.com/song/{CLIP_A}"] * 5)
        assert browser == []

    def test_browser_that_cannot_open_is_reported(self, monkeypatch):
        monkeypatch.setattr(_playback_mod.webbrowser, "open_new_tab", lambda url: False)
        url = f"https://suno.com/song/{CLIP_A}"
        result = _open([url])
        assert result["opened"] == []
        assert result["failed"] == [url]
        assert "hint" in result

    def test_browser_error_is_reported(self, monkeypatch):
        def boom(url):
            raise _playback_mod.webbrowser.Error("no browser")

        monkeypatch.setattr(_playback_mod.webbrowser, "open_new_tab", boom)
        assert _open([f"https://suno.com/song/{CLIP_A}"])["failed"] == [
            f"https://suno.com/song/{CLIP_A}",
        ]


class TestOpenSongPageInIterm:
    def test_opens_panes_instead_of_the_browser(self, browser, monkeypatch):
        seen = {}

        def fake_open(urls):
            seen["urls"] = urls
            return {"panes": ["PANE-1", "PANE-2"], "pages": ["player-1", "player-2"]}

        monkeypatch.setattr(_playback_mod._iterm, "open_in_panes", fake_open)
        urls = [f"https://suno.com/song/{CLIP_A}", f"https://suno.com/song/{CLIP_B}"]
        assert _open(urls, "iterm2_browser") == {
            "opened": urls, "failed": [], "where": "iterm2_browser", "panes": ["PANE-1", "PANE-2"],
        }
        assert seen["urls"] == urls
        assert browser == []

    def test_falls_back_to_the_browser_and_says_why(self, browser, monkeypatch):
        def unavailable(urls):
            raise _playback_mod._iterm.ItermError("this session is not running inside iTerm2")

        monkeypatch.setattr(_playback_mod._iterm, "open_in_panes", unavailable)
        url = f"https://suno.com/song/{CLIP_A}"
        result = _open([url], "iterm2_browser")
        assert result["where"] == "browser"
        assert result["opened"] == [url]
        assert "not running inside iTerm2" in result["note"]
        assert browser == [url]

    def test_urls_are_checked_before_iterm_is_touched(self, browser, monkeypatch):
        def must_not_run(urls):
            raise AssertionError("open_in_panes must not be called for a bad URL")

        monkeypatch.setattr(_playback_mod._iterm, "open_in_panes", must_not_run)
        result = _open(["https://evil.example/song/4ef71736-b95e-489b-b5ac-1a41badceb08"], "iterm2_browser")
        assert "error" in result
        assert browser == []

    def test_unknown_destination(self, browser):
        result = _open([f"https://suno.com/song/{CLIP_A}"], "hologram")
        assert "error" in result
        assert browser == []


class TestCloseSongPanes:
    def test_closes_the_panes(self, monkeypatch):
        monkeypatch.setattr(_playback_mod._iterm, "close_panes", lambda: {"closed": 2})
        assert json.loads(_run(_playback_mod.close_song_panes())) == {"closed": 2}


# ===========================================================================
# compare_audio
# ===========================================================================


class TestCompareAudio:
    def test_plays_the_same_passage_of_each_file(self, album, monkeypatch):  # noqa: F811
        calls = {}

        def fake_compare(paths, roots, start_s=0.0, length_s=15.0):
            calls.update(paths=paths, roots=roots, start_s=start_s, length_s=length_s)
            return {"playing": True, "player": "mpv", "pid": 7, "paths": paths,
                    "start_s": start_s, "length_s": length_s, "total_s": length_s * len(paths)}

        monkeypatch.setattr(player, "compare", fake_compare)
        result = json.loads(_run(_playback_mod.compare_audio(["/x/a.mp3", "/x/b.mp3"], 45, 10)))
        assert result["playing"] is True
        assert result["total_s"] == 20
        assert calls["paths"] == ["/x/a.mp3", "/x/b.mp3"]
        assert (calls["start_s"], calls["length_s"]) == (45, 10)
        assert calls["roots"] == [
            Path(album.state["config"]["audio_root"]), player.takes_cache_dir(),
        ]

    def test_a_player_error_is_reported_not_raised(self, album, monkeypatch):  # noqa: F811
        def refuse(paths, roots, start_s=0.0, length_s=15.0):
            raise player.PlaybackError("Comparing passages needs mpv")

        monkeypatch.setattr(player, "compare", refuse)
        result = json.loads(_run(_playback_mod.compare_audio(["/x/a.mp3", "/x/b.mp3"])))
        assert result == {"playing": False, "error": "Comparing passages needs mpv"}


# ===========================================================================
# prune_takes_cache
# ===========================================================================

ORPHAN = "0f3c6c19-0c42-4d4f-9a37-7f5fd1bd2e01"


@pytest.fixture
def cache(album):  # noqa: F811
    """Track 01 is Generated with two undecided takes (A, B); the cache also holds an orphan."""
    album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B)), status="Generated")
    album.state["albums"]["test-album"]["tracks"]["01-first-track"]["status"] = "Generated"
    directory = player.takes_cache_dir()
    directory.mkdir(parents=True)
    for name, size in ((f"{CLIP_A}.mp3", 10), (f"{CLIP_B}.mp3", 20), (f"{ORPHAN}.mp3", 300),
                       (f"{CLIP_C}.mp3.part", 4000), ("notes.txt", 5)):
        (directory / name).write_bytes(b"x" * size)
    return directory


def _prune(dry_run=None):
    call = _playback_mod.prune_takes_cache() if dry_run is None else _playback_mod.prune_takes_cache(dry_run)
    return json.loads(_run(call))


class TestPruneTakesCache:
    def test_dry_run_is_the_default_and_deletes_nothing(self, cache):
        result = _prune()
        assert result["dry_run"] is True
        assert sorted(item["file"] for item in result["removed"]) == sorted(
            [f"{ORPHAN}.mp3", f"{CLIP_C}.mp3.part"])
        assert result["freed_bytes"] == 4300
        assert result["kept"] == 2
        assert len(list(cache.iterdir())) == 5

    def test_takes_awaiting_a_decision_are_kept(self, cache):
        result = _prune(False)
        assert result["dry_run"] is False
        assert sorted(p.name for p in cache.iterdir()) == sorted(
            [f"{CLIP_A}.mp3", f"{CLIP_B}.mp3", "notes.txt"])
        reasons = {item["file"]: item["reason"] for item in result["removed"]}
        assert reasons[f"{ORPHAN}.mp3"] == "not awaiting a decision"
        assert reasons[f"{CLIP_C}.mp3.part"] == "unfinished download"

    def test_once_a_keeper_is_chosen_the_takes_go(self, cache, album):  # noqa: F811
        album(log_rows=(_row(1, CLIP_A), _row(2, CLIP_B, rating="✓")), status="Generated")
        _prune(False)
        assert sorted(p.name for p in cache.iterdir()) == ["notes.txt"]

    def test_a_track_that_is_not_generated_keeps_nothing(self, cache, album):  # noqa: F811
        album.state["albums"]["test-album"]["tracks"]["01-first-track"]["status"] = "Final"
        assert _prune()["kept"] == 0

    def test_no_cache_directory(self, album):  # noqa: F811
        assert _prune(False) == {"dry_run": False, "removed": [], "kept": 0, "freed_bytes": 0}


class TestVersionsInTheListenPlan:
    def test_a_version_row_is_labelled_and_is_never_the_keeper(self, album):
        album(log_rows=(
            _row(1, CLIP_A, "✓"),
            _row(2, CLIP_B, "✓", notes="0:55, instrumental version of take 1, via MCP"),
        ))
        takes = _listen_plan()["takes"]
        assert [(t["row"], t["version"], t["approved"]) for t in takes] == [
            (1, "", True), (2, "instrumental", False),
        ]
