# Configuration

Plugin configuration lives at `~/.bitwize-music/config.yaml` (outside the plugin directory).

## Setup

```bash
# Create config directory
mkdir -p ~/.bitwize-music

# Copy template from plugin
cp config/config.example.yaml ~/.bitwize-music/config.yaml

# Edit with your settings
nano ~/.bitwize-music/config.yaml
```

## Why Outside the Plugin?

When you install via `/plugin install`, the plugin lives in `~/.claude/plugins/`. Putting config in `~/.bitwize-music/` means:

1. **Easy access** - Always at the same location
2. **Survives updates** - Plugin updates don't overwrite your config
3. **Works everywhere** - Same config whether you cloned the repo or installed as plugin

## Config File Reference

### `~/.bitwize-music/config.yaml`

```yaml
# Artist info
artist:
  name: "your-artist-name"
  genres:
    - "electronic"
    - "hip-hop"
  # style: "dark industrial electronic with aggressive vocals"  # Optional

# Paths (all support ~ for home directory)
paths:
  content_root: "~/music-projects"           # Albums, artists, research
  audio_root: "~/music-projects/audio"       # Mastered audio output
  documents_root: "~/music-projects/documents"  # PDFs, primary sources
  overrides: "~/music-projects/overrides"    # Optional overrides directory
  ideas_file: "~/music-projects/IDEAS.md"    # Album ideas tracking file

# Platform URLs
urls:
  soundcloud: "https://soundcloud.com/your-artist"
  # spotify: "https://open.spotify.com/artist/..."
  # bandcamp: "https://your-artist.bandcamp.com"
  # youtube: "https://youtube.com/@your-artist"
  # twitter: "https://x.com/your-artist"

# Generation service
generation:
  service: suno

# Promo videos (optional)
# promotion:
#   default_style: "pulse"      # pulse, bars, line, mirror, etc.
#   duration: 15                # seconds
#   include_sampler: true
#   sampler_clip_duration: 12

# Sheet music (optional)
sheet_music:
  page_size: "letter"           # letter, 9x12, 6x9
  section_headers: false

# Cloud storage (optional)
# cloud:
#   enabled: true
#   provider: "r2"              # r2 or s3
#   r2:
#     account_id: "..."
#     access_key_id: "..."
#     secret_access_key: "..."
#     bucket: "promo-videos"
```

### Path Structure

All paths use a mirrored structure:

```
{content_root}/artists/[artist]/albums/[genre]/[album]/   # Album files
{audio_root}/artists/[artist]/albums/[genre]/[album]/     # Mastered audio
{documents_root}/artists/[artist]/albums/[genre]/[album]/ # PDFs
```

### Tools Directory

The `~/.bitwize-music/` directory also contains:

```
~/.bitwize-music/
├── config.yaml         # Your configuration
├── mastering-env/      # Shared Python venv for mastering
└── cache/              # Future: cache files
```

## Settings Reference

### Core Settings

| Setting | Required | Description |
|---------|----------|-------------|
| `artist.name` | Yes | Your artist/project name |
| `artist.genres` | No | Primary genres (array) |
| `artist.style` | No | Brief style description to help Claude understand your vibe |
| `paths.content_root` | Yes | Where albums and artists live |
| `paths.audio_root` | Yes | Where mastered audio goes |
| `paths.documents_root` | Yes | Where PDFs/sources go |
| `paths.overrides` | No | Directory for override files. Defaults to `{content_root}/overrides` |
| `paths.ideas_file` | No | Album ideas file. Defaults to `{content_root}/IDEAS.md` |
| `urls.soundcloud` | No | SoundCloud profile URL |
| `urls.spotify` | No | Spotify artist URL |
| `urls.bandcamp` | No | Bandcamp URL |
| `urls.youtube` | No | YouTube channel URL |
| `urls.twitter` | No | Twitter/X profile URL |
| `generation.service` | No | Music service (default: `suno`) |

### Promo Videos (`promotion:`)

Settings for `/bitwize-music:promo-director` skill.

| Setting | Required | Description |
|---------|----------|-------------|
| `promotion.default_style` | No | Visualization style: `pulse`, `bars`, `line`, `mirror`, `mountains`, `colorwave`, `neon`, `dual`, `circular` |
| `promotion.duration` | No | Video duration in seconds (default: 15) |
| `promotion.include_sampler` | No | Generate album sampler video (default: true) |
| `promotion.sampler_clip_duration` | No | Seconds per track in sampler (default: 12) |

### Sheet Music (`sheet_music:`)

Settings for `/bitwize-music:sheet-music-publisher` skill.

| Setting | Required | Description |
|---------|----------|-------------|
| `sheet_music.page_size` | No | Page size: `letter`, `9x12`, `6x9` (default: letter) |
| `sheet_music.section_headers` | No | Include [Verse], [Chorus] labels (default: false) |

### Cloud Storage (`cloud:`)

Settings for `/bitwize-music:cloud-uploader` skill. See `/reference/cloud/setup-guide.md` for setup.

| Setting | Required | Description |
|---------|----------|-------------|
| `cloud.enabled` | No | Master switch to enable uploads |
| `cloud.provider` | No | `r2` (Cloudflare R2) or `s3` (AWS S3) |
| `cloud.public_read` | No | Make uploads publicly accessible |
| `cloud.r2.account_id` | If R2 | Cloudflare account ID |
| `cloud.r2.access_key_id` | If R2 | R2 API access key |
| `cloud.r2.secret_access_key` | If R2 | R2 API secret key |
| `cloud.r2.bucket` | If R2 | R2 bucket name |
| `cloud.s3.region` | If S3 | AWS region |
| `cloud.s3.access_key_id` | If S3 | IAM access key |
| `cloud.s3.secret_access_key` | If S3 | IAM secret key |
| `cloud.s3.bucket` | If S3 | S3 bucket name |

### Database (`database:`)

PostgreSQL database for tweet/promo management. Stores social media posts and their publish state.

| Setting | Required | Description |
|---------|----------|-------------|
| `database.enabled` | No | Master switch to enable database tools |
| `database.host` | If enabled | PostgreSQL hostname or IP |
| `database.port` | No | PostgreSQL port (default: 5432) |
| `database.name` | If enabled | Database name |
| `database.user` | If enabled | Database user |
| `database.password` | If enabled | Database password |

## Missing Config

If Claude can't find `~/.bitwize-music/config.yaml`, it will prompt:

```
Config not found. Run:
  mkdir -p ~/.bitwize-music
  cp config/config.example.yaml ~/.bitwize-music/config.yaml
Then edit ~/.bitwize-music/config.yaml with your settings.
```

## Overrides System

The overrides directory lets you customize any skill or workflow without plugin update conflicts.

### How It Works

**Single directory, per-skill files:**
```bash
~/music-projects/overrides/
├── CLAUDE.md                 # Override base workflow instructions
├── pronunciation-guide.md    # Override base pronunciation guide
├── explicit-words.md         # Custom explicit word list (future)
├── lyric-writing-guide.md    # Custom lyric writing preferences (future)
└── mastering-presets.yaml    # Custom mastering settings (future)
```

**Each skill checks for its own override:**
1. Skill reads `~/.bitwize-music/config.yaml` → `paths.overrides`
2. Checks for `{overrides}/[filename].md`
3. If exists: merge with base (or replace, depending on skill)
4. If not exists: use base only (no error)

### Setup

```bash
# Create overrides directory
mkdir -p ~/music-projects/overrides

# Copy examples from the plugin
cp config/overrides.example/pronunciation-guide.md ~/music-projects/overrides/
cp config/overrides.example/suno-preferences.md ~/music-projects/overrides/
# etc.
```

**See `config/overrides.example/` for ready-to-use templates.**

### Available Overrides

#### `CLAUDE.md` - Workflow Instructions
Supplements base CLAUDE.md with your personal workflow preferences.

**Example:**
```markdown
# My Custom Workflow Preferences

- Always ask before creating new albums
- Prefer aggressive industrial sound for electronic tracks
- Use British spelling in all documentation
```

**Behavior:** Loaded at session start, supplements (doesn't override) base instructions.

#### `pronunciation-guide.md` - Phonetic Spellings
Merges with base pronunciation guide for artist-specific terms.

**Example:**
```markdown
# Custom Pronunciation Guide

## Artist-Specific Terms
| Word | Standard | Phonetic | Notes |
|------|----------|----------|-------|
| BitWize | bitwize | Bit-Wize | Artist name |
| SampleAlbum | samplealbum | Sample-Album | Album title |

## Album-Specific Names
| Word | Standard | Phonetic | Notes |
|------|----------|----------|-------|
| Larocca | larocca | Luh-rock-uh | Character name |
| Finnerty | finnerty | Finn-er-tee | Character name |
```

**Behavior:** Loaded by pronunciation-specialist, merged with base guide, custom takes precedence.

#### `explicit-words.md` - Custom Explicit Word List
Add or remove words from the explicit content scanner.

**Example:**
```markdown
# Custom Explicit Words

## Additional Explicit Words
- slang-term-1
- slang-term-2

## Not Explicit (override base list)
- hell (context: historical/literary usage)
- damn (context: emphasis, not profanity)
```

**Behavior:** Loaded by explicit-checker, merged with base list, custom additions/removals applied.

#### `lyric-writing-guide.md` - Lyric Writing Preferences
Custom style guidelines for your lyric writing.

**Example:**
```markdown
# Lyric Writing Guide

## Style Preferences
- Prefer first-person narrative
- Avoid religious imagery
- Use vivid sensory details
- Keep verses 4-6 lines max

## Vocabulary
- Avoid: utilize, commence, endeavor (too formal)
- Prefer: simple, direct language

## Themes
- Focus on: technology, alienation, urban decay
- Avoid: love songs, party anthems
```

**Behavior:** Loaded by lyric-writer, used as additional context when writing lyrics.

#### `suno-preferences.md` - Suno Generation Preferences
Your preferred Suno settings and genre combinations.

**Example:**
```markdown
# Suno Preferences

## Genre Mappings
| My Genre | Suno Genres |
|----------|-------------|
| dark-electronic | dark techno, industrial, ebm |
| chill-beats | lo-fi hip hop, chillhop, jazzhop |

## Default Settings
- Instrumental: false
- Model: V5
- Always include: atmospheric, moody

## Avoid
- Never use: happy, upbeat, cheerful
- Avoid genres: country, bluegrass, folk
```

**Behavior:** Loaded by suno-engineer, used when generating style prompts.

#### `mastering-presets.yaml` - Custom Mastering Presets
Override mastering EQ and dynamics settings.

**Example:**
```yaml
# Custom Mastering Presets

genres:
  dark-electronic:
    cut_highmid: -3  # More aggressive cut
    boost_sub: 2     # More sub bass
    target_lufs: -12 # Louder master

  ambient:
    cut_highmid: -1  # Gentle cut
    boost_sub: 0     # Natural bass
    target_lufs: -16 # Quieter, more dynamic
```

**Behavior:** Loaded by mastering-engineer, overrides default genre presets.

#### `album-planning-guide.md` - Album Planning Preferences
Custom guidelines for album conceptualization.

**Example:**
```markdown
# Album Planning Guide

## Track Count Preferences
- Full album: 10-12 tracks (not 14-16)
- EP: 4-5 tracks

## Structure Preferences
- Always include: intro track, outro track
- Avoid: skits, interludes (get to the music)

## Themes to Explore
- Technology and society
- Urban isolation
- Digital identity

## Themes to Avoid
- Political commentary
- Relationship drama
```

**Behavior:** Loaded by album-conceptualizer, used when planning albums.

#### `album-art-preferences.md` - Album Art Visual Preferences
Your visual style guidelines for album artwork.

**Example:**
```markdown
# Album Art Preferences

## Visual Style Preferences
- Prefer: minimalist, geometric, high contrast
- Avoid: photorealistic, busy compositions, text overlays

## Color Palette Preferences
- Primary: deep blues, purples, blacks
- Accent: neon cyan, electric pink
- Avoid: warm colors, pastels, earth tones

## Composition Preferences
- Always: centered subject, negative space
- Avoid: cluttered backgrounds, multiple focal points
```

**Behavior:** Loaded by album-art-director, applied when developing visual concepts.

#### `research-preferences.md` - Research Standards
Custom research depth and verification requirements.

**Example:**
```markdown
# Research Preferences

## Source Priority
- Tier 1: Court documents, SEC filings, government reports
- Tier 2: Academic research, peer-reviewed journals
- Tier 3: Investigative journalism from trusted outlets

## Verification Standards
- Minimum sources for key facts: 3 (can override to 2 for background)
- Citation format: Academic (APA/Chicago) or legal (Bluebook)

## Research Depth
- Timeline precision: Exact dates required
- Financial detail level: Dollar amounts to nearest thousand
```

**Behavior:** Loaded by researcher, applied to source selection and verification standards.

#### `release-preferences.md` - Release Workflow
Custom QA requirements and platform priorities.

**Example:**
```markdown
# Release Preferences

## QA Requirements
- Additional checks: listen-through on 3 devices, A/B with reference track
- Skip checks: source verification (for non-documentary albums)

## Platform Priorities
- Primary: SoundCloud (always upload first)
- Secondary: Spotify, Apple Music (via DistroKid)

## Metadata Standards
- Artist name format: "bitwize" (lowercase, no capitals)
- Tags: Always include: ai-music, suno, claude-code
```

**Behavior:** Loaded by release-director, applied to QA checklist and platform workflow.

#### `sheet-music-preferences.md` - Sheet Music Formatting
Page layout, notation, and songbook preferences.

**Example:**
```markdown
# Sheet Music Preferences

## Page Layout
- Page size: 9x12 (standard songbook)
- Staff size: 8mm for large print

## Title Formatting
- Include track numbers: no (default)
- Composer credit: "Music by [artist]" below title

## Songbook Settings
- Table of contents: yes (default)
- Cover page style: minimalist (title + artist)
```

**Behavior:** Loaded by sheet-music-publisher, applied to PDF generation and songbook creation.

### Benefits

**For users:**
- **One directory** - All customizations in one place
- **Self-documenting** - File names match what they override
- **Version control** - Commit overrides with your music content
- **No conflicts** - Plugin updates won't overwrite your files
- **Easy discovery** - `ls overrides/` shows what's overrideable

**For skills:**
- **Convention over configuration** - Skills know where to look
- **No config proliferation** - No new config field per customization
- **Future-proof** - New overrides added without touching config

### Version Control

```bash
# .gitignore (in your content repo)
# Commit overrides with your content
!overrides/
```

Default location (`~/music-projects/overrides/`) can be committed with your music content to share preferences across projects.
