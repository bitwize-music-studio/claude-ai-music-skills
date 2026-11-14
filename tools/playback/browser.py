"""Open a page in the browser the user chose: the system's default, an app by name, or by path.

One rule for every setting that names a browser (``generation.listen_browser``,
``generation.studio_browser``): blank or ``default`` is the system's default
browser; anything else is an app name ("Firefox", "Google Chrome") or a path
(an .app bundle on macOS, the browser's program elsewhere). A choice that
can't be opened falls back to the default, with a note saying why. No shell
ever sees the URL or the name.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

_ITERM_RE = re.compile(r"iterm", re.IGNORECASE)


def is_default(choice: str) -> bool:
    """True for no choice at all: blank, or the word ``default``."""
    return choice.strip().casefold() in ("", "default")


def is_iterm(choice: str) -> bool:
    """True when the choice names iTerm2, whose built-in browser is a pane, not a web browser."""
    return bool(_ITERM_RE.search(choice))


def _looks_like_path(choice: str) -> bool:
    return "/" in choice or "\\" in choice or choice.casefold().endswith((".app", ".exe"))


def _on_macos() -> bool:
    return sys.platform == "darwin"


def _run_open(argv: list[str]) -> subprocess.CompletedProcess[str]:
    # /usr/bin/open by its full path, with an argv list: no shell sees the URL or the name.
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=30)


def _spawn(argv: list[str]) -> None:
    # The browser's own program, started in a session of its own; nothing waits for it.
    subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def _open_chosen(url: str, choice: str) -> str:
    """Open url with the chosen browser: "" when it opened, else why it didn't."""
    target = str(Path(choice).expanduser()) if _looks_like_path(choice) else choice
    if _on_macos():
        try:
            done = _run_open(["/usr/bin/open", "-a", target, url])
        except (OSError, subprocess.SubprocessError) as exc:
            return f"{choice!r} couldn't be opened ({exc})"
        if done.returncode == 0:
            return ""
        said = (done.stderr or "").strip().splitlines()
        return f"{choice!r} couldn't be opened ({said[0] if said else f'exit {done.returncode}'})"
    if _looks_like_path(choice):
        if not Path(target).is_file():
            return f"No browser program at {choice!r}"
        try:
            _spawn([target, url])
        except OSError as exc:
            return f"{choice!r} couldn't be started ({exc})"
        return ""
    try:
        if webbrowser.get(choice).open_new_tab(url):
            return ""
        return f"{choice!r} couldn't open the page"
    except webbrowser.Error:
        return f"No browser named {choice!r} here"


def open_url(url: str, choice: str = "") -> tuple[str | None, str]:
    """Open url in the chosen browser, else the system's default.

    Returns (the browser used: the choice as given, "default", or None when
    nothing could be opened; a note when the choice wasn't the one used).
    """
    choice = choice.strip()
    reason = ""
    if not is_default(choice):
        reason = _open_chosen(url, choice)
        if not reason:
            return choice, ""
        logger.warning("Browser: %s", reason)
    try:
        launched = webbrowser.open_new_tab(url)
    except webbrowser.Error as exc:
        logger.warning("Could not open %s in a browser: %s", url, exc)
        launched = False
    if not launched:
        return None, f"{reason}, and no default browser could be launched" if reason else ""
    return "default", f"{reason}: opened in the default browser instead" if reason else ""
