"""Album artwork — plan a cover, have Codex make candidates, file the one chosen.

The art director writes an image prompt into the album README. What happens
next depends on ``artwork.generator`` in the user's config:

* ``manual`` (the default): the user takes the prompt to an image tool of their
  choice and brings the result back with ``import_album_art``.
* ``codex``: ``generate_album_art`` asks the user's installed Codex CLI for the
  image, using its built-in image tool on their ChatGPT sign-in.

Two rules hold throughout. Generating spends the user's image allowance, so it
does nothing while anything is missing. And the tools never choose: generating
makes candidates and stops; importing files the image it is given.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import (
    _album_dir,
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _safe_json,
)
from tools.artwork import codex as codex_art
from tools.artwork import cover as cover_art
from tools.state.indexer import read_config

logger = logging.getLogger(__name__)

# Where candidates wait to be chosen, beside the album's audio. Nothing else in
# the plugin looks in here, so a candidate is never mistaken for the cover.
CANDIDATES_DIR = "artwork-candidates"

_PLATFORM_RE = re.compile(r"(?m)^\*\*Platform\*\*:\s*(.+?)\s*$")


def _settings() -> dict[str, Any]:
    """The artwork settings, read fresh from the user's config file.

    Read from the file and not from the state cache, so that switching the
    generator in config takes effect on the next call.
    """
    return codex_art.artwork_settings(read_config())


def _problem(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _is_placeholder(value: str) -> bool:
    """True for a template value nobody has replaced: text wrapped in brackets."""
    stripped = value.strip()
    return stripped.startswith("[") and stripped.endswith("]")


def _read_art_section(album_dir: Path) -> tuple[str, str, str]:
    """``(prompt, avoid, platform)`` from the album README; ``""`` where unset."""
    try:
        text = (album_dir / "README.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read album README for its art prompt in %s: %s", album_dir, exc)
        return "", "", ""

    def code_under(heading: str) -> str:
        section = _extract_markdown_section(text, heading)
        value = (_extract_code_block(section) if section else None) or ""
        return "" if _is_placeholder(value) else value.strip()

    platform_match = _PLATFORM_RE.search(text)
    platform = platform_match.group(1) if platform_match else ""
    if _is_placeholder(platform):
        platform = ""
    return code_under("Image Prompt"), code_under("Negative Prompt"), platform


def _art_paths(normalized: str, album: dict[str, Any]) -> tuple[dict[str, Path] | None, str | None]:
    """Where an album's cover files and candidates live, or an error."""
    config = _shared.cache.get_state().get("config", {})
    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")
    genre = album.get("genre", "")
    content_dir = album.get("path", "")
    if not audio_root or not artist:
        return None, _safe_json({"found": True, "error": "audio_root or artist_name not configured"})
    if not genre or not content_dir:
        return None, _safe_json({
            "found": True,
            "error": f"Album '{normalized}' has no genre or path in state. Run rebuild_state.",
        })
    try:
        # confine=False: an album's audio folder may be a symlink out of
        # audio_root, as every other audio tool allows. The slug is still checked.
        audio_dir = _album_dir(audio_root, artist=artist, genre=genre, album=normalized, confine=False)
    except ValueError as exc:
        return None, _safe_json({"found": True, "error": str(exc)})
    return {
        "audio_dir": audio_dir,
        "candidates_dir": audio_dir / CANDIDATES_DIR,
        "album_png": audio_dir / "album.png",
        "content_art": Path(content_dir) / "album-art.png",
    }, None


def _build_plan(album_slug: str) -> tuple[dict[str, Any] | None, str | None]:
    """Everything known before an image is made. Returns ``(plan, error_json)``."""
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return None, error
    assert album is not None
    paths, error = _art_paths(normalized, album)
    if error:
        return None, error
    assert paths is not None

    settings = _settings()
    prompt, avoid, platform = _read_art_section(Path(album["path"]))
    problems: list[dict[str, str]] = []
    codex_info: dict[str, Any] | None = None

    if settings["generator"] != "codex":
        problems.append(_problem(
            "generator_manual", "blocking",
            "artwork.generator is manual, so the image is yours to make: take the prompt "
            "to the image tool you use, then file the result with import_album_art. To "
            "have Codex make it, set `artwork: {generator: codex}` in "
            "~/.bitwize-music/config.yaml.",
        ))
    else:
        codex = codex_art.find_codex(settings["codex_path"])
        if not codex:
            problems.append(_problem(
                "codex_not_found", "blocking",
                "The Codex CLI was not found on PATH or in its usual install folders. "
                "Install it, or set artwork.codex_path in ~/.bitwize-music/config.yaml.",
            ))
        else:
            status = codex_art.codex_status(codex)
            codex_info = {"path": codex, **status}
            if status["logged_in"] is False:
                problems.append(_problem(
                    "codex_not_logged_in", "blocking",
                    "Codex is not signed in. Run `codex login` in a terminal, then try again.",
                ))
            if status["image_generation"] is False:
                problems.append(_problem(
                    "image_generation_off", "blocking",
                    "Codex has its image_generation feature switched off. Turn it on under "
                    "[features] in ~/.codex/config.toml (image_generation = true).",
                ))

    if not prompt:
        problems.append(_problem(
            "no_prompt", "blocking",
            "The album README has no Image Prompt yet. Run "
            "/bitwize-music:album-art-director to design the cover and write one.",
        ))

    try:
        earlier = sorted(p.name for p in paths["candidates_dir"].glob("*.png"))
    except OSError:
        earlier = []
    existing = {
        "album_png": paths["album_png"].exists(),
        "content_art": paths["content_art"].exists(),
        "candidates": earlier,
    }
    if existing["album_png"] or existing["content_art"]:
        problems.append(_problem(
            "art_exists", "warning",
            "This album already has a cover. Importing a new one needs replace=true.",
        ))

    count = settings["candidates"]
    plan = {
        "found": True,
        "album_slug": normalized,
        "generator": settings["generator"],
        "candidates": count,
        "codex": codex_info,
        "platform": platform,
        "prompt": prompt,
        "avoid": avoid,
        "paths": {
            "candidates_dir": str(paths["candidates_dir"]),
            "album_png": str(paths["album_png"]),
            "content_art": str(paths["content_art"]),
        },
        "existing": existing,
        "cost": (
            f"{count} image{'' if count == 1 else 's'} from the ChatGPT plan Codex is signed "
            "in to (one per candidate), plus Codex usage for about a minute per image."
        ),
        "output": (
            "Codex returns a 1254x1254 PNG. The image chosen is enlarged to 3000x3000 "
            "when it is imported, which adds size but no detail."
        ),
        "ready": not any(p["severity"] == "blocking" for p in problems),
        "problems": problems,
    }
    return plan, None


def _open_in_viewer(paths: list[Path]) -> bool:
    """Show images in the system's image viewer. False when that is not possible."""
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["open", *[str(p) for p in paths]],
                check=True, timeout=15, stdin=subprocess.DEVNULL, capture_output=True,
            )
        elif sys.platform == "win32":
            for path in paths:
                os.startfile(str(path))
        else:
            for path in paths:
                subprocess.run(
                    ["xdg-open", str(path)],
                    check=True, timeout=15, stdin=subprocess.DEVNULL, capture_output=True,
                )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.info("Could not open the image viewer: %s", exc)
        return False
    return True


async def get_album_art_plan(album_slug: str) -> str:
    """Say how an album's cover will be made, before anything is spent. Free.

    Reads `artwork.generator` from config (manual or codex), the image prompt
    the art director wrote into the album README, and, for codex, whether the
    Codex CLI is installed, signed in and able to generate images. Call it
    before generate_album_art, tell the user the `cost`, and wait for their
    go-ahead.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with {found, album_slug, generator, candidates, codex: {path,
        version, logged_in, image_generation} | null, platform, prompt, avoid,
        paths: {candidates_dir, album_png, content_art}, existing: {album_png,
        content_art, candidates}, cost, output, ready, problems: [{code,
        severity, message}]}. `ready` is false while any problem is blocking.
    """
    plan, error = _build_plan(album_slug)
    if error:
        return error
    return _safe_json(plan)


async def generate_album_art(
    album_slug: str,
    candidates: int = 0,
    open_viewer: bool = True,
) -> str:
    """Have Codex make cover candidates from the album's image prompt.

    SPENDS the user's ChatGPT image allowance: one image per candidate. Call
    get_album_art_plan first, state its `cost`, and wait for the user to say
    go. Does nothing while the plan has a blocking problem.

    Each candidate is a separate Codex run of about a minute, saved in the
    album's audio folder under artwork-candidates/ and, by default, opened in
    the image viewer. Nothing is imported and no candidate is chosen: show the
    user what was made, let them pick or ask for changes, then call
    import_album_art with the file they chose.

    Args:
        album_slug: Album slug (e.g., "my-album")
        candidates: How many to make, 1 to 4 (0 = artwork.candidates from config)
        open_viewer: Open the new candidates in the system image viewer

    Returns:
        JSON with {found, album_slug, generated, candidates: [{path, width,
        height, seconds, saved_by}], failed: [{file, error}], prompt,
        candidates_dir, opened, next, problems}
    """
    plan, error = _build_plan(album_slug)
    if error:
        return error
    assert plan is not None
    if not plan["ready"]:
        return _safe_json({
            "found": True,
            "album_slug": plan["album_slug"],
            "generated": 0,
            "candidates": [],
            "failed": [],
            "opened": False,
            "problems": plan["problems"],
        })

    asked = candidates if isinstance(candidates, int) and not isinstance(candidates, bool) else 0
    count = min(max(asked if asked > 0 else plan["candidates"], 1), codex_art.MAX_CANDIDATES)
    candidates_dir = Path(plan["paths"]["candidates_dir"])
    codex = plan["codex"]["path"]
    stamp = time.strftime("%Y%m%d-%H%M%S")

    loop = asyncio.get_running_loop()
    made: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for number in range(1, count + 1):
        filename = f"cover-{stamp}-{number}.png"
        result = await loop.run_in_executor(None, functools.partial(
            codex_art.generate_image, codex, plan["prompt"], candidates_dir, filename,
            avoid=plan["avoid"],
        ))
        if result.get("ok"):
            made.append({key: result[key] for key in ("path", "width", "height", "seconds", "saved_by")})
        else:
            failed.append({"file": filename, "error": str(result.get("error", "unknown error"))})

    opened = bool(made) and open_viewer and _open_in_viewer([Path(c["path"]) for c in made])
    return _safe_json({
        "found": True,
        "album_slug": plan["album_slug"],
        "generated": len(made),
        "candidates": made,
        "failed": failed,
        "prompt": plan["prompt"],
        "candidates_dir": str(candidates_dir),
        "opened": opened,
        "next": (
            "Show the user the candidates and ask which one to use, or what to change. "
            "The choice is the user's: never pick for them. Then call import_album_art "
            "with the file they chose."
        ),
        "problems": plan["problems"],
    })


async def import_album_art(album_slug: str, source_path: str, replace: bool = False) -> str:
    """File an image as an album's cover.

    Writes two files: `album.png` in the album's audio folder, as a square PNG
    of at least 3000x3000 (a smaller image is enlarged), and `album-art.png` in
    the album's content folder at the image's own size. Use it for a candidate
    the user chose from generate_album_art, or for art made anywhere else.

    Only import the image the user picked. An existing cover is kept unless
    replace is true.

    Args:
        album_slug: Album slug (e.g., "my-album")
        source_path: The image to use: a path, or the bare file name of a
            candidate in the album's artwork-candidates/ folder
        replace: Overwrite a cover the album already has

    Returns:
        JSON with {found, imported, album_png, content_art, size, source_size,
        enlarged} or {found, imported: false, error}
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None
    paths, error = _art_paths(normalized, album)
    if error:
        return error
    assert paths is not None

    def refused(message: str) -> str:
        return _safe_json({"found": True, "album_slug": normalized, "imported": False,
                           "error": message})

    source = Path(os.path.expanduser(source_path))
    if not source.is_file() and Path(source_path).name == source_path:
        in_candidates = paths["candidates_dir"] / source_path
        if in_candidates.is_file():
            source = in_candidates

    try:
        cover_art.image_size(source)
    except ValueError as exc:
        return refused(str(exc))

    in_the_way = [str(paths[key]) for key in ("album_png", "content_art") if paths[key].exists()]
    if in_the_way and not replace:
        return refused(
            "This album already has a cover (" + ", ".join(in_the_way) + "). "
            "Nothing was changed. Ask the user, then pass replace=true to overwrite it."
        )

    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, cover_art.write_cover, source, paths["album_png"])
        await loop.run_in_executor(None, cover_art.write_png, source, paths["content_art"])
    except ValueError as exc:
        return refused(str(exc))
    except OSError as exc:
        return refused(f"Could not write the cover: {exc}")

    logger.info("Imported album art for '%s' from %s", normalized, source)
    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "imported": True,
        "album_png": str(paths["album_png"]),
        "content_art": str(paths["content_art"]),
        **info,
    })


def register(mcp: Any) -> None:
    """Register the album artwork tools with the MCP server."""
    mcp.tool()(get_album_art_plan)
    mcp.tool()(generate_album_art)
    mcp.tool()(import_album_art)
