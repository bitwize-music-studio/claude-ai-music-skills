"""Pre-generation gates and release readiness checks."""

import logging
import re
from pathlib import Path
from typing import Optional

from handlers._shared import (
    _safe_json, _extract_markdown_section, _extract_code_block,
    _find_album_or_error, _find_track_or_error,
    _SECTION_TAG_RE, _STREAMING_PLACEHOLDER_MARKERS,
)
from handlers import _shared
from handlers import text_analysis as _text_analysis

logger = logging.getLogger("bitwize-music-state")


# =============================================================================
# Pre-Generation Gates
# =============================================================================


def _check_pre_gen_gates_for_track(
    t_data: dict, file_text: Optional[str], blocklist: list,
    max_lyric_words: int = 800,
) -> tuple[int, int, list[dict]]:
    """Run pre-generation gates on a single track.

    Returns (blocking_count, warning_count, gates_list).
    """
    gates: list[dict] = []
    blocking = 0
    warning_count = 0

    # Gate 1: Sources Verified
    sources = t_data.get("sources_verified", "N/A")
    if sources.lower() == "pending":
        gates.append({"gate": "Sources Verified", "status": "FAIL", "severity": "BLOCKING",
                      "detail": "Sources not yet verified by human"})
        blocking += 1
    else:
        gates.append({"gate": "Sources Verified", "status": "PASS",
                      "detail": f"Status: {sources}"})

    # Gate 2: Lyrics Reviewed
    lyrics_content = None
    if file_text:
        lyrics_section = _extract_markdown_section(file_text, "Lyrics Box")
        if lyrics_section:
            lyrics_content = _extract_code_block(lyrics_section)

    if not lyrics_content or not lyrics_content.strip():
        gates.append({"gate": "Lyrics Reviewed", "status": "FAIL", "severity": "BLOCKING",
                      "detail": "Lyrics Box is empty"})
        blocking += 1
    elif re.search(r'\[TODO\]|\[PLACEHOLDER\]', lyrics_content, re.IGNORECASE):
        gates.append({"gate": "Lyrics Reviewed", "status": "FAIL", "severity": "BLOCKING",
                      "detail": "Lyrics contain [TODO] or [PLACEHOLDER] markers"})
        blocking += 1
    else:
        gates.append({"gate": "Lyrics Reviewed", "status": "PASS",
                      "detail": "Lyrics populated"})

    # Gate 3: Pronunciation Resolved
    if file_text:
        pron_section = _extract_markdown_section(file_text, "Pronunciation Notes")
        pron_entries = []
        if pron_section:
            for line in pron_section.split("\n"):
                if not line.startswith("|") or "---" in line or "Word" in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    word = parts[1].strip()
                    phonetic = parts[2].strip()
                    if word and word != "—" and phonetic and phonetic != "—":
                        pron_entries.append({"word": word, "phonetic": phonetic})

        if pron_entries and lyrics_content:
            unapplied = []
            for entry in pron_entries:
                if not re.search(re.escape(entry["phonetic"]), lyrics_content, re.IGNORECASE):
                    unapplied.append(entry["word"])
            if unapplied:
                gates.append({"gate": "Pronunciation Resolved", "status": "FAIL", "severity": "BLOCKING",
                              "detail": f"Unapplied: {', '.join(unapplied)}"})
                blocking += 1
            else:
                gates.append({"gate": "Pronunciation Resolved", "status": "PASS",
                              "detail": f"All {len(pron_entries)} entries applied"})
        else:
            gates.append({"gate": "Pronunciation Resolved", "status": "PASS",
                          "detail": "No pronunciation entries to check"})
    else:
        gates.append({"gate": "Pronunciation Resolved", "status": "SKIP",
                      "detail": "Track file not readable"})

    # Gate 4: Explicit Flag Set
    explicit = t_data.get("explicit")
    if explicit is None:
        gates.append({"gate": "Explicit Flag Set", "status": "FAIL", "severity": "BLOCKING",
                      "detail": "Explicit field not set — set to Yes or No before generating"})
        blocking += 1
    else:
        gates.append({"gate": "Explicit Flag Set", "status": "PASS",
                      "detail": f"Explicit: {'Yes' if explicit else 'No'}"})

    # Gate 5: Style Prompt Complete
    style_content = None
    if file_text:
        style_section = _extract_markdown_section(file_text, "Style Box")
        if style_section:
            style_content = _extract_code_block(style_section)

    if not style_content or not style_content.strip():
        gates.append({"gate": "Style Prompt Complete", "status": "FAIL", "severity": "BLOCKING",
                      "detail": "Style Box is empty"})
        blocking += 1
    else:
        gates.append({"gate": "Style Prompt Complete", "status": "PASS",
                      "detail": f"Style prompt: {len(style_content)} chars"})

    # Gate 6: Artist Names Cleared (uses pre-compiled patterns)
    if style_content:
        found_artists = []
        for entry in blocklist:
            name = entry["name"]
            pattern = _text_analysis._artist_blocklist_patterns.get(name)
            if pattern and pattern.search(style_content):
                found_artists.append(name)

        if found_artists:
            gates.append({"gate": "Artist Names Cleared", "status": "FAIL", "severity": "BLOCKING",
                          "detail": f"Found: {', '.join(found_artists)}"})
            blocking += 1
        else:
            gates.append({"gate": "Artist Names Cleared", "status": "PASS",
                          "detail": "No blocked artist names found"})
    else:
        gates.append({"gate": "Artist Names Cleared", "status": "SKIP",
                      "detail": "No style prompt to check"})

    # Gate 7: Homograph Check — scan lyrics for unresolved homographs
    if lyrics_content and lyrics_content.strip():
        found_homographs = []
        for line in lyrics_content.split("\n"):
            stripped = line.strip()
            # Skip section tags like [Verse 1], [Chorus], etc.
            if stripped.startswith("[") and stripped.endswith("]"):
                continue
            for word, pattern in _text_analysis._HOMOGRAPH_PATTERNS.items():
                if pattern.search(line):
                    if word not in found_homographs:
                        found_homographs.append(word)
        if found_homographs:
            gates.append({"gate": "Homograph Check", "status": "FAIL", "severity": "BLOCKING",
                          "detail": f"Unresolved homographs: {', '.join(found_homographs)}"})
            blocking += 1
        else:
            gates.append({"gate": "Homograph Check", "status": "PASS",
                          "detail": "No homograph risks found"})
    elif not lyrics_content or not lyrics_content.strip():
        gates.append({"gate": "Homograph Check", "status": "SKIP",
                      "detail": "No lyrics to check"})

    # Gate 8: Lyric Length — configurable word count limit
    if lyrics_content and lyrics_content.strip():
        lyric_words = [
            w for line in lyrics_content.split("\n")
            if line.strip() and not _SECTION_TAG_RE.match(line.strip())
            for w in line.split() if w
        ]
        wc = len(lyric_words)
        if wc > max_lyric_words:
            gates.append({"gate": "Lyric Length", "status": "FAIL", "severity": "BLOCKING",
                          "detail": f"Lyrics are {wc} words — limit is {max_lyric_words}"})
            blocking += 1
        else:
            gates.append({"gate": "Lyric Length", "status": "PASS",
                          "detail": f"{wc} words (limit {max_lyric_words})"})
    else:
        gates.append({"gate": "Lyric Length", "status": "SKIP",
                      "detail": "No lyrics to check"})

    return blocking, warning_count, gates


async def run_pre_generation_gates(
    album_slug: str,
    track_slug: str = "",
) -> str:
    """Run all 8 pre-generation validation gates on a track or album.

    Gates:
        1. Sources Verified — sources_verified is not "Pending"
        2. Lyrics Reviewed — Lyrics Box populated, no [TODO]/[PLACEHOLDER]
        3. Pronunciation Resolved — All Pronunciation Notes entries applied
        4. Explicit Flag Set — Explicit field is "Yes" or "No"
        5. Style Prompt Complete — Non-empty Style Box with content
        6. Artist Names Cleared — No real artist names in Style Box
        7. Homograph Check — No unresolved homographs in lyrics
        8. Lyric Length — Lyrics under 800-word Suno limit

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Specific track slug/number (empty = all tracks)

    Returns:
        JSON with per-track gate results and verdicts
    """
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    all_tracks = album.get("tracks", {})

    # Determine which tracks to check
    if track_slug:
        matched_slug, track_data, error = _find_track_or_error(all_tracks, track_slug, album_slug)
        if error:
            return error
        tracks_to_check = {matched_slug: track_data}
    else:
        tracks_to_check = all_tracks

    # Load artist blocklist for gate 6
    blocklist = _text_analysis._load_artist_blocklist()

    # Read configurable gate limits
    state = _shared.cache.get_state()
    state_config = state.get("config", {})
    gen_cfg = state_config.get("generation", {})
    max_lyric_words = gen_cfg.get("max_lyric_words", 800)

    track_results = []
    total_blocking = 0
    total_warnings = 0

    for t_slug, t_data in sorted(tracks_to_check.items()):
        # Read track file if available
        file_text = None
        track_path = t_data.get("path", "")
        if track_path:
            try:
                file_text = Path(track_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read track file for pre-gen gates %s: %s", track_path, e)

        blocking, warning_count, gates = _check_pre_gen_gates_for_track(
            t_data, file_text, blocklist,
            max_lyric_words=max_lyric_words,
        )

        verdict = "READY" if blocking == 0 else "NOT READY"
        total_blocking += blocking
        total_warnings += warning_count

        track_results.append({
            "track_slug": t_slug,
            "title": t_data.get("title", t_slug),
            "verdict": verdict,
            "blocking": blocking,
            "warnings": warning_count,
            "gates": gates,
        })

    if len(tracks_to_check) == 1:
        album_verdict = track_results[0]["verdict"]
    elif total_blocking == 0:
        album_verdict = "ALL READY"
    elif any(t["blocking"] == 0 for t in track_results):
        album_verdict = "PARTIAL"
    else:
        album_verdict = "NOT READY"

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "album_verdict": album_verdict,
        "total_tracks": len(track_results),
        "total_blocking": total_blocking,
        "total_warnings": total_warnings,
        "tracks": track_results,
    })


# =============================================================================
# Release Readiness Checks
# =============================================================================

# End-of-line punctuation that shouldn't appear in streaming lyrics.
# Ellipsis (...) is allowed, so we match single trailing punctuation only.
_END_PUNCT_RE = re.compile(r'[.,:;!?]$')


async def check_streaming_lyrics(album_slug: str, track_slug: str = "") -> str:
    """Check streaming lyrics readiness for an album's tracks.

    Validates that each track has properly formatted streaming lyrics
    (plain text for Spotify/Apple Music). Runs 7 checks per track:
        1. Section Exists — "Streaming Lyrics" heading found
        2. Not Empty — Code block has content beyond whitespace
        3. Not Placeholder — Content doesn't match template placeholder
        4. No Section Tags — No [Verse], [Chorus] etc. lines
        5. Lines Capitalized — Non-blank lines start uppercase
        6. No End Punctuation — Lines don't end with .,:;!? (ellipsis allowed)
        7. Word Count — >= 20 words; if Suno Lyrics exist, >= 80% of Suno count

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Specific track slug/number (empty = all tracks)

    Returns:
        JSON with per-track check results and verdicts
    """
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    all_tracks = album.get("tracks", {})

    # Determine which tracks to check
    if track_slug:
        matched_slug, track_data, error = _find_track_or_error(all_tracks, track_slug, album_slug)
        if error:
            return error
        tracks_to_check = {matched_slug: track_data}
    else:
        tracks_to_check = all_tracks

    track_results = []
    total_blocking = 0
    total_warnings = 0

    for t_slug, t_data in sorted(tracks_to_check.items()):
        checks = []
        blocking = 0
        warning_count = 0
        streaming_word_count = 0
        suno_word_count = 0

        # Read track file
        file_text = None
        track_path = t_data.get("path", "")
        if track_path:
            try:
                file_text = Path(track_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read track file for streaming check %s: %s",
                               track_path, e)

        # Extract streaming lyrics section
        streaming_content = None
        if file_text:
            streaming_section = _extract_markdown_section(file_text, "Streaming Lyrics")
            if streaming_section:
                streaming_content = _extract_code_block(streaming_section)

        # Check 1: Section Exists
        if not file_text:
            checks.append({"check": "Section Exists", "status": "FAIL", "severity": "BLOCKING",
                           "detail": "Track file not readable"})
            blocking += 1
        elif _extract_markdown_section(file_text, "Streaming Lyrics") is None:
            checks.append({"check": "Section Exists", "status": "FAIL", "severity": "BLOCKING",
                           "detail": "No '## Streaming Lyrics' heading found"})
            blocking += 1
        else:
            checks.append({"check": "Section Exists", "status": "PASS",
                           "detail": "Section heading found"})

        # Check 2: Not Empty
        if streaming_content and streaming_content.strip():
            checks.append({"check": "Not Empty", "status": "PASS",
                           "detail": "Content present"})
        else:
            checks.append({"check": "Not Empty", "status": "FAIL", "severity": "BLOCKING",
                           "detail": "Streaming lyrics code block is empty or missing"})
            blocking += 1

        # Check 3: Not Placeholder
        if streaming_content and streaming_content.strip():
            is_placeholder = any(
                marker.lower() in streaming_content.lower()
                for marker in _STREAMING_PLACEHOLDER_MARKERS
            )
            if is_placeholder:
                checks.append({"check": "Not Placeholder", "status": "FAIL", "severity": "BLOCKING",
                               "detail": "Content matches template placeholder text"})
                blocking += 1
            else:
                checks.append({"check": "Not Placeholder", "status": "PASS",
                               "detail": "Content is not placeholder"})
        else:
            checks.append({"check": "Not Placeholder", "status": "SKIP",
                           "detail": "No content to check"})

        # Checks 4-7 only run if we have actual content
        if streaming_content and streaming_content.strip():
            lines = streaming_content.split("\n")
            non_blank_lines = [(i + 1, line) for i, line in enumerate(lines) if line.strip()]

            # Check 4: No Section Tags
            tagged_lines = [(ln, line.strip()) for ln, line in non_blank_lines
                            if _SECTION_TAG_RE.match(line.strip())]
            if tagged_lines:
                examples = ", ".join(f"{tag} (line {ln})" for ln, tag in tagged_lines[:5])
                if len(tagged_lines) > 5:
                    examples += f", ... ({len(tagged_lines)} total)"
                checks.append({"check": "No Section Tags", "status": "WARN", "severity": "WARNING",
                               "detail": f"Found {len(tagged_lines)} tag(s): {examples}"})
                warning_count += 1
            else:
                checks.append({"check": "No Section Tags", "status": "PASS",
                               "detail": "No section tags found"})

            # Check 5: Lines Capitalized
            uncapped = [(ln, line.strip()) for ln, line in non_blank_lines
                        if line.strip() and not line.strip()[0].isupper()
                        and not _SECTION_TAG_RE.match(line.strip())]
            if uncapped:
                examples = ", ".join(
                    f"line {ln}: \"{text[:40]}\"" for ln, text in uncapped[:5]
                )
                if len(uncapped) > 5:
                    examples += f", ... ({len(uncapped)} total)"
                checks.append({"check": "Lines Capitalized", "status": "WARN", "severity": "WARNING",
                               "detail": f"{len(uncapped)} line(s) not capitalized: {examples}"})
                warning_count += 1
            else:
                checks.append({"check": "Lines Capitalized", "status": "PASS",
                               "detail": "All lines start uppercase"})

            # Check 6: No End Punctuation (ellipsis ... is allowed)
            punctuated = []
            for ln, line in non_blank_lines:
                stripped = line.strip()
                if _SECTION_TAG_RE.match(stripped):
                    continue
                # Allow ellipsis (... or more dots)
                if stripped.endswith("..."):
                    continue
                if _END_PUNCT_RE.search(stripped):
                    punctuated.append((ln, stripped))
            if punctuated:
                examples = ", ".join(
                    f"line {ln}: \"{text[-30:]}\"" for ln, text in punctuated[:5]
                )
                if len(punctuated) > 5:
                    examples += f", ... ({len(punctuated)} total)"
                checks.append({"check": "No End Punctuation", "status": "WARN", "severity": "WARNING",
                               "detail": f"{len(punctuated)} line(s) end with punctuation: {examples}"})
                warning_count += 1
            else:
                checks.append({"check": "No End Punctuation", "status": "PASS",
                               "detail": "No trailing punctuation found"})

            # Check 7: Word Count
            # Count words excluding section tags
            words = []
            for line in lines:
                stripped = line.strip()
                if not stripped or _SECTION_TAG_RE.match(stripped):
                    continue
                words.extend(stripped.split())
            streaming_word_count = len(words)

            # Get Suno lyrics word count for comparison
            if file_text:
                suno_section = _extract_markdown_section(file_text, "Lyrics Box")
                if suno_section:
                    suno_content = _extract_code_block(suno_section)
                    if suno_content:
                        suno_words = []
                        for sline in suno_content.split("\n"):
                            s = sline.strip()
                            if not s or _SECTION_TAG_RE.match(s):
                                continue
                            suno_words.extend(s.split())
                        suno_word_count = len(suno_words)

            if streaming_word_count < 20:
                checks.append({"check": "Word Count", "status": "WARN", "severity": "WARNING",
                               "detail": f"Only {streaming_word_count} words (minimum 20 expected)"})
                warning_count += 1
            elif suno_word_count > 0 and streaming_word_count < suno_word_count * 0.8:
                pct = round(streaming_word_count / suno_word_count * 100)
                checks.append({"check": "Word Count", "status": "WARN", "severity": "WARNING",
                               "detail": f"{streaming_word_count} words = {pct}% of Suno lyrics "
                                         f"({suno_word_count} words). Expected >= 80%"})
                warning_count += 1
            else:
                detail = f"{streaming_word_count} words"
                if suno_word_count > 0:
                    pct = round(streaming_word_count / suno_word_count * 100)
                    detail += f" ({pct}% of Suno lyrics)"
                checks.append({"check": "Word Count", "status": "PASS", "detail": detail})
        else:
            # No content — skip content-dependent checks
            for check_name in ("No Section Tags", "Lines Capitalized",
                               "No End Punctuation", "Word Count"):
                checks.append({"check": check_name, "status": "SKIP",
                               "detail": "No content to check"})

        verdict = "READY" if blocking == 0 else "NOT READY"
        total_blocking += blocking
        total_warnings += warning_count

        result = {
            "track_slug": t_slug,
            "title": t_data.get("title", t_slug),
            "verdict": verdict,
            "blocking": blocking,
            "warnings": warning_count,
            "word_count": streaming_word_count,
            "checks": checks,
        }
        if suno_word_count > 0:
            result["suno_word_count"] = suno_word_count
        track_results.append(result)

    if len(tracks_to_check) == 1:
        album_verdict = track_results[0]["verdict"]
    elif total_blocking == 0:
        album_verdict = "ALL READY"
    elif any(t["blocking"] == 0 for t in track_results):
        album_verdict = "PARTIAL"
    else:
        album_verdict = "NOT READY"

    return _safe_json({
        "found": True,
        "album_slug": normalized_album,
        "album_verdict": album_verdict,
        "total_tracks": len(track_results),
        "total_blocking": total_blocking,
        "total_warnings": total_warnings,
        "tracks": track_results,
    })


# =============================================================================
# Registration
# =============================================================================


def register(mcp):
    mcp.tool()(run_pre_generation_gates)
    mcp.tool()(check_streaming_lyrics)
