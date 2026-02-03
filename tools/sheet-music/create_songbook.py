#!/usr/bin/env python3
"""
create_songbook.py - Combine sheet music PDFs into a KDP-ready songbook

Enhanced version with config integration for automatic metadata detection.

Usage:
    python3 create_songbook.py /path/to/sheet-music/ --title "Album Songbook" --artist "Artist Name"

    # With config integration (auto-detects artist, cover art):
    python3 create_songbook.py /path/to/sheet-music/ --title "Album Songbook"

Requirements:
    pip install pypdf reportlab pyyaml
"""

import argparse
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
    """Extract website URL from config"""
    config = read_config()
    if not config:
        return None

    try:
        # Try to find any URL in urls section
        urls = config.get('urls', {})
        if urls:
            # Prefer soundcloud, but take any URL
            for key in ['soundcloud', 'bandcamp', 'website', 'spotify']:
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


def auto_detect_cover_art(sheet_music_dir):
    """Auto-detect album art from sheet-music parent directory

    Assumes structure: {audio_root}/{artist}/{album}/sheet-music/
    Looks for: {audio_root}/{artist}/{album}/album.png
    """
    sheet_music_path = Path(sheet_music_dir)

    # Go up one level to album directory
    album_dir = sheet_music_path.parent

    # Look for album.png or album.jpg
    for ext in ['png', 'jpg', 'jpeg']:
        cover_path = album_dir / f'album.{ext}'
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

        # Subtitle
        text_y -= 0.4 * inch
        c.setFont("Helvetica-Oblique", 14)
        c.drawCentredString(width / 2, text_y, "Piano Arrangements")
    else:
        # No cover image - text only
        c.setFont("Helvetica-Bold", 48)
        c.drawCentredString(width / 2, height - 3 * inch, title)

        c.setFont("Helvetica", 24)
        c.drawCentredString(width / 2, height - 4 * inch, f"by {artist}")

        c.setFont("Helvetica-Oblique", 16)
        c.drawCentredString(width / 2, height - 5 * inch, "Piano Arrangements")

    # Website and year at bottom
    c.setFont("Helvetica", 11)
    if website:
        c.drawCentredString(width / 2, 1.2 * inch, website)
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
        f"© {year} {artist}. All rights reserved.",
        "",
        "No part of this publication may be reproduced, distributed,",
        "or transmitted in any form without the prior written permission",
        "of the copyright holder.",
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
        # Clean up track name (remove number prefix if present)
        display_name = track_name
        if display_name[0:2].isdigit() and display_name[2:4] == " -":
            display_name = display_name[5:]
        elif display_name[0:2].isdigit() and display_name[2] == " ":
            display_name = display_name[3:]

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

    # Clean up track name
    display_name = track_name
    if display_name[0:2].isdigit() and display_name[2:4] == " -":
        display_name = display_name[5:]
    elif display_name[0:2].isdigit() and display_name[2] == " ":
        display_name = display_name[3:]

    # Track number
    c.setFont("Helvetica", 72)
    c.drawCentredString(width / 2, height / 2 + 1 * inch, str(track_num))

    # Track name
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height / 2 - 0.5 * inch, display_name)

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


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
    website=None
):
    """Create a complete songbook PDF."""

    page_size = PAGE_SIZES.get(page_size_name, PAGE_SIZES["letter"])
    year = year or datetime.now().year

    # Find all PDFs in source directory
    source_path = Path(source_dir)
    # Exclude any existing songbook files (files without track number prefix)
    pdf_files = sorted([
        f for f in source_path.glob("*.pdf")
        if re.match(r'^\d+', f.stem)  # Only include files starting with digits (track numbers)
    ])

    if not pdf_files:
        logger.error("No PDF files found in %s", source_dir)
        return False

    print(f"Found {len(pdf_files)} PDF file(s)")

    # Get page counts for TOC
    tracks = []
    for pdf_file in pdf_files:
        track_name = strip_track_number(pdf_file.stem)
        page_count = get_pdf_page_count(pdf_file)
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
        track_name = strip_track_number(pdf_file.stem)
        print(f"Adding: {track_name}")

        # Optional section header
        if include_section_headers:
            writer.add_page(create_section_header(track_name, i, page_size))

        # Add all pages from the track PDF
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            writer.add_page(page)

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
        description="Create a KDP-ready songbook from sheet music PDFs"
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

    # Set output path
    if args.output:
        output_path = args.output
    else:
        safe_title = args.title.replace(" ", "_").replace("/", "-")
        output_path = os.path.join(args.source_dir, f"{safe_title}.pdf")

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
        website=website
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
