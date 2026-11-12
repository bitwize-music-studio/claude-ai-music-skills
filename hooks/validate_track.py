#!/usr/bin/env python3
"""PostToolUse hook: Validate track file YAML frontmatter after Write/Edit.

Only activates for files matching */tracks/*.md pattern.
Reports one thing: a frontmatter block that opens on the first line and is
never closed. Such a block swallows the whole file, and every frontmatter
reader then drops every field at once (title, explicit, genre, suno_url).

It deliberately requires no frontmatter at all, and no field in it. A track's
details live in its Track Details table, which is what the parser, the state
cache and ``update_track_field`` read and write. Most older tracks have no
frontmatter, and some carry a block from an older template with neither
``title`` nor ``track_number``. This hook used to require a block with
``title``, ``track_number`` and ``status``, so a whole-file rewrite of any such
track failed, and the way to quiet it was to bolt on fields nothing reads.
"""
from __future__ import annotations

import json
import sys


def is_track_file(file_path: str) -> bool:
    """True for ``.md`` files living in a directory segment named ``tracks``.

    Claude Code passes the platform's *native* path, so on Windows this arrives
    backslash-separated (``...\\tracks\\01-opener.md``) and mixed separators
    (``C:/foo\\tracks/01-x.md``) are possible too. Backslashes are folded to
    forward slashes before splitting rather than going through ``pathlib``:
    ``PurePosixPath`` would not split backslashes at all, ``PureWindowsPath``
    behaves identically to this but costs an import on a hook that runs on
    every Write/Edit. The trade-off is that a POSIX file whose *name* legally
    contains a backslash could be split at it — vanishingly rare, and the
    failure mode is a harmless extra frontmatter check.

    Matching whole segments (rather than the old ``"/tracks/" in path``
    substring test) also keeps ``soundtracks/``, ``tracks-old/`` and
    ``tracksnotadir/`` from matching, and additionally handles relative paths
    such as ``tracks/01-x.md``, which the substring form rejected.
    """
    if not file_path.endswith(".md"):
        return False
    # Exclude the final component: that is the filename, not a directory.
    return "tracks" in file_path.replace("\\", "/").split("/")[:-1]


def frontmatter_problem(content: str) -> str | None:
    """What is wrong with *content*'s frontmatter block, or None.

    A file that does not start with a ``---`` line has no frontmatter, which
    is fine. One that does must have a second ``---`` line to close it.
    Trailing spaces and Windows line endings are allowed on both.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    if any(line.strip() == "---" for line in lines[1:]):
        return None
    return (
        "Track file opens a YAML frontmatter block (---) on its first line but "
        "it is never closed. Add a closing --- line after the last field."
    )


def get_file_content(data: dict) -> str | None:
    tool_input = data.get("tool_input", {})
    # Write tool provides full content
    if "content" in tool_input:
        return tool_input["content"]
    return None


def validate(data: dict) -> list[str]:
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not is_track_file(file_path):
        return []

    content = get_file_content(data)
    if content is None:
        # Edit tool — can't validate full frontmatter from partial edit
        return []

    problem = frontmatter_problem(content)
    return [problem] if problem else []


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # Well-formed JSON that is not an object (a list, null, a number, a string)
    # has no `tool_input` to inspect. There is nothing to validate, and this
    # hook must never break the user's session over an unexpected payload.
    if not isinstance(data, dict):
        sys.exit(0)

    issues = validate(data)
    if issues:
        msg = "Track frontmatter validation failed:\n" + "\n".join(f"  - {i}" for i in issues)
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
