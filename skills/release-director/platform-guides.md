# Platform Upload Guides

Detailed upload sequences and requirements for each platform.

---

## SoundCloud Upload Sequence

### Preparation
1. Create playlist: "[Album Name] by [Artist]"
2. Prepare track descriptions (from track markdown files)
3. Upload album art (3000x3000px)

### Upload order
1. Upload tracks 1-N (in order)
2. Set playlist order
3. Add album art to playlist
4. Set privacy (public/private as appropriate)
5. Add descriptions and tags
6. Enable downloads (if desired)

### Verification
- All tracks playable
- Order correct
- Album art displays
- Links work

### Platform Specs
- **Audio format**: WAV, MP3, FLAC, AIFF
- **Max file size**: 5GB per track
- **Artwork**: 3000x3000px (JPG/PNG)
- **Metadata**: Title, description, genre, tags

---

## distributor Submission Sequence

### Preparation
1. Have Streaming Lyrics filled in each track file
2. Have album art (3000x3000px JPG/PNG)
3. Have mastered WAV files
4. Know release date

### Submission steps
1. Create new album
2. Upload album art
3. Enter album metadata:
   - Album title
   - Artist name
   - Primary genre
   - Secondary genre
   - Subgenre
   - Release date
   - UPC (auto-generate or provide)
   - Language
   - Copyright info
4. Upload tracks (in order):
   - Track file (WAV)
   - Track title
   - Explicit flag
   - ISRC (auto-generate)
   - Lyrics (from track's Streaming Lyrics section)
5. Review and submit
6. Wait for approval (3-7 days)

### Post-approval
- Verify on Spotify, Apple Music, etc.
- Update album README with streaming links
- Trigger full campaign

### Platform Specs
- **Audio format**: WAV (16-bit or 24-bit, 44.1kHz minimum)
- **Artwork**: 3000x3000px minimum, JPG or PNG, RGB color mode
- **Lyrics**: Plain text, no section labels, written out fully
- **Metadata**: Comprehensive (album, artist, genre, copyright, language)

### Required Fields
- Primary genre (from dropdown)
- Secondary genre (from dropdown)
- Subgenre (from dropdown)
- Release date
- Copyright year and holder
- Language of lyrics

### Important Notes
- Use Streaming Lyrics format from track files
- Mark explicit content accurately
- Choose release date carefully (can't change after submission)

---

## Bandcamp (Optional)

### Platform Specs
- **Audio format**: WAV, FLAC, ALAC
- **Artwork**: 1400x1400px minimum (3000x3000px recommended)
- **Metadata**: Flexible, comprehensive

### Unique Features
- Pay-what-you-want pricing
- Instant download codes
- Fan community building
- Higher artist revenue

---

## Common Release Problems

### Problem 1: QA Checks Fail

**Symptom**: pre-release-qa identifies issues

**Common issues**:
- Track marked Final but has no Suno link
- Source-based track not verified
- Explicit content not flagged
- Lyrics don't match source

**Fix**:
- Return to appropriate agent (lyric-writer, researcher, etc.)
- Fix issue
- Re-run QA
- Don't proceed until clean

### Problem 2: distributor Rejection

**Symptom**: Submission rejected after review

**Common reasons**:
- Artwork doesn't meet specs
- Metadata incomplete/incorrect
- Audio quality issues
- Lyrics contain prohibited content
- Copyright issues

**Fix**:
- Read rejection reason carefully
- Fix specific issue
- Resubmit
- Usually approved on second try

### Problem 3: Streaming Lyrics Not Filled In

**Symptom**: At distributor submission, realize lyrics aren't formatted for streaming

**Fix**:
- Pause submission
- Fill in Streaming Lyrics section in each track file
- Resume submission

---

## Communication Templates

### To Mastering Engineer (when ready)

```
Ready to receive album for release. Please confirm:
- Mastered files location: [path]
- Track count: [N]
- All tracks meet standards (-14 LUFS, -1.0 dBTP)
- Album completion checklist done

Once confirmed, I'll begin pre-release QA and distribution prep.
```

### To Music Promoter (after release)

```
Album "[Album Name]" is now live and ready for promotion campaign.

Release Details:
- Date: [YYYY-MM-DD]
- SoundCloud: [link]
- Spotify: [link] (if applicable)
- Apple Music: [link] (if applicable)

Campaign Brief:
- Album type: [Documentary/Narrative/etc.]
- Key tracks: [Track 3, Track 7, Track 10]
- Target audience: [description]
- Recommended campaign: [Launch/Rotation]

Ready for campaign planning and execution.
```

### To User (release complete)

```
Album "[Album Name]" release complete!

Status:
✓ Pre-release QA passed
✓ All platforms live
✓ Status: Released (release_date set)
✓ Documentation updated
✓ Campaign handoff complete

Live on:
- SoundCloud: [link]
- Spotify: [link] (if applicable)
- Apple Music: [link] (if applicable)

Next: promotion phase will execute promotion campaign.
```
