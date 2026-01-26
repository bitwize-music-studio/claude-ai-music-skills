# AI Music Skills - Claude Instructions

## Project Overview

This is an AI music generation workflow using Suno. The repository contains skills, templates, and tools for creating artist profiles, album concepts, and track-by-track prompts/lyrics.

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

2. **Check skill models** - Run `/bitwize-music:skill-model-updater check` to verify all skills use current Claude models. If any are outdated, offer to update them.
3. **Check album ideas** - Read `paths.ideas_file` from config (default: `{content_root}/IDEAS.md`) for pending album ideas. Report counts by status. User can run `/bitwize-music:album-ideas list` for full details.
4. **Check in-progress albums**:
   - Scan `{content_root}/artists/*/albums/*/` for albums with Status: "In Progress" or "Research Complete"
   - Report album name, status, track count, tracks completed
5. **Check pending verifications**:
   - Look for tracks with Status: `❌ Pending`
   - Report which albums need human verification
6. **Check for incomplete work**:
   - Tracks with Status: "In Progress" (partially generated)
   - Albums with some tracks Final, others not

**Present status summary** to user, ask what to work on.

**Tip**: Users can also run `/bitwize-music:tutorial resume` for an interactive guide to their in-progress work.

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

**Opus 4.5 (`claude-opus-4-5-20251101`)** - Critical creative outputs:
- `/bitwize-music:lyric-writer` - Core content, storytelling, prosody
- `/bitwize-music:suno-engineer` - Music generation prompts
- `/bitwize-music:researchers-legal` - Complex legal document synthesis
- `/bitwize-music:researchers-verifier` - High-stakes quality control

**Sonnet 4.5 (`claude-sonnet-4-5-20250929`)** - Most tasks:
- `/bitwize-music:album-conceptualizer` - Album planning
- `/bitwize-music:researcher` - Research coordination
- All other creative and reasoning tasks

**Haiku 4.5 (`claude-haiku-4-5-20251001`)** - Pattern matching only:
- `/bitwize-music:pronunciation-specialist` - Scanning for pronunciation risks

**The rule**: Optimize for quality on lyrics and Suno prompts. These define the music output. Everything else can use Sonnet.

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
├── genres/[genre]/README.md      # Genre documentation
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

---

## Workflow

1. **Concept** → Define artist/album/track ideas
2. **Research** → Gather source material (see Sources & Verification below)
3. **Document** → Create markdown files using templates
4. **Human Verification** → Required before production for source-based tracks
5. **Generate** → Use Suno to create tracks
6. **Iterate** → Log results in Generation Log, refine prompts
7. **Master** → Optimize audio for streaming platforms
8. **Release** → QA, distribution prep, platform uploads

**Critical**: Research must complete before Document for any source-based content.

**Complete workflow**: Concept → Research → Write → Generate → Master → **Release**

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

#### Trigger 1: After Adding Sources to Track
When you've added source material to a track's "Quotes & Attribution" section:

**Say to user:**
```
⚠️ VERIFICATION REQUIRED

I've added source material to [track name]. Before we proceed to writing lyrics:

1. Review the "Quotes & Attribution" section in tracks/XX-track-name.md
2. Click each source URL and visually confirm the quotes/facts
3. Check that citations match the actual source content
4. If verified, tell me: "sources verified for track XX"
5. If issues found, tell me what needs correction

Do NOT proceed to generation until you confirm verification.
```

#### Trigger 2: After All Track Sources Added
When all tracks in an album have sources but none are verified:

**Say to user:**
```
⚠️ ALBUM VERIFICATION REQUIRED

All tracks have source material added (Status: ❌ Pending).

Next step: Human verification of all sources before any track generation.

To verify:
1. Open each track file in tracks/
2. Review "Quotes & Attribution" section
3. Click URLs, verify quotes/facts match sources
4. Tell me which tracks are verified (e.g., "tracks 1-5 verified")

Current verification status:
- Track 01: ❌ Pending
- Track 02: ❌ Pending
[... list all tracks ...]

I'll wait for your verification before proceeding.
```

#### Trigger 3: User Tries to Skip Verification
If user says "let's generate" or "start production" while tracks show `❌ Pending`:

**Say to user:**
```
⚠️ CANNOT PROCEED - VERIFICATION REQUIRED

Tracks with unverified sources cannot be generated. This is a legal safeguard.

Tracks needing verification:
- Track XX: [name] (❌ Pending)

Please verify sources first, then we can proceed to generation.
```

### After Verification Complete

Once user confirms verification:

1. Update track status from `❌ Pending` to `✅ Verified (YYYY-MM-DD)`
2. Update "Sources Verified" field in track file
3. Now track can move to `In Progress` for generation
4. Update album status if all tracks verified

---

## Building a New Album

**Ask questions first. Don't assume.**

Use `/bitwize-music:album-conceptualizer` for full guidance. See `/skills/album-conceptualizer/SKILL.md` for documentation.

### The 7 Planning Phases (REQUIRED)

**Before writing any lyrics or creating tracks**, work through these phases with the user. Each phase requires explicit answers.

#### Phase 1: Foundation
**MUST answer before proceeding:**
- Who is the artist? (Existing or new?)
- What genre(s)? (Primary category: hip-hop, electronic, country, folk, rock)
- What album type? (Documentary, Narrative, Thematic, Character Study, Collection)
- How many tracks? (Full album ~10-15, EP ~4-6, Single)
- Is this true-story/documentary? (Determines research requirements)

#### Phase 2: Concept Deep Dive
**MUST answer before proceeding:**
- What's the central story/theme/message?
- Who are the key characters or subjects?
- What's the narrative arc or thematic journey?
- What's the emotional core?
- Why this story? (For artist, for audience)

#### Phase 3: Sonic Direction
**MUST answer before proceeding:**
- What artists/albums inspire this sound?
- Production style? (Dark/bright, minimal/dense, organic/synthetic)
- Vocal approach? (Narrator, character voices, sung, rapped, mixed)
- Instrumentation palette?
- Mood/atmosphere?

#### Phase 4: Structure Planning
**MUST answer before proceeding:**
- Tracklist outline (titles or working titles)
- Track-by-track concepts (1-2 sentences each)
- Narrative/thematic flow across tracks
- Which tracks are pivotal?
- Pacing (building, episodic, consistent intensity)?

#### Phase 5: Album Art
**Discuss visual concept:**
- What imagery represents the album?
- Color palette?
- Mood/aesthetic?
- Any symbolic elements?

*(Actual generation happens later - see Album Art Generation)*

#### Phase 6: Practical Details
**Confirm:**
- Album title finalized?
- Track titles finalized (or willing to adjust)?
- Research needs? (Documentary albums: RESEARCH.md, SOURCES.md)
- Explicit content expected?
- distributor genre categories?

#### Phase 7: Confirmation
**Required before writing:**
- Present complete plan to user
- Get explicit go-ahead: **"Ready to start writing?"**
- Document all answers in album README

### Planning Checklist

Before creating any track files:
- [ ] All 7 phases completed with explicit answers
- [ ] User confirmed: "Ready to start writing"
- [ ] Album README created with all planning details documented
- [ ] Research plan established (if true-story album)

**The rule**: No track writing until all phases complete and user confirms.

---

## Creating Content

Use templates from `/templates/` for all new content.

### Creating a New Artist
1. Ask questions: genre(s), style, influences, persona, themes
2. Create `{content_root}/artists/[artist-name]/README.md` from template

### Creating a New Album

**CRITICAL: When user says "make a new album" or "let's work on [album]", IMMEDIATELY create the directory structure BEFORE any discussion or writing.**

**Step 1: Use `/bitwize-music:new-album` skill (FIRST)**

```
/bitwize-music:new-album shell-no electronic
```

The skill:
1. Reads config to get `content_root` and `artist.name`
2. Creates directory: `{content_root}/artists/{artist}/albums/{genre}/{album}/tracks/`
3. Copies album template as README.md
4. For documentary albums, also copies RESEARCH.md and SOURCES.md templates

**Why use the skill**: It always reads config fresh and creates the correct path structure with all templates.

**Step 2: Fill in Album README**
1. **Fill in YAML frontmatter** at the top of README:
   - `title`: Album title (required)
   - `release_date`: YYYY-MM-DD format (fill in when releasing)
   - `genres`: Array like `["hip-hop", "documentary"]`
   - `tags`: Array like `["tech", "linux", "true-story"]`
   - `explicit`: `true` or `false`
   - `soundcloud_url`: Fill in when released
   - `spotify_url`: Optional, fill in when released
   - `slug`: Only needed if overriding auto-generated slug
2. Add distributor genre categories (Primary Genre, Secondary Genre, Subgenre)
3. Fill in Suno Persona if using a consistent persona for the album (name + link)
4. Fill in all sections (Concept, Tracklist, Production Notes, etc.)

**Step 4: Then Ask Planning Questions**
Use the 7 Planning Phases from `/bitwize-music:album-conceptualizer` to fill in details.

**Note**: The album template includes YAML frontmatter skeleton.

### Creating Tracks
1. Create `tracks/XX-track-name.md` (zero-padded: `01-`, `02-`)
2. Fill in all sections including Suno Inputs

### Importing External Track Files

**Trigger**: User says "I created track X for [album]" or "I have a track file for [album]" and the file is outside the album directory (e.g., Downloads, Desktop, another folder).

**Use the `/bitwize-music:import-track` skill:**

```
/bitwize-music:import-track ~/Downloads/t-day-beach.md shell-no 03
```

The skill:
1. Reads config to get `content_root` and `artist.name`
2. Finds album to determine genre folder
3. Constructs correct path: `{content_root}/artists/{artist}/albums/{genre}/{album}/tracks/`
4. Moves and renames file with track number
5. Confirms the move

**Why use the skill**: It always reads the config file fresh and handles the complex path structure (content_root → artists → artist → albums → genre → album → tracks).

### Importing External Audio Files

**Trigger**: User says "I have audio for track X", "I downloaded track X", or mentions a WAV/audio file in Downloads or another location.

**Use the `/bitwize-music:import-audio` skill:**

```
/bitwize-music:import-audio ~/Downloads/03-t-day-beach.wav shell-no
```

The skill:
1. Reads config to get `audio_root` and `artist.name`
2. Constructs correct path: `{audio_root}/[artist]/[album]/`
3. Creates directory and moves file
4. Confirms the move

**Why use the skill**: It always reads the config file fresh and enforces the correct path structure, preventing the common mistake of omitting the artist folder.

---

## Ready to Generate Checkpoint

**Trigger**: When all track lyrics are written for an album

**Claude should:**
1. Review all track statuses
2. Verify all tracks have:
   - Complete lyrics
   - **Phonetic review complete** (all proper nouns, homographs, acronyms checked)
   - Suno Style Box filled
   - Suno Lyrics Box filled
   - Sources verified (if applicable)
3. Run explicit content check: `/bitwize-music:explicit-checker [album-path]`
4. Run phonetic check on all tracks (scan for names, places, homographs, acronyms)
5. Present summary to user

**Say to user:**
```
✅ ALL LYRICS COMPLETE

Album: [name]
Tracks: [count] tracks written
Explicit: [Yes/No]
Sources: [All verified / X pending]

Ready to begin Suno generation?

Next steps:
1. You'll generate tracks on Suno using the Style/Lyrics boxes
2. Log each attempt in Generation Log
3. Mark tracks as "Generated" when you have keepers

Proceed to generation?
```

---

## Suno Generation Workflow

**Reference:** Use `/bitwize-music:suno-engineer` for technical details, or see `/reference/suno/v5-best-practices.md`

### Generation Process

**For each track:**

1. **Copy inputs from track file**:
   - Style Box → Suno's "Style of Music" field
   - Lyrics Box → Suno's "Lyrics" field

2. **Generate**:
   - Use V5 model (or latest)
   - Generate 2-3 variations initially
   - Listen to results

3. **Log attempt** in track's Generation Log:
   ```markdown
   | 1 | 2026-01-09 | V5 | [Suno URL] | First attempt | — |
   ```

4. **Evaluate**:
   - ✓ **Keeper**: Mark Status `Generated`, add Suno Link to track details
   - ❌ **Not good**: Note issues, refine Style/Lyrics, regenerate

5. **Iterate until satisfied**

### When to Stop Iterating

Stop when track has:
- Correct vocal delivery
- Good pronunciation
- Proper structure (verse/chorus/etc)
- Acceptable audio quality
- Matches intended mood

**Don't chase perfection** - "good enough to release" is the bar.

### Batch vs Sequential

- **Sequential** (recommended): Generate one track, get it right, move to next
- **Batch**: Generate all tracks at once, then iterate on problem tracks

User preference drives approach.

---

## Album Generation Complete Checkpoint

**Trigger**: When all tracks marked `Generated` with Suno Links

**Claude should:**
1. Verify all tracks have Status: `Generated`
2. Verify all Suno Links present and working
3. Check Generation Log - all tracks have keeper marked with ✓

**Say to user:**
```
✅ ALL TRACKS GENERATED

Album: [name]
Tracks: [count] / [count] complete

Track Status:
- Track 01: [title] - ✓ Generated [Suno Link]
- Track 02: [title] - ✓ Generated [Suno Link]
[... list all ...]

Ready for QA review?

Please listen through the full album:
1. Check vocal quality, pronunciation
2. Verify structure (all sections present)
3. Check for audio artifacts or issues
4. Confirm track order flows well

After QA, tell me:
- "Album approved" → Move to mastering
- "Track X needs regen" → We'll fix specific tracks
```

---

## Ready to Master Checkpoint

**Trigger**: User says "album approved" after QA review

**Claude should:**
1. Update all track statuses from `Generated` to `Final`
2. Update album status to `Complete`
3. Verify user has WAV files downloaded from Suno

**Say to user:**
```
✅ ALBUM APPROVED FOR MASTERING

All tracks marked Final. Album status: Complete.

Next step: Audio mastering

Do you have WAV files downloaded from Suno?
- If NO: Download all tracks as WAV (highest quality)
- If YES: Tell me where they're located

I'll set up mastering workflow once files are ready.
```

Then proceed to mastering workflow (which already exists).

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
- [ ] Sheet music generated (optional)
- [ ] Streaming Lyrics filled in each track (if using distributor)
- [ ] SoundCloud metadata filled in
- [ ] For source-based albums:
  - [ ] Human source verification complete (all tracks `✅ Verified`)
  - [ ] RESEARCH.md and SOURCES.md complete
  - [ ] All lyrics verified against sources

---

## Album Art Generation

Generate album art when tracks are complete and you're preparing for release.

### When to Generate Album Art

**Proactive trigger**: When user says "album is done" or you see all tracks marked `Final`, ask: **"Ready to generate the album art?"**

### Workflow

**Step 1: Verify Prompt Exists**
- Album README should have ChatGPT/DALL-E prompt in "Album Art" section
- If missing, use `/bitwize-music:album-art-director` to create prompt

**Step 2: Generate with User**
Since Claude Code cannot directly generate images:

1. **Tell user**: "The album art prompt is ready. I'll copy it for you to use with ChatGPT/DALL-E."
2. **Show the prompt** from the album README
3. **Instruct user**:
   - Open ChatGPT (with DALL-E access) or other image generation tool
   - Paste the prompt
   - Generate image (may need multiple attempts)
   - Download as high-resolution (3000x3000px recommended)

**Step 3: Save to Standard Locations**

Once user has generated and downloaded the image, use the `/bitwize-music:import-art` skill:

```
/bitwize-music:import-art ~/Downloads/album-art.jpg shell-no
```

The skill:
1. Reads config to get `audio_root`, `content_root`, and `artist.name`
2. Copies to audio folder: `{audio_root}/{artist}/{album}/album.png`
3. Copies to content folder: `{content_root}/artists/{artist}/albums/{genre}/{album}/album-art.jpg`

**Why use the skill**: It handles both destinations correctly and always includes the artist folder in the audio path.

**Step 4: Update Checklist**
Mark album art as complete in Album Completion Checklist.

### File Naming Standards

| Location | Filename | Format |
|----------|----------|--------|
| NFS share | `album.png` | PNG for platforms |
| Album directory | `album-art.jpg` or `album-art.png` | Either |

### Troubleshooting

**User doesn't have ChatGPT access:**
- Try other tools: Midjourney, Stable Diffusion, etc.
- Adjust prompt for that tool's syntax

**Need prompt revisions:**
- Use `/bitwize-music:album-art-director` to refine visual concept
- Iterate on prompt based on generation results

---

## Ready to Release Checkpoint

**Trigger**: After mastering complete and album art generated

**Claude should:**
1. Review Album Completion Checklist
2. Verify all items checked
3. Present final status

**Say to user:**
```
✅ ALBUM READY FOR RELEASE

Album Completion Checklist:
- [✓] All tracks marked Final with Suno Links
- [✓] Album art generated and saved
- [✓] Audio mastered (-14 LUFS, -1.0 dBTP)
- [✓] SoundCloud metadata filled in
- [✓] Streaming Lyrics filled in each track
- [✓] For source-based albums:
  - [✓] All sources verified
  - [✓] RESEARCH.md and SOURCES.md complete

Album: [name]
Tracks: [count] tracks
Status: Complete → Ready to Release

Proceed with release?

Next steps:
1. Set release_date and Status: Released in album README
2. Upload to SoundCloud/distributor

Confirm to proceed with release.
```

---

## Releasing an Album

When an album is ready for release:

### 1. Verify Completion Checklist
Ensure all items in Album Completion Checklist are done:
- All tracks Final with Suno Links
- Album art generated and saved
- Audio mastered
- Streaming Lyrics filled in each track (if using distributor)

### 2. Update Album README
In the album's README.md:
1. Set `release_date: YYYY-MM-DD` in YAML frontmatter
2. Set `Status: Released`

### 3. Upload to Platforms
- Upload to SoundCloud and/or distributor
- Add platform URLs back to album README

---

## Post-Release Immediate Actions

**Trigger**: After album status set to `Released`

### Immediate Checklist (Day 1)

**Claude should guide user through:**

1. **SoundCloud Upload**:
   - Upload all mastered tracks
   - Use SoundCloud description from album README
   - Add tags and genre
   - Set explicit flag if needed
   - Copy SoundCloud URLs back to album README

2. **Update Album README**:
   - Add SoundCloud URLs to tracklist
   - Verify `release_date` and `Status: Released` are set

3. **Initial Announcement**:
   - Twitter/X announcement
   - Template:
     ```
     🎵 NEW ALBUM 🎵

     [Album Title]
     [X] tracks | [Genre]

     [Brief description]

     Listen now: [SoundCloud URL]
     ```

4. **Distributor Upload** (if distributing):
   - Upload mastered tracks
   - Copy Streaming Lyrics from each track file
   - Set release date (typically 2-4 weeks out for streaming)
   - Enter metadata (genre, explicit, etc.)

### Next Steps

After immediate actions complete:
- Monitor engagement
- Respond to feedback

### Release Complete Message

**After all release actions complete**, generate and display this message:

**IMPORTANT**: Dynamically generate the tweet URL using the ACTUAL album name:
1. Take the real album name from the album README
2. URL-encode it (spaces become %20, quotes become %22, etc.)
3. Insert into the tweet intent URL
4. Display as a clickable markdown link

**Template** (replace `{ALBUM_NAME}` with actual name, `{URL_ENCODED_NAME}` with URL-encoded version):

```
🎉 ALBUM RELEASED

{ALBUM_NAME} is now live!

---

If you used this plugin to make your album, I'd love to hear about it.

[Click to tweet about your release](https://twitter.com/intent/tweet?text=Just%20released%20%22{URL_ENCODED_NAME}%22%20🎵%20Made%20with%20%40bitwizemusic%27s%20Claude%20AI%20Music%20Skills%20%23ClaudeCode%20%23SunoAI%20%23AIMusic)

Or manually: @bitwizemusic #ClaudeCode #SunoAI #AIMusic

Not required, just curious what people create with this. 🎵
```

---

## Error Recovery Procedures

### Wrong Track Marked Final

If a track was marked `Final` but needs regeneration:

1. Change Status: `Final` → `In Progress`
2. Note reason in Generation Log: "Needs regen - [reason]"
3. Regenerate on Suno
4. Log new attempt
5. When satisfied, mark `Generated` → `Final` again

### Lyrics Need Fixing After Verification

If lyrics have errors after human verification:

1. **DO NOT** change Status from `✅ Verified`
2. Fix lyrics in track file
3. Add note in track file: "Lyrics revised [date] - [reason]"
4. Tell user: "Lyrics updated, please re-verify"
5. After re-verification, update verification date

### Need to Regenerate After Mastering

If a mastered track has issues:

1. Don't delete mastered file - rename: `track.wav` → `track-OLD.wav`
2. Go back to Suno, regenerate
3. Download new WAV
4. Re-master just that track
5. Update Generation Log with notes

### Release Went Wrong

If release has issues after going live:

1. **DO NOT** delete from SoundCloud/platforms
2. If fixable: Generate corrected version, update platforms
3. If major issue: Note in album README: "Version History" section
4. Document what happened and resolution

### Undoing Release (Nuclear Option)

If you absolutely must undo a release:

1. Change Status: `Released` → `Complete`
2. Clear `release_date` field (or add note)
3. Remove from platforms (if possible)
4. Document why in album README

---

## Audio Mastering

Before releasing to streaming platforms, master the audio for loudness consistency and tonal balance.

### How to Request Mastering

Tell Claude: **"Master the tracks in /path/to/folder"**

Claude will:
1. Navigate to the folder
2. Set up the Python environment (if needed)
3. Copy mastering scripts from `tools/mastering/`
4. Analyze all tracks
5. Apply mastering with appropriate settings
6. Report results

**Optional modifiers:**
- "Master with reference /path/to/reference.wav" → Uses reference-based mastering
- "Master for [genre]" → Applies genre-appropriate EQ preset
- "Just analyze" → Runs analysis only, no processing

### When to Master

When the user provides a folder of WAV files (from Suno or elsewhere) and asks to master them for release.

### Quick Workflow

```bash
# One-time setup (shared venv in tools_root)
mkdir -p ~/.bitwize-music
python3 -m venv ~/.bitwize-music/mastering-env
source ~/.bitwize-music/mastering-env/bin/activate
pip install matchering pyloudnorm scipy numpy soundfile

# For each album - run scripts from plugin directory:
source ~/.bitwize-music/mastering-env/bin/activate

# Analyze tracks (pass audio folder path)
python3 {plugin_root}/tools/mastering/analyze_tracks.py {audio_root}/{artist}/{album}/

# Preview mastering (dry run)
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_root}/{artist}/{album}/ --dry-run --cut-highmid -2

# Master with standard settings
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_root}/{artist}/{album}/ --cut-highmid -2

# Verify results (mastered/ subfolder created automatically)
python3 {plugin_root}/tools/mastering/analyze_tracks.py {audio_root}/{artist}/{album}/mastered/
```

**Note**: Scripts stay in plugin directory - never copy them into audio folders.

### Mastering by Genre

Use `--genre` flag for automatic presets:

```bash
python3 master_tracks.py --genre country
python3 master_tracks.py --genre rock
python3 master_tracks.py --genre jazz
```

**Available genres:** 60+ presets including pop, k-pop, hip-hop, trap, drill, rock, punk, metal (thrash, black, doom), electronic, house, techno, ambient, lo-fi, folk, country, jazz, classical, latin, afrobeats, and more. Run `python3 master_tracks.py --help` for the full list.

### Target Settings

- **LUFS**: -14 (streaming standard)
- **True Peak**: -1.0 dBTP
- **Album consistency**: < 1 dB LUFS range across tracks

### Problem Tracks

For tracks that won't reach target LUFS (high dynamic range):

```bash
python3 fix_dynamic_track.py "problem_track.wav"
```

### Full Documentation

See `/reference/mastering/mastering-workflow.md` for complete guide including:
- Detailed analysis interpretation
- Troubleshooting
- Platform-specific targets
- Reference-based mastering with `matchering`

---

## Sheet Music Generation (Optional)

After mastering, optionally create professional sheet music and songbooks.

**External software required:**
- **AnthemScore** ($42 Professional edition) - [lunaverus.com](https://www.lunaverus.com/)
  - Free trial: 30 seconds per song, 100 total transcriptions
- **MuseScore** (Free) - [musescore.org](https://musescore.org/)

**Python dependencies (songbook only):**
```bash
pip install pypdf reportlab pyyaml
```

Use `/bitwize-music:sheet-music-publisher` skill:

```bash
/bitwize-music:sheet-music-publisher shell-no
```

**Guides through:**
1. Setup verification (AnthemScore, MuseScore)
2. Track selection
3. Transcription (automated, ~30-60 sec/track)
4. Polish (optional MuseScore editing)
5. Title cleanup
6. Songbook creation (optional KDP-ready PDF)

**Output:**
```
{audio_root}/{artist}/{album}/sheet-music/
├── 01-track.pdf
├── 01-track.xml (MusicXML source)
├── 02-track.pdf
└── Album_Songbook.pdf (combined)
```

**Good candidates:** Melodic tracks, singer-songwriter, folk, acoustic
**Challenging:** Dense electronic, heavy distortion

**Workflow position:** Generate → Master → **[Sheet Music]** → Release (optional enhancement)

**See also:** `/reference/sheet-music/workflow.md` for complete documentation

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

## Streaming Lyrics Format (for Distributors)

Each track file has a "Streaming Lyrics" section for distributor submission (Spotify, Apple Music, etc.).

**Format rules:**
- Just lyrics (no section labels, no vocalist names, no extra text)
- Write out repeats fully
- Capitalize first letter of each line
- No end punctuation
- Blank lines only between sections
- Don't censor explicit words

Fill in the Streaming Lyrics section in each track file before distributor upload.

---

## Explicit Content Guidelines

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

Note: "damn" alone is clean, but "goddamn" is explicit.

### How to Check

When asked to check for explicit content, or before finalizing an album:

1. Use Grep to scan lyrics for explicit words
2. Report any matches with track name and word count
3. Flag mismatches (explicit content but flag says No, or vice versa)

Example scan:
```
Grep pattern: \b(fuck|shit|bitch|cunt|cock|dick|pussy|asshole|whore|slut)\b
Path: {content_root}/artists/[artist]/albums/[genre]/[album]/tracks/
```

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
