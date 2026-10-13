#!/usr/bin/env python3
"""PostToolUse hook: keep the Claude and Codex plugin versions in sync.

The Claude manifest and marketplace entry are the canonical pair.  When the
Codex manifest exists, its version must match the Claude plugin manifest too.
Malformed or partially-written manifests are ignored so an editor's transient
state does not turn this advisory hook into a hard failure.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

MANIFEST_FILES = {"plugin.json", "marketplace.json"}
PLUGIN_DIRS = {".claude-plugin", ".codex-plugin"}


def _manifest_context(file_path: str):
    """Return ``(repository_root, manifest_dir, path)`` for a manifest path."""
    if not isinstance(file_path, str) or not file_path:
        return None

    path = Path(file_path)
    if path.name not in MANIFEST_FILES:
        return None

    for parent in (path.parent, *path.parents):
        if parent.name in PLUGIN_DIRS:
            return parent.parent, parent.name, path
    return None


def is_manifest_file(file_path: str) -> bool:
    return _manifest_context(file_path) is not None


def _read_json(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def _plugin_version(data) -> str:
    return data.get("version", "") if isinstance(data, dict) else ""


def _marketplace_version(data) -> str:
    if not isinstance(data, dict):
        return ""
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list) or not plugins or not isinstance(plugins[0], dict):
        return ""
    return plugins[0].get("version", "")


def _version_pairs(root: Path):
    """Return version pairs that can be checked from this repository root."""
    claude_plugin_path = root / ".claude-plugin" / "plugin.json"
    marketplace_path = root / ".claude-plugin" / "marketplace.json"

    claude_plugin = _read_json(claude_plugin_path)
    marketplace = _read_json(marketplace_path)
    if claude_plugin is None or marketplace is None:
        return []

    pairs = []
    claude_version = _plugin_version(claude_plugin)
    marketplace_version = _marketplace_version(marketplace)
    if claude_version and marketplace_version:
        pairs.append(
            (
                claude_plugin_path,
                "plugin.json",
                claude_version,
                marketplace_path,
                "marketplace.json",
                marketplace_version,
            )
        )

    codex_plugin_path = root / ".codex-plugin" / "plugin.json"
    if codex_plugin_path.exists():
        codex_plugin = _read_json(codex_plugin_path)
        codex_version = _plugin_version(codex_plugin)
        if claude_version and codex_version:
            pairs.append(
                (
                    claude_plugin_path,
                    ".claude-plugin/plugin.json",
                    claude_version,
                    codex_plugin_path,
                    ".codex-plugin/plugin.json",
                    codex_version,
                )
            )

    return pairs


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
        os.path.abspath(str(right))
    )


def _modified_files(root: Path) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(root),
        )
    except (subprocess.TimeoutExpired, OSError):
        return set()

    return {
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }


def _is_modified(path: Path, root: Path, modified: set[str]) -> bool:
    try:
        relative = os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        relative = ""
    absolute = str(path).replace(os.sep, "/")
    return relative in modified or absolute in modified


def check_sync(data: dict) -> list[str]:
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    context = _manifest_context(file_path)
    if context is None:
        return []

    root, _, _ = context
    issues = []
    modified = None
    for left_path, left_label, left_version, right_path, right_label, right_version in _version_pairs(root):
        if left_version == right_version:
            continue

        # If the counterpart is also modified, this is likely a sequential
        # edit of a version pair. Defer until the second file is saved.
        counterpart = None
        if _same_path(Path(file_path), left_path):
            counterpart = right_path
        elif _same_path(Path(file_path), right_path):
            counterpart = left_path
        if counterpart is not None:
            if modified is None:
                modified = _modified_files(root)
            if _is_modified(counterpart, root, modified):
                continue

        issues.append(
            f"Version mismatch: {left_label} has '{left_version}' "
            f"but {right_label} has '{right_version}'. "
            "These must stay in sync."
        )

    return issues


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
