"""Suno release housekeeping — an album's approved takes as a playlist on suno.com.

The plugin's server never talks to Suno. These tools tell a skill which songs
belong in the album's playlist (each track's approved take, in track order) and
record the playlist in the album README, so a later run updates the same
playlist instead of making another. Creating the playlist, and publishing songs,
are Suno tool calls the skill makes — and only when the user asks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from handlers._shared import _find_album_or_error, _safe_json
from handlers.generation import keeper_clip, record_album_ref

logger = logging.getLogger(__name__)

_PLAYLIST_KEY = "suno_playlist"
_PLAYLIST_COMMENT = (
    "# Suno playlist of this album's approved takes; /bitwize-music:release-director fills it in"
)
_PLAYLIST_BATCH = 100  # playlists-add-clips takes at most 100 songs per call
_TEMPLATE_ALBUM_TITLES = frozenset({"", "[Album Title]"})


def _playlist_url(playlist_id: str) -> str:
    return f"https://suno.com/playlist/{playlist_id}"


def _album_playlist(album: dict[str, Any]) -> dict[str, str] | None:
    """The album's recorded Suno playlist, ``{"id", "name", "url"}``, or None."""
    playlist = album.get(_PLAYLIST_KEY)
    if not isinstance(playlist, dict) or not playlist.get("id"):
        return None
    playlist_id = str(playlist["id"])
    return {"id": playlist_id, "name": str(playlist.get("name") or ""), "url": _playlist_url(playlist_id)}


async def get_suno_release_plan(album_slug: str) -> str:
    """The songs that belong in an album's Suno playlist, and what is still missing.

    /bitwize-music:release-director reads this to build a playlist of the
    album's approved takes on suno.com, or to publish them — both only when the
    user asks. Each track contributes its keeper: the take its Suno Link names,
    or the one Generation Log row marked ✓ when the link is unset.

    Args:
        album_slug: Album slug

    Returns:
        JSON with found, album_slug, album_title, album_status,
        playlist ({id, name, url} when one is recorded, else null),
        suggested_name (the album title, or the slug while the title is the
        template's placeholder), keepers ([{track_slug, title, clip_id, url}]
        in track order), clip_ids (the same ids, in order), batches (those ids
        in groups of 100, the limit of playlists-add-clips), missing
        ([{track_slug, title, reason}] — reason is no_keeper, keeper_ambiguous,
        legacy_link, no_path or unreadable) and ready (every track has a keeper)
    """
    album_slug, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    keepers: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    for track_slug, track in sorted((album.get("tracks") or {}).items()):
        title = str(track.get("title") or track_slug)
        path = track.get("path") or ""
        if not path:
            missing.append({"track_slug": track_slug, "title": title, "reason": "no_path"})
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Cannot read %s for the release plan: %s", path, e)
            missing.append({"track_slug": track_slug, "title": title, "reason": "unreadable"})
            continue
        clip_id, _, _, problem = keeper_clip(text)
        if clip_id is None:
            reason = problem["code"] if problem else "no_keeper"
            missing.append({"track_slug": track_slug, "title": title, "reason": reason})
            continue
        keepers.append({
            "track_slug": track_slug,
            "title": title,
            "clip_id": clip_id,
            "url": f"https://suno.com/song/{clip_id}",
        })

    title = str(album.get("title") or "").strip()
    clip_ids = [keeper["clip_id"] for keeper in keepers]
    return _safe_json({
        "found": True,
        "album_slug": album_slug,
        "album_title": title,
        "album_status": album.get("status", ""),
        "playlist": _album_playlist(album),
        "suggested_name": album_slug if title in _TEMPLATE_ALBUM_TITLES else title,
        "keepers": keepers,
        "clip_ids": clip_ids,
        "batches": [
            clip_ids[i:i + _PLAYLIST_BATCH] for i in range(0, len(clip_ids), _PLAYLIST_BATCH)
        ],
        "missing": missing,
        "ready": bool(keepers) and not missing,
    })


async def set_album_playlist(album_slug: str, playlist_id: str, name: str) -> str:
    """Record the Suno playlist that holds an album's approved takes.

    Writes the suno_playlist block in the album README's frontmatter (keeping
    its comments) and refreshes the state cache, so get_suno_release_plan
    reports the playlist and a later release run updates it instead of making
    another. Call it right after playlists-create, or to point the album at a
    playlist that already exists.

    Args:
        album_slug: Album slug
        playlist_id: The playlist's id from playlists-create or playlists-list
        name: The playlist's name, for people reading the README

    Returns:
        JSON with updated, path and playlist ({id, name, url}), or an error
    """
    recorded, error = record_album_ref(
        album_slug, playlist_id, name,
        key=_PLAYLIST_KEY, comment=_PLAYLIST_COMMENT, noun="playlist",
    )
    if error:
        return error
    assert recorded is not None
    ref = recorded["ref"]
    return _safe_json({
        "updated": True,
        "path": recorded["path"],
        "playlist": {**ref, "url": _playlist_url(ref["id"])},
    })


def register(mcp: Any) -> None:
    """Register the Suno release tools with the MCP server."""
    mcp.tool()(get_suno_release_plan)
    mcp.tool()(set_album_playlist)
