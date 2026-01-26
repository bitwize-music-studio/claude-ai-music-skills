# Source Verification Handoff Procedures

This document contains detailed procedures for handling human verification of source material in documentary/true-story albums.

## When to Stop and Request Verification

### Trigger 1: After Adding Sources to Track

When you've added source material to a track's "Quotes & Attribution" section:

**Say to user:**
```
⚠️ VERIFICATION REQUIRED

I've added source material to [track name]. Before we proceed to writing lyrics:

1. Review the "Quotes & Attribution" section in tracks/XX-track-name.md
2. Click each source URL and visually confirm the quotes/facts
3. Check that citations match the actual source content
4. If verified, tell me: "sources verified for track XX"
5. If issues found, tell me what needs correction

Do NOT proceed to generation until you confirm verification.
```

### Trigger 2: After All Track Sources Added

When all tracks in an album have sources but none are verified:

**Say to user:**
```
⚠️ ALBUM VERIFICATION REQUIRED

All tracks have source material added (Status: ❌ Pending).

Next step: Human verification of all sources before any track generation.

To verify:
1. Open each track file in tracks/
2. Review "Quotes & Attribution" section
3. Click URLs, verify quotes/facts match sources
4. Tell me which tracks are verified (e.g., "tracks 1-5 verified")

Current verification status:
- Track 01: ❌ Pending
- Track 02: ❌ Pending
[... list all tracks ...]

I'll wait for your verification before proceeding.
```

### Trigger 3: User Tries to Skip Verification

If user says "let's generate" or "start production" while tracks show `❌ Pending`:

**Say to user:**
```
⚠️ CANNOT PROCEED - VERIFICATION REQUIRED

Tracks with unverified sources cannot be generated. This is a legal safeguard.

Tracks needing verification:
- Track XX: [name] (❌ Pending)

Please verify sources first, then we can proceed to generation.
```

## After Verification Complete

Once user confirms verification:

1. Update track status from `❌ Pending` to `✅ Verified (YYYY-MM-DD)`
2. Update "Sources Verified" field in track file
3. Now track can move to `In Progress` for generation
4. Update album status if all tracks verified

## Track Status Workflow

1. Claude adds sources → Status: `❌ Pending`
2. Human verifies → Status: `✅ Verified (DATE)`
3. Only after verification → Status: `In Progress`
