#!/usr/bin/env python3
"""
fix_titles.py - Strip track numbers from MusicXML titles and re-export PDFs

This script:
1. Reads MusicXML files
2. Strips track number prefixes from titles (e.g., "01 - Song Name" → "Song Name")
3. Saves the updated XML
4. Uses MuseScore CLI to re-export as PDF

Cross-platform version with enhanced OS detection.

Usage:
    python3 fix_titles.py /path/to/sheet-music/
    python3 fix_titles.py /path/to/sheet-music/ --dry-run
    python3 fix_titles.py /path/to/sheet-music/ --xml-only
"""

import argparse
import logging
import platform
import re
import subprocess
import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging

logger = logging.getLogger(__name__)


def strip_track_number(name):
    """Remove track number prefix from title.

    Handles patterns like:
    - "01 - Track Name"
    - "01-Track Name"
    - "1 - Track Name"
    - "01. Track Name"
    """
    pattern = r'^\d+\s*[-.\s]+\s*'
    return re.sub(pattern, '', name)


def fix_xml_title(xml_path, dry_run=False):
    """Fix the title in a MusicXML file."""
    with open(xml_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find and replace work-title
    match = re.search(r'<work-title>([^<]+)</work-title>', content)
    if not match:
        logger.warning("  No <work-title> found in %s", xml_path.name)
        return None

    old_title = match.group(1)
    new_title = strip_track_number(old_title)

    if old_title == new_title:
        logger.info("  %s: title already clean", xml_path.name)
        return None

    print(f"  {old_title} → {new_title}")

    if not dry_run:
        new_content = content.replace(
            f'<work-title>{old_title}</work-title>',
            f'<work-title>{new_title}</work-title>'
        )
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return new_title


def find_musescore():
    """Find MuseScore executable based on OS"""
    system = platform.system().lower()

    # Platform-specific paths
    paths = {
        'darwin': [
            "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
            "/Applications/MuseScore 3.app/Contents/MacOS/mscore",
            "/opt/homebrew/bin/mscore",
            "/usr/local/bin/mscore",
        ],
        'linux': [
            "/usr/bin/musescore4",
            "/usr/bin/musescore",
            "/usr/local/bin/musescore",
            "/usr/bin/mscore",
        ],
        'windows': [
            r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
            r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe",
            r"C:\Program Files (x86)\MuseScore 4\bin\MuseScore4.exe",
            r"C:\Program Files (x86)\MuseScore 3\bin\MuseScore3.exe",
        ]
    }

    # Check known paths
    for path in paths.get(system, []):
        if Path(path).exists():
            return path

    # Try PATH
    try:
        cmd = ['which', 'mscore'] if system != 'windows' else ['where', 'mscore']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass

    # Try alternative names
    try:
        cmd = ['which', 'musescore'] if system != 'windows' else ['where', 'musescore']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass

    return None


def show_install_instructions(system):
    """Show OS-specific MuseScore install instructions"""
    print("\nMuseScore not found. Install from: https://musescore.org/\n")

    if system == 'darwin':
        print("macOS installation:")
        print("  1. Download from https://musescore.org/")
        print("  2. Or: brew install --cask musescore")
        print("\nAfter installing, MuseScore should be at:")
        print("  /Applications/MuseScore 4.app/Contents/MacOS/mscore")
    elif system == 'linux':
        print("Linux installation:")
        print("  Ubuntu/Debian: sudo apt install musescore")
        print("  Fedora: sudo dnf install musescore")
        print("  Arch: sudo pacman -S musescore")
        print("  Or download AppImage from https://musescore.org/")
    elif system == 'windows':
        print("Windows installation:")
        print("  Download installer from https://musescore.org/")
        print("\nAfter installing, MuseScore should be at:")
        print("  C:\\Program Files\\MuseScore 4\\bin\\MuseScore4.exe")

    print("\nMuseScore is free and open source.")


def export_pdf(xml_path, musescore_path, dry_run=False):
    """Export MusicXML to PDF using MuseScore."""
    pdf_path = xml_path.with_suffix('.pdf')

    if dry_run:
        logger.info("  Would export: %s", pdf_path.name)
        return True

    try:
        # MuseScore CLI: mscore -o output.pdf input.xml
        result = subprocess.run(
            [musescore_path, '-o', str(pdf_path), str(xml_path)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            logger.info("  Exported: %s", pdf_path.name)
            return True
        else:
            logger.error("  Export failed: %s", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("  Export timed out: %s", xml_path.name)
        return False
    except Exception as e:
        logger.error("  Export error: %s", e)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Fix track number prefixes in MusicXML titles and re-export PDFs'
    )
    parser.add_argument('source_dir', help='Directory containing XML files')
    parser.add_argument('--dry-run', '-n', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--xml-only', action='store_true',
                       help='Only fix XML titles, skip PDF export')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show debug output')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Only show warnings and errors')

    args = parser.parse_args()

    setup_logging(__name__, verbose=getattr(args, 'verbose', False), quiet=getattr(args, 'quiet', False))

    source_path = Path(args.source_dir)
    if not source_path.is_dir():
        logger.error("%s is not a directory", args.source_dir)
        sys.exit(1)

    # Find MuseScore
    musescore = None
    if not args.xml_only:
        musescore = find_musescore()
        if not musescore:
            logger.warning("MuseScore not found.")
            show_install_instructions(platform.system().lower())
            print("\nOptions:")
            print("  1. Install MuseScore and run this script again")
            print("  2. Use --xml-only to skip PDF export (just fix XML titles)")
            sys.exit(1)
        logger.info("Using MuseScore: %s", musescore)

    # Find XML files (only those starting with digits)
    xml_files = sorted([
        f for f in source_path.glob("*.xml")
        if re.match(r'^\d+', f.stem)
    ])

    # Also check for .musicxml extension
    musicxml_files = sorted([
        f for f in source_path.glob("*.musicxml")
        if re.match(r'^\d+', f.stem)
    ])

    xml_files.extend(musicxml_files)

    if not xml_files:
        logger.error("No XML files found in %s", source_path)
        logger.error("Looking for files like: 01-track.xml, 02-track.musicxml")
        sys.exit(1)

    print(f"Found {len(xml_files)} XML file(s)")
    if args.dry_run:
        print("DRY RUN - no changes will be made\n")

    # Process each file
    print("\nFixing titles...")
    fixed_count = 0
    for xml_file in xml_files:
        result = fix_xml_title(xml_file, args.dry_run)
        if result:
            fixed_count += 1

    print(f"\nFixed {fixed_count} title(s)")

    # Export PDFs
    if not args.xml_only and fixed_count > 0:
        logger.info("Exporting PDFs...")
        export_count = 0
        for xml_file in xml_files:
            if export_pdf(xml_file, musescore, args.dry_run):
                export_count += 1
        print(f"\nExported {export_count} PDF(s)")

    print("\nDone!")


if __name__ == '__main__':
    main()
