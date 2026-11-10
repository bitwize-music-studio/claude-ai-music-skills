"""Ask an installed Codex CLI to make an image with its built-in image tool.

What this relies on was measured against codex-cli 0.164.0:

* ``codex exec`` runs one turn without a terminal, and reads its prompt from
  stdin when the prompt argument is ``-``.
* The built-in image tool needs no API key: it uses the ChatGPT sign-in Codex
  already has. Each image counts against that plan's image allowance.
* The tool takes no destination. It saves the PNG under
  ``$CODEX_HOME/generated_images/<thread id>/``, and the agent then copies it to
  wherever the prompt asked. ``--json`` prints the thread id in its first event.
* The image is 1254x1254 whatever size is asked for, and a run takes about
  fifty seconds.
* ``--ephemeral`` keeps the run out of the user's saved Codex sessions.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.artwork.cover import image_size

logger = logging.getLogger(__name__)

# Who makes the cover image. "manual" is the user, in a tool of their choice.
GENERATORS = ("manual", "codex")
# Each candidate is one image against the user's allowance, so the count is capped.
MAX_CANDIDATES = 4
# A run took 49 and 52 seconds when measured; this leaves room for a slow one.
DEFAULT_TIMEOUT_S = 300
_STATUS_TIMEOUT_S = 20

# The id Codex gives a run. It becomes a folder name, so it is checked first.
_THREAD_ID_RE = re.compile(r"^[0-9A-Za-z-]{8,64}$")

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _candidate_count(value: Any) -> int:
    """A count from config, kept between 1 and MAX_CANDIDATES."""
    if isinstance(value, bool) or value is None:
        return 1
    try:
        count = int(value)
    except (TypeError, ValueError, OverflowError):
        return 1
    return min(max(count, 1), MAX_CANDIDATES)


def artwork_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    """The ``artwork`` section of the user's config, validated.

    Returns ``{"generator": "manual" | "codex", "candidates": 1..4,
    "codex_path": str}``. Anything missing or unreadable falls back to the
    default, which is the user making the image themselves.
    """
    section = config.get("artwork") if isinstance(config, dict) else None
    if not isinstance(section, dict):
        section = {}

    written = section.get("generator")
    generator = written.strip().lower() if isinstance(written, str) else ""
    if generator not in GENERATORS:
        if written not in (None, ""):
            logger.warning(
                "Config artwork.generator is not one of %s — using manual",
                ", ".join(GENERATORS),
            )
        generator = "manual"

    codex_path = section.get("codex_path")
    return {
        "generator": generator,
        "candidates": _candidate_count(section.get("candidates")),
        "codex_path": codex_path if isinstance(codex_path, str) else "",
    }


# ---------------------------------------------------------------------------
# Finding Codex and asking what it can do
# ---------------------------------------------------------------------------

_EXECUTABLE_NAMES = ("codex", "codex.cmd", "codex.exe")


def find_codex(
    configured: str = "",
    *,
    which: Callable[[str], str | None] = shutil.which,
    home: Path | None = None,
) -> str:
    """Path to the Codex executable, or ``""`` when there is none.

    A path from config wins when it exists. Otherwise PATH is searched, and
    then the folders Codex is usually installed in, because an MCP server does
    not always inherit the PATH of the shell the user works in.

    *home* is for tests: when given, only folders under it are tried.
    """
    if configured:
        candidate = Path(os.path.expanduser(configured))
        if candidate.is_file():
            return str(candidate)
        logger.warning("Config artwork.codex_path does not exist — searching PATH instead")

    found = which("codex")
    if found:
        return found

    base = home if home is not None else Path.home()
    folders = [base / ".local" / "bin", base / ".codex" / "bin", base / "bin"]
    if home is None:
        folders += [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    for folder in folders:
        for name in _EXECUTABLE_NAMES:
            if (folder / name).is_file():
                return str(folder / name)
    return ""


def _ask(codex: str, args: list[str], run: Runner) -> str:
    """Everything Codex prints for one quick question; ``""`` if it will not run."""
    try:
        proc = run(
            [codex, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, timeout=_STATUS_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return f"{proc.stdout or ''}\n{proc.stderr or ''}"


def codex_status(codex: str, *, run: Runner = subprocess.run) -> dict[str, Any]:
    """What the Codex at *codex* reports about itself.

    Returns ``{"version": str, "logged_in": bool | None, "image_generation":
    bool | None}``. ``None`` means Codex did not say, which is not the same as
    "no": an older CLI does not list the feature at all.
    """
    version = next((line.strip() for line in _ask(codex, ["--version"], run).splitlines()
                    if line.strip()), "")

    login = _ask(codex, ["login", "status"], run).lower()
    logged_in: bool | None
    if "not logged in" in login:
        logged_in = False
    elif "logged in" in login:
        logged_in = True
    else:
        logged_in = None

    image_generation: bool | None = None
    for line in _ask(codex, ["features", "list"], run).splitlines():
        parts = line.split()
        if parts and parts[0] == "image_generation" and parts[-1] in ("true", "false"):
            image_generation = parts[-1] == "true"
            break

    return {"version": version, "logged_in": logged_in, "image_generation": image_generation}


# ---------------------------------------------------------------------------
# Making one image
# ---------------------------------------------------------------------------


def build_instruction(prompt: str, filename: str, avoid: str = "") -> str:
    """What Codex is told: make one square image, save it under one name."""
    parts = [
        "Use your built-in image generation tool to create one square (1:1) album cover image.",
        "",
        "Image prompt:",
        prompt.strip(),
    ]
    if avoid.strip():
        parts += ["", f"Avoid: {avoid.strip()}"]
    parts += [
        "",
        "Then copy the generated PNG into the current working directory as "
        f"{filename} . Do not create or change any other file. "
        "Reply with only the saved file's path.",
    ]
    return "\n".join(parts)


def _read_events(output: str) -> tuple[str, str]:
    """The run's thread id and the last thing the agent said, from ``--json`` output."""
    thread_id = ""
    last_message = ""
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id") or "")
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            last_message = str(item.get("text") or "")
    return thread_id, last_message


def _fetch_original(thread_id: str, codex_home: Path, target: Path) -> bool:
    """Copy the image Codex stored for *thread_id* to *target*, if there is one."""
    if not _THREAD_ID_RE.match(thread_id):
        return False
    folder = codex_home / "generated_images" / thread_id
    try:
        images = sorted(folder.glob("*.png"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return False
    if not images:
        return False
    shutil.copyfile(images[-1], target)
    return True


def generate_image(
    codex: str,
    prompt: str,
    dest_dir: Path,
    filename: str,
    *,
    avoid: str = "",
    timeout: int = DEFAULT_TIMEOUT_S,
    run: Runner = subprocess.run,
    codex_home: Path | None = None,
) -> dict[str, Any]:
    """Have Codex make one image and save it as ``dest_dir / filename``.

    This spends one image of the user's ChatGPT allowance. The caller is
    responsible for having asked first.

    Codex is run once, without a saved session, and may write only inside
    *dest_dir*. The prompt goes in on stdin: it is prose, and must never be
    parsed by a shell.

    Returns ``{"ok": True, "path", "width", "height", "seconds", "saved_by"}``,
    where ``saved_by`` is ``"codex"`` when the agent copied the image itself and
    ``"plugin"`` when it had to be fetched from Codex's own store. On failure
    returns ``{"ok": False, "error", "seconds"}``; an existing file is never
    overwritten and no file is left behind.
    """
    if (not filename or Path(filename).name != filename
            or not filename.lower().endswith(".png") or filename.lower() == ".png"):
        return {"ok": False, "error": f"Not a plain PNG file name: {filename!r}", "seconds": 0}
    target = dest_dir / filename
    if target.exists():
        return {"ok": False, "error": f"{target} already exists; it was not overwritten",
                "seconds": 0}

    dest_dir.mkdir(parents=True, exist_ok=True)
    command = [
        codex, "exec",
        "--skip-git-repo-check",    # an audio folder is not a repository
        "--ephemeral",              # keep the run out of the user's saved sessions
        "-s", "workspace-write",    # may write inside dest_dir and nowhere else
        "-C", str(dest_dir),
        "--json",
        "-",                        # read the prompt from stdin
    ]
    started = time.monotonic()

    def elapsed() -> int:
        return round(time.monotonic() - started)

    try:
        proc = run(
            command,
            input=build_instruction(prompt, filename, avoid),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return {"ok": False, "error": f"Codex was not found at {codex}", "seconds": elapsed()}
    except subprocess.TimeoutExpired:
        target.unlink(missing_ok=True)
        return {"ok": False, "error": f"Codex did not finish within {timeout} seconds",
                "seconds": elapsed()}
    except OSError as exc:
        return {"ok": False, "error": f"Codex could not be run: {exc}", "seconds": elapsed()}

    thread_id, last_message = _read_events(proc.stdout or "")
    saved_by = "codex"
    if not target.exists():
        home = codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        if _fetch_original(thread_id, home, target):
            saved_by = "plugin"

    if not target.exists():
        said = " ".join(last_message.split())[:300]
        stderr_tail = " ".join((proc.stderr or "").split())[-300:]
        detail = "; ".join(part for part in (said, stderr_tail) if part)
        return {
            "ok": False,
            "error": f"Codex finished (exit {proc.returncode}) without saving an image"
                     + (f": {detail}" if detail else ""),
            "seconds": elapsed(),
        }

    try:
        width, height = image_size(target)
    except ValueError as exc:
        target.unlink(missing_ok=True)
        return {"ok": False, "error": f"Codex saved a file that is not an image ({exc})",
                "seconds": elapsed()}

    return {
        "ok": True,
        "path": str(target),
        "width": width,
        "height": height,
        "seconds": elapsed(),
        "saved_by": saved_by,
    }
