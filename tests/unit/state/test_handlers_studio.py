"""open_in_studio and find_studio_download: the Suno Studio route for importing a keeper.

When the account's download credits run out, /bitwize-music:import-audio opens
the keeper in Suno Studio in a real browser; the user selects the whole
waveform and clicks Download .WAV, and the file is picked up from ~/Downloads.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for _path in (PROJECT_ROOT, SERVER_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from handlers import _shared as shared_mod
from handlers import studio as studio_mod
from tools.playback import browser as browser_mod

pytestmark = pytest.mark.unit

CLIP = "e892f3fd-2d28-4093-b897-d0c419cda7ea"
STUDIO_URL = f"https://suno.com/studio?for_clip_id={CLIP}&create_new=1"

README = """---
title: "Paper Boats"
---
# Paper Boats

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Complete |
"""


def _track(link: str) -> str:
    return (
        '---\ntitle: "Harbor"\n---\n# Harbor\n\n## Track Details\n\n'
        "| Attribute | Detail |\n|-----------|--------|\n"
        "| **Title** | Harbor |\n| **Status** | Final |\n"
        f"| **Suno Link** | {link} |\n"
    )


class _Cache:
    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def get_state_ref(self):
        return self.state


@pytest.fixture
def album(tmp_path, monkeypatch):
    """An album with a keeper, indexed by the real indexer; launches are recorded, not run."""
    from tools.state.indexer import build_state

    content = tmp_path / "content" / "artists" / "bitwize" / "albums" / "folk" / "paper-boats"
    (content / "tracks").mkdir(parents=True)
    (content / "README.md").write_text(README, encoding="utf-8")
    track = content / "tracks" / "01-harbor.md"
    track.write_text(_track(f"[Listen](https://suno.com/song/{CLIP})"), encoding="utf-8")

    def index(**generation):
        state = build_state({
            "artist": {"name": "bitwize"},
            "paths": {"content_root": str(tmp_path / "content"),
                      "audio_root": str(tmp_path / "audio"),
                      "documents_root": str(tmp_path / "documents")},
            "generation": generation,
        }, plugin_root=tmp_path)
        monkeypatch.setattr(shared_mod, "cache", _Cache(state))

    index()
    launched: list[tuple[str, object]] = []
    open_result = {"returncode": 0, "stderr": ""}

    def run_open(argv):
        launched.append(("open", argv))
        return subprocess.CompletedProcess(argv, open_result["returncode"], "", open_result["stderr"])

    monkeypatch.setattr(browser_mod, "_run_open", run_open)
    monkeypatch.setattr(browser_mod, "_on_macos", lambda: True)
    monkeypatch.setattr(browser_mod.webbrowser, "open_new_tab",
                        lambda url: launched.append(("default", url)) or True)
    return {"track": track, "launched": launched, "index": index, "open_result": open_result}


def _open(**kwargs) -> dict:
    kwargs.setdefault("plan", "Premier Plan")
    return json.loads(asyncio.run(studio_mod.open_in_studio("paper-boats", "01", **kwargs)))


class TestOpenInStudio:
    def test_premier_opens_the_keeper_in_the_default_browser(self, album):
        before = datetime.now(UTC)
        result = _open()
        assert result["url"] == STUDIO_URL
        assert result["clip_id"] == CLIP
        assert result["browser"] == "default"
        assert album["launched"] == [("default", STUDIO_URL)]
        opened_at = datetime.fromisoformat(result["opened_at"])
        assert before - timedelta(seconds=1) <= opened_at <= datetime.now(UTC)
        assert "Download .WAV" in result["next"]

    @pytest.mark.parametrize("plan", ["Pro Plan", "Free Plan", ""])
    def test_studio_needs_premier(self, album, plan):
        result = _open(plan=plan)
        assert "Premier" in result["error"]
        assert album["launched"] == []

    def test_the_configured_browser_is_opened_by_name(self, album):
        album["index"](studio_browser="Firefox")
        result = _open()
        assert album["launched"] == [("open", ["/usr/bin/open", "-a", "Firefox", STUDIO_URL])]
        assert result["browser"] == "Firefox"

    def test_the_setting_can_be_a_path_to_an_app(self, album):
        app = "/Applications/Firefox Developer Edition.app"
        album["index"](studio_browser=app)
        assert _open()["browser"] == app
        assert album["launched"] == [("open", ["/usr/bin/open", "-a", app, STUDIO_URL])]

    def test_default_spelled_out_is_the_systems_browser(self, album):
        album["index"](studio_browser="default")
        assert _open()["browser"] == "default"
        assert album["launched"] == [("default", STUDIO_URL)]

    def test_a_browser_for_one_run_overrides_the_setting(self, album):
        album["index"](studio_browser="Firefox")
        _open(browser="Safari")
        assert album["launched"] == [("open", ["/usr/bin/open", "-a", "Safari", STUDIO_URL])]

    def test_a_browser_that_isnt_installed_falls_back_to_the_default_and_says_so(self, album):
        album["index"](studio_browser="Netscape")
        album["open_result"].update(returncode=1, stderr="Unable to find application named 'Netscape'\n")
        result = _open()
        assert album["launched"][-1] == ("default", STUDIO_URL)
        assert result["browser"] == "default"
        assert "Netscape" in result["note"]
        assert "Unable to find application" in result["note"]

    @pytest.mark.parametrize("where", ["setting", "run"])
    def test_iterm2_is_refused(self, album, where):
        """Studio hands the WAV over as a blob: URL, which iTerm2's browser can't save."""
        if where == "setting":
            album["index"](studio_browser="iTerm2")
            result = _open()
        else:
            result = _open(browser="iTerm")
        assert "blob:" in result["error"]
        assert album["launched"] == []

    def test_elsewhere_a_named_browser_goes_through_webbrowser(self, album, monkeypatch):
        album["index"](studio_browser="firefox")
        monkeypatch.setattr(browser_mod, "_on_macos", lambda: False)

        class _Browser:
            def open_new_tab(self, url):
                album["launched"].append(("firefox", url))
                return True

        monkeypatch.setattr(browser_mod.webbrowser, "get", lambda name: _Browser())
        result = _open()
        assert album["launched"] == [("firefox", STUDIO_URL)]
        assert result["browser"] == "firefox"

    def test_no_browser_at_all_gives_the_link_to_open_by_hand(self, album, monkeypatch):
        monkeypatch.setattr(browser_mod.webbrowser, "open_new_tab", lambda url: False)
        result = _open()
        assert result["browser"] is None
        assert result["url"] == STUDIO_URL
        assert "by hand" in result["hint"]

    def test_a_track_without_a_keeper_opens_nothing(self, album):
        album["track"].write_text(_track(""), encoding="utf-8")
        result = _open()
        assert "keeper" in result["error"]
        assert [p["code"] for p in result["problems"]] == ["no_keeper"]
        assert album["launched"] == []

    def test_a_legacy_share_link_has_no_clip_to_open(self, album):
        album["track"].write_text(_track("[Listen](https://suno.com/s/AbC123)"), encoding="utf-8")
        result = _open()
        assert [p["code"] for p in result["problems"]] == ["legacy_link"]
        assert album["launched"] == []


# --- find_studio_download -------------------------------------------------


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    folder = tmp_path / "Downloads"
    folder.mkdir()
    monkeypatch.setattr(studio_mod, "DOWNLOADS_DIR", folder)
    return folder


def _wav(path: Path, seconds: float, age: float = 5.0) -> Path:
    """A finished download: written, then left alone for `age` seconds."""
    sf.write(str(path), np.zeros((int(8000 * seconds), 2), dtype=np.float32), 8000, subtype="PCM_16")
    stamp = time.time() - age
    os.utime(path, (stamp, stamp))
    return path


def _since(seconds_ago: float = 60.0) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat()


def _find(**kwargs) -> dict:
    kwargs.setdefault("since", _since())
    kwargs.setdefault("wait_seconds", 0)
    return json.loads(asyncio.run(studio_mod.find_studio_download(**kwargs)))


class TestFindStudioDownload:
    def test_finds_the_finished_wav_and_checks_it_against_the_song(self, downloads):
        _wav(downloads / "Harbor [0m00s-0m02s].wav", 2.0)
        _wav(downloads / "Older song.wav", 2.0, age=3600)  # from before Studio opened
        result = _find(title="Harbor", expected_seconds=2.0)
        assert result["status"] == "found"
        assert result["name"] == "Harbor [0m00s-0m02s].wav"
        assert result["file"] == str(downloads / "Harbor [0m00s-0m02s].wav")
        assert result["seconds"] == pytest.approx(2.0, abs=0.01)
        assert (result["sample_rate"], result["channels"]) == (8000, 2)
        assert (result["title_matches"], result["length_matches"]) == (True, True)
        assert result["problems"] == []

    def test_a_short_file_means_the_selection_missed_part_of_the_song(self, downloads):
        _wav(downloads / "Harbor [0m00s-0m02s].wav", 2.0)
        result = _find(title="Harbor", expected_seconds=157.5)
        assert result["status"] == "found"
        assert result["length_matches"] is False
        assert "whole waveform" in result["problems"][0]

    def test_nothing_while_the_browser_is_still_writing(self, downloads):
        _wav(downloads / "Harbor [0m00s-0m02s].wav", 2.0)
        (downloads / "Harbor [0m00s-0m02s].wav.part").write_bytes(b"\0" * 10)
        result = _find()
        assert result["status"] == "not_found"
        assert result["downloading"] == ["Harbor [0m00s-0m02s].wav.part"]

    def test_a_file_written_a_moment_ago_may_still_be_growing(self, downloads):
        _wav(downloads / "Harbor [0m00s-0m02s].wav", 2.0, age=0.0)
        assert _find()["status"] == "not_found"

    def test_nothing_new_says_so(self, downloads):
        _wav(downloads / "Older song.wav", 2.0, age=3600)
        result = _find()
        assert result["status"] == "not_found"
        assert result["downloading"] == []
        assert "Download .WAV" in result["hint"]

    def test_the_title_picks_between_several(self, downloads):
        _wav(downloads / "Something else.wav", 2.0)
        _wav(downloads / "Harbor [0m00s-0m02s].wav", 2.0)
        result = _find(title="Harbor")
        assert result["status"] == "found"
        assert result["name"] == "Harbor [0m00s-0m02s].wav"

    def test_several_without_a_way_to_choose_are_listed(self, downloads):
        _wav(downloads / "One.wav", 2.0)
        _wav(downloads / "Two.wav", 2.0)
        result = _find()
        assert result["status"] == "several"
        assert sorted(c["name"] for c in result["candidates"]) == ["One.wav", "Two.wav"]

    def test_waits_for_the_download_to_land(self, downloads, monkeypatch):
        naps = []

        async def nap(seconds):
            naps.append(seconds)
            _wav(downloads / "Harbor [0m00s-0m02s].wav", 2.0)

        monkeypatch.setattr(studio_mod, "_sleep", nap)
        result = _find(wait_seconds=30)
        assert result["status"] == "found"
        assert naps == [studio_mod.POLL_SECONDS]

    def test_a_since_that_isnt_a_time_is_an_error(self, downloads):
        assert "since" in _find(since="yesterday")["error"]
