---
name: import-audio
description: Moves audio files to the correct album location with proper path structure, or pulls an approved take's WAV and stems straight from Suno. Use when the user has downloaded WAV files from Suno or other sources that need to be organized, or wants to import the keeper after approving a take.
argument-hint: <file-path> <album-name> [track-slug] | --from-suno <album-name> <track> [--stems]
model: sonnet
effort: medium
allowed-tools:
  - Read
  - Bash
  - bitwize-music-mcp
  - mcp__suno__*
---

## Your Task

**Input**: $ARGUMENTS

Import audio to the correct album location based on config — from a local file, or with `--from-suno` straight from Suno through its MCP server.

---

# Import Audio Skill

You put audio in the correct location in the user's audio directory. Two forms:

- **A file on disk** — `<file-path> <album-name> [track-slug]`: Steps 1–5 below.
- **Straight from Suno** — `--from-suno <album-name> <track> [--stems]`: skip to **Importing From Suno**.

## Step 1: Parse Arguments

Expected format: `<file-path> <album-name> [track-slug]`

The `track-slug` is optional — only needed for stems zip imports when the track can't be inferred from the filename.

Examples:
- `~/Downloads/track.wav sample-album`
- `~/Downloads/03-t-day-beach.wav sample-album`
- `~/Downloads/stems.zip sample-album 01-first-taste`

If arguments are missing, ask:
```
Usage: /import-audio <file-path> <album-name> [track-slug]

Examples:
  /import-audio ~/Downloads/track.wav sample-album
  /import-audio ~/Downloads/stems.zip sample-album 01-first-taste
```

## Step 2: Resolve Audio Path via MCP

1. Call `resolve_path("audio", album_slug)` — returns the full audio directory path
2. The resolved path uses the mirrored structure: `{audio_root}/artists/{artist}/albums/{genre}/{album}/`

Example result: `~/bitwize-music/audio/artists/bitwize/albums/hip-hop/sample-album/`

**CRITICAL**: Always use `resolve_path` — never construct paths manually.

## Step 3: Detect File Type

Check the file extension and whether it's a stems zip:

| File Type | Action |
|-----------|--------|
| `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a` | Move to album audio dir (Step 4) |
| `.zip` (stems) | Extract to per-track stems subfolder (Step 4b) |

**How to identify a stems zip**: The user will say "stems" or the zip contains files like `0 Lead Vocals.wav`, `1 Backing Vocals.wav`, etc.

## Step 4: Create Directory and Move File

```bash
mkdir -p {resolved_path}
mv "{source_file}" "{resolved_path}/{filename}"
```

## Step 4b: Import Stems Zip

Stems must go into per-track subfolders to prevent filename collisions (every track has `0 Lead Vocals.wav`, etc.):

```
{resolved_path}/
  01-first-taste.wav
  02-sugar-high.wav
  stems/
    01-first-taste/
      0 Lead Vocals.wav
      1 Backing Vocals.wav
      2 Drums.wav
      ...
    02-sugar-high/
      0 Lead Vocals.wav
      1 Backing Vocals.wav
      ...
```

**Workflow:**

1. **Determine the track slug** from one of:
   - The zip filename if it matches a track pattern (e.g., `01-first-taste-stems.zip` → `01-first-taste`)
   - The user specifying which track (e.g., `/import-audio stems.zip sample-album 01-first-taste`)
   - **If neither**: Ask the user which track the stems belong to
2. **Extract** into the per-track subfolder:
   ```bash
   mkdir -p {resolved_path}/stems/{track-slug}
   unzip "{source_file}" -d "{resolved_path}/stems/{track-slug}"
   ```
3. **Update track metadata**: Call `update_track_field(album_slug, track_slug, "stems", "Yes")`

**Argument format for stems**: `<zip-path> <album-name> [track-slug]`

## Step 5: Confirm

Report:
```
Moved: {source_file}
   To: {resolved_path}/{filename}
```

For stems:
```
Extracted stems: {source_file}
       To: {resolved_path}/stems/{track-slug}/
    Files: {count} stem files extracted
  Updated: {track-slug} stems → Yes
```

## Importing From Suno (`--from-suno`)

Pulls a track's approved take from Suno through the Suno MCP server: the WAV, and with `--stems` the 12 stems. No browser, no Downloads folder.

Costs, limits and the tool notes are in `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md`. In short: the first download of a song uses one Suno download credit; every later download of it, in any format, and of its stems, is free. A take that was played in the terminal with `/bitwize-music:listen` has already used its credit.

### A. Find the keeper

Call `get_suno_import_plan(album_slug, track_slug)`.

| `problems` code | Meaning | Do |
|-----------------|---------|-----|
| *(none)* | `clip_id` is the keeper | Continue |
| `no_keeper` | No take is approved yet | Ask the user to pick one first (`/bitwize-music:listen`), then stop |
| `keeper_ambiguous` | Several takes are marked ✓ and no Suno Link is set | Ask which one, set the Suno Link, then call the plan again |
| `legacy_link` | The Suno Link is a share link from before MCP generation | Explain that it carries no clip id; the file has to be downloaded on suno.com and imported with the file form of this skill. Stop |

If `wav.existing` is set, a file is already imported for this track. Say which file and ask before replacing it.

### B. Check the Suno server

Run § Preflight in the reference doc. If the server is not connected, give the setup command and stop — the file form of this skill still works for a manual download.

### C. Download the WAV

1. Call `audio-download(id: <clip_id>, format: "wav")` **without** `confirm`.

   | Answer | Do |
   |--------|-----|
   | `status: "ok"` | Free — save it (step 2) |
   | `status: "requires_credit"` | Say it uses one download credit and how many are left (`credits_remaining` in the answer). Ask. On yes, call again with `confirm: true` |
   | `status: "processing"` | Call `audio-download` again |
   | `rate_limited` | Wait `retry_after_seconds`, then call again |
   | Any other refusal | Report what Suno said and stop |

2. Save the link to `wav.path`, exactly as the plan gave it:

   ```bash
   mkdir -p "$(dirname "{wav.path}")" \
     && curl -fsSL --max-time 600 -o "{wav.path}.part" "{url}" \
     && mv "{wav.path}.part" "{wav.path}"
   ```

   Quote the URL — it contains `&`. Links last an hour. If `curl` fails, remove the `.part` file and report the error.

3. Call `get_suno_import_plan` again and check that `wav.existing` is now the new file.

### D. Stems (`--stems` only)

1. **State the price and ask.** A 12-part split costs 50 Suno song credits. Show the balance from `account-usage`. If `stems.exists` is true, also say the stems folder already exists and will be overwritten. Stop unless the answer is yes.
2. Call `audio-stems-create(id: <clip_id>, mode: "twelve", idempotency_key: "{album_slug}/{track_slug}/stems/{UTC timestamp}")`. Keep the `id` in the answer (`stemgrp_...`).
3. Call `audio-stems-retrieve(id: <clip_id>, group_id: <that id>)` about every 20 seconds until `status` is no longer `pending` — usually one to two minutes. `partial` means some stems failed: say which, and carry on with the rest.
4. The split returns **two takes** of all 12 parts. Use the stems with `take: 1`, and say that take 2 exists. Never mix the two takes — they are separate renderings and do not sum together.
5. For each take-1 stem, in the order returned, about two seconds apart:
   - `audio-download(id: <the stem's audio_id>, format: "wav")`. It answers `ok` once the song itself has been downloaded (step C did that). Handle `processing` and `rate_limited` as in step C. If it answers `requires_credit`, ask once — that one credit covers the song and every stem.
   - Save the link to `stems.files[<the stem's name>]`, the same way as the WAV. The plan maps Suno's part names (`vocals`, `backing_vocals`, `drums`, ... `fx`) to the file names the mix tools expect.
6. Call `update_track_field(album_slug, track_slug, "stems", "Yes")`.

Import all 12 files, including parts the song does not have: Suno returns those as near-silent stems, and `/bitwize-music:mix-engineer` skips them on its own.

The split also leaves 24 stem songs in the user's Suno library. Mention it once.

### E. Confirm

```
Imported from Suno: [NN] [Title]
   WAV: {wav.path}
 Stems: {stems.dir} (12 files, take 1)
 Spent: 1 download credit, 50 song credits
  Next: /bitwize-music:mix-engineer [album]
```

Leave out the lines that do not apply.

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

Suno allows downloading in both WAV and MP3 formats (WAV on Pro/Premier, web only). **Always prefer WAV** for mastering quality.

**Downloads are metered since 2026-09-03.** Free accounts get 7 lifetime trial downloads (personal use only — never releasable); Pro 20 a month; Premier 60 a month; the count resets on the billing date and does not roll over. **One song is one download whatever the format, and its stems are included** — download the WAV first, then pull stems later at no extra cost; re-downloading the same song is free. Premier's **Suno Studio exports are uncapped** and arrive as 32-bit float / 48 kHz WAV — the practical route for a full album in one month. Commercial rights attach only to a permitted download made on a paid plan.

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
   To: ~/bitwize-music/audio/artists/bitwize/albums/hip-hop/sample-album/03-t-day-beach.wav
```

### Import from Suno example

```
/import-audio --from-suno sample-album 03 --stems
```

Result:
```
Imported from Suno: 03 T-Day Beach
   WAV: ~/bitwize-music/audio/artists/bitwize/albums/hip-hop/sample-album/03-t-day-beach.wav
 Stems: ~/bitwize-music/audio/artists/bitwize/albums/hip-hop/sample-album/stems/03-t-day-beach/ (12 files, take 1)
 Spent: 50 song credits
  Next: /bitwize-music:mix-engineer sample-album
```

### Stems import example

```
/import-audio ~/Downloads/stems.zip sample-album 01-first-taste
```

Result:
```
Extracted stems: ~/Downloads/stems.zip
       To: ~/bitwize-music/audio/artists/bitwize/albums/hip-hop/sample-album/stems/01-first-taste/
    Files: 5 stem files extracted
  Updated: 01-first-taste stems → Yes
```

---

## Common Mistakes

### ❌ Don't: Manually read config and construct paths

**Wrong:**
```bash
cat ~/.bitwize-music/config.yaml
mv file.wav ~/music-projects/audio/artists/bitwize/albums/electronic/sample-album/
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
- Audio: `{audio_root}/artists/{artist}/albums/{genre}/{album}/` (WAV files, stems)
- Documents: `{documents_root}/artists/{artist}/albums/{genre}/{album}/` (PDFs, research)

Use `resolve_path` with the appropriate `path_type` ("content", "audio", "documents") to get the right path.
