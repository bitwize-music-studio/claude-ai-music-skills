"""Suno Studio in the browser: the route for importing a keeper once downloads run out.

``/bitwize-music:import-audio --from-suno`` downloads a keeper's WAV through
Suno's MCP server, which spends one of the account's download credits. With
none left, a Premier account can still take the WAV from Suno Studio: the user
selects the song's whole waveform in Studio's editor and clicks Download .WAV.
These tools open the keeper there, in a real browser, and find the finished
file in ~/Downloads. Neither calls Suno, and neither moves the file: the skill
asks the user before importing it.

Studio comes with Premier only (suno.com/pricing). iTerm2's browser can't be
used: Studio hands the WAV over as a blob: URL, which it can't save.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import _safe_json
from handlers.generation import get_suno_import_plan
from tools.playback import browser as _browser

logger = logging.getLogger(__name__)

# The plan Studio comes with: Suno's pricing page lists "Access to Suno Studio"
# under Premier, and "Not included" for Free and Pro.
STUDIO_PLAN = "premier"

# create_new=1 starts a new Studio project on every open. It is the form known
# to work; whether leaving it out reuses a project hasn't been checked.
_STUDIO_URL = "https://suno.com/studio?for_clip_id={clip_id}&create_new=1"
_STUDIO_URL_RE = re.compile(
    r"https://suno\.com/studio\?for_clip_id="
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}&create_new=1"
)
_NEXT_STEP = (
    "In Studio's editor, select the song's whole waveform, then click Download .WAV. "
    "The file goes to your Downloads folder."
)

DOWNLOADS_DIR = Path.home() / "Downloads"
# What browsers name a download still being written: Firefox, Chrome, Safari.
_PARTIAL_SUFFIXES = (".part", ".crdownload", ".download")
POLL_SECONDS = 2.0
# A file left alone this long, with no partial download beside it, is finished.
_SETTLED_SECONDS = 2.0
_MAX_WAIT_SECONDS = 600
# How far the file's length may stray from the song's before it's flagged.
_LENGTH_TOLERANCE = 0.5
_sleep = asyncio.sleep


def _configured_browser() -> str:
    state = _shared.cache.get_state() or {}
    generation = (state.get("config") or {}).get("generation") or {}
    return str(generation.get("studio_browser") or "")


async def open_in_studio(
    album_slug: str, track_slug: str, plan: str, browser: str = "", version: str = "",
) -> str:
    """Open a track's keeper in Suno Studio in the browser, to download its WAV there.

    The route for /bitwize-music:import-audio --from-suno once the account's
    download credits run out. Studio comes with the Premier plan only, so pass
    the plan name account-usage reports (suno_account.plan.name); any other
    plan is refused and nothing opens. The page opens in the browser named by
    `browser`, else config generation.studio_browser, else the system's
    default: either can be "default", an app name or a path to one. iTerm2 is refused: Studio hands the WAV over as a blob: URL,
    which iTerm2's browser can't save. Nothing is downloaded or charged here.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        plan: The Suno plan name from account-usage, e.g. "Premier Plan"
        browser: A browser for this run only: "default", an app name
            ("Firefox", "Google Chrome", "Safari") or a path to one;
            overrides generation.studio_browser
        version: "" for the keeper, or "instrumental" for that version of the
            track, as in get_suno_import_plan

    Returns:
        JSON with url, clip_id, opened_at (ISO time: pass it to
        find_studio_download), browser (the app used, "default", or null when
        none could open: give the user the url), note (why the browser named
        wasn't used), hint, next (what the user does in Studio) and wav (where
        the file goes, from get_suno_import_plan); or an error
    """
    if STUDIO_PLAN not in (plan or "").casefold():
        shown = (plan or "").strip() or "unknown"
        return _safe_json({
            "error": (
                "Suno Studio comes with the Premier plan only (suno.com/pricing); "
                f"this account's plan is {shown!r}. Nothing was opened."
            ),
            "plan": plan,
        })
    import_plan = json.loads(await get_suno_import_plan(album_slug, track_slug, version))
    if import_plan.get("error"):
        return _safe_json(import_plan)
    clip_id = import_plan.get("clip_id")
    if not clip_id:
        return _safe_json({
            "error": "This track has no keeper clip to open in Studio. Nothing was opened.",
            "problems": import_plan.get("problems") or [],
        })
    url = _STUDIO_URL.format(clip_id=str(clip_id).lower())
    if not _STUDIO_URL_RE.fullmatch(url):
        return _safe_json({"error": f"Not a Suno clip id: {clip_id!r}. Nothing was opened."})

    app = (browser or _configured_browser()).strip()
    if _browser.is_iterm(app):
        return _safe_json({"error": (
            f"Suno Studio can't be used in {app}: Studio hands the WAV over as a blob: URL, "
            "which iTerm2's browser can't save ('Plug-in handled load'). Name another "
            "browser, or leave generation.studio_browser unset for the default."
        )})

    opened_at = datetime.now(UTC)
    used, note = _browser.open_url(url, app)
    result: dict[str, Any] = {
        "url": url,
        "clip_id": clip_id,
        "opened_at": opened_at.isoformat(),
        "browser": used,
        "next": _NEXT_STEP,
        "wav": import_plan.get("wav"),
    }
    if note:
        result["note"] = note
    if used is None:
        result["hint"] = "No browser could be launched here: open the url by hand"
    return _safe_json(result)


def _parse_time(value: str) -> float:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.timestamp()


def _scan(start: float) -> tuple[list[Path], list[Path]]:
    """Finished WAVs, and downloads still being written, in Downloads since start."""
    now = time.time()
    done: list[Path] = []
    partial: list[Path] = []
    try:
        entries = list(DOWNLOADS_DIR.iterdir())
    except OSError:
        return [], []
    for entry in entries:
        try:
            info = entry.stat()
        except OSError:
            continue
        if info.st_mtime < start - 1:  # a second's grace for coarse file-system clocks
            continue
        name = entry.name.lower()
        if name.endswith(_PARTIAL_SUFFIXES):
            partial.append(entry)
        elif (entry.is_file() and name.endswith(".wav") and info.st_size > 0
              and now - info.st_mtime >= _SETTLED_SECONDS):
            done.append(entry)
    return sorted(done), sorted(partial)


def _describe(path: Path, title: str, expected_seconds: float) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "file": str(path), "name": path.name, "bytes": path.stat().st_size,
        "seconds": None, "sample_rate": None, "channels": None, "subtype": None,
        "title_matches": None, "length_matches": None, "problems": [],
    }
    try:
        import soundfile as sf

        info = sf.info(str(path))
    except Exception as exc:  # soundfile raises its own error types for unreadable files
        entry["problems"].append(f"It can't be read as audio ({exc})")
        return entry
    entry.update(seconds=round(info.duration, 3), sample_rate=info.samplerate,
                 channels=info.channels, subtype=info.subtype)
    if title.strip():
        entry["title_matches"] = path.name.casefold().startswith(title.strip().casefold())
    if expected_seconds > 0:
        entry["length_matches"] = abs(info.duration - expected_seconds) <= _LENGTH_TOLERANCE
        if info.duration < expected_seconds - _LENGTH_TOLERANCE:
            entry["problems"].append(
                f"It is {info.duration:.1f} s but the song is {expected_seconds:.1f} s: the "
                "selection missed part of it. Select the whole waveform and download again."
            )
        elif info.duration > expected_seconds + _LENGTH_TOLERANCE:
            entry["problems"].append(
                f"It is {info.duration:.1f} s but the song is {expected_seconds:.1f} s: the "
                "selection took in more than the song. Select just its whole waveform."
            )
    return entry


async def find_studio_download(
    since: str, title: str = "", expected_seconds: float = 0.0, wait_seconds: int = 120,
) -> str:
    """Find the WAV the user downloaded from Suno Studio, in ~/Downloads.

    Waits up to wait_seconds (at most 600) for a finished .wav that changed
    after `since` (open_in_studio's opened_at): no browser partial (.part,
    .crdownload, .download) still being written beside it, and left alone for
    two seconds. Studio names the file after the song's Suno title and the
    range downloaded ("Harbor [0m00s-2m37s].wav"), so pass the clip's title
    and length (audio-retrieve: title and metadata.duration) to tell its file
    from others and to catch a selection that missed part of the song.
    Read-only: the file stays where it is.

    Args:
        since: open_in_studio's opened_at (ISO time)
        title: The song's Suno title
        expected_seconds: The song's length in seconds
        wait_seconds: How long to wait for the file; 0 looks once

    Returns:
        JSON with status "found" (file, name, bytes, seconds, sample_rate,
        channels, subtype, title_matches, length_matches, problems),
        "several" (candidates with the same fields, for the user to choose),
        or "not_found" (downloading: partials still being written, and a
        hint); or an error
    """
    try:
        start = _parse_time(since)
    except ValueError:
        return _safe_json({
            "error": f"since must be an ISO time, like open_in_studio's opened_at: {since!r}",
        })
    deadline = time.monotonic() + max(0, min(int(wait_seconds), _MAX_WAIT_SECONDS))
    while True:
        done, partial = _scan(start)
        if done and not partial:
            return _safe_json(_report(done, title, expected_seconds))
        if time.monotonic() >= deadline:
            return _safe_json({
                "status": "not_found",
                "downloading": [p.name for p in partial],
                "hint": (
                    "Nothing finished yet. In Studio's editor, select the whole waveform and "
                    "click Download .WAV; call again once the browser shows it finished."
                ),
            })
        await _sleep(POLL_SECONDS)


def _report(done: list[Path], title: str, expected_seconds: float) -> dict[str, Any]:
    described = [_describe(path, title, expected_seconds) for path in done]
    if len(described) == 1:
        return {"status": "found", **described[0]}
    if title.strip() or expected_seconds > 0:
        matching = [d for d in described
                    if d["title_matches"] is not False and d["length_matches"] is not False]
        if len(matching) == 1:
            return {"status": "found", **matching[0]}
    return {"status": "several", "candidates": described}


def register(mcp: Any) -> None:
    """Register the Suno Studio tools with the MCP server."""
    mcp.tool()(open_in_studio)
    mcp.tool()(find_studio_download)
