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

# Paths (all support ~ for home directory)
paths:
  content_root: "~/music-projects"           # Albums, artists, research
  audio_root: "~/music-projects/audio"       # Mastered audio output
  documents_root: "~/music-projects/docs"    # PDFs, primary sources
  overrides: "~/music-projects/overrides"    # Optional overrides directory

# Platform URLs
urls:
  soundcloud: "https://soundcloud.com/your-artist"

# Generation service
generation:
  service: suno
```

### Path Structure

All paths use a mirrored structure:

```
{content_root}/artists/[artist]/albums/[genre]/[album]/   # Album files
{audio_root}/[artist]/[album]/                            # Mastered audio
{documents_root}/[artist]/[album]/                        # PDFs
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

| Setting | Required | Description |
|---------|----------|-------------|
| `artist.name` | Yes | Your artist/project name |
| `artist.genres` | No | Primary genres (array) |
| `paths.content_root` | Yes | Where albums and artists live |
| `paths.audio_root` | Yes | Where mastered audio goes |
| `paths.documents_root` | Yes | Where PDFs/sources go |
| `paths.overrides` | No | Directory containing override files for skills and workflows. Defaults to `{content_root}/overrides` if not set. |
| `urls.soundcloud` | No | SoundCloud profile URL |
| `urls.spotify` | No | Spotify artist URL |
| `urls.bandcamp` | No | Bandcamp URL |
| `generation.service` | No | Music service (default: `suno`) |

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

# Add any override files you want
touch ~/music-projects/overrides/CLAUDE.md
touch ~/music-projects/overrides/pronunciation-guide.md
```

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
| ShellNo | shellno | Shell-No | Album title |

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
