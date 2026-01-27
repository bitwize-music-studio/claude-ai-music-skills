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

import os
import sys
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
import colorsys
import re
import yaml


def load_config() -> dict:
    """Load bitwize-music config file."""
    config_path = Path.home() / ".bitwize-music" / "config.yaml"
    if not config_path.exists():
        return {"artist": {"name": "bitwize"}}  # Fallback

    with open(config_path) as f:
        return yaml.safe_load(f)


def find_font() -> Optional[str]:
    """Find an available system font."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]

    for font in font_paths:
        if Path(font).exists():
            return font

    return None


# Video settings
WIDTH = 1080
HEIGHT = 1920
FPS = 30
DEFAULT_CLIP_DURATION = 12  # seconds per track
DEFAULT_CROSSFADE = 0.5  # seconds

# Colors
BG_COLOR = "#0a0a0a"
TEXT_COLOR = "#ffffff"

# Font settings
TITLE_FONT_SIZE = 64
ARTIST_FONT_SIZE = 48


def extract_dominant_color(image_path: Path) -> Tuple[int, int, int]:
    """Extract the dominant color from an image using PIL."""
    try:
        from PIL import Image
        img = Image.open(image_path)
        img = img.convert('RGB')
        img = img.resize((100, 100))

        pixels = list(img.getdata())
        filtered = [p for p in pixels if 30 < sum(p)/3 < 225]
        if not filtered:
            filtered = pixels

        from collections import Counter
        quantized = [(r//32*32, g//32*32, b//32*32) for r, g, b in filtered]
        most_common = Counter(quantized).most_common(5)
        best_color = max(most_common, key=lambda x: max(x[0]) - min(x[0]))[0]
        return best_color
    except Exception as e:
        print(f"  Color extraction failed: {e}, using default cyan")
        return (0, 255, 255)


def get_complementary_color(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Get complementary color with boosted visibility."""
    r, g, b = [x / 255.0 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + 0.5) % 1.0
    l = max(l, 0.6)
    s = max(s, 0.8)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (int(r * 255), int(g * 255), int(b * 255))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex string for ffmpeg."""
    return f"0x{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def check_ffmpeg():
    """Verify ffmpeg is installed."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except FileNotFoundError:
        print("Error: ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file in seconds."""
    result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(audio_path)
    ], capture_output=True, text=True)
    return float(result.stdout.strip())


def find_best_segment(audio_path: Path, duration: int = 12) -> float:
    """Find the best segment by analyzing audio energy."""
    total_duration = get_audio_duration(audio_path)

    if total_duration <= duration:
        return 0

    max_start = total_duration - duration

    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        hop_length = 512
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        times = librosa.times_like(rms, sr=sr, hop_length=hop_length)

        window_samples = int(duration * sr / hop_length)
        best_start = 0
        best_energy = 0

        for i in range(len(rms) - window_samples):
            window_energy = np.mean(rms[i:i + window_samples])
            if window_energy > best_energy:
                best_energy = window_energy
                best_start = times[i]

        return min(max(best_start, 0), max_start)

    except ImportError:
        return min(total_duration * 0.2, max_start)
    except Exception:
        return min(total_duration * 0.2, max_start)


def get_track_title(filename: str) -> str:
    """Extract clean track title from filename."""
    title = Path(filename).stem
    # Remove "XX - " prefix pattern (e.g., "08 - 116 Cadets" -> "116 Cadets")
    if ' - ' in title:
        title = title.split(' - ', 1)[-1]
    else:
        # Only remove 1-2 digit track numbers at start (not 3+ like "116")
        title = re.sub(r'^\d{1,2}[\.\-_\s]+', '', title)
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

    # Escape for ffmpeg drawtext filter
    # Remove apostrophes (they break ffmpeg's single-quote text wrapper)
    safe_title = title.replace("'", "").replace("'", "").replace(":", "\\:").replace("%", "\\%").replace("\\", "\\\\")
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

    [withwave]drawtext=text='{safe_title}':
         fontfile={font_path}:
         fontsize={TITLE_FONT_SIZE}:
         fontcolor={TEXT_COLOR}:
         x=(w-text_w)/2:
         y=h-130:
         shadowcolor=black:shadowx=2:shadowy=2[withtitle];

    [withtitle]drawtext=text='{artist_name}':
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


def concatenate_with_crossfade(
    clip_paths: List[Path],
    output_path: Path,
    crossfade: float = 0.5
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
    cumulative_offset = 12 - crossfade  # First crossfade starts at 11.5s

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
        cumulative_offset += 12 - crossfade  # Add 11.5s for next clip

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
            print(f"Concatenation error: {result.stderr[:500]}")
            return False
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def generate_album_sampler(
    tracks_dir: Path,
    artwork_path: Path,
    output_path: Path,
    clip_duration: int = DEFAULT_CLIP_DURATION,
    crossfade: float = DEFAULT_CROSSFADE,
    artist_name: str = "bitwize",
    font_path: Optional[str] = None
) -> bool:
    """Generate album sampler video."""

    if font_path is None:
        font_path = find_font()
        if font_path is None:
            print("Error: No suitable font found")
            return False

    # Find audio files
    audio_extensions = {'.wav', '.mp3', '.flac', '.m4a'}
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(tracks_dir.glob(f'*{ext}'))

    # Filter out album.png if it somehow got in
    audio_files = [f for f in audio_files if f.suffix.lower() in audio_extensions]
    audio_files = sorted(audio_files)

    if not audio_files:
        print(f"No audio files found in {tracks_dir}")
        return False

    print(f"Found {len(audio_files)} tracks")

    # Extract colors from artwork
    print("Extracting colors from artwork...")
    dominant = extract_dominant_color(artwork_path)
    complementary = get_complementary_color(dominant)
    color_hex = rgb_to_hex(complementary)
    print(f"  Using color: {color_hex}")

    # Create temp directory for clips
    temp_dir = Path(tempfile.mkdtemp(prefix="album_sampler_"))
    clip_paths = []

    try:
        # Generate individual clips
        for i, audio_file in enumerate(audio_files):
            title = get_track_title(audio_file.name)
            print(f"[{i+1}/{len(audio_files)}] {title}...")

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
                print(f"  OK")
            else:
                print(f"  FAILED - skipping")

        if not clip_paths:
            print("No clips generated!")
            return False

        # Concatenate all clips
        print(f"\nConcatenating {len(clip_paths)} clips with {crossfade}s crossfades...")
        success = concatenate_with_crossfade(clip_paths, output_path, crossfade)

        if success:
            # Get final duration
            final_duration = get_audio_duration(output_path)
            file_size = output_path.stat().st_size / (1024 * 1024)
            print(f"\nCreated: {output_path}")
            print(f"  Duration: {final_duration:.1f}s")
            print(f"  Size: {file_size:.1f} MB")

            if final_duration > 140:
                print(f"  WARNING: Duration exceeds Twitter limit (140s)")

            return True
        else:
            print("Failed to concatenate clips")
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

    args = parser.parse_args()

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
            print("Error: No artwork found in album directory")
            print("  Looked for: album.png, album.jpg, album-art.png, artwork.png, cover.png")
            print("  Specify with: --artwork /path/to/artwork.png")
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

    print(f"Album Sampler Generator")
    print(f"=======================")
    print(f"Tracks: {track_count}")
    print(f"Clip duration: {args.clip_duration}s")
    print(f"Crossfade: {args.crossfade}s")
    print(f"Expected duration: {expected_duration:.1f}s")
    print(f"Twitter limit: 140s")
    print()

    if expected_duration > 140:
        print(f"WARNING: Expected duration exceeds Twitter limit!")
        print(f"Consider reducing --clip-duration to {int(140 / track_count)}s or less")
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
