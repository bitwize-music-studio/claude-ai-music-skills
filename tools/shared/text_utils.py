"""Shared text utilities for track naming and formatting."""

import re


def sanitize_filename(title):
    """Remove characters invalid in filenames (Windows + macOS + Linux).

    Strips < > : " / \\ | ? * and collapses whitespace.
    Returns "Untitled" if the result would be empty.
    """
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized or "Untitled"


def strip_track_number(name):
    """Remove track number prefix from filename/title.

    Handles patterns like:
    - "01 - Track Name"
    - "01-Track Name"
    - "1 - Track Name"
    - "01. Track Name"
    """
    pattern = r'^\d+\s*[-.\s]+\s*'
    return re.sub(pattern, '', name)


_TITLE_CASE_SMALL = {
    'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'yet', 'so',
    'in', 'on', 'at', 'to', 'of', 'by', 'with', 'from', 'as', 'is',
}


def slug_to_title(slug):
    """Convert '01-ocean-of-tears' → 'Ocean of Tears'.

    Strips track number prefix, replaces hyphens with spaces,
    and applies smart title casing (small words stay lowercase
    except at start/end).
    """
    name = strip_track_number(slug)
    name = name.replace('-', ' ')
    words = name.split()
    if not words:
        return name
    result = []
    for i, word in enumerate(words):
        if i == 0 or i == len(words) - 1:
            result.append(word.capitalize())
        elif word.lower() in _TITLE_CASE_SMALL:
            result.append(word.lower())
        else:
            result.append(word.capitalize())
    return ' '.join(result)
