"""System font discovery for video generation."""

import os
import platform
from pathlib import Path

# macOS/Linux candidates, bold-first — the style ffmpeg ``drawtext`` wants for
# legible overlay text on video. Order is load-bearing and must not change.
_POSIX_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

# Filenames under %SystemRoot%\Fonts, bold first to match the POSIX intent.
# All of these ship with every currently supported Windows release, so at
# least one is present on a stock install.
_WINDOWS_FONT_FILES = [
    "arialbd.ttf",   # Arial Bold
    "segoeuib.ttf",  # Segoe UI Bold
    "calibrib.ttf",  # Calibri Bold
    "tahomabd.ttf",  # Tahoma Bold
    "arial.ttf",     # regular fallbacks
    "segoeui.ttf",
]


def _windows_font_paths() -> list[str]:
    """Candidate font paths under the host's Windows font directory.

    Resolved from ``%SYSTEMROOT%`` (falling back to ``%WINDIR%``, then
    ``C:\\Windows``) rather than hardcoding ``C:``, since Windows is not
    always installed on the system drive. Windows environment lookups are
    case-insensitive, so the canonical upper-case spelling is used.
    """
    system_root = (
        os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or "C:\\Windows"
    )
    return [os.path.join(system_root, "Fonts", name) for name in _WINDOWS_FONT_FILES]


def _candidate_fonts() -> list[str]:
    """Font paths to probe, in priority order, for the current platform."""
    candidates = list(_POSIX_FONT_PATHS)
    if platform.system() == "Windows":
        # Appended, never interleaved: macOS/Linux discovery stays byte-identical.
        candidates.extend(_windows_font_paths())
    return candidates


def find_font() -> str | None:
    """Find an available system font for video text rendering."""
    for font in _candidate_fonts():
        if Path(font).exists():
            return font

    return None
