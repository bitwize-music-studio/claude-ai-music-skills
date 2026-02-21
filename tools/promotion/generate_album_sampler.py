#!/usr/bin/env python3
"""
Album Sampler Video Generator

Creates a single promotional video that cycles through all tracks on an album
with short clips, designed to fit Twitter's 2:20 (140 second) limit.

Requirements:
    - ffmpeg with drawtext filter (brew install ffmpeg)
    - Python 3.8+

Usage:
    python generate_album_sampler.py /path/to/mastered --artwork album.png -o sampler.mp4
    python generate_album_sampler.py /path/to/mastered --clip-duration 10
"""

import atexit
import os
import sys
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List
import re

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import logging

from tools.shared.config import load_config as _load_config
from tools.shared.fonts import find_font
from tools.shared.logging_config import setup_logging
from tools.shared.progress import ProgressBar
from tools.shared.media_utils import (
    extract_dominant_color,
    get_complementary_color,
    rgb_to_hex,
    check_ffmpeg,
    get_audio_duration,
    find_best_segment,
)

logger = logging.getLogger(__name__)

# Safety-net cleanup for temp files left behind on abnormal exit
_temp_files_to_cleanup: list = []


def _cleanup_temp_files():
    for path in _temp_files_to_cleanup:
        try:
            os.unlink(path)
        except OSError:
            pass
    _temp_files_to_cleanup.clear()


atexit.register(_cleanup_temp_files)

_DEFAULT_CONFIG = {"artist": {"name": "bitwize"}}


def load_config() -> dict:
    """Load bitwize-music config file."""
    return _load_config(fallback=_DEFAULT_CONFIG) or _DEFAULT_CONFIG


# Video settings
WIDTH = 1080
HEIGHT = 1920
FPS = 30
DEFAULT_CLIP_DURATION = 12  # seconds per track
DEFAULT_CROSSFADE = 0.5  # seconds

# Colors
TEXT_COLOR = "#ffffff"

# Font settings
TITLE_FONT_SIZE = 64
ARTIST_FONT_SIZE = 48


def get_track_title(filename: str) -> str:
    """Extract clean track title from filename."""
    title = Path(filename).stem
    # Remove "XX - " prefix pattern (e.g., "08 - 116 Cadets" -> "116 Cadets")
    if ' - ' in title:
        title = title.split(' - ', 1)[-1]
    else:
        # Only remove 1-2 digit track numbers at start (not 3+ like "116")
        title = re.sub(r'^\d{1,2}[\.\-_\s]+', '', title)
    # Convert slug format to readable title
    title = title.replace('-', ' ').replace('_', ' ')
    title = title.title()
    return title


def generate_clip(
    audio_path: Path,
    artwork_path: Path,
    title: str,
    output_path: Path,
    duration: int,
    start_time: float,
    color_hex: str,
    artist_name: str,
    font_path: str
) -> bool:
    """Generate a single clip for one track."""

    # Write title and artist to temp files so ffmpeg reads them via textfile=
    # This avoids all escaping issues with drawtext's text= parameter,
    # preventing injection of ffmpeg filter directives through track titles.
    title_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    os.chmod(title_file.name, 0o600)
    title_file.write(title)
    title_file.close()
    title_file_path = title_file.name
    _temp_files_to_cleanup.append(title_file_path)

    artist_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    os.chmod(artist_file.name, 0o600)
    artist_file.write(artist_name)
    artist_file.close()
    artist_file_path = artist_file.name
    _temp_files_to_cleanup.append(artist_file_path)

    viz_height = 600

    # Pulse style visualization
    viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height}:mode=cline:scale=sqrt:colors={color_hex}:rate={FPS}[wave_core];
         [wave_core]split=3[c1][c2][c3];
         [c2]gblur=sigma=8[glow1];
         [c3]gblur=sigma=25[glow2];
         [c1][glow1]blend=all_mode=screen[layer1];
         [layer1][glow2]blend=all_mode=screen[wave]"""

    filter_complex = f"""
    [1:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,
         crop={WIDTH}:{HEIGHT},
         gblur=sigma=30,
         colorbalance=bs=-.1:bm=-.1:bh=-.1[bg];

    [1:v]scale={WIDTH-200}:-1:force_original_aspect_ratio=decrease[art];

    [bg][art]overlay=(W-w)/2:(H-h)/2-200[base];

    {viz_filter};

    [base][wave]overlay=0:H-750[withwave];

    [withwave]drawtext=textfile='{title_file_path}':
         fontfile={font_path}:
         fontsize={TITLE_FONT_SIZE}:
         fontcolor={TEXT_COLOR}:
         x=(w-text_w)/2:
         y=h-130:
         shadowcolor=black:shadowx=2:shadowy=2[withtitle];

    [withtitle]drawtext=textfile='{artist_file_path}':
         fontfile={font_path}:
         fontsize={ARTIST_FONT_SIZE}:
         fontcolor={TEXT_COLOR}@0.8:
         x=(w-text_w)/2:
         y=h-70:
         shadowcolor=black:shadowx=2:shadowy=2[final]
    """.replace('\n', '').replace('    ', '')

    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-t', str(duration),
        '-i', str(audio_path),
        '-loop', '1',
        '-i', str(artwork_path),
        '-filter_complex', filter_complex,
        '-map', '[final]',
        '-map', '0:a',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-t', str(duration),
        '-r', str(FPS),
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False
    finally:
        # Clean up temp text files (also remove from atexit list)
        for tmp in (title_file_path, artist_file_path):
            try:
                os.unlink(tmp)
            except OSError:
                pass
            try:
                _temp_files_to_cleanup.remove(tmp)
            except ValueError:
                pass


def concatenate_with_crossfade(
    clip_paths: List[Path],
    output_path: Path,
    crossfade: float = 0.5,
    clip_duration: int = DEFAULT_CLIP_DURATION
) -> bool:
    """Concatenate clips with audio and video crossfades."""

    if len(clip_paths) < 2:
        # Just copy the single file
        shutil.copy(clip_paths[0], output_path)
        return True

    # Build complex filter for crossfades
    inputs = []
    for clip in clip_paths:
        inputs.extend(['-i', str(clip)])

    # Build the filter graph
    n = len(clip_paths)

    # Build crossfade chain with cumulative offsets
    video_filters_fixed = []
    audio_filters_fixed = []

    # Label inputs
    for i in range(n):
        video_filters_fixed.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
        audio_filters_fixed.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")

    # Build crossfade chain with cumulative offsets
    current_v = "v0"
    current_a = "a0"
    cumulative_offset = clip_duration - crossfade

    for i in range(1, n):
        next_v = f"v{i}"
        next_a = f"a{i}"
        out_v = f"vout{i}" if i < n-1 else "vfinal"
        out_a = f"aout{i}" if i < n-1 else "afinal"

        video_filters_fixed.append(
            f"[{current_v}][{next_v}]xfade=transition=fade:duration={crossfade}:offset={cumulative_offset:.2f}[{out_v}]"
        )
        audio_filters_fixed.append(
            f"[{current_a}][{next_a}]acrossfade=d={crossfade}[{out_a}]"
        )

        current_v = out_v
        current_a = out_a
        cumulative_offset += clip_duration - crossfade

    filter_complex = ";".join(video_filters_fixed + audio_filters_fixed)

    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '[vfinal]',
        '-map', '[afinal]',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("Concatenation error: %s", result.stderr[:500])
            return False
        return True
    except Exception as e:
        logger.error("Concatenation failed: %s", e)
        return False


def generate_album_sampler(
    tracks_dir: Path,
    artwork_path: Path,
    output_path: Path,
    clip_duration: int = DEFAULT_CLIP_DURATION,
    crossfade: float = DEFAULT_CROSSFADE,
    artist_name: str = "bitwize",
    font_path: Optional[str] = None,
    titles: Optional[dict] = None,
) -> bool:
    """Generate album sampler video.

    Args:
        titles: Optional dict mapping filename stems to display titles.
                When provided (e.g. from MCP state cache), these take
                priority over get_track_title() filename parsing.
    """

    if font_path is None:
        font_path = find_font()
        if font_path is None:
            logger.error("No suitable font found")
            return False

    # Find audio files (check originals/ subdirectory first)
    audio_extensions = {'.wav', '.mp3', '.flac', '.m4a'}
    originals = tracks_dir / "originals"
    search_dir = originals if originals.is_dir() else tracks_dir
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(search_dir.glob(f'*{ext}'))

    # Filter out album.png if it somehow got in
    audio_files = [f for f in audio_files if f.suffix.lower() in audio_extensions]
    audio_files = sorted(audio_files)

    if not audio_files:
        logger.warning("No audio files found in %s", tracks_dir)
        return False

    logger.info("Found %d tracks", len(audio_files))

    # Extract colors from artwork
    logger.info("Extracting colors from artwork...")
    dominant = extract_dominant_color(artwork_path)
    complementary = get_complementary_color(dominant)
    color_hex = rgb_to_hex(complementary)
    logger.debug("Using color: %s", color_hex)

    # Create temp directory for clips
    temp_dir = Path(tempfile.mkdtemp(prefix="album_sampler_"))
    clip_paths = []

    try:
        # Generate individual clips
        clip_progress = ProgressBar(len(audio_files), prefix="Clips")
        for i, audio_file in enumerate(audio_files):
            clip_progress.update(audio_file.name)
            title = (titles or {}).get(audio_file.stem) or get_track_title(audio_file.name)
            logger.info("[%d/%d] %s...", i + 1, len(audio_files), title)

            # Find best segment
            start_time = find_best_segment(audio_file, clip_duration)

            # Generate clip
            clip_path = temp_dir / f"clip_{i:02d}.mp4"
            success = generate_clip(
                audio_path=audio_file,
                artwork_path=artwork_path,
                title=title,
                output_path=clip_path,
                duration=clip_duration,
                start_time=start_time,
                color_hex=color_hex,
                artist_name=artist_name,
                font_path=font_path
            )

            if success:
                clip_paths.append(clip_path)
                logger.info("  OK")
            else:
                logger.error("  FAILED - skipping")

        if not clip_paths:
            logger.error("No clips generated!")
            return False

        # Concatenate all clips
        logger.info("Concatenating %d clips with %ss crossfades...", len(clip_paths), crossfade)
        success = concatenate_with_crossfade(clip_paths, output_path, crossfade, clip_duration)

        if success:
            # Get final duration
            final_duration = get_audio_duration(output_path)
            file_size = output_path.stat().st_size / (1024 * 1024)
            print(f"\nCreated: {output_path}")
            print(f"  Duration: {final_duration:.1f}s")
            print(f"  Size: {file_size:.1f} MB")

            if final_duration > 140:
                logger.warning("Duration exceeds Twitter limit (140s)")

            return True
        else:
            logger.error("Failed to concatenate clips")
            return False

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description='Generate album sampler video for Twitter/social media',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_album_sampler.py /path/to/mastered -o sampler.mp4
    python generate_album_sampler.py /path/to/mastered --clip-duration 10
        """
    )

    parser.add_argument('tracks_dir', type=Path,
                        help='Directory containing mastered tracks')
    parser.add_argument('--artwork', '-a', type=Path,
                        help='Album artwork path (default: album.png in tracks dir)')
    parser.add_argument('-o', '--output', type=Path,
                        help='Output path (default: album_sampler.mp4)')
    parser.add_argument('--clip-duration', type=int, default=DEFAULT_CLIP_DURATION,
                        help=f'Duration per track in seconds (default: {DEFAULT_CLIP_DURATION})')
    parser.add_argument('--crossfade', type=float, default=DEFAULT_CROSSFADE,
                        help=f'Crossfade duration in seconds (default: {DEFAULT_CROSSFADE})')
    parser.add_argument('--artist', type=str,
                        help='Artist name (read from config if not set)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show debug output')
    parser.add_argument('--quiet', action='store_true',
                        help='Only show warnings and errors')

    args = parser.parse_args()

    setup_logging(__name__,
                  verbose=getattr(args, 'verbose', False),
                  quiet=getattr(args, 'quiet', False))

    check_ffmpeg()

    # Load config for artist name
    config = load_config()
    artist_name = args.artist or config.get('artist', {}).get('name', 'bitwize')

    # Find artwork
    if args.artwork:
        artwork = args.artwork
    else:
        # Try multiple naming patterns
        artwork_patterns = [
            'album.png', 'album.jpg',
            'album-art.png', 'album-art.jpg',
            'artwork.png', 'artwork.jpg',
            'cover.png', 'cover.jpg'
        ]
        artwork = None
        for pattern in artwork_patterns:
            candidate = args.tracks_dir / pattern
            if candidate.exists():
                artwork = candidate
                break

        if not artwork:
            # Try parent directory
            for pattern in artwork_patterns:
                candidate = args.tracks_dir.parent / pattern
                if candidate.exists():
                    artwork = candidate
                    break

        if not artwork:
            logger.error("No artwork found in album directory")
            logger.error("  Looked for: album.png, album.jpg, album-art.png, artwork.png, cover.png")
            logger.error("  Specify with: --artwork /path/to/artwork.png")
            sys.exit(1)

    # Set output path (default to promo_videos folder)
    if args.output:
        output = args.output
    else:
        promo_dir = args.tracks_dir.parent / 'promo_videos'
        promo_dir.mkdir(exist_ok=True)
        output = promo_dir / 'album_sampler.mp4'

    # Calculate expected duration
    audio_extensions = {'.wav', '.mp3', '.flac', '.m4a'}
    track_count = sum(1 for f in args.tracks_dir.iterdir()
                      if f.suffix.lower() in audio_extensions)
    expected_duration = track_count * args.clip_duration - (track_count - 1) * args.crossfade

    print("Album Sampler Generator")
    print("=======================")
    print(f"Tracks: {track_count}")
    print(f"Clip duration: {args.clip_duration}s")
    print(f"Crossfade: {args.crossfade}s")
    print(f"Expected duration: {expected_duration:.1f}s")
    print("Twitter limit: 140s")
    print()

    if expected_duration > 140:
        logger.warning("Expected duration exceeds Twitter limit!")
        logger.warning("Consider reducing --clip-duration to %ds or less",
                        int(140 / track_count))
        print()

    success = generate_album_sampler(
        tracks_dir=args.tracks_dir,
        artwork_path=artwork,
        output_path=output,
        clip_duration=args.clip_duration,
        crossfade=args.crossfade,
        artist_name=artist_name
    )

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
