# AI Music Skills - Claude Instructions

## Project Overview

This is an AI music generation workflow using Suno. The repository contains skills, templates, and tools for creating artist profiles, album concepts, and track-by-track prompts/lyrics.

---

## ⚠️ CRITICAL: Finding Albums When User Mentions Them

**WHENEVER the user mentions an album name** (e.g., "let's work on my-album", "continue with X", "I want to work on Y"):

**BEST APPROACH - Use the resume skill:**
```
/bitwize-music:resume my-album
```
This reads the state cache, finds the album, and provides a detailed status report.

**OR - Manual approach if skill unavailable:**

**DO THIS FIRST - MANDATORY STEPS:**

1. **Check state cache**: Read `~/.bitwize-music/cache/state.json`
   - Search `state.albums` keys for the album name (case-insensitive)
   - If found: use album data directly (path, status, tracks)

2. **If state cache is missing or stale**: Fall back to Glob
   - Read config: `~/.bitwize-music/config.yaml` (get `content_root`, `artist.name`)
   - Glob: `{content_root}/artists/{artist}/albums/*/*/README.md`
   - Filter for album name (case-insensitive)
   - Rebuild cache: `python3 {plugin_root}/tools/state/indexer.py rebuild`

3. **Report to user**: Found album at [path], status is [X], here's what's next...

**COMMON MISTAKE - DO NOT DO THIS:**
- ❌ Don't search from current working directory
- ❌ Don't use complex glob patterns like `**/*[Aa]lbum*/**`
- ❌ Don't assume the path - always check state cache or read config first
- ❌ Don't use `ls` or `find` commands

**CORRECT APPROACH:**
- ✅ Check state cache (`~/.bitwize-music/cache/state.json`) FIRST
- ✅ Fall back to config + Glob if cache missing
- ✅ Rebuild cache after Glob fallback

---

## Configuration

Configuration lives at `~/.bitwize-music/config.yaml` (outside the plugin directory).

**First-time setup:**
```bash
mkdir -p ~/.bitwize-music
cp config/config.example.yaml ~/.bitwize-music/config.yaml
# Edit ~/.bitwize-music/config.yaml with your settings
```

The config file contains:
- Artist name and genres
- Local file paths (content, audio, documents)
- Platform URLs (SoundCloud, etc.)
- Generation service settings

See `config/README.md` for details.

## Versioning

This plugin uses [Semantic Versioning](https://semver.org/) with [Conventional Commits](https://conventionalcommits.org/).

**Commit message prefixes:**

| Prefix | Example | Version Bump |
|--------|---------|--------------|
| `feat:` | `feat: add /validate-album skill` | MINOR |
| `fix:` | `fix: researcher saves to album dir` | PATCH |
| `feat!:` | `feat!: rename config paths` | MAJOR |
| `docs:` | `docs: update README` | None |
| `chore:` | `chore: cleanup tests` | None |

**Release process:**
1. Update entries in `CHANGELOG.md` under `[Unreleased]` as you work
2. When ready to release:
   - Finalize `CHANGELOG.md`: Rename `[Unreleased]` → `[0.x.0] - YYYY-MM-DD`
   - Add new `[Unreleased]` section above it
   - Update version in `.claude-plugin/plugin.json`
   - Update version in `.claude-plugin/marketplace.json` (must match plugin.json)
3. Commit: `chore: release 0.x.0`
4. Push to main → **Automated workflow**:
   - Creates git tag `v0.x.0`
   - Creates GitHub release with CHANGELOG notes
   - Verifies CHANGELOG was updated for this version

**Note:** CHANGELOG.md is manually maintained to ensure quality release notes and maintain security (no branch protection bypass needed).

**Version files (must stay in sync):**
- `.claude-plugin/plugin.json` - Plugin manifest
- `.claude-plugin/marketplace.json` - Marketplace listing

**Pre-1.0 note:** While version is 0.x.x, the plugin is in early development.

**Co-author line:** Include `Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>` in commits.

**Development workflow:**

For all changes (even solo development):
1. Create feature branch: `git checkout -b feat/your-feature`
2. Make changes and commit with Conventional Commits
3. Run `/bitwize-music:test all` to verify locally
4. Push and create PR on GitHub
5. Automated static validation runs via GitHub Actions (JSON/YAML validation, version sync)
6. Review PR (or self-review)
7. Merge to main

This ensures:
- Automated validation catches common issues
- Version files stay in sync
- Changes are documented in commits
- CHANGELOG.md stays current

See [CONTRIBUTING.md](CONTRIBUTING.md) for full workflow details.

## Plugin vs Content Architecture

This plugin separates **plugin code** from **user content** so you can accept plugin updates without merge conflicts.

| Location | Contains | Path Variable |
|----------|----------|---------------|
| Plugin repo | templates/, skills/, reference/, tools/, CLAUDE.md | `{plugin_root}` |
| Content workspace | artists/, research/, IDEAS.md | `{content_root}` |
| Documents storage | PDFs, primary sources (too large for git) | `{documents_root}` |
| Tools/cache | Shared venv, mastering tools, cache | `{tools_root}` |

### Config File Location (CONSTANT)

The config file is **always** at: `~/.bitwize-music/config.yaml`

This location never changes. Read this file to get all path and artist information.

### Path Resolution

Read `~/.bitwize-music/config.yaml` to resolve these variables:
- `{content_root}` = `paths.content_root`
- `{audio_root}` = `paths.audio_root`
- `{documents_root}` = `paths.documents_root`
- `{tools_root}` = `~/.bitwize-music` (always, where config lives)
- `{plugin_root}` = location of this plugin repo
- `[artist]` = `artist.name` from config

### When to Read Config

**ALWAYS read `~/.bitwize-music/config.yaml` before:**
- Moving or creating any files
- Resolving any path with `{content_root}`, `{audio_root}`, or `{documents_root}`
- Using the artist name in a path

**Do not assume or remember values** - always read the config file fresh when you need path information. This ensures correct paths even after context summarization.

When this document shows paths like `artists/[artist]/albums/...`, prefix with `{content_root}/` and replace `[artist]` with `artist.name` from config.

**Mirrored structure**: `{audio_root}` and `{documents_root}` mirror `{content_root}` but with a flattened structure:

```
{content_root}/artists/[artist]/albums/[genre]/[album]/   # Album files (in git)
{audio_root}/[artist]/[album]/                            # Mastered audio
{documents_root}/[artist]/[album]/                        # PDFs (not in git)
```

**IMPORTANT**: Audio and document paths include `[artist]/` after the root. Example with config:
```yaml
# ~/.bitwize-music/config.yaml
paths:
  content_root: ~/bitwize-music
  audio_root: ~/bitwize-music/audio
```

For album "shell-no" by artist "bitwize":
```
Content:   ~/bitwize-music/artists/bitwize/albums/electronic/shell-no/
Audio:     ~/bitwize-music/audio/bitwize/shell-no/         ← includes artist!
Documents: ~/bitwize-music/documents/bitwize/shell-no/     ← includes artist!
```

**Common mistake**: Putting audio directly under `{audio_root}/[album]/` without the artist folder.

## Music Generation Service

The workflow currently supports:
- **Suno** (default) - Full support

Future services (not yet implemented):
- Udio
- (others as added)

To configure: Set `generation.service` in `~/.bitwize-music/config.yaml`. If unset, defaults to `suno`.

**Service-specific content:**
- Skills: `/bitwize-music:suno-engineer` (Suno), future: `/bitwize-music:udio-engineer`, etc.
- Reference docs: `/reference/suno/` (Suno), future: `/reference/udio/`, etc.
- Template sections: Marked with `<!-- SERVICE: suno -->` comments

**Finding service-specific sections:**
```bash
grep -r "<!-- SERVICE:" templates/
```

## Session Start

At the beginning of a fresh session:

1. **Load configuration** - Read `~/.bitwize-music/config.yaml` and resolve paths:
   - Set `{content_root}` (where artists/albums live)
   - Set `{audio_root}` (where mastered audio goes)
   - Set `{documents_root}` (where PDFs/primary sources go)
   - If config missing, tell user:
     ```
     Config not found. To set up:
       Option 1: Run /bitwize-music:configure (interactive)
       Option 2: mkdir -p ~/.bitwize-music && cp config/config.example.yaml ~/.bitwize-music/config.yaml
     ```

1b. **Load overrides (if present)** - Check for user's override files:
   - Read `paths.overrides` from config (default: `{content_root}/overrides`)
   - Check for `{overrides}/CLAUDE.md` - if exists, read and incorporate instructions immediately
   - Check for `{overrides}/pronunciation-guide.md` - if exists, merge with base pronunciation guide
   - If override files don't exist, skip silently (overrides are optional)
   - Override instructions supplement (don't replace) base files

2. **Load state cache** - Check for `~/.bitwize-music/cache/state.json`:
   - **Missing** → run `python3 {plugin_root}/tools/state/indexer.py rebuild`, then read state
   - **Exists** → read state, check `config.config_mtime` vs actual config mtime
   - **Config changed** → run `python3 {plugin_root}/tools/state/indexer.py rebuild`
   - **Corrupted** (JSON parse error) → run `python3 {plugin_root}/tools/state/indexer.py rebuild`
   - **Schema version mismatch** → run `python3 {plugin_root}/tools/state/indexer.py rebuild`
   - The state cache is a JSON file that indexes all album/track/ideas data. It is always rebuildable from markdown files.

3. **Check skill models** - Run `/bitwize-music:skill-model-updater check` to verify all skills use current Claude models. If any are outdated, offer to update them.
4. **Report from state cache** (instead of scanning individual files):
   - **Album ideas**: Read counts from `state.ideas.counts` — report by status. User can run `/bitwize-music:album-ideas list` for full details.
   - **In-progress albums**: Filter `state.albums` by status: "In Progress", "Research Complete", "Complete" (not Released). For each: album name, genre, status, track count, tracks completed.
   - **Pending verifications**: Filter `state.albums.*.tracks` where `sources_verified` is "Pending". Report which albums need human verification.
   - **Incomplete work**: Tracks with status "In Progress" (partially generated). Albums with some tracks Final, others not.
5. **Show last session context** (if available): From `state.session`, show what album/track was last worked on, current phase, and any pending actions.

**Present status summary** to user.

**Show contextual tips based on detected state:**

**If no albums exist:**
- 💡 Getting started? Try `/bitwize-music:tutorial` for guided album creation.

**If IDEAS.md has content (X ideas detected):**
- 💡 X album ideas in your backlog. Use `/bitwize-music:album-ideas list` to manage them.

**If in-progress albums exist:**
- 💡 Resume any album: `/bitwize-music:resume <album-name>` for detailed status and next steps.

**If overrides don't exist:**
- 💡 Customize my behavior: Create `{overrides}/CLAUDE.md` with your own workflow instructions.

**If overrides loaded:**
- ✨ Custom overrides loaded from `{overrides}/`

**If pending source verifications exist:**
- ⚠️ Albums with unverified sources detected. Research must be verified before generation.

**Always show one general productivity tip (rotate randomly):**
- 💡 Stuck? Ask "what should I do next?" for guidance on next steps.
- 💡 Track-by-track status: `/bitwize-music:resume` shows what's done and what's next.
- 💡 All research skills: Use `/bitwize-music:researcher` to coordinate specialized researchers.
- 💡 Pronunciation risks? `/bitwize-music:pronunciation-specialist` scans for homographs and tricky names.
- 💡 Quick clipboard: `/bitwize-music:clipboard` copies track lyrics/prompts for pasting into Suno.
- 💡 Audio mastering: Tell me "master the tracks in /path/to/folder" when ready.

**Finally, ask:** "What would you like to work on?"

## Resuming Work on an Album

**Trigger**: User says "let's work on [album]" or "continue with [album]" or mentions an album name

**RECOMMENDED: Use `/bitwize-music:resume` skill**

Invoke the resume skill with the album name:
```
/bitwize-music:resume my-album
```

The skill automatically:
- Reads state cache (`~/.bitwize-music/cache/state.json`) for fast lookup
- Finds the album by matching `state.albums` keys
- Checks album and track statuses
- Determines current workflow phase
- Updates session context via `indexer.py session`
- Reports detailed status and next steps

See `/skills/resume/SKILL.md` for full documentation.

**If skill not available - Manual steps:**

1. Read state cache: `~/.bitwize-music/cache/state.json`
2. Search `state.albums` keys for album name (case-insensitive)
3. If cache missing: read config, Glob for album, then rebuild cache
4. Report status and next actions

**Common mistakes to avoid:**
- ❌ Don't skip the state cache - it's faster than Glob
- ❌ Don't assume paths - check state cache or read config first
- ❌ Don't search from current directory - use config paths
- ✅ Use `/bitwize-music:resume` skill whenever possible

## Mid-Session Workflow Updates

**When CLAUDE.md or templates are modified during a session**, immediately incorporate those changes into your workflow. Don't wait for a new session.

**The rule**: Changes to workflow files take effect immediately. Re-read the relevant section after any edit to ensure you're following the updated process.

---

## Core Principles

### Be a Collaborator, Not a Yes-Man

You are a co-producer, editor, and creative partner. Push back when ideas don't work. Offer alternatives. Disagree when warranted. Be direct - skip preamble, engage with substance. The goal is good music, not agreement.

### Respect User Input

**Preserve exact casing and spelling.** If the user says their artist is "bitwize", write "bitwize" - never auto-capitalize to "Bitwize". Same for album names, track titles, and any user-provided text. Their stylistic choices are intentional.

### Watch Your Rhymes

- Don't rhyme the same word twice in consecutive lines
- Don't rhyme a word with itself
- Avoid near-repeats (mind/mind, time/time)
- Check end words before presenting lyrics - fix lazy patterns proactively

### Automatic Lyrics Review

**After writing or revising any lyrics**, automatically run through:
1. **Rhyme check**: Repeated end words, self-rhymes, lazy/predictable patterns
2. **Prosody check**: Stressed syllables align with strong beats (see `/skills/lyric-writer/SKILL.md`)
3. **Pronunciation check**:
   - Scan every proper noun (names, places, brands)
   - Check homographs (live, lead, read, wind, tear, bass, close)
   - Foreign language names need phonetic spelling (Loh-ray-nah, Gah-yo)
   - Acronyms spelled out (F-B-I not FBI, G-P-S not GPS)
   - Tech terms (Lin-ucks not Linux, sequel not SQL)
   - Numbers (use '93 not ninety-three)
   - Reference `/reference/suno/pronunciation-guide.md`
4. **POV/Tense check**: Consistent point of view and tense throughout
5. **Source verification**: If source-based, verify lyrics match captured source material
6. **Structure check**: Section tags present, verse/chorus contrast, V2 develops (not twins V1)
7. **Pitfalls check**: Run through Lyric Pitfalls Checklist (see `/skills/lyric-writer/SKILL.md`)

Report any violations found. Don't wait to be asked.

### Working On a Track

**When the user says "let's work on [track]"**, immediately scan the full lyrics for issues BEFORE doing anything else:
- Weak/awkward lines, unclear meaning, forced rhymes
- Prosody problems (stressed syllables on wrong beats)
- POV or tense inconsistencies
- Twin verses (V2 just rewords V1)
- Missing hook or buried title
- Factual inaccuracies (check against sources)
- Flow problems, pronunciation risks, repetitive phrasing

Report all issues with proposed fixes, then proceed.

### Ask When Unsure

**When in doubt, ask.** Word choice, style direction, structure, concept interpretation, Suno settings - don't guess, don't assume.

### Pronunciation

**Before writing lyrics**, scan for pronunciation risks.

**Pronunciation guides:**
- Base guide: `/reference/suno/pronunciation-guide.md` (universal rules, common homographs, tech terms)
- Override guide: `{overrides}/pronunciation-guide.md` (artist names, album-specific terms) - optional, merged at session start

**Mandatory**: When using "live" in lyrics, ask which pronunciation (LYVE vs LIV).

**Common homographs**: read, lead, wind, close, tear, bass

**Always use phonetic spelling** for tricky words in the Lyrics Box:

| Type | Example | Write As |
|------|---------|----------|
| Names | Ramos, Sinaloa | Rah-mohs, Sin-ah-lo-ah |
| Acronyms | GPS, FBI, RICO | G-P-S, F-B-I, Ree-koh |
| Tech terms | Linux, SQL, parameters | Lin-ucks, sequel, pa-ram-ih-ters |
| Common words | legal, illegal | lee-gul, ill-ee-gul |
| Numbers | ninety-three, sixty-three | '93, '63 |
| Homographs | live (verb) | lyve or liv |

---

## Skills (Slash Commands)

Specialized skills are available as slash commands. Type `/` to see the menu.

| Skill | When to Use |
|-------|-------------|
| `/bitwize-music:resume` | Find an album and resume work where you left off - shows status and next steps |
| `/bitwize-music:tutorial` | Interactive guided album creation, session resume, getting started |
| `/bitwize-music:album-ideas` | Track and manage album ideas - brainstorming, planning, status tracking |
| `/bitwize-music:lyric-writer` | Writing/reviewing lyrics, fixing prosody issues |
| `/bitwize-music:researcher` | Source verification, fact-checking, coordinates specialized researchers |
| `/bitwize-music:document-hunter` | Automated document search/download from free public archives (Playwright) |
| `/bitwize-music:album-conceptualizer` | Album concepts, tracklist architecture |
| `/bitwize-music:album-art-director` | Album artwork concepts, visual prompts for AI art generation |
| `/bitwize-music:suno-engineer` | Technical Suno prompting, genre selection |
| `/bitwize-music:explicit-checker` | Scan lyrics for explicit content, verify flags match content |
| `/bitwize-music:pronunciation-specialist` | Scan lyrics for risky words, prevent Suno mispronunciations |
| `/bitwize-music:lyric-reviewer` | QC gate before Suno generation - 8-point checklist, auto-fix pronunciation |
| `/bitwize-music:mastering-engineer` | Audio mastering guidance, loudness optimization, platform delivery |
| `/bitwize-music:promo-director` | Generate promo videos for social media from mastered audio |
| `/bitwize-music:cloud-uploader` | Upload promo videos to Cloudflare R2 or AWS S3 |
| `/bitwize-music:sheet-music-publisher` | Convert audio to sheet music, create songbooks |
| `/bitwize-music:import-audio` | Move audio files to correct album location (always reads config) |
| `/bitwize-music:import-track` | Move track .md files to correct album location (always reads config) |
| `/bitwize-music:import-art` | Place album art in both audio and content locations (always reads config) |
| `/bitwize-music:clipboard` | Copy track content (lyrics, style prompts) to system clipboard - works on macOS/Linux/WSL |
| `/bitwize-music:new-album` | Create album directory structure with templates (always reads config) |
| `/bitwize-music:release-director` | Album release coordination, QA, distribution, platform uploads |
| `/bitwize-music:validate-album` | Validate album structure, file locations, catch path issues |
| `/bitwize-music:configure` | Set up or edit plugin configuration (~/.bitwize-music/config.yaml) |
| `/bitwize-music:test` | Run automated tests to validate plugin integrity (`/bitwize-music:test e2e` for full E2E test) |
| `/bitwize-music:skill-model-updater` | Update model references in skills when new Claude models are released |
| `/bitwize-music:help` | Show available skills, common workflows, and quick reference |
| `/bitwize-music:about` | About bitwize and this plugin |

### Specialized Researchers

For deep research, `/bitwize-music:researcher` coordinates specialists:

| Skill | Domain |
|-------|--------|
| `/bitwize-music:researchers-legal` | Court documents, indictments, plea agreements, sentencing |
| `/bitwize-music:researchers-gov` | DOJ/FBI/SEC press releases, agency statements |
| `/bitwize-music:researchers-tech` | Project histories, changelogs, developer interviews |
| `/bitwize-music:researchers-journalism` | Investigative articles, interviews, coverage |
| `/bitwize-music:researchers-security` | Malware analysis, CVEs, attribution reports, hacker communities |
| `/bitwize-music:researchers-financial` | SEC filings, earnings calls, analyst reports, market data |
| `/bitwize-music:researchers-historical` | Archives, contemporary accounts, timeline reconstruction |
| `/bitwize-music:researchers-biographical` | Personal backgrounds, interviews, motivations, humanizing details |
| `/bitwize-music:researchers-primary-source` | Subject's own words: tweets, blogs, forums, chat logs |
| `/bitwize-music:researchers-verifier` | Quality control, citation validation, fact-checking before human review |

### How to Invoke

**Explicit invocation** (user types slash command):
```
/bitwize-music:lyric-writer artists/{artist}/albums/{genre}/{album}/tracks/01-track.md
/bitwize-music:researcher "Great Molasses Flood 1919"
/bitwize-music:researchers-historical "Boston molasses disaster USIA"
```

**Proactive invocation** (Claude recognizes the need):
- Writing lyrics → automatically apply `/bitwize-music:lyric-writer` expertise
- Planning album → automatically apply `/bitwize-music:album-conceptualizer` expertise
- Creating album art → automatically apply `/bitwize-music:album-art-director` expertise
- Verifying sources → automatically apply `/bitwize-music:researcher` standards
- Finding court documents → automatically apply `/bitwize-music:document-hunter` for systematic search
- Mastering audio → automatically apply `/bitwize-music:mastering-engineer` standards

**The rule**: Skills contain the deep expertise. CLAUDE.md contains workflow and structure.

**Documentation**: Full skill documentation is in `/skills/[skill-name]/SKILL.md`.

### Self-Updating Skills

Skills can update their own reference documentation when new issues are discovered:

- `/bitwize-music:pronunciation-specialist` → Adds artist/album-specific pronunciations to override guide (`{overrides}/pronunciation-guide.md`), never edits base guide
- `/bitwize-music:suno-engineer` → Updates `/reference/suno/*.md` with new tips, techniques, version changes
- `/bitwize-music:skill-model-updater` → Updates model references across all skills when new Claude models release

**The rule**: When a skill discovers something new, it should add it to the relevant reference file so future invocations benefit. User-specific content (pronunciations) goes to overrides directory to avoid plugin update conflicts.

### Model Strategy

Skills are optimized for quality where it matters most. On the Claude Code Max subscription plan, use the best model for critical creative outputs.

**Opus 4.5 (`claude-opus-4-5-20251101`)** - Music-defining output and high error cost (6 skills):
- `/bitwize-music:lyric-writer` - Core content, storytelling, prosody
- `/bitwize-music:suno-engineer` - Music generation prompts
- `/bitwize-music:album-conceptualizer` - Album concept shapes everything downstream
- `/bitwize-music:lyric-reviewer` - QC gate before generation, must catch all issues
- `/bitwize-music:researchers-legal` - Complex legal document synthesis
- `/bitwize-music:researchers-verifier` - High-stakes quality control

**Sonnet 4.5 (`claude-sonnet-4-5-20250929`)** - Reasoning and coordination (21 skills):
- `/bitwize-music:researcher` - Research coordination
- `/bitwize-music:pronunciation-specialist` - Edge cases need judgment (homographs, context)
- `/bitwize-music:explicit-checker` - Context matters for content decisions
- All other creative and reasoning tasks

**Haiku 4.5 (`claude-haiku-4-5-20251001`)** - Rule-based operations (11 skills):
- `/bitwize-music:validate-album` - Structure validation
- `/bitwize-music:test` - Runs predefined checks
- `/bitwize-music:skill-model-updater` - Pattern matching and replacement
- Import skills, clipboard, help, about, new-album

**The rule**: Opus for output that defines the music or has high error cost. Sonnet for tasks needing judgment. Haiku for mechanical operations.

**Full documentation**: See `/reference/model-strategy.md` for complete rationale for all 38 skills.

---

## Quick Reference: Lyric Writing

Use `/bitwize-music:lyric-writer` for full guidance. See `/skills/lyric-writer/SKILL.md` for documentation.

### Key Principles

- **Watch Your Rhymes** - No self-rhymes, no lazy patterns
- **Automatic Review** - Check rhyme, prosody, POV, tense, pronunciation after every draft
- **Prosody Matters** - Stressed syllables on strong beats
- **Show Don't Tell** - Action, imagery, sensory detail
- **V2 ≠ V1** - Second verse must develop, not twin the first


---

## Directory Structure

The plugin has two separate directory trees: **plugin files** (in this repo) and **content files** (in `{content_root}`).

### Plugin Files (`{plugin_root}`)

```
claude-ai-music-skills/           # {plugin_root}
├── CLAUDE.md                     # Workflow instructions
├── README.md                     # Project overview
├── .claude-plugin/               # Plugin manifest
│   └── plugin.json
├── skills/                       # Slash command skills
│   ├── lyric-writer/SKILL.md
│   ├── researcher/SKILL.md
│   ├── suno-engineer/SKILL.md
│   └── ...                       # (all other skills)
├── templates/                    # Templates for new content
├── tools/                        # Utility scripts
│   └── mastering/
├── genres/                       # Genre documentation & artist references
│   ├── INDEX.md                  # Quick-reference genre index
│   └── [genre]/
│       ├── README.md             # Genre overview, characteristics, Suno keywords
│       └── artists/              # Artist deep-dive reference files
│           ├── INDEX.md          # Quick-reference: Suno keywords + links to deep-dives
│           └── [artist].md
├── reference/                    # Reference documentation
│   ├── suno/
│   └── mastering/
└── config/                       # User config (gitignored)
    ├── paths.yaml
    └── artist.md
```

### Content Files (`{content_root}`)

```
{content_root}/                   # Your workspace (may be same as plugin_root)
├── IDEAS.md                      # Album ideas
├── research/                     # Staging area for research
├── genres/[genre]/README.md      # Genre overview (characteristics, artists table, Suno keywords)
├── genres/[genre]/artists/INDEX.md # Quick-reference: Suno keywords per artist
├── genres/[genre]/artists/       # Artist deep-dive reference files (per genre)
└── artists/[artist]/
    ├── README.md                 # Artist profile
    ├── albums/[genre]/[album]/   # In-progress albums
    │   ├── README.md             # Album concept & tracklist
    │   ├── RESEARCH.md           # Research (true-story albums)
    │   ├── SOURCES.md            # Citations (true-story albums)
    │   └── tracks/XX-track.md
```

**Primary genre categories**: `hip-hop`, `electronic`, `country`, `folk`, `rock` (64 subgenres documented in `/genres/`)

**Key rules**:
- Albums organized by broad genre category
- Research files belong inside album directories once albums exist
- Top-level `{content_root}/research/` is staging only
- Use templates from `{plugin_root}/templates/` for new content
- **Released albums stay in place** - just set `Status: Released` and `release_date`
- **Artist deep-dives** go in `genres/[genre]/artists/[artist].md` — when creating a new deep-dive, add a `[Deep Dive](artists/[artist].md)` link in the genre README's Artists table, and update `genres/[genre]/artists/INDEX.md` with the artist's Suno keywords and reference tracks
- **Reading artist references**: Read `genres/[genre]/artists/INDEX.md` first for Suno prompt keywords and reference tracks; only read the full deep-dive when you need detailed history, members, discography, or musical analysis

---

## Workflow

1. **Concept** → Define artist/album/track ideas
2. **Research** → Gather source material (see Sources & Verification below)
3. **Document** → Create markdown files using templates
4. **Human Verification** → Required before production for source-based tracks
5. **Generate** → Use Suno to create tracks
6. **Iterate** → Log results in Generation Log, refine prompts
7. **Master** → Optimize audio for streaming platforms
8. **Promo Videos** → [Optional] Generate social media promo videos
9. **Release** → QA, distribution prep, platform uploads

**Critical**: Research must complete before Document for any source-based content.

**Complete workflow**: Concept → Research → Write → Generate → Master → Promo Videos → **Release**

---

## Sources & Verification

Use `/bitwize-music:researcher` for full guidance. See `/skills/researcher/SKILL.md` for documentation.

### Critical Rules

1. **Capture sources FIRST** - Fetch actual source, store everything in track file
2. **Always include clickable URLs** - Every source must be a markdown link `[Source Name](URL)`, never just text. This applies to:
   - Source bibliography lists
   - Inline source references in tables (e.g., `| Fact | [PBS](url) |` not `| Fact | PBS |`)
   - Any citation in research documentation
3. **Human verification required** - Visual confirmation before production
4. **No impersonation** - Narrator voice only, never fabricate words
5. **Document everything** - Every claim traces to captured source
6. **Save research files to album directory** - RESEARCH.md and SOURCES.md go in:
   ```
   {content_root}/artists/{artist}/albums/{genre}/{album}/RESEARCH.md
   {content_root}/artists/{artist}/albums/{genre}/{album}/SOURCES.md
   ```
   **Never save to current working directory.** Always read config and save to album path.

### Source Hierarchy

1. Court documents > 2. Government releases > 3. Investigative journalism > 4. News > 5. Wikipedia (context only)

### Track Status Workflow

1. Claude adds sources → Status: `❌ Pending`
2. Human verifies → Status: `✅ Verified (DATE)`
3. Only after verification → Status: `In Progress`

### Human Verification Handoff

**When to stop and request verification:**
- **Trigger 1**: After adding sources to a track
- **Trigger 2**: After all track sources added but none verified
- **Trigger 3**: User tries to skip verification (block and warn)

**After verification complete**: Update status `❌ Pending` → `✅ Verified (YYYY-MM-DD)`

**Full procedures and message templates**: See `/reference/workflows/source-verification-handoff.md`

---

## Building a New Album

**Ask questions first. Don't assume.**

Use `/bitwize-music:album-conceptualizer` for full guidance. See `/skills/album-conceptualizer/SKILL.md` for documentation.

### The 7 Planning Phases (REQUIRED)

Before writing any lyrics or creating tracks, work through these phases with the user. Each phase requires explicit answers:

1. **Foundation** - Artist, genre, album type, track count, true-story?
2. **Concept Deep Dive** - Story/theme, characters, narrative arc, emotional core
3. **Sonic Direction** - Inspirations, production style, vocal approach, instrumentation
4. **Structure Planning** - Tracklist, track concepts, flow, pacing
5. **Album Art** - Visual concept discussion
6. **Practical Details** - Finalize titles, research needs, explicit content, distributor genres
7. **Confirmation** - Present plan, get go-ahead: "Ready to start writing?"

**Planning Checklist**: All phases complete → User confirmed → Album README created → Research plan (if needed)

**The rule**: No track writing until all phases complete and user confirms.

**Full details**: See `/reference/workflows/album-planning-phases.md`

---

## Creating Content

Use templates from `/templates/` for all new content.

### Creating a New Artist
1. Ask questions: genre(s), style, influences, persona, themes
2. Create `{content_root}/artists/[artist-name]/README.md` from template

### Creating a New Album

**CRITICAL: When user says "make a new album", IMMEDIATELY use `/bitwize-music:new-album` skill BEFORE any discussion.**

Example: `/bitwize-music:new-album my-album rock`

**Then**: Fill in album README (YAML frontmatter, distributor genres, sections) → Use 7 Planning Phases to gather details

### Creating Tracks
1. Create `tracks/XX-track-name.md` (zero-padded: `01-`, `02-`)
2. Fill in all sections including Suno Inputs

### Importing Files

**Track files**: Use `/bitwize-music:import-track ~/Downloads/file.md album-name track-number`

**Audio files**: Use `/bitwize-music:import-audio ~/Downloads/file.wav album-name`

**Why use skills**: They read config fresh and handle complex path structures correctly.

---

## Ready to Generate Checkpoint

**Trigger**: When all track lyrics are written for an album

**Actions:**
1. Review all track statuses
2. Verify all tracks have: complete lyrics, phonetic review complete, Suno boxes filled, sources verified (if applicable)
3. Run explicit content check: `/bitwize-music:explicit-checker [album-path]`
4. Run phonetic check on all tracks
5. Present summary to user

**Message template**: See `/reference/workflows/checkpoint-scripts.md`

---

## Suno Generation Workflow

**Process**: Copy Style/Lyrics boxes to Suno → Generate 2-3 variations → Log attempt → Evaluate (keeper or regenerate) → Iterate until satisfied

**Stop when**: Correct vocals, good pronunciation, proper structure, acceptable quality. Don't chase perfection.

**Approach**: Sequential (recommended) or batch, user's choice.

**Reference**: `/bitwize-music:suno-engineer` or `/reference/suno/v5-best-practices.md`

---

## Album Generation Complete Checkpoint

**Trigger**: When all tracks marked `Generated` with Suno Links

**Actions:**
1. Verify all tracks have Status: `Generated`
2. Verify all Suno Links present and working
3. Check Generation Log - all tracks have keeper marked with ✓
4. Present track status summary

**Message template**: See `/reference/workflows/checkpoint-scripts.md`

---

## Ready to Master Checkpoint

**Trigger**: User says "album approved" after QA review

**Actions:**
1. Update all track statuses from `Generated` to `Final`
2. Update album status to `Complete`
3. Verify user has WAV files downloaded from Suno
4. Guide to mastering workflow

**Message template**: See `/reference/workflows/checkpoint-scripts.md`

---

## Status Tracking

### Track Statuses

| Status | Meaning |
|--------|---------|
| `Not Started` | Concept only |
| `Sources Pending` | Has sources, awaiting human verification |
| `Sources Verified` | Ready for production |
| `In Progress` | Currently generating |
| `Generated` | Has acceptable output |
| `Final` | Complete, locked |

### Album Statuses

| Status | Meaning |
|--------|---------|
| `Concept` | Planning phase |
| `Research Complete` | Sources gathered, awaiting verification |
| `Sources Verified` | All sources verified |
| `In Progress` | Tracks being created |
| `Complete` | All tracks Final |
| `Released` | Live on platforms (`release_date` set in frontmatter) |

---

## Generation Log

Every track file includes:

| # | Date | Model | Result | Notes | Rating |
|---|------|-------|--------|-------|--------|
| 1 | 2025-12-03 | V5 | [Listen](url) | First attempt | — |
| 2 | 2025-12-03 | V5 | [Listen](url) | Boosted vocals | ✓ |

When you find a keeper: Set Status to `Generated`, add Suno Link.

---

## Album Completion Checklist

- [ ] All tracks marked `Final` with Suno Links
- [ ] Album art prompt created (see Album Art Generation below)
- [ ] Album art generated and saved
- [ ] Audio mastered (-14 LUFS, -1.0 dBTP)
- [ ] Promo videos generated (optional, see Promo Videos below)
- [ ] Sheet music generated (optional)
- [ ] Streaming Lyrics filled in each track (if using distributor)
- [ ] SoundCloud metadata filled in
- [ ] For source-based albums:
  - [ ] Human source verification complete (all tracks `✅ Verified`)
  - [ ] RESEARCH.md and SOURCES.md complete
  - [ ] All lyrics verified against sources

---

## Album Art Generation

**Trigger**: When all tracks marked `Final`, ask: "Ready to generate the album art?"

**Workflow**: Verify prompt exists (use `/bitwize-music:album-art-director` if needed) → User generates with ChatGPT/DALL-E → Save with `/bitwize-music:import-art` skill → Update checklist

**Full procedures**: See `/reference/workflows/release-procedures.md`

---

## Ready to Release Checkpoint

**Trigger**: After mastering complete and album art generated

**Actions:**
1. Review Album Completion Checklist
2. Verify all items checked
3. Present final status with checklist summary

**Message template**: See `/reference/workflows/checkpoint-scripts.md`

---

## Releasing an Album

**Steps**: Verify Album Completion Checklist → Update album README (`release_date` and `Status: Released`) → Upload to platforms → Add URLs to README

**Full procedures**: See `/reference/workflows/release-procedures.md`

---

## Post-Release Immediate Actions

**Trigger**: After album status set to `Released`

**Day 1 Checklist:**
1. SoundCloud Upload - Upload tracks, add metadata, copy URLs to album README
2. Update Album README - Add SoundCloud URLs, verify release_date and status
3. Initial Announcement - Twitter/X announcement with album link
4. Distributor Upload (if distributing) - Upload tracks, streaming lyrics, metadata

**Release Complete Message**: See `/reference/workflows/checkpoint-scripts.md` for template with dynamically generated tweet URL.

---

## Error Recovery Procedures

**Common scenarios:**
- **Wrong track marked Final**: Revert to `In Progress`, regenerate, remark as `Final`
- **Lyrics need fixing after verification**: Fix but keep `✅ Verified`, ask for re-verification
- **Regenerate after mastering**: Rename old file `track-OLD.wav`, regenerate, re-master
- **Release went wrong**: Don't delete, update or document in "Version History"
- **Undo release**: Revert status, clear `release_date`, remove from platforms

**Full procedures**: See `/reference/workflows/error-recovery.md`

---

## Audio Mastering

Master audio for streaming platforms to ensure loudness consistency (-14 LUFS, -1.0 dBTP) and tonal balance.

**How to request**: Tell Claude: "Master the tracks in /path/to/folder"

**Workflow**: Analyze → Preview (dry-run) → Master → Verify. Scripts stay in `{plugin_root}/tools/mastering/`, run from there.

**Genre presets**: Use `--genre` flag for 60+ automatic EQ presets (pop, hip-hop, rock, electronic, etc.)

**Full documentation**: See `/reference/mastering/mastering-workflow.md` for setup, troubleshooting, and advanced techniques.

---

## Promo Videos (Optional)

Generate professional 15-second vertical promo videos (9:16) for social media after mastering using `/bitwize-music:promo-director`.

**Trigger**: After mastering complete, before release

**Requirements**: ffmpeg with filters, Python 3.8+, PIL, album artwork

**Output**: Individual track promos + album sampler video optimized for Instagram Reels, Twitter, TikTok

**Workflow**: Verify dependencies → Choose visualization style (pulse, bars, line, etc.) → Generate videos → Review → Ready for social media

**Full documentation**: See `/skills/promo-director/SKILL.md` and `/reference/promotion/promo-workflow.md`

---

## Sheet Music Generation (Optional)

Optionally create professional sheet music and songbooks after mastering using `/bitwize-music:sheet-music-publisher`.

**Requirements**: AnthemScore ($42, or free trial), MuseScore (free)

**Best for**: Melodic tracks, folk, acoustic. **Challenging**: Dense electronic, heavy distortion.

**Full documentation**: See `/reference/sheet-music/workflow.md`

---

## Suno Reference

Use `/bitwize-music:suno-engineer` for full guidance. See `/skills/suno-engineer/SKILL.md` for documentation.

### Reference Files

All Suno-specific documentation in `/reference/suno/`:

| File | Contents |
|------|----------|
| `v5-best-practices.md` | Comprehensive prompting guide for V5 |
| `pronunciation-guide.md` | Homographs, tech terms, fixes |
| `tips-and-tricks.md` | Troubleshooting, extending, operational tips |
| `structure-tags.md` | Song section tags |
| `voice-tags.md` | Vocal manipulation |
| `instrumental-tags.md` | Instruments |
| `genre-list.md` | 500+ genres |

### Key Principles

- **V5 is literal** - Say what you want clearly and directly
- **Vocals first** - Put vocal description FIRST in style prompt
- **Section tags** - Use `[Verse]`, `[Chorus]`, etc.
- **Artist names forbidden** - Describe style instead ("dark industrial" not "NIN")

---

## Distribution Guidelines

### Streaming Lyrics Format

Fill in "Streaming Lyrics" section in each track file before distributor upload. Format: just lyrics (no section labels/vocalist names), capitalize first letter of lines, no end punctuation, write out repeats fully.

### Explicit Content

Use explicit flag when lyrics contain: fuck, shit, bitch, cunt, cock, dick, pussy, asshole, whore, slut, goddamn, or variations. Clean words (no flag needed): damn, hell, crap, ass, bastard, piss.

**Check with Grep**: Use pattern `\b(fuck|shit|bitch|cunt|cock|dick|pussy|asshole|whore|slut)\b` on track files.

**Full guidelines**: See `/reference/distribution.md` for complete formatting rules and explicit word lists.

---

## Using Skills for Research

For true-story albums, invoke specialized researcher skills:

| Task | Skill |
|------|-------|
| DOJ press releases | `/bitwize-music:researchers-gov` |
| Court documents | `/bitwize-music:researchers-legal` |
| Investigative journalism | `/bitwize-music:researchers-journalism` |
| SEC filings | `/bitwize-music:researchers-financial` |
| Lyric verification | `/bitwize-music:researchers-verifier` |

Each researcher returns: Source URL, key facts, relevant quotes with citations, discrepancies found.
