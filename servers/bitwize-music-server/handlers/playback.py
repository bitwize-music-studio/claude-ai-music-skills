"""Auditioning tools — what there is to listen to, local playback, and song pages.

Playback is local only: these tools play files that are already on disk (album
audio, or an audition copy a skill saved to the takes cache) and open Suno song
pages in the browser. They never fetch audio themselves and never call Suno.
"""

from __future__ import annotations

import logging
import re
import webbrowser
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import _safe_json
from handlers.generation import (
    _first_url,
    _load_track,
    album_audio_dir,
    clip_id_from_url,
    parse_generation_log,
)
from tools.playback import player as _player
from tools.state.parsers import _extract_table_value

logger = logging.getLogger(__name__)

# Only Suno song pages may be opened: the page for a clip id, or a legacy share link.
_SONG_PAGE_RE = re.compile(
    r"https://suno\.com/(?:song/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
    r"|s/[A-Za-z0-9]+)"
)
_MAX_PAGES = 4

# Newest first: what a finished track should play by default.
_STAGES = ("mastered", "polished", "original")


def _local_stages(album_slug: str, album: dict[str, Any], track_slug: str) -> dict[str, str | None]:
    """This track's audio file in each stage directory, where one exists."""
    stages: dict[str, str | None] = {"original": None, "polished": None, "mastered": None}
    audio_dir, error = album_audio_dir(album_slug, album)
    if error or audio_dir is None:
        return stages
    originals = audio_dir / "originals"
    directories = {
        "original": originals if originals.is_dir() else audio_dir,
        "polished": audio_dir / "polished",
        "mastered": audio_dir / "mastered",
    }
    for stage, directory in directories.items():
        found = _player.find_track_audio(directory, track_slug)
        stages[stage] = str(found) if found else None
    return stages


async def get_listen_plan(album_slug: str, track_slug: str) -> str:
    """List what can be listened to for a track, and what to play by default.

    Read-only, and it never calls Suno. Takes come from the track's Generation
    Log; local files from the album's audio directory.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")

    Returns:
        JSON with:
            takes: Generation Log rows that link to Suno — row, date, model, url,
                clip_id (null for a legacy share link, which can only be opened
                in the browser), rating, approved, is_keeper, cache_path (where
                the audition copy belongs) and cached (whether it is there)
            local: {original, polished, mastered} — file path or null
            default: {"kind": "takes", "rows": [...]} for takes awaiting a
                decision (the newest two), {"kind": "local", "stage", "path"} for
                an approved track's newest file, or {"kind": "none"}
            mode: "terminal" or "browser" (config generation.listen_mode)
            confirm_download: whether to ask before a terminal audition spends a
                Suno download credit (config generation.listen_confirm_download)
            player: the installed audio player, or null
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]
    track: dict[str, Any] = ctx["track"]

    keeper_url = _first_url((_extract_table_value(text, "Suno Link") or "").strip())
    keeper_clip = clip_id_from_url(keeper_url) if keeper_url else None
    cache = _player.takes_cache_dir()

    takes: list[dict[str, Any]] = []
    for take in parse_generation_log(text):
        url = take["url"]
        if not url:
            continue  # nothing to play or open (e.g. a failed attempt)
        clip_id = take["clip_id"]
        cache_path = cache / f"{clip_id}.mp3" if clip_id else None
        takes.append({
            "row": take["row"],
            "date": take["date"],
            "model": take["model"],
            "url": url,
            "clip_id": clip_id,
            "rating": take["rating"],
            "approved": take["approved"],
            "is_keeper": bool(
                (clip_id and clip_id == keeper_clip) or (keeper_url and url == keeper_url)
            ),
            "cache_path": str(cache_path) if cache_path else None,
            "cached": bool(cache_path and cache_path.is_file()),
        })

    local = _local_stages(ctx["album_slug"], ctx["album"], ctx["track_slug"])

    approved = [take for take in takes if take["approved"]]
    pending = [take for take in takes if not take["approved"]]
    newest_stage = next((stage for stage in _STAGES if local[stage]), None)
    default: dict[str, Any]
    if pending and not approved:
        default = {"kind": "takes", "rows": [take["row"] for take in pending[-2:]]}
    elif newest_stage:
        default = {"kind": "local", "stage": newest_stage, "path": local[newest_stage]}
    elif approved:
        keepers = [take for take in approved if take["is_keeper"]] or approved[-1:]
        default = {"kind": "takes", "rows": [take["row"] for take in keepers]}
    else:
        default = {"kind": "none"}

    generation = _shared.cache.get_state().get("config", {}).get("generation", {})
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "title": track.get("title", ctx["track_slug"]),
        "track_status": track.get("status", ""),
        "takes": takes,
        "local": local,
        "default": default,
        "mode": generation.get("listen_mode", "terminal"),
        "confirm_download": generation.get("listen_confirm_download", True),
        "player": _player.find_player(),
    })


async def play_audio(path: str, start_s: float = 0.0, length_s: float = 0.0) -> str:
    """Play a local audio file through the computer's speakers, in the background.

    Returns as soon as the player has started; use stop_audio to stop it.
    Starting a new playback stops the current one. Only files under the audio
    root or the takes cache can be played — never a URL.

    Args:
        path: Absolute path to an audio file (wav, mp3, flac, m4a, ogg, aiff)
        start_s: Where to start, in seconds (needs mpv or ffplay)
        length_s: How long to play, in seconds; 0 plays to the end

    Returns:
        JSON with playing, player, pid, path, start_s, duration_s (file length,
        or null) and command (to run the player by hand), or playing: false
        with an error
    """
    config = _shared.cache.get_state().get("config", {})
    roots: list[Path] = []
    audio_root = config.get("audio_root", "")
    if audio_root:
        roots.append(Path(audio_root))
    roots.append(_player.takes_cache_dir())

    try:
        result = _player.play(
            path, roots, start_s=start_s, length_s=length_s if length_s > 0 else None,
        )
    except _player.PlaybackError as e:
        return _safe_json({"playing": False, "error": str(e)})
    except OSError as e:
        return _safe_json({"playing": False, "error": f"Could not start the player: {e}"})

    result["duration_s"] = _player.audio_duration(Path(str(result.get("path", path))))
    return _safe_json(result)


async def stop_audio() -> str:
    """Stop the audio started by play_audio.

    Returns:
        JSON with stopped, and when something was playing: path and position_s
        (where it had reached — pass it to play_audio as start_s to resume)
    """
    return _safe_json(_player.stop())


async def open_song_page(urls: list[str]) -> str:
    """Open Suno song pages in the default web browser, one tab each.

    Listening on the song page is free and unlimited. Accepts only
    https://suno.com/song/<clip id> and https://suno.com/s/<share id> links;
    if any URL is something else, nothing is opened.

    Args:
        urls: One to four Suno song page URLs

    Returns:
        JSON with opened and failed URL lists (failed when no browser could be
        launched — give those links to the user instead), or an error
    """
    if not urls:
        return _safe_json({"error": "No URLs given"})
    if len(urls) > _MAX_PAGES:
        return _safe_json({"error": f"Open at most {_MAX_PAGES} song pages at once"})
    for url in urls:
        if not _SONG_PAGE_RE.fullmatch(str(url)):
            return _safe_json({
                "error": f"Not a Suno song page: '{url}' — nothing was opened",
            })

    opened: list[str] = []
    failed: list[str] = []
    for url in urls:
        try:
            launched = webbrowser.open_new_tab(url)
        except webbrowser.Error as e:
            logger.warning("Could not open %s in a browser: %s", url, e)
            launched = False
        (opened if launched else failed).append(url)

    result: dict[str, Any] = {"opened": opened, "failed": failed}
    if failed:
        result["hint"] = "No browser could be launched here — open these links by hand"
    return _safe_json(result)


def register(mcp: Any) -> None:
    """Register auditioning tools with the MCP server."""
    mcp.tool()(get_listen_plan)
    mcp.tool()(play_audio)
    mcp.tool()(stop_audio)
    mcp.tool()(open_song_page)
