# Importing Audio Files

This document covers procedures for importing audio files (WAV, MP3) from Suno to the correct album location.

## When to Use

**Trigger**: User has WAV files from Suno in Downloads folder, ready to move to album location.

**Common scenarios:**
- Downloaded final track from Suno after generation
- Multiple keeper tracks ready for mastering
- Re-downloaded track after regeneration

## Required Path Structure

Audio files MUST go to:

```
{audio_root}/artists/{artist}/albums/{genre}/{album}/
```

**CRITICAL**: The path MUST use the full mirrored structure: `artists/{artist}/albums/{genre}/{album}/`.

### Path Comparison

| Type | Path Structure | Example |
|------|----------------|---------|
| Audio | `{audio_root}/artists/{artist}/albums/{genre}/{album}/` | `~/music/audio/artists/bitwize/albums/electronic/sample-album/` |
| Content | `{content_root}/artists/{artist}/albums/{genre}/{album}/` | `~/music/artists/bitwize/albums/electronic/sample-album/` |

Note: Audio and content paths both use the mirrored structure with artist and genre folders.

## Step-by-Step Process

### Step 1: Use the Import Skill

**Recommended**: Use `/bitwize-music:import-audio` skill:

```
/bitwize-music:import-audio ~/Downloads/03-t-day-beach.wav sample-album
```

The skill automatically:
1. Reads config to get `audio_root` and `artist.name`
2. Constructs correct path with artist folder
3. Creates directory if needed
4. Moves file to destination

### Step 2: Verify Location

After import, verify with:

```bash
ls {audio_root}/artists/{artist}/albums/{genre}/{album}/
```

Expected output shows your file in the correct location.

## Examples

### Correct Import

**Config:**
```yaml
paths:
  audio_root: ~/bitwize-music/audio
artist:
  name: bitwize
```

**Command:**
```
/bitwize-music:import-audio ~/Downloads/03-t-day-beach.wav sample-album
```

**Result:**
```
Moved: ~/Downloads/03-t-day-beach.wav
   To: ~/bitwize-music/audio/artists/bitwize/albums/electronic/sample-album/03-t-day-beach.wav
```

### Correct vs Incorrect Paths

| Status | Path |
|--------|------|
| CORRECT | `~/bitwize-music/audio/artists/bitwize/albums/electronic/sample-album/03-track.wav` |
| WRONG | `~/bitwize-music/audio/sample-album/03-track.wav` |
| WRONG | `~/bitwize-music/artists/bitwize/albums/electronic/sample-album/03-track.wav` |
| WRONG | `./audio/sample-album/03-track.wav` |

## Common Mistakes

### Forgetting the Artist Folder

**This is the most common mistake.**

Wrong:
```
{audio_root}/{album}/file.wav
~/bitwize-music/audio/sample-album/03-track.wav
```

Correct:
```
{audio_root}/artists/{artist}/albums/{genre}/{album}/file.wav
~/bitwize-music/audio/artists/bitwize/albums/electronic/sample-album/03-track.wav
```

**Why it matters:** Mastering scripts and other tools expect the full mirrored path. Missing segments breaks the workflow.

### Skipping Config Read

Wrong:
```bash
# Assuming paths
mv file.wav ~/music-projects/audio/artists/bitwize/albums/electronic/sample-album/
```

Correct:
```bash
# Always read config first
cat ~/.bitwize-music/config.yaml
# Use paths.audio_root from config
```

**Why it matters:** If `audio_root` differs from your assumption, files end up in the wrong place.

### Using Content Path for Audio

Wrong:
```
{content_root}/artists/{artist}/albums/{genre}/{album}/track.wav
```

Correct:
```
{audio_root}/artists/{artist}/albums/{genre}/{album}/track.wav
```

**Why it matters:** Content root is for markdown files (lyrics, track docs). Audio root is for WAV/MP3 files. Both use the same mirrored structure but serve different purposes.

### Manual Move Without Config

Wrong:
```bash
mv ~/Downloads/track.wav ./sample-album/
```

Correct:
```
/bitwize-music:import-audio ~/Downloads/track.wav sample-album
```

**Why it matters:** The skill reads config fresh, ensuring correct paths even after context changes.

## Verification Checklist

After importing, verify:

- [ ] File exists at `{audio_root}/artists/{artist}/albums/{genre}/{album}/filename.wav`
- [ ] Path includes artist folder (not directly under audio_root)
- [ ] File is NOT in content directory (where markdown lives)
- [ ] File is NOT in current working directory

## Troubleshooting

### File Not Found Error

```
Error: File not found: ~/Downloads/track.wav
```

**Solution:** Verify exact filename and path. Check Downloads folder for actual filename (Suno adds IDs).

### Config Missing Error

```
Error: Config not found at ~/.bitwize-music/config.yaml
```

**Solution:** Run `/bitwize-music:configure` to set up config.

### Destination Already Exists

```
Warning: File already exists at destination.
```

**Solution:** Either:
- Rename existing file (e.g., `track-OLD.wav`)
- Confirm overwrite if replacing with newer version
- Check if you're importing a duplicate

## Bulk Import

For multiple files from the same album:

```
/bitwize-music:import-audio ~/Downloads/01-track.wav sample-album
/bitwize-music:import-audio ~/Downloads/02-track.wav sample-album
/bitwize-music:import-audio ~/Downloads/03-track.wav sample-album
```

Or tell Claude: "Import all WAV files from Downloads to sample-album album"
