# Quick Start: True Story Album

Step-by-step for creating documentary or narrative albums based on real events.

**Time estimate**: 4-8 hours (research adds significant time)

**Key difference from standard albums**: Research and source verification are mandatory before writing lyrics.

---

## Prerequisites

Before you begin:

1. **Standard prerequisites** - Suno account, Claude Code, config file
2. **Research topic** - A real event, person, or case you want to document
3. **Time for verification** - Human review of sources is required

---

## Phase 1: Setup (5 minutes)

### Step 1: Create Album with Research Templates

```
/bitwize-music:new-album my-true-story hip-hop documentary
```

The `documentary` flag creates additional files:
- `RESEARCH.md` - Consolidated findings
- `SOURCES.md` - Full citations

### Step 2: Verify Creation

Confirm you have:
- `README.md`
- `RESEARCH.md`
- `SOURCES.md`
- `tracks/` folder

---

## Phase 2: Planning (30-60 minutes)

### The 7 Phases (Same as Standard)

Work through planning phases. For true-story albums, Phase 2 (Concept) is critical:

**Phase 2 Questions for True Story:**
- What's the real event or subject?
- What's the narrative angle? (chronological, thematic, perspective)
- Who are the key figures?
- What's the emotional truth you're conveying?
- What research sources exist?

### CHECKPOINT: Planning Complete

Stop here until:
- [ ] All 7 phases complete
- [ ] Research scope defined
- [ ] You confirmed "ready to start research"

---

## Phase 3: Research (1-3 hours)

This is the critical phase that distinguishes true-story albums.

### Step 1: Invoke the Researcher

```
/bitwize-music:researcher "your topic keywords"
```

The researcher:
- Searches primary sources (court docs, government releases)
- Cross-verifies facts across 3+ sources
- Extracts verbatim quotes with page numbers
- Documents methodology

### Step 2: Use Specialized Researchers (Optional)

For deep dives, Claude coordinates specialists:

| Topic | Invoke |
|-------|--------|
| Court documents | `/bitwize-music:researchers-legal` |
| DOJ/FBI releases | `/bitwize-music:researchers-gov` |
| Investigative journalism | `/bitwize-music:researchers-journalism` |
| SEC filings | `/bitwize-music:researchers-financial` |
| Security incidents | `/bitwize-music:researchers-security` |
| Historical events | `/bitwize-music:researchers-historical` |
| Personal backgrounds | `/bitwize-music:researchers-biographical` |

### Step 3: Document Everything

Research outputs go to your album directory:
- `RESEARCH.md` - Findings with verification status
- `SOURCES.md` - Full academic citations

**Reference**: See [CLAUDE.md > Sources & Verification](../../CLAUDE.md#sources--verification)

### Source Hierarchy

1. Court documents (highest)
2. Government releases
3. Investigative journalism
4. News coverage
5. Wikipedia (context only, never primary)

### CHECKPOINT: Research Complete

Stop here until:
- [ ] RESEARCH.md populated with verified facts
- [ ] SOURCES.md has all citations with URLs
- [ ] Key facts have 3+ independent sources
- [ ] Album status: `Research Complete`

---

## Phase 4: Human Verification (REQUIRED)

**This step cannot be skipped.** You must personally verify sources before writing lyrics.

### Step 1: Review Sources

For each track's source material:
1. Open the track file
2. Find "Quotes & Attribution" section
3. Click each URL
4. Visually confirm quotes match sources
5. Check citations are accurate

### Step 2: Report Verification

Tell Claude which tracks you've verified:
```
Tracks 1-5 sources verified
```

Claude updates status from `Pending` to `Verified (DATE)`.

### Verification Rules

- **You cannot skip this** - Claude will block generation
- **Visual confirmation required** - Actually click the URLs
- **Document discrepancies** - If something doesn't match, report it

**Reference**: See [source-verification-handoff.md](../workflows/source-verification-handoff.md)

### CHECKPOINT: All Sources Verified

Stop here until:
- [ ] All tracks show `Verified` (not `Pending`)
- [ ] Any discrepancies resolved
- [ ] Album status: `Sources Verified`

---

## Phase 5: Writing Lyrics (1-2 hours)

Now you can write lyrics based on verified research.

### Key Constraints for True Story Lyrics

1. **Narrator voice only** - Never impersonate real people
2. **No fabricated quotes** - Only use verified statements
3. **Every claim traceable** - Must connect to SOURCES.md
4. **Factual accuracy** - Names, dates, amounts must be correct

### Step 1: Write Track by Track

For each track:
```
Let's write lyrics for track 01 based on the research
```

Claude uses the verified research to draft lyrics.

### Step 2: Source Check

After writing, Claude automatically verifies:
- All facts match RESEARCH.md
- No claims exceed source material
- Chronology is accurate

### CHECKPOINT: Lyrics Complete

Stop here until:
- [ ] All tracks have lyrics
- [ ] All claims verified against sources
- [ ] `/bitwize-music:lyric-reviewer` passed

---

## Phase 6: Generation (1-2 hours)

Same as standard album. See [first-album.md](first-album.md#phase-4-suno-generation-1-2-hours).

### True Story Specific Tips

- **Pronunciation critical** - Names must be correct
- **Run `/bitwize-music:pronunciation-specialist`** on all tracks
- **Phonetic spelling** - Use for all proper nouns

---

## Phase 7: Mastering & Release

Same as standard album. See [first-album.md](first-album.md#phase-5-mastering-30-minutes).

### True Story Release Checklist

Additional items:
- [ ] All sources verified by human
- [ ] RESEARCH.md and SOURCES.md complete
- [ ] All lyrics verified against sources
- [ ] Narrator voice only (no impersonation)

---

## Complete Workflow Summary

```
1. /bitwize-music:new-album name genre documentary
2. Complete 7 Planning Phases
3. /bitwize-music:researcher "topic"
   (Uses specialized researchers as needed)
4. HUMAN VERIFICATION - You verify all sources
5. Write lyrics based on verified research
6. /bitwize-music:lyric-reviewer (verify sources match)
7. Generate on Suno
8. Master audio
9. Create album art
10. Release
```

---

## Quick Reference: Research Commands

| Task | Command |
|------|---------|
| Start research | `/bitwize-music:researcher "topic"` |
| Find court docs | `/bitwize-music:researchers-legal` |
| Find gov releases | `/bitwize-music:researchers-gov` |
| Find journalism | `/bitwize-music:researchers-journalism` |
| Verify research | `/bitwize-music:researchers-verifier` |
| Check pronunciation | `/bitwize-music:pronunciation-specialist` |

---

## Troubleshooting

**"Cannot proceed - verification required"**
- You have `Pending` sources
- Click the URLs, verify quotes, then tell Claude they're verified

**Source not found?**
- Try `/bitwize-music:document-hunter` for automated search
- Check free sources in researcher's `free-sources.md`

**Conflicting sources?**
- Document the discrepancy
- Use highest-tier source (court > gov > journalism)
- Note the conflict in lyrics if relevant

**Name pronunciation wrong?**
- Add to phonetic guide
- Use `/bitwize-music:pronunciation-specialist`

---

## Legal & Ethical Notes

- **No impersonation** - Never put words in real people's mouths
- **Document everything** - Every claim must trace to a source
- **Narrator perspective** - You're telling the story, not speaking as the subject
- **Fair use** - Short quotes for commentary/criticism, not wholesale reproduction
