#!/usr/bin/env python3
"""
Generate All Promo Videos

Generates both individual track promo videos AND an album sampler video in one command.

Usage:
    python generate_all_promos.py /path/to/album
    python generate_all_promos.py /path/to/album --tracks-only
    python generate_all_promos.py /path/to/album --sampler-only
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging

logger = logging.getLogger(__name__)


def find_mastered_dir(album_dir: Path) -> Path:
    """Find the mastered tracks directory."""
    # Check common locations
    candidates = [
        album_dir,  # Most common for plugin: audio goes directly in album dir
        album_dir / "wavs" / "mastered",
        album_dir / "mastered",
        album_dir / "wavs",
    ]

    for candidate in candidates:
        if candidate.exists():
            # Check if it has audio files
            audio_extensions = {'.wav', '.mp3', '.flac', '.m4a'}
            has_audio = any(f.suffix.lower() in audio_extensions
                          for f in candidate.iterdir() if f.is_file())
            if has_audio:
                return candidate

    return album_dir


def find_artwork(album_dir: Path) -> Path:
    """Find album artwork."""
    # Check common locations and names
    # Note: import-art skill saves as album.png in audio_root
    candidates = [
        album_dir / "album.png",
        album_dir / "album.jpg",
        album_dir / "album-art.png",  # Alternative from import-art content location
        album_dir / "album-art.jpg",
        album_dir / "artwork.png",
        album_dir / "artwork.jpg",
        album_dir / "cover.png",
        album_dir / "cover.jpg",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Check in wavs subdirectory
    wavs_dir = album_dir / "wavs"
    if wavs_dir.exists():
        for name in ["album.png", "album.jpg"]:
            candidate = wavs_dir / name
            if candidate.exists():
                return candidate

    # Check mastered subdirectory
    mastered_dir = album_dir / "wavs" / "mastered"
    if mastered_dir.exists():
        for name in ["album.png", "album.jpg"]:
            candidate = mastered_dir / name
            if candidate.exists():
                return candidate

    return None


def main():
    parser = argparse.ArgumentParser(
        description='Generate all promo videos for an album (individual tracks + sampler)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate everything
    python generate_all_promos.py /path/to/album

    # Individual track promos only
    python generate_all_promos.py /path/to/album --tracks-only

    # Album sampler only
    python generate_all_promos.py /path/to/album --sampler-only
        """
    )

    parser.add_argument('album_dir', type=Path,
                        help='Album directory (containing mastered tracks and album art)')
    parser.add_argument('--tracks-only', action='store_true',
                        help='Only generate individual track promos')
    parser.add_argument('--sampler-only', action='store_true',
                        help='Only generate album sampler')
    parser.add_argument('--style', default='pulse',
                        choices=['mirror', 'mountains', 'colorwave', 'neon', 'pulse', 'dual', 'bars', 'line', 'circular'],
                        help='Visualization style (default: pulse)')
    parser.add_argument('--clip-duration', type=int, default=12,
                        help='Sampler clip duration per track (default: 12)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show debug output')
    parser.add_argument('--quiet', action='store_true',
                        help='Only show warnings and errors')

    args = parser.parse_args()

    setup_logging(__name__,
                  verbose=getattr(args, 'verbose', False),
                  quiet=getattr(args, 'quiet', False))

    # Resolve paths
    album_dir = args.album_dir.resolve()
    if not album_dir.exists():
        logger.error("Album directory not found: %s", album_dir)
        sys.exit(1)

    mastered_dir = find_mastered_dir(album_dir)
    artwork = find_artwork(album_dir)

    if not artwork:
        logger.error("Could not find album artwork in %s", album_dir)
        logger.error("  Looked for: album.png, album.jpg, artwork.png, cover.png")
        sys.exit(1)

    # Count tracks
    audio_extensions = {'.wav', '.mp3', '.flac', '.m4a'}
    track_count = sum(1 for f in mastered_dir.iterdir()
                      if f.is_file() and f.suffix.lower() in audio_extensions)

    print("Album Promo Generator")
    print("=====================")
    print(f"Album dir: {album_dir}")
    print(f"Tracks dir: {mastered_dir}")
    print(f"Artwork: {artwork}")
    print(f"Tracks: {track_count}")
    print(f"Style: {args.style}")
    print()

    # Get script directory
    script_dir = Path(__file__).parent

    success = True

    # Generate individual track promos
    if not args.sampler_only:
        print("=" * 50)
        print("GENERATING INDIVIDUAL TRACK PROMOS")
        print("=" * 50)

        promo_dir = album_dir / "promo_videos"

        cmd = [
            sys.executable,
            str(script_dir / "generate_promo_video.py"),
            "--batch", str(mastered_dir),
            "--style", args.style,
            "-o", str(promo_dir)
        ]

        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.warning("Track promo generation had errors")
            success = False

        print()

    # Generate album sampler
    if not args.tracks_only:
        print("=" * 50)
        print("GENERATING ALBUM SAMPLER")
        print("=" * 50)

        sampler_output = album_dir / "promo_videos" / "album_sampler.mp4"

        cmd = [
            sys.executable,
            str(script_dir / "generate_album_sampler.py"),
            str(mastered_dir),
            "--artwork", str(artwork),
            "--clip-duration", str(args.clip_duration),
            "-o", str(sampler_output)
        ]

        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.warning("Album sampler generation had errors")
            success = False

        print()

    # Summary
    print("=" * 50)
    print("COMPLETE")
    print("=" * 50)

    if not args.sampler_only:
        promo_dir = album_dir / "promo_videos"
        promo_count = sum(1 for f in promo_dir.glob("*.mp4")) if promo_dir.exists() else 0
        print(f"Track promos: {promo_dir}")
        print(f"  {promo_count} videos generated")

    if not args.tracks_only:
        sampler = album_dir / "promo_videos" / "album_sampler.mp4"
        if sampler.exists():
            size_mb = sampler.stat().st_size / (1024 * 1024)
            print(f"Album sampler: {sampler}")
            print(f"  {size_mb:.1f} MB")

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
