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
    python3 transcribe.py shell-no

    # By path (direct)
    python3 transcribe.py /path/to/mastered/

    # Options
    python3 transcribe.py shell-no --pdf-only
    python3 transcribe.py /path/to/mastered/ --midi --dry-run
"""

import argparse
import os
import platform
import subprocess
import sys
import yaml
from pathlib import Path


# ANSI colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color

    @classmethod
    def disable(cls):
        """Disable colors (for non-TTY)"""
        cls.RED = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.NC = ''


if not sys.stdout.isatty():
    Colors.disable()


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
    except:
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
        print(f"After installing, AnthemScore should be at:")
        print(f"  /Applications/AnthemScore.app/Contents/MacOS/AnthemScore")
    elif system == 'linux':
        print(f"After installing, AnthemScore should be at:")
        print(f"  /usr/bin/anthemscore or /usr/local/bin/anthemscore")
    elif system == 'windows':
        print(f"After installing, AnthemScore should be at:")
        print(f"  C:\\Program Files\\AnthemScore\\AnthemScore.exe")

    print(f"\nThen run this command again.")


def read_config():
    """Read ~/.bitwize-music/config.yaml"""
    config_path = Path.home() / '.bitwize-music' / 'config.yaml'

    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"{Colors.RED}Error reading config: {e}{Colors.NC}")
        return None


def resolve_album_path(album_name):
    """Resolve album name to audio path using config"""
    config = read_config()

    if not config:
        print(f"{Colors.YELLOW}Config not found at ~/.bitwize-music/config.yaml{Colors.NC}")
        print("Treating as direct path instead of album name.\n")
        return None

    try:
        audio_root = config['paths']['audio_root']
        artist = config['artist']['name']

        # Expand ~ to home directory
        audio_root = Path(audio_root).expanduser()

        # Construct: {audio_root}/{artist}/{album}/
        album_path = audio_root / artist / album_name

        if not album_path.exists():
            print(f"{Colors.YELLOW}Album path not found: {album_path}{Colors.NC}")
            print("Treating as direct path instead.\n")
            return None

        return album_path

    except KeyError as e:
        print(f"{Colors.YELLOW}Config missing key: {e}{Colors.NC}")
        return None


def get_wav_files(source):
    """Get list of WAV files from source (file or directory)"""
    source_path = Path(source)

    if source_path.is_file():
        if source_path.suffix.lower() == '.wav':
            return [source_path], source_path.parent
        else:
            print(f"{Colors.RED}Error: {source} is not a WAV file{Colors.NC}")
            sys.exit(1)
    elif source_path.is_dir():
        wav_files = sorted(source_path.glob('*.wav'))
        if not wav_files:
            print(f"{Colors.RED}Error: No WAV files found in {source}{Colors.NC}")
            sys.exit(1)
        return wav_files, source_path
    else:
        print(f"{Colors.RED}Error: {source} does not exist{Colors.NC}")
        sys.exit(1)


def transcribe_track(anthemscore, wav_file, output_dir, args):
    """Transcribe a single WAV file"""
    basename = wav_file.stem

    print(f"{Colors.YELLOW}Processing: {wav_file.name}{Colors.NC}")

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
        print(f"  Would run: {' '.join(cmd)}")
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
            print(f"  {Colors.GREEN}[OK] Complete{Colors.NC}")
            if args.pdf:
                print(f"    → {output_dir / f'{basename}.pdf'}")
            if args.xml:
                print(f"    → {output_dir / f'{basename}.xml'}")
            if args.midi:
                print(f"    → {output_dir / f'{basename}.mid'}")
            return True
        else:
            print(f"  {Colors.RED}[FAIL] Failed{Colors.NC}")
            if result.stderr:
                print(f"  Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  {Colors.RED}[FAIL] Timed out (>5 minutes){Colors.NC}")
        return False
    except Exception as e:
        print(f"  {Colors.RED}[FAIL] Error: {e}{Colors.NC}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Batch convert WAV files to sheet music using AnthemScore',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s shell-no                    # By album name (reads config)
  %(prog)s /path/to/mastered/          # By path
  %(prog)s track.wav --pdf-only        # Single file, PDF only
  %(prog)s shell-no --midi --dry-run   # Preview with MIDI
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

    args = parser.parse_args()

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
            print(f"{Colors.RED}Error: Source not found: {args.source}{Colors.NC}\n")
            print("Tried:")
            print(f"  1. Direct path: {args.source}")
            config = read_config()
            if config:
                try:
                    audio_root = Path(config['paths']['audio_root']).expanduser()
                    artist = config['artist']['name']
                    print(f"  2. Album path: {audio_root}/{artist}/{args.source}")
                except:
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
        print(f"Clef:    Treble only")
    elif args.bass:
        print(f"Clef:    Bass only")
    print()

    # Create output directory
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Process each file
    success_count = 0
    failed_count = 0

    for wav_file in wav_files:
        if transcribe_track(anthemscore, wav_file, output_dir, args):
            success_count += 1
        else:
            failed_count += 1
        print()

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
