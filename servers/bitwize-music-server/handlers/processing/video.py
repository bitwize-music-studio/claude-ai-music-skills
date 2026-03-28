"""Promo video generation tools."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import (
    _find_wav_source_dir,
    _normalize_slug,
    # _resolve_audio_dir accessed via _helpers for patch compatibility
    _safe_json,
)
from handlers.processing import _helpers

logger = logging.getLogger("bitwize-music-state")


async def generate_promo_videos(
    album_slug: str,
    style: str = "pulse",
    duration: int = 15,
    track_filename: str = "",
    color_hex: str = "",
    glow: float = 0.6,
    text_color: str = "",
) -> str:
    """Generate promo videos with waveform visualization for social media.

    Creates 15-second vertical videos (1080x1920) combining album artwork,
    audio waveform visualization, and track titles.

    Args:
        album_slug: Album slug (e.g., "my-album")
        style: Visualization style - "pulse", "mirror", "mountains", "colorwave",
               "neon", "dual", "bars", "line", "circular" (default: "pulse")
        duration: Video duration in seconds (default: 15)
        track_filename: Optional single track WAV filename (empty = batch all)
        color_hex: Wave color as hex (e.g. "#C9A96E"). Empty = auto-extract from artwork
        glow: Glow intensity 0.0 (none) to 1.0 (full). Default 0.6
        text_color: Text color as hex (e.g. "#FFD700"). Empty = white

    Returns:
        JSON with per-track results and summary
    """
    ffmpeg_err = _helpers._check_ffmpeg()
    if ffmpeg_err:
        return _safe_json({"error": ffmpeg_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Find artwork
    artwork_patterns = [
        "album.png", "album.jpg", "album-art.png", "album-art.jpg",
        "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
    ]
    artwork = None
    for pattern in artwork_patterns:
        candidate = audio_dir / pattern
        if candidate.exists():
            artwork = candidate
            break
    if not artwork:
        return _safe_json({
            "error": "No album artwork found in audio directory.",
            "suggestion": "Place album.png in the audio directory or use /bitwize-music:import-art.",
            "looked_for": artwork_patterns,
        })

    from tools.promotion.generate_promo_video import (
        batch_process_album,
        generate_waveform_video,
    )
    from tools.shared.fonts import find_font

    # Get artist from state
    state = _shared.cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "bitwize")

    font_path = find_font()

    output_dir = audio_dir / "promo_videos"
    output_dir.mkdir(exist_ok=True)

    loop = asyncio.get_running_loop()

    if track_filename:
        # Single track
        track_path = audio_dir / track_filename
        if not track_path.exists():
            # Also check originals/ and mastered/
            track_path = audio_dir / "originals" / track_filename
            if not track_path.exists():
                track_path = audio_dir / "mastered" / track_filename
            if not track_path.exists():
                return _safe_json({
                    "error": f"Track file not found: {track_filename}",
                    "available_files": [f.name for f in _find_wav_source_dir(audio_dir).glob("*.wav")],
                })

        # Resolve title: prefer markdown title from state cache over filename
        title = None
        albums = state.get("albums", {})
        normalized = _normalize_slug(album_slug)
        album_data = albums.get(normalized)
        if album_data:
            # Match track by stem (filename without extension)
            track_stem = track_path.stem
            track_slug = _normalize_slug(track_stem)
            tracks = album_data.get("tracks", {})
            track_data = tracks.get(track_slug)
            if track_data:
                title = track_data.get("title")

        if not title:
            # Fall back to cleaning up the filename
            title = track_path.stem
            if " - " in title:
                title = title.split(" - ", 1)[-1]
            else:
                title = re.sub(r"^\d{1,2}[\.\-_\s]+", "", title)
            title = title.replace("-", " ").replace("_", " ").title()

        output_path = output_dir / f"{track_path.stem}_promo.mp4"

        success = await loop.run_in_executor(
            None,
            lambda: generate_waveform_video(
                audio_path=track_path,
                artwork_path=artwork,
                title=title,
                output_path=output_path,
                duration=duration,
                style=style,
                artist_name=artist,
                font_path=font_path,
                color_hex=color_hex,
                glow=glow,
                text_color=text_color,
            ),
        )

        return _safe_json({
            "tracks": [{"filename": track_filename, "output": str(output_path), "success": success}],
            "summary": {"success": 1 if success else 0, "failed": 0 if success else 1},
        })
    else:
        # Batch all tracks
        # Resolve content dir for title lookup
        albums = state.get("albums", {})
        normalized = _normalize_slug(album_slug)
        content_dir = None
        album_data = albums.get(normalized)
        if album_data:
            content_dir_path = Path(album_data.get("path", ""))
            if content_dir_path.is_dir():
                content_dir = content_dir_path

        await loop.run_in_executor(
            None,
            lambda: batch_process_album(
                album_dir=audio_dir,
                artwork_path=artwork,
                output_dir=output_dir,
                duration=duration,
                style=style,
                artist_name=artist,
                font_path=font_path,
                content_dir=content_dir,
                color_hex=color_hex,
                glow=glow,
                text_color=text_color,
            ),
        )

        # Collect results from output dir
        output_files = sorted(output_dir.glob("*_promo.mp4"))
        results = [{"filename": f.name, "output": str(f), "success": True} for f in output_files]

        return _safe_json({
            "tracks": results,
            "summary": {
                "success": len(results),
                "output_dir": str(output_dir),
            },
        })


async def generate_album_sampler(
    album_slug: str,
    clip_duration: int = 12,
    crossfade: float = 0.5,
    style: str = "pulse",
    color_hex: str = "",
    glow: float = 0.6,
    text_color: str = "",
) -> str:
    """Generate an album sampler video cycling through all tracks.

    Creates a single promotional video with short clips from each track,
    designed to fit Twitter's 2:20 (140 second) limit.

    Args:
        album_slug: Album slug (e.g., "my-album")
        clip_duration: Duration per track clip in seconds (default: 12)
        crossfade: Crossfade duration between clips in seconds (default: 0.5)
        style: Visualization style - "pulse", "mirror", "mountains", "colorwave",
               "neon", "dual", "bars", "line", "circular" (default: "pulse")
        color_hex: Wave color as hex (e.g. "#C9A96E"). Empty = auto-extract from artwork
        glow: Glow intensity 0.0 (none) to 1.0 (full). Default 0.6
        text_color: Text color as hex (e.g. "#FFD700"). Empty = white

    Returns:
        JSON with output path, tracks included, and duration
    """
    ffmpeg_err = _helpers._check_ffmpeg()
    if ffmpeg_err:
        return _safe_json({"error": ffmpeg_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Find artwork
    artwork_patterns = [
        "album.png", "album.jpg", "album-art.png", "album-art.jpg",
        "artwork.png", "artwork.jpg", "cover.png", "cover.jpg",
    ]
    artwork = None
    for pattern in artwork_patterns:
        candidate = audio_dir / pattern
        if candidate.exists():
            artwork = candidate
            break
    if not artwork:
        return _safe_json({
            "error": "No album artwork found in audio directory.",
            "suggestion": "Place album.png in the audio directory.",
        })

    from tools.promotion.generate_album_sampler import (
        generate_album_sampler as _gen_sampler,
    )

    # Get artist from state
    state = _shared.cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "bitwize")

    # Pre-resolve titles from state cache (proper titles from markdown metadata)
    titles: dict[str, str] = {}
    albums = state.get("albums", {})
    normalized = _normalize_slug(album_slug)
    album_data = albums.get(normalized)
    if album_data:
        for track_slug, track_data in album_data.get("tracks", {}).items():
            title = track_data.get("title")
            if title:
                titles[track_slug] = title

    output_dir = audio_dir / "promo_videos"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "album_sampler.mp4"

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        lambda: _gen_sampler(
            tracks_dir=audio_dir,
            artwork_path=artwork,
            output_path=output_path,
            clip_duration=clip_duration,
            crossfade=crossfade,
            artist_name=artist,
            titles=titles,
            style=style,
            color_hex=color_hex,
            glow=glow,
            text_color=text_color,
        ),
    )

    if success and output_path.exists():
        file_size = output_path.stat().st_size / (1024 * 1024)
        # Count audio files
        audio_extensions = {".wav", ".mp3", ".flac", ".m4a"}
        track_count = sum(
            1 for f in _find_wav_source_dir(audio_dir).iterdir()
            if f.suffix.lower() in audio_extensions
        )
        expected_duration = track_count * clip_duration - max(0, track_count - 1) * crossfade

        return _safe_json({
            "success": True,
            "output_path": str(output_path),
            "tracks_included": track_count,
            "clip_duration": clip_duration,
            "crossfade": crossfade,
            "expected_duration_seconds": expected_duration,
            "file_size_mb": round(file_size, 1),
            "twitter_limit_ok": expected_duration <= 140,
        })
    else:
        return _safe_json({"error": "Album sampler generation failed."})


def register(mcp: Any) -> None:
    """Register promo video tools."""
    mcp.tool()(generate_promo_videos)
    mcp.tool()(generate_album_sampler)
