# Checkpoint Scripts

This document contains the detailed example messages for workflow checkpoints. CLAUDE.md references these scripts but keeps only triggers and action lists for brevity.

> **Related docs**: [release-procedures.md](release-procedures.md), [error-recovery.md](error-recovery.md)
> **Related skills**: `/bitwize-music:release-director` (release coordination), `/bitwize-music:validate-album` (structure validation)

## Ready to Generate Checkpoint

**Trigger**: When all track lyrics are written for an album

**Say to user:**
```
✅ ALL LYRICS COMPLETE

Album: [name]
Tracks: [count] tracks written
Explicit: [Yes/No]
Sources: [All verified / X pending]

Ready to begin Suno generation?

Next steps:
1. You'll generate tracks on Suno using the Style/Lyrics boxes
2. Log each attempt in Generation Log
3. Mark tracks as "Generated" when you have keepers

Proceed to generation?
```

## Album Generation Complete Checkpoint

**Trigger**: When all tracks marked `Generated` with Suno Links

**Say to user:**
```
✅ ALL TRACKS GENERATED

Album: [name]
Tracks: [count] / [count] complete

Track Status:
- Track 01: [title] - ✓ Generated [Suno Link]
- Track 02: [title] - ✓ Generated [Suno Link]
[... list all ...]

Ready for QA review?

Please listen through the full album:
1. Check vocal quality, pronunciation
2. Verify structure (all sections present)
3. Check for audio artifacts or issues
4. Confirm track order flows well

After QA, tell me:
- "Album approved" → Move to mastering
- "Track X needs regen" → We'll fix specific tracks
```

## Ready to Master Checkpoint

**Trigger**: User says "album approved" after QA review

**Say to user:**
```
✅ ALBUM APPROVED FOR MASTERING

All tracks marked Final. Album status: Complete.

Next step: Audio mastering

Do you have WAV files downloaded from Suno?
- If NO: Download all tracks as WAV (highest quality)
- If YES: Tell me where they're located

I'll set up mastering workflow once files are ready.
```

## Ready to Release Checkpoint

**Trigger**: After mastering complete and album art generated

**Say to user:**
```
✅ ALBUM READY FOR RELEASE

Album Completion Checklist:
- [✓] All tracks marked Final with Suno Links
- [✓] Album art generated and saved
- [✓] Audio mastered (-14 LUFS, -1.0 dBTP)
- [✓] SoundCloud metadata filled in
- [✓] Streaming Lyrics filled in each track
- [✓] For source-based albums:
  - [✓] All sources verified
  - [✓] RESEARCH.md and SOURCES.md complete

Album: [name]
Tracks: [count] tracks
Status: Complete → Ready to Release

Proceed with release?

Next steps:
1. Set release_date and Status: Released in album README
2. Upload to SoundCloud/distributor

Confirm to proceed with release.
```

## Post-Release Message

**Trigger**: After all release actions complete

**IMPORTANT**: Dynamically generate the tweet URL using the ACTUAL album name:
1. Take the real album name from the album README
2. URL-encode it (spaces become %20, quotes become %22, etc.)
3. Insert into the tweet intent URL
4. Display as a clickable markdown link

**Template** (replace `{ALBUM_NAME}` with actual name, `{URL_ENCODED_NAME}` with URL-encoded version):

```
🎉 ALBUM RELEASED

{ALBUM_NAME} is now live!

---

If you used this plugin to make your album, I'd love to hear about it.

[Click to tweet about your release](https://twitter.com/intent/tweet?text=Just%20released%20%22{URL_ENCODED_NAME}%22%20🎵%20Made%20with%20%40bitwizemusic%27s%20Claude%20AI%20Music%20Skills%20%23ClaudeCode%20%23SunoAI%20%23AIMusic)

Or manually: @bitwizemusic #ClaudeCode #SunoAI #AIMusic

Not required, just curious what people create with this. 🎵
```
