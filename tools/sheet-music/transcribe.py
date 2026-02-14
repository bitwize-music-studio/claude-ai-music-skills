#!/usr/bin/env python3
"""
transcribe.py - Batch convert WAV files to sheet music using AnthemScore

Cross-platform version of transcribe.sh with config integration.

Usage:
    python3 transcribe.py <album-name>
    python3 transcribe.py /path/to/wav/files
    python3 transcribe.py /path/to/single/track.wav

Options:
    --pdf-only      Only generate PDF (skip MusicXML)
    --xml-only      Only generate MusicXML (skip PDF)
    --midi          Also generate MIDI files
    --treble        Treble clef only
    --bass          Bass clef only
    --output DIR    Output directory (default: sheet-music/ in source dir)
    --dry-run       Show what would be done without doing it

Examples:
    # By album name (reads config)
    python3 transcribe.py sample-album

    # By path (direct)
    python3 transcribe.py /path/to/mastered/

    # Options
    python3 transcribe.py sample-album --pdf-only
    python3 transcribe.py /path/to/mastered/ --midi --dry-run
"""

import argparse
import os
import platform
import subprocess
import sys
try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required. Install: pip install pyyaml")
    sys.exit(1)
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from tools.shared.colors import Colors
from tools.shared.logging_config import setup_logging
from tools.shared.progress import ProgressBar

logger = logging.getLogger(__name__)

Colors.auto()


def find_anthemscore():
    """Detect AnthemScore based on OS"""
    system = platform.system().lower()

    # Platform-specific paths
    paths = {
        'darwin': [
            '/Applications/AnthemScore.app/Contents/MacOS/AnthemScore',
        ],
        'linux': [
            '/usr/bin/anthemscore',
            '/usr/local/bin/anthemscore',
        ],
        'windows': [
            r'C:\Program Files\AnthemScore\AnthemScore.exe',
            r'C:\Program Files (x86)\AnthemScore\AnthemScore.exe',
        ]
    }

    # Check known paths for this OS
    for path in paths.get(system, []):
        if Path(path).exists():
            return path

    # Try PATH
    try:
        result = subprocess.run(
            ['which', 'anthemscore'] if system != 'windows' else ['where', 'anthemscore'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return None


def show_install_instructions(system):
    """Show OS-specific installation instructions"""
    print(f"{Colors.RED}AnthemScore not found on your system.{Colors.NC}\n")
    print("Install from: https://www.lunaverus.com/\n")
    print("Editions:")
    print("  - Lite: $31 (basic transcription, no editing)")
    print("  - Professional: $42 (full editing + CLI) ← Recommended")
    print("  - Studio: $107 (lifetime updates)\n")
    print("Free trial: 30 seconds per song, 100 total transcriptions\n")

    if system == 'darwin':
        print("After installing, AnthemScore should be at:")
        print("  /Applications/AnthemScore.app/Contents/MacOS/AnthemScore")
    elif system == 'linux':
        print("After installing, AnthemScore should be at:")
        print("  /usr/bin/anthemscore or /usr/local/bin/anthemscore")
    elif system == 'windows':
        print("After installing, AnthemScore should be at:")
        print("  C:\\Program Files\\AnthemScore\\AnthemScore.exe")

    print("\nThen run this command again.")


def read_config():
    """Read ~/.bitwize-music/config.yaml"""
    from tools.shared.config import load_config
    return load_config()


def resolve_album_path(album_name):
    """Resolve album name to audio path using config"""
    config = read_config()

    if not config:
        logger.warning("Config not found at ~/.bitwize-music/config.yaml")
        logger.warning("Treating as direct path instead of album name.")
        return None

    try:
        audio_root = config['paths']['audio_root']
        artist = config['artist']['name']

        # Expand ~ to home directory
        audio_root = Path(audio_root).expanduser()

        # Construct: {audio_root}/artists/{artist}/albums/{genre}/{album}/
        album_path = audio_root / artist / album_name

        if not album_path.exists():
            logger.warning("Album path not found: %s", album_path)
            logger.warning("Treating as direct path instead.")
            return None

        # Validate resolved path stays within audio_root (prevent path traversal)
        try:
            album_path.resolve().relative_to(audio_root.resolve())
        except ValueError:
            logger.error("Album path resolves outside audio_root (possible path traversal): %s", album_path)
            return None

        return album_path

    except KeyError as e:
        logger.warning("Config missing key: %s", e)
        return None


def get_wav_files(source):
    """Get list of WAV files from source (file or directory)"""
    source_path = Path(source)

    if source_path.is_file():
        if source_path.suffix.lower() == '.wav':
            return [source_path], source_path.parent
        else:
            logger.error("%s is not a WAV file", source)
            sys.exit(1)
    elif source_path.is_dir():
        wav_files = sorted(source_path.glob('*.wav'))
        if not wav_files:
            logger.error("No WAV files found in %s", source)
            sys.exit(1)
        return wav_files, source_path
    else:
        logger.error("%s does not exist", source)
        sys.exit(1)


def transcribe_track(anthemscore, wav_file, output_dir, args):
    """Transcribe a single WAV file"""
    basename = wav_file.stem

    logger.info("Processing: %s", wav_file.name)

    # Build command
    cmd = [anthemscore, str(wav_file), '-a']  # -a = headless mode

    if args.pdf:
        cmd.extend(['-p', str(output_dir / f"{basename}.pdf")])

    if args.xml:
        cmd.extend(['-x', str(output_dir / f"{basename}.xml")])

    if args.midi:
        cmd.extend(['-m', str(output_dir / f"{basename}.mid")])

    if args.treble:
        cmd.append('-t')

    if args.bass:
        cmd.append('-b')

    if args.dry_run:
        logger.info("  Would run: %s", ' '.join(cmd))
        return True

    # Run AnthemScore
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            logger.info("  [OK] Complete")
            if args.pdf:
                logger.info("    -> %s", output_dir / f'{basename}.pdf')
            if args.xml:
                logger.info("    -> %s", output_dir / f'{basename}.xml')
            if args.midi:
                logger.info("    -> %s", output_dir / f'{basename}.mid')
            return True
        else:
            logger.error("  [FAIL] Failed")
            if result.stderr:
                logger.error("  Error: %s", result.stderr)
            return False

    except subprocess.TimeoutExpired:
        logger.error("  [FAIL] Timed out (>5 minutes)")
        return False
    except Exception as e:
        logger.error("  [FAIL] Error: %s", e)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Batch convert WAV files to sheet music using AnthemScore',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sample-album                    # By album name (reads config)
  %(prog)s /path/to/mastered/          # By path
  %(prog)s track.wav --pdf-only        # Single file, PDF only
  %(prog)s sample-album --midi --dry-run   # Preview with MIDI
        """
    )

    parser.add_argument(
        'source',
        help='Album name (from config), directory with WAVs, or single WAV file'
    )
    parser.add_argument(
        '--pdf-only',
        action='store_true',
        help='Only generate PDF (skip MusicXML)'
    )
    parser.add_argument(
        '--xml-only',
        action='store_true',
        help='Only generate MusicXML (skip PDF)'
    )
    parser.add_argument(
        '--midi',
        action='store_true',
        help='Also generate MIDI files'
    )
    parser.add_argument(
        '--treble',
        action='store_true',
        help='Treble clef only'
    )
    parser.add_argument(
        '--bass',
        action='store_true',
        help='Bass clef only'
    )
    parser.add_argument(
        '--output',
        help='Output directory (default: sheet-music/ in source dir)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show debug output'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Only show warnings and errors'
    )
    parser.add_argument(
        '-j', '--jobs', type=int, default=1,
        help='Parallel jobs (0=auto, default: 1)'
    )

    args = parser.parse_args()

    setup_logging(__name__, verbose=getattr(args, 'verbose', False), quiet=getattr(args, 'quiet', False))

    # Determine output formats
    if args.pdf_only:
        args.pdf = True
        args.xml = False
    elif args.xml_only:
        args.pdf = False
        args.xml = True
    else:
        args.pdf = True
        args.xml = True

    # Find AnthemScore
    anthemscore = find_anthemscore()
    if not anthemscore:
        show_install_instructions(platform.system().lower())
        sys.exit(1)

    # Resolve source (album name or path)
    source = args.source
    if not os.path.exists(source):
        # Try resolving as album name
        album_path = resolve_album_path(source)
        if album_path:
            source = album_path
        else:
            logger.error("Source not found: %s", args.source)
            logger.error("Tried:")
            logger.error("  1. Direct path: %s", args.source)
            config = read_config()
            if config:
                try:
                    audio_root = Path(config['paths']['audio_root']).expanduser()
                    artist = config['artist']['name']
                    logger.error("  2. Album path: %s/%s/%s", audio_root, artist, args.source)
                except (KeyError, TypeError):
                    pass
            sys.exit(1)

    # Get WAV files
    wav_files, source_dir = get_wav_files(source)

    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = source_dir / 'sheet-music'

    # Show summary
    print(f"{Colors.GREEN}AnthemScore Batch Transcription{Colors.NC}")
    print("=" * 40)
    print(f"Source:  {source_dir}")
    print(f"Output:  {output_dir}")
    print(f"Files:   {len(wav_files)} WAV file(s)")
    formats = []
    if args.pdf:
        formats.append("PDF")
    if args.xml:
        formats.append("MusicXML")
    if args.midi:
        formats.append("MIDI")
    print(f"Format:  {' '.join(formats)}")
    if args.treble:
        print("Clef:    Treble only")
    elif args.bass:
        print("Clef:    Bass only")
    print()

    # Create output directory
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Process each file
    success_count = 0
    failed_count = 0
    workers = args.jobs if args.jobs > 0 else (os.cpu_count() or 1)

    progress = ProgressBar(len(wav_files), prefix="Transcribing")

    if workers == 1:
        for wav_file in wav_files:
            progress.update(wav_file.name)
            if transcribe_track(anthemscore, wav_file, output_dir, args):
                success_count += 1
            else:
                failed_count += 1
            print()
    else:
        logger.info("Using %d parallel workers", workers)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(transcribe_track, anthemscore, wf, output_dir, args): wf
                for wf in wav_files
            }
            for future in as_completed(futures):
                wf = futures[future]
                progress.update(wf.name)
                if future.result():
                    success_count += 1
                else:
                    failed_count += 1

    # Summary
    print("=" * 40)
    print(f"{Colors.GREEN}Complete: {success_count}{Colors.NC} | {Colors.RED}Failed: {failed_count}{Colors.NC}")
    print()
    print(f"Output directory: {output_dir}")

    if args.xml and not args.dry_run and success_count > 0:
        print()
        print("Next steps:")
        print("  1. Review/edit MusicXML files in MuseScore")
        print("  2. Add dynamics, fix notation errors")
        print("  3. Run fix_titles.py to clean up titles")
        print("  4. Export final PDFs from MuseScore")

    sys.exit(failed_count)


if __name__ == '__main__':
    main()
