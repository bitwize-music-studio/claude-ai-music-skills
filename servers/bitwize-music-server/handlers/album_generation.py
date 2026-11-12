"""Album-wide generation — which tracks can be generated now, and what it would cost.

/bitwize-music:generate works one track at a time. For a whole album the skill
needs one picture before it asks for one go-ahead: the tracks that pass the
pre-generation gates and map to a Suno request, the ones that are blocked and
why, the ones that already have takes, and the credits the batch would spend.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import _find_album_or_error, _safe_json
from handlers.gates import _check_pre_gen_gates_for_track
from handlers.generation import (
    _album_workspace,
    get_generation_request,
    parse_generation_log,
)
from handlers.text_analysis import _load_artist_blocklist

logger = logging.getLogger(__name__)

# One audio-create call makes two takes for 10 song credits (measured), and
# so do audio-covers-create and speech-create. Max Mode costs a multiple of that;
# suno.com charges double.
_CREDITS_PER_CALL = 10
_MAX_MODE_FACTOR = 2
_TAKES_PER_CALL = 2
_DONE_STATUSES = frozenset({"Generated", "Final"})
_TEMPLATE_ALBUM_TITLES = frozenset({"", "[Album Title]"})
_GATES_SHOWN = 3


async def _plan_track(
    album_slug: str, track_slug: str, track: dict[str, Any],
    blocklist: list[dict[str, str]], max_lyric_words: int,
) -> dict[str, Any]:
    """One track's place in the batch: generate, blocked (with the reason) or skip."""
    entry: dict[str, Any] = {
        "track_slug": track_slug,
        "title": track.get("title", track_slug),
        "status": track.get("status", ""),
        "action": "generate",
        "reason": "",
        "kind": "",
        "max_mode": False,
        "credits": 0,
    }

    text: str | None = None
    path = track.get("path") or ""
    if path:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Cannot read %s for the generation plan: %s", path, e)

    if text and any(take["url"] for take in parse_generation_log(text)):
        return {**entry, "action": "skip", "reason": "already has takes"}
    if entry["status"] in _DONE_STATUSES:
        return {**entry, "action": "skip", "reason": f"status is {entry['status']}"}
    if text is None:
        return {**entry, "action": "blocked", "reason": "track file cannot be read"}

    blocking, _, gates = _check_pre_gen_gates_for_track(
        track, text, blocklist, max_lyric_words=max_lyric_words,
    )
    if blocking:
        failed = [g["gate"] for g in gates if g.get("severity") == "BLOCKING"]
        more = f" and {len(failed) - _GATES_SHOWN} more" if len(failed) > _GATES_SHOWN else ""
        return {
            **entry, "action": "blocked",
            "reason": "gates: " + ", ".join(failed[:_GATES_SHOWN]) + more,
        }

    built = json.loads(await get_generation_request(album_slug, track_slug))
    if not built.get("supported"):
        details = [p["detail"] for p in built.get("problems", []) if p["severity"] == "blocking"]
        return {
            **entry, "action": "blocked",
            "reason": details[0] if details else built.get("error", "no request could be built"),
        }

    max_mode = bool(built["request"].get("max_mode"))
    return {
        **entry,
        "kind": built["kind"],
        "max_mode": max_mode,
        "credits": _CREDITS_PER_CALL * (_MAX_MODE_FACTOR if max_mode else 1),
    }


async def get_album_generation_plan(album_slug: str) -> str:
    """Which tracks of an album can be generated now, and what the batch would cost.

    /bitwize-music:generate uses this for a whole album: show the plan, get one
    go-ahead that names the number of calls and the credits, then generate the
    listed tracks one after another. A track is generated when it passes the
    pre-generation gates and get_generation_request can build its request;
    tracks that already have takes, or are Generated or Final, are skipped.

    Args:
        album_slug: Album slug

    Returns:
        JSON with found, album_slug, album_title, tracks ([{track_slug, title,
        status, action: generate|blocked|skip, reason, kind (for a track to
        generate: song, cover or speech — see get_generation_request),
        max_mode, credits}]),
        generate / blocked / skipped (track slugs), calls (one per track to
        generate), takes (two per call), estimated_credits (10 per call, 20
        with Max Mode — an estimate; the account balance is the truth),
        workspace ({id, name} or null) and suggested_workspace_name
    """
    album_slug, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    generation = _shared.cache.get_state().get("config", {}).get("generation", {}) or {}
    blocklist = _load_artist_blocklist()
    max_lyric_words = generation.get("max_lyric_words", 800)

    tracks = [
        await _plan_track(album_slug, slug, track, blocklist, max_lyric_words)
        for slug, track in sorted((album.get("tracks") or {}).items())
    ]
    to_generate = [t for t in tracks if t["action"] == "generate"]
    title = str(album.get("title") or "").strip()
    return _safe_json({
        "found": True,
        "album_slug": album_slug,
        "album_title": title,
        "tracks": tracks,
        "generate": [t["track_slug"] for t in to_generate],
        "blocked": [t["track_slug"] for t in tracks if t["action"] == "blocked"],
        "skipped": [t["track_slug"] for t in tracks if t["action"] == "skip"],
        "calls": len(to_generate),
        "takes": len(to_generate) * _TAKES_PER_CALL,
        "estimated_credits": sum(t["credits"] for t in to_generate),
        "workspace": _album_workspace(album),
        "suggested_workspace_name": album_slug if title in _TEMPLATE_ALBUM_TITLES else title,
    })


def register(mcp: Any) -> None:
    """Register the album generation plan with the MCP server."""
    mcp.tool()(get_album_generation_plan)
