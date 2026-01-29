# Distribution Reference

This document covers formatting and guidelines for distributing music to streaming platforms and digital distributors.

> **Related skills**: `/bitwize-music:explicit-checker` (scan for explicit content), `/bitwize-music:release-director` (release coordination)
> **Related docs**: [release/distributor-guide.md](release/distributor-guide.md), [release/platform-comparison.md](release/platform-comparison.md)

## Streaming Lyrics Format

Each track file has a "Streaming Lyrics" section for distributor submission (Spotify, Apple Music, etc.).

### Format Rules

- Just lyrics (no section labels, no vocalist names, no extra text)
- Write out repeats fully
- Capitalize first letter of each line
- No end punctuation
- Blank lines only between sections
- Don't censor explicit words

Fill in the Streaming Lyrics section in each track file before distributor upload.

---

## Explicit Content Guidelines

Use these guidelines to determine whether an album or track requires the explicit content flag.

### Explicit Words (require Explicit = Yes)

These words and variations require the explicit flag:

| Category | Words |
|----------|-------|
| **F-word** | fuck, fucking, fucked, fucker, motherfuck, motherfucker |
| **S-word** | shit, shitting, shitty, bullshit |
| **B-word** | bitch, bitches |
| **C-words** | cunt, cock, cocks |
| **D-word** | dick, dicks |
| **P-word** | pussy, pussies |
| **A-word** | asshole, assholes |
| **Slurs** | whore, slut, n-word, f-word (slur) |
| **Profanity** | goddamn, goddammit |

### Clean Words (no explicit flag needed)

These are fine without explicit flag: damn, hell, crap, ass, bastard, piss.

**Note**: "damn" alone is clean, but "goddamn" is explicit.

### How to Check

When asked to check for explicit content, or before finalizing an album:

1. Use Grep to scan lyrics for explicit words
2. Report any matches with track name and word count
3. Flag mismatches (explicit content but flag says No, or vice versa)

**Example scan:**
```
Grep pattern: \b(fuck|shit|bitch|cunt|cock|dick|pussy|asshole|whore|slut)\b
Path: {content_root}/artists/[artist]/albums/[genre]/[album]/tracks/
```
