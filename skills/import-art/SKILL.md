---
name: import-art
description: Place album art in correct audio and content locations
argument-hint: <file-path> <album-name>
model: claude-haiku-4-5-20251001
allowed-tools:
  - Read
  - Bash
  - Glob
---

## Your Task

**Input**: $ARGUMENTS

Import album art to both the audio folder and album content folder.

---

# Import Art Skill

You copy album art to both required locations based on config.

## Step 1: Parse Arguments

Expected format: `<file-path> <album-name>`

Examples:
- `~/Downloads/album-art.jpg shell-no`
- `~/Downloads/cover.png shell-no`

If arguments are missing, ask:
```
Usage: /import-art <file-path> <album-name>

Example: /import-art ~/Downloads/album-art.jpg shell-no
```

## Step 2: Read Config (REQUIRED)

**ALWAYS read the config file first. Never skip this step.**

```bash
cat ~/.bitwize-music/config.yaml
```

Extract:
- `paths.content_root` → The base content directory
- `paths.audio_root` → The base audio directory
- `artist.name` → The artist name (e.g., "bitwize")

## Step 3: Find Album Genre

Search for the album to determine its genre:

```bash
find {content_root}/artists/{artist}/albums -type d -name "{album-name}" 2>/dev/null
```

Extract genre from path (the folder between `albums/` and `{album-name}/`).

If album not found:
```
Error: Album "{album-name}" not found in content directory.
Create it first with: /new-album {album-name} <genre>
```

## Step 4: Construct Target Paths

**TWO destinations required:**

1. **Audio folder** (for platforms/mastering):
   ```
   {audio_root}/{artist}/{album}/album.png
   ```

2. **Content folder** (for documentation):
   ```
   {content_root}/artists/{artist}/albums/{genre}/{album}/album-art.{ext}
   ```

Example with:
- `content_root: ~/bitwize-music`
- `audio_root: ~/bitwize-music/audio`
- `artist: bitwize`
- `genre: electronic`
- `album: shell-no`

Results:
```
Audio:   ~/bitwize-music/audio/bitwize/shell-no/album.png
Content: ~/bitwize-music/artists/bitwize/albums/electronic/shell-no/album-art.jpg
```

**CRITICAL**: Audio path includes artist folder: `{audio_root}/{artist}/{album}/`

## Step 5: Create Directories and Copy Files

```bash
# Create audio directory (includes artist folder!)
mkdir -p {audio_root}/{artist}/{album}

# Copy to audio folder as album.png
cp "{source_file}" "{audio_root}/{artist}/{album}/album.png"

# Copy to content folder preserving extension
cp "{source_file}" "{content_root}/artists/{artist}/albums/{genre}/{album}/album-art.{ext}"
```

## Step 6: Confirm

Report:
```
Album art imported for: {album-name}

Copied to:
1. {audio_root}/{artist}/{album}/album.png (for platforms)
2. {content_root}/artists/{artist}/albums/{genre}/{album}/album-art.{ext} (for docs)
```

## Error Handling

**Source file doesn't exist:**
```
Error: File not found: {source_file}
```

**Config file missing:**
```
Error: Config not found at ~/.bitwize-music/config.yaml
Run /configure to set up.
```

**Album not found:**
```
Error: Album "{album-name}" not found.
Create it first with: /new-album {album-name} <genre>
```

**Not an image file:**
```
Warning: File doesn't appear to be an image: {source_file}
Expected: .jpg, .jpeg, .png, .webp

Continue anyway? (y/n)
```

---

## Examples

```
/import-art ~/Downloads/shell-no-cover.jpg shell-no
```

Config has:
```yaml
paths:
  content_root: ~/bitwize-music
  audio_root: ~/bitwize-music/audio
artist:
  name: bitwize
```

Album found at: `~/bitwize-music/artists/bitwize/albums/electronic/shell-no/`

Result:
```
Album art imported for: shell-no

Copied to:
1. ~/bitwize-music/audio/bitwize/shell-no/album.png (for platforms)
2. ~/bitwize-music/artists/bitwize/albums/electronic/shell-no/album-art.jpg (for docs)
```
