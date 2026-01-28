# How to Customize the Plugin

The override system lets you personalize Claude's behavior without modifying plugin files. Your customizations are stored separately and survive plugin updates.

## Quick Start

```bash
# 1. Create your overrides directory
mkdir -p ~/music-projects/overrides

# 2. Copy any templates you want to customize
cp /path/to/plugin/config/overrides.example/pronunciation-guide.md ~/music-projects/overrides/
cp /path/to/plugin/config/overrides.example/suno-preferences.md ~/music-projects/overrides/

# 3. Edit your copies with your preferences
nano ~/music-projects/overrides/pronunciation-guide.md

# 4. Verify config points to your overrides
# In ~/.bitwize-music/config.yaml:
# paths:
#   overrides: "~/music-projects/overrides"
```

## What Can Be Overridden?

| Override File | What It Controls |
|---------------|------------------|
| `CLAUDE.md` | Workflow instructions, general behavior |
| `pronunciation-guide.md` | Artist/album-specific pronunciations |
| `explicit-words.md` | Custom explicit content word list |
| `lyric-writing-guide.md` | Lyric style, vocabulary, themes |
| `suno-preferences.md` | Genre mappings, vocal preferences |
| `album-planning-guide.md` | Track counts, structure preferences |
| `album-art-preferences.md` | Visual style, color palette |
| `research-preferences.md` | Source priorities, verification standards |
| `release-preferences.md` | QA requirements, platform priorities |
| `mastering-presets.yaml` | Custom genre EQ/dynamics presets |
| `sheet-music-preferences.md` | Page layout, notation preferences |

See [override-index.md](override-index.md) for detailed descriptions of each override.

## When to Use Overrides

### Use overrides when you want to:

- **Establish consistent style** - Define your lyric writing voice, visual aesthetic, or sonic preferences once and have them applied automatically
- **Add artist-specific pronunciations** - Ensure Suno pronounces your artist name, album titles, and character names correctly
- **Customize QA workflows** - Add or skip checks based on your album types
- **Set default genre mappings** - Translate your genre names to Suno-specific tags
- **Define research standards** - Set source priorities and verification requirements for documentary albums

### Don't use overrides when:

- **One-time exceptions** - Just tell Claude in the conversation
- **Album-specific details** - Put these in the album README instead
- **Experimentation** - Try things in conversation first, then codify what works

## How Overrides Work

### Loading Process

1. At session start, Claude reads `~/.bitwize-music/config.yaml`
2. Gets `paths.overrides` (defaults to `{content_root}/overrides`)
3. Checks for each override file
4. If found: loads and merges with base behavior
5. If not found: uses defaults (no error)

### Merge Behavior

Different overrides merge differently:

| Override | Merge Behavior |
|----------|----------------|
| `CLAUDE.md` | **Supplements** base instructions (additive) |
| `pronunciation-guide.md` | **Merges** with base guide, custom takes precedence |
| `explicit-words.md` | **Adds/removes** from base word list |
| `mastering-presets.yaml` | **Overrides** specific genre presets |
| All others | **Adds context** to skill behavior |

### Example: Pronunciation Guide Merging

Base guide (`/reference/suno/pronunciation-guide.md`):
```markdown
| live (verb) | live | lyve | "I live here" |
```

Your override (`{overrides}/pronunciation-guide.md`):
```markdown
| bitwize | bitwize | bit-wize | Artist name |
```

Result: Both entries are available. Your custom pronunciations take precedence if there's a conflict.

## Best Practices

### Start Small

Begin with one or two overrides:
- `pronunciation-guide.md` - Almost always useful
- `CLAUDE.md` - If you have specific workflow preferences

Add more as you discover patterns in your work.

### Be Specific

Good:
```markdown
## Vocabulary
### Avoid
- utilize (use "use" instead)
- commence (use "start" instead)
```

Less useful:
```markdown
## Vocabulary
### Avoid
- boring words
```

### Document Context

Add notes explaining why:
```markdown
## Not Explicit (Override Base)
- hell (context: historical narrative about mining disasters)
- damn (context: period-accurate 1920s dialogue)
```

### Version Control

Commit your overrides with your content:

```bash
# In your content repo's .gitignore
# Don't ignore overrides - commit them
!overrides/
```

This lets you share preferences across machines or collaborate with others.

## Directory Structure

Default location (recommended):
```
~/music-projects/           # {content_root}
├── artists/
├── overrides/              # Your customizations
│   ├── CLAUDE.md
│   ├── pronunciation-guide.md
│   └── suno-preferences.md
└── IDEAS.md
```

Custom location (set in config):
```yaml
# ~/.bitwize-music/config.yaml
paths:
  content_root: "~/music-projects"
  overrides: "~/my-custom-overrides"  # Different location
```

## Troubleshooting

### Override Not Loading

1. Check path in config:
   ```yaml
   paths:
     overrides: "~/music-projects/overrides"
   ```

2. Verify file exists:
   ```bash
   ls ~/music-projects/overrides/
   ```

3. Check file name matches exactly (case-sensitive)

### Unexpected Behavior

If an override seems to have no effect:

1. The skill may not support that specific customization yet
2. Check the override file format matches the example
3. Try restarting the Claude session

### Conflicting Instructions

If your override conflicts with base behavior:

- `CLAUDE.md` supplements (both apply)
- Pronunciation guide: your entries take precedence
- Other overrides: varies by skill

When in doubt, be explicit about what you want in the override.

## See Also

- [override-index.md](override-index.md) - Detailed index of all overrides
- [/config/overrides.example/](../../config/overrides.example/) - Example templates
- [/config/README.md](../../config/README.md) - Configuration reference
