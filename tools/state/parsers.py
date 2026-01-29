#!/usr/bin/env python3
"""
Markdown parsing functions for state cache indexer.

Parses album READMEs, track files, and IDEAS.md into structured dicts.
Uses regex against the exact markdown table format in templates:
  | **Key** | Value |
"""

import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import yaml, provide helpful error if missing
try:
    import yaml
except ImportError:
    yaml = None


def parse_frontmatter(text: str) -> Dict[str, Any]:
    """Parse YAML frontmatter from markdown content.

    Expects content starting with '---' delimiter.

    Returns:
        Dict of frontmatter fields, or empty dict if no frontmatter found.
        On parse error, returns {'_error': str}.
    """
    if not text.startswith('---'):
        return {}

    lines = text.split('\n')
    end_index = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            end_index = i
            break

    if end_index == -1:
        return {}

    frontmatter_text = '\n'.join(lines[1:end_index])
    if not frontmatter_text.strip():
        return {}

    if yaml is None:
        return {'_error': 'PyYAML not installed'}

    try:
        return yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        return {'_error': f'Invalid YAML: {e}'}


def _extract_table_value(text: str, key: str) -> Optional[str]:
    """Extract a value from a markdown table row matching | **Key** | Value |.

    Args:
        text: Full markdown text to search.
        key: The bold key to look for (without ** markers).

    Returns:
        The value string, stripped, or None if not found.
    """
    # Match: | **Key** | Value | (with optional whitespace)
    pattern = re.compile(
        r'^\|\s*\*\*' + re.escape(key) + r'\*\*\s*\|\s*(.*?)\s*\|',
        re.MULTILINE
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


def _normalize_status(raw: Optional[str]) -> str:
    """Normalize a status string to canonical form.

    Handles common variations and template placeholders.
    """
    if not raw:
        return "Unknown"

    status = raw.strip()

    # Map common variations to canonical names
    status_map = {
        'concept': 'Concept',
        'in progress': 'In Progress',
        'research complete': 'Research Complete',
        'sources verified': 'Sources Verified',
        'complete': 'Complete',
        'released': 'Released',
        'not started': 'Not Started',
        'sources pending': 'Sources Pending',
        'generated': 'Generated',
        'final': 'Final',
    }

    lower = status.lower()
    if lower in status_map:
        return status_map[lower]

    # If it starts with a known status, use that (handles trailing content)
    for key, val in status_map.items():
        if lower.startswith(key):
            return val

    return status


def parse_album_readme(path: Path) -> Dict[str, Any]:
    """Parse an album README.md into structured data.

    Extracts:
        - YAML frontmatter (title, release_date, explicit, genres)
        - Album Details table (status, track count)
        - Tracklist table (track statuses)

    Args:
        path: Path to album README.md

    Returns:
        Dict with keys: title, status, genre, explicit, release_date,
        track_count, tracks_completed, tracklist.
        On error, includes '_error' key.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        return {'_error': f'Cannot read file: {e}'}

    result: Dict[str, Any] = {}

    # Parse frontmatter
    fm = parse_frontmatter(text)
    if '_error' in fm:
        result['_warning'] = fm['_error']
        fm = {}

    result['title'] = fm.get('title', '').strip('"').strip("'") or _extract_heading(text)
    result['release_date'] = fm.get('release_date') or None
    result['explicit'] = fm.get('explicit', False)

    # Genre from frontmatter list or table
    fm_genres = fm.get('genres', [])
    if fm_genres and isinstance(fm_genres, list) and len(fm_genres) > 0:
        result['genre'] = fm_genres[0]
    else:
        # Try extracting from path (albums/{genre}/{album}/)
        result['genre'] = _extract_genre_from_path(path)

    # Album Details table fields
    result['status'] = _normalize_status(_extract_table_value(text, 'Status'))

    tracks_raw = _extract_table_value(text, 'Tracks')
    result['track_count'] = _parse_track_count(tracks_raw)

    # Parse tracklist table for track status summary
    tracklist = _parse_tracklist_table(text)
    result['tracklist'] = tracklist

    completed_statuses = {'Final', 'Generated', 'Complete'}
    result['tracks_completed'] = sum(
        1 for t in tracklist if t.get('status') in completed_statuses
    )

    return result


def _extract_heading(text: str) -> str:
    """Extract first H1 heading from markdown."""
    match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    return match.group(1).strip() if match else ''


def _extract_genre_from_path(path: Path) -> str:
    """Extract genre from album path structure: .../albums/{genre}/{album}/README.md"""
    parts = path.parts
    for i, part in enumerate(parts):
        if part == 'albums' and i + 1 < len(parts):
            return parts[i + 1]
    return ''


def _parse_track_count(raw: Optional[str]) -> int:
    """Parse track count from string like '12' or '[Number]'."""
    if not raw:
        return 0
    match = re.search(r'(\d+)', raw)
    return int(match.group(1)) if match else 0


def _parse_tracklist_table(text: str) -> List[Dict[str, str]]:
    """Parse the Tracklist table from album README.

    Flexibly handles any number of columns (3+). Expects:
    - First column: track number (digits)
    - Second column: title (may contain markdown link)
    - Last column: status

    Example formats (all supported):
    | # | Title | Status |
    | # | Title | POV | Concept | Status |
    | # | Title | POV | Concept | Duration | Status |
    """
    tracks = []

    # Find the Tracklist section
    tracklist_match = re.search(r'^##\s+Tracklist', text, re.MULTILINE)
    if not tracklist_match:
        return tracks

    # Get text after "## Tracklist" heading
    section_text = text[tracklist_match.end():]

    # Match any table row starting with a digit in the first column
    # Captures: track number (first col), remaining columns as one string
    for line in section_text.split('\n'):
        line = line.strip()
        if not line.startswith('|'):
            # Stop at next section heading or non-table content
            if line.startswith('#'):
                break
            continue

        # Split into columns
        cols = [c.strip() for c in line.split('|')]
        # Leading/trailing splits produce empty strings: ['', col1, col2, ..., '']
        cols = [c for c in cols if c or c == '']
        # Remove empty strings from split edges
        if cols and cols[0] == '':
            cols = cols[1:]
        if cols and cols[-1] == '':
            cols = cols[:-1]

        # Need at least 3 columns (number, title, status)
        if len(cols) < 3:
            continue

        # First column must be a track number (digits only)
        num = cols[0].strip()
        if not re.match(r'^\d+$', num):
            continue

        title_raw = cols[1]
        status = cols[-1]

        # Extract title from markdown link if present
        link_match = re.search(r'\[([^\]]+)\]', title_raw)
        title = link_match.group(1) if link_match else title_raw.strip()

        tracks.append({
            'number': num.strip().zfill(2),
            'title': title,
            'status': _normalize_status(status),
        })

    if tracklist_match and not tracks:
        warnings.warn("Tracklist section found but no track rows matched", stacklevel=2)

    return tracks


def parse_track_file(path: Path) -> Dict[str, Any]:
    """Parse a track markdown file into structured data.

    Extracts:
        - Track Details table (status, explicit, suno link, sources verified)
        - Title from heading or table

    Args:
        path: Path to track .md file

    Returns:
        Dict with keys: title, status, explicit, has_suno_link,
        sources_verified.
        On error, includes '_error' key.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        return {'_error': f'Cannot read file: {e}'}

    result: Dict[str, Any] = {}

    # Title from table or heading
    table_title = _extract_table_value(text, 'Title')
    if table_title and not table_title.startswith('['):
        result['title'] = table_title
    else:
        result['title'] = _extract_heading(text)

    # Status
    result['status'] = _normalize_status(_extract_table_value(text, 'Status'))

    # Explicit
    explicit_raw = _extract_table_value(text, 'Explicit')
    if explicit_raw:
        result['explicit'] = explicit_raw.lower().strip() in ('yes', 'true')
    else:
        result['explicit'] = False

    # Suno Link
    suno_link_raw = _extract_table_value(text, 'Suno Link')
    if suno_link_raw and suno_link_raw.strip() not in ('—', '–', '-', ''):
        result['has_suno_link'] = True
    else:
        result['has_suno_link'] = False

    # Sources Verified
    sources_raw = _extract_table_value(text, 'Sources Verified')
    if sources_raw:
        raw_lower = sources_raw.strip().lower()
        if 'n/a' in raw_lower:
            result['sources_verified'] = 'N/A'
        elif '❌' in sources_raw or raw_lower == 'pending' or raw_lower.startswith('pending'):
            # Check pending BEFORE verified so "pending verification" doesn't match "verified"
            result['sources_verified'] = 'Pending'
        elif '✅' in sources_raw or raw_lower == 'verified' or raw_lower.startswith('verified'):
            result['sources_verified'] = 'Verified'
        else:
            result['sources_verified'] = sources_raw
    else:
        result['sources_verified'] = 'N/A'

    return result


def parse_ideas_file(path: Path) -> Dict[str, Any]:
    """Parse IDEAS.md into structured data.

    Extracts:
        - Idea titles, genres, types, statuses
        - Status counts

    Args:
        path: Path to IDEAS.md

    Returns:
        Dict with keys: counts (dict), items (list of dicts).
        On error, includes '_error' key.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        return {'_error': f'Cannot read file: {e}'}

    items: List[Dict[str, str]] = []
    counts: Dict[str, int] = {}

    # Split into sections by ### headings (idea entries)
    # Skip template section and preamble
    ideas_section = text
    ideas_marker = re.search(r'^##\s+Ideas\b', text, re.MULTILINE)
    if ideas_marker:
        ideas_section = text[ideas_marker.end():]

    # Find each idea entry (### heading)
    idea_blocks = re.split(r'^###\s+', ideas_section, flags=re.MULTILINE)

    for block in idea_blocks[1:]:  # Skip content before first ###
        lines = block.strip().split('\n')
        if not lines:
            continue

        title = lines[0].strip()
        if not title or title.startswith('['):
            # Template placeholder, skip
            continue

        block_text = '\n'.join(lines)

        # Extract fields using **Key**: Value pattern
        genre = _extract_bold_field(block_text, 'Genre')
        idea_type = _extract_bold_field(block_text, 'Type')
        status = _extract_bold_field(block_text, 'Status')

        # Normalize status - take first value if it's a choice list
        if status and '|' in status:
            status = status.split('|')[0].strip()

        if not status:
            status = 'Pending'

        items.append({
            'title': title,
            'genre': genre or '',
            'type': idea_type or '',
            'status': status,
        })

        counts[status] = counts.get(status, 0) + 1

    return {
        'counts': counts,
        'items': items,
    }


def _extract_bold_field(text: str, key: str) -> Optional[str]:
    """Extract value from **Key**: Value pattern in text."""
    pattern = re.compile(r'\*\*' + re.escape(key) + r'\*\*\s*:\s*(.+)', re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None
