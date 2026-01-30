"""System font discovery for video generation."""

from pathlib import Path
from typing import Optional


def find_font() -> Optional[str]:
    """Find an available system font for video text rendering."""
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
