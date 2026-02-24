#!/usr/bin/env python3
"""
create_songbook.py - Combine sheet music PDFs into a distribution-ready songbook

Enhanced version with config integration for automatic metadata detection.
Reads from singles/ directory (or flat layout for backward compatibility).

Usage:
    python3 create_songbook.py /path/to/sheet-music/singles/ --title "Album Songbook" --artist "Artist Name"

    # With config integration (auto-detects artist, cover art):
    python3 create_songbook.py /path/to/sheet-music/singles/ --title "Album Songbook"

Requirements:
    pip install pypdf reportlab pyyaml
"""

import argparse
import json
import logging
import os
import re
import sys
try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required. Install: pip install pyyaml")
    sys.exit(1)
from pathlib import Path
from datetime import datetime

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging

logger = logging.getLogger(__name__)


from tools.shared.text_utils import strip_track_number  # noqa: E402


try:
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    import io
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install pypdf reportlab")
    sys.exit(1)


# Page sizes
PAGE_SIZES = {
    "letter": (8.5 * inch, 11 * inch),
    "9x12": (9 * inch, 12 * inch),
    "6x9": (6 * inch, 9 * inch),
}


def read_config():
    """Read ~/.bitwize-music/config.yaml"""
    # Late import to avoid requiring project root on sys.path at module load
    from tools.shared.config import load_config
    return load_config()


def get_website_from_config():
    """Extract website URL from config (short display form, no protocol)."""
    config = read_config()
    if not config:
        return None

    try:
        # Try to find any URL in urls section
        urls = config.get('urls', {})
        if urls:
            # Prefer website, then soundcloud, then others
            for key in ['website', 'soundcloud', 'bandcamp', 'spotify']:
                if key in urls:
                    url = urls[key]
                    # Strip https://www. prefix for cleaner display
                    url = re.sub(r'https?://(www\.)?', '', url)
                    # Strip trailing slash
                    url = url.rstrip('/')
                    return url
        return None
    except (KeyError, TypeError, AttributeError):
        return None


def get_footer_url_from_config():
    """Get the footer URL for PDFs from config.

    Checks sheet_music.footer_url first, then falls back to urls section.
    Returns full URL (with protocol) for footer display.
    """
    config = read_config()
    if not config:
        return None

    try:
        # Explicit footer_url takes priority
        footer = config.get('sheet_music', {}).get('footer_url')
        if footer:
            return footer

        # Fall back to urls section (keep full URL for footer)
        urls = config.get('urls', {})
        if urls:
            for key in ['website', 'soundcloud', 'bandcamp', 'spotify']:
                if key in urls:
                    return urls[key].rstrip('/')
        return None
    except (KeyError, TypeError, AttributeError):
        return None


def auto_detect_cover_art(sheet_music_dir):
    """Auto-detect album art by walking up from the given directory.

    Handles both new structure (singles/ or songbook/ inside sheet-music/)
    and old flat structure (sheet-music/ directly under album).
    Walks up to 3 levels to find album.png/jpg.
    """
    current = Path(sheet_music_dir)

    # Walk up to 3 levels (e.g., singles/ -> sheet-music/ -> album/)
    for _ in range(3):
        current = current.parent
        for ext in ['png', 'jpg', 'jpeg']:
            cover_path = current / f'album.{ext}'
            if cover_path.exists():
                return str(cover_path)

    return None


def create_title_page(title, artist, page_size, cover_image=None, website=None):
    """Create a title page PDF with optional cover image."""
    buffer = io.BytesIO()
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    if cover_image and os.path.exists(cover_image):
        # Draw cover image centered
        from reportlab.lib.utils import ImageReader
        img = ImageReader(cover_image)
        img_width, img_height = img.getSize()

        # Scale to fit with margins
        max_width = width - 2 * inch
        max_height = height - 4 * inch
        scale = min(max_width / img_width, max_height / img_height)

        draw_width = img_width * scale
        draw_height = img_height * scale
        x = (width - draw_width) / 2
        y = height - 1.5 * inch - draw_height

        c.drawImage(cover_image, x, y, draw_width, draw_height)

        # Title below image
        text_y = y - 0.7 * inch
        c.setFont("Helvetica-Bold", 36)
        c.drawCentredString(width / 2, text_y, title)

        # Artist
        text_y -= 0.5 * inch
        c.setFont("Helvetica", 20)
        c.drawCentredString(width / 2, text_y, f"by {artist}")

        # Subtitle (website URL or fallback)
        text_y -= 0.4 * inch
        subtitle = website or "Piano Arrangements"
        c.setFont("Helvetica-Oblique", 14)
        c.drawCentredString(width / 2, text_y, subtitle)
    else:
        # No cover image - text only
        c.setFont("Helvetica-Bold", 48)
        c.drawCentredString(width / 2, height - 3 * inch, title)

        c.setFont("Helvetica", 24)
        c.drawCentredString(width / 2, height - 4 * inch, f"by {artist}")

        subtitle = website or "Piano Arrangements"
        c.setFont("Helvetica-Oblique", 16)
        c.drawCentredString(width / 2, height - 5 * inch, subtitle)

    # Year at bottom (website is already shown as subtitle and in page footer)
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, 0.8 * inch, str(datetime.now().year))

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def create_copyright_page(title, artist, year, page_size, website=None):
    """Create a copyright page PDF."""
    buffer = io.BytesIO()
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    y = height - 2 * inch
    c.setFont("Helvetica", 11)

    lines = [
        f"{title}",
        f"by {artist}",
        "",
        f"© {year} {artist}.",
        "",
        "This songbook is a free companion to the album.",
        "Share freely. Credit appreciated.",
        "",
        "",
        "Piano arrangements transcribed using AnthemScore.",
        "Notation edited with MuseScore.",
        "",
    ]

    if website:
        lines.extend([
            "",
            f"Listen to the album: {website}",
            "",
        ])

    lines.append(f"Published {year}")

    for line in lines:
        c.drawCentredString(width / 2, y, line)
        y -= 18

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def create_toc_page(tracks, page_size):
    """Create a table of contents page."""
    buffer = io.BytesIO()
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 1.5 * inch, "Contents")

    # Track listing
    y = height - 2.5 * inch
    c.setFont("Helvetica", 12)

    current_page = 4  # After title, copyright, TOC pages

    for i, (track_name, page_count) in enumerate(tracks, 1):
        # Use track name directly (already clean from manifest or strip_track_number)
        display_name = track_name

        # Draw track number and name
        c.drawString(1 * inch, y, f"{i}.")
        c.drawString(1.4 * inch, y, display_name)

        # Draw dots and page number
        c.drawRightString(width - 1 * inch, y, str(current_page))

        # Draw leader dots
        name_width = c.stringWidth(display_name, "Helvetica", 12)
        dots_start = 1.4 * inch + name_width + 10
        dots_end = width - 1.2 * inch
        if dots_end > dots_start:
            dot_spacing = 8
            x = dots_start
            while x < dots_end:
                c.drawString(x, y, ".")
                x += dot_spacing

        y -= 24
        current_page += page_count

        if y < 1 * inch:
            # Would need another page for long TOCs
            break

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def create_section_header(track_name, track_num, page_size):
    """Create a section header page for each track."""
    buffer = io.BytesIO()
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    # Track number
    c.setFont("Helvetica", 72)
    c.drawCentredString(width / 2, height / 2 + 1 * inch, str(track_num))

    # Track name (already clean from manifest or strip_track_number)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height / 2 - 0.5 * inch, track_name)

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def create_single_title_page(track_title, artist, page_size, cover_image=None, footer_url=None):
    """Create a title/cover page for an individual single PDF.

    Similar to songbook title page but focused on a single track.
    """
    buffer = io.BytesIO()
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    if cover_image and os.path.exists(cover_image):
        from reportlab.lib.utils import ImageReader
        img = ImageReader(cover_image)
        img_width, img_height = img.getSize()

        max_width = width - 2 * inch
        max_height = height - 4.5 * inch
        scale = min(max_width / img_width, max_height / img_height)

        draw_width = img_width * scale
        draw_height = img_height * scale
        x = (width - draw_width) / 2
        y = height - 1.5 * inch - draw_height

        c.drawImage(cover_image, x, y, draw_width, draw_height)

        text_y = y - 0.7 * inch
        c.setFont("Helvetica-Bold", 32)
        c.drawCentredString(width / 2, text_y, track_title)

        text_y -= 0.5 * inch
        c.setFont("Helvetica", 18)
        c.drawCentredString(width / 2, text_y, f"by {artist}")
    else:
        c.setFont("Helvetica-Bold", 42)
        c.drawCentredString(width / 2, height - 3 * inch, track_title)

        c.setFont("Helvetica", 22)
        c.drawCentredString(width / 2, height - 4 * inch, f"by {artist}")

    # Footer URL
    if footer_url:
        c.setFont("Helvetica", 9)
        c.drawCentredString(width / 2, 0.5 * inch, footer_url)

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def create_footer_overlay(page_size, footer_url):
    """Create a transparent overlay page with just a footer URL.

    Used to stamp a footer onto existing PDF pages.
    """
    buffer = io.BytesIO()
    width, height = page_size
    c = canvas.Canvas(buffer, pagesize=page_size)

    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 0.35 * inch, footer_url)

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def add_footer_to_pdf(input_path, output_path, footer_url, page_size_name="letter"):
    """Add a footer URL to every page of an existing PDF.

    Reads the PDF, overlays a footer on each page, writes to output_path.
    input_path and output_path can be the same file.
    """
    page_size = PAGE_SIZES.get(page_size_name, PAGE_SIZES["letter"])
    footer_page = create_footer_overlay(page_size, footer_url)

    reader = PdfReader(str(input_path))
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(footer_page)
        writer.add_page(page)

    with open(str(output_path), "wb") as f:
        writer.write(f)


def get_pdf_page_count(pdf_path):
    """Get number of pages in a PDF."""
    reader = PdfReader(pdf_path)
    return len(reader.pages)


def create_songbook(
    source_dir,
    output_path,
    title,
    artist,
    page_size_name="letter",
    include_section_headers=False,
    year=None,
    cover_image=None,
    website=None,
    footer_url=None
):
    """Create a complete songbook PDF."""

    page_size = PAGE_SIZES.get(page_size_name, PAGE_SIZES["letter"])
    year = year or datetime.now().year

    source_path = Path(source_dir)

    # Try to read manifest for track ordering
    manifest_path = source_path / ".manifest.json"
    manifest = None
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            logger.info("Using track order from .manifest.json")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read manifest: %s", e)

    if manifest:
        # Use manifest for ordering — try filename field first (numbered singles),
        # then title (clean-titled), then source/source_slug (legacy)
        pdf_files = []
        for entry in manifest.get("tracks", []):
            entry_title = entry.get("title", "")
            filename = entry.get("filename", "")
            # Try numbered filename first (e.g., "01 - First Pour")
            if filename:
                pdf_path = source_path / f"{filename}.pdf"
                if pdf_path.exists():
                    pdf_files.append(pdf_path)
                    continue
            # Fallback: try clean title
            if entry_title:
                pdf_path = source_path / f"{entry_title}.pdf"
                if pdf_path.exists():
                    pdf_files.append(pdf_path)
                    continue
            # Fallback: try source slug
            source_name = entry.get("source", entry.get("source_slug", ""))
            if source_name:
                alt_path = source_path / f"{source_name}.pdf"
                if alt_path.exists():
                    pdf_files.append(alt_path)
                    continue
            logger.warning("PDF not found for track: %s", entry_title or filename)
    else:
        # No manifest — include all PDFs, try numbered first, then alphabetical
        numbered = sorted([
            f for f in source_path.glob("*.pdf")
            if re.match(r'^\d+', f.stem)
        ])
        if numbered:
            pdf_files = numbered
        else:
            # Alphabetical, excluding known songbook patterns
            pdf_files = sorted([
                f for f in source_path.glob("*.pdf")
                if not any(kw in f.stem.lower() for kw in ['songbook', 'complete'])
            ])

    if not pdf_files:
        logger.error("No PDF files found in %s", source_dir)
        return False

    print(f"Found {len(pdf_files)} PDF file(s)")

    # Build a title lookup from manifest (maps filename stem -> title)
    manifest_title_lookup = {}
    if manifest:
        for entry in manifest.get("tracks", []):
            filename = entry.get("filename", "")
            entry_title = entry.get("title", "")
            if filename:
                manifest_title_lookup[filename] = entry_title
            if entry_title:
                manifest_title_lookup[entry_title] = entry_title

    # When manifest is present, all singles from prepare_singles have title pages.
    # Without manifest, only non-numbered files (clean-titled) have title pages.
    singles_have_title_pages = manifest is not None

    # Get page counts for TOC
    tracks = []
    for pdf_file in pdf_files:
        # Determine display name from manifest or filename
        if pdf_file.stem in manifest_title_lookup:
            track_name = manifest_title_lookup[pdf_file.stem]
        elif re.match(r'^\d+', pdf_file.stem):
            track_name = strip_track_number(pdf_file.stem)
        else:
            track_name = pdf_file.stem
        page_count = get_pdf_page_count(pdf_file)
        # Singles have a prepended title page — don't count it for the songbook
        if singles_have_title_pages:
            has_title_page = True
        else:
            has_title_page = not re.match(r'^\d+', pdf_file.stem)
        if has_title_page:
            page_count -= 1
        if include_section_headers:
            page_count += 1  # Add section header page
        tracks.append((track_name, page_count))
        print(f"  {track_name}: {page_count} page(s)")

    # Create output PDF
    writer = PdfWriter()

    # Add front matter
    print("\nAdding front matter...")
    writer.add_page(create_title_page(title, artist, page_size, cover_image, website))
    writer.add_page(create_copyright_page(title, artist, year, page_size, website))
    writer.add_page(create_toc_page(tracks, page_size))

    # Add each track
    for i, pdf_file in enumerate(pdf_files, 1):
        if pdf_file.stem in manifest_title_lookup:
            track_name = manifest_title_lookup[pdf_file.stem]
        elif re.match(r'^\d+', pdf_file.stem):
            track_name = strip_track_number(pdf_file.stem)
        else:
            track_name = pdf_file.stem
        print(f"Adding: {track_name}")

        # Optional section header
        if include_section_headers:
            writer.add_page(create_section_header(track_name, i, page_size))

        # Add all pages from the track PDF
        # Singles have a prepended title page — skip it in the songbook
        # (the songbook has its own front matter and optional section headers)
        reader = PdfReader(pdf_file)
        if singles_have_title_pages:
            has_title_page = True
        else:
            has_title_page = not re.match(r'^\d+', pdf_file.stem)
        start_page = 1 if has_title_page else 0
        for page in reader.pages[start_page:]:
            writer.add_page(page)

    # Add footer URL to every page
    if footer_url:
        footer_page = create_footer_overlay(page_size, footer_url)
        for i in range(len(writer.pages)):
            writer.pages[i].merge_page(footer_page)

    # Write output
    print(f"\nWriting songbook to: {output_path}")
    with open(output_path, "wb") as f:
        writer.write(f)

    # Summary
    total_pages = len(writer.pages)
    print(f"\n[OK] Songbook created: {total_pages} page(s)")
    print(f"  Title: {title}")
    print(f"  Artist: {artist}")
    print(f"  Tracks: {len(pdf_files)}")
    print(f"  Output: {output_path}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Create a distribution-ready songbook from sheet music PDFs"
    )
    parser.add_argument(
        "source_dir",
        help="Directory containing sheet music PDFs"
    )
    parser.add_argument(
        "--title", "-t",
        default="Songbook",
        help="Book title (default: Songbook)"
    )
    parser.add_argument(
        "--artist", "-a",
        help="Artist name (auto-detected from config if not provided)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: [source_dir]/[title].pdf)"
    )
    parser.add_argument(
        "--page-size", "-p",
        choices=["letter", "9x12", "6x9"],
        help="Page size (default: from config or letter)"
    )
    parser.add_argument(
        "--section-headers", "-s",
        action="store_true",
        help="Add section header pages before each track"
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=datetime.now().year,
        help=f"Copyright year (default: {datetime.now().year})"
    )
    parser.add_argument(
        "--cover", "-c",
        help="Path to cover image (auto-detected if not provided)"
    )
    parser.add_argument(
        "--website", "-w",
        help="Website URL to include (auto-detected from config if not provided)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show debug output"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show warnings and errors"
    )

    args = parser.parse_args()

    setup_logging(__name__, verbose=getattr(args, 'verbose', False), quiet=getattr(args, 'quiet', False))

    # Validate source directory
    if not os.path.isdir(args.source_dir):
        logger.error("%s is not a directory", args.source_dir)
        sys.exit(1)

    # Read config for auto-detection
    config = read_config()

    # Auto-detect artist from config
    artist = args.artist
    if not artist and config:
        try:
            artist = config['artist']['name']
            logger.info("Auto-detected artist from config: %s", artist)
        except KeyError:
            pass

    if not artist:
        artist = "Unknown Artist"
        logger.warning("Artist not specified, using: %s", artist)

    # Auto-detect page size from config
    page_size = args.page_size
    if not page_size and config:
        try:
            page_size = config.get('sheet_music', {}).get('page_size', 'letter')
            logger.info("Using page size from config: %s", page_size)
        except (TypeError, AttributeError):
            page_size = 'letter'
    elif not page_size:
        page_size = 'letter'

    # Auto-detect section headers from config
    section_headers = args.section_headers
    if not section_headers and config:
        try:
            section_headers = config.get('sheet_music', {}).get('section_headers', False)
            if section_headers:
                logger.info("Using section headers from config: %s", section_headers)
        except (TypeError, AttributeError):
            pass

    # Auto-detect cover art
    cover = args.cover
    if not cover:
        cover = auto_detect_cover_art(args.source_dir)
        if cover:
            logger.info("Auto-detected cover art: %s", cover)

    # Auto-detect website from config
    website = args.website
    if not website:
        website = get_website_from_config()
        if website:
            logger.info("Auto-detected website from config: %s", website)

    # Set output path — default to songbook/ sibling of source dir
    if args.output:
        output_path = args.output
    else:
        source_p = Path(args.source_dir)
        # If inside singles/, put songbook/ as sibling
        if source_p.name == 'singles':
            songbook_dir = source_p.parent / 'songbook'
        else:
            songbook_dir = source_p / 'songbook'
        os.makedirs(songbook_dir, exist_ok=True)
        safe_title = args.title.replace(" ", "_").replace("/", "-")
        output_path = str(songbook_dir / f"{safe_title}.pdf")

    # Auto-detect footer URL from config
    footer_url = get_footer_url_from_config()
    if footer_url:
        logger.info("Using footer URL: %s", footer_url)

    # Create songbook
    success = create_songbook(
        source_dir=args.source_dir,
        output_path=output_path,
        title=args.title,
        artist=artist,
        page_size_name=page_size,
        include_section_headers=section_headers,
        year=args.year,
        cover_image=cover,
        website=website,
        footer_url=footer_url
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
