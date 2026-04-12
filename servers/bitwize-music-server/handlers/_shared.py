"""Shared state, constants, and helpers used across handler modules.

``cache`` and ``PLUGIN_ROOT`` are set by ``server.py`` before any handler
module's ``register()`` function is called.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from handlers._atomic import atomic_write_text

# ---------------------------------------------------------------------------
# Shared state — set by server.py at startup
# ---------------------------------------------------------------------------

cache: Any = None  # StateCache instance
PLUGIN_ROOT: Path | None = None  # Path to plugin root

# ---------------------------------------------------------------------------
# Status constants — single source of truth for track and album statuses.
# Use these instead of string literals to prevent typos and simplify refactoring.
# ---------------------------------------------------------------------------

# Track statuses (in order)
TRACK_NOT_STARTED = "Not Started"
TRACK_SOURCES_PENDING = "Sources Pending"
TRACK_SOURCES_VERIFIED = "Sources Verified"
TRACK_IN_PROGRESS = "In Progress"
TRACK_GENERATED = "Generated"
TRACK_FINAL = "Final"

# Album statuses (in order)
ALBUM_CONCEPT = "Concept"
ALBUM_RESEARCH_COMPLETE = "Research Complete"
ALBUM_SOURCES_VERIFIED = "Sources Verified"
ALBUM_IN_PROGRESS = "In Progress"
ALBUM_COMPLETE = "Complete"
ALBUM_RELEASED = "Released"

# Sets for membership checks
TRACK_COMPLETED_STATUSES = {TRACK_FINAL, TRACK_GENERATED}
ALBUM_VALID_STATUSES = [
    ALBUM_CONCEPT, ALBUM_RESEARCH_COMPLETE, ALBUM_SOURCES_VERIFIED,
    ALBUM_IN_PROGRESS, ALBUM_COMPLETE, ALBUM_RELEASED,
]

# Default for missing status fields
STATUS_UNKNOWN = "Unknown"

# Markdown link pattern — used for source verification gates
_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

# Valid genres for album creation — derived from genres/ directory at runtime
_VALID_GENRES: frozenset[str] | None = None


def _get_valid_genres() -> frozenset[str]:
    """Return valid genre slugs by scanning the genres/ directory.

    Results are cached after the first call.
    """
    global _VALID_GENRES
    if _VALID_GENRES is not None:
        return _VALID_GENRES
    if PLUGIN_ROOT is None:
        # Fallback if called before init (shouldn't happen)
        return frozenset()
    genres_dir = PLUGIN_ROOT / "genres"
    if genres_dir.is_dir():
        _VALID_GENRES = frozenset(
            d.name for d in genres_dir.iterdir()
            if d.is_dir() and (d / "README.md").exists()
        )
    else:
        _VALID_GENRES = frozenset()
    return _VALID_GENRES

_GENRE_ALIASES = {
    "r&b": "rnb", "rb": "rnb", "r-and-b": "rnb",
    "hip hop": "hip-hop", "hiphop": "hip-hop",
    "k pop": "k-pop", "kpop": "k-pop",
    "indie folk": "indie-folk",
}


# ---------------------------------------------------------------------------
# Shared helper functions
# ---------------------------------------------------------------------------

def _is_path_confined(base: Path, user_component: str) -> bool:
    """Return True if *base / user_component* stays within *base* after resolution.

    Use this to reject path-traversal attempts (e.g. ``../../etc/passwd``)
    before performing any file I/O with user-supplied path fragments.
    """
    try:
        resolved = (base / user_component).resolve()
        return resolved.is_relative_to(base.resolve())
    except (ValueError, OSError):
        return False


def _normalize_slug(name: str) -> str:
    """Normalize input to slug format."""
    return name.lower().replace(" ", "-").replace("_", "-")


def _safe_json(data: Any) -> str:
    """Serialize data to JSON with error fallback.

    If json.dumps() fails (e.g., circular references, non-serializable types),
    returns a JSON error object instead of crashing.
    """
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError, OverflowError) as e:
        return json.dumps({"error": f"JSON serialization failed: {e}"})


def _update_frontmatter_block(
    file_path: Path, key: str, values: dict[str, Any]
) -> tuple[bool, str | None]:
    """Add or update a top-level YAML frontmatter block in a markdown file.

    Parses the ``---`` delimited frontmatter, sets *key* to *values* using
    ``yaml.safe_load`` / ``yaml.dump``, and writes back.  The rest of the
    file is preserved unchanged.

    Args:
        file_path: Path to a ``.md`` file with ``---`` frontmatter.
        key: Top-level key to set (e.g. ``"sheet_music"``).
        values: Dict of sub-keys to write under *key*.

    Returns:
        ``(True, None)`` on success, ``(False, error_string)`` on failure.
    """
    import yaml

    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, f"Cannot read {file_path}: {exc}"

    if not text.startswith("---"):
        return False, f"{file_path} has no YAML frontmatter"

    lines = text.split("\n")
    end_index = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index == -1:
        return False, f"Cannot find closing --- in {file_path}"

    frontmatter_text = "\n".join(lines[1:end_index])
    try:
        fm = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        return False, f"Cannot parse frontmatter YAML in {file_path}: {exc}"

    fm[key] = values

    new_fm_text = yaml.dump(
        fm, default_flow_style=False, allow_unicode=True, sort_keys=False,
    ).rstrip("\n")

    rest_of_file = "\n".join(lines[end_index + 1:])
    new_text = "---\n" + new_fm_text + "\n---\n" + rest_of_file

    try:
        atomic_write_text(file_path, new_text)
    except OSError as exc:
        return False, f"Cannot write {file_path}: {exc}"

    return True, None


# Pre-compiled patterns for section extraction
_RE_SECTION = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
_RE_CODE_BLOCK = re.compile(r'```(?:[^\n]*\n)(.*?)```|```(.*?)```', re.DOTALL)


def _extract_markdown_section(text: str, heading: str) -> str | None:
    """Extract content under a specific markdown heading.

    Returns the text between the target heading and the next heading
    of equal or higher level, or end of file.
    """
    matches = list(_RE_SECTION.finditer(text))
    target_idx = None
    target_level = None

    for i, m in enumerate(matches):
        level = len(m.group(1))  # number of # chars
        title = m.group(2).strip()
        if title.lower() == heading.lower():
            target_idx = i
            target_level = level
            break

    if target_idx is None:
        return None

    start = matches[target_idx].end()

    # Find next heading at same or higher level
    for m in matches[target_idx + 1:]:
        level = len(m.group(1))
        assert target_level is not None
        if level <= target_level:
            end = m.start()
            return text[start:end].strip()

    # No next heading — return rest of file
    return text[start:].strip()


def _extract_code_block(section_text: str) -> str | None:
    """Extract the first code block from section text.

    Handles both fenced code blocks with language identifiers
    and plain fenced blocks.
    """
    match = _RE_CODE_BLOCK.search(section_text)
    if match:
        # group(1) = content after lang+newline; group(2) = inline content
        content = match.group(1) if match.group(1) is not None else (match.group(2) or "")
        return content.strip()
    return None


# ---------------------------------------------------------------------------
# Shared regex patterns — used by lyrics analysis, cross-track repetition, etc.
# ---------------------------------------------------------------------------

# Maximum text input length for text analysis tools (50,000 chars ≈ 10x a long song)
MAX_TEXT_INPUT_LENGTH = 50_000


def _check_text_length(text: str, tool_name: str) -> str | None:
    """Return a JSON error string if *text* exceeds MAX_TEXT_INPUT_LENGTH, else None."""
    if len(text) > MAX_TEXT_INPUT_LENGTH:
        return _safe_json({
            "error": (
                f"Input too long ({len(text):,} chars). "
                f"{tool_name} accepts at most {MAX_TEXT_INPUT_LENGTH:,} characters."
            ),
        })
    return None


# Section tag pattern — matches [Verse 1], [Chorus], etc.
_SECTION_TAG_RE = re.compile(r'^\[.*\]$')

# Word tokeniser — extracts alphabetic words (with internal apostrophes)
_WORD_TOKEN_RE = re.compile(r"[a-zA-Z']+")

# Stopwords: English function words + common song filler + ubiquitous song vocabulary.
# These appear so often across tracks that flagging them is noise, not signal.
_CROSS_TRACK_STOPWORDS = frozenset({
    # English function words
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet", "for",
    "in", "on", "at", "to", "of", "by", "up", "as", "if", "is", "it",
    "be", "am", "are", "was", "were", "been", "being", "do", "did",
    "does", "done", "has", "had", "have", "having", "he", "she", "we",
    "me", "my", "her", "his", "its", "our", "us", "they", "them",
    "their", "you", "your", "who", "what", "that", "this", "with",
    "from", "not", "no", "can", "will", "would", "could", "should",
    "may", "might", "shall", "just", "how", "when", "where", "why",
    "all", "each", "every", "some", "any", "than", "then", "too",
    "also", "very", "more", "most", "much", "many", "such", "own",
    "same", "other", "about", "into", "over", "after", "before",
    "through", "between", "under", "again", "out", "off", "here",
    "there", "which", "these", "those", "only", "im", "ive", "ill",
    "id", "dont", "wont", "cant", "didnt", "isnt", "wasnt", "youre",
    "youve", "youll", "youd", "hes", "shes", "weve", "theyre",
    "theyve", "theyll", "aint", "gonna", "wanna", "gotta",
    # Common song filler / vocables
    "oh", "ooh", "ah", "ahh", "yeah", "yea", "hey", "na", "la",
    "da", "uh", "huh", "mmm", "whoa", "wo", "yo",
    # Ubiquitous song vocabulary — too common to flag
    "love", "heart", "baby", "night", "day", "time", "life", "way",
    "feel", "know", "see", "come", "go", "get", "got", "let", "take",
    "make", "say", "said", "back", "down", "like", "right", "left",
    "good", "new", "now", "one", "two", "still", "never", "ever",
    "keep", "need", "want", "look", "think", "thought", "mind",
    "world", "man", "eye", "eyes", "hand", "hands",
})


def _find_album_or_error(album_slug: str) -> tuple[str, dict[str, Any] | None, str | None]:
    """Find album in state cache, return (normalized_slug, album_data, error_json).

    If album found: (slug, data, None)
    If not found: (slug, None, error_json_string)
    """
    state = cache.get_state()
    albums = state.get("albums", {})
    normalized = _normalize_slug(album_slug)
    album = albums.get(normalized)

    if not album:
        return normalized, None, _safe_json({
            "found": False,
            "error": f"Album '{album_slug}' not found",
            "available_albums": list(albums.keys()),
        })

    return normalized, album, None


def _find_track_or_error(tracks: dict[str, Any], track_slug: str, album_slug: str = "") -> tuple[str, dict[str, Any] | None, str | None]:
    """Find track in tracks dict by exact match or prefix match.

    If track found: (matched_slug, track_data, None)
    If not found: (slug, None, error_json_string)
    """
    normalized = _normalize_slug(track_slug)
    track_data = tracks.get(normalized)
    if track_data:
        return normalized, track_data, None

    # Prefix match
    prefix_matches = {s: d for s, d in tracks.items() if s.startswith(normalized)}
    if len(prefix_matches) == 1:
        matched_slug = next(iter(prefix_matches))
        return matched_slug, prefix_matches[matched_slug], None
    elif len(prefix_matches) > 1:
        return normalized, None, _safe_json({
            "found": False,
            "error": f"Multiple tracks match '{track_slug}': {', '.join(sorted(prefix_matches.keys()))}",
        })
    else:
        ctx = f" in album '{album_slug}'" if album_slug else ""
        return normalized, None, _safe_json({
            "found": False,
            "error": f"Track '{track_slug}' not found{ctx}.",
            "available_tracks": list(tracks.keys()),
        })


def _resolve_audio_dir(album_slug: str, subfolder: str = "") -> tuple[str | None, Path | None]:
    """Resolve album slug to audio directory path.

    Returns (error_json_or_None, Path_or_None).
    """
    state = cache.get_state()
    config = state.get("config", {})
    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")
    if not audio_root or not artist:
        return _safe_json({"error": "audio_root or artist_name not configured"}), None
    normalized = _normalize_slug(album_slug)
    albums = state.get("albums", {})
    album_data = albums.get(normalized, {})
    genre = album_data.get("genre", "")
    if not genre:
        return _safe_json({
            "error": f"Genre not found for album '{album_slug}'. Ensure album exists in state.",
        }), None
    audio_path = Path(audio_root) / "artists" / artist / "albums" / genre / normalized
    if subfolder:
        if not _is_path_confined(audio_path, subfolder):
            return _safe_json({
                "error": "Invalid subfolder: path must not escape the album directory",
                "subfolder": subfolder,
            }), None
        audio_path = audio_path / subfolder
    if not audio_path.is_dir():
        return _safe_json({
            "error": f"Audio directory not found: {audio_path}",
            "suggestion": "Check album slug or download audio first.",
        }), None
    return None, audio_path


# ---------------------------------------------------------------------------
# Shared constants — used by multiple handler modules
# ---------------------------------------------------------------------------

# Map user-friendly section names to markdown headings
_SECTION_NAMES = {
    "style": "Style Box",
    "style-box": "Style Box",
    "lyrics": "Lyrics Box",
    "lyrics-box": "Lyrics Box",
    "streaming": "Streaming Lyrics",
    "streaming-lyrics": "Streaming Lyrics",
    "pronunciation": "Pronunciation Notes",
    "pronunciation-notes": "Pronunciation Notes",
    "concept": "Concept",
    "source": "Source",
    "original-quote": "Original Quote",
    "musical-direction": "Musical Direction",
    "production-notes": "Production Notes",
    "generation-log": "Generation Log",
    "phonetic-review": "Phonetic Review Checklist",
    "mood": "Mood & Imagery",
    "mood-imagery": "Mood & Imagery",
    "lyrical-approach": "Lyrical Approach",
    "exclude": "Exclude Styles",
    "exclude-styles": "Exclude Styles",
}

# Canonical streaming platform names and accepted aliases
_STREAMING_PLATFORMS = {
    "soundcloud": "soundcloud",
    "spotify": "spotify",
    "apple_music": "apple_music",
    "apple-music": "apple_music",
    "applemusic": "apple_music",
    "youtube_music": "youtube_music",
    "youtube-music": "youtube_music",
    "youtubemusic": "youtube_music",
    "amazon_music": "amazon_music",
    "amazon-music": "amazon_music",
    "amazonmusic": "amazon_music",
}


# Template placeholder markers — if streaming lyrics contain these, the section
# hasn't been filled in yet.
_STREAMING_PLACEHOLDER_MARKERS = [
    "Plain lyrics here",
    "Capitalize first letter of each line",
    "No end punctuation",
    "Write out all repeats fully",
    "Blank lines between sections only",
]

# Sections whose markdown content should be extracted as a code block
_CODE_BLOCK_SECTIONS = frozenset({"Style Box", "Exclude Styles", "Lyrics Box", "Streaming Lyrics", "Original Quote"})


def _find_wav_source_dir(audio_dir: Path) -> Path:
    """Return originals/ if it exists, else album root (legacy fallback)."""
    originals = audio_dir / "originals"
    if originals.is_dir():
        return originals
    return audio_dir


def _derive_title_from_slug(slug: str) -> str:
    """Derive a display title from a slug.

    Strips leading track number prefix (e.g., "01-") and converts hyphens
    to spaces with title case.

    Examples:
        "01-my-track-name" -> "My Track Name"
        "my-album"         -> "My Album"
    """
    # Strip leading track number prefix like "01-", "02-"
    stripped = re.sub(r'^\d+-', '', slug)
    return stripped.replace('-', ' ').title()
