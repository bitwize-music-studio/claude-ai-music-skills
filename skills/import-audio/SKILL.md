---
name: import-audio
description: Moves audio files to the correct album location with proper path structure. Use when the user has downloaded WAV files from Suno or other sources that need to be organized.
argument-hint: <file-path> <album-name>
model: claude-haiku-4-5-20251001
allowed-tools:
  - Read
  - Bash
---

## Your Task

**Input**: $ARGUMENTS

Import an audio file (WAV, MP3, etc.) to the correct album location based on config.

---

# Import Audio Skill

You move audio files to the correct location in the user's audio directory.

## Step 1: Parse Arguments

Expected format: `<file-path> <album-name>`

Examples:
- `~/Downloads/track.wav sample-album`
- `~/Downloads/03-t-day-beach.wav sample-album`

If arguments are missing, ask:
```
Usage: /import-audio <file-path> <album-name>

Example: /import-audio ~/Downloads/track.wav sample-album
```

## Step 2: Resolve Audio Path via MCP

1. Call `resolve_path("audio", album_slug)` — returns the full audio directory path including artist folder
2. The resolved path is **ALWAYS**: `{audio_root}/{artist}/{album}/`

Example result: `~/bitwize-music/audio/bitwize/sample-album/`

**CRITICAL**: The path MUST include the artist folder. `resolve_path` handles this automatically.

## Step 4: Create Directory and Move File

```bash
mkdir -p {audio_root}/{artist}/{album}
mv "{source_file}" "{audio_root}/{artist}/{album}/{filename}"
```

## Step 5: Confirm

Report:
```
Moved: {source_file}
   To: {audio_root}/{artist}/{album}/{filename}
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

**File already exists at destination:**
```
Warning: File already exists at destination.
Overwrite? (The original was not moved)
```

---

## MP3 Files

Suno allows downloading in both WAV and MP3 formats. **Always prefer WAV** for mastering quality.

**If the user provides an MP3 file:**

1. Accept the MP3 and import it normally (same path logic)
2. Warn the user:
```
Note: This is an MP3 file. For best mastering results, download the WAV
version from Suno instead. MP3 compression removes audio data that can't
be recovered during mastering.

If WAV isn't available, this MP3 will work but mastering quality may be limited.
```

3. Import the file to the same destination path as WAV files

**Supported formats:** WAV (preferred), MP3, FLAC, OGG, M4A

---

## Examples

```
/import-audio ~/Downloads/03-t-day-beach.wav sample-album
```

Config has:
```yaml
paths:
  audio_root: ~/bitwize-music/audio
artist:
  name: bitwize
```

Result:
```
Moved: ~/Downloads/03-t-day-beach.wav
   To: ~/bitwize-music/audio/bitwize/sample-album/03-t-day-beach.wav
```

---

## Common Mistakes

### ❌ Don't: Manually read config and construct paths

**Wrong:**
```bash
cat ~/.bitwize-music/config.yaml
mv file.wav ~/music-projects/audio/bitwize/sample-album/
```

**Right:**
```
# Use MCP to resolve the correct path
resolve_path("audio", album_slug) → returns full path with artist folder
```

**Why it matters:** `resolve_path` reads config, resolves variables, and includes the artist folder automatically. No manual config parsing or path construction needed.

### ❌ Don't: Mix up content_root and audio_root

**Path comparison:**
- Content: `{content_root}/artists/{artist}/albums/{genre}/{album}/` (markdown, lyrics)
- Audio: `{audio_root}/{artist}/{album}/` (WAV files, flattened structure)
- Documents: `{documents_root}/{artist}/{album}/` (PDFs, research)

Use `resolve_path` with the appropriate `path_type` ("content", "audio", "documents") to get the right path.
