---
name: import-track
description: Move track markdown files to the correct album location
argument-hint: <file-path> <album-name> [track-number]
model: claude-haiku-4-5-20251001
allowed-tools:
  - Read
  - Bash
  - Glob
---

## Your Task

**Input**: $ARGUMENTS

Import a track markdown file (.md) to the correct album location based on config.

---

# Import Track Skill

You move track markdown files to the correct location in the user's content directory.

## Step 1: Parse Arguments

Expected format: `<file-path> <album-name> [track-number]`

Examples:
- `~/Downloads/track.md shell-no 03`
- `~/Downloads/t-day-beach.md shell-no 03`
- `~/Downloads/03-t-day-beach.md shell-no` (number already in filename)

If arguments are missing, ask:
```
Usage: /import-track <file-path> <album-name> [track-number]

Example: /import-track ~/Downloads/track.md shell-no 03
```

## Step 2: Read Config (REQUIRED)

**ALWAYS read the config file first. Never skip this step.**

```bash
cat ~/.bitwize-music/config.yaml
```

Extract:
- `paths.content_root` → The base content directory
- `artist.name` → The artist name (e.g., "bitwize")

## Step 3: Find Album and Determine Genre

Search for the album directory to find its genre:

```bash
find {content_root}/artists/{artist}/albums -type d -name "{album-name}" 2>/dev/null
```

If album not found:
```
Error: Album "{album-name}" not found.

Available albums:
[list albums found in artists/{artist}/albums/]

Create album first with: /new-album {album-name} <genre>
```

## Step 4: Construct Target Path

The target path is **ALWAYS**:

```
{content_root}/artists/{artist}/albums/{genre}/{album}/tracks/{XX}-{track-name}.md
```

Example with:
- `content_root: ~/bitwize-music`
- `artist: bitwize`
- `genre: electronic` (found from album location)
- `album: shell-no`
- `track-number: 03`
- `track-name: t-day-beach`

Result:
```
~/bitwize-music/artists/bitwize/albums/electronic/shell-no/tracks/03-t-day-beach.md
```

**Track numbering**:
- If track number provided, use it (zero-padded: `03`)
- If filename already has number prefix (e.g., `03-name.md`), preserve it
- If neither, ask user for track number

## Step 5: Move File

```bash
mv "{source_file}" "{target_path}"
```

## Step 6: Confirm

Report:
```
Moved: {source_file}
   To: {target_path}
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

**Track already exists:**
```
Warning: Track already exists at destination.
Overwrite? (The original was not moved)
```

---

## Examples

```
/import-track ~/Downloads/t-day-beach.md shell-no 03
```

Config has:
```yaml
paths:
  content_root: ~/bitwize-music
artist:
  name: bitwize
```

Album found at: `~/bitwize-music/artists/bitwize/albums/electronic/shell-no/`

Result:
```
Moved: ~/Downloads/t-day-beach.md
   To: ~/bitwize-music/artists/bitwize/albums/electronic/shell-no/tracks/03-t-day-beach.md
```
