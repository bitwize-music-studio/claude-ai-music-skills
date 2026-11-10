#!/usr/bin/env python3
"""PostToolUse hook: Validate track file YAML frontmatter after Write/Edit.

Only activates for files matching */tracks/*.md pattern.
Checks that the frontmatter block exists and carries its required fields.

``status`` is deliberately not one of them. A track's status lives in the
``| **Status** |`` row of its Track Details table: that is what the parser, the
state cache and ``update_track_field`` read and write, and ``templates/track.md``
has never had a frontmatter copy. This hook used to require one anyway, so the
first whole-file Write of any track failed, and the way to quiet it was to add
a second status that nothing keeps up to date. A frontmatter ``status`` left
over from then is ignored, whatever it says.
"""
from __future__ import annotations

import json
import re
import sys

REQUIRED_FIELDS = ["title", "track_number"]


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


def extract_frontmatter(content: str) -> dict | None:
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


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

    fm = extract_frontmatter(content)
    if fm is None:
        return ["Track file is missing YAML frontmatter (--- block)."]

    issues = []
    for field in REQUIRED_FIELDS:
        if field not in fm or not fm[field]:
            issues.append(f"Missing required frontmatter field: {field}")

    return issues


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
