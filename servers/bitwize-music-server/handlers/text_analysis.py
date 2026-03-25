"""Text analysis tools — homographs, artist names, pronunciation, explicit content, lyrics stats."""

import logging
import re
import threading
from pathlib import Path
from typing import Optional

from handlers._shared import (
    _normalize_slug, _safe_json, _extract_markdown_section, _extract_code_block,
    _find_album_or_error,
    _SECTION_TAG_RE, _WORD_TOKEN_RE, _CROSS_TRACK_STOPWORDS,
    _MARKDOWN_LINK_RE,
    _find_track_or_error,
)
from handlers import _shared

logger = logging.getLogger("bitwize-music-state")


# =============================================================================
# Text Analysis Tools
# =============================================================================

# High-risk homographs that always require user clarification.
# Loaded from the pronunciation guide but kept as a compiled set for fast scanning.
_HIGH_RISK_HOMOGRAPHS = {
    "live": [
        {"pron_a": "LIV (live performance)", "pron_b": "LYVE (alive, living)"},
    ],
    "read": [
        {"pron_a": "REED (present tense)", "pron_b": "RED (past tense)"},
    ],
    "lead": [
        {"pron_a": "LEED (guide)", "pron_b": "LED (the metal)"},
    ],
    "wind": [
        {"pron_a": "WIND (breeze)", "pron_b": "WYND (turn, coil)"},
    ],
    "close": [
        {"pron_a": "KLOHS (near)", "pron_b": "KLOHZ (shut)"},
    ],
    "tear": [
        {"pron_a": "TEER (from crying)", "pron_b": "TAIR (rip)"},
    ],
    "bow": [
        {"pron_a": "BOH (ribbon, weapon)", "pron_b": "BOW (bend, ship front)"},
    ],
    "bass": [
        {"pron_a": "BAYSS (instrument)", "pron_b": "BASS (the fish)"},
    ],
    "row": [
        {"pron_a": "ROH (line, propel boat)", "pron_b": "ROW (argument)"},
    ],
    "sow": [
        {"pron_a": "SOH (plant seeds)", "pron_b": "SOW (female pig)"},
    ],
    "wound": [
        {"pron_a": "WOOND (injury)", "pron_b": "WOWND (coiled)"},
    ],
    "minute": [
        {"pron_a": "MIN-it (60 seconds)", "pron_b": "my-NOOT (tiny)"},
    ],
    "resume": [
        {"pron_a": "ri-ZOOM (continue)", "pron_b": "REZ-oo-may (CV)"},
    ],
    "object": [
        {"pron_a": "OB-jekt (thing)", "pron_b": "ob-JEKT (protest)"},
    ],
    "project": [
        {"pron_a": "PROJ-ekt (plan)", "pron_b": "pro-JEKT (throw)"},
    ],
    "record": [
        {"pron_a": "REK-ord (noun)", "pron_b": "ri-KORD (verb)"},
    ],
    "present": [
        {"pron_a": "PREZ-ent (gift, here)", "pron_b": "pri-ZENT (give)"},
    ],
    "content": [
        {"pron_a": "KON-tent (stuff)", "pron_b": "kon-TENT (satisfied)"},
    ],
    "desert": [
        {"pron_a": "DEZ-ert (sandy place)", "pron_b": "di-ZURT (abandon)"},
    ],
    "refuse": [
        {"pron_a": "REF-yoos (garbage)", "pron_b": "ri-FYOOZ (decline)"},
    ],
}

# Pre-compiled word boundary patterns for homograph scanning
_HOMOGRAPH_PATTERNS = {
    word: re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
    for word in _HIGH_RISK_HOMOGRAPHS
}


async def check_homographs(text: str) -> str:
    """Scan text for homograph words that Suno cannot disambiguate.

    Checks against the high-risk homograph list from the pronunciation guide.
    Returns found words with line numbers and pronunciation options.

    Args:
        text: Lyrics text to scan

    Returns:
        JSON with {has_homographs: bool, matches: [{word, line, line_number, options}], count: int}
    """
    if not text.strip():
        return _safe_json({"has_homographs": False, "matches": [], "count": 0})

    results = []
    lines = text.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Skip section tags like [Verse 1], [Chorus], etc.
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            continue

        for word, pattern in _HOMOGRAPH_PATTERNS.items():
            for match in pattern.finditer(line):
                results.append({
                    "word": match.group(0),
                    "canonical": word,
                    "line": stripped,
                    "line_number": line_num,
                    "column": match.start(),
                    "options": _HIGH_RISK_HOMOGRAPHS[word],
                })

    return _safe_json({"has_homographs": len(results) > 0, "matches": results, "count": len(results)})


# Artist blocklist cache — loaded lazily from reference file
_artist_blocklist_cache: Optional[list] = None
_artist_blocklist_patterns: Optional[dict] = None  # name -> compiled re.Pattern
_artist_blocklist_mtime: float = 0.0
_artist_blocklist_lock = threading.Lock()


def _load_artist_blocklist() -> list:
    """Load and parse the artist blocklist from the reference file.

    Automatically reloads when the source file changes on disk.
    Returns a list of dicts: [{name: str, alternative: str, genre: str}]
    """
    global _artist_blocklist_cache, _artist_blocklist_patterns
    global _artist_blocklist_mtime
    with _artist_blocklist_lock:
        blocklist_path = _shared.PLUGIN_ROOT / "reference" / "suno" / "artist-blocklist.md"
        try:
            current_mtime = blocklist_path.stat().st_mtime if blocklist_path.exists() else 0.0
        except OSError:
            current_mtime = 0.0
        if _artist_blocklist_cache is not None and current_mtime == _artist_blocklist_mtime:
            return _artist_blocklist_cache

        entries = []

        if not blocklist_path.exists():
            logger.warning("Artist blocklist not found at %s", blocklist_path)
            _artist_blocklist_cache = entries
            _artist_blocklist_patterns = {}
            _artist_blocklist_mtime = current_mtime
            return entries

        try:
            text = blocklist_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.error("Cannot read artist blocklist: %s", e)
            _artist_blocklist_cache = entries
            _artist_blocklist_patterns = {}
            _artist_blocklist_mtime = current_mtime
            return entries

        current_genre = ""
        # Parse table rows: | Don't Say | Say Instead |
        for line in text.split("\n"):
            # Detect genre headings
            heading_match = re.match(r'^###\s+(.+)', line)
            if heading_match:
                current_genre = heading_match.group(1).strip()
                continue

            # Parse table rows (skip header/separator rows)
            if line.startswith("|") and "---" not in line and "Don't Say" not in line:
                parts = [p.strip() for p in line.split("|")]
                # parts[0] is empty (before first |), parts[-1] is empty (after last |)
                if len(parts) >= 4:
                    name = parts[1].strip()
                    alternative = parts[2].strip()
                    if name and name != "Don't Say":
                        entries.append({
                            "name": name,
                            "alternative": alternative,
                            "genre": current_genre,
                        })

        _artist_blocklist_cache = entries
        _artist_blocklist_mtime = current_mtime
        # Pre-compile patterns for each artist name
        _artist_blocklist_patterns = {
            entry["name"]: re.compile(r'\b' + re.escape(entry["name"]) + r'\b', re.IGNORECASE)
            for entry in entries
        }
        logger.info("Loaded artist blocklist: %d entries", len(entries))
        return entries


async def scan_artist_names(text: str) -> str:
    """Scan text for real artist/band names from the blocklist.

    Checks style prompts or lyrics against the artist blocklist. Found names
    should be replaced with sonic descriptions.

    Args:
        text: Style prompt or lyrics to scan

    Returns:
        JSON with {clean: bool, matches: [{name, alternative, genre}], count: int}
    """
    if not text.strip():
        return _safe_json({"clean": True, "matches": [], "count": 0})

    blocklist = _load_artist_blocklist()
    matches = []

    for entry in blocklist:
        name = entry["name"]
        pattern = _artist_blocklist_patterns.get(name)
        if pattern and pattern.search(text):
            matches.append({
                "name": name,
                "alternative": entry["alternative"],
                "genre": entry["genre"],
            })

    return _safe_json({
        "clean": len(matches) == 0,
        "matches": matches,
        "count": len(matches),
    })


async def check_pronunciation_enforcement(
    album_slug: str,
    track_slug: str,
) -> str:
    """Verify that all Pronunciation Notes entries are applied in the Suno lyrics.

    Reads the track's Pronunciation Notes table and Lyrics Box, then checks
    that each phonetic entry appears in the lyrics.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")

    Returns:
        JSON with {entries: [{word, phonetic, applied, occurrences}],
                   all_applied: bool, unapplied_count: int}
    """
    # Resolve track file
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    tracks = album.get("tracks", {})
    matched_slug, track_data, error = _find_track_or_error(tracks, track_slug, album_slug)
    if error:
        return error

    track_path = track_data.get("path", "")
    if not track_path:
        return _safe_json({"found": False, "error": f"No path stored for track '{matched_slug}'"})

    try:
        text = Path(track_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read track file: {e}"})

    # Extract Pronunciation Notes table
    pron_section = _extract_markdown_section(text, "Pronunciation Notes")
    if pron_section is None:
        return _safe_json({
            "found": True,
            "track_slug": matched_slug,
            "entries": [],
            "all_applied": True,
            "unapplied_count": 0,
            "note": "No Pronunciation Notes section found",
        })

    # Parse the pronunciation table: | Word/Phrase | Pronunciation | Reason |
    entries = []
    for line in pron_section.split("\n"):
        if not line.startswith("|") or "---" in line or "Word" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            word = parts[1].strip()
            phonetic = parts[2].strip()
            if word and word != "—" and phonetic and phonetic != "—":
                entries.append({"word": word, "phonetic": phonetic})

    if not entries:
        return _safe_json({
            "found": True,
            "track_slug": matched_slug,
            "entries": [],
            "all_applied": True,
            "unapplied_count": 0,
            "note": "Pronunciation table is empty",
        })

    # Extract Lyrics Box content
    lyrics_section = _extract_markdown_section(text, "Lyrics Box")
    lyrics_content = ""
    if lyrics_section:
        code = _extract_code_block(lyrics_section)
        lyrics_content = code if code else lyrics_section

    # Check each pronunciation entry
    results = []
    unapplied = 0
    for entry in entries:
        phonetic = entry["phonetic"]
        # Check if the phonetic version appears in lyrics (case-insensitive)
        occurrences = len(re.findall(
            re.escape(phonetic), lyrics_content, re.IGNORECASE
        ))
        applied = occurrences > 0
        if not applied:
            unapplied += 1
        results.append({
            "word": entry["word"],
            "phonetic": phonetic,
            "applied": applied,
            "occurrences": occurrences,
        })

    return _safe_json({
        "found": True,
        "track_slug": matched_slug,
        "entries": results,
        "all_applied": unapplied == 0,
        "unapplied_count": unapplied,
    })


# --- Explicit content scanning ---

# Base explicit words from explicit-checker skill.  Override via
# {overrides}/explicit-words.md (sections: "Additional Explicit Words",
# "Not Explicit (Override Base)").
_BASE_EXPLICIT_WORDS = {
    "fuck", "fucking", "fucked", "fucker", "motherfuck", "motherfucker",
    "shit", "shitting", "shitty", "bullshit",
    "bitch", "bitches",
    "cunt", "cock", "cocks",
    "dick", "dicks",
    "pussy", "pussies",
    "asshole", "assholes",
    "whore", "slut",
    "goddamn", "goddammit",
}

_explicit_word_cache: Optional[set] = None
_explicit_word_patterns: Optional[dict] = None  # word -> compiled re.Pattern
_explicit_word_mtime: float = 0.0
_explicit_word_lock = threading.Lock()


def _load_explicit_words() -> set:
    """Load the explicit word set, merging base list with user overrides.

    Automatically reloads when the user override file changes on disk.
    """
    global _explicit_word_cache, _explicit_word_patterns
    global _explicit_word_mtime

    # Resolve the override file path BEFORE acquiring _explicit_word_lock
    # to avoid lock ordering issues (cache.get_state() acquires cache._lock).
    override_path = None
    try:
        state = _shared.cache.get_state()
        config = state.get("config", {})
        overrides_dir = config.get("overrides_dir", "")
        if not overrides_dir:
            content_root = config.get("content_root", "")
            overrides_dir = str(Path(content_root) / "overrides")
        override_path = Path(overrides_dir) / "explicit-words.md"
    except Exception:
        pass

    with _explicit_word_lock:

        try:
            current_mtime = override_path.stat().st_mtime if override_path and override_path.exists() else 0.0
        except OSError:
            current_mtime = 0.0

        if _explicit_word_cache is not None and current_mtime == _explicit_word_mtime:
            return _explicit_word_cache

        words = set(_BASE_EXPLICIT_WORDS)

        # Load user overrides (override_path already resolved above)
        try:
            if override_path and override_path.exists():
                text = override_path.read_text(encoding="utf-8")

                # Parse "Additional Explicit Words" section
                add_section = _extract_markdown_section(text, "Additional Explicit Words")
                if add_section:
                    for line in add_section.split("\n"):
                        line = line.strip()
                        if line.startswith("- ") and line[2:].strip():
                            word = line[2:].split("(")[0].strip().lower()
                            if word:
                                words.add(word)

                # Parse "Not Explicit (Override Base)" section
                remove_section = _extract_markdown_section(text, "Not Explicit (Override Base)")
                if remove_section:
                    for line in remove_section.split("\n"):
                        line = line.strip()
                        if line.startswith("- ") and line[2:].strip():
                            word = line[2:].split("(")[0].strip().lower()
                            words.discard(word)
        except (OSError, UnicodeDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to load explicit word overrides: %s", e)

        _explicit_word_cache = words
        _explicit_word_mtime = current_mtime
        # Pre-compile patterns for each word
        _explicit_word_patterns = {
            w: re.compile(r'\b' + re.escape(w) + r'\b', re.IGNORECASE)
            for w in words
        }
        return words


async def check_explicit_content(text: str) -> str:
    """Scan lyrics for explicit/profane words.

    Uses the base explicit word list merged with user overrides from
    {overrides}/explicit-words.md. Returns found words with line numbers
    and occurrence counts.

    Args:
        text: Lyrics text to scan

    Returns:
        JSON with {has_explicit: bool, matches: [{word, line, line_number, count}],
                   total_count: int, unique_words: int}
    """
    if not text.strip():
        return _safe_json({
            "has_explicit": False, "matches": [], "total_count": 0, "unique_words": 0,
        })

    _load_explicit_words()

    # Scan line by line using pre-compiled patterns
    hits: dict = {}  # word -> {count, lines: [{line, line_number}]}
    for line_num, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        # Skip section tags
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        for word, pattern in _explicit_word_patterns.items():
            matches = pattern.findall(line)
            if matches:
                if word not in hits:
                    hits[word] = {"count": 0, "lines": []}
                hits[word]["count"] += len(matches)
                hits[word]["lines"].append({
                    "line": stripped,
                    "line_number": line_num,
                })

    found = []
    total = 0
    for word, data in sorted(hits.items()):
        total += data["count"]
        found.append({
            "word": word,
            "count": data["count"],
            "lines": data["lines"],
        })

    return _safe_json({
        "has_explicit": len(found) > 0,
        "matches": found,
        "total_count": total,
        "unique_words": len(found),
    })


# --- Link extraction ---


async def extract_links(
    album_slug: str,
    file_name: str = "SOURCES.md",
) -> str:
    """Extract markdown links from an album file.

    Scans SOURCES.md, RESEARCH.md, or a track file for [text](url) links.
    Useful for source verification workflows.

    Args:
        album_slug: Album slug (e.g., "my-album")
        file_name: File to scan — "SOURCES.md", "RESEARCH.md", "README.md",
                   or a track slug like "01-track-name" (resolves to track file)

    Returns:
        JSON with {links: [{text, url, line_number}], count: int}
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    album_path = album.get("path", "")

    # Determine file path
    file_path = None
    normalized_file = _normalize_slug(file_name)

    # Check if it's a track slug
    tracks = album.get("tracks", {})
    track = tracks.get(normalized_file)
    if not track:
        # Try prefix match
        prefix_matches = {s: d for s, d in tracks.items()
                         if s.startswith(normalized_file)}
        if len(prefix_matches) == 1:
            track = next(iter(prefix_matches.values()))

    if track:
        file_path = track.get("path", "")
    else:
        # It's a file name in the album directory
        candidate = Path(album_path) / file_name
        if candidate.exists():
            file_path = str(candidate)

    if not file_path:
        return _safe_json({
            "found": False,
            "error": f"File '{file_name}' not found in album '{album_slug}'",
        })

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read file: {e}"})

    links = []
    for line_num, line in enumerate(text.split("\n"), 1):
        for match in _MARKDOWN_LINK_RE.finditer(line):
            links.append({
                "text": match.group(1),
                "url": match.group(2),
                "line_number": line_num,
            })

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "file_name": file_name,
        "file_path": file_path,
        "links": links,
        "count": len(links),
    })


# --- Lyrics stats ---

# Genre word-count targets from craft-reference.md
_GENRE_WORD_TARGETS = {
    "pop":        {"min": 150, "max": 250},
    "dance-pop":  {"min": 150, "max": 250},
    "synth-pop":  {"min": 150, "max": 250},
    "punk":       {"min": 150, "max": 250},
    "pop-punk":   {"min": 150, "max": 250},
    "rock":       {"min": 200, "max": 350},
    "alt-rock":   {"min": 200, "max": 350},
    "folk":       {"min": 200, "max": 350},
    "country":    {"min": 200, "max": 350},
    "americana":  {"min": 200, "max": 350},
    "hip-hop":    {"min": 300, "max": 500},
    "rap":        {"min": 300, "max": 500},
    "ballad":     {"min": 200, "max": 300},
    "electronic": {"min": 100, "max": 200},
    "edm":        {"min": 100, "max": 200},
    "ambient":    {"min": 50,  "max": 150},
    "lo-fi":      {"min": 50,  "max": 150},
}


def _tokenize_lyrics_by_line(lyrics: str) -> list:
    """Split lyrics into per-line word lists, skipping section tags.

    Lowercases all words, strips leading/trailing apostrophes, and filters
    out single-character tokens.
    """
    result = []
    for line in lyrics.split("\n"):
        stripped = line.strip()
        if not stripped or _SECTION_TAG_RE.match(stripped):
            continue
        words = []
        for token in _WORD_TOKEN_RE.findall(stripped.lower()):
            # Strip leading/trailing apostrophes (e.g., 'bout -> bout)
            clean = token.strip("'")
            if len(clean) > 1:
                words.append(clean)
        if words:
            result.append(words)
    return result


def _ngrams_from_lines(lines: list, min_n: int = 2, max_n: int = 4) -> list:
    """Generate n-grams from per-line word lists, never crossing line boundaries.

    Skips n-grams where every word is a stopword.
    """
    phrases = []
    for words in lines:
        for n in range(min_n, max_n + 1):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]
                # Skip if all words are stopwords
                if all(w in _CROSS_TRACK_STOPWORDS for w in gram):
                    continue
                phrases.append(" ".join(gram))
    return phrases


async def get_lyrics_stats(
    album_slug: str,
    track_slug: str = "",
) -> str:
    """Get word count, character count, and genre target comparison for lyrics.

    Counts lyrics excluding section tags. Compares against genre-appropriate
    word count targets from the craft reference. Flags tracks that are over
    the 800-word danger zone (Suno rushes/compresses).

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Specific track slug/number (empty = all tracks)

    Returns:
        JSON with per-track stats and genre targets
    """
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    genre = album.get("genre", "").lower()
    all_tracks = album.get("tracks", {})

    # Determine which tracks
    if track_slug:
        matched_slug, track_data, error = _find_track_or_error(all_tracks, track_slug, album_slug)
        if error:
            return error
        tracks_to_check = {matched_slug: track_data}
    else:
        tracks_to_check = all_tracks

    # Get genre target
    target = _GENRE_WORD_TARGETS.get(genre, {"min": 150, "max": 350})

    track_results = []
    for t_slug, t_data in sorted(tracks_to_check.items()):
        track_path = t_data.get("path", "")
        if not track_path:
            track_results.append({
                "track_slug": t_slug,
                "title": t_data.get("title", t_slug),
                "error": "No file path",
            })
            continue

        try:
            text = Path(track_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            track_results.append({
                "track_slug": t_slug,
                "title": t_data.get("title", t_slug),
                "error": "Cannot read file",
            })
            continue

        # Extract Lyrics Box
        lyrics_section = _extract_markdown_section(text, "Lyrics Box")
        lyrics = ""
        if lyrics_section:
            code = _extract_code_block(lyrics_section)
            lyrics = code if code else lyrics_section

        if not lyrics.strip():
            track_results.append({
                "track_slug": t_slug,
                "title": t_data.get("title", t_slug),
                "word_count": 0,
                "char_count": 0,
                "line_count": 0,
                "section_count": 0,
                "status": "EMPTY",
            })
            continue

        # Count words excluding section tags
        words = []
        section_count = 0
        content_lines = 0
        for line in lyrics.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if _SECTION_TAG_RE.match(stripped):
                section_count += 1
                continue
            content_lines += 1
            words.extend(stripped.split())

        word_count = len(words)
        char_count = len(lyrics.strip())

        # Determine status
        if word_count > 800:
            status = "DANGER"
            note = "Over 800 words — Suno will rush/compress/skip sections"
        elif word_count > target["max"]:
            status = "OVER"
            note = f"Over target ({target['max']} max for {genre})"
        elif word_count < target["min"]:
            status = "UNDER"
            note = f"Under target ({target['min']} min for {genre})"
        else:
            status = "OK"
            note = f"Within target ({target['min']}–{target['max']} for {genre})"

        track_results.append({
            "track_slug": t_slug,
            "title": t_data.get("title", t_slug),
            "word_count": word_count,
            "char_count": char_count,
            "line_count": content_lines,
            "section_count": section_count,
            "status": status,
            "note": note,
        })

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "genre": genre,
        "target": target,
        "tracks": track_results,
    })


async def check_cross_track_repetition(
    album_slug: str,
    min_tracks: int = 3,
) -> str:
    """Scan all tracks in an album for words/phrases repeated across multiple tracks.

    Extracts lyrics from every track, tokenizes into words and 2-4 word
    n-grams, and flags items appearing in N+ tracks. Filters out stopwords
    and common song vocabulary automatically.

    Args:
        album_slug: Album slug (e.g., "my-album")
        min_tracks: Minimum number of tracks a word/phrase must appear in
                    to be flagged (default 3, floor 2)

    Returns:
        JSON with flagged words, phrases, and summary stats
    """
    # Floor min_tracks at 2 — repeating in 1 track is not cross-track
    if min_tracks < 2:
        min_tracks = 2

    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    all_tracks = album.get("tracks", {})
    if not all_tracks:
        return _safe_json({
            "found": True,
            "album_slug": normalized_album,
            "track_count": 0,
            "min_tracks_threshold": min_tracks,
            "repeated_words": [],
            "repeated_phrases": [],
            "summary": {
                "flagged_words": 0,
                "flagged_phrases": 0,
                "most_repeated_word": None,
                "most_repeated_phrase": None,
            },
        })

    # Per-track word and phrase sets, plus occurrence counts
    # word -> set of track slugs where it appears
    word_tracks: dict[str, set] = {}
    # word -> total count across all tracks
    word_total: dict[str, int] = {}
    # phrase -> set of track slugs
    phrase_tracks: dict[str, set] = {}
    # phrase -> total count across all tracks
    phrase_total: dict[str, int] = {}

    tracks_analyzed = 0

    for t_slug, t_data in sorted(all_tracks.items()):
        track_path = t_data.get("path", "")
        if not track_path:
            continue

        try:
            text = Path(track_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Extract Lyrics Box
        lyrics_section = _extract_markdown_section(text, "Lyrics Box")
        lyrics = ""
        if lyrics_section:
            code = _extract_code_block(lyrics_section)
            lyrics = code if code else lyrics_section

        if not lyrics.strip():
            continue

        tracks_analyzed += 1
        lines = _tokenize_lyrics_by_line(lyrics)

        # Count words for this track
        track_word_counts: dict[str, int] = {}
        for words in lines:
            for w in words:
                track_word_counts[w] = track_word_counts.get(w, 0) + 1

        for w, count in track_word_counts.items():
            if w not in word_tracks:
                word_tracks[w] = set()
                word_total[w] = 0
            word_tracks[w].add(t_slug)
            word_total[w] += count

        # Count phrases for this track
        phrases = _ngrams_from_lines(lines)
        track_phrase_counts: dict[str, int] = {}
        for p in phrases:
            track_phrase_counts[p] = track_phrase_counts.get(p, 0) + 1

        for p, count in track_phrase_counts.items():
            if p not in phrase_tracks:
                phrase_tracks[p] = set()
                phrase_total[p] = 0
            phrase_tracks[p].add(t_slug)
            phrase_total[p] += count

    # Filter to items in >= min_tracks, exclude stopwords for words
    repeated_words = []
    for w, track_set in word_tracks.items():
        if len(track_set) >= min_tracks and w not in _CROSS_TRACK_STOPWORDS:
            repeated_words.append({
                "word": w,
                "track_count": len(track_set),
                "tracks": sorted(track_set),
                "total_occurrences": word_total[w],
            })

    repeated_phrases = []
    for p, track_set in phrase_tracks.items():
        if len(track_set) >= min_tracks:
            repeated_phrases.append({
                "phrase": p,
                "track_count": len(track_set),
                "tracks": sorted(track_set),
                "total_occurrences": phrase_total[p],
            })

    # Sort by track_count descending, then alphabetically
    repeated_words.sort(key=lambda x: (-x["track_count"], x["word"]))
    repeated_phrases.sort(key=lambda x: (-x["track_count"], x["phrase"]))

    summary = {
        "flagged_words": len(repeated_words),
        "flagged_phrases": len(repeated_phrases),
        "most_repeated_word": repeated_words[0] if repeated_words else None,
        "most_repeated_phrase": repeated_phrases[0] if repeated_phrases else None,
    }

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "track_count": tracks_analyzed,
        "min_tracks_threshold": min_tracks,
        "repeated_words": repeated_words,
        "repeated_phrases": repeated_phrases,
        "summary": summary,
    })


def register(mcp):
    """Register text analysis tools with the MCP server."""
    mcp.tool()(check_homographs)
    mcp.tool()(scan_artist_names)
    mcp.tool()(check_pronunciation_enforcement)
    mcp.tool()(check_explicit_content)
    mcp.tool()(extract_links)
    mcp.tool()(get_lyrics_stats)
    mcp.tool()(check_cross_track_repetition)
