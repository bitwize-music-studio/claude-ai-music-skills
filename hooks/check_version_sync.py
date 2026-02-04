#!/usr/bin/env python3
"""PostToolUse hook: Check plugin.json and marketplace.json versions stay in sync.

Only activates when editing plugin.json or marketplace.json.
"""
import json
import os
import sys


MANIFEST_FILES = {"plugin.json", "marketplace.json"}


def is_manifest_file(file_path: str) -> bool:
    return os.path.basename(file_path) in MANIFEST_FILES and ".claude-plugin" in file_path


def check_sync(data: dict) -> list[str]:
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not is_manifest_file(file_path):
        return []

    plugin_dir = os.path.dirname(file_path)
    plugin_path = os.path.join(plugin_dir, "plugin.json")
    marketplace_path = os.path.join(plugin_dir, "marketplace.json")

    if not os.path.exists(plugin_path) or not os.path.exists(marketplace_path):
        return []

    try:
        with open(plugin_path) as f:
            plugin_data = json.load(f)
        with open(marketplace_path) as f:
            marketplace_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    plugin_version = plugin_data.get("version", "")
    marketplace_version = ""
    plugins = marketplace_data.get("plugins", [])
    if plugins:
        marketplace_version = plugins[0].get("version", "")

    if plugin_version and marketplace_version and plugin_version != marketplace_version:
        return [
            f"Version mismatch: plugin.json has '{plugin_version}' "
            f"but marketplace.json has '{marketplace_version}'. "
            f"These must stay in sync."
        ]

    return []


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    issues = check_sync(data)
    if issues:
        msg = "Version sync check failed:\n" + "\n".join(f"  - {i}" for i in issues)
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
