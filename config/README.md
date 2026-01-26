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
  custom_instructions: "~/music-projects/CUSTOM_CLAUDE.md"  # Optional custom workflow instructions
  custom_pronunciation: "~/music-projects/CUSTOM_PRONUNCIATION.md"  # Optional custom phonetic spellings

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
| `paths.custom_instructions` | No | Path to markdown file with custom Claude instructions. Defaults to `{content_root}/CUSTOM_CLAUDE.md` if not set. |
| `paths.custom_pronunciation` | No | Path to markdown file with custom phonetic spellings. Defaults to `{content_root}/CUSTOM_PRONUNCIATION.md` if not set. Merges with base pronunciation guide. |
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

## Custom Instructions

You can provide custom Claude instructions to supplement the base CLAUDE.md workflow:

**Setup:**
1. Set `paths.custom_instructions` in config (or use default)
2. Create the file with your custom instructions:
   ```bash
   touch ~/music-projects/CUSTOM_CLAUDE.md
   ```
3. Add your preferences:
   ```markdown
   # My Custom Workflow Preferences

   - Always ask before creating new albums
   - Prefer aggressive industrial sound for electronic tracks
   - Use British spelling in all documentation
   ```

**When it loads:**
- At session start, Claude reads this file if it exists
- Instructions supplement (don't override) base CLAUDE.md
- If file doesn't exist, no error - it's optional

**Version control:**
- Default location (`~/music-projects/CUSTOM_CLAUDE.md`) can be committed with your content
- Or point to separate repo for shared workflow across projects

## Custom Pronunciation Guide

You can provide custom phonetic spellings to supplement the base pronunciation guide:

**Setup:**
1. Set `paths.custom_pronunciation` in config (or use default)
2. Create the file with your custom pronunciations:
   ```bash
   touch ~/music-projects/CUSTOM_PRONUNCIATION.md
   ```
3. Add your phonetic spellings:
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

**When it loads:**
- At session start, Claude reads this file if it exists
- Merges with base pronunciation guide from `/reference/suno/pronunciation-guide.md`
- Your custom entries take precedence over base guide
- If file doesn't exist, no error - it's optional

**Why separate from base guide:**
- Plugin updates won't overwrite your additions
- Version control your custom pronunciations with your music content
- Share artist-specific pronunciations across projects

**Version control:**
- Default location (`~/music-projects/CUSTOM_PRONUNCIATION.md`) can be committed with your content
- Avoids merge conflicts when plugin updates the base guide
