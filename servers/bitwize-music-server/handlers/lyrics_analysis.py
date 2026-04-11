"""Lyrics analysis tools — plagiarism detection, syllable counting, readability, rhyme analysis."""

from __future__ import annotations

import statistics
from typing import Any

from handlers._shared import (
    _CROSS_TRACK_STOPWORDS,
    _SECTION_TAG_RE,
    _WORD_TOKEN_RE,
    _check_text_length,
    _safe_json,
)

# =============================================================================
# Plagiarism / Distinctive Phrase Extraction
# =============================================================================

# Common song cliches — phrases so ubiquitous they're not useful plagiarism signals.
_COMMON_SONG_PHRASES = frozenset({
    # Love / heartbreak
    "break my heart", "broke my heart", "breaking my heart",
    "falling in love", "fall in love", "fell in love",
    "heart and soul", "heart on my sleeve",
    "love you forever", "love you more",
    "hold me close", "hold me tight",
    "never let go", "never let you go",
    "take my hand", "hold my hand",
    "tear me apart", "tore me apart",
    "missing you tonight", "thinking of you",
    "all my love", "give my love",
    "you and me", "me and you",
    # Night / time
    "middle of the night", "dead of night",
    "end of the world", "end of time",
    "light of day", "break of dawn",
    "run out of time", "running out of time",
    "turn back time", "stand the test of time",
    "day and night", "night and day",
    # Pain / struggle
    "pain inside", "pain in my heart",
    "down on my knees", "brought to my knees",
    "weight of the world", "world on my shoulders",
    "lost my mind", "losing my mind",
    "break me down", "breaking me down",
    "pick me up", "lift me up",
    "fight for you", "fight for love",
    "set me free", "set you free",
    "let me go", "let it go",
    # Movement / journey
    "walking away", "walk away",
    "running away", "run away",
    "long way home", "find my way",
    "find my way home", "find my way back",
    "road to nowhere", "path to follow",
    # Fire / light
    "burning inside", "fire inside",
    "light in the dark", "light in the darkness",
    "shine so bright", "shining bright",
    "spark in the dark",
    # Generic emotional
    "cant stop thinking", "cant get enough",
    "never be the same", "nothing is the same",
    "over and over", "again and again",
    "round and round", "on and on",
    "the way you make me feel",
    "what you do to me", "what you mean to me",
    "take me away", "far away",
    "here with me", "stay with me",
    "come back to me", "back to you",
    "all night long", "tonight tonight",
    "dreams come true", "make it through",
    "side by side", "hand in hand",
    "once upon a time", "happily ever after",
})

# Section priority for ranking phrase importance.
# Higher = more important for plagiarism (chorus hooks matter most).
_SECTION_PRIORITY = {
    "chorus": 3,
    "hook": 3,
    "pre-chorus": 2,
    "bridge": 2,
    "outro": 2,
    "verse": 1,
    "intro": 1,
    "end": 1,
}


def _tokenize_lyrics_with_sections(lyrics: str) -> list[dict[str, Any]]:
    """Split lyrics into per-line dicts tracking section context.

    Returns a list of dicts, each with:
        section: str — current section name (e.g., "Chorus", "Verse 1")
        section_type: str — normalized type (e.g., "chorus", "verse")
        line_number: int — 1-based line number in original text
        words: list[str] — lowercased, cleaned word tokens
        raw_line: str — original line text (stripped)
    """
    result = []
    current_section = "Unknown"
    current_section_type = "verse"  # default

    for line_num, line in enumerate(lyrics.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            continue

        # Check for section tag
        if _SECTION_TAG_RE.match(stripped):
            # Extract section name from brackets
            current_section = stripped[1:-1].strip()
            # Normalize section type (strip numbers: "Verse 2" -> "verse")
            section_lower = current_section.lower()
            # Check longest keys first so "pre-chorus" matches before "chorus"
            for stype in sorted(_SECTION_PRIORITY, key=len, reverse=True):
                if stype in section_lower:
                    current_section_type = stype
                    break
            else:
                current_section_type = "verse"  # default for unknown sections
            continue

        # Tokenize the line
        words = []
        for token in _WORD_TOKEN_RE.findall(stripped.lower()):
            clean = token.strip("'")
            if len(clean) > 1:
                words.append(clean)

        if words:
            result.append({
                "section": current_section,
                "section_type": current_section_type,
                "line_number": line_num,
                "words": words,
                "raw_line": stripped,
            })

    return result


def _extract_distinctive_ngrams(
    lines_with_sections: list[dict[str, Any]],
    min_n: int = 4,
    max_n: int = 7,
) -> list[dict[str, Any]]:
    """Extract distinctive n-grams from section-aware tokenized lines.

    Generates n-grams of length min_n..max_n, filters out:
      - n-grams where ALL words are stopwords
      - n-grams matching common song cliches
    Deduplicates by keeping the highest-priority section occurrence.
    Returns sorted by priority descending, then word count descending.
    """
    # phrase -> best entry (highest priority)
    seen: dict[str, dict[str, Any]] = {}

    for line_data in lines_with_sections:
        words = line_data["words"]
        priority = _SECTION_PRIORITY.get(line_data["section_type"], 1)

        for n in range(min_n, max_n + 1):
            for i in range(len(words) - n + 1):
                gram = words[i:i + n]

                # Skip if all stopwords
                if all(w in _CROSS_TRACK_STOPWORDS for w in gram):
                    continue

                phrase = " ".join(gram)

                # Skip common song cliches
                if phrase in _COMMON_SONG_PHRASES:
                    continue

                # Keep highest-priority occurrence
                if phrase not in seen or priority > seen[phrase]["priority"]:
                    seen[phrase] = {
                        "phrase": phrase,
                        "word_count": n,
                        "section": line_data["section"],
                        "section_type": line_data["section_type"],
                        "line_number": line_data["line_number"],
                        "raw_line": line_data["raw_line"],
                        "priority": priority,
                    }

    # Sort: priority desc, word_count desc, phrase asc
    results = sorted(
        seen.values(),
        key=lambda x: (-x["priority"], -x["word_count"], x["phrase"]),
    )
    return results


async def extract_distinctive_phrases(
    text: str,
    max_phrases: int = 0,
    include_raw_lines: bool = True,
) -> str:
    """Extract distinctive phrases from lyrics for plagiarism checking.

    Takes raw lyrics text, extracts 4-7 word n-grams with section awareness,
    filters common song cliches and stopword-only phrases, and ranks by
    section priority (chorus/hook > verse). Returns phrases and pre-formatted
    web search suggestions.

    Args:
        text: Lyrics text to scan (with [Section] tags)
        max_phrases: Maximum number of phrases to return (0 = all, default)
        include_raw_lines: Include raw_line field in each phrase entry
                          (default True; set False to reduce payload size)

    Returns:
        JSON with {phrases: [...], total_phrases: int, truncated: bool,
                   sections_found: [...], search_suggestions: [...]}
    """
    if not text or not text.strip():
        return _safe_json({
            "phrases": [],
            "total_phrases": 0,
            "truncated": False,
            "sections_found": [],
            "search_suggestions": [],
        })

    err = _check_text_length(text, "extract_distinctive_phrases")
    if err:
        return err

    # Tokenize with section tracking
    lines = _tokenize_lyrics_with_sections(text)

    # Extract distinctive n-grams
    ngrams = _extract_distinctive_ngrams(lines)

    # Collect unique sections found
    sections_found = sorted({
        line_data["section"]
        for line_data in lines
    })

    # Build phrases list
    total_phrases = len(ngrams)
    truncated = max_phrases > 0 and total_phrases > max_phrases
    output_ngrams = ngrams[:max_phrases] if max_phrases > 0 else ngrams

    phrases = []
    for ng in output_ngrams:
        entry: dict[str, Any] = {
            "phrase": ng["phrase"],
            "word_count": ng["word_count"],
            "section": ng["section"],
            "line_number": ng["line_number"],
            "priority": ng["priority"],
        }
        if include_raw_lines:
            entry["raw_line"] = ng["raw_line"]
        phrases.append(entry)

    # Build search suggestions — top 15, formatted for WebSearch
    search_suggestions = []
    for ng in ngrams[:15]:
        search_suggestions.append({
            "query": f'"{ng["phrase"]}" lyrics',
            "priority": ng["priority"],
            "section": ng["section"],
        })

    return _safe_json({
        "phrases": phrases,
        "total_phrases": total_phrases,
        "truncated": truncated,
        "sections_found": sections_found,
        "search_suggestions": search_suggestions,
    })


# ---------------------------------------------------------------------------
# Lyrics Analysis Helpers
# ---------------------------------------------------------------------------

def _count_syllables_word(word: str) -> int:
    """Count syllables in a single word using vowel cluster heuristic.

    Rules:
    1. Count vowel groups (aeiouy; consecutive vowels = 1 group)
    2. Subtract trailing silent 'e' if count > 1
    3. Handle consonant-'le' endings (bottle, apple — add 1)
    4. Floor at 1
    """
    if not word:
        return 0
    word = word.lower().strip("'")
    if not word:
        return 0

    vowels = set("aeiouy")
    count = 0
    prev_vowel = False

    for char in word:
        if char in vowels:
            if not prev_vowel:
                count += 1
            prev_vowel = True
        else:
            prev_vowel = False

    # Silent 'e' at end
    if word.endswith("e") and count > 1:
        count -= 1

    # Consonant + 'le' endings (bottle, apple, little)
    if len(word) >= 3 and word.endswith("le") and word[-3] not in vowels:
        count += 1

    return max(count, 1)


def _get_rhyme_tail(word: str) -> str:
    """Extract rhyme tail from last vowel cluster to end of word.

    Strips trailing 's' for plural tolerance before extracting.
    Examples: "night" -> "ight", "away" -> "ay", "desire" -> "ire"
    """
    if not word:
        return ""
    word = word.lower().strip("'")
    if not word:
        return ""

    # Strip trailing 's' for plural tolerance
    if len(word) > 2 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]

    vowels = set("aeiouy")

    # Handle silent 'e' — if word ends with consonant + 'e', find the
    # vowel cluster before the 'e' but include 'e' in the returned tail
    scan_word = word
    if len(word) > 2 and word.endswith("e") and word[-2] not in vowels:
        scan_word = word[:-1]

    # Find last vowel cluster start in scan_word
    last_vowel_pos = -1
    for i in range(len(scan_word) - 1, -1, -1):
        if scan_word[i] in vowels:
            last_vowel_pos = i
            # Walk back through consecutive vowels
            while i > 0 and scan_word[i - 1] in vowels:
                i -= 1
                last_vowel_pos = i
            break

    if last_vowel_pos < 0:
        return word  # No vowels — return whole word

    # Return from vowel position to end of ORIGINAL word
    return word[last_vowel_pos:]


async def count_syllables(text: str) -> str:
    """Get syllable counts per line with section tracking and consistency analysis.

    Parses lyrics by section, counts syllables per line, and calculates
    consistency (stdev > 3 = "UNEVEN").

    Args:
        text: Lyrics text to analyze (with [Section] tags)

    Returns:
        JSON with {sections: [{section, lines: [{line_number, text,
        syllable_count, word_count}], avg_syllables_per_line, line_count}],
        summary: {total_syllables, total_lines, avg_syllables_per_line,
        min_line, max_line, consistency}}
    """
    if not text or not text.strip():
        return _safe_json({
            "sections": [],
            "summary": {
                "total_syllables": 0,
                "total_lines": 0,
                "avg_syllables_per_line": 0,
                "min_line": 0,
                "max_line": 0,
                "consistency": "N/A",
            },
        })

    err = _check_text_length(text, "count_syllables")
    if err:
        return err

    sections = []
    current_section = "Unknown"
    current_lines: list[dict[str, Any]] = []
    all_syllable_counts: list[int] = []

    for line_num, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            continue

        if _SECTION_TAG_RE.match(stripped):
            # Save previous section if it has lines
            if current_lines:
                avg = sum(line["syllable_count"] for line in current_lines) / len(current_lines)
                sections.append({
                    "section": current_section,
                    "lines": current_lines,
                    "avg_syllables_per_line": round(avg, 1),
                    "line_count": len(current_lines),
                })
            current_section = stripped[1:-1].strip()
            current_lines = []
            continue

        # Count syllables for this line
        words = _WORD_TOKEN_RE.findall(stripped)
        syllable_count = sum(_count_syllables_word(w) for w in words)
        all_syllable_counts.append(syllable_count)

        current_lines.append({
            "line_number": line_num,
            "text": stripped,
            "syllable_count": syllable_count,
            "word_count": len(words),
        })

    # Don't forget last section
    if current_lines:
        avg = sum(line["syllable_count"] for line in current_lines) / len(current_lines)
        sections.append({
            "section": current_section,
            "lines": current_lines,
            "avg_syllables_per_line": round(avg, 1),
            "line_count": len(current_lines),
        })

    # Summary
    total_syllables = sum(all_syllable_counts)
    total_lines = len(all_syllable_counts)
    avg_overall = round(total_syllables / total_lines, 1) if total_lines else 0
    min_line = min(all_syllable_counts) if all_syllable_counts else 0
    max_line = max(all_syllable_counts) if all_syllable_counts else 0

    if total_lines >= 2:
        stdev = statistics.stdev(all_syllable_counts)
        consistency = "UNEVEN" if stdev > 3 else "CONSISTENT"
    else:
        consistency = "N/A"

    return _safe_json({
        "sections": sections,
        "summary": {
            "total_syllables": total_syllables,
            "total_lines": total_lines,
            "avg_syllables_per_line": avg_overall,
            "min_line": min_line,
            "max_line": max_line,
            "consistency": consistency,
        },
    })


async def analyze_readability(text: str) -> str:
    """Analyze readability of lyrics text using Flesch Reading Ease.

    Reuses _count_syllables_word. Pure math — no NLP dependencies.

    Args:
        text: Lyrics text to analyze (with or without [Section] tags)

    Returns:
        JSON with {word_stats: {total_words, unique_words, vocabulary_richness,
        avg_word_length, avg_syllables_per_word}, line_stats: {total_lines,
        avg_words_per_line, min_words_line, max_words_line},
        readability: {flesch_reading_ease, grade_level, assessment}}
    """
    if not text or not text.strip():
        return _safe_json({
            "word_stats": {
                "total_words": 0,
                "unique_words": 0,
                "vocabulary_richness": 0,
                "avg_word_length": 0,
                "avg_syllables_per_word": 0,
            },
            "line_stats": {
                "total_lines": 0,
                "avg_words_per_line": 0,
                "min_words_line": 0,
                "max_words_line": 0,
            },
            "readability": {
                "flesch_reading_ease": 0,
                "grade_level": "N/A",
                "assessment": "No content to analyze",
            },
        })

    err = _check_text_length(text, "analyze_readability")
    if err:
        return err

    all_words = []
    words_per_line = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or _SECTION_TAG_RE.match(stripped):
            continue
        words = _WORD_TOKEN_RE.findall(stripped)
        if words:
            all_words.extend(words)
            words_per_line.append(len(words))

    if not all_words:
        return _safe_json({
            "word_stats": {
                "total_words": 0,
                "unique_words": 0,
                "vocabulary_richness": 0,
                "avg_word_length": 0,
                "avg_syllables_per_word": 0,
            },
            "line_stats": {
                "total_lines": 0,
                "avg_words_per_line": 0,
                "min_words_line": 0,
                "max_words_line": 0,
            },
            "readability": {
                "flesch_reading_ease": 0,
                "grade_level": "N/A",
                "assessment": "No content to analyze",
            },
        })

    total_words = len(all_words)
    unique_words = len(set(w.lower() for w in all_words))
    total_syllables = sum(_count_syllables_word(w) for w in all_words)
    total_lines = len(words_per_line)

    avg_word_length = round(
        sum(len(w) for w in all_words) / total_words, 1
    )
    avg_syllables_per_word = round(total_syllables / total_words, 2)
    vocabulary_richness = round(unique_words / total_words, 2)

    avg_words_per_line = round(total_words / total_lines, 1)
    min_words_line = min(words_per_line)
    max_words_line = max(words_per_line)

    # Flesch Reading Ease
    asl = total_words / total_lines  # avg sentence (line) length
    asw = total_syllables / total_words  # avg syllables per word
    flesch = round(206.835 - (1.015 * asl) - (84.6 * asw), 1)

    # Grade level assessment
    if flesch >= 90:
        grade_level = "Very Easy"
        assessment = "Very easy to read — conversational, accessible lyrics"
    elif flesch >= 80:
        grade_level = "Easy"
        assessment = "Easy to read — clear, natural language"
    elif flesch >= 70:
        grade_level = "Standard"
        assessment = "Standard readability — well-crafted lyrics"
    elif flesch >= 60:
        grade_level = "Moderate"
        assessment = "Moderately complex — dense or literary vocabulary"
    else:
        grade_level = "Complex"
        assessment = "Complex vocabulary — may challenge listeners on first hearing"

    return _safe_json({
        "word_stats": {
            "total_words": total_words,
            "unique_words": unique_words,
            "vocabulary_richness": vocabulary_richness,
            "avg_word_length": avg_word_length,
            "avg_syllables_per_word": avg_syllables_per_word,
        },
        "line_stats": {
            "total_lines": total_lines,
            "avg_words_per_line": avg_words_per_line,
            "min_words_line": min_words_line,
            "max_words_line": max_words_line,
        },
        "readability": {
            "flesch_reading_ease": flesch,
            "grade_level": grade_level,
            "assessment": assessment,
        },
    })


async def analyze_rhyme_scheme(text: str) -> str:
    """Analyze rhyme scheme of lyrics with section awareness.

    Parses by section, extracts end words, builds rhyme groups (A/B/C letters),
    and detects self-rhymes.

    Args:
        text: Lyrics text to analyze (with [Section] tags)

    Returns:
        JSON with {sections: [{section, section_type, scheme, lines: [{line_number,
        end_word, rhyme_group, rhyme_tail}], issues: []}],
        issues: [{type, section, line_numbers, word, severity}],
        summary: {total_sections, sections_with_issues, self_rhymes}}
    """
    if not text or not text.strip():
        return _safe_json({
            "sections": [],
            "issues": [],
            "summary": {
                "total_sections": 0,
                "sections_with_issues": 0,
                "self_rhymes": 0,
            },
        })

    err = _check_text_length(text, "analyze_rhyme_scheme")
    if err:
        return err

    # Parse into sections using _tokenize_lyrics_with_sections
    tokenized = _tokenize_lyrics_with_sections(text)

    # Group by section
    section_groups = {}
    section_order = []
    for entry in tokenized:
        sec = entry["section"]
        if sec not in section_groups:
            section_groups[sec] = {
                "section": sec,
                "section_type": entry["section_type"],
                "entries": [],
            }
            section_order.append(sec)
        section_groups[sec]["entries"].append(entry)

    all_issues = []
    result_sections = []

    for sec_name in section_order:
        group = section_groups[sec_name]
        entries = group["entries"]
        section_type = group["section_type"]

        # Extract end words
        end_words = []
        for entry in entries:
            if entry["words"]:
                end_words.append({
                    "line_number": entry["line_number"],
                    "end_word": entry["words"][-1],
                    "rhyme_tail": _get_rhyme_tail(entry["words"][-1]),
                })

        # Build rhyme groups
        rhyme_labels: dict[str, str] = {}  # rhyme_tail -> label letter
        next_label = 0
        lines_data = []

        for ew in end_words:
            tail = ew["rhyme_tail"]
            # Find matching group
            assigned = False
            for existing_tail, label in rhyme_labels.items():
                if len(tail) >= 2 and len(existing_tail) >= 2 and tail == existing_tail:
                    lines_data.append({
                        "line_number": ew["line_number"],
                        "end_word": ew["end_word"],
                        "rhyme_group": label,
                        "rhyme_tail": tail,
                    })
                    assigned = True
                    break

            if not assigned:
                label = chr(ord("A") + next_label) if next_label < 26 else f"Z{next_label}"
                next_label += 1
                rhyme_labels[tail] = label
                lines_data.append({
                    "line_number": ew["line_number"],
                    "end_word": ew["end_word"],
                    "rhyme_group": label,
                    "rhyme_tail": tail,
                })

        scheme = "".join(ld["rhyme_group"] for ld in lines_data)

        # Detect issues within this section
        section_issues = []

        # Self-rhymes: same word used as end word in multiple lines
        word_lines: dict[str, list[int]] = {}
        for ld in lines_data:
            w = ld["end_word"].lower()
            if w not in word_lines:
                word_lines[w] = []
            word_lines[w].append(ld["line_number"])

        for w, lnums in word_lines.items():
            if len(lnums) > 1:
                issue = {
                    "type": "self_rhyme",
                    "section": sec_name,
                    "line_numbers": lnums,
                    "word": w,
                    "severity": "warning",
                }
                section_issues.append(issue)
                all_issues.append(issue)

        result_sections.append({
            "section": sec_name,
            "section_type": section_type,
            "scheme": scheme,
            "lines": lines_data,
            "issues": section_issues,
        })

    # Summary counts
    self_rhymes = sum(1 for i in all_issues if i["type"] == "self_rhyme")
    sections_with_issues = sum(1 for s in result_sections if s["issues"])

    return _safe_json({
        "sections": result_sections,
        "issues": all_issues,
        "summary": {
            "total_sections": len(result_sections),
            "sections_with_issues": sections_with_issues,
            "self_rhymes": self_rhymes,
        },
    })


async def validate_section_structure(text: str) -> str:
    """Validate section structure of lyrics.

    Checks: valid tags present, balanced section lengths (V1 vs V2 diff > 2
    lines flagged), empty sections, duplicate consecutive tags.

    Args:
        text: Lyrics text to validate (with [Section] tags)

    Returns:
        JSON with {sections: [{tag, line_number, content_lines, section_type}],
        issues: [{type, sections/tag, line_number, severity}],
        summary: {total_sections, has_verse, has_chorus, has_bridge,
        issues_count, section_balance}}
    """
    if not text or not text.strip():
        return _safe_json({
            "sections": [],
            "issues": [{
                "type": "no_content",
                "tag": None,
                "line_number": 0,
                "severity": "error",
            }],
            "summary": {
                "total_sections": 0,
                "has_verse": False,
                "has_chorus": False,
                "has_bridge": False,
                "issues_count": 1,
                "section_balance": "N/A",
            },
        })

    sections: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    current_tag = None
    current_tag_line = 0
    content_line_count = 0
    prev_tag = None

    lines = text.split("\n")

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        if _SECTION_TAG_RE.match(stripped):
            # Save previous section or warn about untagged content
            if current_tag is None and content_line_count > 0:
                issues.append({
                    "type": "content_before_first_tag",
                    "tag": None,
                    "line_number": 1,
                    "severity": "warning",
                })
            if current_tag is not None:
                # Check for empty section
                if content_line_count == 0:
                    issues.append({
                        "type": "empty_section",
                        "tag": current_tag,
                        "line_number": current_tag_line,
                        "severity": "warning",
                    })
                tag_name = current_tag[1:-1].strip()
                section_lower = tag_name.lower()
                section_type = "verse"
                for stype in sorted(_SECTION_PRIORITY, key=len, reverse=True):
                    if stype in section_lower:
                        section_type = stype
                        break
                sections.append({
                    "tag": current_tag,
                    "line_number": current_tag_line,
                    "content_lines": content_line_count,
                    "section_type": section_type,
                })

            # Check for duplicate consecutive tags
            if stripped == prev_tag:
                issues.append({
                    "type": "duplicate_consecutive_tag",
                    "tag": stripped,
                    "line_number": line_num,
                    "severity": "error",
                })

            prev_tag = stripped
            current_tag = stripped
            current_tag_line = line_num
            content_line_count = 0

        elif stripped:
            content_line_count += 1

    # Save last section
    if current_tag is not None:
        if content_line_count == 0:
            issues.append({
                "type": "empty_section",
                "tag": current_tag,
                "line_number": current_tag_line,
                "severity": "warning",
            })
        tag_name = current_tag[1:-1].strip()
        section_lower = tag_name.lower()
        section_type = "verse"
        for stype in sorted(_SECTION_PRIORITY, key=len, reverse=True):
            if stype in section_lower:
                section_type = stype
                break
        sections.append({
            "tag": current_tag,
            "line_number": current_tag_line,
            "content_lines": content_line_count,
            "section_type": section_type,
        })

    # Check for no section tags at all
    if not sections:
        issues.append({
            "type": "no_section_tags",
            "tag": None,
            "line_number": 0,
            "severity": "warning",
        })

    # Detect section types present
    types_present = {s["section_type"] for s in sections}
    has_verse = "verse" in types_present
    has_chorus = "chorus" in types_present or "hook" in types_present
    has_bridge = "bridge" in types_present

    # Check missing common sections
    if sections and not has_verse:
        issues.append({
            "type": "missing_verse",
            "tag": None,
            "line_number": 0,
            "severity": "info",
        })
    if sections and not has_chorus:
        issues.append({
            "type": "missing_chorus",
            "tag": None,
            "line_number": 0,
            "severity": "info",
        })

    # Check section balance — compare verse lengths
    verse_sections = [s for s in sections if s["section_type"] == "verse"]
    section_balance = "BALANCED"
    if len(verse_sections) >= 2:
        lengths = [s["content_lines"] for s in verse_sections]
        max_diff = max(lengths) - min(lengths)
        if max_diff > 2:
            section_balance = "UNBALANCED"
            # Find the unbalanced pair
            issues.append({
                "type": "unbalanced_sections",
                "sections": [s["tag"] for s in verse_sections],
                "line_number": verse_sections[0]["line_number"],
                "severity": "warning",
                "detail": f"Verse line counts vary by {max_diff} lines: {lengths}",
            })

    return _safe_json({
        "sections": sections,
        "issues": issues,
        "summary": {
            "total_sections": len(sections),
            "has_verse": has_verse,
            "has_chorus": has_chorus,
            "has_bridge": has_bridge,
            "issues_count": len(issues),
            "section_balance": section_balance,
        },
    })


def register(mcp: Any) -> None:
    """Register lyrics analysis tools with the MCP server."""
    mcp.tool()(extract_distinctive_phrases)
    mcp.tool()(count_syllables)
    mcp.tool()(analyze_readability)
    mcp.tool()(analyze_rhyme_scheme)
    mcp.tool()(validate_section_structure)
