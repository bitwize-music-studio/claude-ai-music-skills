"""Where Claude Code and Codex record MCP servers — read-only.

Claude Code keeps user-scope servers, and each project's local-scope servers,
in ``~/.claude.json`` (``$CLAUDE_CONFIG_DIR/.claude.json`` when that is set);
project-scope servers in the project's ``.mcp.json``; and administrator-managed
servers in one file per OS. Codex keeps its servers in ``~/.codex/config.toml``.

This module finds the servers registered for one host. The plugin uses it to
tell whether Suno's MCP server is set up for the current session, whatever the
user named it. It never writes, and a missing or malformed file counts as
"nothing registered there".
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# The order find_servers() reports scopes in: nearest to the session first.
SCOPE_ORDER = ("local", "project", "user", "managed", "codex")


# =============================================================================
# Locations
# =============================================================================


def claude_config_file() -> Path:
    """Claude Code's per-user config, which holds the user- and local-scope servers."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config_dir) if config_dir else Path.home()) / ".claude.json"


def project_dir(explicit: str | Path | None = None) -> Path:
    """The project the session runs in: as given, else ``$CLAUDE_PROJECT_DIR``, else the cwd."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path.cwd()


_MANAGED_FILE_BY_PLATFORM = {
    "darwin": Path("/Library/Application Support/ClaudeCode/managed-mcp.json"),
}
_MANAGED_FILE_ELSEWHERE = Path("/etc/claude-code/managed-mcp.json")


def _is_windows() -> bool:
    return os.name == "nt"


def managed_file() -> Path:
    """The administrator-managed server list for this OS."""
    if _is_windows():
        # Windows environment names are case-insensitive; os.environ spells them upper-case.
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(program_data) / "ClaudeCode" / "managed-mcp.json"
    return _MANAGED_FILE_BY_PLATFORM.get(sys.platform, _MANAGED_FILE_ELSEWHERE)


def codex_config_file() -> Path:
    """Codex's config, which holds its ``[mcp_servers.*]`` tables."""
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home) if codex_home else Path.home() / ".codex") / "config.toml"


# =============================================================================
# Reading
# =============================================================================


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.debug("Skipping %s: %s", path, e)
        return {}
    return data if isinstance(data, dict) else {}


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.debug("Skipping %s: %s", path, e)
        return {}


def _matching(servers: Any, host: str, scope: str) -> list[dict[str, str]]:
    """The entries of a ``mcpServers``-style mapping whose URL is on *host*."""
    found: list[dict[str, str]] = []
    if not isinstance(servers, dict):
        return found
    wanted = host.lower()
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if not isinstance(url, str):
            continue  # a stdio server
        if (urlparse(url).hostname or "").lower() == wanted:
            found.append({"name": str(name), "scope": scope, "url": url})
    return found


def _project_keys(directory: Path) -> list[str]:
    """The spellings under which ``~/.claude.json`` may file this project."""
    keys = [str(directory)]
    try:
        resolved = str(directory.resolve())
    except OSError:
        return keys
    if resolved not in keys:
        keys.append(resolved)
    return keys


def _local_servers(claude: dict[str, Any], directory: Path) -> Any:
    projects = claude.get("projects")
    if not isinstance(projects, dict):
        return None
    for key in _project_keys(directory):
        entry = projects.get(key)
        if isinstance(entry, dict):
            return entry.get("mcpServers")
    return None


# =============================================================================
# Public API
# =============================================================================


def find_servers(host: str, project: str | Path | None = None) -> list[dict[str, str]]:
    """Every registered MCP server whose URL is on *host*.

    Args:
        host: The host to look for, e.g. ``api.suno.com``. Compared case-insensitively.
        project: The project directory for local and project scope; defaults to
            ``$CLAUDE_PROJECT_DIR``, then the current directory.

    Returns:
        ``[{"name", "scope", "url"}, ...]`` in ``SCOPE_ORDER``: local, project,
        user, managed, codex. Empty when nothing is registered.
    """
    directory = project_dir(project)
    claude = _load_json(claude_config_file())
    found: list[dict[str, str]] = []
    found += _matching(_local_servers(claude, directory), host, "local")
    found += _matching(_load_json(directory / ".mcp.json").get("mcpServers"), host, "project")
    found += _matching(claude.get("mcpServers"), host, "user")
    found += _matching(_load_json(managed_file()).get("mcpServers"), host, "managed")
    found += _matching(_load_toml(codex_config_file()).get("mcp_servers"), host, "codex")
    return found
