"""Shared media utilities for promotion video and album sampler generation.

Provides color extraction, audio analysis, and ffmpeg helpers used by
generate_promo_video.py and generate_album_sampler.py.
"""

import colorsys
import logging
import subprocess
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def extract_dominant_color(image_path: Path) -> Tuple[int, int, int]:
    """Extract the dominant color from an image using PIL."""
    try:
        from PIL import Image
        from collections import Counter
        with Image.open(image_path) as img:
            img = img.convert('RGB')
            img = img.resize((100, 100))
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
    except (OSError, ImportError, IndexError, ValueError) as e:
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


def check_ffmpeg(require_showwaves: bool = False) -> bool:
    """Verify ffmpeg is installed, optionally check for showwaves filter."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-filters'],
            capture_output=True, text=True
        )
        if require_showwaves and 'showwaves' not in result.stdout:
            logger.warning("ffmpeg showwaves filter not found. Visualization may not work.")
            return False
        return True
    except FileNotFoundError:
        logger.error("ffmpeg not found. Install with: brew install ffmpeg")
        import sys
        sys.exit(1)


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file in seconds."""
    result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(audio_path)
    ], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed for {audio_path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def find_best_segment(audio_path: Path, duration: int = 15) -> float:
    """Find the most energetic segment by analyzing audio energy.

    Uses librosa to find the highest-energy window (usually chorus).
    Falls back to 20% into track if librosa unavailable.
    Returns the start time in seconds.
    """
    total_duration = get_audio_duration(audio_path)

    if total_duration <= duration:
        return 0

    max_start = total_duration - duration

    try:
        import librosa
        import numpy as np

        logger.info("Analyzing audio for most energetic segment...")

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

        best_start = min(max(best_start, 0), max_start)
        logger.info("Found energetic segment at %.1fs", best_start)
        return best_start

    except ImportError:
        logger.warning("librosa not installed, using fallback (20%% into track)")
        return min(total_duration * 0.2, max_start)
    except Exception as e:
        logger.warning("Energy analysis failed: %s, using fallback", e)
        return min(total_duration * 0.2, max_start)
