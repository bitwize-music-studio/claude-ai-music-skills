#!/usr/bin/env python3
"""SessionStart hook: give every session the plugin's standing rules.

Claude Code never loads a ``CLAUDE.md`` from a plugin's folder, so a user who
installs the plugin from a marketplace never sees the repo's ``CLAUDE.md``. This
hook is how the rules reach them: Claude Code adds a SessionStart hook's plain
stdout to the session's context, on startup and again after ``/clear`` and
compaction.

The plugin is usually installed at user scope, so this hook runs in *every*
session on the machine, in every repository. It therefore prints the full rules
(``reference/plugin-rules.md``) only when the session's working directory is
inside the music workspace named in ``~/.bitwize-music/config.yaml``
(``content_root``, ``audio_root`` or ``documents_root``). Anywhere else it
prints a one-line pointer to the rules file instead, and when there is no
config (or it names no workspace) a one-line note that the plugin is not set
up yet, pointing to ``/bitwize-music:configure``.

Claude Code keeps SessionStart output whole only below 10,000 characters;
anything longer is replaced by a 2 KB preview and a file path. The rules are
printed only while they fit under ``LIMIT``, and the pointer is printed
otherwise, so an oversized rules file degrades to a pointer rather than to a
truncated rulebook. ``tests/unit/hooks/test_session_rules.py`` keeps the file
under the limit.

Like the other hooks, this runs on the system ``python3``, not the plugin's
venv: standard library only, and it must import on Python 3.9. It never fails
the session: any error prints nothing and exits 0.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Claude Code's cap is 10,000 characters; leave room for the path substitution.
LIMIT = 9000

RULES_RELPATH = "reference/plugin-rules.md"
CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"
ROOT_KEYS = ("content_root", "audio_root", "documents_root")

POINTER = (
    "The bitwize-music plugin is installed (AI music: albums, lyrics, Suno, "
    "mastering, release). This session is outside the music workspace set in "
    "~/.bitwize-music/config.yaml, so the plugin's rules are not loaded. Before "
    "doing any music work here, read {rules} and follow it."
)

# No config, or a config that names no workspace folder: the plugin was
# installed but never set up, so there is no workspace to be outside of.
SETUP_POINTER = (
    "The bitwize-music plugin is installed (AI music: albums, lyrics, Suno, "
    "mastering, release) but not set up yet: ~/.bitwize-music/config.yaml is "
    "missing or names no workspace folder. If the user wants music work, suggest "
    "/bitwize-music:configure (and /bitwize-music:setup for dependencies), and "
    "read {rules} first."
)

_KEY_LINE = re.compile(
    r"^(?P<indent>\s+)(?P<key>" + "|".join(ROOT_KEYS) + r")\s*:\s*(?P<value>.*?)\s*$"
)


def plugin_root() -> Path:
    """The plugin's folder: ``CLAUDE_PLUGIN_ROOT``, else this file's parent's parent."""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def _clean_value(raw: str) -> str:
    """A YAML scalar from one line: quotes removed, a trailing comment dropped."""
    value = raw.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end > 0 else value[1:]
    return value.split(" #", 1)[0].strip()


def workspace_roots(config_text: str) -> list[Path]:
    """The workspace folders named under ``paths:`` in the config.

    A deliberately small reader: the hook cannot rely on PyYAML being
    installed for the system Python. It reads the ``content_root``,
    ``audio_root`` and ``documents_root`` keys indented under a top-level
    ``paths:`` line, expanding ``~`` and environment variables.
    """
    roots: list[Path] = []
    in_paths = False
    for line in config_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[:1].isspace():
            in_paths = line.split("#", 1)[0].strip() == "paths:"
            continue
        if not in_paths:
            continue
        match = _KEY_LINE.match(line)
        if not match:
            continue
        value = _clean_value(match.group("value"))
        if not value:
            continue
        expanded = os.path.expandvars(os.path.expanduser(value))
        roots.append(Path(expanded))
    return roots


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return path.absolute()


def in_workspace(cwd: Path, roots: list[Path]) -> bool:
    """Whether *cwd* is one of *roots* or inside one."""
    here = _resolve(cwd)
    for root in roots:
        top = _resolve(root)
        if here == top or top in here.parents:
            return True
    return False


def session_cwd(stdin_text: str) -> Path:
    """The session's working directory from the hook input, else the process's."""
    try:
        data = json.loads(stdin_text) if stdin_text.strip() else {}
        cwd = data.get("cwd") if isinstance(data, dict) else None
        if isinstance(cwd, str) and cwd:
            return Path(cwd)
    except ValueError:
        pass
    return Path.cwd()


def render(rules_text: str, root: Path) -> str:
    """The rules with ``{plugin_root}`` replaced by the plugin's real folder."""
    return rules_text.replace("{plugin_root}", root.as_posix())


def build_output(cwd: Path, config_text: str | None, root: Path) -> str:
    """What the hook prints for a session in *cwd*."""
    rules_path = root / RULES_RELPATH
    roots = workspace_roots(config_text) if config_text is not None else []
    if not roots:
        return SETUP_POINTER.format(rules=rules_path.as_posix())
    pointer = POINTER.format(rules=rules_path.as_posix())
    if not in_workspace(cwd, roots):
        return pointer
    try:
        rules = render(rules_path.read_text(encoding="utf-8"), root)
    except OSError:
        return pointer
    if len(rules) > LIMIT:
        return pointer
    return rules


def main() -> int:
    try:
        stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""
        try:
            config_text: str | None = CONFIG_PATH.read_text(encoding="utf-8")
        except OSError:
            config_text = None
        output = build_output(session_cwd(stdin_text), config_text, plugin_root())
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
    except Exception:  # a hook must never break the session
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
