"""Album status transitions and track creation tools."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._atomic import atomic_write_text
from handlers._shared import (
    _STREAMING_PLACEHOLDER_MARKERS,
    ALBUM_COMPLETE,
    ALBUM_CONCEPT,
    ALBUM_IN_PROGRESS,
    ALBUM_RELEASED,
    ALBUM_RESEARCH_COMPLETE,
    ALBUM_SOURCES_VERIFIED,
    ALBUM_VALID_STATUSES,
    STATUS_UNKNOWN,
    TRACK_FINAL,
    TRACK_GENERATED,
    TRACK_IN_PROGRESS,
    TRACK_NOT_STARTED,
    TRACK_SOURCES_PENDING,
    TRACK_SOURCES_VERIFIED,
    _album_dir,
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _find_wav_source_dir,
    _normalize_slug,
    _safe_json,
    _slug_from_title,
)

logger = logging.getLogger(__name__)

# templates/track.md's undecided frontmatter flag: ``explicit:`` with no value
# (or the ``explicit: false`` the template shipped before #683).
_RE_TEMPLATE_EXPLICIT_FM = re.compile(r"^explicit:[ \t]*(?:false)?[ \t]*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Status transition rules — single source of truth for validation logic.
# Imported by core.py (lazy) for update_track_field.
# ---------------------------------------------------------------------------

# Valid track statuses (lowercase set for input validation)
_VALID_TRACK_STATUSES = {
    TRACK_NOT_STARTED.lower(), TRACK_SOURCES_PENDING.lower(),
    TRACK_SOURCES_VERIFIED.lower(), TRACK_IN_PROGRESS.lower(),
    TRACK_GENERATED.lower(), TRACK_FINAL.lower(),
}

# Valid album statuses (lowercase set for input validation)
_VALID_ALBUM_STATUSES = {s.lower() for s in ALBUM_VALID_STATUSES}

# Not Started → In Progress is allowed (non-documentary albums skip sources)
_VALID_TRACK_TRANSITIONS = {
    TRACK_NOT_STARTED: {TRACK_SOURCES_PENDING, TRACK_IN_PROGRESS},
    TRACK_SOURCES_PENDING: {TRACK_SOURCES_VERIFIED},
    TRACK_SOURCES_VERIFIED: {TRACK_IN_PROGRESS},
    TRACK_IN_PROGRESS: {TRACK_GENERATED},
    TRACK_GENERATED: {TRACK_FINAL},
    TRACK_FINAL: set(),  # terminal
}

# Concept → In Progress is allowed (non-documentary albums skip sources)
_VALID_ALBUM_TRANSITIONS = {
    ALBUM_CONCEPT: {ALBUM_RESEARCH_COMPLETE, ALBUM_IN_PROGRESS},
    ALBUM_RESEARCH_COMPLETE: {ALBUM_SOURCES_VERIFIED},
    ALBUM_SOURCES_VERIFIED: {ALBUM_IN_PROGRESS},
    ALBUM_IN_PROGRESS: {ALBUM_COMPLETE},
    ALBUM_COMPLETE: {ALBUM_RELEASED},
    ALBUM_RELEASED: set(),  # terminal
}

# Canonical status lookup for case-insensitive matching
_CANONICAL_TRACK_STATUS = {s.lower(): s for s in _VALID_TRACK_TRANSITIONS}
_CANONICAL_ALBUM_STATUS = {s.lower(): s for s in _VALID_ALBUM_TRANSITIONS}

# Status level mappings for album/track consistency checks
_TRACK_STATUS_LEVEL = {
    TRACK_NOT_STARTED: 0, TRACK_SOURCES_PENDING: 1, TRACK_SOURCES_VERIFIED: 2,
    TRACK_IN_PROGRESS: 3, TRACK_GENERATED: 4, TRACK_FINAL: 5,
}
_ALBUM_STATUS_LEVEL = {
    ALBUM_CONCEPT: 0, ALBUM_RESEARCH_COMPLETE: 1, ALBUM_SOURCES_VERIFIED: 2,
    ALBUM_IN_PROGRESS: 3, ALBUM_COMPLETE: 4, ALBUM_RELEASED: 5,
}


def _validate_track_transition(current: str, new: str, *, force: bool = False) -> str | None:
    """Return error message if transition is invalid, or None if OK."""
    if force:
        return None
    canonical_current = _CANONICAL_TRACK_STATUS.get(current.lower().strip(), current)
    canonical_new = _CANONICAL_TRACK_STATUS.get(new.lower().strip(), new)
    allowed = _VALID_TRACK_TRANSITIONS.get(canonical_current)
    if allowed is None:
        return None  # unknown current status — don't block (recovery)
    if canonical_new not in allowed:
        return (
            f"Invalid transition: '{canonical_current}' → '{canonical_new}'. "
            f"Allowed next: {', '.join(sorted(allowed)) or 'none (terminal)'}. "
            f"Use force=True to override."
        )
    return None


def _validate_album_transition(current: str, new: str, *, force: bool = False) -> str | None:
    """Return error message if transition is invalid, or None if OK."""
    if force:
        return None
    canonical_current = _CANONICAL_ALBUM_STATUS.get(current.lower().strip(), current)
    canonical_new = _CANONICAL_ALBUM_STATUS.get(new.lower().strip(), new)
    allowed = _VALID_ALBUM_TRANSITIONS.get(canonical_current)
    if allowed is None:
        return None  # unknown current status — don't block (recovery)
    if canonical_new not in allowed:
        return (
            f"Invalid transition: '{canonical_current}' → '{canonical_new}'. "
            f"Allowed next: {', '.join(sorted(allowed)) or 'none (terminal)'}. "
            f"Use force=True to override."
        )
    return None


def _check_album_track_consistency(album: dict[str, Any], new_status: str) -> str | None:
    """Check if album status is consistent with its tracks' statuses.

    Returns error message if inconsistent, or None if OK.

    Rules:
    - Album "In Progress" -> at least 1 track past "Not Started"
    - Album "Complete" -> ALL tracks Final (status-tracking.md; #679 item 4)
    - Album "Released" -> ALL tracks at Final
    - Levels 0-2 (Concept/Research/Sources Verified) -> no track requirements
    - Empty albums (no tracks) -> always pass
    """
    canonical = _CANONICAL_ALBUM_STATUS.get(new_status.lower().strip(), new_status)
    album_level = _ALBUM_STATUS_LEVEL.get(canonical)
    if album_level is None or album_level <= 2:
        return None  # no track requirements for early statuses

    tracks = album.get("tracks", {})
    if not tracks:
        return None  # empty albums always pass

    if canonical == ALBUM_IN_PROGRESS:
        has_active = any(
            _TRACK_STATUS_LEVEL.get(t.get("status", TRACK_NOT_STARTED), 0) > 0
            for t in tracks.values()
        )
        if not has_active:
            return (
                "Cannot set album to 'In Progress' — all tracks are still 'Not Started'. "
                "At least one track must have progressed."
            )

    elif canonical == ALBUM_COMPLETE:
        non_final = [
            slug for slug, t in tracks.items()
            if t.get("status", TRACK_NOT_STARTED) != TRACK_FINAL
        ]
        if non_final:
            return (
                f"Cannot set album to 'Complete' — {len(non_final)} track(s) not Final: "
                f"{', '.join(sorted(non_final)[:5])}. An album is Complete when all "
                f"its tracks are Final."
            )

    elif canonical == ALBUM_RELEASED:
        non_final = [
            slug for slug, t in tracks.items()
            if t.get("status", TRACK_NOT_STARTED) != TRACK_FINAL
        ]
        if non_final:
            return (
                f"Cannot set album to 'Released' — {len(non_final)} track(s) not Final: "
                f"{', '.join(sorted(non_final)[:5])}. All tracks must be Final."
            )

    return None


# ---------------------------------------------------------------------------
# Promo and release constants
# ---------------------------------------------------------------------------

# Expected promo files (from templates/promo/)
_PROMO_FILES = [
    "campaign.md", "twitter.md", "instagram.md",
    "tiktok.md", "facebook.md", "youtube.md",
]

# Album art file patterns for release readiness check
_ALBUM_ART_PATTERNS = [
    "album.png", "album.jpg", "album-art.png", "album-art.jpg",
    "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
]


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


async def update_album_status(album_slug: str, status: str, force: bool = False) -> str:
    """Update an album's status in its README.md file.

    Modifies the album details table (| **Status** | Value |) and updates
    the state cache to reflect the change.

    Args:
        album_slug: Album slug (e.g., "my-album")
        status: New status. Valid options:
            "Concept", "Research Complete", "Sources Verified",
            "In Progress", "Complete", "Released"
        force: Override transition validation (for recovery/correction only)

    Returns:
        JSON with update result or error
    """
    from tools.state.indexer import write_state
    from tools.state.parsers import parse_album_readme, sources_verified_cleared

    # Validate status
    if status.lower().strip() not in _VALID_ALBUM_STATUSES:
        return _safe_json({
            "error": (
                f"Invalid status '{status}'. Valid options: "
                + ", ".join(ALBUM_VALID_STATUSES)
            ),
        })

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    # Validate status transition
    current_status = album.get("status", ALBUM_CONCEPT)
    err = _validate_album_transition(current_status, status, force=force)
    if err:
        return _safe_json({"error": err})

    # Single state lookup for config checks below
    state = _shared.cache.get_state()

    # Documentary album gate: albums with SOURCES.md cannot skip Concept → In Progress (configurable)
    if not force:
        state_config = state.get("config", {})
        gen_cfg = state_config.get("generation", {})
        require_source_path = gen_cfg.get("require_source_path_for_documentary", True)
        if require_source_path:
            canonical_status = _CANONICAL_ALBUM_STATUS.get(status.lower().strip(), status)
            canonical_current = _CANONICAL_ALBUM_STATUS.get(
                current_status.lower().strip(), current_status)
            if canonical_current == ALBUM_CONCEPT and canonical_status == ALBUM_IN_PROGRESS:
                album_path = album.get("path", "")
                # Documentary = the album keeps research (SOURCES.md, RESEARCH.md,
                # a research/ folder), the same test create_track uses (#679 item 6).
                if album_path and _album_keeps_research(Path(album_path)):
                    return _safe_json({
                        "error": "Cannot skip to 'In Progress' — this album keeps research "
                                 "(SOURCES.md / RESEARCH.md: documentary). Transition through "
                                 "'Research Complete' → "
                                 "'Sources Verified' → 'In Progress' instead, or use "
                                 "force=True to override. To disable this check, set "
                                 "generation.require_source_path_for_documentary: false "
                                 "in config.",
                    })

    # Album/track consistency gate: album status must not exceed track statuses
    if not force:
        consistency_err = _check_album_track_consistency(album, status)
        if consistency_err:
            return _safe_json({"error": consistency_err})

    # Source verification gate: all tracks must be verified before album
    # can advance to Sources Verified
    if status.lower().strip() == ALBUM_SOURCES_VERIFIED.lower() and not force:
        tracks = album.get("tracks", {})
        # Each track's own Sources Verified field decides, not its status: a
        # verified track still at status Sources Pending counts as verified, an
        # In Progress track whose sources are pending does not (#679 item 6).
        unverified = [
            s for s, t in tracks.items()
            if not sources_verified_cleared(t.get("sources_verified", "N/A"))
        ]
        if unverified:
            return _safe_json({
                "error": (
                    f"Cannot mark album as Sources Verified — {len(unverified)} track(s) "
                    f"still unverified: {', '.join(unverified[:5])}"
                ),
            })

    # Release readiness gate: audio, mastered files, and album art must exist
    canonical_status = _CANONICAL_ALBUM_STATUS.get(status.lower().strip(), status)
    if canonical_status == ALBUM_RELEASED and not force:
        release_issues = []
        state_config = state.get("config", {})
        tracks = album.get("tracks", {})

        # Check 1: All tracks Final (explicit message, complements consistency check)
        non_final = [s for s, t in tracks.items() if t.get("status") != TRACK_FINAL]
        if non_final:
            release_issues.append(
                f"{len(non_final)} track(s) not Final: {', '.join(sorted(non_final)[:5])}"
            )

        # Check 1b: release_date set in the README frontmatter (status-tracking.md:
        # "Released — release_date set in frontmatter"; #679 item 7). The README
        # is read fresh: the date may have been set since the last rebuild.
        release_date = album.get("release_date")
        if not release_date and album.get("path"):
            readme_for_date = Path(album["path"]) / "README.md"
            if readme_for_date.is_file():
                try:
                    release_date = parse_album_readme(readme_for_date).get("release_date")
                except Exception as e:
                    logger.warning("Cannot read release_date from %s: %s", readme_for_date, e)
        if not release_date or not str(release_date).strip():
            release_issues.append(
                "No release_date in the album README frontmatter — set it with "
                "update_album_field(album_slug, \"release-date\", \"YYYY-MM-DD\") first"
            )

        # Check 2: Audio files exist
        audio_root = state_config.get("audio_root", "")
        artist_name = state_config.get("artist_name", "")
        genre = album.get("genre", "")
        # confine=False: this gate never had a resolved check, and it inspects an
        # album directory that already exists — which may be a symlink pointing
        # outside audio_root. The lexical traversal guard still applies.
        #
        # Caught rather than raised: the whole point of this block is to
        # aggregate every problem into release_issues, and a raise would replace
        # that list with one opaque error from the MCP boundary.
        try:
            audio_path: Path | None = _album_dir(
                audio_root, artist=artist_name, genre=genre, album=normalized,
                confine=False,
            )
        except ValueError as exc:
            release_issues.append(f"Could not resolve audio directory: {exc}")
            audio_path = None

        if audio_path is not None:
            if not audio_path.is_dir() or not list(_find_wav_source_dir(audio_path).glob("*.wav")):
                release_issues.append("No WAV files in audio directory")

            # Check 3: Mastered audio exists
            mastered_dir = audio_path / "mastered"
            if not mastered_dir.is_dir() or not list(mastered_dir.glob("*.wav")):
                release_issues.append("No mastered audio files")

            # Check 4: Album art exists
            if not any((audio_path / p).exists() for p in _ALBUM_ART_PATTERNS):
                release_issues.append("No album art found")

        # Check 5: Explicit flag consistency
        explicit_tracks = [
            s for s, t in tracks.items() if t.get("explicit") is True
        ]
        if explicit_tracks and not album.get("explicit", False):
            release_issues.append(
                f"Album not marked explicit but {len(explicit_tracks)} track(s) are: "
                + ", ".join(sorted(explicit_tracks)[:5])
            )

        # Check 6: Streaming lyrics ready
        streaming_issues = []
        for t_slug, t_data in tracks.items():
            track_path_str = t_data.get("path", "")
            if not track_path_str:
                streaming_issues.append(f"{t_slug}: no track path")
                continue
            try:
                tfile = Path(track_path_str).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                streaming_issues.append(f"{t_slug}: cannot read track file")
                continue
            section = _extract_markdown_section(tfile, "Streaming Lyrics")
            if not section:
                streaming_issues.append(f"{t_slug}: missing Streaming Lyrics section")
                continue
            block = _extract_code_block(section)
            if not block or not block.strip():
                streaming_issues.append(f"{t_slug}: empty Streaming Lyrics")
                continue
            if any(m.lower() in block.lower() for m in _STREAMING_PLACEHOLDER_MARKERS):
                streaming_issues.append(f"{t_slug}: placeholder content in Streaming Lyrics")
        if streaming_issues:
            release_issues.append(
                f"Streaming lyrics not ready for {len(streaming_issues)} track(s): "
                + ", ".join(streaming_issues[:5])
            )

        if release_issues:
            return _safe_json({
                "error": (
                    f"Cannot release album — {len(release_issues)} issue(s) found"
                ),
                "issues": release_issues,
                "hint": "Use force=True to override.",
            })

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    readme_path = Path(album_path) / "README.md"
    if not readme_path.exists():
        return _safe_json({"error": f"README.md not found at {readme_path}"})

    # Read file
    try:
        text = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read README.md: {e}"})

    # Find and replace the Status row
    pattern = re.compile(
        r'^(\|\s*\*\*Status\*\*\s*\|)\s*.*?\s*\|',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return _safe_json({"error": "Status field not found in album README.md table"})

    old_status = album.get("status", STATUS_UNKNOWN)
    new_row = f"{match.group(1)} {status} |"
    updated_text = text[:match.start()] + new_row + text[match.end():]

    # Write back
    try:
        atomic_write_text(readme_path, updated_text)
    except OSError as e:
        return _safe_json({"error": f"Cannot write README.md: {e}"})

    logger.info("Updated album '%s' status to '%s'", normalized, status)

    # Update cache — mutate the album dict already in state (obtained from
    # _find_album_or_error) and write the same state object; do NOT re-fetch
    # via cache.get_state() which could return a different object if the cache
    # was invalidated between calls.
    try:
        parsed = parse_album_readme(readme_path)
        album["status"] = parsed.get("status", status)
        state = _shared.cache.get_state_ref()  # same object album references into
        if state:
            write_state(state)
    except Exception as e:
        logger.warning("File written but cache update failed for album %s: %s", normalized, e)

    return _safe_json({
        "success": True,
        "album_slug": normalized,
        "old_status": old_status,
        "new_status": status,
    })


def _album_keeps_research(album_dir: Path) -> bool:
    """True when the album folder holds source or research material, under any name.

    ``SOURCES.md`` is only one spelling. Most research-backed albums keep a
    ``RESEARCH.md`` or a ``research/`` folder and no ``SOURCES.md`` at all, and
    a few use names such as ``primary-sources/``. Anything named for sources or
    research counts. A folder that cannot be listed counts too: the doubt
    should leave a track waiting for a human, not wave it through.
    """
    try:
        names = [entry.name.lower() for entry in album_dir.iterdir()]
    except OSError:
        return True
    return any("source" in name or "research" in name for name in names)


async def create_track(
    album_slug: str,
    track_number: str | int,
    title: str,
    documentary: bool = False,
) -> str:
    """Create a new track file in an album from the track template.

    Copies the track template and fills in what is already known: the track
    number and title, the album link, and the Explicit flag from the album.
    A non-documentary track gets ``Sources Verified: N/A`` only on an album
    that keeps no source or research material (no SOURCES.md, RESEARCH.md,
    research/ folder or the like); otherwise it stays ``❌ Pending`` for a
    human.
    The Lyrics Box and Style Box keep the template's placeholders, which the
    pre-generation gates treat as unwritten.

    The filename is made from the title with its punctuation removed:
    "It's a Bicycle" becomes ``04-its-a-bicycle.md``. Use the returned
    ``track_slug`` to refer to the track afterwards.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_number: Positive track number as a numeric string or int
            (e.g., "01", "2", 7). Anything else returns a structured error.
        title: Track title (e.g., "My New Track"). Needs at least one letter
            or digit.
        documentary: Keep source/quote sections and leave Sources Verified
            pending (default: strip the sections)

    Returns:
        JSON with created file path, track_slug and filename, or error
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    album_dir = Path(album_path)
    if not album_dir.is_dir():
        return _safe_json({"error": f"Album folder not found: {album_path}"})
    # Git keeps no empty folder, so an album committed before its first track
    # comes back without tracks/. It is made just before the track is written,
    # rather than the album being refused.
    tracks_dir = album_dir / "tracks"

    # Validate track_number: must be a positive integer, as an int or a
    # numeric string (#372). Check bool explicitly — it is an int subclass,
    # so True would otherwise silently become track 01.
    invalid_track_number = _safe_json({
        "error": (
            f"Invalid track_number {track_number!r}: "
            'must be a positive integer (e.g., "01", "2")'
        )
    })
    if isinstance(track_number, bool) or not isinstance(track_number, (int, str)):
        return invalid_track_number
    if isinstance(track_number, str):
        try:
            number = int(track_number.strip())
        except ValueError:
            return invalid_track_number
    else:
        number = track_number
    if number < 1:
        return invalid_track_number

    # Normalize track number to zero-padded two digits
    padded = str(number).zfill(2)

    # Build the filename from the number and the title. A title is prose, so its
    # punctuation is cleaned out here ("It's a Bicycle" -> "its-a-bicycle").
    # Names that already exist are still resolved with _normalize_slug.
    title_slug = _slug_from_title(title)
    if not title_slug:
        return _safe_json({
            "error": (
                f"Invalid title {title!r}: a track title needs at least one "
                "letter or digit to make a filename from"
            ),
        })
    filename = f"{padded}-{title_slug}.md"
    track_path = tracks_dir / filename

    # A track made before filenames were cleaned may sit under the old spelling
    # ("04-it's-a-bicycle.md"). It is the same track: do not make a second one.
    existing_names = [track_path]
    try:
        old_spelling = tracks_dir / f"{padded}-{_normalize_slug(title)}.md"
    except ValueError:
        old_spelling = track_path  # the old rule refused this title outright
    if old_spelling != track_path:
        existing_names.append(old_spelling)
    for existing in existing_names:
        if existing.exists():
            return _safe_json({
                "created": False,
                "error": f"Track file already exists: {existing}",
                "path": str(existing),
            })

    # Read template
    assert _shared.PLUGIN_ROOT is not None
    template_path = _shared.PLUGIN_ROOT / "templates" / "track.md"
    if not template_path.exists():
        return _safe_json({"error": f"Track template not found at {template_path}"})

    try:
        template = template_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track template: {e}"})

    # Fill in placeholders. An album whose README is still templates/album.md has
    # the title "[Album Title]"; linking that gave "[[Album Title]](../README.md)".
    # Until the album is named, the slug is the honest label.
    album_title = str(album.get("title") or "").strip()
    if not album_title or album_title.startswith("["):
        album_title = normalized
    # The frontmatter title is a quoted YAML scalar (title: "[Track Title]"),
    # so it must receive a properly escaped value — a raw replace of a title
    # containing a double quote would break the YAML and silently drop every
    # frontmatter field on parse (#403). json.dumps() emits a valid YAML
    # double-quoted scalar (escapes quotes/backslashes); ensure_ascii=False
    # keeps non-ASCII readable so the scalar matches the human-readable body
    # (H1, details table), which still take the raw title.
    content = template.replace(
        'title: "[Track Title]"', f"title: {json.dumps(title, ensure_ascii=False)}"
    )
    content = content.replace("[Track Title]", title)
    content = content.replace("| **Track #** | XX |", f"| **Track #** | {padded} |")
    content = content.replace("[Album Name](../README.md)", f"[{album_title}](../README.md)")
    content = content.replace("[Character/Perspective]", "—")
    content = content.replace("[Track's role in the album narrative]", "—")

    # Fill frontmatter placeholders
    content = content.replace("track_number: 0", f"track_number: {number}")
    # Explicit is decided per track, once its lyrics are checked: a fresh
    # track keeps the template's blank flag and "Yes / No" row, so the
    # pre-generation gate blocks until someone decides (#370, #683). The one
    # thing carried over is a "Yes" from an album the user marked explicit —
    # the safe direction; an album's false is the album template's default,
    # not a decision about this track.
    if album.get("explicit") is True:
        content = _RE_TEMPLATE_EXPLICIT_FM.sub("explicit: true", content, count=1)
        content = content.replace(
            "| **Explicit** | Yes / No |", "| **Explicit** | Yes |",
        )

    # A track with no source material has nothing for a human to verify. The
    # template's "❌ Pending" stays wherever there may be sources: on a
    # documentary track, and on any album that keeps research of its own.
    if not documentary and not _album_keeps_research(Path(album_path)):
        content = content.replace(
            "| **Sources Verified** | ❌ Pending |",
            "| **Sources Verified** | N/A |",
        )

    # Strip documentary sections if not needed
    if not documentary:
        # Remove from <!-- SOURCE-BASED TRACKS --> to <!-- END SOURCE SECTIONS -->
        source_start = content.find("<!-- SOURCE-BASED TRACKS")
        source_end = content.find("<!-- END SOURCE SECTIONS -->")
        if source_start != -1 and source_end != -1:
            content = content[:source_start] + content[source_end + len("<!-- END SOURCE SECTIONS -->"):]

        # Remove Documentary/True Story sections
        doc_start = content.find("<!-- DOCUMENTARY/TRUE STORY")
        doc_end = content.find("<!-- END DOCUMENTARY SECTIONS -->")
        if doc_start != -1 and doc_end != -1:
            content = content[:doc_start] + content[doc_end + len("<!-- END DOCUMENTARY SECTIONS -->"):]

    # Write file
    try:
        tracks_dir.mkdir(exist_ok=True)
        atomic_write_text(track_path, content)
    except OSError as e:
        return _safe_json({"error": f"Cannot write track file: {e}"})

    logger.info("Created track %s in album '%s'", filename, normalized)

    # Refresh state so subsequent tools (get_track, update_track_field,
    # list_tracks, ...) can find the new track without a manual rebuild_state,
    # mirroring create_album_structure. The file is already written, so a
    # rebuild failure does not undo the create: it is reported in "warnings".
    result: dict[str, Any] = {
        "created": True,
        "path": str(track_path),
        "album_slug": normalized,
        "track_slug": f"{padded}-{title_slug}",
        "filename": filename,
    }
    # A failed rebuild — returned or raised — is reported (#679 item 9).
    _rebuilt, rebuild_error = _shared.rebuild_cache()
    result["indexed"] = rebuild_error is None
    if rebuild_error is not None:
        logger.warning("Track created but cache rebuild failed: %s", rebuild_error)
        result["warnings"] = [_shared.rebuild_warning(
            f"The track file was created at {track_path}", rebuild_error,
        )]
    return _safe_json(result)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp: Any) -> None:
    """Register album status transition and track creation tools with the MCP server."""
    mcp.tool()(update_album_status)
    mcp.tool()(create_track)
