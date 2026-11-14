"""build_release_kit: the page and JSON for uploading an album to DistroKid and SoundCloud.

Gathers the album's facts (state cache, track files, config, masters, cover)
and hands them to tools.release. Nothing here touches either site: the user
pastes and submits.
"""

from __future__ import annotations

import json
import logging
import re
import webbrowser
from datetime import date
from pathlib import Path
from typing import Any

from handlers._atomic import atomic_write_text
from handlers._shared import (
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _resolve_audio_dir,
    _safe_json,
)
from tools.playback import iterm as _iterm
from tools.release.kit import UNREADABLE, AlbumFacts, TrackFacts, build_kit
from tools.release.kit_page import render_html, render_json
from tools.state.parsers import _extract_table_value, parse_frontmatter

logger = logging.getLogger(__name__)

KIT_HTML = "release-kit.html"
KIT_JSON = "release-kit.json"
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_TRACK_NUMBER_RE = re.compile(r"^(\d+)")


async def build_release_kit(album_slug: str, open_page: bool = True) -> str:
    """Build an album's release kit for DistroKid and SoundCloud, beside mastered/.

    Writes release-kit.html (every value each upload form asks for, with a
    copy button, and the checks to clear first) and release-kit.json (the
    same data) into the album's audio folder. Nothing touches either site:
    the user pastes and submits. Every run rebuilds both files.

    Args:
        album_slug: Album slug (e.g., "my-album")
        open_page: Open the page afterwards: in an iTerm2 pane beside the
            session when panes work here, else in the default browser

    Returns:
        JSON with html and json (the paths), opened ("iterm2", "browser" or
        null) and checks ({fail, warn, info, items: [{level, message}]})
    """
    slug, album, err = _find_album_or_error(album_slug)
    if err:
        return err
    assert album is not None
    audio_err, audio_dir = _resolve_audio_dir(slug)
    if audio_err:
        return audio_err
    assert audio_dir is not None

    kit = build_kit(await _gather(slug, album, audio_dir), date.today())
    html_path = audio_dir / KIT_HTML
    json_path = audio_dir / KIT_JSON
    try:
        atomic_write_text(html_path, render_html(kit))
        atomic_write_text(json_path, render_json(kit))
    except OSError as exc:
        return _safe_json({"error": f"Could not write the release kit: {exc}", "path": str(html_path)})

    counts = {level: sum(1 for c in kit.checks if c.level == level) for level in ("fail", "warn", "info")}
    return _safe_json({
        "album_slug": slug,
        "html": str(html_path),
        "json": str(json_path),
        "opened": _open_page(html_path) if open_page else None,
        "checks": {**counts, "items": [{"level": c.level, "message": c.message} for c in kit.checks]},
    })


async def _gather(slug: str, album: dict[str, Any], audio_dir: Path) -> AlbumFacts:
    """Everything the kit needs about the album, from state, files and config."""
    from tools.shared.config import load_config

    config = load_config() or {}
    artist_cfg = config.get("artist") or {}
    release_cfg = config.get("release") or {}
    artist = str(artist_cfg.get("name") or "")

    album_path = str(album.get("path") or "")
    readme = _read(Path(album_path) / "README.md") if album_path else ""
    frontmatter = parse_frontmatter(readme) if readme else {}
    genre, subgenre = _genres(readme, str(album.get("genre") or ""))
    tags = _tags(frontmatter.get("tags"), genre)

    mastered = audio_dir / "mastered"
    entries = album.get("tracks") or {}
    problems = await _lyrics_problems(slug)
    tracks = [
        await _track(index, t_slug, entries[t_slug], mastered, problems.get(t_slug, ()))
        for index, t_slug in enumerate(sorted(entries), start=1)
    ]
    slugs = {t.slug for t in tracks}
    stray = tuple(sorted(p.name for p in _wavs(mastered) if p.stem not in slugs))
    cover = audio_dir / "album.png"
    return AlbumFacts(
        slug=slug,
        title=str(album.get("title") or slug),
        artist=artist,
        legal_name=str(artist_cfg.get("legal_name") or "").strip(),
        label=str(artist_cfg.get("label") or artist),
        copyright_holder=str(artist_cfg.get("copyright_holder") or artist),
        ai_disclosure=_ai_disclosure(release_cfg.get("ai_disclosure")),
        language=str(release_cfg.get("language") or "English"),
        release_date=str(frontmatter.get("release_date") or album.get("release_date") or ""),
        genre=genre,
        subgenre=subgenre,
        tags=tags,
        description=_concept(readme),
        explicit=bool(album.get("explicit", False)),
        upc=str(frontmatter.get("upc") or ""),
        cover=str(cover) if cover.is_file() else "",
        cover_size=_image_size(cover),
        mastered_dir=str(mastered),
        stray_wavs=stray,
        tracks=tuple(tracks),
    )


async def _track(number: int, t_slug: str, entry: dict[str, Any], mastered: Path,
                 problems: tuple[str, ...]) -> TrackFacts:
    from handlers.lyrics_analysis import _is_instrumental_track
    from handlers.text_analysis import check_explicit_content

    track_path = str(entry.get("path") or "")
    text = _read(Path(track_path)) if track_path else ""
    instrumental = _is_instrumental_track(text) if text else False
    lyrics = _streaming_lyrics(text)
    explicit_found = None
    if lyrics and not instrumental:
        explicit_found = bool(json.loads(await check_explicit_content(lyrics)).get("has_explicit"))
    match = _TRACK_NUMBER_RE.match(t_slug)
    wav = mastered / f"{t_slug}.wav"
    return TrackFacts(
        number=int(match.group(1)) if match else number,
        slug=t_slug,
        title=str(entry.get("title") or t_slug),
        status=str(entry.get("status") or ""),
        explicit=bool(entry.get("explicit", False)),
        instrumental=instrumental,
        lyrics=lyrics,
        isrc=str((parse_frontmatter(text) if text else {}).get("isrc") or ""),
        wav=str(wav) if wav.is_file() else "",
        wav_format=_wav_format(wav),
        lyrics_problems=problems,
        explicit_found=explicit_found,
    )


async def _lyrics_problems(slug: str) -> dict[str, tuple[str, ...]]:
    """Per track, what check_streaming_lyrics found wrong (failures and warnings)."""
    from handlers.gates import check_streaming_lyrics

    try:
        result = json.loads(await check_streaming_lyrics(slug))
    except (ValueError, TypeError):
        return {}
    problems: dict[str, tuple[str, ...]] = {}
    for track in result.get("tracks") or []:
        found = tuple(
            str(c.get("detail") or c.get("check"))
            for c in track.get("checks") or []
            if c.get("status") in ("FAIL", "WARN")
        )
        if found:
            problems[str(track.get("track_slug"))] = found
    return problems


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _genres(readme: str, slug_genre: str) -> tuple[str, str]:
    """The album's genre and subgenre, from the README's Genre row."""
    fallback = slug_genre.replace("-", " ").title()
    cell = _extract_table_value(readme, "Genre") if readme else None
    parts = [p.strip() for p in _LINK_RE.sub(r"\1", cell or "").split("/")]
    parts = [p for p in parts if p and not p.startswith("[") and p not in ("Genre", "Subgenre")]
    genre = parts[0] if parts else fallback
    return genre or fallback, parts[1] if len(parts) > 1 else ""


def _tags(listed: Any, genre: str) -> tuple[str, ...]:
    """The README's tags plus the genre, each once, ignoring case."""
    if isinstance(listed, str):
        listed = [listed]
    seen: set[str] = set()
    tags: list[str] = []
    for tag in [*(str(t).strip() for t in (listed or [])), genre]:
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    return tuple(tags)


def _concept(readme: str) -> str:
    """The README's Concept section as plain text; the template's placeholder is none."""
    section = _extract_markdown_section(readme, "Concept") if readme else None
    text = re.sub(r"<!--.*?-->", "", section or "", flags=re.S).strip()
    return "" if not text or (text.startswith("[") and text.endswith("]")) else text


def _streaming_lyrics(text: str) -> str:
    section = _extract_markdown_section(text, "Streaming Lyrics") if text else None
    return (_extract_code_block(section) or "").strip() if section else ""


def _ai_disclosure(value: Any) -> tuple[str, ...] | None:
    """The configured answer to DistroKid's AI question; None when unset."""
    if value is None:
        return None
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if str(v).strip())
    return None


def _wavs(mastered: Path) -> list[Path]:
    if not mastered.is_dir():
        return []
    return sorted(p for p in mastered.iterdir() if p.is_file() and p.suffix.lower() == ".wav")


def _wav_format(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        import soundfile as sf

        info = sf.info(str(path))
    except Exception:  # reported by the kit's master check
        return UNREADABLE
    return f"{info.subtype} {info.samplerate} Hz"


def _image_size(path: Path) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    try:
        from PIL import Image

        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:  # reported by the kit's cover check
        return None


def _open_page(path: Path) -> str | None:
    """Open the page beside the session in iTerm2 when panes work, else in the browser."""
    if _iterm.unavailable_reason() is None:
        try:
            _iterm.open_page_in_pane(path)
            return "iterm2"
        except _iterm.ItermError as exc:
            logger.warning("Could not open the release kit in iTerm2: %s", exc)
    try:
        return "browser" if webbrowser.open_new_tab(path.as_uri()) else None
    except webbrowser.Error as exc:
        logger.warning("Could not open the release kit in the browser: %s", exc)
        return None


def register(mcp: Any) -> None:
    """Register the release kit tool."""
    mcp.tool()(build_release_kit)
