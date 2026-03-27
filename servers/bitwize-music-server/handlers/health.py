"""Plugin version and venv health check tools."""

from __future__ import annotations

import importlib.metadata
import json
import logging
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import _safe_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_requirements(path: Path) -> dict[str, str]:
    """Parse requirements.txt into {package_name: version} dict.

    Handles ``==`` pins only (our format), skips comments and blank lines.
    Strips extras markers (e.g., ``mcp[cli]==1.23.0`` → ``mcp: 1.23.0``).
    Lowercases package names for consistent comparison.

    Returns:
        dict mapping lowercased package names to pinned version strings.
        Empty dict on missing or unreadable file.
    """
    result: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return result

    for line in text.splitlines():
        line = line.strip()
        # Strip inline comments
        if "#" in line:
            line = line[:line.index("#")].strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            continue
        name, _, version = line.partition("==")
        # Strip extras: mcp[cli] → mcp
        if "[" in name:
            name = name[:name.index("[")]
        name = name.strip().lower()
        version = version.strip()
        if name and version:
            result[name] = version
    return result


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


async def get_plugin_version() -> str:
    """Get the current and stored plugin version.

    Compares the plugin version stored in state.json with the current
    version from .claude-plugin/plugin.json. Useful for upgrade detection.

    Returns:
        JSON with stored_version, current_version, and needs_upgrade flag
    """
    state = _shared.cache.get_state()
    stored = state.get("plugin_version")

    # Read current version from plugin.json
    assert _shared.PLUGIN_ROOT is not None
    plugin_json = _shared.PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    current = None
    try:
        if plugin_json.exists():
            data = json.loads(plugin_json.read_text(encoding="utf-8"))
            current = data.get("version")
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Cannot read plugin.json: %s", e)

    needs_upgrade = False
    if stored is None and current is not None:
        needs_upgrade = True  # First run
    elif stored and current and stored != current:
        needs_upgrade = True

    return _safe_json({
        "stored_version": stored,
        "current_version": current,
        "needs_upgrade": needs_upgrade,
        "plugin_root": str(_shared.PLUGIN_ROOT),
    })


async def check_venv_health() -> str:
    """Check if venv packages match requirements.txt pinned versions.

    Compares installed package versions in the plugin venv against
    the pinned versions in requirements.txt. Useful for detecting
    version drift after plugin upgrades.

    Returns:
        JSON with status ("ok", "stale", "no_venv", "error"),
        mismatches, missing packages, counts, and fix command.
    """
    venv_python = Path.home() / ".bitwize-music" / "venv" / "bin" / "python3"
    if not venv_python.exists():
        return _safe_json({
            "status": "no_venv",
            "message": "Venv not found at ~/.bitwize-music/venv",
        })

    assert _shared.PLUGIN_ROOT is not None
    req_path = _shared.PLUGIN_ROOT / "requirements.txt"
    requirements = _parse_requirements(req_path)
    if not requirements:
        return _safe_json({
            "status": "error",
            "message": f"Cannot read or parse {req_path}",
        })

    mismatches = []
    missing = []
    ok_count = 0

    for pkg, required_version in sorted(requirements.items()):
        try:
            installed_version = importlib.metadata.version(pkg)
            if installed_version == required_version:
                ok_count += 1
            else:
                mismatches.append({
                    "package": pkg,
                    "required": required_version,
                    "installed": installed_version,
                })
        except importlib.metadata.PackageNotFoundError:
            missing.append({
                "package": pkg,
                "required": required_version,
            })

    checked = len(requirements)
    status = "ok" if not mismatches and not missing else "stale"

    result = {
        "status": status,
        "checked": checked,
        "ok_count": ok_count,
        "mismatches": mismatches,
        "missing": missing,
    }

    if status == "stale":
        result["fix_command"] = (
            f"~/.bitwize-music/venv/bin/pip install -r {req_path}"
        )

    return _safe_json(result)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp: Any) -> None:
    """Register plugin version and venv health tools with the MCP server."""
    mcp.tool()(get_plugin_version)
    mcp.tool()(check_venv_health)
