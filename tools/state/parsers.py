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

# =============================================================================
# Pre-compiled regex patterns (F2: avoid recompilation on every call)
# =============================================================================
_RE_HEADING_H1 = re.compile(r'^#\s+(.+)$', re.MULTILINE)
_RE_TRACKLIST_SECTION = re.compile(r'^##\s+Tracklist', re.MULTILINE)
_RE_TRACK_NUMBER = re.compile(r'^\d+$')
_RE_MARKDOWN_LINK = re.compile(r'\[([^\]]+)\]')
_RE_DIGIT_EXTRACT = re.compile(r'(\d+)')
_RE_IDEAS_SECTION = re.compile(r'^##\s+Ideas\b', re.MULTILINE)
_RE_IDEAS_SPLIT = re.compile(r'^###\s+', re.MULTILINE)


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
        result = yaml.safe_load(frontmatter_text) or {}
        if not isinstance(result, dict):
            return {'_error': f'Frontmatter is not a mapping (got {type(result).__name__})'}
        return result
    except yaml.YAMLError as e:
        return {'_error': f'Invalid YAML: {e}'}


_table_value_cache: Dict[str, re.Pattern] = {}


def _extract_table_value(text: str, key: str) -> Optional[str]:
    """Extract a value from a markdown table row matching | **Key** | Value |.

    Args:
        text: Full markdown text to search.
        key: The bold key to look for (without ** markers).

    Returns:
        The value string, stripped, or None if not found.
    """
    # Use cached compiled pattern for each key
    if key not in _table_value_cache:
        _table_value_cache[key] = re.compile(
            r'^\|\s*\*\*' + re.escape(key) + r'\*\*\s*\|\s*(.*?)\s*\|',
            re.MULTILINE
        )
    match = _table_value_cache[key].search(text)
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

    # Streaming URLs from frontmatter
    streaming_fm = fm.get('streaming', {})
    if isinstance(streaming_fm, dict):
        result['streaming_urls'] = {
            k: v for k, v in streaming_fm.items()
            if isinstance(v, str) and v.strip()
        }
    else:
        result['streaming_urls'] = {}

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

    completed_statuses = {'Final', 'Generated'}
    result['tracks_completed'] = sum(
        1 for t in tracklist if t.get('status') in completed_statuses
    )

    return result


def _extract_heading(text: str) -> str:
    """Extract first H1 heading from markdown."""
    match = _RE_HEADING_H1.search(text)
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
    match = _RE_DIGIT_EXTRACT.search(raw)
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
    tracklist_match = _RE_TRACKLIST_SECTION.search(text)
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
        if not _RE_TRACK_NUMBER.match(num):
            continue

        title_raw = cols[1]
        status = cols[-1]

        # Extract title from markdown link if present
        link_match = _RE_MARKDOWN_LINK.search(title_raw)
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

    # Parse frontmatter (optional — older files may not have it)
    fm = parse_frontmatter(text)
    if '_error' in fm:
        result['_warning'] = fm['_error']
        fm = {}

    # Title: table → frontmatter → heading
    table_title = _extract_table_value(text, 'Title')
    if table_title and not table_title.startswith('['):
        result['title'] = table_title
    elif fm.get('title') and fm['title'] not in ('[Track Title]', ''):
        result['title'] = str(fm['title']).strip('"').strip("'")
    else:
        result['title'] = _extract_heading(text)

    # Status
    result['status'] = _normalize_status(_extract_table_value(text, 'Status'))

    # Explicit: table → frontmatter → False
    explicit_raw = _extract_table_value(text, 'Explicit')
    if explicit_raw:
        result['explicit'] = explicit_raw.lower().strip() in ('yes', 'true')
    elif 'explicit' in fm:
        result['explicit'] = bool(fm['explicit'])
    else:
        result['explicit'] = False

    # Suno Link
    suno_link_raw = _extract_table_value(text, 'Suno Link')
    if suno_link_raw and suno_link_raw.strip() not in ('—', '–', '-', ''):
        result['has_suno_link'] = True
    else:
        result['has_suno_link'] = False

    # Suno URL from frontmatter (not in table)
    fm_suno_url = fm.get('suno_url', '')
    if fm_suno_url and str(fm_suno_url).strip():
        result['suno_url'] = str(fm_suno_url).strip()

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
            # Preserve verification date if present (e.g., "✅ Verified (2025-01-15)")
            date_match = re.search(r'\((\d{4}-\d{2}-\d{2})\)', sources_raw)
            if date_match:
                result['sources_verified'] = f'Verified ({date_match.group(1)})'
            else:
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
    ideas_marker = _RE_IDEAS_SECTION.search(text)
    if ideas_marker:
        ideas_section = text[ideas_marker.end():]

    # Find each idea entry (### heading)
    idea_blocks = _RE_IDEAS_SPLIT.split(ideas_section)

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


_bold_field_cache: Dict[str, re.Pattern] = {}


def _extract_bold_field(text: str, key: str) -> Optional[str]:
    """Extract value from **Key**: Value pattern in text."""
    if key not in _bold_field_cache:
        _bold_field_cache[key] = re.compile(
            r'\*\*' + re.escape(key) + r'\*\*\s*:\s*(.+)', re.IGNORECASE
        )
    match = _bold_field_cache[key].search(text)
    if match:
        return match.group(1).strip()
    return None


# =============================================================================
# Skill file parsing
# =============================================================================

# Known model tier keywords in order of precedence
_MODEL_TIER_KEYWORDS = ['opus', 'sonnet', 'haiku']


def _derive_model_tier(model: str) -> str:
    """Derive model tier (opus/sonnet/haiku) from a model ID string.

    Args:
        model: Model identifier (e.g., "claude-opus-4-6", "claude-sonnet-4-5-20250929")

    Returns:
        Lowercase tier string ("opus", "sonnet", "haiku") or "unknown".
    """
    if not model or not isinstance(model, str):
        return 'unknown'
    lower = model.lower()
    for tier in _MODEL_TIER_KEYWORDS:
        if tier in lower:
            return tier
    return 'unknown'


def parse_skill_file(path: Path) -> Dict[str, Any]:
    """Parse a SKILL.md file into structured metadata.

    Extracts YAML frontmatter and normalizes field names (hyphens to
    underscores). Validates that required fields (name, description, model)
    are present.

    Args:
        path: Path to SKILL.md file.

    Returns:
        Dict with skill metadata. On error, includes '_error' key.
        Fields returned:
            name, description, model, model_tier, argument_hint,
            allowed_tools, prerequisites, requirements, user_invocable,
            context, path, mtime
    """
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as e:
        return {'_error': f'Cannot read file: {e}'}

    fm = parse_frontmatter(text)
    if '_error' in fm:
        return {'_error': fm['_error']}
    if not fm:
        return {'_error': 'No frontmatter found'}

    # Normalize hyphenated keys to underscores
    normalized: Dict[str, Any] = {}
    for key, value in fm.items():
        normalized[key.replace('-', '_')] = value

    # Validate required fields
    missing = []
    for field in ('name', 'description'):
        if not normalized.get(field):
            missing.append(field)
    if missing:
        return {'_error': f"Missing required fields: {', '.join(missing)}"}

    # Extract model (default to empty string if missing)
    model = normalized.get('model', '')

    # Build result
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    return {
        'name': normalized['name'],
        'description': normalized['description'],
        'model': model,
        'model_tier': _derive_model_tier(model),
        'argument_hint': normalized.get('argument_hint'),
        'allowed_tools': normalized.get('allowed_tools', []),
        'prerequisites': normalized.get('prerequisites', []),
        'requirements': normalized.get('requirements', {}),
        'user_invocable': normalized.get('user_invocable', True),
        'context': normalized.get('context'),
        'path': str(path),
        'mtime': mtime,
    }
