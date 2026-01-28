# Override Index

Complete reference for all override files. Each override customizes a specific aspect of Claude's behavior.

## Overview

| # | Override File | Used By | Purpose |
|---|---------------|---------|---------|
| 1 | `CLAUDE.md` | Main workflow | General workflow instructions |
| 2 | `pronunciation-guide.md` | `/pronunciation-specialist` | Phonetic spellings for Suno |
| 3 | `explicit-words.md` | `/explicit-checker` | Explicit content word list |
| 4 | `lyric-writing-guide.md` | `/lyric-writer` | Lyric style preferences |
| 5 | `suno-preferences.md` | `/suno-engineer` | Suno prompt customization |
| 6 | `album-planning-guide.md` | `/album-conceptualizer` | Album structure preferences |
| 7 | `album-art-preferences.md` | `/album-art-director` | Visual style guidelines |
| 8 | `research-preferences.md` | `/researcher` | Research standards |
| 9 | `release-preferences.md` | `/release-director` | Release workflow |
| 10 | `mastering-presets.yaml` | `/mastering-engineer` | Audio mastering presets |
| 11 | `sheet-music-preferences.md` | `/sheet-music-publisher` | Sheet music formatting |

---

## 1. CLAUDE.md

**Purpose:** Add your own workflow rules and preferences that supplement the base instructions.

**Used by:** Main workflow (loaded at session start)

**Merge behavior:** Supplements (additive) - your instructions are added to base behavior

### Default Behavior
Claude follows the workflow defined in the plugin's CLAUDE.md.

### With Override
Your custom workflow preferences are loaded in addition to base instructions.

### What You Can Customize

| Section | Examples |
|---------|----------|
| Workflow preferences | "Always ask before creating new albums" |
| Album naming conventions | "All lowercase with hyphens" |
| Track naming conventions | "Title case for display names" |
| Research preferences | "Minimum 3 sources per factual claim" |
| Generation preferences | "Generate 3 variations per track" |
| Release preferences | "Upload to SoundCloud same day" |

### Example
```markdown
## My Workflow Preferences
- Default to 8-track albums unless specified
- Use dark/moody themes by default

## Album Naming Conventions
- All lowercase with hyphens
- Keep names under 20 characters
```

---

## 2. pronunciation-guide.md

**Purpose:** Define phonetic spellings for artist names, album titles, character names, and other terms Suno might mispronounce.

**Used by:** `/bitwize-music:pronunciation-specialist`

**Merge behavior:** Merged with base guide - custom entries take precedence

### Default Behavior
Uses only the base pronunciation guide at `/reference/suno/pronunciation-guide.md`.

### With Override
Your custom pronunciations are merged with the base guide. If the same word appears in both, your pronunciation takes precedence.

### What You Can Customize

| Category | Examples |
|----------|----------|
| Artist names | `bitwize` -> `bit-wize` |
| Album titles | `shellno` -> `shell-no` |
| Character names | `Larocca` -> `Luh-rock-uh` |
| Location names | `Sinaloa` -> `Sin-ah-lo-ah` |
| Genre jargon | Custom terms for your style |

### Format
```markdown
| Standard | Phonetic | Notes |
|----------|----------|-------|
| bitwize | bit-wize | Artist name |
| Finnerty | Finn-er-tee | Character in documentary album |
```

### Notes
- The pronunciation specialist auto-adds entries when it discovers issues
- Use hyphens for syllable breaks: `Sin-ah-lo-ah`
- Use capitals for stressed syllables: `reh-CORD` (verb) vs `REH-cord` (noun)

---

## 3. explicit-words.md

**Purpose:** Add or remove words from the explicit content scanner.

**Used by:** `/bitwize-music:explicit-checker`

**Merge behavior:** Additive/subtractive - add new words, remove base words

### Default Behavior
Scans for base explicit word list: fuck, shit, bitch, cunt, cock, dick, pussy, asshole, whore, slut, goddamn (and variations).

### With Override
Your additions are added to the list. Your removals are removed from the list.

### What You Can Customize

| Section | Purpose |
|---------|---------|
| Additional Explicit Words | Words to add to the scanner |
| Not Explicit (Override Base) | Words to remove from the scanner |

### Example
```markdown
## Additional Explicit Words
- regional-slang-term
- genre-specific-profanity

## Not Explicit (Override Base)
- hell (context: historical narrative)
- damn (context: period-accurate dialogue)
```

---

## 4. lyric-writing-guide.md

**Purpose:** Define your personal lyric writing style, vocabulary preferences, and thematic focus.

**Used by:** `/bitwize-music:lyric-writer`

**Merge behavior:** Adds context - used when writing lyrics

### Default Behavior
Claude uses general lyric writing best practices.

### With Override
Your style preferences guide lyric creation and revision.

### What You Can Customize

| Section | Examples |
|---------|----------|
| Style preferences | "Prefer first-person narrative", "Use vivid sensory details" |
| Point of view | Default POV for different contexts |
| Vocabulary (prefer) | "Simple, direct language" |
| Vocabulary (avoid) | "utilize, commence, endeavor (too formal)" |
| Themes (focus on) | "Technology, alienation, urban decay" |
| Themes (avoid) | "Love songs, party anthems" |
| Structure preferences | "Verses 4-6 lines max", "Always include bridge" |
| Custom rules | "Never use the word 'baby' in lyrics" |

### Example
```markdown
## Style Preferences
- Prefer first-person narrative
- Use vivid sensory details
- Keep verses 4-6 lines max

## Vocabulary
### Avoid
- utilize (use "use" instead)
- Cliches: heart of gold, burning bright

## Custom Rules
- Always end with a callback to the opening line
```

---

## 5. suno-preferences.md

**Purpose:** Customize Suno prompt generation with your genre mappings, vocal preferences, and avoidances.

**Used by:** `/bitwize-music:suno-engineer`

**Merge behavior:** Adds context - used when generating style prompts

### Default Behavior
Claude uses general Suno best practices from `/reference/suno/`.

### With Override
Your mappings and preferences are applied to style prompt generation.

### What You Can Customize

| Section | Examples |
|---------|----------|
| Genre mappings | Map your genre names to Suno tags |
| Default settings | Always include in style prompts |
| Vocal preferences | Default vocal descriptions by context |
| Avoid (genres) | Genres to never use |
| Avoid (descriptors) | Words to filter out |
| Instrument preferences | Preferred instruments by genre |

### Example
```markdown
## Genre Mappings
| My Genre | Suno Genres |
|----------|-------------|
| dark-electronic | dark techno, industrial, ebm, aggressive synths |
| chill-beats | lo-fi hip hop, chillhop, jazzhop, mellow |

## Default Settings
- Always include in style: atmospheric, polished production

## Avoid
- Genres: country, bluegrass, folk
- Descriptors: happy, upbeat, cheerful
```

---

## 6. album-planning-guide.md

**Purpose:** Define your album structure preferences, track counts, and thematic focus.

**Used by:** `/bitwize-music:album-conceptualizer`

**Merge behavior:** Adds context - used when planning albums

### Default Behavior
Claude uses general album planning best practices.

### With Override
Your preferences guide the album conceptualization process.

### What You Can Customize

| Section | Examples |
|---------|----------|
| Track count preferences | Full album: 10-12, EP: 4-5 |
| Structure (always include) | "Intro track", "Strong closer" |
| Structure (avoid) | "Skits or spoken interludes" |
| Themes to explore | "Technology and society", "Urban isolation" |
| Themes to avoid | "Political commentary", "Relationship drama" |
| Sonic direction | Production preferences |

### Example
```markdown
## Track Count Preferences
| Format | Track Count |
|--------|-------------|
| Full album | 10-12 tracks |
| EP | 4-5 tracks |

## Structure Preferences
### Always Include
- Intro track (instrumental or ambient)
- Strong closer that ties back to opener

### Avoid
- Skits or spoken interludes
```

---

## 7. album-art-preferences.md

**Purpose:** Define your visual style guidelines for album artwork and AI art generation.

**Used by:** `/bitwize-music:album-art-director`

**Merge behavior:** Adds context - used when developing visual concepts

### Default Behavior
Claude provides general album art concepts based on the album theme.

### With Override
Your visual preferences guide artwork concept development.

### What You Can Customize

| Section | Examples |
|---------|----------|
| Visual style (prefer) | "Minimalist, geometric, high contrast" |
| Visual style (avoid) | "Photorealistic, busy compositions" |
| Color palette (primary) | "Deep blues, purples, blacks" |
| Color palette (accent) | "Neon cyan, electric pink" |
| Color palette (avoid) | "Warm colors, pastels" |
| Composition (prefer) | "Centered subject, negative space" |
| Composition (avoid) | "Cluttered backgrounds" |
| AI art notes | What to include/avoid in prompts |

### Example
```markdown
## Visual Style
### Prefer
- Minimalist, geometric, high contrast
- Abstract representations
- Glitch art, digital aesthetics

### Avoid
- Photorealistic images
- Text overlays (except artist name)

## Color Palette
### Primary Colors
- Deep blues (#0a1628)
- Rich purples (#2d1b4e)
```

---

## 8. research-preferences.md

**Purpose:** Define your research standards, source priorities, and verification requirements.

**Used by:** `/bitwize-music:researcher` and specialized researcher skills

**Merge behavior:** Adds context - applied to source selection and verification

### Default Behavior
Claude uses the standard source hierarchy: Court docs > Government > Journalism > News > Wikipedia.

### With Override
Your source priorities and verification standards are applied.

### What You Can Customize

| Section | Examples |
|---------|----------|
| Source priority | Ranked list of preferred source types |
| Verification standards | Minimum sources, citation format |
| Research depth | Timeline precision, financial detail level |
| Trusted sources | Always trust / approach with caution / never use |

### Example
```markdown
## Source Priority
1. Court documents, SEC filings, government reports
2. Academic research, peer-reviewed journals
3. Investigative journalism (NYT, WSJ, WaPo)

## Verification Standards
- Minimum sources for key facts: 3
- Citation format: Chicago style
- Cross-reference requirement: Yes for all claims

## Trusted Sources
### Never Use
- Anonymous forum posts without corroboration
- Tabloid sources
```

---

## 9. release-preferences.md

**Purpose:** Define your release workflow, QA requirements, and platform priorities.

**Used by:** `/bitwize-music:release-director`

**Merge behavior:** Adds context - applied to QA checklist and platform workflow

### Default Behavior
Claude uses the standard release checklist and platform workflow.

### With Override
Your QA requirements and platform priorities are applied.

### What You Can Customize

| Section | Examples |
|---------|----------|
| QA requirements (additional) | "Listen-through on 3 devices" |
| QA requirements (skip) | "Source verification for non-documentary albums" |
| Platform priorities | Ordered list with timing |
| Metadata standards | Artist name format, required tags |
| Timing | Days between completion and release |

### Example
```markdown
## QA Requirements
### Additional Checks
- Listen-through on 3 devices
- A/B comparison with reference track

## Platform Priorities
| Priority | Platform | Notes |
|----------|----------|-------|
| 1 | SoundCloud | Always upload first, same day |
| 2 | Bandcamp | Within 24 hours |
| 3 | Spotify/Apple | Via DistroKid, 1 week after |

## Metadata Standards
- Artist name format: lowercase (bitwize not Bitwize)
- Tags to always include: ai-music, suno, electronic
```

---

## 10. mastering-presets.yaml

**Purpose:** Override default genre presets for audio mastering with custom EQ and dynamics settings.

**Used by:** `/bitwize-music:mastering-engineer`

**Merge behavior:** Overrides - replaces default presets for specified genres

**Format:** YAML (not Markdown)

### Default Behavior
Uses built-in genre presets with standard streaming targets (-14 LUFS, -1.0 dBTP).

### With Override
Your custom presets replace defaults for specified genres.

### What You Can Customize

| Setting | Unit | Description |
|---------|------|-------------|
| `cut_highmid` | dB | High-mid EQ cut |
| `boost_sub` | dB | Sub bass boost |
| `target_lufs` | LUFS | Loudness target |
| `true_peak` | dBTP | True peak ceiling |

### Example
```yaml
genres:
  dark-electronic:
    cut_highmid: -3      # More aggressive high-mid cut
    boost_sub: 2         # Extra sub bass
    target_lufs: -12     # Louder master

  ambient:
    cut_highmid: -1      # Gentle cut
    boost_sub: 0         # Natural bass
    target_lufs: -16     # Quieter, more dynamic range

defaults:
  target_lufs: -14
  true_peak: -1.0
```

---

## 11. sheet-music-preferences.md

**Purpose:** Define page layout, notation preferences, and songbook formatting for sheet music generation.

**Used by:** `/bitwize-music:sheet-music-publisher`

**Merge behavior:** Adds context - applied to PDF generation and songbook creation

### Default Behavior
Uses standard settings: letter page size, no section headers.

### With Override
Your formatting preferences are applied to sheet music generation.

### What You Can Customize

| Section | Examples |
|---------|----------|
| Page layout | Page size, staff size, margins |
| Title page | Track numbers, composer credit, copyright |
| Notation | Key signature preference, chord symbols |
| Songbook settings | Table of contents, cover style, page numbers |

### Example
```markdown
## Page Layout
- Page size: 9x12 (standard songbook)
- Staff size: 7mm (standard) or 8mm (large print)
- Margins: 0.75 inch all sides

## Title Page
- Include track numbers: No
- Composer credit format: "Music by [artist]"
- Copyright notice: "CC BY-NC 4.0"

## Songbook Settings
- Table of contents: Yes
- Cover page style: Minimalist (title + artist + album art)
- Page numbers: Bottom center
```

---

## See Also

- [how-to-customize.md](how-to-customize.md) - Getting started guide
- [/config/overrides.example/](../../config/overrides.example/) - Example templates to copy
- [/config/README.md](../../config/README.md) - Full configuration reference
