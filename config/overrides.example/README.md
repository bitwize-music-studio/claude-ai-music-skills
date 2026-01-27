# Override Files

Override files let you customize skill behavior without editing plugin files.

## Setup

1. Create your overrides directory:
   ```bash
   mkdir -p ~/music-projects/overrides
   ```

2. Copy the examples you want to customize:
   ```bash
   cp config/overrides.example/pronunciation-guide.md ~/music-projects/overrides/
   cp config/overrides.example/suno-preferences.md ~/music-projects/overrides/
   # etc.
   ```

3. Verify your config points to the right location:
   ```yaml
   # ~/.bitwize-music/config.yaml
   paths:
     overrides: "~/music-projects/overrides"
   ```

## Available Override Files

All files below have examples in this directory.

| File | Used By | Purpose |
|------|---------|---------|
| `CLAUDE.md` | Main workflow | Custom workflow instructions |
| `pronunciation-guide.md` | `/pronunciation-specialist` | Artist/album-specific pronunciations |
| `explicit-words.md` | `/explicit-checker` | Custom explicit word list |
| `suno-preferences.md` | `/suno-engineer` | Genre mappings, defaults, avoidances |
| `lyric-writing-guide.md` | `/lyric-writer` | Style preferences, vocabulary, themes |
| `album-planning-guide.md` | `/album-conceptualizer` | Planning preferences |
| `album-art-preferences.md` | `/album-art-director` | Visual style preferences |
| `research-preferences.md` | `/researcher` | Research workflow preferences |
| `release-preferences.md` | `/release-director` | Release workflow preferences |
| `mastering-presets.yaml` | `/mastering-engineer` | Custom genre presets (YAML format) |
| `sheet-music-preferences.md` | `/sheet-music-publisher` | Sheet music preferences |

## How Overrides Work

1. Skill checks for override file at startup
2. If found, loads and merges with base behavior
3. Override settings take precedence
4. If not found, skill uses defaults (no error)

## Tips

- Start with one or two overrides, add more as needed
- Override files are version-controlled with your content
- Plugin updates won't overwrite your overrides
- Each file has a specific format - see examples
