# Error Recovery Procedures

This document covers edge cases and recovery procedures for common workflow issues.

## Wrong Track Marked Final

If a track was marked `Final` but needs regeneration:

1. Change Status: `Final` → `In Progress`
2. Note reason in Generation Log: "Needs regen - [reason]"
3. Regenerate on Suno
4. Log new attempt
5. When satisfied, mark `Generated` → `Final` again

## Lyrics Need Fixing After Verification

If lyrics have errors after human verification:

1. **DO NOT** change Status from `✅ Verified`
2. Fix lyrics in track file
3. Add note in track file: "Lyrics revised [date] - [reason]"
4. Tell user: "Lyrics updated, please re-verify"
5. After re-verification, update verification date

## Need to Regenerate After Mastering

If a mastered track has issues:

1. Don't delete mastered file - rename: `track.wav` → `track-OLD.wav`
2. Go back to Suno, regenerate
3. Download new WAV
4. Re-master just that track
5. Update Generation Log with notes

## Release Went Wrong

If release has issues after going live:

1. **DO NOT** delete from SoundCloud/platforms
2. If fixable: Generate corrected version, update platforms
3. If major issue: Note in album README: "Version History" section
4. Document what happened and resolution

## Undoing Release (Nuclear Option)

If you absolutely must undo a release:

1. Change Status: `Released` → `Complete`
2. Clear `release_date` field (or add note)
3. Remove from platforms (if possible)
4. Document why in album README
