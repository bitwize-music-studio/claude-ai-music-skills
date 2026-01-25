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
