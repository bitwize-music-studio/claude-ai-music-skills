# Skill Index & Decision Tree

Quick-reference guide for finding the right skill for any task.

---

## Decision Tree: "I need to..."

### Getting Started
| I need to... | Use this skill |
|--------------|----------------|
| ...install dependencies and verify setup | `/setup` |
| ...set up the plugin for the first time | `/configure` |
| ...learn how to use this plugin | `/tutorial` |
| ...see what skills are available | `/help` |
| ...learn about the plugin creator | `/about` |

### Album Lifecycle
| I need to... | Use this skill |
|--------------|----------------|
| ...start a new album | `/new-album <name> <genre>` |
| ...plan album concept and tracklist | `/album-conceptualizer` |
| ...continue working on an existing album | `/resume <album-name>` |
| ...see album progress at a glance | `/album-dashboard <album-name>` |
| ...know what to do next | `/resume [album-name]` (includes next-step advice) |
| ...check if album structure is correct | `/validate-album <album-name>` |
| ...release my finished album | `/release-director` |

### Writing & Quality
| I need to... | Use this skill |
|--------------|----------------|
| ...write lyrics for a track | `/lyric-writer` |
| ...check lyrics for pronunciation risks | `/pronunciation-specialist` |
| ...run full QC before Suno generation | `/lyric-reviewer` |
| ...run final pre-generation checkpoint | `/pre-generation-check` |
| ...check if explicit flag is needed | `/explicit-checker` |

### Suno Generation
| I need to... | Use this skill |
|--------------|----------------|
| ...create Suno prompts and settings | `/suno-engineer` |
| ...copy lyrics/prompts to clipboard | `/clipboard` |

### Research (True-Story Albums)
| I need to... | Use this skill |
|--------------|----------------|
| ...research a topic for lyrics | `/researcher` |
| ...find court documents automatically | `/document-hunter` |
| ...find DOJ/FBI/SEC press releases | `/researchers-gov` |
| ...find court filings and legal docs | `/researchers-legal` |
| ...find investigative journalism | `/researchers-journalism` |
| ...find SEC filings and financial data | `/researchers-financial` |
| ...find historical archives | `/researchers-historical` |
| ...find personal backgrounds | `/researchers-biographical` |
| ...find subject's own words (tweets, blogs) | `/researchers-primary-source` |
| ...find tech/security research | `/researchers-tech` or `/researchers-security` |
| ...verify research quality | `/researchers-verifier` |
| ...verify sources before writing | `/verify-sources <album-name>` |

### Production & Release
| I need to... | Use this skill |
|--------------|----------------|
| ...master audio for streaming platforms | `/mastering-engineer` |
| ...create promo videos for social media | `/promo-director` |
| ...upload promo videos to cloud storage | `/cloud-uploader` |
| ...create sheet music from audio | `/sheet-music-publisher` |
| ...design album artwork concept | `/album-art-director` |

### File Management
| I need to... | Use this skill |
|--------------|----------------|
| ...import audio files to album | `/import-audio` |
| ...import track markdown files | `/import-track` |
| ...place album art in correct locations | `/import-art` |

### Ideas & Planning
| I need to... | Use this skill |
|--------------|----------------|
| ...track album ideas for later | `/album-ideas` |

### Session & Workflow
| I need to... | Use this skill |
|--------------|----------------|
| ...start a fresh session | `/session-start` |
| ...get recommended next action | `/resume [album-name]` |
| ...see album progress dashboard | `/album-dashboard <album-name>` |

### Maintenance
| I need to... | Use this skill |
|--------------|----------------|
| ...run plugin tests | `/test` |
| ...update skill model references | `/skill-model-updater` |

---

## Alphabetical Skill Reference

| Skill | Description | Primary Use Case |
|-------|-------------|------------------|
| [`about`](/skills/about/SKILL.md) | About bitwize and this plugin | Learning about the plugin creator |
| [`album-art-director`](/skills/album-art-director/SKILL.md) | Visual concepts for album artwork and AI art prompts | Creating album cover concepts for DALL-E/ChatGPT |
| [`album-conceptualizer`](/skills/album-conceptualizer/SKILL.md) | Album concepts, tracklist architecture, thematic planning | Planning a new album's structure and narrative |
| [`album-dashboard`](/skills/album-dashboard/SKILL.md) | Visual album progress dashboard with completion percentages | Quick overview of album progress by phase |
| [`album-ideas`](/skills/album-ideas/SKILL.md) | Track and manage album ideas | Brainstorming and planning future albums |
| [`clipboard`](/skills/clipboard/SKILL.md) | Copy track content to system clipboard | Quickly copying lyrics/prompts for Suno |
| [`cloud-uploader`](/skills/cloud-uploader/SKILL.md) | Upload promo videos to Cloudflare R2 or AWS S3 | Hosting promo videos for social sharing |
| [`configure`](/skills/configure/SKILL.md) | Set up or edit plugin configuration | First-time setup of ~/.bitwize-music/config.yaml |
| [`document-hunter`](/skills/document-hunter/SKILL.md) | Automated browser-based document search from free archives | Finding court docs for true-story albums |
| [`explicit-checker`](/skills/explicit-checker/SKILL.md) | Scan lyrics for explicit content, verify flags | Ensuring explicit flags match actual content |
| [`help`](/skills/help/SKILL.md) | Show available skills and common workflows | Quick reference for what skills exist |
| [`import-art`](/skills/import-art/SKILL.md) | Place album art in audio and content locations | Copying artwork to correct paths after creation |
| [`import-audio`](/skills/import-audio/SKILL.md) | Move audio files to correct album location | Importing WAV files from Suno downloads |
| [`import-track`](/skills/import-track/SKILL.md) | Move track .md files to correct album location | Importing track files from external sources |
| [`lyric-reviewer`](/skills/lyric-reviewer/SKILL.md) | QC gate before Suno generation (14-point checklist) | Final quality check before generating |
| [`lyric-writer`](/skills/lyric-writer/SKILL.md) | Write or review lyrics with prosody and rhyme craft | Writing new lyrics or fixing existing ones |
| [`mastering-engineer`](/skills/mastering-engineer/SKILL.md) | Audio mastering guidance, loudness optimization | Mastering tracks to -14 LUFS for streaming |
| [`new-album`](/skills/new-album/SKILL.md) | Create album directory structure with templates | Starting a brand new album project |
| [`next-step`](/skills/next-step/SKILL.md) | Analyze state and recommend optimal next action (also available via `/resume`) | Workflow guidance when unsure what to do |
| [`promo-director`](/skills/promo-director/SKILL.md) | Generate promo videos for social media | Creating 15s vertical videos for Instagram/Twitter |
| [`pre-generation-check`](/skills/pre-generation-check/SKILL.md) | Final pre-generation checkpoint (6 gates) | Validating all requirements before Suno generation |
| [`pronunciation-specialist`](/skills/pronunciation-specialist/SKILL.md) | Scan lyrics for pronunciation risks | Catching homographs and tricky words before Suno |
| [`release-director`](/skills/release-director/SKILL.md) | Album release coordination, QA, distribution | Releasing finished album to platforms |
| [`researcher`](/skills/researcher/SKILL.md) | Investigative-grade research and source verification | Coordinating research for true-story albums |
| [`researchers-biographical`](/skills/researchers-biographical/SKILL.md) | Personal backgrounds, interviews, motivations | Finding humanizing details about subjects |
| [`researchers-financial`](/skills/researchers-financial/SKILL.md) | SEC filings, earnings calls, market data | Finding financial records and fraud documentation |
| [`researchers-gov`](/skills/researchers-gov/SKILL.md) | DOJ/FBI/SEC press releases, agency statements | Finding official government announcements |
| [`researchers-historical`](/skills/researchers-historical/SKILL.md) | Archives, contemporary accounts, timelines | Researching historical events and eras |
| [`researchers-journalism`](/skills/researchers-journalism/SKILL.md) | Investigative articles, interviews, coverage | Finding news and investigative reporting |
| [`researchers-legal`](/skills/researchers-legal/SKILL.md) | Court documents, indictments, sentencing | Finding legal filings and court records |
| [`researchers-primary-source`](/skills/researchers-primary-source/SKILL.md) | Subject's own words: tweets, blogs, forums | Finding first-person accounts and statements |
| [`researchers-security`](/skills/researchers-security/SKILL.md) | Malware analysis, CVEs, attribution reports | Researching cybersecurity incidents |
| [`researchers-tech`](/skills/researchers-tech/SKILL.md) | Project histories, changelogs, developer interviews | Researching technology and open source history |
| [`researchers-verifier`](/skills/researchers-verifier/SKILL.md) | Quality control, citation validation, fact-checking | Verifying research before human review |
| [`resume`](/skills/resume/SKILL.md) | Find album and resume work where you left off | Continuing work on an existing album |
| [`session-start`](/skills/session-start/SKILL.md) | Session startup procedure — verify setup, load state, report status | Beginning a fresh working session |
| [`sheet-music-publisher`](/skills/sheet-music-publisher/SKILL.md) | Convert audio to sheet music, create songbooks | Creating printable sheet music from tracks |
| [`skill-model-updater`](/skills/skill-model-updater/SKILL.md) | Update model references when new Claude models release | Keeping skills on current Claude models |
| [`suno-engineer`](/skills/suno-engineer/SKILL.md) | Technical Suno V5 prompting, genre selection | Crafting optimal Suno style prompts |
| [`test`](/skills/test/SKILL.md) | Run automated tests to validate plugin integrity | Verifying plugin works correctly |
| [`tutorial`](/skills/tutorial/SKILL.md) | Interactive guided album creation | Learning the workflow step-by-step |
| [`validate-album`](/skills/validate-album/SKILL.md) | Validate album structure, file locations | Catching path issues before they cause problems |
| [`verify-sources`](/skills/verify-sources/SKILL.md) | Human source verification gate with timestamps | Verifying sources before generation |

---

## Skill Prerequisites

What to have ready before using each skill:

| Skill | Prerequisites |
|-------|---------------|
| `/album-conceptualizer` | Album name and genre decided |
| `/lyric-writer` | Track concept defined, sources captured (if documentary) |
| `/pronunciation-specialist` | Lyrics written |
| `/lyric-reviewer` | Lyrics complete, pronunciation checked |
| `/pre-generation-check` | Lyrics written, pronunciation resolved, style prompt created |
| `/suno-engineer` | Lyrics written (auto-invoked by lyric-writer) |
| `/mastering-engineer` | WAV files downloaded from Suno |
| `/promo-director` | Mastered audio + album artwork |
| `/cloud-uploader` | Promo videos generated |
| `/release-director` | Mastering complete, all QA passed |
| `/import-audio` | Audio files in known location (e.g., ~/Downloads) |
| `/import-art` | Album art generated (from DALL-E or similar) |
| `/researcher` | Album concept with research needs identified |
| `/document-hunter` | Playwright installed (`pip install playwright && playwright install chromium`) |

---

## Common Skill Sequences

### New Album (Standard)
```
/new-album <name> <genre>
    -> /album-conceptualizer (plan concept, tracklist)
    -> /lyric-writer (for each track — auto-invokes /suno-engineer)
    -> /pronunciation-specialist (scan for risks)
    -> /lyric-reviewer (final QC)
    -> /pre-generation-check (validate all gates)
    -> [Generate in Suno]
    -> /mastering-engineer (master audio)
    -> /promo-director (optional: promo videos)
    -> /release-director (release to platforms)
```

### True-Story/Documentary Album
```
/new-album <name> <genre>
    -> /researcher (coordinate research)
        -> /document-hunter (find court docs)
        -> /researchers-legal, /researchers-gov, etc. (specialized research)
        -> /researchers-verifier (verify citations)
    -> /verify-sources (human source verification)
    -> /lyric-writer (write lyrics from sources — auto-invokes /suno-engineer)
    -> /pronunciation-specialist (names, places, acronyms)
    -> /lyric-reviewer (verify against sources)
    -> /pre-generation-check (validate all gates)
    -> [Generate in Suno] -> /mastering-engineer -> /release-director
```

### Resume Existing Work
```
/resume <album-name>
    -> [Claude reports status and next steps]
    -> Continue from appropriate skill based on phase
```

### Quick Quality Check
```
/pronunciation-specialist <track>
    -> /lyric-reviewer <track>
    -> /explicit-checker <album>
    -> /validate-album <album>
```

### Post-Generation to Release
```
/mastering-engineer <audio-folder>
    -> /promo-director <album> (optional)
    -> /cloud-uploader <album> (optional)
    -> /release-director <album>
```

---

## Skills That Work Together

Natural pairings that complement each other:

| Primary Skill | Pairs Well With | Why |
|---------------|-----------------|-----|
| `/lyric-writer` | `/pronunciation-specialist` | Catch pronunciation issues immediately |
| `/pronunciation-specialist` | `/lyric-reviewer` | Reviewer verifies pronunciation fixes applied correctly |
| `/lyric-reviewer` | `/pre-generation-check` | Review must pass before generation gate |
| `/researcher` | `/document-hunter` | Automate document acquisition |
| `/suno-engineer` | `/clipboard` | Copy prompts directly to Suno |
| `/mastering-engineer` | `/promo-director` | Promo videos need mastered audio |
| `/promo-director` | `/cloud-uploader` | Upload videos for sharing |
| `/album-conceptualizer` | `/album-art-director` | Visual and sonic vision together |
| `/new-album` | `/album-conceptualizer` | Always plan after creating structure |
| `/lyric-reviewer` | `/explicit-checker` | Both are pre-generation QC |

---

## Skills to Avoid Combining

Redundant or conflicting combinations:

| Avoid Combining | Reason |
|-----------------|--------|
| `/lyric-writer` + `/lyric-reviewer` (simultaneously) | Run separately: writer first, reviewer after pronunciation pass |
| Multiple researcher specialists at once | Use `/researcher` to coordinate them instead |
| `/mastering-engineer` before audio import | Need to generate on Suno and import audio first |
| `/release-director` before `/mastering-engineer` | Audio must be mastered before release |
| `/promo-director` before mastering | Promo videos need final mastered audio |

---

## Skill Categories by Model

Skills are assigned to models based on task complexity. See [model-strategy.md](model-strategy.md) for full rationale.

### Opus 4.6 (Critical Creative Work — 6 skills)
- `/lyric-writer` - Core creative content
- `/suno-engineer` - Music generation prompts
- `/album-conceptualizer` - Album concept shapes everything downstream
- `/lyric-reviewer` - QC gate before generation, must catch all issues
- `/researchers-legal` - Complex legal synthesis
- `/researchers-verifier` - High-stakes verification

### Sonnet 4.5 (Reasoning & Coordination — 24 skills)
- `/album-art-director` - Visual direction
- `/album-ideas` - Idea brainstorming and organization
- `/cloud-uploader` - Cloud storage coordination
- `/configure` - Interactive config setup
- `/document-hunter` - Automated searching
- `/explicit-checker` - Context-dependent content scanning
- `/mastering-engineer` - Audio guidance
- `/promo-director` - Video generation
- `/pronunciation-specialist` - Edge cases need judgment (homographs, context)
- `/release-director` - Release coordination
- `/researcher` - Research coordination
- `/researchers-biographical`, `/researchers-financial`, `/researchers-gov` - Specialized research
- `/researchers-historical`, `/researchers-journalism`, `/researchers-primary-source` - Specialized research
- `/researchers-security`, `/researchers-tech` - Specialized research
- `/resume` - Status reporting
- `/session-start` - Session startup procedure
- `/sheet-music-publisher` - Transcription workflow
- `/tutorial` - Interactive guided creation

### Haiku 4.5 (Pattern Matching — 14 skills)
- `/about` - Static information
- `/album-dashboard` - Progress dashboard
- `/clipboard` - Copy to clipboard
- `/help` - Display information
- `/import-art` - File operations
- `/import-audio` - File operations
- `/import-track` - File operations
- `/new-album` - Directory creation
- `/next-step` - Workflow routing
- `/pre-generation-check` - Gate validation
- `/skill-model-updater` - Pattern replacement
- `/test` - Run predefined checks
- `/validate-album` - Structure validation

---

## Quick Tips

- **Lost?** Start with `/resume <album-name>` to see status and next steps
- **New here?** Run `/tutorial` for guided walkthrough
- **Building true-story album?** Always start with `/researcher` before writing
- **Before Suno?** Run `/lyric-reviewer` to catch issues
- **Weird pronunciations?** Run `/pronunciation-specialist` on every track
- **Not sure what's available?** Run `/help` for categorized skill list
