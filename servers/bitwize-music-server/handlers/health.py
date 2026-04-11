"""Plugin version, venv health check, and diagnostic tools."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import shutil
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


def _find_plugin_cache_dir() -> Path | None:
    """Locate the Claude Code plugin cache directory for bitwize-music.

    Scans ``~/.claude/plugins/cache/bitwize-music/`` for versioned
    subdirectories and returns the one with the highest version number.
    Returns ``None`` if no cache directory exists.
    """
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "bitwize-music"
    if not cache_base.is_dir():
        return None

    # Walk one level: each child may be an org/name dir containing version dirs
    candidates: list[Path] = []
    for org_or_name in cache_base.iterdir():
        if not org_or_name.is_dir():
            continue
        for version_dir in org_or_name.iterdir():
            if version_dir.is_dir() and (version_dir / "skills").is_dir():
                candidates.append(version_dir)

    if not candidates:
        return None

    # Sort by directory name descending (version-ish sort) and pick latest
    candidates.sort(key=lambda p: p.name, reverse=True)
    return candidates[0]


def _check_skill_registration() -> dict[str, Any]:
    """Compare on-disk skills against the Claude Code plugin cache.

    Scans ``{PLUGIN_ROOT}/skills/*/SKILL.md`` for the canonical set of
    skill names, then compares against the cached copy at
    ``~/.claude/plugins/cache/bitwize-music/*/skills/*/SKILL.md``.

    Returns:
        dict with status ("ok", "stale", "no_cache"), missing skills,
        ghost skills, counts, cached version, and fix message.
    """
    assert _shared.PLUGIN_ROOT is not None

    # Canonical skills from the plugin source
    source_skills = {
        p.parent.name
        for p in (_shared.PLUGIN_ROOT / "skills").glob("*/SKILL.md")
    }

    # Find the plugin cache
    cache_dir = _find_plugin_cache_dir()
    if cache_dir is None:
        return {
            "status": "no_cache",
            "message": "No Claude Code plugin cache found for bitwize-music",
            "source_count": len(source_skills),
            "fix_message": (
                "Install or update the plugin: claude plugin update bitwize-music "
                "— or use --plugin-dir for local development"
            ),
        }

    cached_skills = {
        p.parent.name
        for p in (cache_dir / "skills").glob("*/SKILL.md")
    }

    missing = sorted(source_skills - cached_skills)
    ghost = sorted(cached_skills - source_skills)
    ok_count = len(source_skills & cached_skills)

    # Read cached version from plugin.json
    cached_version = None
    cached_plugin_json = cache_dir / ".claude-plugin" / "plugin.json"
    try:
        if cached_plugin_json.exists():
            data = json.loads(cached_plugin_json.read_text(encoding="utf-8"))
            cached_version = data.get("version")
    except (json.JSONDecodeError, OSError):
        pass

    status = "ok" if not missing and not ghost else "stale"

    result: dict[str, Any] = {
        "status": status,
        "source_count": len(source_skills),
        "cached_count": len(cached_skills),
        "ok_count": ok_count,
        "missing": missing,
        "ghost": ghost,
        "cached_version": cached_version,
        "cache_path": str(cache_dir),
    }

    if status == "stale":
        result["fix_message"] = (
            "Plugin cache is stale — run: claude plugin update bitwize-music "
            "— or use --plugin-dir for local development"
        )

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


async def health_check() -> str:
    """Run startup health checks: venv packages and skill registration.

    Combines check_venv_health and skill registration checks into a
    single call for session startup. Use this instead of calling
    check_venv_health directly during session start.

    Returns:
        JSON with overall status ("ok", "warn", "fail"), per-check
        summaries, and raw results for venv and skills.
    """
    checks: list[dict[str, Any]] = []

    # --- Venv check ---
    venv_raw = json.loads(await check_venv_health())
    venv_status = venv_raw.get("status", "error")
    if venv_status == "ok":
        checks.append({"name": "venv", "status": "ok",
                        "detail": f"{venv_raw.get('checked', 0)} packages verified"})
    elif venv_status == "stale":
        parts = []
        if venv_raw.get("mismatches"):
            parts.append(f"{len(venv_raw['mismatches'])} outdated")
        if venv_raw.get("missing"):
            parts.append(f"{len(venv_raw['missing'])} missing")
        checks.append({"name": "venv", "status": "warn",
                        "detail": ", ".join(parts),
                        "fix": venv_raw.get("fix_command")})
    elif venv_status == "no_venv":
        checks.append({"name": "venv", "status": "fail",
                        "detail": "Venv not found at ~/.bitwize-music/venv"})
    else:
        checks.append({"name": "venv", "status": "fail",
                        "detail": venv_raw.get("message", venv_status)})

    # --- Skill registration check ---
    skills_raw = _check_skill_registration()
    skills_status = skills_raw.get("status", "error")
    if skills_status == "ok":
        checks.append({"name": "skills", "status": "ok",
                        "detail": f"{skills_raw.get('ok_count', 0)} skills registered"})
    elif skills_status == "stale":
        parts = []
        if skills_raw.get("missing"):
            parts.append(f"{len(skills_raw['missing'])} missing: {', '.join(skills_raw['missing'])}")
        if skills_raw.get("ghost"):
            parts.append(f"{len(skills_raw['ghost'])} ghost: {', '.join(skills_raw['ghost'])}")
        checks.append({"name": "skills", "status": "warn",
                        "detail": "; ".join(parts),
                        "fix": skills_raw.get("fix_message")})
    elif skills_status == "no_cache":
        checks.append({"name": "skills", "status": "warn",
                        "detail": "No plugin cache found",
                        "fix": skills_raw.get("fix_message")})

    # --- Overall status ---
    statuses = [c["status"] for c in checks]
    if "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"
    else:
        overall = "ok"

    return _safe_json({
        "status": overall,
        "checks": checks,
        "venv": venv_raw,
        "skills": skills_raw,
    })


# ---------------------------------------------------------------------------
# Diagnose
# ---------------------------------------------------------------------------


def _check_config() -> dict[str, Any]:
    """Check config completeness and path accessibility."""
    state = _shared.cache.get_state()
    config = state.get("config", {})

    issues: list[str] = []

    # Required fields
    for field in ("artist_name", "content_root", "audio_root", "documents_root"):
        if not config.get(field):
            issues.append(f"Missing required config field: {field}")

    # Path existence
    for field in ("content_root", "audio_root", "documents_root"):
        path_str = config.get(field, "")
        if path_str:
            p = Path(path_str).expanduser()
            if not p.is_dir():
                issues.append(f"{field} does not exist: {path_str}")

    if issues:
        return {"name": "config", "status": "fail", "detail": "; ".join(issues)}
    return {"name": "config", "status": "ok", "detail": "All required fields set, paths accessible"}


def _check_state_cache() -> dict[str, Any]:
    """Check state cache file integrity."""
    cache_path = Path.home() / ".bitwize-music" / "cache" / "state.json"

    if not cache_path.exists():
        return {"name": "state_cache", "status": "warn",
                "detail": "state.json not found — run rebuild_state()"}

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"name": "state_cache", "status": "fail",
                "detail": f"Cannot parse state.json: {e}"}

    version = data.get("schema_version", "unknown")
    album_count = len(data.get("albums", {}))
    return {"name": "state_cache", "status": "ok",
            "detail": f"Schema {version}, {album_count} album(s)"}


def _check_disk_space() -> dict[str, Any]:
    """Check disk space on audio root."""
    state = _shared.cache.get_state()
    audio_root = state.get("config", {}).get("audio_root", "")
    if not audio_root:
        return {"name": "disk_space", "status": "warn",
                "detail": "audio_root not configured"}

    p = Path(audio_root).expanduser()
    if not p.exists():
        return {"name": "disk_space", "status": "warn",
                "detail": f"audio_root does not exist: {audio_root}"}

    usage = shutil.disk_usage(str(p))
    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)

    if free_gb < 1.0:
        return {"name": "disk_space", "status": "fail",
                "detail": f"{free_gb:.1f} GB free of {total_gb:.0f} GB on audio root"}
    if free_gb < 5.0:
        return {"name": "disk_space", "status": "warn",
                "detail": f"{free_gb:.1f} GB free of {total_gb:.0f} GB on audio root"}
    return {"name": "disk_space", "status": "ok",
            "detail": f"{free_gb:.1f} GB free of {total_gb:.0f} GB on audio root"}


def _check_ffmpeg() -> dict[str, Any]:
    """Check if ffmpeg is available."""
    if shutil.which("ffmpeg"):
        return {"name": "ffmpeg", "status": "ok", "detail": "Found in PATH"}
    return {"name": "ffmpeg", "status": "warn",
            "detail": "Not found — needed for promo videos and audio conversion"}


def _check_database() -> dict[str, Any]:
    """Check database connectivity if enabled."""
    state = _shared.cache.get_state()
    db_config = state.get("config", {}).get("database", {})

    if not db_config.get("enabled"):
        return {"name": "database", "status": "ok",
                "detail": "Not enabled (optional)"}

    for field in ("host", "name", "user"):
        if not db_config.get(field):
            return {"name": "database", "status": "fail",
                    "detail": f"Database enabled but missing field: {field}"}

    try:
        import psycopg2
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config.get("port", 5432),
            dbname=db_config["name"],
            user=db_config["user"],
            password=db_config.get("password", ""),
            connect_timeout=5,
        )
        conn.close()
        return {"name": "database", "status": "ok", "detail": "Connected successfully"}
    except ImportError:
        return {"name": "database", "status": "fail",
                "detail": "psycopg2 not installed — pip install psycopg2-binary"}
    except Exception as e:
        return {"name": "database", "status": "fail",
                "detail": f"Connection failed: {e}"}


def _check_cloud() -> dict[str, Any]:
    """Check cloud config if enabled."""
    state = _shared.cache.get_state()
    cloud = state.get("config", {}).get("cloud", {})

    if not cloud.get("enabled"):
        return {"name": "cloud", "status": "ok",
                "detail": "Not enabled (optional)"}

    provider = cloud.get("provider", "")
    if provider == "r2":
        r2 = cloud.get("r2", {})
        missing = [f for f in ("account_id", "access_key_id", "secret_access_key", "bucket")
                   if not r2.get(f)]
        if missing:
            return {"name": "cloud", "status": "fail",
                    "detail": f"R2 enabled but missing: {', '.join(missing)}"}
    elif provider == "s3":
        s3 = cloud.get("s3", {})
        missing = [f for f in ("access_key_id", "secret_access_key", "bucket")
                   if not s3.get(f)]
        if missing:
            return {"name": "cloud", "status": "fail",
                    "detail": f"S3 enabled but missing: {', '.join(missing)}"}
    elif not provider:
        return {"name": "cloud", "status": "fail",
                "detail": "Cloud enabled but no provider set"}

    return {"name": "cloud", "status": "ok",
            "detail": f"Provider: {provider}, configured"}


async def diagnose() -> str:
    """Run comprehensive health checks on the plugin environment.

    Checks config completeness, state cache integrity, disk space,
    tool availability, and optional service connectivity.

    Returns:
        JSON with per-check results and overall status
    """
    checks = [
        _check_config(),
        _check_state_cache(),
        _check_disk_space(),
        _check_ffmpeg(),
        _check_database(),
        _check_cloud(),
    ]

    # Add venv check (reuse existing logic)
    venv_result = json.loads(await check_venv_health())
    venv_status = venv_result.get("status", "error")
    if venv_status == "ok":
        checks.append({"name": "venv", "status": "ok",
                        "detail": f"{venv_result.get('checked', 0)} packages verified"})
    elif venv_status == "stale":
        mismatches = venv_result.get("mismatches", [])
        missing = venv_result.get("missing", [])
        parts = []
        if mismatches:
            parts.append(f"{len(mismatches)} outdated")
        if missing:
            parts.append(f"{len(missing)} missing")
        checks.append({"name": "venv", "status": "warn",
                        "detail": ", ".join(parts),
                        "fix": venv_result.get("fix_command")})
    else:
        checks.append({"name": "venv", "status": "fail",
                        "detail": venv_result.get("message", venv_status)})

    # Add skill registration check
    skills_result = _check_skill_registration()
    skills_status = skills_result.get("status", "error")
    if skills_status == "ok":
        checks.append({"name": "skills", "status": "ok",
                        "detail": f"{skills_result.get('ok_count', 0)} skills registered"})
    elif skills_status == "stale":
        parts = []
        if skills_result.get("missing"):
            parts.append(f"{len(skills_result['missing'])} missing")
        if skills_result.get("ghost"):
            parts.append(f"{len(skills_result['ghost'])} ghost")
        checks.append({"name": "skills", "status": "warn",
                        "detail": ", ".join(parts),
                        "fix": skills_result.get("fix_message")})
    else:
        checks.append({"name": "skills", "status": "warn",
                        "detail": skills_result.get("message", skills_status)})

    # Add version check
    version_result = json.loads(await get_plugin_version())
    if version_result.get("needs_upgrade"):
        checks.append({"name": "plugin_version", "status": "warn",
                        "detail": f"Upgrade available: {version_result.get('stored_version')} → {version_result.get('current_version')}"})
    else:
        checks.append({"name": "plugin_version", "status": "ok",
                        "detail": f"v{version_result.get('current_version', 'unknown')}"})

    # Overall status
    statuses = [c["status"] for c in checks]
    if "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"
    else:
        overall = "ok"

    return _safe_json({
        "status": overall,
        "checks": checks,
        "total": len(checks),
        "ok": statuses.count("ok"),
        "warn": statuses.count("warn"),
        "fail": statuses.count("fail"),
    })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp: Any) -> None:
    """Register plugin version, health check, venv, and diagnostic tools."""
    mcp.tool()(get_plugin_version)
    mcp.tool()(check_venv_health)
    mcp.tool()(health_check)
    mcp.tool()(diagnose)
