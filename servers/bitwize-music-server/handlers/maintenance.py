"""Maintenance tools — reset mastering, legacy cleanup, audio layout migration."""

import logging
import shutil
from pathlib import Path

from handlers._shared import _normalize_slug, _safe_json, _resolve_audio_dir
from handlers import _shared

logger = logging.getLogger("bitwize-music-state")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESET_ALLOWED_SUBFOLDERS = {"mastered", "polished"}

_LEGACY_VENV_DIRS = ["mastering-env", "promotion-env", "cloud-env"]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def reset_mastering(
    album_slug: str,
    subfolders: list[str] = ["mastered"],
    dry_run: bool = True,
) -> str:
    """Remove mastered/ and/or polished/ subfolders so the mastering pipeline can be re-run.

    Only 'mastered' and 'polished' are allowed — originals/ and stems/ are
    protected and cannot be deleted through this tool.

    Default is dry_run=True: reports what would be deleted without removing anything.
    Set dry_run=False to actually delete.

    Args:
        album_slug: Album slug (e.g., "my-album")
        subfolders: Which subfolders to remove (default: ["mastered"])
        dry_run: If true (default), only report what would be deleted

    Returns:
        JSON with per-subfolder results (deleted/not_found/rejected)
    """
    # Validate subfolder names against allowlist
    rejected = [s for s in subfolders if s not in _RESET_ALLOWED_SUBFOLDERS]
    if rejected:
        return _safe_json({
            "error": f"Disallowed subfolders: {rejected}",
            "allowed": sorted(_RESET_ALLOWED_SUBFOLDERS),
            "hint": "Only 'mastered' and 'polished' can be reset. "
                    "originals/ and stems/ are protected.",
        })

    err, audio_dir = _resolve_audio_dir(album_slug)
    if err:
        return err

    results = {}
    for subfolder in subfolders:
        target = audio_dir / subfolder
        if not target.is_dir():
            results[subfolder] = {"status": "not_found", "path": str(target)}
            continue

        # Count files and total size
        file_count = 0
        total_bytes = 0
        for f in target.rglob("*"):
            if f.is_file():
                file_count += 1
                total_bytes += f.stat().st_size

        size_mb = round(total_bytes / (1024 * 1024), 2)

        if dry_run:
            results[subfolder] = {
                "status": "would_delete",
                "path": str(target),
                "file_count": file_count,
                "size_mb": size_mb,
            }
        else:
            shutil.rmtree(target)
            results[subfolder] = {
                "status": "deleted",
                "path": str(target),
                "file_count": file_count,
                "size_mb": size_mb,
            }

    return _safe_json({
        "album_slug": album_slug,
        "dry_run": dry_run,
        "results": results,
    })


async def cleanup_legacy_venvs(
    dry_run: bool = True,
) -> str:
    """Detect and remove stale per-tool virtual environments from ~/.bitwize-music/.

    Prior to 0.40.0, each tool had its own venv (mastering-env, promotion-env,
    cloud-env). These are now consolidated into a single ~/.bitwize-music/venv/.

    Default is dry_run=True: reports what would be removed.
    Set dry_run=False to actually delete the stale directories.

    Args:
        dry_run: If true (default), only report stale venvs without removing them

    Returns:
        JSON with per-directory status (found/not_found) and sizes
    """
    tools_root = Path.home() / ".bitwize-music"
    results = {}

    for dirname in _LEGACY_VENV_DIRS:
        target = tools_root / dirname
        if not target.is_dir():
            results[dirname] = {"status": "not_found"}
            continue

        # Calculate size
        total_bytes = 0
        file_count = 0
        for f in target.rglob("*"):
            if f.is_file():
                file_count += 1
                total_bytes += f.stat().st_size

        size_mb = round(total_bytes / (1024 * 1024), 2)

        if dry_run:
            results[dirname] = {
                "status": "would_delete",
                "path": str(target),
                "file_count": file_count,
                "size_mb": size_mb,
            }
        else:
            shutil.rmtree(target)
            results[dirname] = {
                "status": "deleted",
                "path": str(target),
                "file_count": file_count,
                "size_mb": size_mb,
            }

    found = [d for d, r in results.items() if r["status"] != "not_found"]
    return _safe_json({
        "dry_run": dry_run,
        "stale_venvs_found": len(found),
        "results": results,
        "note": "All tools now use ~/.bitwize-music/venv/ (unified venv).",
    })


async def migrate_audio_layout(
    album_slug: str = "",
    dry_run: bool = True,
) -> str:
    """Migrate album audio from legacy root layout to originals/ subdirectory.

    Moves root-level WAV files into an originals/ subdirectory for one or all
    albums. Safe by default — dry_run=True shows what would happen without
    moving files.

    Args:
        album_slug: Specific album slug (empty string = all albums)
        dry_run: If True, only report what would be moved (default: True)

    Returns:
        JSON with per-album results and summary counts
    """
    state = _shared.cache.get_state()
    config = state.get("config", {})
    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")

    if not audio_root or not artist:
        return _safe_json({"error": "audio_root or artist_name not configured"})

    albums = state.get("albums", {})
    if album_slug:
        normalized = _normalize_slug(album_slug)
        if normalized not in albums:
            return _safe_json({"error": f"Album '{album_slug}' not found in state"})
        album_items = [(normalized, albums[normalized])]
    else:
        album_items = list(albums.items())

    results = []
    migrated_count = 0
    skipped_count = 0
    already_migrated_count = 0
    total_files = 0

    for slug, album_data in album_items:
        genre = album_data.get("genre", "")
        if not genre:
            results.append({
                "slug": slug,
                "status": "skipped",
                "files_moved": [],
                "skip_reason": "no genre in state",
            })
            skipped_count += 1
            continue

        audio_dir = Path(audio_root) / "artists" / artist / "albums" / genre / slug

        if not audio_dir.is_dir():
            results.append({
                "slug": slug,
                "status": "skipped",
                "files_moved": [],
                "skip_reason": "no audio dir",
            })
            skipped_count += 1
            continue

        originals_dir = audio_dir / "originals"
        if originals_dir.is_dir():
            results.append({
                "slug": slug,
                "status": "already_migrated",
                "files_moved": [],
                "skip_reason": "already has originals/",
            })
            already_migrated_count += 1
            continue

        wav_files = sorted(
            f for f in audio_dir.iterdir()
            if f.suffix.lower() == ".wav"
        )

        if not wav_files:
            results.append({
                "slug": slug,
                "status": "skipped",
                "files_moved": [],
                "skip_reason": "no WAV files in root",
            })
            skipped_count += 1
            continue

        moved_names = [f.name for f in wav_files]

        if not dry_run:
            originals_dir.mkdir(parents=True, exist_ok=True)
            for wav in wav_files:
                shutil.move(str(wav), str(originals_dir / wav.name))

        results.append({
            "slug": slug,
            "status": "migrated" if not dry_run else "would_migrate",
            "files_moved": moved_names,
            "skip_reason": None,
        })
        migrated_count += 1
        total_files += len(moved_names)

    return _safe_json({
        "albums": results,
        "summary": {
            "total_albums": len(album_items),
            "migrated": migrated_count,
            "skipped": skipped_count,
            "already_migrated": already_migrated_count,
            "total_files_moved": total_files,
        },
        "dry_run": dry_run,
    })


def register(mcp):
    """Register maintenance tools with the MCP server."""
    mcp.tool()(reset_mastering)
    mcp.tool()(cleanup_legacy_venvs)
    mcp.tool()(migrate_audio_layout)
