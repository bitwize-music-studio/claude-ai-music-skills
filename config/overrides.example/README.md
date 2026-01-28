# Override Examples

This directory contains example templates for all override files. Copy the ones you want to customize to your overrides directory.

## Quick Setup

```bash
# 1. Create your overrides directory (adjust path as needed)
mkdir -p ~/music-projects/overrides

# 2. Copy the examples you want to customize
cp pronunciation-guide.md ~/music-projects/overrides/
cp suno-preferences.md ~/music-projects/overrides/
# ... add more as needed

# 3. Edit your copies
nano ~/music-projects/overrides/pronunciation-guide.md

# 4. Verify config points to your overrides
# In ~/.bitwize-music/config.yaml:
# paths:
#   overrides: "~/music-projects/overrides"
```

## Available Override Files

| File | Purpose | Priority |
|------|---------|----------|
| `CLAUDE.md` | Custom workflow instructions | Start here |
| `pronunciation-guide.md` | Artist/album-specific pronunciations | Essential |
| `explicit-words.md` | Custom explicit word list | As needed |
| `lyric-writing-guide.md` | Lyric style, vocabulary, themes | Recommended |
| `suno-preferences.md` | Genre mappings, vocal preferences | Recommended |
| `album-planning-guide.md` | Track counts, structure preferences | Optional |
| `album-art-preferences.md` | Visual style guidelines | Optional |
| `research-preferences.md` | Source priorities, verification standards | For documentary albums |
| `release-preferences.md` | QA requirements, platform priorities | Optional |
| `mastering-presets.yaml` | Custom genre EQ/dynamics presets | Advanced |
| `sheet-music-preferences.md` | Page layout, notation preferences | Optional |

## Recommended Starting Point

Most users should start with these two:

1. **`pronunciation-guide.md`** - Add your artist name and any album-specific terms
2. **`CLAUDE.md`** - Add any workflow preferences (optional)

Add more overrides as you discover patterns in your work.

## File Descriptions

### CLAUDE.md
Add custom workflow rules that supplement the base instructions. Good for:
- Album/track naming conventions
- Default settings you always want
- Research or generation preferences

### pronunciation-guide.md
Essential for getting Suno to pronounce your artist name, album titles, and character names correctly. The pronunciation specialist skill auto-adds entries when it discovers issues.

### explicit-words.md
Customize the explicit content scanner. Add regional slang or remove words that have non-explicit uses in your content (e.g., "hell" in a historical narrative).

### lyric-writing-guide.md
Define your lyric writing voice: preferred POV, vocabulary to use/avoid, themes to explore, structure preferences. Claude references this when writing or revising lyrics.

### suno-preferences.md
Map your genre names to Suno-specific tags, set default vocal descriptions, and define what to avoid in style prompts.

### album-planning-guide.md
Set default track counts, structure preferences (always include intro, avoid skits), and thematic focus areas.

### album-art-preferences.md
Define your visual style: color palette, composition preferences, what to include/avoid in AI art prompts.

### research-preferences.md
For documentary/true-story albums: set source priorities, verification standards, and research depth requirements.

### release-preferences.md
Customize QA checklists, platform upload order, metadata standards, and release timing.

### mastering-presets.yaml
Override default mastering EQ and dynamics settings for specific genres. YAML format (not Markdown).

### sheet-music-preferences.md
Page layout, notation preferences, and songbook formatting for the sheet music publisher.

## How Overrides Work

1. At session start, Claude checks your overrides directory
2. For each override file found, it's loaded and merged with base behavior
3. Missing files are silently skipped (no error)
4. Your overrides take precedence over base settings

## Tips

- **Start small** - Don't copy all files at once. Add overrides as you need them.
- **Be specific** - Vague preferences don't help. Be concrete.
- **Add context** - Document why you're making each customization.
- **Version control** - Commit overrides with your music content.

## Full Documentation

For complete details on each override, see:
- [/reference/overrides/how-to-customize.md](../../reference/overrides/how-to-customize.md) - Getting started guide
- [/reference/overrides/override-index.md](../../reference/overrides/override-index.md) - Detailed reference for all overrides
