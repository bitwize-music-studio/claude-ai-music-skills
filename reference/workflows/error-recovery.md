# Error Recovery Procedures

This document covers edge cases and recovery procedures for common workflow issues.

---

## 1. Wrong Track Marked as Final

**Symptoms**: Discovered quality issues, wrong lyrics, or pronunciation problems after marking a track as Final.

**Prevention**: Always play through the full track before marking Final. Use the lyric-reviewer skill before generation.

**Recovery Steps**:
1. Change Status: `Final` → `In Progress`
2. Note reason in Generation Log: "Needs regen - [reason]"
3. Regenerate on Suno
4. Log new attempt with notes
5. When satisfied, mark `Generated` → `Final` again

**When to Delete vs Revert**: Never delete the track file. Always revert status and regenerate. Keep the Generation Log history for reference.

---

## 2. Suno Generation Failed Mid-Batch

**Symptoms**: Some tracks generated successfully, others failed or timed out. Partial album completion.

**Prevention**: Generate 2-3 tracks at a time maximum. Save progress frequently.

**Recovery Steps**:
1. Identify which tracks completed (check Suno dashboard)
2. Update completed tracks: add Suno Links, set Status: `Generated`
3. Note failed tracks in their Generation Logs: "Attempt failed - [error]"
4. Retry failed tracks individually
5. If persistent failures, adjust style prompt or try different time of day

**When to Delete vs Revert**: Keep all partial progress. Only retry failed tracks.

---

## 3. Audio Mastering Corrupted or Wrong Settings

**Symptoms**: Audio sounds distorted, clipped, wrong loudness, or different from expected.

**Prevention**: Always run preview (dry-run) before mastering. Check LUFS/dBTP after mastering.

**Recovery Steps**:
1. Rename bad masters: `track.wav` → `track-BAD.wav`
2. Keep original unmastered files (never overwrite originals)
3. Re-run mastering with correct settings
4. Compare A/B against original
5. Delete BAD files only after confirming new masters are correct

**When to Delete vs Revert**: Keep BAD files until new masters are verified. If originals were overwritten, re-download from Suno.

---

## 4. Album Accidentally Released

**Symptoms**: Album marked Released and/or uploaded to platforms before it was ready.

**Prevention**: Use Release Director skill for guided release. Always verify checklist before changing status.

**Recovery Steps**:
1. **If on platforms**: Set tracks to private/unlisted (don't delete yet)
2. Change Status: `Released` → `Complete`
3. Remove or comment out `release_date` field
4. Add "Version History" section in album README documenting the incident
5. Fix whatever issues exist
6. When ready, go through proper release flow again

**When to Delete vs Revert**: On platforms, prefer unlisting over deletion. Deletion may cause issues with future uploads of same content.

---

## 5. Lyrics Mistake After Generation

**Symptoms**: Discovered factual error, typo, or problematic content in lyrics after Suno generation.

**Prevention**: Run lyric-reviewer and pronunciation-specialist before generation. Verify against sources for true-story albums.

**Recovery Steps**:
1. Fix lyrics in track file immediately
2. Add note: "Lyrics revised [date] - [reason]"
3. **If track was Final**: Revert to `In Progress`, regenerate
4. **If source-based**: Request re-verification from user
5. Update Generation Log with regeneration notes

**When to Delete vs Revert**: Never delete track file. Always fix in place and regenerate audio if needed.

---

## 6. Duplicate Tracks or Mixed Up File Names

**Symptoms**: Two tracks have same content, files named wrong, or track numbers don't match content.

**Prevention**: Use `/bitwize-music:import-track` skill which validates naming. Review tracklist before generation.

**Recovery Steps**:
1. Identify correct mapping: which file should be which track
2. Rename files to temporary names first: `01-track.md` → `01-track-TEMP.md`
3. Rename to correct names in order
4. Update any Suno Links if they point to wrong tracks
5. Verify tracklist in album README matches file order
6. Update track numbers in frontmatter

**When to Delete vs Revert**: Delete true duplicates (identical content). Rename/reorganize misnamed files.

---

## 7. Wrong Genre/Style Prompt Results

**Symptoms**: Generated audio sounds completely wrong for the intended style. Wrong tempo, mood, or genre.

**Prevention**: Use `/bitwize-music:suno-engineer` for style prompts. Test style on one track before batch generation.

**Recovery Steps**:
1. Document what went wrong in Generation Log
2. Analyze: Was it the style prompt, lyrics structure, or Suno interpretation?
3. Revise style prompt (see `/reference/suno/v5-best-practices.md`)
4. Test new prompt on a single track
5. Once working, regenerate affected tracks
6. Save both old and new style prompts for reference

**When to Delete vs Revert**: Keep failed generations in log for learning. Only regenerate audio, don't delete documentation.

---

## 8. Research Sources Incorrect or Outdated

**Symptoms**: Discovered source was unreliable, facts changed, or better sources exist.

**Prevention**: Use source hierarchy (court docs > gov releases > journalism > news). Verify with multiple sources.

**Recovery Steps**:
1. Mark affected source in SOURCES.md as `[DEPRECATED]` with note
2. Find replacement source
3. Update RESEARCH.md with corrected information
4. Review all lyrics that used the bad source
5. Reset affected tracks: Status → `Sources Pending`
6. Request re-verification from user
7. Only after verification, proceed with any needed regeneration

**When to Delete vs Revert**: Never delete source entries. Mark deprecated and add replacement. Audit trail matters.

---

## 9. Album Art Rejected or Wrong Dimensions

**Symptoms**: Platform rejects album art, art appears cropped/stretched, or wrong aspect ratio.

**Prevention**: Always use 3000x3000 pixels, sRGB color space, JPEG or PNG under 20MB.

**Recovery Steps**:
1. Check rejection reason (dimensions, file size, content policy)
2. Regenerate with correct specs using art director prompt
3. Save new art with version number: `album-art-v2.jpg`
4. Use `/bitwize-music:import-art` to place in correct locations
5. Update album README if art prompt was revised
6. Re-upload to platforms

**When to Delete vs Revert**: Keep old versions (v1, v2) until release is complete. Delete only unused drafts.

---

## 10. Configuration Paths Wrong, Files in Wrong Location

**Symptoms**: Files saved to wrong directory, can't find expected files, path errors in skills.

**Prevention**: Always read `~/.bitwize-music/config.yaml` before file operations. Use import skills.

**Recovery Steps**:
1. Read config to get correct paths
2. Locate misplaced files (check current directory, home, Downloads)
3. Move files to correct location using proper path structure:
   - Content: `{content_root}/artists/{artist}/albums/{genre}/{album}/`
   - Audio: `{audio_root}/{artist}/{album}/`
   - Documents: `{documents_root}/{artist}/{album}/`
4. Verify no broken references in track files
5. Run `/bitwize-music:validate-album` to confirm structure

**When to Delete vs Revert**: Move files, don't delete. Only delete after confirming files are in correct location.

---

## 11. Track Numbers Out of Order

**Symptoms**: Tracks display in wrong order, numbering gaps, or doesn't match album flow.

**Prevention**: Plan tracklist before creating files. Use zero-padded numbers (01, 02, not 1, 2).

**Recovery Steps**:
1. Document intended track order
2. Rename files to temporary names: `01-track.md` → `TEMP-01.md`
3. Rename to correct numbers in sequence
4. Update frontmatter `track_number` field in each file
5. Update tracklist in album README
6. Verify Suno Links still point to correct audio
7. If mastered, rename audio files to match

**When to Delete vs Revert**: Never delete. Rename and renumber in place.

---

## 12. Forgot Pronunciation Check, Suno Mispronounced Words

**Symptoms**: Generated audio has mispronounced names, homographs read wrong, or acronyms spoken as words.

**Prevention**: ALWAYS run `/bitwize-music:pronunciation-specialist` before generation. Check homographs (live, lead, read, wind, tear, bass, close).

**Recovery Steps**:
1. Identify all mispronounced words in the track
2. Run pronunciation-specialist on lyrics
3. Apply phonetic spellings to Lyrics Box:
   - Names: "Ramos" → "Rah-mohs"
   - Acronyms: "FBI" → "F-B-I"
   - Homographs: "live" → "lyve" or "liv"
4. Update track file with corrected lyrics
5. Regenerate on Suno
6. Verify pronunciation in new generation

**When to Delete vs Revert**: Keep original in Generation Log. Regenerate with corrected lyrics.

---

## Emergency Recovery

For major disasters (data loss, corrupted files, accidental mass deletion):

### Immediate Actions
1. **STOP** - Don't make more changes
2. Check git status: `git status` - are changes committed?
3. Check git log: `git log --oneline -10` - find last good state
4. If uncommitted changes lost: Check file recovery (Trash, Time Machine, etc.)

### Git Recovery
- Recover deleted file: `git checkout HEAD -- path/to/file`
- Revert to previous commit: `git checkout [commit-hash] -- path/to/file`
- See what changed: `git diff HEAD~1`

### Suno Recovery
- All generations saved in Suno account history
- Re-download any needed audio from Suno dashboard
- Check "Library" for all past generations

### When All Else Fails
1. Export what you can (lyrics from track files, notes from READMEs)
2. Document what was lost
3. Start fresh with `/bitwize-music:new-album`
4. Import salvaged content

---

## Prevention Checklist

Verify before each phase to avoid recovery scenarios:

### Before Research
- [ ] Config file readable (`~/.bitwize-music/config.yaml`)
- [ ] Album directory exists in correct location
- [ ] SOURCES.md created in album directory

### Before Writing Lyrics
- [ ] Research verified (`Status: Sources Verified` for source-based)
- [ ] Track files created with correct numbering
- [ ] Artist/album style defined in album README

### Before Generation
- [ ] Pronunciation check complete on all tracks
- [ ] Lyric review complete (9-point checklist)
- [ ] Style prompts filled in all track files
- [ ] Explicit content flags set correctly

### Before Mastering
- [ ] All tracks have Status: `Generated`
- [ ] All Suno Links present and working
- [ ] Original WAV files downloaded and backed up
- [ ] Mastering preview (dry-run) looks correct

### Before Release
- [ ] Album Completion Checklist fully checked
- [ ] All tracks Status: `Final`
- [ ] Album art correct dimensions (3000x3000)
- [ ] release_date ready to set

---

## When to Start Over

Sometimes a fresh start is better than fixing. Consider starting over when:

- **More than 50% of tracks need major changes** - Faster to rebuild than fix
- **Concept fundamentally changed** - New album is cleaner than retrofitting
- **Source material was entirely wrong** - Research needs complete redo
- **File structure is unsalvageable** - Missing files, broken references everywhere
- **Learning curve issues** - Early album before you understood the workflow

### How to Start Over Cleanly
1. Rename old album directory: `album-name` → `album-name-OLD`
2. Create fresh album: `/bitwize-music:new-album album-name genre`
3. Salvage what works from OLD version (copy specific content)
4. Delete OLD directory only after new album is complete
5. Document lessons learned for future reference

### What to Salvage
- Research that's still valid (RESEARCH.md, SOURCES.md)
- Lyrics that worked well
- Style prompts that produced good results
- Generation Log notes about what worked/failed

### What NOT to Salvage
- Broken file structures
- Unverified sources
- Lyrics with known issues
- Style prompts that failed
