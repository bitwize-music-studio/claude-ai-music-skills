# Terminology Glossary

Comprehensive reference for terms used in the bitwize-music plugin. Alphabetized within categories.

---

## Core Concepts

| Term | Definition | Example |
|------|------------|---------|
| **Audio Root** | Directory where mastered audio files are stored. Uses flat structure without genre folders. | `~/bitwize-music/audio/bitwize/sample-album/` |
| **Config File** | The YAML configuration file that stores all paths and artist settings. Always located at `~/.bitwize-music/config.yaml`. | `paths.content_root: ~/bitwize-music` |
| **Content Root** | Directory where albums, artists, research files, and markdown content live. Has genre-based folder structure. | `~/bitwize-music/artists/bitwize/albums/electronic/sample-album/` |
| **Documents Root** | Directory for PDFs and primary source documents too large for git. Mirrors content root structure. | `~/bitwize-music/documents/bitwize/sample-album/` |
| **Override** | User-created file that customizes plugin behavior without modifying plugin files. Survives plugin updates. | `{overrides}/CLAUDE.md`, `{overrides}/pronunciation-guide.md` |
| **Plugin Root** | Directory where the plugin code lives. Contains skills, templates, reference docs, and tools. | `~/.claude/plugins/bitwize-music` |
| **Skill** | A slash command that invokes specialized functionality. Each skill has its own SKILL.md documentation. | `/bitwize-music:lyric-writer`, `/bitwize-music:researcher` |
| **Tools Root** | Directory for shared tools, virtual environments, and cache. Always at `~/.bitwize-music`. | `~/.bitwize-music/venv/` |

---

## Album Workflow Terms

| Term | Definition | Example |
|------|------------|---------|
| **7 Planning Phases** | Structured planning process required before writing lyrics: Foundation, Concept Deep Dive, Sonic Direction, Structure Planning, Album Art, Practical Details, Confirmation. | "Phase 3: What are the sonic inspirations?" |
| **Album Completion Checklist** | Final checklist before release covering all tracks Final, album art, mastering, metadata, and platform uploads. | See CLAUDE.md "Album Completion Checklist" |
| **Album Status** | Lifecycle state of an album: Concept, Research Complete, Sources Verified, In Progress, Complete, Released. | `Status: In Progress` in album README |
| **Generation Log** | Table in each track file logging Suno generation attempts with date, model, result URL, notes, and keeper rating. | `| 2 | 2025-12-03 | V5 | [Listen](url) | Boosted vocals | ✓ |` |
| **Human Verification** | Required manual review confirming captured sources are accurate before using them in lyrics. For true-story albums only. | Status changes from `Pending` to `Verified (2025-01-15)` |
| **Keeper** | A generated track that meets quality standards and is marked for use. Indicated with checkmark in Generation Log. | `✓` in Rating column |
| **Source Verification** | The process of confirming research sources are accurate and properly cited. Required before production. | `Status: Sources Verified` |
| **Streaming Lyrics** | Clean version of lyrics for distribution platforms. No section tags, proper capitalization, no phonetic spellings. | Standard lyrics without `[Verse]` tags |
| **Suno Lyrics** | Version of lyrics formatted for Suno with section tags, phonetic spellings, and pronunciation helpers. | `[Verse 1]\nWalking through the Lin-ucks lab...` |
| **Track Status** | Lifecycle state of a single track: Not Started, Sources Pending, Sources Verified, In Progress, Generated, Final. | `Status: Generated` |
| **True-Story Album** | Album based on real events requiring research, source verification, and factual accuracy. Requires human verification. | Album about a historical event or real person |

---

## Suno Terms

| Term | Definition | Example |
|------|------------|---------|
| **Cover** | Suno feature to reimagine an existing track in a different style or genre. | Cover a folk song as electronic |
| **Extend** | Suno feature to continue a generated clip by adding ~1 minute of new content. Creates 2 versions per extension. | Click EXTEND to add verse 2 |
| **Extend From Timestamp** | Ability to continue generation from an earlier point in the clip rather than the end. | Go back to 1:30 and regenerate |
| **Lyrics Box** | Text field in Suno where lyrics with section tags are entered. Accepts structure tags and vocal directions. | The input field for `[Verse 1]\nLyrics here...` |
| **Negative Prompting** | Using exclusions in style prompts to remove unwanted elements. V5 handles reliably. | `"no drums, no electric guitar"` |
| **Persona** | Description of the vocalist to maintain consistency across an album. Stored in album README. | `Male baritone, gravelly, introspective, folk storyteller` |
| **Replace Section** | Suno Pro/Premier feature to edit lyrics or insert instrumental sections within a 10-30 second segment. | Fix one verse without regenerating entire track |
| **Reroll** | Generating new variations of a track using the same prompts. Each reroll produces different results. | Generate 3 variations, pick the best |
| **Section Tags** | Markers in lyrics that tell Suno how to structure the song. | `[Verse]`, `[Chorus]`, `[Bridge]`, `[End]` |
| **Stem Extraction** | Suno V5 feature to separate a track into 12 individual stems (vocals, drums, bass, etc.). | Extract vocals for a cappella version |
| **Style Box** | Text field in Suno for describing musical style. Contains genre, vocal style, instrumentation, mood. | `"dark industrial electronic, aggressive male vocals"` |
| **Style Prompt** | The text written for the Style Box. Same as Style Box content. | `"nerdcore hip-hop, lo-fi, nostalgic, 85 BPM"` |
| **Suno Link** | URL to a generated track on Suno. Stored in track files after generation. | `https://suno.com/song/abc123` |
| **Suno Studio** | Generative audio workstation (Premier plan) with multitrack editing, stem controls, MIDI export, and Sample to Song. | Timeline-based editing with AI generation |
| **Top-Anchor Approach** | Starting Suno prompts with vocal description before lyrics for better voice consistency. | Put `"Female pop vocalist, breathy"` first |
| **V5** | Current Suno generation model with improved vocals, 12-stem extraction, and up to 8-minute tracks. | `Model: V5` in Generation Log |
| **Voice Tags** | Descriptors in style prompts that control vocal delivery. | `breathy, raspy, powerful, intimate, gravelly` |

---

## Audio Terms

| Term | Definition | Example |
|------|------------|---------|
| **Clipping** | Distortion caused by audio exceeding maximum level (0 dBFS). Prevented by true peak limiting. | Audio sounds harsh/crunchy at peaks |
| **Crest Factor** | Difference between peak and RMS levels, indicating dynamic range. High crest factor = more dynamics. | Crest factor > 12dB may need compression |
| **dBFS** | Decibels Full Scale. Measures audio level where 0 is the maximum digital value. | Peak at -3 dBFS |
| **dBTP** | Decibels True Peak. Maximum sample value accounting for inter-sample peaks. Target: -1.0 dBTP for streaming. | `--ceiling -1.0` |
| **Dry Run** | Preview mode that shows what processing would be applied without writing files. | `--dry-run` flag |
| **Dynamic Range** | Difference between quietest and loudest parts of audio. Classical has high DR; compressed pop has low DR. | LUFS Range < 2 dB across album |
| **Genre Preset** | Pre-configured EQ and dynamics settings for specific genres in mastering tools. 60+ available. | `--genre country`, `--genre hip-hop` |
| **High-Mid Cut** | EQ reduction in 2-6kHz range to reduce harshness/tinniness. Common mastering correction. | `--cut-highmid -2` for 2dB cut at 3.5kHz |
| **LUFS** | Loudness Units Full Scale. Measures perceived loudness. Streaming platforms normalize to -14 LUFS. | Target: -14 LUFS for Spotify |
| **Mastering** | Final audio processing for streaming platforms. Includes loudness normalization, EQ, and limiting. | Run `master_tracks.py` on album folder |
| **Normalization** | Adjusting audio levels to meet a target loudness. LUFS normalization ensures consistent playback. | Normalize to -14 LUFS |
| **Reference Mastering** | Matching a track's tonal balance and loudness to a professionally mastered reference track. | Match to a commercial release in same genre |
| **Tinniness** | Harsh, thin sound quality caused by excessive high-mid frequencies (2-6kHz). Common in AI-generated audio. | High-mid ratio > 0.6 indicates tinniness |
| **True Peak** | Maximum absolute sample value, including inter-sample peaks. Different from sample peak. | True peak at -1.0 dBTP prevents streaming clipping |

---

## Research Terms

| Term | Definition | Example |
|------|------------|---------|
| **Citation** | Reference to a source with clickable URL. Required for all claims in true-story albums. | `[PBS Documentary](https://pbs.org/...)` |
| **Document Hunter** | Skill for automated browser-based document search from free public archives using Playwright. | `/bitwize-music:document-hunter "SEC filing Tesla 2020"` |
| **Primary Source** | Direct evidence: court documents, official statements, subject's own words. Highest reliability. | Indictment, tweet from subject, press release |
| **RESEARCH.md** | File in album directory containing detailed research notes and findings for true-story albums. | `{album}/RESEARCH.md` |
| **Secondary Source** | Reporting about primary sources: journalism, analysis, Wikipedia summaries. Lower reliability. | News article, book about the event |
| **Source Hierarchy** | Priority order for source trustworthiness: Court documents > Government > Journalism > News > Wikipedia. | Court docs carry more weight than news |
| **SOURCES.md** | File in album directory listing all sources with URLs and verification status for true-story albums. | `{album}/SOURCES.md` |
| **Specialized Researcher** | Domain-specific research skills for deep investigation: legal, gov, tech, journalism, security, financial, historical, biographical, primary-source, verifier. | `/bitwize-music:researchers-legal` |
| **Verification Status** | Whether a source has been confirmed by human review: Pending or Verified (with date). | `Status: Verified (2025-01-15)` |

---

## Lyric Writing Terms

| Term | Definition | Example |
|------|------------|---------|
| **Homograph** | Word with multiple pronunciations that Suno may mispronounce. Requires clarification or phonetic spelling. | "live" (LYVE vs LIV), "lead", "wind", "bass" |
| **Lazy Rhyme** | Predictable, overused, or weak rhyme pattern. Includes self-rhymes and same-word repeats. | Rhyming "time" with "time" |
| **Phonetic Spelling** | Writing words as they should be pronounced to prevent Suno mispronunciation. | "Lin-ucks" for Linux, "Rah-mohs" for Ramos |
| **POV** | Point of view. Should be consistent throughout a track (first person, third person, etc.). | Don't switch from "I" to "you" mid-verse |
| **Prosody** | Alignment of stressed syllables with strong musical beats. Critical for natural-sounding vocals. | Stressed syllables on beats 1 and 3 |
| **Self-Rhyme** | Rhyming a word with itself or using the same end word twice consecutively. A common pitfall. | "mind/mind", "time/time" |
| **Twin Verses** | When Verse 2 merely rewords Verse 1 without developing the story/theme. A quality issue. | V2 should advance the narrative, not repeat V1 |

---

## Distribution Terms

| Term | Definition | Example |
|------|------------|---------|
| **Distributor** | Service that uploads music to streaming platforms. | DistroKid, TuneCore, CD Baby |
| **Explicit Flag** | Marker indicating lyrics contain explicit content (profanity, adult themes). | Set when lyrics contain "fuck", "shit", etc. |
| **Metadata** | Information about a track: title, artist, album, genre, release date, ISRC. Required for distribution. | Title, BPM, key, mood tags |
| **Streaming Platforms** | Services where listeners access music: Spotify, Apple Music, YouTube Music, Tidal, etc. | Target -14 LUFS for most platforms |

---

## Commonly Confused Terms

| Terms | Clarification |
|-------|---------------|
| **Album Ideas vs Album Status** | Album Ideas (`IDEAS.md`) are brainstorming before creation. Album Status (README field) tracks progress of created albums. |
| **Content Root vs Audio Root** | Content Root has markdown files with genre folders. Audio Root has WAV files with flat structure (no genre folders). |
| **Master (file) vs Master (process)** | Master (file) = the final processed audio file. Master (process) = the act of processing audio for release. |
| **Plugin Root vs Content Root** | Plugin Root contains code/templates (don't edit). Content Root contains your albums/lyrics (edit freely). |
| **Project vs Album** | "Project" is not used in this plugin. Use "Album" for a collection of tracks being released together. |
| **Song vs Track** | Interchangeable in this plugin. Both refer to a single piece of music. |
| **Style Prompt vs Style Box** | Same thing. "Style prompt" is what you write; "Style Box" is where it goes in Suno. |
| **Suno Link vs Suno URL** | Interchangeable. Both refer to the URL of a generated track. Prefer "Suno Link" in track files. |
| **Workspace vs Content Root** | "Workspace" is informal. Use "Content Root" for the specific directory defined in config. |

---

## Path Variables

Variables used in documentation that resolve from config:

| Variable | Source | Example |
|----------|--------|---------|
| `{audio_root}` | `paths.audio_root` | `~/bitwize-music/audio` |
| `{content_root}` | `paths.content_root` | `~/bitwize-music` |
| `{documents_root}` | `paths.documents_root` | `~/bitwize-music/documents` |
| `{overrides}` | `paths.overrides` | `~/bitwize-music/overrides` |
| `{plugin_root}` | Location of plugin repo | `~/.claude/plugins/bitwize-music` |
| `{tools_root}` | Always `~/.bitwize-music` | `~/.bitwize-music` |
| `[artist]` | `artist.name` | `bitwize` |
| `[genre]` | Album's genre category | `electronic`, `rock`, `hip-hop` |
| `[album]` | Album directory name | `sample-album`, `my-album` |

---

## Abbreviations

| Abbrev | Full Form | Definition |
|--------|-----------|------------|
| **BPM** | Beats Per Minute | Tempo measurement |
| **DAW** | Digital Audio Workstation | Software for audio production (Logic, Ableton, etc.) |
| **dB** | Decibel | Unit of sound level measurement |
| **DR** | Dynamic Range | Difference between quiet and loud parts |
| **EQ** | Equalization | Adjusting frequency balance |
| **LUFS** | Loudness Units Full Scale | Perceived loudness measurement |
| **QA** | Quality Assurance | Review process before release |
| **V5** | Version 5 | Current Suno model |
| **WAV** | Waveform Audio File | Uncompressed audio format |

---

## See Also

- [CLAUDE.md](/CLAUDE.md) - Main workflow instructions
- [skills/help/SKILL_GLOSSARY.md](/skills/help/SKILL_GLOSSARY.md) - Quick glossary in help skill
- [reference/suno/v5-best-practices.md](/reference/suno/v5-best-practices.md) - Suno prompting guide
- [reference/mastering/mastering-workflow.md](/reference/mastering/mastering-workflow.md) - Audio mastering details
