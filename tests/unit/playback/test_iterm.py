#!/usr/bin/env python3
"""Unit tests for tools/playback/iterm.py — song pages in iTerm2 split panes.

AppleScript is never run: ``_osascript`` is replaced by a fake that records
each call and answers the way iTerm2 does. The dynamic-profiles directory is a
temp folder, and pane state lands in the isolated state-cache directory that
the autouse conftest fixture provides.

Usage:
    python -m pytest tests/unit/playback/test_iterm.py -v
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.playback import iterm

pytestmark = pytest.mark.unit

# The real functions, kept from before any fixture swaps a fake in: the suite-wide
# guard in tests/conftest.py and the rig below both replace them for every test.
_REAL_OSASCRIPT = iterm._osascript
_REAL_PLUGIN_INSTALLED = iterm._plugin_installed

CLIP_A = "4ef71736-b95e-489b-b5ac-1a41badceb08"
CLIP_B = "6455b9ea-f786-4769-ac20-a2eb3eb49fee"
CLIP_C = "71af26e1-7ca6-486b-8511-a5a93ddc10df"
CLIP_D = "ede52b0a-e021-4b7e-8954-bc7628a969f6"
SONG_A = f"https://suno.com/song/{CLIP_A}"
SONG_B = f"https://suno.com/song/{CLIP_B}"
SONG_C = f"https://suno.com/song/{CLIP_C}"
SONG_D = f"https://suno.com/song/{CLIP_D}"
OWN_PANE = "287287FA-9DD5-4864-906A-0493BEAC469E"
# The pane a second Claude Code session runs in, in another tab.
OTHER_PANE = "C5E2A1B4-3D6F-4A8B-9C0D-1E2F3A4B5C6D"
FOCUSED_PANE = "74C908E1-918E-4B44-9639-F8736DA5E1C6"
# Pane ids in the order iTerm2 hands them out.
NEW_PANES = [
    "39DDADDC-8B9B-4E3E-8CE8-CDDED592FC6A",
    "70AFBF40-0693-4D9D-BF9F-A4EF90D9A17D",
    "9CC0417F-E7D6-445E-A6A6-56FE23F7072E",
    "1872EBF9-7236-4005-B379-D8E28035BAB3",
    "41989C4C-1E10-4413-AC2F-51A85AB8519A",
]


class FakeIterm:
    """Answers the scripts the way iTerm2 does, and records every call."""

    def __init__(self):
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.split_errors: list[str] = []  # raised, in order, before splits succeed
        self.split_answer: str | None = None  # answered instead of the two pane ids
        self.select_error: str | None = None
        self.list_error: str | None = None
        # The panes iTerm2 has open: the sessions' own, then every pane split off.
        self.live: set[str] = {OWN_PANE, OTHER_PANE, FOCUSED_PANE}
        self._next_pane = 0

    def __call__(self, script, *args):
        if script is iterm._SPLIT_SCRIPT:
            self.calls.append(("split", args))
            if self.split_errors:
                raise iterm.ItermError(self.split_errors.pop(0))
            if self.split_answer is not None:
                return self.split_answer
            pane = NEW_PANES[self._next_pane]
            self._next_pane += 1
            self.live.add(pane)
            return f"{args[0] or FOCUSED_PANE}\n{pane}"
        if script is iterm._CLOSE_SCRIPT:
            self.calls.append(("close", args))
            self.live.difference_update(args)
            return str(len(args))
        if script is iterm._SELECT_SCRIPT:
            self.calls.append(("select", args))
            if self.select_error:
                raise iterm.ItermError(self.select_error)
            return ""
        if script is iterm._LIST_SCRIPT:
            self.calls.append(("list", args))
            if self.list_error:
                raise iterm.ItermError(self.list_error)
            return "\n".join(sorted(self.live))
        raise AssertionError("unexpected script")

    def of(self, kind):
        return [args for name, args in self.calls if name == kind]


@pytest.fixture(autouse=True)
def rig(tmp_path, monkeypatch):
    """A fake iTerm2 for every test here, so none can reach the real one."""
    profiles_dir = tmp_path / "DynamicProfiles"
    fake = FakeIterm()
    monkeypatch.setattr(iterm, "_IS_MACOS", True)
    monkeypatch.setattr(iterm, "dynamic_profiles_dir", lambda: profiles_dir)
    monkeypatch.setattr(iterm, "_plugin_installed", lambda: True)
    monkeypatch.setattr(iterm, "_osascript", fake)
    monkeypatch.setattr(iterm.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(iterm.time, "sleep", lambda seconds: None)
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.setenv("TERM_PROGRAM_VERSION", "3.6.6")
    monkeypatch.setenv("ITERM_SESSION_ID", f"w0t1p0:{OWN_PANE}")
    fake.profiles_dir = profiles_dir
    return fake


def _profiles():
    return json.loads(iterm.profiles_path().read_text(encoding="utf-8"))["Profiles"]


# ===========================================================================
# unavailable_reason
# ===========================================================================


class TestUnavailableReason:
    def test_available(self, rig):
        assert iterm.unavailable_reason() is None

    def test_not_macos(self, rig, monkeypatch):
        monkeypatch.setattr(iterm, "_IS_MACOS", False)
        assert "macOS" in iterm.unavailable_reason()

    @pytest.mark.parametrize("program", ["Apple_Terminal", "vscode", ""])
    def test_not_inside_iterm(self, rig, monkeypatch, program):
        monkeypatch.setenv("TERM_PROGRAM", program)
        assert "not running inside iTerm2" in iterm.unavailable_reason()

    def test_iterm_too_old(self, rig, monkeypatch):
        monkeypatch.setenv("TERM_PROGRAM_VERSION", "3.5.14")
        reason = iterm.unavailable_reason()
        assert "3.6" in reason and "3.5.14" in reason

    def test_unknown_version_is_not_blocked(self, rig, monkeypatch):
        monkeypatch.delenv("TERM_PROGRAM_VERSION")
        assert iterm.unavailable_reason() is None

    def test_browser_plugin_missing(self, rig, monkeypatch):
        monkeypatch.setattr(iterm, "_plugin_installed", lambda: False)
        reason = iterm.unavailable_reason()
        assert "Browser Plugin" in reason
        assert "https://iterm2.com/browser-plugin.html" in reason

    def test_no_osascript(self, rig, monkeypatch):
        monkeypatch.setattr(iterm.shutil, "which", lambda name: None)
        assert "osascript" in iterm.unavailable_reason()


# ===========================================================================
# _plugin_installed
# ===========================================================================


class TestPluginInstalled:
    @pytest.fixture
    def spotlight(self, tmp_path, monkeypatch):
        """No plugin in the application folders; Spotlight answers what the test sets."""
        box = {"stdout": "", "raises": None, "calls": 0}

        def run(cmd, **kwargs):
            box["calls"] += 1
            box["cmd"] = cmd
            if box["raises"]:
                raise box["raises"]
            return subprocess.CompletedProcess(cmd, 0, box["stdout"], "")

        monkeypatch.setattr(iterm, "_application_dirs", lambda: [tmp_path / "Applications"])
        monkeypatch.setattr(iterm.subprocess, "run", run)
        box["apps"] = tmp_path / "Applications"
        return box

    def test_found_in_an_application_folder_without_asking_spotlight(self, spotlight):
        (spotlight["apps"] / iterm.PLUGIN_APP).mkdir(parents=True)
        assert _REAL_PLUGIN_INSTALLED() is True
        assert spotlight["calls"] == 0

    def test_found_elsewhere_by_spotlight(self, spotlight):
        spotlight["stdout"] = "/Users/someone/Tools/iTermBrowserPlugin.app\n"
        assert _REAL_PLUGIN_INSTALLED() is True
        assert iterm.PLUGIN_BUNDLE_ID in spotlight["cmd"][1]

    def test_not_installed(self, spotlight):
        assert _REAL_PLUGIN_INSTALLED() is False
        assert spotlight["calls"] == 1

    def test_no_spotlight_command(self, spotlight, monkeypatch):
        monkeypatch.setattr(iterm.shutil, "which", lambda name: None)
        assert _REAL_PLUGIN_INSTALLED() is False
        assert spotlight["calls"] == 0

    @pytest.mark.parametrize("error", [
        OSError("mdfind vanished"),
        subprocess.TimeoutExpired("mdfind", 5),
    ])
    def test_a_spotlight_failure_counts_as_not_installed(self, spotlight, error):
        spotlight["raises"] = error
        assert _REAL_PLUGIN_INSTALLED() is False


# ===========================================================================
# _osascript
# ===========================================================================


class TestOsascript:
    @pytest.fixture
    def run(self, monkeypatch):
        box = {"returncode": 0, "stdout": "", "stderr": "", "raises": None}

        def fake_run(cmd, **kwargs):
            box["cmd"] = cmd
            box["kwargs"] = kwargs
            if box["raises"]:
                raise box["raises"]
            return subprocess.CompletedProcess(cmd, box["returncode"], box["stdout"], box["stderr"])

        monkeypatch.setattr(iterm.subprocess, "run", fake_run)
        return box

    def test_values_go_in_as_arguments_after_the_script(self, run):
        run["stdout"] = "HOME-PANE\nNEW-PANE\n"
        assert _REAL_OSASCRIPT("the script", "one", "two; three") == "HOME-PANE\nNEW-PANE"
        assert run["cmd"] == ["osascript", "-e", "the script", "one", "two; three"]

    def test_never_waits_for_ever(self, run):
        """A macOS permission dialog would otherwise hold the tool call open."""
        _REAL_OSASCRIPT("the script")
        assert 0 < run["kwargs"]["timeout"] <= 60

    def test_a_failure_carries_the_message_without_the_source_range(self, run):
        run["returncode"] = 1
        run["stderr"] = "613:646: execution error: pane ABC not found (-2700)\n"
        with pytest.raises(iterm.ItermError) as raised:
            _REAL_OSASCRIPT("the script")
        assert str(raised.value) == "pane ABC not found (-2700)"

    def test_a_profile_that_has_not_loaded_is_still_recognisable(self, run):
        run["returncode"] = 1
        run["stderr"] = "277:333: execution error: iTerm got an error: No profile named bitwize-music player X (1)"
        with pytest.raises(iterm.ItermError, match="No profile named"):
            _REAL_OSASCRIPT("the script")

    def test_a_failure_with_nothing_to_say(self, run):
        run["returncode"] = 1
        with pytest.raises(iterm.ItermError, match="AppleScript failed"):
            _REAL_OSASCRIPT("the script")

    @pytest.mark.parametrize("error", [
        FileNotFoundError("osascript"),
        subprocess.TimeoutExpired("osascript", 20),
    ])
    def test_not_being_able_to_run_it_is_an_iterm_error(self, run, error):
        run["raises"] = error
        with pytest.raises(iterm.ItermError, match="could not run AppleScript"):
            _REAL_OSASCRIPT("the script")


# ===========================================================================
# player_url
# ===========================================================================


class TestPlayerUrl:
    def test_song_page_becomes_the_compact_player(self):
        assert iterm.player_url(SONG_A) == f"https://suno.com/embed/{CLIP_A}"

    def test_clip_id_is_lowercased(self):
        assert iterm.player_url(SONG_A.upper().replace("HTTPS://SUNO.COM/SONG", "https://suno.com/song")) == (
            f"https://suno.com/embed/{CLIP_A}"
        )

    def test_legacy_share_link_is_left_alone(self):
        url = "https://suno.com/s/4hZKwZySCc8Lc63Q"
        assert iterm.player_url(url) == url


# ===========================================================================
# open_in_panes
# ===========================================================================


class TestOpenInPanes:
    def test_first_take_beside_the_session_the_rest_stacked_under_it(self, rig):
        result = iterm.open_in_panes([SONG_A, SONG_B])

        first, second = _profiles()
        assert rig.of("split") == [
            (OWN_PANE, first["Name"], "vertical"),
            (NEW_PANES[0], second["Name"], "horizontal"),
        ]
        assert rig.of("select") == [(OWN_PANE,)]
        assert result == {
            "panes": NEW_PANES[:2],
            "pages": [f"https://suno.com/embed/{CLIP_A}", f"https://suno.com/embed/{CLIP_B}"],
            "lyrics_pane": None,
        }

    def test_four_takes_make_one_column(self, rig):
        """Each pane goes under the one before; iTerm2 evens out their heights itself."""
        result = iterm.open_in_panes([SONG_A, SONG_B, SONG_C, SONG_D])

        names = [p["Name"] for p in _profiles()]
        assert rig.of("split") == [
            (OWN_PANE, names[0], "vertical"),
            (NEW_PANES[0], names[1], "horizontal"),
            (NEW_PANES[1], names[2], "horizontal"),
            (NEW_PANES[2], names[3], "horizontal"),
        ]
        assert result["panes"] == NEW_PANES[:4]  # top to bottom: takes 1, 2, 3, 4
        assert json.loads(iterm.panes_path().read_text(encoding="utf-8")) == NEW_PANES[:4]

    def test_the_same_take_twice_opens_one_pane(self, rig):
        shouted = SONG_A.replace(CLIP_A, CLIP_A.upper())  # the same page, spelled differently
        result = iterm.open_in_panes([SONG_A, SONG_A, shouted])
        assert len(rig.of("split")) == 1
        assert len(_profiles()) == 1
        assert result["panes"] == NEW_PANES[:1]

    @pytest.mark.parametrize("url", [
        "https://evil.example/embed/4ef71736-b95e-489b-b5ac-1a41badceb08",
        "http://suno.com/song/4ef71736-b95e-489b-b5ac-1a41badceb08",
        "https://suno.com.evil.example/song/4ef71736-b95e-489b-b5ac-1a41badceb08",
        "file:///etc/passwd",
    ])
    def test_only_suno_pages_are_opened(self, rig, url):
        with pytest.raises(iterm.ItermError, match="not a Suno page"):
            iterm.open_in_panes([SONG_A, url])
        assert rig.calls == []
        assert not iterm.profiles_path().exists()

    def test_each_take_gets_a_browser_profile_for_its_player_page(self, rig):
        iterm.open_in_panes([SONG_A, SONG_B])
        profiles = _profiles()
        assert [p["Initial URL"] for p in profiles] == [
            f"https://suno.com/embed/{CLIP_A}", f"https://suno.com/embed/{CLIP_B}",
        ]
        assert all(p["Custom Command"] == "Browser" for p in profiles)
        assert all(p["Name"].startswith("bitwize-music player ") for p in profiles)
        assert len({p["Name"] for p in profiles}) == 2
        assert len({p["Guid"] for p in profiles}) == 2

    def test_profiles_are_stable_for_the_same_take(self, rig):
        iterm.open_in_panes([SONG_A])
        first = _profiles()
        iterm.open_in_panes([SONG_A])
        assert _profiles() == first

    def test_opened_panes_are_remembered(self, rig):
        iterm.open_in_panes([SONG_A, SONG_B])
        assert json.loads(iterm.panes_path().read_text(encoding="utf-8")) == NEW_PANES[:2]

    def test_values_travel_as_arguments_not_inside_the_script(self, rig):
        """Nothing from a URL or a pane id is ever pasted into AppleScript source."""
        iterm.open_in_panes([SONG_A])
        for script in (iterm._SPLIT_SCRIPT, iterm._CLOSE_SCRIPT, iterm._SELECT_SCRIPT,
                       iterm._LIST_SCRIPT):
            assert "suno.com" not in script
            assert OWN_PANE not in script
            assert "on run argv" in script

    def test_without_a_session_id_the_focused_pane_is_used(self, rig, monkeypatch):
        monkeypatch.delenv("ITERM_SESSION_ID")
        iterm.open_in_panes([SONG_A])
        assert rig.of("split")[0][0] == ""
        assert rig.of("select") == [(FOCUSED_PANE,)]

    def test_malformed_session_id_is_ignored(self, rig, monkeypatch):
        monkeypatch.setenv("ITERM_SESSION_ID", "w0t1p0:not-a-uuid")
        iterm.open_in_panes([SONG_A])
        assert rig.of("split")[0][0] == ""

    def test_waits_for_iterm_to_load_the_new_profile(self, rig):
        rig.split_errors = [
            "execution error: iTerm got an error: No profile named bitwize-music player X (1)",
            "execution error: iTerm got an error: No profile named bitwize-music player X (1)",
        ]
        result = iterm.open_in_panes([SONG_A])
        assert len(rig.of("split")) == 3
        assert result["panes"] == NEW_PANES[:1]

    def test_gives_up_when_the_profile_never_loads(self, rig, monkeypatch):
        monkeypatch.setattr(iterm, "_PROFILE_WAIT_ATTEMPTS", 3)
        rig.split_errors = ["No profile named X"] * 3
        with pytest.raises(iterm.ItermError, match="No profile named"):
            iterm.open_in_panes([SONG_A])
        assert not iterm.profiles_path().exists()
        assert not iterm.panes_path().exists()

    def test_an_answer_that_is_not_two_pane_ids_is_refused(self, rig):
        rig.split_answer = "missing value"
        with pytest.raises(iterm.ItermError, match="unexpected answer"):
            iterm.open_in_panes([SONG_A])
        assert not iterm.profiles_path().exists()
        assert not iterm.panes_path().exists()

    def test_panes_stay_open_when_the_focus_cannot_be_returned(self, rig):
        rig.select_error = "pane vanished"
        result = iterm.open_in_panes([SONG_A])
        assert result["panes"] == NEW_PANES[:1]
        assert json.loads(iterm.panes_path().read_text(encoding="utf-8")) == NEW_PANES[:1]

    def test_other_errors_are_not_retried(self, rig):
        rig.split_errors = ["Not authorized to send Apple events to iTerm. (-1743)"]
        with pytest.raises(iterm.ItermError, match="Not authorized"):
            iterm.open_in_panes([SONG_A])
        assert len(rig.of("split")) == 1
        assert not iterm.profiles_path().exists()

    def test_a_failure_part_way_closes_what_was_opened(self, rig, monkeypatch):
        real = rig.__call__

        def fail_second_split(script, *args):
            if script is iterm._SPLIT_SCRIPT and len(rig.of("split")) == 1:
                rig.calls.append(("split", args))
                raise iterm.ItermError("pane vanished")
            return real(script, *args)

        monkeypatch.setattr(iterm, "_osascript", fail_second_split)
        with pytest.raises(iterm.ItermError, match="pane vanished"):
            iterm.open_in_panes([SONG_A, SONG_B])
        assert rig.of("close") == [(NEW_PANES[0],)]
        assert not iterm.panes_path().exists()
        assert not iterm.profiles_path().exists()

    def test_opening_again_closes_the_previous_panes_first(self, rig):
        iterm.open_in_panes([SONG_A, SONG_B])
        iterm.open_in_panes([SONG_A])
        assert rig.of("close") == [tuple(NEW_PANES[:2])]
        assert json.loads(iterm.panes_path().read_text(encoding="utf-8")) == [NEW_PANES[2]]

    def test_unavailable_raises_with_the_reason(self, rig, monkeypatch):
        monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
        with pytest.raises(iterm.ItermError, match="not running inside iTerm2"):
            iterm.open_in_panes([SONG_A])
        assert rig.calls == []

    def test_no_urls(self, rig):
        with pytest.raises(iterm.ItermError):
            iterm.open_in_panes([])


# ===========================================================================
# The lyrics pane
# ===========================================================================

LYRICS = "[Verse 1 - calm]\nPaper boats on the water\n\n[Chorus - big]\nSail away\n\n[End]"


class TestLyricsPane:
    """The track's lyrics in a plain pane under the takes. Not timed to the music."""

    def test_the_lyrics_pane_goes_under_the_takes(self, rig):
        result = iterm.open_in_panes([SONG_A, SONG_B], lyrics=LYRICS, title="Paper Boats")
        names = [p["Name"] for p in _profiles()]
        assert rig.of("split") == [
            (OWN_PANE, names[0], "vertical"),
            (NEW_PANES[0], names[1], "horizontal"),
            (NEW_PANES[1], names[2], "horizontal"),
        ]
        assert result["panes"] == NEW_PANES[:3]
        assert result["lyrics_pane"] == NEW_PANES[2]
        assert json.loads(iterm.panes_path().read_text(encoding="utf-8")) == NEW_PANES[:3]

    def test_it_shows_the_text_in_a_pager_that_interprets_nothing(self, rig):
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        profile = _profiles()[-1]
        assert profile["Custom Command"] == "Yes"
        assert "Initial URL" not in profile
        argv = shlex.split(profile["Command"])
        assert Path(argv[0]).name == "less"
        assert "-L" in argv          # no LESSOPEN preprocessor
        assert "-R" not in argv      # escape codes in the text are shown, never run
        assert Path(argv[-1]) == iterm.lyrics_path()

    def test_the_bottom_line_says_how_to_scroll_and_close_not_the_file_path(self, rig):
        """The pane is small, so the hint lives in the pager's prompt line."""
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        argv = shlex.split(_profiles()[-1]["Command"])
        prompt = next(a for a in argv if a.startswith("-Ps"))
        assert "q closes" in prompt
        assert not any(c in prompt[3:] for c in "?:.%\\")  # less prompt syntax

    def test_the_header_is_two_lines(self, rig):
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        lines = iterm.lyrics_path().read_text(encoding="utf-8").splitlines()
        assert lines[:3] == ["Paper Boats", "From the track file, not timed to the take", ""]
        assert lines[3] == "[Verse 1 - calm]"

    def test_q_closes_the_pane_and_closing_it_never_stops_to_ask(self, rig):
        """Set on the profile itself, so another user's default profile cannot
        leave a dead pane behind, or hold the close behind a "running job" prompt."""
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        profile = _profiles()[-1]
        assert profile["Close Sessions On End"] is True
        assert profile["Prompt Before Closing 2"] == 2  # only for jobs not ignored
        assert profile["Jobs to Ignore"] == ["less"]

    def test_the_text_names_the_track_and_says_it_is_not_timed(self, rig):
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        text = iterm.lyrics_path().read_text(encoding="utf-8")
        assert text.splitlines()[0] == "Paper Boats"
        assert "not timed" in text
        assert "Paper boats on the water" in text
        assert text.rstrip().endswith("[End]")

    def test_without_lyrics_there_is_no_lyrics_pane(self, rig):
        result = iterm.open_in_panes([SONG_A, SONG_B])
        assert len(rig.of("split")) == 2
        assert result["lyrics_pane"] is None
        assert not iterm.lyrics_path().exists()

    @pytest.mark.parametrize("blank", ["", "   \n  \n"])
    def test_blank_lyrics_open_no_pane(self, rig, blank):
        result = iterm.open_in_panes([SONG_A], lyrics=blank, title="Paper Boats")
        assert len(rig.of("split")) == 1
        assert result["lyrics_pane"] is None

    def test_the_lyrics_never_reach_applescript(self, rig):
        hostile = LYRICS + '\n" & do shell script "say gotcha" & "'
        iterm.open_in_panes([SONG_A], lyrics=hostile, title="Paper Boats")
        for _name, args in rig.calls:
            assert not any("Paper boats" in a or "do shell script" in a for a in args)

    def test_profiles_stay_distinct(self, rig):
        iterm.open_in_panes([SONG_A, SONG_B], lyrics=LYRICS, title="Paper Boats")
        profiles = _profiles()
        assert len({p["Guid"] for p in profiles}) == 3
        assert len({p["Name"] for p in profiles}) == 3

    def test_closing_removes_the_lyrics_text(self, rig):
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        iterm.close_panes()
        assert rig.of("close") == [tuple(NEW_PANES[:2])]
        assert not iterm.lyrics_path().exists()

    def test_opening_without_lyrics_clears_the_earlier_text(self, rig):
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        iterm.open_in_panes([SONG_B])
        assert not iterm.lyrics_path().exists()

    def test_a_failure_on_the_lyrics_pane_closes_the_takes_too(self, rig, monkeypatch):
        real = rig.__call__

        def fail_third_split(script, *args):
            if script is iterm._SPLIT_SCRIPT and len(rig.of("split")) == 2:
                rig.calls.append(("split", args))
                raise iterm.ItermError("pane vanished")
            return real(script, *args)

        monkeypatch.setattr(iterm, "_osascript", fail_third_split)
        with pytest.raises(iterm.ItermError, match="pane vanished"):
            iterm.open_in_panes([SONG_A, SONG_B], lyrics=LYRICS, title="Paper Boats")
        assert rig.of("close") == [tuple(NEW_PANES[:2])]
        assert not iterm.lyrics_path().exists()
        assert not iterm.profiles_path().exists()


# ===========================================================================
# close_panes
# ===========================================================================


class TestClosePanes:
    def test_closes_what_was_opened_and_removes_its_profiles(self, rig):
        iterm.open_in_panes([SONG_A, SONG_B])
        assert iterm.close_panes() == {"closed": 2}
        assert rig.of("close") == [tuple(NEW_PANES[:2])]
        assert not iterm.profiles_path().exists()
        assert not iterm.panes_path().exists()

    def test_nothing_open(self, rig):
        assert iterm.close_panes() == {"closed": 0}
        assert rig.calls == []

    def test_ignores_a_corrupt_or_tampered_state_file(self, rig):
        iterm.panes_path().parent.mkdir(parents=True, exist_ok=True)
        iterm.panes_path().write_text('["not-a-pane-id", 7, "' + NEW_PANES[0] + '"]', encoding="utf-8")
        assert iterm.close_panes() == {"closed": 1}
        assert rig.of("close") == [(NEW_PANES[0],)]

        iterm.panes_path().write_text("{broken", encoding="utf-8")
        assert iterm.close_panes() == {"closed": 0}

        iterm.panes_path().write_text('{"panes": ["' + NEW_PANES[0] + '"]}', encoding="utf-8")
        assert iterm.close_panes() == {"closed": 0}

    def test_an_applescript_failure_still_clears_the_state(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A])

        def boom(script, *args):
            raise iterm.ItermError("iTerm2 is not running")

        monkeypatch.setattr(iterm, "_osascript", boom)
        assert iterm.close_panes() == {"closed": 0}
        assert not iterm.panes_path().exists()
        assert not iterm.profiles_path().exists()

    def test_off_macos_only_the_state_is_cleared(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A])
        monkeypatch.setattr(iterm, "_IS_MACOS", False)
        assert iterm.close_panes() == {"closed": 0}
        assert rig.of("close") == []
        assert not iterm.panes_path().exists()


# ===========================================================================
# Two sessions (#625)
# ===========================================================================


def _be(monkeypatch, pane):
    """Make this process a Claude Code session started from *pane*."""
    monkeypatch.setenv("ITERM_SESSION_ID", f"w0t2p0:{pane}")


class TestEachSessionKeepsItsOwnPanes:
    """Two Claude Code sessions in two tabs: neither touches the other's panes."""

    def test_opening_leaves_the_other_sessions_panes_open(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A])
        _be(monkeypatch, OTHER_PANE)
        result = iterm.open_in_panes([SONG_B])
        assert rig.of("close") == []
        assert rig.of("split")[-1][0] == OTHER_PANE
        assert result["panes"] == [NEW_PANES[1]]

    def test_closing_closes_only_this_sessions_panes(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A])
        _be(monkeypatch, OTHER_PANE)
        iterm.open_in_panes([SONG_B])

        assert iterm.close_panes() == {"closed": 1}
        assert rig.of("close") == [(NEW_PANES[1],)]

        _be(monkeypatch, OWN_PANE)
        assert iterm.close_panes() == {"closed": 1}
        assert rig.of("close")[-1] == (NEW_PANES[0],)

    def test_each_session_has_its_own_files(self, rig, monkeypatch):
        mine = (iterm.panes_path(), iterm.profiles_path(), iterm.lyrics_path())
        _be(monkeypatch, OTHER_PANE)
        theirs = (iterm.panes_path(), iterm.profiles_path(), iterm.lyrics_path())
        assert all(a != b for a, b in zip(mine, theirs, strict=True))

    def test_the_other_sessions_lyrics_are_left_alone(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        mine = iterm.lyrics_path()
        _be(monkeypatch, OTHER_PANE)
        iterm.open_in_panes([SONG_B], lyrics="[Verse]\nSomething else", title="Other")
        assert "Paper boats on the water" in mine.read_text(encoding="utf-8")

    def test_the_same_take_in_two_sessions_gets_two_profiles(self, rig, monkeypatch):
        """iTerm2 must never see two profiles with one Guid, or two with one name."""
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        mine = _profiles()
        _be(monkeypatch, OTHER_PANE)
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        theirs = _profiles()
        assert not {p["Guid"] for p in mine} & {p["Guid"] for p in theirs}
        assert not {p["Name"] for p in mine} & {p["Name"] for p in theirs}

    def test_without_a_session_id_the_shared_files_are_used(self, rig, monkeypatch):
        monkeypatch.delenv("ITERM_SESSION_ID")
        assert iterm.panes_path().name == "listen-panes.json"
        assert iterm.profiles_path().name == "bitwize-music-listen.json"
        assert iterm.lyrics_path().name == "listen-lyrics.txt"


class TestFilesLeftByOtherSessions:
    """Another session's files go once none of its panes is open. Nothing is closed."""

    def test_removed_once_all_of_its_panes_are_gone(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A], lyrics=LYRICS, title="Paper Boats")
        gone = (iterm.panes_path(), iterm.profiles_path(), iterm.lyrics_path())
        rig.live -= {OWN_PANE, *NEW_PANES[:2]}  # its tab was closed
        _be(monkeypatch, OTHER_PANE)
        iterm.open_in_panes([SONG_B])
        assert not any(path.exists() for path in gone)
        assert rig.of("close") == []

    def test_kept_while_any_of_its_panes_is_open(self, rig, monkeypatch):
        """Its own pane may be gone while one of its players is still playing."""
        iterm.open_in_panes([SONG_A, SONG_B])
        kept = (iterm.panes_path(), iterm.profiles_path())
        rig.live -= {OWN_PANE, NEW_PANES[0]}
        _be(monkeypatch, OTHER_PANE)
        iterm.open_in_panes([SONG_C])
        assert all(path.exists() for path in kept)
        assert rig.of("close") == []

    def test_closing_cleans_up_too(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A])
        gone = iterm.panes_path()
        rig.live.discard(NEW_PANES[0])
        _be(monkeypatch, OTHER_PANE)
        assert iterm.close_panes() == {"closed": 0}
        assert not gone.exists()

    def test_the_shared_files_go_once_their_panes_are_gone(self, rig, monkeypatch):
        """Left by an earlier build, or by a session with no pane id."""
        monkeypatch.delenv("ITERM_SESSION_ID")
        iterm.open_in_panes([SONG_A])
        shared = (iterm.panes_path(), iterm.profiles_path())
        rig.live.discard(NEW_PANES[0])
        _be(monkeypatch, OWN_PANE)
        iterm.open_in_panes([SONG_B])
        assert not any(path.exists() for path in shared)

    def test_nothing_is_asked_when_no_other_session_left_files(self, rig):
        iterm.open_in_panes([SONG_A])
        iterm.open_in_panes([SONG_B])
        assert rig.of("list") == []

    def test_skipped_when_iterm2_cannot_list_its_panes(self, rig, monkeypatch):
        iterm.open_in_panes([SONG_A])
        theirs = iterm.panes_path()
        rig.list_error = "iTerm got an error: Connection is invalid. (-609)"
        _be(monkeypatch, OTHER_PANE)
        result = iterm.open_in_panes([SONG_B])
        assert result["panes"] == [NEW_PANES[1]]
        assert theirs.exists()
