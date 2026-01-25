# Claude AI Music Skills

A complete AI music production workflow for Suno. Install as a Claude Code plugin or clone the repo and start making albums.

> [!WARNING]
> **Early Development** - This is a personal project I built to streamline my own music production workflow with Claude Code and Suno. It's being shared publicly in case others find it useful, but expect rough edges. Bugs are likely. Documentation may be incomplete. Features may change without notice.
>
> If you run into issues, feel free to [open an issue](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues) or just fix it yourself and submit a PR.

## What Is This?

This is a collection of **25 specialized skills** that turn Claude Code into a full music production assistant. It handles everything from album concept development to lyrics, Suno prompts, mastering, and release.

**What you get:**
- Structured workflow from idea to released album
- Lyrics with prosody checks, rhyme analysis, and pronunciation fixes
- Optimized Suno V5 prompts for better generations
- Research tools for documentary/true-story albums
- Audio mastering scripts for streaming platforms
- Quality gates at every stage

---

## Behind the Music

Want to know how this project came together? Read the full story:

https://www.bitwizemusic.com/behind-the-music/

---

## Share What You Make

Not required, but I'd love to hear what you create with this. Drop a tweet with your album:

**[@bitwizemusic](https://x.com/bitwizemusic) #ClaudeCode #SunoAI #AIMusic**

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

**Audio mastering** (optional):
- Python 3.8+
- pip packages: `matchering`, `pyloudnorm`, `scipy`, `numpy`, `soundfile`

**Document hunting** (optional, for research):
- Python 3.8+
- Playwright (`pip install playwright && playwright install chromium`)

Claude Code will prompt you to install these when needed.

---

## Quick Start

### 1. Configure the Plugin

```bash
# Create config directory
mkdir -p ~/.bitwize-music

# Copy config template
cp config/config.example.yaml ~/.bitwize-music/config.yaml

# Edit with your settings
nano ~/.bitwize-music/config.yaml  # or your preferred editor
```

Key settings in `~/.bitwize-music/config.yaml`:
- `artist.name` - Your artist/project name
- `paths.content_root` - Where your albums live (e.g., `~/music-projects`)
- `paths.audio_root` - Where mastered audio goes

### 2. Start Claude Code

```bash
claude
```

### 3. Create Your First Album

Just say: **"Let's plan a new album"**

Claude will walk you through the 7 planning phases before any writing begins.

---

## How It Works

### The Workflow

```
Concept → Research → Write → Generate → Master → Release
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

The plugin separates **plugin files** (skills, templates, reference docs) from **your content** (albums, artists). Your content lives in `{content_root}` (configured in `paths.yaml`).

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

By default, `content_root: "."` keeps everything in the plugin folder (with `artists/` gitignored). Set it to a separate path to keep your content completely independent.

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
| `/bitwize-music:lyric-reviewer` | QC gate before Suno - 8-point checklist |
| `/bitwize-music:explicit-checker` | Scan lyrics for explicit content |

### Release

| Skill | Description |
|-------|-------------|
| `/bitwize-music:mastering-engineer` | Audio mastering for streaming |
| `/bitwize-music:release-director` | QA, distribution prep |

### Setup & Maintenance

| Skill | Description |
|-------|-------------|
| `/bitwize-music:configure` | Set up or edit plugin configuration |
| `/bitwize-music:test` | Run automated tests to validate plugin integrity |
| `/bitwize-music:skill-model-updater` | Update Claude model references |

---

## Tools

### Audio Mastering (`tools/mastering/`)

Python scripts for preparing audio for streaming platforms:

| Script | Purpose |
|--------|---------|
| `analyze_tracks.py` | LUFS/dynamics analysis |
| `master_tracks.py` | Automated mastering with genre presets |
| `fix_dynamic_track.py` | Fix high-dynamic-range tracks |
| `reference_master.py` | Match loudness to reference track |

**Targets:** -14 LUFS, -1.0 dBTP (streaming standard)

---

## Reference Documentation

All in `reference/`:

| Path | Contents |
|------|----------|
| `suno/v5-best-practices.md` | Comprehensive Suno V5 prompting guide |
| `suno/pronunciation-guide.md` | Phonetic spelling for tricky words |
| `suno/structure-tags.md` | Song section tags (`[Verse]`, `[Chorus]`, etc.) |
| `suno/genre-list.md` | 500+ genre tags |
| `suno/voice-tags.md` | Vocal style tags |
| `mastering/mastering-workflow.md` | Full mastering guide |

---

## Templates

Copy these for new content:

| Template | Purpose |
|----------|---------|
| `templates/track.md` | Track structure with Suno inputs |
| `templates/album.md` | Album planning template |
| `templates/artist.md` | Artist profile |
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

## License

CC0 - Public Domain. Do whatever you want with it.

---

## Contributing

PRs welcome. See the skills in `skills/` for examples of the format.

---

## Disclaimer

Artist and song references in the genre documentation are for educational and reference purposes only. This plugin does not encourage creating infringing content. Users are responsible for ensuring their generated content complies with applicable laws and platform terms of service.
