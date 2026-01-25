---
name: import-audio
description: Move audio files to the correct album location
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
- `~/Downloads/track.wav shell-no`
- `~/Downloads/03-t-day-beach.wav shell-no`

If arguments are missing, ask:
```
Usage: /import-audio <file-path> <album-name>

Example: /import-audio ~/Downloads/track.wav shell-no
```

## Step 2: Read Config (REQUIRED)

**ALWAYS read the config file first. Never skip this step.**

```bash
cat ~/.bitwize-music/config.yaml
```

Extract:
- `paths.audio_root` → The base audio directory
- `artist.name` → The artist name (e.g., "bitwize")

## Step 3: Construct Target Path

The target path is **ALWAYS**:

```
{audio_root}/{artist}/{album}/{filename}
```

Example with:
- `audio_root: ~/bitwize-music/audio`
- `artist: bitwize`
- `album: shell-no`
- `file: 03-t-day-beach.wav`

Result:
```
~/bitwize-music/audio/bitwize/shell-no/03-t-day-beach.wav
```

**CRITICAL**: The path MUST include the artist folder. Never put files directly at `{audio_root}/{album}/`.

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

## Examples

```
/import-audio ~/Downloads/03-t-day-beach.wav shell-no
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
   To: ~/bitwize-music/audio/bitwize/shell-no/03-t-day-beach.wav
```
