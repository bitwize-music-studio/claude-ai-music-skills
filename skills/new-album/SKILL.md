---
name: new-album
description: Create a new album with correct directory structure and templates
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

Expected format: `<album-name> <genre>`

Examples:
- `shell-no electronic`
- `my-new-album hip-hop`
- `protest-songs folk`

Valid genres (primary categories):
- `hip-hop`
- `electronic`
- `country`
- `folk`
- `rock`

If arguments are missing, ask:
```
Usage: /new-album <album-name> <genre>

Example: /new-album shell-no electronic

Valid genres: hip-hop, electronic, country, folk, rock
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
- `album-name: shell-no`

Result:
```
~/bitwize-music/artists/bitwize/albums/electronic/shell-no/
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
```

This creates:
```
{content_root}/artists/{artist}/albums/{genre}/{album-name}/
└── tracks/
```

## Step 7: Copy Templates

Copy templates from plugin directory:

```bash
cp {plugin_root}/templates/album.md {album_path}/README.md
```

For documentary/true-story albums (ask user):
```bash
cp {plugin_root}/templates/research.md {album_path}/RESEARCH.md
cp {plugin_root}/templates/sources.md {album_path}/SOURCES.md
```

## Step 8: Confirm

Report:
```
Created album: {album-name}
Location: {album_path}

Files created:
- README.md (album template)
- tracks/ (empty, ready for track files)

Next steps:
1. Edit README.md with album concept
2. Create tracks with: /import-track or manually in tracks/
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

Valid genres: hip-hop, electronic, country, folk, rock
```

**Album already exists:**
```
Error: Album already exists at {album_path}
```

**Templates not found:**
```
Error: Templates not found. Is the plugin installed correctly?
Expected at: {plugin_root}/templates/
```

---

## Examples

```
/new-album shell-no electronic
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
Created album: shell-no
Location: ~/bitwize-music/artists/bitwize/albums/electronic/shell-no/

Files created:
- README.md (album template)
- tracks/ (empty, ready for track files)

Next steps:
1. Edit README.md with album concept
2. Create tracks with: /import-track or manually in tracks/
```

---

## True Story Albums

If user mentions this is a documentary or true-story album:

```
/new-album the-heist documentary hip-hop
```

Also copy research templates:
```bash
cp {plugin_root}/templates/research.md {album_path}/RESEARCH.md
cp {plugin_root}/templates/sources.md {album_path}/SOURCES.md
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
