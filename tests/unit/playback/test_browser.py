"""tools.playback.browser: the system's default browser, an app by name, or one by path.

Launches are recorded, never run: nothing here opens a window.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.playback import browser  # noqa: E402

pytestmark = pytest.mark.unit

URL = "https://suno.com/song/e892f3fd-2d28-4093-b897-d0c419cda7ea"


@pytest.fixture
def launches(monkeypatch):
    """Record every launch; macOS `open` succeeds unless a test says otherwise."""
    record: list[tuple[str, object]] = []
    outcome = {"returncode": 0, "stderr": ""}

    def run_open(argv):
        record.append(("open", argv))
        return subprocess.CompletedProcess(argv, outcome["returncode"], "", outcome["stderr"])

    monkeypatch.setattr(browser, "_run_open", run_open)
    monkeypatch.setattr(browser, "_spawn", lambda argv: record.append(("spawn", argv)))
    monkeypatch.setattr(browser, "_on_macos", lambda: True)
    monkeypatch.setattr(browser.webbrowser, "open_new_tab",
                        lambda url: record.append(("default", url)) or True)
    return {"record": record, "outcome": outcome}


class TestOpenUrl:
    @pytest.mark.parametrize("choice", ["", "default", " Default "])
    def test_default_is_the_systems_browser(self, launches, choice):
        assert browser.open_url(URL, choice) == ("default", "")
        assert launches["record"] == [("default", URL)]

    def test_an_app_by_name_on_macos(self, launches):
        assert browser.open_url(URL, "Firefox") == ("Firefox", "")
        assert launches["record"] == [("open", ["/usr/bin/open", "-a", "Firefox", URL])]

    def test_an_app_by_path_on_macos(self, launches):
        app = "/Applications/Firefox Developer Edition.app"
        assert browser.open_url(URL, app) == (app, "")
        assert launches["record"] == [("open", ["/usr/bin/open", "-a", app, URL])]

    def test_a_path_from_home_is_expanded(self, launches):
        used, _ = browser.open_url(URL, "~/Applications/Arc.app")
        assert used == "~/Applications/Arc.app"
        assert launches["record"][0][1][2] == str(Path.home() / "Applications" / "Arc.app")

    def test_an_app_that_wont_open_falls_back_to_the_default(self, launches):
        launches["outcome"].update(returncode=1, stderr="Unable to find application named 'Netscape'\n")
        used, note = browser.open_url(URL, "Netscape")
        assert used == "default"
        assert launches["record"][-1] == ("default", URL)
        assert note == ("'Netscape' couldn't be opened (Unable to find application named "
                        "'Netscape'): opened in the default browser instead")

    def test_nothing_opens(self, launches, monkeypatch):
        monkeypatch.setattr(browser.webbrowser, "open_new_tab", lambda url: False)
        assert browser.open_url(URL) == (None, "")

    def test_elsewhere_a_name_goes_through_webbrowser(self, launches, monkeypatch):
        monkeypatch.setattr(browser, "_on_macos", lambda: False)
        opened = []

        class _Named:
            def open_new_tab(self, url):
                opened.append(url)
                return True

        monkeypatch.setattr(browser.webbrowser, "get", lambda name: _Named())
        assert browser.open_url(URL, "firefox") == ("firefox", "")
        assert opened == [URL]

    def test_elsewhere_an_unknown_name_falls_back(self, launches, monkeypatch):
        monkeypatch.setattr(browser, "_on_macos", lambda: False)

        def unknown(name):
            raise browser.webbrowser.Error("could not locate runnable browser")

        monkeypatch.setattr(browser.webbrowser, "get", unknown)
        used, note = browser.open_url(URL, "netscape")
        assert used == "default"
        assert note.startswith("No browser named 'netscape' here")

    def test_elsewhere_a_path_runs_that_program(self, launches, monkeypatch, tmp_path):
        monkeypatch.setattr(browser, "_on_macos", lambda: False)
        program = tmp_path / "firefox"
        program.write_text("", encoding="utf-8")
        assert browser.open_url(URL, str(program)) == (str(program), "")
        assert launches["record"] == [("spawn", [str(program), URL])]

    def test_elsewhere_a_missing_path_falls_back(self, launches, monkeypatch, tmp_path):
        monkeypatch.setattr(browser, "_on_macos", lambda: False)
        used, note = browser.open_url(URL, str(tmp_path / "nope" / "firefox"))
        assert used == "default"
        assert note.startswith("No browser program at")


@pytest.mark.parametrize("choice, expected", [
    ("iTerm2", True), ("iterm", True), ("/Applications/iTerm.app", True),
    ("Firefox", False), ("", False), ("default", False),
])
def test_is_iterm(choice, expected):
    assert browser.is_iterm(choice) is expected
