"""Shared text utilities for track naming and formatting."""

import re


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
