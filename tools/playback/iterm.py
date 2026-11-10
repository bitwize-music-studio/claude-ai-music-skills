"""Song pages in iTerm2 split panes — iTerm2's built-in browser, driven by AppleScript.

iTerm2 3.6 can show a web page in a pane. This module opens Suno's compact
player page for each take beside the pane the plugin's server was started from,
remembers which panes it opened, and closes them again. Given a track's lyrics,
it also opens them in a plain terminal pane under the takes. The lyrics are not
timed to the music: the module cannot see where Suno's player is.

A browser pane can only be given its page through a profile's Initial URL, so
each take gets a small dynamic profile; they are removed when the panes close.
Nothing from a URL or a pane id is ever pasted into AppleScript source — every
value is passed to the script as an argument.

There is one set of player panes per machine, not per session: opening takes
closes the panes of the previous call, whichever session made it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from tools.playback import player as _player

logger = logging.getLogger(__name__)

_IS_MACOS = sys.platform == "darwin"

MIN_VERSION = (3, 6)
PLUGIN_APP = "iTermBrowserPlugin.app"
PLUGIN_BUNDLE_ID = "com.googlecode.iterm2.iTermBrowserPlugin"
PLUGIN_URL = "https://iterm2.com/browser-plugin.html"
PROFILE_PREFIX = "bitwize-music player"
PROFILES_FILE = "bitwize-music-listen.json"

# Profile Guids are derived from the page URL, so the same take always gets the
# same profile and iTerm2 never sees two profiles with one Guid.
_PROFILE_NAMESPACE = uuid.UUID("6b1d2c0e-5a7f-4e7b-9c1a-b17e11570000")

_SUNO_PREFIX = "https://suno.com/"
_PANE_ID_RE = re.compile(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}")
_SONG_URL_RE = re.compile(
    r"https://suno\.com/song/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})"
)

# osascript prefixes its errors with the failing source range: "613:646: execution error: ".
_OSASCRIPT_PREFIX_RE = re.compile(r"^\d+:\d+: (?:execution error: )?")

# The lyrics pane's bottom line. Plain words only: ? : . % and \ mean
# something in a less prompt.
_LYRICS_HINT = "Wheel or arrows to scroll, q closes this pane"

# iTerm2 loads a new dynamic profile a moment after its file changes.
_PROFILE_WAIT_ATTEMPTS = 12
_PROFILE_WAIT_SECONDS = 0.5

# Pane references shift when a pane is added, so every script looks panes up by id.
_FIND_SESSION = """
on findSession(theId)
  tell application "iTerm2"
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if (id of s) is theId then return s
        end repeat
      end repeat
    end repeat
  end tell
  return missing value
end findSession
"""

# argv: anchor pane id ("" = the focused pane), profile name, "vertical" | "horizontal".
# Answers two lines: the anchor's id, then the new pane's id.
_SPLIT_SCRIPT = _FIND_SESSION + """
on run argv
  set anchorId to item 1 of argv
  set profileName to item 2 of argv
  set direction to item 3 of argv
  tell application "iTerm2"
    if anchorId is "" then set anchorId to (id of current session of current window)
    set anchor to my findSession(anchorId)
    if anchor is missing value then error "pane " & anchorId & " not found"
    tell anchor
      if direction is "vertical" then
        set newSession to (split vertically with profile profileName)
      else
        set newSession to (split horizontally with profile profileName)
      end if
    end tell
    return anchorId & linefeed & (id of newSession)
  end tell
end run
"""

# argv: pane ids to close. Answers how many were found and closed.
_CLOSE_SCRIPT = _FIND_SESSION + """
on run argv
  set closed to 0
  repeat with paneId in argv
    set pane to my findSession(paneId as text)
    if pane is not missing value then
      tell application "iTerm2" to tell pane to close
      set closed to closed + 1
    end if
  end repeat
  return closed
end run
"""

# argv: the pane id to give the keyboard focus back to.
_SELECT_SCRIPT = _FIND_SESSION + """
on run argv
  set pane to my findSession(item 1 of argv)
  if pane is not missing value then
    tell application "iTerm2" to tell pane to select
  end if
end run
"""


class ItermError(Exception):
    """iTerm2 panes could not be used; the message says why."""


# =============================================================================
# Locations
# =============================================================================


def dynamic_profiles_dir() -> Path:
    """Where iTerm2 picks up dynamic profiles."""
    return Path.home() / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles"


def profiles_path() -> Path:
    """The one dynamic-profiles file this module owns."""
    return dynamic_profiles_dir() / PROFILES_FILE


def panes_path() -> Path:
    """The file recording which panes are open."""
    return _player.cache_dir() / "listen-panes.json"


def lyrics_path() -> Path:
    """The text file the lyrics pane shows."""
    return _player.cache_dir() / "listen-lyrics.txt"


# =============================================================================
# Availability
# =============================================================================


def _application_dirs() -> list[Path]:
    """Where macOS applications are normally installed."""
    return [Path("/Applications"), Path.home() / "Applications"]


def _plugin_installed() -> bool:
    """True when iTerm2's Browser Plugin can be found."""
    if any((base / PLUGIN_APP).exists() for base in _application_dirs()):
        return True
    # Not in the usual places: ask Spotlight where it is.
    mdfind = shutil.which("mdfind")
    if not mdfind:
        return False
    try:
        found = subprocess.run(
            [mdfind, f"kMDItemCFBundleIdentifier == '{PLUGIN_BUNDLE_ID}'"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(found.strip())


def unavailable_reason() -> str | None:
    """Why iTerm2 panes cannot be used from this process, or None when they can."""
    if not _IS_MACOS:
        return "iTerm2 panes need macOS"
    if os.environ.get("TERM_PROGRAM") != "iTerm.app":
        return "this session is not running inside iTerm2"
    version_text = os.environ.get("TERM_PROGRAM_VERSION", "")
    version = tuple(int(part) for part in re.findall(r"\d+", version_text)[:3])
    if version and version < MIN_VERSION:
        wanted = ".".join(str(part) for part in MIN_VERSION)
        return f"iTerm2 {wanted} or later is needed (this is {version_text})"
    if shutil.which("osascript") is None:
        return "osascript is not available"
    if not _plugin_installed():
        return f"iTerm2's Browser Plugin is not installed — get it from {PLUGIN_URL}"
    return None


# =============================================================================
# Pages and profiles
# =============================================================================


def player_url(url: str) -> str:
    """Suno's compact player page for a song URL; any other URL is returned as is.

    The compact player puts the play button at the top of the page, which suits
    a pane far better than the full song page.
    """
    match = _SONG_URL_RE.fullmatch(url)
    return f"https://suno.com/embed/{match.group(1).lower()}" if match else url


def _profile(page: str) -> dict[str, str]:
    """The browser profile that opens *page*."""
    guid = str(uuid.uuid5(_PROFILE_NAMESPACE, page)).upper()
    return {
        "Name": f"{PROFILE_PREFIX} {guid[:8]}",
        "Guid": guid,
        "Custom Command": "Browser",
        "Initial URL": page,
    }


def _lyrics_profile(path: Path) -> dict[str, Any]:
    """The terminal profile that shows *path* in a pager.

    ``less -L`` ignores any LESSOPEN preprocessor, and without ``-R`` it shows
    control characters in the text instead of passing them to the terminal.
    Its prompt line carries the hint on scrolling and closing, in place of the
    file's path. The pane closes when the pager quits, and closing it never
    stops to ask about the running pager, whatever the user's default profile
    says.
    """
    pager = shutil.which("less") or "/usr/bin/less"
    return {
        "Name": f"{PROFILE_PREFIX} lyrics",
        "Guid": str(uuid.uuid5(_PROFILE_NAMESPACE, "lyrics")).upper(),
        "Custom Command": "Yes",
        "Command": shlex.join([pager, "-L", f"-Ps{_LYRICS_HINT}", str(path)]),
        "Close Sessions On End": True,
        "Prompt Before Closing 2": 2,  # only when a job outside the list runs
        "Jobs to Ignore": ["less"],
    }


def _write_lyrics(lyrics: str, title: str) -> Path:
    """Write the lyrics pane's text: the title, a note on what it is, the lyrics."""
    head = [title.strip()] if title.strip() else []
    head += ["From the track file, not timed to the take", ""]
    path = lyrics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(head) + "\n" + lyrics.strip("\n") + "\n", encoding="utf-8")
    return path


def _write_profiles(profiles: list[dict[str, Any]]) -> None:
    target = profiles_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"Profiles": profiles}, indent=2) + "\n", encoding="utf-8")


def _remove_profiles() -> None:
    profiles_path().unlink(missing_ok=True)


# =============================================================================
# Pane state
# =============================================================================


def _load_panes() -> list[str]:
    """Recorded pane ids. Anything that is not a pane id is dropped."""
    try:
        data = json.loads(panes_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str) and _PANE_ID_RE.fullmatch(item)]


def _save_panes(panes: list[str]) -> None:
    target = panes_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(panes), encoding="utf-8")


def _own_pane_id() -> str:
    """The pane this process was started from, or "" when that is unknown.

    iTerm2 exports ITERM_SESSION_ID as ``w0t1p0:<pane id>`` to everything it
    starts, so the plugin's server inherits the id of its own Claude Code pane.
    """
    candidate = os.environ.get("ITERM_SESSION_ID", "").rpartition(":")[2]
    return candidate if _PANE_ID_RE.fullmatch(candidate) else ""


# =============================================================================
# AppleScript
# =============================================================================


def _osascript(script: str, *args: str) -> str:
    """Run an AppleScript with arguments and return what it answered."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script, *args],
            capture_output=True, encoding="utf-8", errors="replace", timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise ItermError(f"could not run AppleScript: {e}") from e
    if result.returncode != 0:
        message = _OSASCRIPT_PREFIX_RE.sub("", result.stderr.strip())
        raise ItermError(message or "AppleScript failed")
    return result.stdout.strip()


def _split(anchor: str, profile_name: str, direction: str) -> tuple[str, str]:
    """Split *anchor* with a profile. Returns ``(anchor id, new pane id)``."""
    last_error = ""
    for _ in range(_PROFILE_WAIT_ATTEMPTS):
        try:
            answer = _osascript(_SPLIT_SCRIPT, anchor, profile_name, direction)
        except ItermError as e:
            last_error = str(e)
            if "No profile named" not in last_error:
                raise
            time.sleep(_PROFILE_WAIT_SECONDS)
            continue
        lines = answer.splitlines()
        if len(lines) != 2 or not all(_PANE_ID_RE.fullmatch(line) for line in lines):
            raise ItermError(f"unexpected answer from iTerm2: {answer!r}")
        return lines[0], lines[1]
    raise ItermError(last_error or "iTerm2 did not load the player profile")


def _close(panes: list[str]) -> int:
    """Close panes by id; returns how many iTerm2 found. Never raises."""
    if not panes or not _IS_MACOS or shutil.which("osascript") is None:
        return 0
    try:
        return int(_osascript(_CLOSE_SCRIPT, *panes) or 0)
    except (ItermError, ValueError) as e:
        logger.warning("Could not close iTerm2 panes: %s", e)
        return 0


# =============================================================================
# Public API
# =============================================================================


def close_panes() -> dict[str, Any]:
    """Close the panes this module opened and remove their profiles."""
    closed = _close(_load_panes())
    _remove_profiles()
    panes_path().unlink(missing_ok=True)
    lyrics_path().unlink(missing_ok=True)
    return {"closed": closed}


def open_in_panes(urls: list[str], lyrics: str = "", title: str = "") -> dict[str, Any]:
    """Open each Suno page's player in an iTerm2 pane beside this session.

    The panes form one column to the right of the session, the first URL at
    the top: each pane is split off under the one before, and iTerm2 shares
    the column's height evenly between them. Panes from an earlier call are
    closed first, and the keyboard focus goes back to the session afterwards.
    A page given twice gets one pane.

    With *lyrics*, one more pane at the bottom of the column shows them in a
    pager, under *title*. They are not timed to the music. The text reaches the
    pane through a file and a profile, never through AppleScript.

    Returns ``{"panes": [pane ids, top to bottom], "pages": [the URLs shown],
    "lyrics_pane": the lyrics pane's id, or None}``.

    Raises:
        ItermError: a URL is not a Suno page, iTerm2 panes are not available
            here, or iTerm2 refused. Any pane already opened by this call is
            closed again.
    """
    if not urls:
        raise ItermError("no URLs to open")
    for url in urls:
        if not url.startswith(_SUNO_PREFIX):
            raise ItermError(f"not a Suno page: {url}")
    reason = unavailable_reason()
    if reason:
        raise ItermError(reason)

    # One pane, and one profile, per page: two profiles must never share a Guid.
    profiles = [_profile(page) for page in dict.fromkeys(player_url(url) for url in urls)]
    close_panes()
    text_profile = _lyrics_profile(_write_lyrics(lyrics, title)) if lyrics.strip() else None
    _write_profiles(profiles + ([text_profile] if text_profile else []))

    home = _own_pane_id()
    opened: list[str] = []
    lyrics_pane = None
    try:
        home, pane = _split(home, profiles[0]["Name"], "vertical")
        opened.append(pane)
        for profile in profiles[1:]:
            _, pane = _split(opened[-1], profile["Name"], "horizontal")
            opened.append(pane)
        if text_profile:
            _, lyrics_pane = _split(opened[-1], text_profile["Name"], "horizontal")
            opened.append(lyrics_pane)
    except ItermError:
        _close(opened)
        _remove_profiles()
        lyrics_path().unlink(missing_ok=True)
        raise

    _save_panes(opened)
    try:
        _osascript(_SELECT_SCRIPT, home)
    except ItermError as e:
        logger.warning("Opened the panes but could not return focus: %s", e)

    return {
        "panes": opened,
        "pages": [profile["Initial URL"] for profile in profiles],
        "lyrics_pane": lyrics_pane,
    }
