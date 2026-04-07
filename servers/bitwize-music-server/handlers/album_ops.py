"""Album operation tools — full album query, structure validation, album creation."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import (
    _CODE_BLOCK_SECTIONS,
    _GENRE_ALIASES,
    _SECTION_NAMES,
    _get_valid_genres,
    STATUS_UNKNOWN,
    TRACK_COMPLETED_STATUSES,
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _find_wav_source_dir,
    _normalize_slug,
    _safe_json,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


async def get_album_full(
    album_slug: str,
    include_sections: str = "",
    track_slugs: str = "",
    summary_only: bool = False,
) -> str:
    """Get full album data including track content sections in one call.

    Combines find_album + extract_section for all tracks, eliminating N+1
    queries. Without include_sections, returns the same as find_album.

    Args:
        album_slug: Album slug (e.g., "my-album")
        include_sections: Comma-separated section names to extract from each track
                         (e.g., "lyrics,style,pronunciation,streaming")
                         Empty = metadata only (no file reads)
        track_slugs: Comma-separated track slugs to include (empty = all tracks,
                    default). Only matching tracks are returned.
        summary_only: When True, return album metadata + track list with
                     statuses only (no sections, no paths). Overrides
                     include_sections. (default False)

    Returns:
        JSON with album data + embedded track sections
    """
    state = _shared.cache.get_state()
    albums = state.get("albums", {})
    normalized = _normalize_slug(album_slug)

    # Try exact then fuzzy match
    album = albums.get(normalized)
    matched_slug = normalized
    if not album:
        matches = {s: d for s, d in albums.items() if normalized in s or s in normalized}
        if len(matches) == 1:
            matched_slug = next(iter(matches))
            album = matches[matched_slug]
        elif len(matches) > 1:
            return _safe_json({
                "found": False,
                "error": f"Multiple albums match '{album_slug}': {', '.join(matches.keys())}",
            })
        else:
            return _safe_json({
                "found": False,
                "error": f"Album '{album_slug}' not found",
                "available_albums": list(albums.keys()),
            })

    result: dict[str, Any] = {
        "found": True,
        "slug": matched_slug,
        "album": {
            "title": album.get("title", matched_slug),
            "status": album.get("status", STATUS_UNKNOWN),
            "genre": album.get("genre", ""),
            "path": album.get("path", ""),
            "track_count": album.get("track_count", 0),
            "tracks_completed": album.get("tracks_completed", 0),
        },
        "tracks": {},
    }

    # Parse track slug filter
    track_filter: set[str] = set()
    if track_slugs:
        track_filter = {_normalize_slug(s) for s in track_slugs.split(",") if s.strip()}

    # Parse requested sections (ignored if summary_only)
    sections: list[str] = []
    if include_sections and not summary_only:
        sections = [s.strip().lower() for s in include_sections.split(",") if s.strip()]

    tracks = album.get("tracks", {})
    for track_slug_key, track in sorted(tracks.items()):
        # Apply track filter
        if track_filter and track_slug_key not in track_filter:
            continue

        if summary_only:
            track_entry: dict[str, Any] = {
                "title": track.get("title", track_slug_key),
                "status": track.get("status", STATUS_UNKNOWN),
                "explicit": track.get("explicit", False),
                "has_suno_link": track.get("has_suno_link", False),
                "sources_verified": track.get("sources_verified", "N/A"),
            }
        else:
            track_entry = {
                "title": track.get("title", track_slug_key),
                "status": track.get("status", STATUS_UNKNOWN),
                "explicit": track.get("explicit", False),
                "has_suno_link": track.get("has_suno_link", False),
                "sources_verified": track.get("sources_verified", "N/A"),
                "path": track.get("path", ""),
            }

            # Read sections from disk if requested
            if sections and track.get("path"):
                try:
                    file_text = Path(track["path"]).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as e:
                    logger.warning("Cannot read track file %s: %s", track["path"], e)
                    file_text = None

                if file_text:
                    track_entry["sections"] = {}
                    for sec in sections:
                        heading = _SECTION_NAMES.get(sec)
                        if not heading:
                            continue
                        sec_content = _extract_markdown_section(file_text, heading)
                        if sec_content is not None:
                            # For code-block sections, extract just the code block
                            if heading in _CODE_BLOCK_SECTIONS:
                                code = _extract_code_block(sec_content)
                                if code is not None:
                                    sec_content = code
                            track_entry["sections"][sec] = sec_content

        result["tracks"][track_slug_key] = track_entry

    return _safe_json(result)


async def validate_album_structure(
    album_slug: str,
    checks: str = "all",
) -> str:
    """Run structural validation on an album's files and directories.

    Checks directory structure, required files, audio placement, and track
    content integrity. Returns structured results with actionable fix commands.

    Args:
        album_slug: Album slug (e.g., "my-album")
        checks: Comma-separated checks to run: "structure", "audio", "art",
                "tracks", "all" (default)

    Returns:
        JSON with {passed, failed, warnings, skipped, issues[], checks[]}
    """
    state = _shared.cache.get_state()
    config = state.get("config", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    # Parse check types
    check_set = set()
    for c in checks.split(","):
        c = c.strip().lower()
        if c == "all":
            check_set = {"structure", "audio", "art", "tracks"}
            break
        if c in ("structure", "audio", "art", "tracks"):
            check_set.add(c)
    if not check_set:
        check_set = {"structure", "audio", "art", "tracks"}

    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")
    album_path = album.get("path", "")
    genre = album.get("genre", "")
    audio_path = str(Path(audio_root) / "artists" / artist / "albums" / genre / normalized)

    passed = 0
    failed = 0
    warnings = 0
    skipped = 0
    results = []
    issues = []

    def _pass(category: str, msg: str) -> None:
        nonlocal passed
        passed += 1
        results.append({"status": "PASS", "category": category, "message": msg})

    def _fail(category: str, msg: str, fix: str = "") -> None:
        nonlocal failed
        failed += 1
        results.append({"status": "FAIL", "category": category, "message": msg})
        if fix:
            issues.append({"message": msg, "fix": fix})

    def _warn(category: str, msg: str) -> None:
        nonlocal warnings
        warnings += 1
        results.append({"status": "WARN", "category": category, "message": msg})

    def _skip(category: str, msg: str) -> None:
        nonlocal skipped
        skipped += 1
        results.append({"status": "SKIP", "category": category, "message": msg})

    # --- Structure checks ---
    if "structure" in check_set:
        ap = Path(album_path)
        if ap.is_dir():
            _pass("structure", f"Album directory exists: {album_path}")
        else:
            _fail("structure", f"Album directory missing: {album_path}")

        readme = ap / "README.md"
        if readme.exists():
            _pass("structure", "README.md exists")
        else:
            _fail("structure", "README.md missing")

        tracks_dir = ap / "tracks"
        if tracks_dir.is_dir():
            _pass("structure", "tracks/ directory exists")
            track_files = list(tracks_dir.glob("*.md"))
            if track_files:
                _pass("structure", f"{len(track_files)} track files found")
            else:
                _warn("structure", "No track files found in tracks/")
        else:
            _fail("structure", "tracks/ directory missing",
                  fix=f"mkdir -p {album_path}/tracks")

    # --- Audio checks ---
    if "audio" in check_set:
        audio_p = Path(audio_path)
        wrong_path = Path(audio_root) / artist / normalized  # old flat structure

        if audio_p.is_dir():
            _pass("audio", f"Audio directory exists: {audio_path}")
            wav_files = list(_find_wav_source_dir(audio_p).glob("*.wav"))
            if wav_files:
                _pass("audio", f"{len(wav_files)} WAV files found")
            else:
                _skip("audio", "No audio files yet")

            mastered = audio_p / "mastered"
            if mastered.is_dir():
                _pass("audio", "mastered/ directory exists")
            else:
                _skip("audio", "Not mastered yet")
        elif wrong_path.is_dir():
            _fail("audio", "Audio in wrong location (missing artist folder)",
                  fix=f"mv {wrong_path} {audio_path}")
        else:
            _skip("audio", "No audio directory yet")

    # --- Art checks ---
    if "art" in check_set:
        audio_p = Path(audio_path)
        ap = Path(album_path)

        if (audio_p / "album.png").exists():
            _pass("art", "album.png in audio folder")
        else:
            _skip("art", "No album art in audio folder yet")

        art_files = list(ap.glob("album-art.*"))
        if art_files:
            _pass("art", f"Album art in content folder: {art_files[0].name}")
        else:
            _skip("art", "No album art in content folder yet")

    # --- Track content checks ---
    if "tracks" in check_set:
        tracks = album.get("tracks", {})
        for t_slug, t_data in sorted(tracks.items()):
            status = t_data.get("status", STATUS_UNKNOWN)
            has_link = t_data.get("has_suno_link", False)
            sources = t_data.get("sources_verified", "N/A")

            track_issues = []
            if status in TRACK_COMPLETED_STATUSES and not has_link:
                track_issues.append("Suno Link missing")
            if sources.lower() == "pending":
                track_issues.append("Sources not verified")

            if track_issues:
                _warn("tracks", f"{t_slug}: Status={status}, issues: {', '.join(track_issues)}")
            else:
                _pass("tracks", f"{t_slug}: Status={status}")

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "skipped": skipped,
        "total": passed + failed + warnings + skipped,
        "checks": results,
        "issues": issues,
    })


async def create_album_structure(
    album_slug: str,
    genre: str,
    documentary: bool = False,
) -> str:
    """Create a new album directory with templates.

    Creates the content directory structure and copies templates. Does NOT
    create audio or documents directories (those are created when needed).

    Args:
        album_slug: Album name as slug (e.g., "my-new-album")
        genre: Primary genre (e.g., "hip-hop", "electronic", "country", "folk", "rock")
        documentary: Whether to include research/sources templates

    Returns:
        JSON with {created: bool, path: str, files: [...]}
    """
    state = _shared.cache.get_state()
    config = state.get("config", {})

    if not config:
        return _safe_json({"error": "No config in state. Run rebuild_state first."})

    content_root = config.get("content_root", "")
    artist = config.get("artist_name", "")

    if not content_root or not artist:
        return _safe_json({"error": "content_root or artist_name not configured"})

    normalized = _normalize_slug(album_slug)
    genre_slug = _normalize_slug(genre)
    genre_slug = _GENRE_ALIASES.get(genre_slug, genre_slug)

    gen_cfg = config.get("generation", {})
    additional = set(gen_cfg.get("additional_genres", []))
    all_genres = _get_valid_genres() | additional
    if genre_slug not in all_genres:
        return _safe_json({
            "error": f"Invalid genre '{genre}'. Valid genres: {', '.join(sorted(all_genres))}",
            "hint": "Use a primary genre, or add custom genres via "
                    "generation.additional_genres in config.",
        })

    album_path = Path(content_root) / "artists" / artist / "albums" / genre_slug / normalized
    tracks_path = album_path / "tracks"
    assert _shared.PLUGIN_ROOT is not None
    templates_path = _shared.PLUGIN_ROOT / "templates"

    # Check if already exists
    if album_path.exists():
        return _safe_json({
            "created": False,
            "error": f"Album directory already exists: {album_path}",
            "path": str(album_path),
        })

    # Create directories
    try:
        tracks_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return _safe_json({"error": f"Cannot create directory: {e}"})

    # Copy templates
    created_files = []

    # Album README (always)
    album_template = templates_path / "album.md"
    readme_dest = album_path / "README.md"
    if album_template.exists():
        shutil.copy2(str(album_template), str(readme_dest))
        created_files.append("README.md")

    # Documentary templates
    if documentary:
        research_template = templates_path / "research.md"
        sources_template = templates_path / "sources.md"

        if research_template.exists():
            shutil.copy2(str(research_template), str(album_path / "RESEARCH.md"))
            created_files.append("RESEARCH.md")
        if sources_template.exists():
            shutil.copy2(str(sources_template), str(album_path / "SOURCES.md"))
            created_files.append("SOURCES.md")

    created_files.append("tracks/")

    # Rebuild state so subsequent tools (e.g., create_track) can find the new album
    _shared.cache.rebuild()

    return _safe_json({
        "created": True,
        "path": str(album_path),
        "tracks_path": str(tracks_path),
        "genre": genre_slug,
        "documentary": documentary,
        "files": created_files,
    })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp: Any) -> None:
    """Register album operation tools with the MCP server."""
    mcp.tool()(get_album_full)
    mcp.tool()(validate_album_structure)
    mcp.tool()(create_album_structure)
