"""Local audio playback for auditioning — find a track's audio file and play it.

Playback runs in a detached player process (mpv, ffplay or afplay), so the call
that starts it returns at once. One playback at a time; what is playing is
recorded in the plugin cache so a later call, or a restarted server, can stop
it. Local files only — never URLs.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools.state import indexer as _indexer

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aiff", ".aif"})

# Preference order: mpv seeks and stays quiet; ffplay ships with ffmpeg; afplay
# is built into macOS but cannot start mid-file.
PLAYERS = ("mpv", "ffplay", "afplay")

INSTALL_HINT = (
    "Install mpv (macOS: brew install mpv; Debian/Ubuntu: sudo apt install mpv; "
    "Windows: winget install mpv) or ffmpeg, which includes ffplay."
)

_IS_WINDOWS = sys.platform == "win32"
# subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP, spelled as
# numbers because those names only exist on Windows.
_WINDOWS_DETACH_FLAGS = 0x00000008 | 0x00000200

_LEADING_NUMBER_RE = re.compile(r"(\d+)")

# Player processes this server started, by pid, so they can be polled and reaped.
_children: dict[int, subprocess.Popen[bytes]] = {}


class PlaybackError(Exception):
    """A playback request that cannot be honoured (bad path, no player, ...)."""


# =============================================================================
# Locations
# =============================================================================


def cache_dir() -> Path:
    """The plugin cache directory (~/.bitwize-music/cache).

    Read through the indexer module on every call, so anything that redirects
    the state cache (the test suite does) redirects playback state with it.
    """
    return Path(_indexer.CACHE_DIR)


def takes_cache_dir() -> Path:
    """Where audition copies of Suno takes are kept, as ``<clip_id>.mp3``."""
    return cache_dir() / "takes"


def state_path() -> Path:
    """The file recording what is playing."""
    return cache_dir() / "playback.json"


# =============================================================================
# Finding audio
# =============================================================================


def find_track_audio(directory: Path, track_slug: str) -> Path | None:
    """The audio file for *track_slug* in *directory*, or None.

    Matches ``<slug>.<ext>`` first (WAV before other formats), then a single file
    whose leading number equals the slug's — ``01 - Title.wav`` for ``01-title``,
    which is how hand-named downloads look. Two such files are ambiguous: None.
    """
    if not directory.is_dir():
        return None
    try:
        files = sorted(
            (
                p for p in directory.iterdir()
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
            ),
            key=lambda p: (p.suffix.lower() != ".wav", p.name),
        )
    except OSError:
        return None

    for candidate in files:
        if candidate.stem == track_slug:
            return candidate

    number = _LEADING_NUMBER_RE.match(track_slug)
    if not number:
        return None
    wanted = int(number.group(1))
    numbered = [
        p for p in files
        if (match := _LEADING_NUMBER_RE.match(p.stem)) and int(match.group(1)) == wanted
    ]
    return numbered[0] if len(numbered) == 1 else None


def audio_duration(path: Path) -> float | None:
    """Length of an audio file in seconds, or None when it cannot be read."""
    try:
        import soundfile

        return float(soundfile.info(str(path)).duration)
    except Exception as e:
        # A nicety for the caller's report; any failure just means "unknown".
        logger.debug("Could not read duration of %s: %s", path, e)
        return None


# =============================================================================
# Player selection and command lines
# =============================================================================


def find_player() -> str | None:
    """The first installed player from PLAYERS, or None."""
    for name in PLAYERS:
        if shutil.which(name):
            return name
    return None


def build_command(
    player: str, path: Path, start_s: float = 0.0, length_s: float | None = None,
) -> list[str]:
    """The argument list that plays *path* with *player*, without any window."""
    executable = shutil.which(player) or player
    if player == "mpv":
        command = [executable, "--no-config", "--no-video", "--no-terminal", "--really-quiet"]
        if start_s > 0:
            command.append(f"--start={start_s:g}")
        if length_s is not None:
            command.append(f"--length={length_s:g}")
        return [*command, "--", str(path)]
    if player == "ffplay":
        command = [executable, "-nodisp", "-autoexit", "-loglevel", "quiet"]
        if start_s > 0:
            command += ["-ss", f"{start_s:g}"]
        if length_s is not None:
            command += ["-t", f"{length_s:g}"]
        return [*command, "-i", str(path)]
    if player == "afplay":
        command = [executable]
        if length_s is not None:
            command += ["-t", f"{length_s:g}"]
        return [*command, str(path)]
    raise PlaybackError(f"Unknown player '{player}'")


def validate_path(path: str | Path, allowed_roots: list[Path]) -> Path:
    """Check that *path* is a local audio file under one of *allowed_roots*.

    Returns the normalized path. An album directory may be a symlink that leaves
    the audio root (a supported layout), so a path passes when it sits under a
    root either as written or after resolving links.

    Raises:
        PlaybackError: a URL, a relative path, a non-audio extension, a missing
            file, or a file outside every allowed root.
    """
    raw = str(path).strip()
    if "://" in raw:
        raise PlaybackError("Only local files can be played, not URLs")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise PlaybackError("Path must be absolute")
    if candidate.suffix.lower() not in AUDIO_EXTENSIONS:
        raise PlaybackError(
            f"Not an audio file: {candidate.name} "
            f"(supported: {', '.join(sorted(AUDIO_EXTENSIONS))})"
        )
    lexical = Path(os.path.normpath(candidate))
    if not lexical.is_file():
        raise PlaybackError(f"File not found: {lexical}")
    resolved = lexical.resolve()
    for root in allowed_roots:
        root_lexical = Path(os.path.normpath(root.expanduser()))
        if lexical.is_relative_to(root_lexical) or resolved.is_relative_to(root_lexical.resolve()):
            return lexical
    raise PlaybackError("Path is outside the audio root and the takes cache")


# =============================================================================
# Process control
# =============================================================================


def _read_state() -> dict[str, Any] | None:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_state(data: dict[str, Any]) -> None:
    target = state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data), encoding="utf-8")


def _clear_state() -> None:
    state_path().unlink(missing_ok=True)


def _process_name(pid: int) -> str | None:
    """The executable name (or path) of a running process, or None if it is gone."""
    if _IS_WINDOWS:
        command = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
    else:
        command = ["ps", "-p", str(pid), "-o", "comm="]
    try:
        output = subprocess.run(
            command, capture_output=True, encoding="utf-8", errors="replace",
            timeout=5, check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not output or output.upper().startswith("INFO:"):
        return None
    first_line = output.splitlines()[0].strip()
    if _IS_WINDOWS:
        return first_line.split(",")[0].strip('"')
    return first_line


def _terminate(pid: int) -> None:
    """Ask a process to stop."""
    if _IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True, timeout=5, check=False,
        )
        return
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGTERM)


def _is_our_player(pid: int, player: str) -> bool:
    """True while *pid* is still the player process that was started.

    A handle from this server process is authoritative. After a server restart
    there is none, so the process table decides — and the executable name must
    match, because the pid may have been recycled for something else.
    """
    child = _children.get(pid)
    if child is not None:
        return child.poll() is None
    name = _process_name(pid)
    return bool(name) and player.lower() in Path(str(name)).name.lower()


def _reap_finished() -> None:
    for pid, child in list(_children.items()):
        if child.poll() is not None:
            del _children[pid]


def status() -> dict[str, Any]:
    """What is playing right now: ``{"playing": False}`` or pid, player, path, position."""
    state = _read_state()
    if not state:
        return {"playing": False}
    try:
        pid = int(state["pid"])
        player = str(state["player"])
        started_at = float(state["started_at"])
        start_s = float(state.get("start_s", 0.0))
    except (KeyError, TypeError, ValueError):
        _clear_state()
        return {"playing": False}
    if not _is_our_player(pid, player):
        _clear_state()
        _reap_finished()
        return {"playing": False}
    return {
        "playing": True,
        "pid": pid,
        "player": player,
        "path": state.get("path"),
        "position_s": round(start_s + (time.time() - started_at), 1),
    }


def stop() -> dict[str, Any]:
    """Stop the current playback, if any, and report where it had reached."""
    current = status()
    if not current["playing"]:
        return {"stopped": False, "reason": "nothing is playing"}
    pid = int(current["pid"])
    _terminate(pid)
    child = _children.pop(pid, None)
    if child is not None:
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
    _clear_state()
    return {"stopped": True, "path": current["path"], "position_s": current["position_s"]}


def play(
    path: str | Path,
    allowed_roots: list[Path],
    start_s: float = 0.0,
    length_s: float | None = None,
) -> dict[str, Any]:
    """Start playing a local audio file in a detached process and return at once.

    Stops whatever was playing first. Raises PlaybackError for a bad path, bad
    times, or when no player is installed.
    """
    target = validate_path(path, allowed_roots)
    if start_s < 0:
        raise PlaybackError("start_s cannot be negative")
    if length_s is not None and length_s <= 0:
        raise PlaybackError("length_s must be greater than zero")

    player = find_player()
    if player is None:
        raise PlaybackError(f"No audio player found. {INSTALL_HINT}")

    warnings: list[str] = []
    if player == "afplay" and start_s > 0:
        warnings.append(
            "afplay cannot start mid-file — playing from the beginning. "
            "Install mpv to seek."
        )
        start_s = 0.0

    stop()
    _reap_finished()

    command = build_command(player, target, start_s, length_s)
    if _IS_WINDOWS:
        child = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True,
            creationflags=_WINDOWS_DETACH_FLAGS,
        )
    else:
        child = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True,
        )
    _children[child.pid] = child
    _write_state({
        "pid": child.pid,
        "player": player,
        "path": str(target),
        "started_at": time.time(),
        "start_s": float(start_s),
    })

    result: dict[str, Any] = {
        "playing": True,
        "player": player,
        "pid": child.pid,
        "path": str(target),
        "start_s": float(start_s),
        "command": subprocess.list2cmdline(command) if _IS_WINDOWS else shlex.join(command),
    }
    if warnings:
        result["warnings"] = warnings
    return result
