#!/usr/bin/env python3
"""PostToolUse hook: Validate track file YAML frontmatter after Write/Edit.

Only activates for files matching */tracks/*.md pattern.
Checks required frontmatter fields and valid status values.
"""
import json
import sys
import re


REQUIRED_FIELDS = ["title", "track_number", "status"]
VALID_STATUSES = [
    "Not Started",
    "Sources Pending",
    "Sources Verified",
    "In Progress",
    "Generated",
    "Final",
]


def is_track_file(file_path: str) -> bool:
    return "/tracks/" in file_path and file_path.endswith(".md")


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

    status = fm.get("status", "")
    if status and status not in VALID_STATUSES:
        issues.append(
            f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}"
        )

    return issues


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    issues = validate(data)
    if issues:
        msg = "Track frontmatter validation failed:\n" + "\n".join(f"  - {i}" for i in issues)
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
