# Quick Start: Bulk Releases

How to efficiently create multiple albums. Best practices for high-volume production.

**Use case**: You want to release several albums in a short timeframe.

---

## Strategy Overview

### Sequential vs Parallel

| Approach | When to Use |
|----------|-------------|
| **Sequential** | First 2-3 albums. Learn the workflow. |
| **Parallel planning** | Plan multiple albums, write one at a time. |
| **Batch generation** | Generate all tracks for one album in one session. |
| **Pipeline** | Advanced: Different albums at different phases. |

**Recommendation**: Start sequential until you're comfortable, then move to parallel planning.

---

## Phase 1: Batch Planning

Plan multiple albums before writing any lyrics.

### Step 1: Collect Ideas

```
/bitwize-music:album-ideas list
```

Review your backlog. Select 3-5 albums to plan.

### Step 2: Create All Album Structures

```
/bitwize-music:new-album album-one electronic
/bitwize-music:new-album album-two hip-hop
/bitwize-music:new-album album-three folk
```

### Step 3: Plan Each Album

Work through 7 Planning Phases for each album.

**Time-saving tip**: Keep notes in a separate document while planning, then populate READMEs in batch.

### CHECKPOINT: All Albums Planned

Before writing any lyrics:
- [ ] All album structures created
- [ ] All 7 phases complete for each album
- [ ] All album READMEs populated
- [ ] Research needs identified (for true-story albums)

---

## Phase 2: Batch Research (If Applicable)

For true-story albums, research before writing.

### Parallel Research

If multiple albums need research:
1. Start research on all topics
2. Let document searches run
3. Compile findings album by album
4. Human verification can happen in parallel

**Reference**: See [true-story-album.md](true-story-album.md#phase-3-research-1-3-hours)

### CHECKPOINT: All Research Complete

For each true-story album:
- [ ] RESEARCH.md populated
- [ ] SOURCES.md complete
- [ ] Human verification done

---

## Phase 3: Writing Strategy

### Option A: Album-by-Album (Recommended)

Write all tracks for one album before moving to the next.

**Advantages**:
- Consistent voice/style per album
- Easier to track progress
- Can release as you complete

### Option B: Track Type Batching

Write similar tracks across albums together.

**Example**:
1. Write all intros across albums
2. Write all closers
3. Fill in middles

**Advantages**:
- Gets you in a groove for similar content
- Useful if albums share themes

### Efficient Writing Tips

1. **Use clipboard skill** - `/bitwize-music:clipboard` for quick Suno pasting
2. **Template reuse** - Similar albums can share style prompt structures
3. **Pronunciation batch** - Run `/bitwize-music:pronunciation-specialist` on all albums at once

---

## Phase 4: Batch Generation

### Session Planning

Plan your Suno sessions by album:

```
Session 1: Album One (6 tracks)
Session 2: Album Two (8 tracks)
Session 3: Album Three (10 tracks)
```

### Efficient Generation Flow

For each album session:

1. **Prep**: Copy all style prompts to a notes file
2. **Generate**: Work through tracks sequentially
3. **Log immediately**: Tell Claude each result as you go
4. **Mark keepers**: Update status as you find keepers

### Batch Logging Example

```
Album one, track 01: [link] - keeper
Album one, track 02: [link] - good but regen verse 2
Album one, track 02 attempt 2: [link] - keeper
Album one, track 03: [link] - keeper
...
```

### CHECKPOINT: Generation Complete

For each album:
- [ ] All tracks have keepers
- [ ] All Suno links logged
- [ ] QA listening done

---

## Phase 5: Batch Mastering

### Organize WAV Downloads

Create a clear folder structure:

```
~/Downloads/bulk-master/
  album-one/
    01-track.wav
    02-track.wav
  album-two/
    01-track.wav
    ...
  album-three/
    ...
```

### Master Album by Album

```
Master the tracks in ~/Downloads/bulk-master/album-one/
```

Repeat for each album.

### Verify All Masters

Check each album's mastered output:
- Loudness normalized
- No clipping
- Consistent levels across tracks

---

## Phase 6: Batch Album Art

### Option A: Generate Sequentially

```
/bitwize-music:album-art-director album-one
# Generate in ChatGPT
/bitwize-music:import-art ~/Downloads/art1.png album-one

/bitwize-music:album-art-director album-two
# Generate in ChatGPT
/bitwize-music:import-art ~/Downloads/art2.png album-two
```

### Option B: Batch Prompts

Get all prompts first, then generate images in one ChatGPT session:

1. Get all art prompts
2. Generate all images in ChatGPT
3. Download all
4. Import all with `/bitwize-music:import-art`

---

## Phase 7: Staged Releases

### Release Schedule Options

| Strategy | Description |
|----------|-------------|
| **All at once** | Release everything same day |
| **Weekly** | One album per week |
| **Bi-weekly** | One album every two weeks |
| **Monthly** | One album per month for sustained presence |

### Staged Release Benefits

- **More content updates** for followers
- **Learning between releases** - Apply lessons to later albums
- **Algorithm visibility** - Regular releases help platform discovery

### Release Workflow Per Album

```
1. Run release checklist
2. Update README (release_date, Status: Released)
3. Upload to SoundCloud
4. Upload to distributor (if using)
5. Social announcement
```

---

## Efficiency Tips

### Time Savers

1. **Batch similar tasks** - All planning, then all writing, then all generation
2. **Use clipboard skill** - `/bitwize-music:clipboard` to quickly copy prompts between tracks
3. **Template consistency** - Reuse style prompt structures across similar genres
4. **Session notes** - Keep a running log of what's done/pending

### Quality Maintenance

1. **Don't rush verification** - Source verification is still required for true-story albums
2. **QA each album** - Listen through before marking complete
3. **Run validators** - `/bitwize-music:validate-album` catches issues early

### Progress Tracking

Use `/bitwize-music:resume` to check any album's status:

```
/bitwize-music:resume album-one
/bitwize-music:resume album-two
```

Or start a session with a full scan (Claude does this automatically on session start).

---

## Quick Reference: Bulk Commands

| Task | Command |
|------|---------|
| List album ideas | `/bitwize-music:album-ideas list` |
| Create album | `/bitwize-music:new-album name genre` |
| Check album status | `/bitwize-music:resume album-name` |
| Validate structure | `/bitwize-music:validate-album` |
| Copy to clipboard | `/bitwize-music:clipboard track-name` |
| Import art | `/bitwize-music:import-art path album` |
| Check explicit | `/bitwize-music:explicit-checker` |

---

## Sample Bulk Timeline

### Week 1: Planning
- Day 1-2: Plan Album A (7 phases)
- Day 3-4: Plan Album B (7 phases)
- Day 5: Plan Album C (7 phases)

### Week 2: Writing
- Day 1-2: Write Album A lyrics
- Day 3-4: Write Album B lyrics
- Day 5: Write Album C lyrics

### Week 3: Generation
- Day 1-2: Generate Album A on Suno
- Day 3-4: Generate Album B on Suno
- Day 5: Generate Album C on Suno

### Week 4: Finishing
- Day 1: Master all albums
- Day 2: Generate all album art
- Day 3: QA and final checks
- Day 4: Release Album A
- Day 5: Prepare releases for B and C

---

## Troubleshooting

**Lost track of which albums are where?**
- Start a new session - Claude scans all in-progress albums

**Inconsistent quality across albums?**
- Slow down. Quality > quantity.
- Run full QA on each album before releasing

**Running out of Suno credits?**
- Plan generation sessions around credit refresh
- Be more selective with regenerations

**Overwhelmed?**
- Go back to sequential (one album at a time)
- Bulk releases are advanced - build up to it
