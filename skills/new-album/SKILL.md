---
name: new-album
description: Creates a new album with the correct directory structure and templates. Use IMMEDIATELY when the user says 'make a new album' or similar, before any discussion.
argument-hint: <album-name> <genre>
model: claude-haiku-4-5-20251001
allowed-tools:
  - Read
  - Bash
  - Write
---

## Your Task

**Input**: $ARGUMENTS

Create a new album directory structure with all required files and templates.

---

# New Album Skill

You create the complete album directory structure based on config.

## Step 1: Parse Arguments

Expected formats:
- `<album-name> <genre>` — standard album
- `<album-name> documentary <genre>` — true-story/documentary album (creates RESEARCH.md + SOURCES.md)

Examples:
- `sample-album electronic`
- `my-new-album hip-hop`
- `protest-songs folk`
- `the-heist documentary hip-hop`

Valid genres (primary categories):
- `hip-hop`
- `electronic`
- `rock`
- `folk`
- `country`
- `pop`
- `metal`
- `jazz`
- `rnb`
- `classical`
- `reggae`
- `punk`
- `indie-folk`
- `blues`
- `gospel`
- `latin`
- `k-pop`

**Parsing logic:**
1. If 3 arguments and second is `documentary`: album = arg1, genre = arg3, documentary = true
2. If 2 arguments: album = arg1, genre = arg2, documentary = false
3. If 2 arguments and neither matches a valid genre: ask for clarification
4. If only 1 argument or none: ask the user

**After parsing, if documentary flag was not set, ask:**
"Is this a documentary/true-story album? (This adds research and sources templates.)"

If arguments are missing, ask:
```
Usage: /new-album <album-name> <genre>
       /new-album <album-name> documentary <genre>

Example: /new-album sample-album electronic
         /new-album the-heist documentary hip-hop

Valid genres: hip-hop, electronic, rock, folk, country, pop, metal, jazz, rnb, classical, reggae, punk, indie-folk, blues, gospel, latin, k-pop
```

## Step 2: Read Config (REQUIRED)

**ALWAYS read the config file first. Never skip this step.**

```bash
cat ~/.bitwize-music/config.yaml
```

Extract:
- `paths.content_root` → The base content directory
- `artist.name` → The artist name (e.g., "bitwize")

## Step 3: Determine Plugin Root

Find where the plugin is installed to access templates:

```bash
# Find plugin by looking for CLAUDE.md
find ~ -name "CLAUDE.md" -path "*claude-ai-music-skills*" 2>/dev/null | head -1 | xargs dirname
```

Or if you know the plugin location from context, use that.

## Step 4: Construct Album Path

The album path is **ALWAYS**:

```
{content_root}/artists/{artist}/albums/{genre}/{album-name}/
```

Example with:
- `content_root: ~/bitwize-music`
- `artist: bitwize`
- `genre: electronic`
- `album-name: sample-album`

Result:
```
~/bitwize-music/artists/bitwize/albums/electronic/sample-album/
```

## Step 5: Check Album Doesn't Already Exist

```bash
if [ -d "{album_path}" ]; then
  echo "Album already exists"
fi
```

If exists:
```
Error: Album already exists at {album_path}

To work on this album, just reference it by name.
```

## Step 6: Create Directory Structure

```bash
mkdir -p {album_path}/tracks
mkdir -p {album_path}/promo
```

This creates:
```
{content_root}/artists/{artist}/albums/{genre}/{album-name}/
├── tracks/
└── promo/
```

## Step 7: Copy Templates

Copy templates from plugin directory:

```bash
cp ${CLAUDE_PLUGIN_ROOT}/templates/album.md {album_path}/README.md
cp ${CLAUDE_PLUGIN_ROOT}/templates/promo/*.md {album_path}/promo/
```

For documentary/true-story albums (ask user):
```bash
cp ${CLAUDE_PLUGIN_ROOT}/templates/research.md {album_path}/RESEARCH.md
cp ${CLAUDE_PLUGIN_ROOT}/templates/sources.md {album_path}/SOURCES.md
```

## Step 8: Confirm

Report:
```
Created album: {album-name}
Location: {album_path}

Files created:
- README.md (album template)
- tracks/ (empty, ready for track files)
- promo/ (social media copy templates)

Next steps:
  Option 1 - Interactive (Recommended):
    Run /bitwize-music:album-conceptualizer to design your album concept
    through the 7 Planning Phases.

  Option 2 - Manual:
    1. Edit README.md with your album concept
    2. Create tracks with /import-track or manually in tracks/
```

## Error Handling

**Config file missing:**
```
Error: Config not found at ~/.bitwize-music/config.yaml
Run /configure to set up.
```

**Invalid genre:**
```
Error: Invalid genre "{genre}"

Valid genres: hip-hop, electronic, rock, folk, country, pop, metal, jazz, rnb, classical, reggae, punk, indie-folk, blues, gospel, latin, k-pop
```

**Album already exists:**
```
Error: Album already exists at {album_path}
```

**Templates not found:**
```
Error: Templates not found. Is the plugin installed correctly?
Expected at: ${CLAUDE_PLUGIN_ROOT}/templates/
```

---

## Examples

```
/new-album sample-album electronic
```

Config has:
```yaml
paths:
  content_root: ~/bitwize-music
artist:
  name: bitwize
```

Result:
```
Created album: sample-album
Location: ~/bitwize-music/artists/bitwize/albums/electronic/sample-album/

Files created:
- README.md (album template)
- tracks/ (empty, ready for track files)

Next steps:
  Option 1 - Interactive (Recommended):
    Run /bitwize-music:album-conceptualizer to design your album concept
    through the 7 Planning Phases.

  Option 2 - Manual:
    1. Edit README.md with your album concept
    2. Create tracks with /import-track or manually in tracks/
```

---

## True Story Albums

If user mentions this is a documentary or true-story album:

```
/new-album the-heist documentary hip-hop
```

Also copy research templates:
```bash
cp ${CLAUDE_PLUGIN_ROOT}/templates/research.md {album_path}/RESEARCH.md
cp ${CLAUDE_PLUGIN_ROOT}/templates/sources.md {album_path}/SOURCES.md
```

Report:
```
Created album: the-heist (documentary)
Location: ~/bitwize-music/artists/bitwize/albums/hip-hop/the-heist/

Files created:
- README.md (album template)
- RESEARCH.md (research template)
- SOURCES.md (sources template)
- tracks/ (empty, ready for track files)
```

---

## Common Mistakes

### ❌ Don't: Skip reading config

**Wrong:**
```bash
# Assuming paths
mkdir -p ~/music-projects/artists/...
```

**Right:**
```bash
# Always read config first
cat ~/.bitwize-music/config.yaml
# Use paths.content_root from config
```

### ❌ Don't: Use current working directory

**Wrong:**
```bash
# Create album relative to wherever we are
mkdir -p ./artists/bitwize/albums/...
```

**Right:**
```bash
# Use absolute path from config
mkdir -p {content_root}/artists/{artist}/albums/{genre}/{album-name}/
```

### ❌ Don't: Hardcode artist name

**Wrong:**
```bash
# Assuming artist name
mkdir -p ~/music-projects/artists/bitwize/albums/...
```

**Right:**
```bash
# Read artist.name from config
artist=$(yq '.artist.name' ~/.bitwize-music/config.yaml)
mkdir -p {content_root}/artists/$artist/albums/...
```

### ❌ Don't: Forget path structure

**Wrong paths:**
```
~/music-projects/{album}/           # Missing artists/{artist}/albums/{genre}/
~/music-projects/albums/{album}/    # Missing artists/{artist}/
~/music-projects/{artist}/{album}/  # Missing albums/{genre}/
```

**Correct structure:**
```
{content_root}/artists/{artist}/albums/{genre}/{album-name}/
```

### ❌ Don't: Use wrong genre category

**Wrong:**
```bash
# Using subgenre instead of primary category
/new-album my-album boom-bap        # boom-bap is a subgenre
/new-album my-album trap            # trap is a subgenre
```

**Right:**
```bash
# Use primary genre category
/new-album my-album hip-hop         # boom-bap and trap go in hip-hop
/new-album my-album electronic      # house, techno go in electronic
```

Valid primary genres: `hip-hop`, `electronic`, `rock`, `folk`, `country`, `pop`, `metal`, `jazz`, `rnb`, `classical`, `reggae`, `punk`, `indie-folk`, `blues`, `gospel`, `latin`, `k-pop`
