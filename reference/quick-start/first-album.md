# Quick Start: Your First Album

Complete guide for creating your first album from scratch.

**Time estimate**: 2-4 hours for a 6-track EP

---

## Prerequisites

Before you begin:

1. **Suno account** - Sign up at [suno.com](https://suno.com)
2. **Claude Code** - With this plugin installed
3. **Config file** - Run `/bitwize-music:configure` if not set up

---

## Phase 1: Setup (5 minutes)

### Step 1: Create the Album

```
/bitwize-music:new-album my-first-album electronic
```

Replace `my-first-album` with your album name (use hyphens, lowercase).

Valid genres: `hip-hop`, `electronic`, `country`, `folk`, `rock`

### Step 2: Verify Creation

The skill reports the album location and creates:
- `README.md` (album template)
- `tracks/` folder (empty)

---

## Phase 2: Planning (30-60 minutes)

Work through the 7 Planning Phases with Claude. Answer one question at a time.

### The 7 Phases

| Phase | What You'll Define |
|-------|-------------------|
| 1. Foundation | Artist, genre, track count |
| 2. Concept | Theme, story, emotional core |
| 3. Sonic Direction | Sound references, mood, production style |
| 4. Structure | Tracklist with brief concepts per track |
| 5. Album Art | Visual concept (generated later) |
| 6. Practical | Titles, explicit content, distributor genres |
| 7. Confirmation | Review plan, confirm "ready to write" |

**Reference**: See [CLAUDE.md > Building a New Album](../../CLAUDE.md#building-a-new-album)

### CHECKPOINT: Do Not Skip Planning

Stop here until:
- [ ] All 7 phases answered
- [ ] You said "ready to start writing"
- [ ] Album README has your concept documented

---

## Phase 3: Writing Lyrics (1-2 hours)

### Step 1: Create Track Files

For each track:
```
Create track 01-intro.md for me
```

Or use the import skill if you've written tracks elsewhere.

### Step 2: Write Lyrics

For each track, Claude helps you write:
- Lyrics with section tags (`[Verse]`, `[Chorus]`, etc.)
- Style prompt for Suno
- Phonetic fixes for tricky words

**Tip**: Use `/bitwize-music:lyric-writer` for dedicated lyric help.

### Step 3: Review Before Generation

After all lyrics are written:
```
Run lyric review on all tracks
```

This catches:
- Pronunciation risks
- Prosody problems
- Rhyme issues
- Missing section tags

### CHECKPOINT: Ready to Generate

Stop here until:
- [ ] All track files created with lyrics
- [ ] Style prompts filled in
- [ ] Lyric review complete (no issues)
- [ ] `/bitwize-music:explicit-checker` run (if needed)

---

## Phase 4: Suno Generation (1-2 hours)

### Step 1: Copy to Suno

For each track:
1. Tell Claude: "Copy track 01 to clipboard"
2. Open Suno, paste into Custom mode
3. Generate 2-3 variations

### Step 2: Log Results

After each generation, tell Claude:
```
Track 01 attempt 1: [paste Suno link]
Good vocals but structure off
```

Claude logs it in the track's Generation Log.

### Step 3: Find Keepers

When you find a keeper:
```
Track 01 keeper: [paste Suno link]
```

Claude marks the track as `Generated`.

### Generation Tips

- **Sequential approach**: Finish one track before starting next
- **Don't chase perfection**: Good enough is good enough
- **Pronunciation issues?** Adjust phonetic spellings, regenerate

### CHECKPOINT: All Tracks Generated

Stop here until:
- [ ] All tracks have Status: `Generated`
- [ ] All tracks have Suno Links
- [ ] You've listened through the full album
- [ ] Tell Claude: "Album QA approved" or "Track X needs regen"

---

## Phase 5: Mastering (30 minutes)

### Step 1: Download WAVs

From Suno, download all keeper tracks as WAV files.

### Step 2: Run Mastering

Tell Claude where the files are:
```
Master the tracks in ~/Downloads/my-album-wavs/
```

Claude runs the mastering workflow:
- Analyzes loudness
- Applies genre-appropriate EQ
- Normalizes to streaming standards (-14 LUFS)

**Reference**: See [mastering-workflow.md](../mastering/mastering-workflow.md)

---

## Phase 6: Album Art (15 minutes)

### Step 1: Get Art Prompt

```
/bitwize-music:album-art-director my-first-album
```

### Step 2: Generate Image

Use ChatGPT/DALL-E with the prompt Claude provides.

### Step 3: Import Art

```
/bitwize-music:import-art ~/Downloads/album-art.png my-first-album
```

---

## Phase 7: Release

### Step 1: Final Checklist

Ask Claude: "Run release checklist"

Verify:
- [ ] All tracks Final
- [ ] Album art saved
- [ ] Audio mastered
- [ ] Metadata filled in

### Step 2: Release

Tell Claude: "Release the album"

Claude updates status to `Released` and provides upload instructions.

### Step 3: Upload

- **SoundCloud**: Upload tracks, add metadata
- **Distributor** (optional): Upload for streaming platforms

---

## Quick Reference: Key Commands

| Task | Command |
|------|---------|
| Create album | `/bitwize-music:new-album name genre` |
| Resume work | `/bitwize-music:resume album-name` |
| Write lyrics | `/bitwize-music:lyric-writer` |
| Review lyrics | `/bitwize-music:lyric-reviewer` |
| Check explicit | `/bitwize-music:explicit-checker` |
| Copy to clipboard | `/bitwize-music:clipboard track-name` |
| Create album art | `/bitwize-music:album-art-director` |
| Import art | `/bitwize-music:import-art path album` |
| Validate album | `/bitwize-music:validate-album` |

---

## Troubleshooting

**Suno mispronounces words?**
- Use phonetic spelling in lyrics
- Run `/bitwize-music:pronunciation-specialist`

**Lost track of progress?**
- Run `/bitwize-music:resume album-name`

**Config issues?**
- Run `/bitwize-music:configure`

**Need more guidance?**
- Run `/bitwize-music:tutorial new-album` for step-by-step walkthrough
