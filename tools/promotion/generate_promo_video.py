#!/usr/bin/env python3
"""
Promo Video Generator

Creates 15-second vertical videos (9:16, 1080x1920) for Instagram/Facebook ads.
Uses ffmpeg to combine audio, album artwork, and waveform visualization.

Requirements:
    - ffmpeg with drawtext filter (brew install ffmpeg)
    - Python 3.8+

Usage:
    # Single track
    python generate_promo_video.py track.wav artwork.png "Track Name" -o output.mp4

    # Batch process album (auto-finds artwork in folder)
    python generate_promo_video.py --batch /path/to/album

    # Batch with explicit artwork path
    python generate_promo_video.py --batch /path/to/album --batch-artwork /path/to/artwork.png

    # Batch with album name (checks content directory for artwork)
    python generate_promo_video.py --batch /path/to/album --album my-album

    # Custom duration and style
    python generate_promo_video.py track.wav art.png "Song" --duration 30 --style circular
"""

import os
import sys
import argparse
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple
import colorsys

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import logging

from tools.shared.config import load_config as _load_config
from tools.shared.progress import ProgressBar
from tools.shared.fonts import find_font
from tools.shared.logging_config import setup_logging

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = {"artist": {"name": "bitwize"}}


def load_config() -> dict:
    """Load bitwize-music config file."""
    return _load_config(fallback=_DEFAULT_CONFIG) or _DEFAULT_CONFIG


def extract_dominant_color(image_path: Path) -> Tuple[int, int, int]:
    """Extract the dominant color from an image using PIL."""
    try:
        from PIL import Image
        from collections import Counter
        with Image.open(image_path) as img:
            img = img.convert('RGB')
            img = img.resize((100, 100))  # Resize for speed

            # Get all pixels and find most common
            pixels = list(img.getdata())

        # Filter out very dark and very light pixels
        filtered = [p for p in pixels if 30 < sum(p)/3 < 225]
        if not filtered:
            filtered = pixels

        # Quantize to reduce color space
        quantized = [(r//32*32, g//32*32, b//32*32) for r, g, b in filtered]
        most_common = Counter(quantized).most_common(5)

        # Pick the most saturated of the top colors
        best_color = max(most_common, key=lambda x: max(x[0]) - min(x[0]))[0]
        return best_color
    except Exception as e:
        logger.debug("Color extraction failed: %s, using default cyan", e)
        return (0, 255, 255)


def get_complementary_color(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Get complementary color with boosted visibility."""
    r, g, b = [x / 255.0 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + 0.5) % 1.0  # Rotate 180°
    l = max(l, 0.6)  # Ensure visible
    s = max(s, 0.8)  # Vibrant
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (int(r * 255), int(g * 255), int(b * 255))


def get_analogous_colors(rgb: Tuple[int, int, int]) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Get two analogous colors (30 degrees on each side)."""
    r, g, b = [x / 255.0 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    h1 = (h + 0.083) % 1.0  # +30 degrees
    h2 = (h - 0.083) % 1.0  # -30 degrees

    r1, g1, b1 = colorsys.hls_to_rgb(h1, l, s)
    r2, g2, b2 = colorsys.hls_to_rgb(h2, l, s)

    return (
        (int(r1 * 255), int(g1 * 255), int(b1 * 255)),
        (int(r2 * 255), int(g2 * 255), int(b2 * 255))
    )


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex string for ffmpeg."""
    return f"0x{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


# Video settings
WIDTH = 1080
HEIGHT = 1920
FPS = 30
DEFAULT_DURATION = 15  # seconds

# Colors
BG_COLOR = "#0a0a0a"  # Near black
WAVEFORM_COLOR = "#ffffff"  # White
TEXT_COLOR = "#ffffff"

# Font settings
TITLE_FONT_SIZE = 64
ARTIST_FONT_SIZE = 48


def check_ffmpeg():
    """Verify ffmpeg is installed with required filters."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-filters'],
            capture_output=True, text=True
        )
        if 'showwaves' not in result.stdout:
            logger.warning("ffmpeg showwaves filter not found. Visualization may not work.")
            return False
        return True
    except FileNotFoundError:
        logger.error("ffmpeg not found. Install with: brew install ffmpeg")
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


def find_best_segment(audio_path: Path, duration: int = 15) -> float:
    """
    Find the best 15-second segment by analyzing audio energy.
    Uses librosa to find the most energetic section (usually chorus).
    Falls back to 20% into track if librosa unavailable.
    Returns the start time in seconds.
    """
    total_duration = get_audio_duration(audio_path)

    if total_duration <= duration:
        return 0

    max_start = total_duration - duration

    # Try librosa energy analysis
    try:
        import librosa
        import numpy as np

        logger.info("Analyzing audio for most energetic segment...")

        # Load audio (mono, 22050 Hz is fine for energy analysis)
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)

        # Compute RMS energy over time
        hop_length = 512
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

        # Convert to time
        times = librosa.times_like(rms, sr=sr, hop_length=hop_length)

        # Find the window with highest average energy
        window_samples = int(duration * sr / hop_length)
        best_start = 0
        best_energy = 0

        for i in range(len(rms) - window_samples):
            window_energy = np.mean(rms[i:i + window_samples])
            if window_energy > best_energy:
                best_energy = window_energy
                best_start = times[i]

        # Clamp to valid range
        best_start = min(best_start, max_start)
        best_start = max(best_start, 0)

        logger.info("Found energetic segment at %.1fs", best_start)
        return best_start

    except ImportError:
        logger.warning("librosa not installed, using fallback (20%% into track)")
        logger.info("For energy analysis, set up venv:")
        logger.info("  source ~/.bitwize-music/promotion-env/bin/activate")
        logger.info("  pip install librosa numpy")
        return min(total_duration * 0.2, max_start)
    except Exception as e:
        logger.warning("Energy analysis failed: %s, using fallback", e)
        return min(total_duration * 0.2, max_start)


def generate_waveform_video(
    audio_path: Path,
    artwork_path: Path,
    title: str,
    output_path: Path,
    duration: int = DEFAULT_DURATION,
    style: str = "bars",
    start_time: Optional[float] = None,
    artist_name: str = "bitwize",
    font_path: Optional[str] = None
) -> bool:
    """
    Generate promo video with waveform visualization.

    Args:
        audio_path: Path to audio file (WAV, MP3, etc.)
        artwork_path: Path to album artwork (PNG, JPG)
        title: Track title to display
        output_path: Output video path
        duration: Video duration in seconds
        style: Visualization style (bars, line, circular)
        start_time: Start time in audio (auto-detect if None)
        artist_name: Artist name to display
        font_path: Path to TrueType font file
    """

    if font_path is None:
        font_path = find_font()
        if font_path is None:
            logger.error("No suitable font found")
            return False

    if start_time is None:
        start_time = find_best_segment(audio_path, duration)

    # Extract colors from album art
    logger.info("Extracting colors from artwork...")
    dominant = extract_dominant_color(artwork_path)
    complementary = get_complementary_color(dominant)
    analogous1, analogous2 = get_analogous_colors(dominant)

    # Convert to hex for ffmpeg
    color1 = rgb_to_hex(dominant)
    color2 = rgb_to_hex(complementary)
    color_ana1 = rgb_to_hex(analogous1)
    color_ana2 = rgb_to_hex(analogous2)

    logger.debug("Dominant: %s -> Complementary: %s (hex: %s)", dominant, complementary, color2)

    # Write title and artist to temp files so ffmpeg reads them via textfile=
    # This avoids all escaping issues with drawtext's text= parameter,
    # preventing injection of ffmpeg filter directives through track titles.
    title_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    title_file.write(title)
    title_file.close()
    title_file_path = title_file.name

    artist_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    artist_file.write(artist_name)
    artist_file.close()
    artist_file_path = artist_file.name

    # Build visualization filter based on style
    viz_height = 600  # Much taller - fills space between art and text

    if style == "mirror":
        # Option A: Mirrored waveform with glow - uses complementary color
        viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height//2}:mode=cline:scale=sqrt:colors={color2}:rate={FPS}[wave_top];
             [wave_top]split[w1][w2];
             [w2]vflip[wave_bot];
             [w1][wave_bot]vstack[wave_stack];
             [wave_stack]split[ws1][ws2];
             [ws2]gblur=sigma=8[wave_blur];
             [ws1][wave_blur]blend=all_mode=screen[wave]"""

    elif style == "mountains":
        # Option B: Dual-channel spectrum - uses complementary color
        viz_filter = f"""[0:a]showfreqs=s={WIDTH}x{viz_height//2}:mode=line:ascale=sqrt:fscale=log:colors={color2}:win_size=1024:overlap=0.7[freq_top];
             [freq_top]split[f1][f2];
             [f2]vflip[freq_bot];
             [f1][freq_bot]vstack[wave_stack];
             [wave_stack]split[ws1][ws2];
             [ws2]gblur=sigma=5[wave_blur];
             [ws1][wave_blur]blend=all_mode=screen[wave]"""

    elif style == "colorwave":
        # Option C: Clean waveform with subtle glow - single complementary color
        viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height}:mode=cline:scale=sqrt:colors={color2}:rate={FPS}[wave_raw];
             [wave_raw]split[wr1][wr2];
             [wr2]gblur=sigma=4[wave_blur];
             [wr1][wave_blur]blend=all_mode=screen:all_opacity=0.5[wave]"""

    elif style == "neon":
        # Sharp waveform with punchy glow - bright but not blinding
        viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height}:mode=cline:scale=sqrt:colors={color2}:rate={FPS}[wave_raw];
             [wave_raw]split[wr1][wr2];
             [wr2]gblur=sigma=2[wave_glow];
             [wr1][wave_glow]blend=all_mode=addition:all_opacity=0.6[wave]"""

    elif style == "pulse":
        # Oscilloscope/EKG style - centered waveform with heavy multi-layer glow
        # Uses complementary color from album art for cohesive look
        viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height}:mode=cline:scale=sqrt:colors={color2}:rate={FPS}[wave_core];
             [wave_core]split=3[c1][c2][c3];
             [c2]gblur=sigma=8[glow1];
             [c3]gblur=sigma=25[glow2];
             [c1][glow1]blend=all_mode=screen[layer1];
             [layer1][glow2]blend=all_mode=screen[wave]"""

    elif style == "dual":
        # Option E: Two separate waveforms - dominant on top, complementary below
        viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height//2}:mode=cline:scale=sqrt:colors={color2}:rate={FPS}[wave1];
             [0:a]showwaves=s={WIDTH}x{viz_height//2}:mode=cline:scale=sqrt:colors={color1}:rate={FPS}[wave2];
             [wave2]vflip[wave2f];
             [wave1][wave2f]vstack[wave]"""

    elif style == "bars":
        # Fast reactive spectrum line
        viz_filter = f"""[0:a]showfreqs=s={WIDTH}x{viz_height}:mode=line:ascale=sqrt:fscale=log:
             colors=white:win_size=2048:overlap=0.5[wave]"""
    elif style == "line":
        # Classic waveform - highly reactive, centered
        viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height}:mode=cline:scale=sqrt:
             colors=white:rate={FPS}:split_channels=0[wave]"""
    else:  # circular
        # Audio vectorscope - creates wild circular patterns
        viz_filter = f"""[0:a]avectorscope=s=600x600:mode=lissajous_xy:
             scale=sqrt:draw=line:zoom=1.5:rc=255:gc=255:bc=255[wave_raw];
             [wave_raw]pad={WIDTH}:{viz_height}:(ow-iw)/2:(oh-ih)/2:black[wave]"""

    # Build the complex filter
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
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-t', str(duration),
        '-r', str(FPS),
        str(output_path)
    ]

    logger.info("Generating: %s", output_path.name)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("ffmpeg failed: %s", result.stderr)
            return False
        return True
    except Exception as e:
        logger.error("Error generating video: %s", e)
        return False
    finally:
        # Clean up temp text files
        for tmp in (title_file_path, artist_file_path):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def get_title_from_markdown(track_md_path: Path) -> Optional[str]:
    """Extract title from track markdown frontmatter."""
    try:
        content = track_md_path.read_text()
        if content.startswith('---'):
            # Parse YAML frontmatter
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                for line in frontmatter.split('\n'):
                    if line.strip().startswith('title:'):
                        title = line.split(':', 1)[1].strip()
                        # Remove quotes if present
                        if (title.startswith('"') and title.endswith('"')) or \
                           (title.startswith("'") and title.endswith("'")):
                            title = title[1:-1]
                        return title
    except Exception:
        pass
    return None


def batch_process_album(
    album_dir: Path,
    artwork_path: Path,
    output_dir: Path,
    duration: int = DEFAULT_DURATION,
    style: str = "bars",
    artist_name: str = "bitwize",
    font_path: Optional[str] = None,
    content_dir: Optional[Path] = None,
    jobs: int = 1,
):
    """Process all audio files in an album directory."""
    audio_extensions = {'.wav', '.mp3', '.flac', '.m4a'}

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find audio files
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(album_dir.glob(f'*{ext}'))

    if not audio_files:
        logger.warning("No audio files found in %s", album_dir)
        return

    logger.info("Found %d tracks", len(audio_files))
    if content_dir:
        logger.info("Reading titles from: %s/tracks/", content_dir)

    sorted_audio = sorted(audio_files)

    def _resolve_title(audio_file):
        """Resolve track title from markdown or filename."""
        import re
        title = None
        if content_dir:
            track_md = content_dir / 'tracks' / f"{audio_file.stem}.md"
            if track_md.exists():
                title = get_title_from_markdown(track_md)
                if title:
                    logger.debug("Found title for %s: %s", audio_file.stem, title)
        if not title:
            title = audio_file.stem
            if ' - ' in title:
                title = title.split(' - ', 1)[-1]
            else:
                title = re.sub(r'^\d{1,2}[\.\-_\s]+', '', title)
            title = title.replace('-', ' ').replace('_', ' ')
            title = title.title()
        return title

    def _process_one(audio_file):
        """Generate promo video for a single track. Returns (name, success)."""
        title = _resolve_title(audio_file)
        output_file = output_dir / f"{audio_file.stem}_promo.mp4"
        success = generate_waveform_video(
            audio_path=audio_file,
            artwork_path=artwork_path,
            title=title,
            output_path=output_file,
            duration=duration,
            style=style,
            artist_name=artist_name,
            font_path=font_path
        )
        return (audio_file.name, output_file.name, success)

    workers = jobs if jobs > 0 else (os.cpu_count() or 1)
    progress = ProgressBar(len(sorted_audio), prefix="Generating")

    if workers == 1:
        for audio_file in sorted_audio:
            progress.update(audio_file.name)
            _, out_name, success = _process_one(audio_file)
            if success:
                logger.info("  [OK] %s", out_name)
            else:
                logger.error("  [FAIL] %s", audio_file.name)
    else:
        logger.info("Using %d parallel workers", workers)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_process_one, af): af for af in sorted_audio}
            for future in as_completed(futures):
                af = futures[future]
                progress.update(af.name)
                _, out_name, success = future.result()
                if success:
                    logger.info("  [OK] %s", out_name)
                else:
                    logger.error("  [FAIL] %s", af.name)


def main():
    parser = argparse.ArgumentParser(
        description='Generate promo videos for social media ads',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Single track
    python generate_promo_video.py song.wav cover.png "Song Title"

    # Full album (auto-finds artwork)
    python generate_promo_video.py --batch ./mastered -o ./videos

    # Full album with explicit artwork
    python generate_promo_video.py --batch ./mastered --batch-artwork /path/to/art.png

    # Full album checking content dir for artwork
    python generate_promo_video.py --batch ./mastered --album my-album

    # 30 second clip with line style
    python generate_promo_video.py song.wav cover.png "Title" --duration 30 --style line
        """
    )

    parser.add_argument('audio', nargs='?', help='Audio file path')
    parser.add_argument('artwork', nargs='?', help='Album artwork path')
    parser.add_argument('title', nargs='?', help='Track title')

    parser.add_argument('--batch', type=Path,
                        help='Batch process all audio in directory')
    parser.add_argument('--batch-artwork', type=Path, dest='batch_artwork',
                        help='Path to album artwork (for batch mode)')
    parser.add_argument('-o', '--output', type=Path,
                        help='Output path (file or directory for batch)')
    parser.add_argument('--duration', '-d', type=int, default=DEFAULT_DURATION,
                        help=f'Video duration in seconds (default: {DEFAULT_DURATION})')
    parser.add_argument('--style', '-s', choices=['mirror', 'mountains', 'colorwave', 'neon', 'pulse', 'dual', 'bars', 'line', 'circular'],
                        default='bars', help='Waveform visualization style')
    parser.add_argument('--start', type=float,
                        help='Start time in seconds (auto-detect if not set)')
    parser.add_argument('--artist', type=str,
                        help='Artist name (read from config if not set)')
    parser.add_argument('--album', type=str,
                        help='Album name (for finding artwork in content directory)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show debug output')
    parser.add_argument('--quiet', action='store_true',
                        help='Only show warnings and errors')
    parser.add_argument('-j', '--jobs', type=int, default=1,
                        help='Parallel jobs for batch mode (0=auto, default: 1)')

    args = parser.parse_args()

    setup_logging(__name__,
                  verbose=getattr(args, 'verbose', False),
                  quiet=getattr(args, 'quiet', False))

    check_ffmpeg()

    # Load config for artist name
    config = load_config()
    artist_name = args.artist or config.get('artist', {}).get('name', 'bitwize')

    # Find font
    font_path = find_font()
    if font_path is None:
        logger.error("No suitable font found")
        sys.exit(1)

    if args.batch:
        # Batch mode
        album_content_dir = None  # Will be set if --album provided
        if args.batch_artwork:
            artwork = args.batch_artwork
        else:
            # Try to find artwork with multiple naming patterns
            artwork_patterns = [
                'album.png', 'album.jpg',
                'album-art.png', 'album-art.jpg',
                'artwork.png', 'artwork.jpg',
                'cover.png', 'cover.jpg'
            ]
            artwork = None

            # 1. Check batch directory (audio folder)
            for pattern in artwork_patterns:
                candidate = args.batch / pattern
                if candidate.exists():
                    artwork = candidate
                    break

            # 2. Check parent directory
            if not artwork:
                for pattern in artwork_patterns:
                    candidate = args.batch.parent / pattern
                    if candidate.exists():
                        artwork = candidate
                        break

            # 3. Check content directory via config
            album_content_dir = None
            if args.album:
                content_root = Path(config.get('paths', {}).get('content_root', '')).expanduser()
                if content_root.exists():
                    # Search for album in content directory
                    for genre_dir in (content_root / 'artists' / artist_name / 'albums').glob('*'):
                        candidate_dir = genre_dir / args.album
                        if candidate_dir.exists():
                            album_content_dir = candidate_dir
                            if not artwork:
                                for pattern in artwork_patterns:
                                    candidate = album_content_dir / pattern
                                    if candidate.exists():
                                        artwork = candidate
                                        logger.info("Found artwork in content dir: %s", artwork)
                                        break
                            break

            if not artwork:
                logger.error("No artwork found")
                logger.error("  Looked in:")
                logger.error("    - %s/", args.batch)
                logger.error("    - %s/", args.batch.parent)
                if args.album:
                    logger.error("    - content directory for album '%s'", args.album)
                logger.error("  Specify with: --batch-artwork /path/to/artwork.png")
                logger.error("  Or use: /bitwize-music:import-art to copy artwork to audio folder")
                sys.exit(1)

        output_dir = args.output or args.batch / 'promo_videos'

        batch_process_album(
            album_dir=args.batch,
            artwork_path=artwork,
            output_dir=output_dir,
            duration=args.duration,
            style=args.style,
            artist_name=artist_name,
            font_path=font_path,
            content_dir=album_content_dir,
            jobs=args.jobs,
        )

    else:
        # Single file mode
        if not all([args.audio, args.artwork, args.title]):
            parser.print_help()
            logger.error("audio, artwork, and title are required for single file mode")
            sys.exit(1)

        audio = Path(args.audio)
        artwork = Path(args.artwork)
        output = args.output or audio.with_suffix('.mp4')

        success = generate_waveform_video(
            audio_path=audio,
            artwork_path=artwork,
            title=args.title,
            output_path=output,
            duration=args.duration,
            style=args.style,
            start_time=args.start,
            artist_name=artist_name,
            font_path=font_path
        )

        if success:
            logger.info("[OK] Created: %s", output)
        else:
            logger.error("[FAIL] Failed to create video")
            sys.exit(1)


if __name__ == '__main__':
    main()
