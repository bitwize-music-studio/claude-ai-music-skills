# Claude AI Music Skills

A complete AI music production workflow for Suno. Install as a Claude Code plugin or clone the repo and start making albums.

> [!WARNING]
> **Early Development** - This is a personal project I built to streamline my own music production workflow with Claude Code and Suno. It's being shared publicly in case others find it useful, but expect rough edges. Bugs are likely. Documentation may be incomplete. Features may change without notice.
>
> If you run into issues, feel free to [open an issue](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues) or just fix it yourself and submit a PR.

> [!WARNING]
> **Claude Code Max plan recommended** ($200/month). This plugin uses 47 specialized skills that spawn subagents across Opus, Sonnet, and Haiku models. Session startup, automatic lyric reviews, multi-agent research workflows, and full album production pipelines are all token-intensive. The standard Pro plan will hit rate limits quickly during any multi-track session.

[![Static Validation](https://github.com/bitwize-music-studio/claude-ai-music-skills/actions/workflows/test.yml/badge.svg)](https://github.com/bitwize-music-studio/claude-ai-music-skills/actions/workflows/test.yml)
[![Model Updater](https://github.com/bitwize-music-studio/claude-ai-music-skills/actions/workflows/model-updater.yml/badge.svg)](https://github.com/bitwize-music-studio/claude-ai-music-skills/actions/workflows/model-updater.yml)
![Version](https://img.shields.io/badge/version-0.53.0-blue)
![Skills](https://img.shields.io/badge/skills-47-green)
![Tests](https://img.shields.io/badge/tests-1884-brightgreen)

## What Is This?

This is a collection of **48 specialized skills** that turn Claude Code into a full music production assistant. It handles everything from album concept development to lyrics, Suno prompts, mastering, and release.

**What you get:**
- Structured workflow from idea to released album
- Lyrics with prosody checks, rhyme analysis, and pronunciation fixes
- Optimized Suno V5 prompts for better generations
- Research tools for documentary/true-story albums
- Audio mastering scripts for streaming platforms
- Quality gates at every stage

---

## What's New

See [CHANGELOG.md](CHANGELOG.md) for full history.

| Version | Highlights |
|---------|------------|
| **0.53** | `check_cross_track_repetition` MCP tool — detect overused words/phrases across album tracks |
| **0.52** | `get_python_command` MCP tool, skills migrated from bare python3 to MCP tools |
| **0.51** | Mirrored path structure for audio/documents, per-track stems subfolders in import-audio |
| **0.50** | Audio QC tool (7 checks), `qc_audio` and `master_album` MCP tools, end-to-end mastering pipeline |
| **0.49** | K-pop genre research with 27 artist deep-dives, artist blocklist, Suno V5 K-pop tips |
| **0.48** | Promo writer skill for social media copy generation, best practices reference, Twitter hashtag fixes |
| **0.47** | 9 processing MCP tools, Suno auto-fill clipboard + Tampermonkey script, album streaming block |
| **0.45** | Promo reviewer skill for social media copy polish, cross-file count consistency fixes |
| **0.43** | MCP server expanded to 30 tools, 160 integration tests, 843 total tests |
| **0.39** | Setup skill with auto dependency detection, improved MCP error handling |
| **0.38** | MCP server for instant state queries, Claude 4.6 upgrade, lyric writer examples |
| **0.37** | Security hardening (6 fixes), prompt quality improvements across 30+ skill/reference files |
| **0.34** | Python 3.9–3.12 CI matrix, bandit/pip-audit security scanning, path traversal fixes |
| **0.33** | Pronunciation table enforcement — table entries must be applied to Suno lyrics |
| **0.29** | Suno verse length limits by genre and BPM across all 67 genres |
| **0.25** | Genre-specific lyric conventions (rhyme schemes, structures) for all 67 genres |
| **0.21** | 46 artist deep-dives, genre keyword indexes for lazy-loading |
| **0.20** | Python logging, progress bars, concurrent processing, 180 tests at 91% coverage |
| **0.18** | State cache layer — fast session startup (2-3 file reads vs 50-220) |
| **0.17** | Test automation, genre INDEX, model strategy docs, 64 quick-start guides |

---

## Behind the Music

Want to know how this project came together? Read the full story:

**[The Story Behind bitwize-music](https://www.bitwizemusic.com/behind-the-music/)**

---

## Share What You Make

Not required, but I'd love to hear what you create with this. Drop a tweet with your album:

**#ClaudeCode #SunoAI #AIMusic [@bitwizemusic](https://x.com/bitwizemusic)**

---

## Installation

```bash
# Add the marketplace
/plugin marketplace add bitwize-music-studio/claude-ai-music-skills

# Install the plugin
/plugin install bitwize-music@claude-ai-music-skills
```

## Requirements

**Platform**: Linux or macOS (Windows users: use WSL)

**Core workflow** (album planning, lyrics, Suno prompts):
- Claude Code
- That's it

**MCP server** (fast state queries, auto-enabled):
- Python 3.10+
- `mcp[cli]>=1.2.0`, `pyyaml` — install with: `pip install --user "mcp[cli]>=1.2.0" pyyaml`

**Audio mastering** (optional):
- Python 3.8+
- pip packages: `matchering`, `pyloudnorm`, `scipy`, `numpy`, `soundfile`

**Document hunting** (optional, for research):
- Python 3.8+
- Playwright (`pip install playwright && playwright install chromium`)

**Install all optional dependencies at once:**
```bash
pip install --user -r requirements.txt
pip install --user -r requirements.txt
playwright install chromium
```

Claude Code will prompt you to install these when needed.

---

## Getting Started Checklist

New to the plugin? Follow these steps to get up and running:

- [ ] **Install the plugin**
  ```bash
  /plugin marketplace add bitwize-music-studio/claude-ai-music-skills
  /plugin install bitwize-music@claude-ai-music-skills
  ```

- [ ] **Run setup assistant** (detects your environment and installs dependencies)
  ```bash
  /bitwize-music:setup
  ```

- [ ] **Configure your workspace**
  ```bash
  /bitwize-music:configure
  ```

- [ ] **Edit config with your settings**
  ```bash
  nano ~/.bitwize-music/config.yaml  # or your preferred editor
  ```

  **Required settings:**
  - `artist.name` - Your artist/project name (e.g., "bitwize", "my-band")
  - `paths.content_root` - Where albums will be stored (e.g., `~/music-projects`)
  - `paths.audio_root` - Where mastered audio goes (e.g., `~/music-projects/audio`)
  - `paths.documents_root` - Where research PDFs go (e.g., `~/music-projects/documents`)

- [ ] **(Optional) Install mastering dependencies**
  ```bash
  pip install matchering pyloudnorm scipy numpy soundfile
  ```
  Only needed if you plan to master audio for streaming platforms.

- [ ] **(Optional) Install document hunter dependencies**
  ```bash
  pip install playwright
  playwright install chromium
  ```
  Only needed if you plan to do research for documentary/true-story albums.

- [ ] **Start Claude Code and begin**
  ```bash
  claude
  ```

  Then say: **"Let's make a new album"**

**That's it!** Claude will create the album directory structure and guide you through the 7 planning phases.

**Next steps:**
- Read the [Tutorial](#tutorial-create-your-album) below for a walkthrough
- Run `/bitwize-music:help` to see all available skills
- Check the [Troubleshooting](#troubleshooting) section if you hit issues

---

## How It Works

### The Workflow

```
┌─────────┐    ┌──────────┐    ┌───────┐    ┌──────────┐    ┌────────┐    ┌─────────┐
│ Concept │ -> │ Research │ -> │ Write │ -> │ Generate │ -> │ Master │ -> │ Release │
└─────────┘    └──────────┘    └───────┘    └──────────┘    └────────┘    └─────────┘
     │              │               │              │              │              │
     v              v               v              v              v              v
 Plan album    Gather sources  Create lyrics  Generate on    Optimize     Upload &
 Define theme  Verify facts    Check quality  Suno V5        audio for    distribute
 Tracklist     Citations       Pronunciation  Iterate        streaming    to platforms
```

Each phase has specialized skills and quality gates:

| Phase | What Happens | Skills Used |
|-------|--------------|-------------|
| **Concept** | Define album theme, tracklist, sonic direction | `/bitwize-music:album-conceptualizer` |
| **Research** | Gather sources (for true-story albums) | `/bitwize-music:researcher`, `/bitwize-music:document-hunter` |
| **Write** | Create lyrics with quality checks | `/bitwize-music:lyric-writer`, `/bitwize-music:pronunciation-specialist` |
| **Generate** | Create tracks on Suno | `/bitwize-music:suno-engineer` |
| **Master** | Optimize audio for streaming | `/bitwize-music:mastering-engineer` |
| **Release** | QA, upload, distribute | `/bitwize-music:release-director` |

### Skills = Specialized Expertise

Skills are invoked with `/bitwize-music:skill-name`. They can be called explicitly or Claude will use them automatically when relevant.

**Example explicit call:**
```
/bitwize-music:lyric-writer Write verse 2 for track 3
```

**Example automatic use:**
When you say "let's write the lyrics for track 1", Claude automatically applies `/bitwize-music:lyric-writer` expertise including rhyme checks, prosody analysis, and pronunciation scanning.

### File Structure

The plugin separates **plugin files** (skills, templates, reference docs) from **your content** (albums, artists). Your content lives in `{content_root}` (configured in `~/.bitwize-music/config.yaml`).

```
{content_root}/                  # Your workspace
└── artists/your-artist/
    ├── README.md                # Artist profile
    └── albums/hip-hop/my-album/ # Album by genre
        ├── README.md            # Album concept, tracklist
        ├── RESEARCH.md          # Sources (if true-story)
        ├── SOURCES.md           # Citations
        └── tracks/
            ├── 01-first-track.md
            ├── 02-second-track.md
            └── ...
```

Set `content_root` in your config to point to your workspace. You can keep it in the plugin folder (with `artists/` gitignored) or set a separate path to keep content independent.

Each track file contains:
- Concept and narrative role
- Full lyrics
- Suno Style Box (copy to Suno's style field)
- Suno Lyrics Box (copy to Suno's lyrics field)
- Generation log

---

## Tutorial: Create Your Album

Let's walk through creating an album from scratch.

### Step 1: Start Planning

**You say:**
> Let's make a new album

**Claude will ask about:**
- Artist (existing or new?)
- Genre and sonic direction
- Album concept and theme
- Track count and structure
- Track concepts (what's each song about?)

### Step 2: Approve the Concept

Claude presents the full plan. Review and confirm:
> Ready to start writing

### Step 3: Write Track 1

**You say:**
> Let's write track 1

Claude drafts lyrics and automatically:
- Checks for repeated rhymes
- Analyzes prosody (stressed syllables on beats)
- Scans for pronunciation risks
- Suggests fixes for any issues

**Review and iterate:**
> The second verse feels weak, can we make it more visual?

### Step 4: Prepare for Suno

Once lyrics are approved, Claude fills in:
- **Style Box**: Genre tags, vocal description, instrumentation
- **Lyrics Box**: Lyrics with section tags and phonetic fixes

**Example Style Box:**
```
[your genre], [vocal style],
[instruments], [mood], [tempo] BPM
```

**Example Lyrics Box:**
```
[Verse 1]
Your lyrics here
With section tags

[Chorus]
Hook goes here
...
```

### Step 5: Generate on Suno

1. Open [suno.com](https://suno.com)
2. Copy Style Box → "Style of Music" field
3. Copy Lyrics Box → "Lyrics" field
4. Generate and listen
5. Tell Claude the result:
   > Track 1 generation 1: vocals too quiet, otherwise good

Claude logs the attempt and suggests prompt adjustments.

### Step 6: Iterate Until Happy

Keep generating until you have a keeper:
> Track 1 is done, this one is perfect: [suno-link]

Claude marks it complete and you move to track 2.

### Step 7: Repeat for All Tracks

Work through each track. Claude maintains context across the full album.

### Step 8: Master the Audio

Download WAV files from Suno, then:
> Master the tracks in ~/Music/your-album/

Claude runs the mastering scripts:
- Analyzes loudness (LUFS)
- Applies EQ and limiting
- Targets -14 LUFS for streaming
- Creates `mastered/` folder with final files

### Step 9: Release

> Release the album

Claude runs the release checklist:
- Verifies all tracks are final
- Prepares streaming lyrics for distributors
- Guides you through SoundCloud/distributor upload
- Updates album status and documentation

**Done!** Your album is live.

---

## Skills Reference

### Core Production

| Skill | Description |
|-------|-------------|
| `/bitwize-music:lyric-writer` | Write/review lyrics with prosody and rhyme checks |
| `/bitwize-music:album-conceptualizer` | Album concepts, tracklist architecture |
| `/bitwize-music:suno-engineer` | Technical Suno V5 prompting |
| `/bitwize-music:pronunciation-specialist` | Prevent Suno mispronunciations |
| `/bitwize-music:album-art-director` | Album artwork concepts and AI art prompts |

### Research & Verification

For documentary or true-story albums:

| Skill | Description |
|-------|-------------|
| `/bitwize-music:researcher` | Coordinates specialized researchers |
| `/bitwize-music:document-hunter` | Automated document search from public archives |
| `/bitwize-music:researchers-legal` | Court documents, indictments |
| `/bitwize-music:researchers-gov` | DOJ/FBI/SEC press releases |
| `/bitwize-music:researchers-journalism` | Investigative articles |
| `/bitwize-music:researchers-tech` | Project histories, changelogs |
| `/bitwize-music:researchers-security` | Malware analysis, CVEs |
| `/bitwize-music:researchers-financial` | SEC filings, market data |
| `/bitwize-music:researchers-historical` | Archives, timelines |
| `/bitwize-music:researchers-biographical` | Personal backgrounds |
| `/bitwize-music:researchers-primary-source` | Subject's own words |
| `/bitwize-music:researchers-verifier` | Quality control, fact-checking |

### Quality Control

| Skill | Description |
|-------|-------------|
| `/bitwize-music:lyric-reviewer` | QC gate before Suno - 9-point checklist |
| `/bitwize-music:explicit-checker` | Scan lyrics for explicit content |
| `/bitwize-music:verify-sources` | Human source verification gate — timestamps and records verification |
| `/bitwize-music:validate-album` | Validate album structure, file locations, content integrity |

### Release & Distribution

| Skill | Description |
|-------|-------------|
| `/bitwize-music:mastering-engineer` | Audio mastering for streaming |
| `/bitwize-music:promo-director` | Generate promo videos for social media |
| `/bitwize-music:promo-reviewer` | Review and polish social media copy before release |
| `/bitwize-music:cloud-uploader` | Upload promo videos to Cloudflare R2 or AWS S3 |
| `/bitwize-music:sheet-music-publisher` | Convert audio to sheet music, create songbooks |
| `/bitwize-music:release-director` | QA, distribution prep |

### Setup & Maintenance

| Skill | Description |
|-------|-------------|
| `/bitwize-music:resume` | Resume work on an album - finds album, shows status and next steps |
| `/bitwize-music:tutorial` | Interactive guided album creation and getting started |
| `/bitwize-music:album-ideas` | Track and manage album ideas — brainstorming, planning, status |
| `/bitwize-music:new-album` | Create album directory structure with templates |
| `/bitwize-music:configure` | Set up or edit plugin configuration |
| `/bitwize-music:import-audio` | Move audio files to correct album location |
| `/bitwize-music:import-track` | Move track .md files to correct album location |
| `/bitwize-music:import-art` | Place album art in audio and content locations |
| `/bitwize-music:clipboard` | Copy track content to clipboard (macOS/Linux/WSL) |
| `/bitwize-music:test` | Run automated tests to validate plugin integrity |
| `/bitwize-music:skill-model-updater` | Update Claude model references |
| `/bitwize-music:help` | Show available skills, workflows, and quick reference |
| `/bitwize-music:about` | About bitwize and this plugin |

---

## Model Strategy

Skills use different Claude models optimized for quality vs cost. On Claude Code Max plans, critical creative outputs use the best models available.

| Model | When Used | Skills |
|-------|-----------|--------|
| **Opus 4.6** | Critical creative outputs (6 skills) | `/bitwize-music:lyric-writer`, `/bitwize-music:suno-engineer`, `/bitwize-music:album-conceptualizer`, `/bitwize-music:lyric-reviewer`, `/bitwize-music:researchers-legal`, `/bitwize-music:researchers-verifier` |
| **Sonnet 4.5** | Reasoning and coordination (25 skills) | `/bitwize-music:researcher`, `/bitwize-music:pronunciation-specialist`, `/bitwize-music:explicit-checker`, and most other skills |
| **Haiku 4.5** | Rule-based operations (15 skills) | `/bitwize-music:validate-album`, `/bitwize-music:test`, imports, clipboard, help |

**Why different models?**
- **Opus 4.6** for lyrics, Suno prompts, album concepts, lyric review, and legal/verification research — these define the final music and have high error cost
- **Sonnet** for planning, research coordination, and most tasks — excellent quality at lower cost
- **Haiku** for mechanical operations (imports, validation, clipboard) where speed matters more than creativity

**Checking models:** Run `/bitwize-music:skill-model-updater check` to verify all skills use current Claude models. The updater can automatically update model references when new versions release.

---

## Tools

All in `tools/`. Python 3.8+ required for optional tools.

| Directory | Purpose | Key Scripts |
|-----------|---------|-------------|
| `mastering/` | Audio mastering for streaming | `master_tracks.py` (genre presets, -14 LUFS), `analyze_tracks.py`, `reference_master.py` |
| `promotion/` | Social media promo videos | `generate_promo_video.py`, `generate_album_sampler.py` |
| `cloud/` | Cloud storage uploads | `upload_to_cloud.py` (R2/S3) |
| `sheet-music/` | Sheet music generation | `transcribe.py` |
| `state/` | State cache for fast session startup | `indexer.py` (rebuild, update, validate, session) |
| `tests/` | Automated test suite | `run_tests.py` (180 tests, 91% coverage) |
| `shared/` | Common utilities | `logging_config.py`, `progress.py` |

---

## Reference Documentation

All in `reference/` (46+ files). Key references:

| Path | Contents |
|------|----------|
| `suno/v5-best-practices.md` | Comprehensive Suno V5 prompting guide |
| `suno/pronunciation-guide.md` | Phonetic spelling for tricky words |
| `suno/structure-tags.md` | Song section tags (`[Verse]`, `[Chorus]`, etc.) |
| `suno/genre-list.md` | 500+ genre tags |
| `suno/voice-tags.md` | Vocal style tags |
| `mastering/mastering-workflow.md` | Full mastering guide |
| `model-strategy.md` | Skill-to-model assignments and rationale |
| `workflows/` | Checkpoint scripts, album planning, source verification, error recovery |
| `promotion/` | Promo video workflow, social media specs |
| `release/` | Platform comparison, distributor guide, metadata |
| `quick-start/` | First album, true-story album, bulk releases |

---

## Templates

Copy these for new content:

| Template | Purpose |
|----------|---------|
| `templates/track.md` | Track structure with Suno inputs |
| `templates/album.md` | Album planning template |
| `templates/artist.md` | Artist profile |
| `templates/genre.md` | Genre documentation |
| `templates/ideas.md` | Album ideas tracking |
| `templates/research.md` | Research documentation |
| `templates/sources.md` | Citation tracking |

---

## Configuration

Config file location: `~/.bitwize-music/config.yaml`

### Settings

| Setting | Purpose | Default |
|---------|---------|---------|
| `artist.name` | Your artist/project name | (required) |
| `artist.genres` | Primary genres | `[]` |
| `paths.content_root` | Where albums/artists are stored | (required) |
| `paths.audio_root` | Where mastered audio goes | (required) |
| `paths.documents_root` | Where PDFs/primary sources go | (required) |
| `urls.soundcloud` | SoundCloud profile URL | (optional) |
| `generation.service` | Music generation service | `suno` |

**Mirrored structure:** `audio_root` and `documents_root` use the same `[artist]/[album]/` structure as `content_root`.

**Tools directory:** `~/.bitwize-music/` also contains the shared mastering venv and cache files.

See `config/README.md` for details.

---

## Tips

### For Better Suno Generations

- Put vocal description FIRST in the style prompt
- Be specific: "raspy male vocals" not just "male vocals"
- Use section tags: `[Verse]`, `[Chorus]`, `[Bridge]`
- Avoid artist names (against Suno TOS) - describe the style instead

### For Better Lyrics

- Watch your rhymes - no self-rhymes, no lazy patterns
- Check prosody - stressed syllables should land on strong beats
- Use phonetic spelling for names: "Rah-mohs" not "Ramos"
- Spell out acronyms: "F-B-I" not "FBI"

### For Documentary Albums

- Capture sources FIRST, write lyrics SECOND
- Human verification required before generation
- Never impersonate - narrator voice only
- Every claim must trace to a captured source

---

## Troubleshooting

### Config Not Found

**Problem:** "Config not found at ~/.bitwize-music/config.yaml"

**Solution:**
```bash
mkdir -p ~/.bitwize-music
cp config/config.example.yaml ~/.bitwize-music/config.yaml
# Edit with your settings
nano ~/.bitwize-music/config.yaml
```

Or use the interactive config tool:
```
/bitwize-music:configure
```

### Album Not Found When Resuming

**Problem:** `/bitwize-music:resume my-album` can't find the album

**Possible causes:**
1. **Wrong album name** - Album names are case-sensitive. Try: `/bitwize-music:resume` (without name) to see all albums
2. **Wrong path in config** - Check `paths.content_root` in `~/.bitwize-music/config.yaml` points to where your albums live
3. **Album in wrong location** - Albums must be in: `{content_root}/artists/{artist}/albums/{genre}/{album}/`

**Debug steps:**
```bash
# Check config
cat ~/.bitwize-music/config.yaml

# List all album READMEs
find ~/your-content-root/artists -name README.md -path "*/albums/*"
```

### Path Resolution Issues

**Problem:** Files created in wrong locations, "path not found" errors

**Common mistakes:**
- Using relative paths instead of reading config
- Forgetting to include artist name in audio/documents paths
- Hardcoding paths instead of using `{content_root}` from config

**The rule:** Always read `~/.bitwize-music/config.yaml` first to get paths. Never assume or hardcode.

**Correct path structure:**
```
{content_root}/artists/{artist}/albums/{genre}/{album}/    # Content
{audio_root}/artists/{artist}/albums/{genre}/{album}/      # Audio (mirrored structure)
{documents_root}/artists/{artist}/albums/{genre}/{album}/  # Documents (mirrored structure)
```

### Python Dependency Issues (Mastering)

**Problem:** Mastering fails with import errors

**Solution:** Install mastering dependencies:
```bash
pip install matchering pyloudnorm scipy numpy soundfile
```

Or use a virtual environment (recommended):
```bash
python3 -m venv ~/.bitwize-music/venv
source ~/.bitwize-music/venv/bin/activate
pip install matchering pyloudnorm scipy numpy soundfile
```

### Playwright Setup (Document Hunter)

**Problem:** `/bitwize-music:document-hunter` fails with browser errors

**Solution:** Install Playwright and browser:
```bash
pip install playwright
playwright install chromium
```

### Plugin Updates Breaking Things

**Problem:** After updating the plugin, things don't work

**Common causes:**
1. **Config schema changed** - Compare your `~/.bitwize-music/config.yaml` with `config/config.example.yaml`
2. **Template changes** - Existing albums may use old template format
3. **Skill renamed or removed** - Check CHANGELOG.md for breaking changes

**Solutions:**
- Backup your config before updating
- Review CHANGELOG.md after updates
- Keep content in separate `content_root` to avoid conflicts

### Skills Not Showing Up

**Problem:** Skills don't appear in `/` menu or can't be invoked

**Check:**
1. Plugin installed correctly: `/plugin list`
2. Skill files exist: `ls ~/.claude/plugins/bitwize-music@claude-ai-music-skills/skills/`
3. Try restarting Claude Code

### Still Stuck?

[Open an issue](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues) with:
- What you tried to do
- What happened (error messages, unexpected behavior)
- Your OS and Claude Code version
- Relevant config (redact personal info)

---

## License

CC0 - Public Domain. Do whatever you want with it.

---

## Contributing

PRs welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for our development workflow and guidelines.

---

## Disclaimer

Artist and song references in the genre documentation are for educational and reference purposes only. This plugin does not encourage creating infringing content. Users are responsible for ensuring their generated content complies with applicable laws and platform terms of service.
