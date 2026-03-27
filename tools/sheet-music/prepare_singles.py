#!/usr/bin/env python3
"""
prepare_singles.py - Prepare consumer-ready sheet music singles from source files

This script:
1. Reads numbered source files from a source/ directory
2. Applies smart title casing (e.g., "01-ocean-of-tears" → "Ocean of Tears")
3. Updates <work-title> in MusicXML files
4. Writes clean-named files to a sibling singles/ directory
5. Optionally re-exports PDFs via MuseScore CLI
6. Creates .manifest.json for track ordering

Source files are NEVER modified (non-destructive).

Usage:
    python3 prepare_singles.py /path/to/sheet-music/source/
    python3 prepare_singles.py /path/to/sheet-music/source/ --dry-run
    python3 prepare_singles.py /path/to/sheet-music/source/ --xml-only

Backward compatibility:
    If given a flat sheet-music/ directory (no source/ subdir), treats it as source.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging
from tools.shared.text_utils import slug_to_title

logger = logging.getLogger(__name__)


def find_musescore() -> str | None:
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
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Try alternative names
    try:
        cmd = ['which', 'musescore'] if system != 'windows' else ['where', 'musescore']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return None


def show_install_instructions(system: str) -> None:
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


def export_pdf(xml_path: Path, pdf_path: Path, musescore_path: str, dry_run: bool = False) -> bool:
    """Export MusicXML to PDF using MuseScore."""
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


def _extract_track_number(stem: str) -> int | None:
    """Extract numeric track number from a filename stem like '01-ocean-of-tears'."""
    match = re.match(r'^(\d+)', stem)
    return int(match.group(1)) if match else None


def prepare_xml(source_xml: Path, singles_dir: Path, title: str, dry_run: bool = False, output_name: str | None = None) -> Path:
    """Update <work-title> in MusicXML and write to singles/ with clean filename.

    Args:
        source_xml: Path to source XML file
        singles_dir: Output directory
        title: Clean track title (used for <work-title> tag)
        dry_run: If True, don't write files
        output_name: Output filename stem (without extension). Defaults to title.

    Returns the output path on success, None on failure.
    Source file is never modified.
    """
    out_stem = output_name or title

    with open(source_xml, encoding='utf-8') as f:
        content = f.read()

    # Update work-title
    match = re.search(r'<work-title>([^<]+)</work-title>', content)
    if match:
        old_title = match.group(1)
        content = content.replace(
            f'<work-title>{old_title}</work-title>',
            f'<work-title>{title}</work-title>'
        )
        print(f"  XML title: {old_title} -> {title}")
    else:
        logger.warning("  No <work-title> found in %s, writing as-is", source_xml.name)

    out_path = singles_dir / f"{out_stem}{source_xml.suffix}"
    if not dry_run:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)
    return out_path


def _add_title_page_and_footer(pdf_path: Path, title: str, artist: str | None, cover_image: str | None, footer_url: str | None, page_size_name: str) -> None:
    """Prepend a title page and add footer URL to every page of a single PDF.

    Uses shared helpers from create_songbook module. Gracefully skips
    if pypdf/reportlab are not available (they're optional deps).
    """
    try:
        # Late import — songbook module needs pypdf/reportlab
        import importlib.util
        songbook_path = Path(__file__).parent / "create_songbook.py"
        spec = importlib.util.spec_from_file_location("create_songbook", songbook_path)
        if spec is None or spec.loader is None:
            raise ImportError("Cannot load create_songbook")
        songbook_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(songbook_mod)

        from pypdf import PdfReader, PdfWriter

        page_size = songbook_mod.PAGE_SIZES.get(page_size_name, songbook_mod.PAGE_SIZES["letter"])
        reader = PdfReader(str(pdf_path))
        writer = PdfWriter()

        # Add title page
        title_page = songbook_mod.create_single_title_page(
            title, artist or "", page_size,
            cover_image=cover_image, footer_url=footer_url,
        )
        writer.add_page(title_page)

        # Add content pages with footer overlay
        footer_page = None
        if footer_url:
            footer_page = songbook_mod.create_footer_overlay(page_size, footer_url)

        for page in reader.pages:
            if footer_page:
                page.merge_page(footer_page)
            writer.add_page(page)

        with open(str(pdf_path), "wb") as f:
            writer.write(f)

        logger.info("  Added title page + footer to %s", pdf_path.name)
    except ImportError:
        logger.warning("  pypdf/reportlab not installed — skipping title page and footer for %s", pdf_path.name)
    except Exception as e:
        logger.warning("  Could not add title page to %s: %s", pdf_path.name, e)


def resolve_source_dir(given_path: str | Path) -> tuple[Path, Path]:
    """Resolve the source directory, handling backward compatibility.

    If given a path ending in source/, use it directly.
    If given a sheet-music/ dir that contains a source/ subdir, use source/.
    If given a flat sheet-music/ dir with numbered files, use it as source (backward compat).
    """
    given = Path(given_path)

    # Already pointing at source/
    if given.name == 'source' and given.is_dir():
        return given, given.parent / 'singles'

    # Has a source/ subdirectory
    source_sub = given / 'source'
    if source_sub.is_dir():
        return source_sub, given / 'singles'

    # Flat layout (backward compat) — check if it has numbered XML files
    has_numbered = any(
        re.match(r'^\d+', f.stem) for f in given.glob("*.xml")
    ) or any(
        re.match(r'^\d+', f.stem) for f in given.glob("*.musicxml")
    )
    if has_numbered:
        logger.info("Using flat directory as source (backward compatibility): %s", given)
        return given, given / 'singles'

    return given, given / 'singles'


def _read_source_manifest(source_path: Path) -> dict[str, Any] | None:
    """Read .manifest.json from source directory if it exists.

    Returns manifest dict or None.
    """
    manifest_path = source_path / ".manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, encoding='utf-8') as f:
                data: dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read source manifest: %s", e)
    return None


def prepare_singles(source_dir: str | Path, singles_dir: str | Path, musescore: str | None = None, dry_run: bool = False, xml_only: bool = False,
                     artist: str | None = None, cover_image: str | None = None, footer_url: str | None = None, page_size_name: str = "letter",
                     title_map: dict[str, str] | None = None) -> dict[str, object]:
    """Prepare consumer-ready singles from source files.

    Supports two source layouts:
    - **New flow** (manifest present): Source files have clean titles (e.g., "First Pour.pdf").
      Reads .manifest.json for ordering and titles.
    - **Legacy flow** (no manifest): Source files are numbered (e.g., "01-first-pour.pdf").
      Derives titles from slugs.

    Output files are numbered: "01 - First Pour.pdf", "02 - Running on Vapors.pdf", etc.

    Each single PDF gets a title page prepended (with cover art if available)
    and a footer URL on every page.

    Args:
        title_map: Optional dict {slug: title} to override slug_to_title() derivation.

    Returns dict with results including manifest entries.
    """
    source_path = Path(source_dir)
    singles_path = Path(singles_dir)

    # Check for source manifest (new flow: clean-titled files from transcribe_audio)
    source_manifest = _read_source_manifest(source_path)

    if source_manifest:
        # --- New flow: manifest-based, clean-titled source files ---
        track_entries = source_manifest.get("tracks", [])
        if not track_entries:
            logger.error("Source manifest has no tracks in %s", source_path)
            return {"error": "Source manifest has no tracks"}

        # Build lookup of source files by title
        xml_by_title = {}
        for f in source_path.glob("*.xml"):
            xml_by_title[f.stem] = f
        for f in source_path.glob("*.musicxml"):
            xml_by_title[f.stem] = f
        pdf_by_title = {f.stem: f for f in source_path.glob("*.pdf")}
        mid_by_title = {f.stem: f for f in source_path.glob("*.mid")}

        ordered_tracks: list[tuple[int | None, str, str]] = []
        for entry in track_entries:
            title = str(entry.get("title", ""))
            source_slug = str(entry.get("source_slug", ""))
            track_num: int | None = entry.get("number")
            ordered_tracks.append((track_num, source_slug, title))
    else:
        # --- Legacy flow: numbered source files ---
        xml_files = sorted([
            f for f in source_path.glob("*.xml")
            if re.match(r'^\d+', f.stem)
        ])
        musicxml_files = sorted([
            f for f in source_path.glob("*.musicxml")
            if re.match(r'^\d+', f.stem)
        ])
        xml_files.extend(musicxml_files)

        pdf_files_legacy = {f.stem: f for f in source_path.glob("*.pdf") if re.match(r'^\d+', f.stem)}
        mid_files_legacy = {f.stem: f for f in source_path.glob("*.mid") if re.match(r'^\d+', f.stem)}

        all_stems = set()
        for f in xml_files:
            all_stems.add(f.stem)
        all_stems.update(pdf_files_legacy.keys())
        all_stems.update(mid_files_legacy.keys())

        if not all_stems:
            logger.error("No numbered files found in %s", source_path)
            return {"error": "No numbered source files found"}

        ordered_stems = sorted(all_stems)
        ordered_tracks = []
        for stem in ordered_stems:
            track_num = _extract_track_number(stem)
            if title_map and stem in title_map:
                title = title_map[stem]
            else:
                title = slug_to_title(stem)
            ordered_tracks.append((track_num, stem, title))

        # Map legacy files by stem for lookup
        xml_by_title = {f.stem: f for f in xml_files}
        pdf_by_title = pdf_files_legacy
        mid_by_title = mid_files_legacy

    if not dry_run:
        singles_path.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(ordered_tracks)} track(s) in source")
    if dry_run:
        print("DRY RUN - no changes will be made\n")

    manifest_tracks = []
    xml_processed = {}  # singles_name -> singles XML path (for PDF re-export)
    results = []

    for track_num, source_slug, title in ordered_tracks:
        # Determine the lookup key for source files
        if source_manifest:
            lookup_key = title  # Clean-titled source files
        else:
            lookup_key = source_slug  # Numbered source files

        # Build numbered output filename: "01 - First Pour"
        if track_num is not None:
            singles_name = f"{track_num:02d} - {title}"
        else:
            singles_name = title

        print(f"\n  [{lookup_key}] -> \"{singles_name}\"")

        manifest_tracks.append({
            "number": track_num,
            "source_slug": source_slug,
            "title": title,
            "filename": singles_name,
        })

        track_result: dict[str, Any] = {"source": source_slug, "title": title, "filename": singles_name, "files": []}

        # Process XML/MusicXML
        xml_match = xml_by_title.get(lookup_key)
        if xml_match:
            out_xml = prepare_xml(xml_match, singles_path, title, dry_run, output_name=singles_name)
            if out_xml:
                xml_processed[singles_name] = out_xml
                track_result["files"].append(str(out_xml.name))

        # Process PDF
        pdf_src = pdf_by_title.get(lookup_key)
        if pdf_src:
            pdf_dst = singles_path / f"{singles_name}.pdf"
            pdf_written = False

            if xml_match and musescore and not xml_only:
                cached_xml = xml_processed.get(singles_name)
                if cached_xml and not dry_run:
                    exported = export_pdf(cached_xml, pdf_dst, musescore, dry_run)
                    if exported:
                        pdf_written = True
                    else:
                        logger.warning("  PDF re-export failed, copying source PDF")
                        shutil.copy2(pdf_src, pdf_dst)
                        pdf_written = True
                elif dry_run:
                    logger.info("  Would export PDF: %s", pdf_dst.name)
                    track_result["files"].append(pdf_dst.name)
            else:
                if not xml_only:
                    if not musescore and xml_match:
                        logger.warning("  No MuseScore available, copying source PDF (title may show track number)")
                    if not dry_run:
                        shutil.copy2(pdf_src, pdf_dst)
                        pdf_written = True
                    else:
                        track_result["files"].append(pdf_dst.name)

            # Add title page and footer to the PDF
            if pdf_written and not dry_run:
                _add_title_page_and_footer(
                    pdf_dst, title, artist, cover_image, footer_url, page_size_name
                )
                track_result["files"].append(pdf_dst.name)

        # Process MIDI
        mid_src = mid_by_title.get(lookup_key)
        if mid_src:
            mid_dst = singles_path / f"{singles_name}.mid"
            if not dry_run:
                shutil.copy2(mid_src, mid_dst)
            track_result["files"].append(mid_dst.name)

        results.append(track_result)

    # Write manifest
    manifest = {"tracks": manifest_tracks}
    manifest_path = singles_path / ".manifest.json"
    if not dry_run:
        with open(manifest_path, 'w', encoding='utf-8') as mf:
            json.dump(manifest, mf, indent=2)
        print(f"\nWrote manifest: {manifest_path}")

    print(f"\nPrepared {len(results)} track(s) in {singles_path}")
    return {"tracks": results, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Prepare consumer-ready sheet music singles from numbered source files'
    )
    parser.add_argument('source_dir',
                        help='Directory containing numbered source files (source/ or flat sheet-music/)')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--xml-only', action='store_true',
                        help='Only process XML files, skip PDF export and copy')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show debug output')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Only show warnings and errors')

    args = parser.parse_args()

    setup_logging(__name__, verbose=getattr(args, 'verbose', False), quiet=getattr(args, 'quiet', False))

    source_path, singles_path = resolve_source_dir(args.source_dir)
    if not source_path.is_dir():
        logger.error("%s is not a directory", source_path)
        sys.exit(1)

    # Find MuseScore
    musescore = None
    if not args.xml_only:
        musescore = find_musescore()
        if not musescore:
            logger.warning("MuseScore not found — PDFs will be copied from source (titles may show track numbers).")
            show_install_instructions(platform.system().lower())
            print("\nContinuing without MuseScore (XML titles will still be updated)...\n")
        else:
            logger.info("Using MuseScore: %s", musescore)

    # Read config for artist, cover art, footer URL
    artist = None
    cover_image = None
    footer_url = None
    page_size_name = "letter"
    try:
        from tools.shared.config import load_config
        config = load_config()
        if config:
            artist = config.get('artist', {}).get('name')
            page_size_name = config.get('sheet_music', {}).get('page_size', 'letter')
            footer_url = config.get('sheet_music', {}).get('footer_url')
            if not footer_url:
                # Fall back to urls section
                urls = config.get('urls', {})
                for key in ['website', 'soundcloud', 'bandcamp', 'spotify']:
                    if key in urls:
                        footer_url = urls[key].rstrip('/')
                        break
    except Exception:
        pass

    # Auto-detect cover art by walking up from source dir
    try:
        import importlib.util
        songbook_path = Path(__file__).parent / "create_songbook.py"
        spec = importlib.util.spec_from_file_location("create_songbook", songbook_path)
        if spec is None or spec.loader is None:
            raise ImportError("Cannot load create_songbook")
        songbook_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(songbook_mod)
        cover_image = songbook_mod.auto_detect_cover_art(str(source_path))
    except Exception:
        pass

    result = prepare_singles(
        source_dir=source_path,
        singles_dir=singles_path,
        musescore=musescore,
        dry_run=args.dry_run,
        xml_only=args.xml_only,
        artist=artist,
        cover_image=cover_image,
        footer_url=footer_url,
        page_size_name=page_size_name,
    )

    if "error" in result:
        logger.error(result["error"])
        sys.exit(1)

    print("\nDone!")


if __name__ == '__main__':
    main()
