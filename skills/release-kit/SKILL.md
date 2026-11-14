---
name: release-kit
description: Builds everything the DistroKid and SoundCloud upload forms ask for, so uploading an album is pasting, not typing. It makes a page with every field and a copy button, the audio and cover paths, and the checks to clear first. Nothing touches either site. Use when the user is ready to upload an album, says "release kit", "upload sheet", "get it ready for DistroKid" or "what do I paste into SoundCloud".
argument-hint: <album-name>
model: sonnet
effort: low
allowed-tools:
  - Read
  - bitwize-music-mcp
---

## Your Task

**Input**: $ARGUMENTS

Build the album's release kit and open it. The user then fills in the DistroKid and SoundCloud forms from it, and submits them, themselves.

---

# Release Kit Skill

`build_release_kit` writes two files into the album's audio folder, beside `mastered/`:
- `release-kit.html`: every value each upload form asks for, with a copy button, and the checks
- `release-kit.json`: the same data

Every run rebuilds both from the album files and config.

**Never automate either site.** DistroKid's terms bar "any high volume, automated, or electronic means to access the Services (including, without limitation, robots, spiders or scripts)". Don't open, fill or submit either form. The user pastes, uploads and submits.

## Step 1: Find the Album

`find_album(<album-name>)`. If it isn't found, say so and stop.

## Step 2: Build

`build_release_kit(album_slug)`. It opens the page in an iTerm2 pane beside the session when panes work there, and in the default browser otherwise.

- An `error`: show it and stop. That happens for an unknown album, or one with no audio folder yet (master it first).

## Step 3: Report

Lead with what blocks the upload, then the advice:

```
Release kit for Paper Boats: open beside you (iTerm2 pane)
✗ 2 to fix first:
  - Set artist.legal_name in config: DistroKid needs the songwriter's real name
  - album.png is 1400×1400: it must be square, at least 3000×3000
⚠ 1 to look at:
  - Track 4 (Tide) has explicit words but isn't marked explicit
Files: …/release-kit.html
```

With nothing ✗ or ⚠: "Ready: paste from the page into DistroKid and SoundCloud."

## Step 4: Fixes

Offer the fix for each item, and rebuild after any change:

| Check | Fix |
|---|---|
| no mastered WAV, stray WAV | `/bitwize-music:mastering-engineer`; move strays out of `mastered/` |
| cover missing or too small | `/bitwize-music:import-art` |
| `artist.legal_name`, `release.ai_disclosure` | `/bitwize-music:configure`, or edit `~/.bitwize-music/config.yaml`. The AI answer is the user's own statement: ask, never pick |
| release date | the album README's `release_date` |
| titles, explicit flags, Streaming Lyrics | the track files (`/bitwize-music:lyric-writer` for lyrics) |

## Remember

1. **Nothing touches DistroKid or SoundCloud.** The user pastes, uploads and submits.
2. **The AI disclosure is the user's answer.** The kit shows `release.ai_disclosure` exactly as configured.
3. **Rebuild after every fix.** The page is generated, so edit the source, not the page.
4. **The legal name stays out of git.** It lives in config, and the kit lives beside the audio.
