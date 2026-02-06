---
name: resume
description: Finds an album by name and shows detailed status with next steps. Use when the user mentions an album name or wants to continue previous work.
argument-hint: <album-name>
model: claude-sonnet-4-5-20250929
allowed-tools:
  - Read
  - Glob
  - Bash
---

# Resume Album Work

**Purpose**: Find an album and resume work where you left off.

**Usage**:
```
/bitwize-music:resume <album-name>
/bitwize-music:resume my-album
/bitwize-music:resume "demo album"
```

**When to use**: When user wants to continue working on an existing album.

---

## Instructions

When this skill is invoked with an album name:

### Step 1: Read State Cache

Read `~/.bitwize-music/cache/state.json` to get album and track data.

**If state.json is missing or corrupted**:
- Resolve `${CLAUDE_PLUGIN_ROOT}`: find the plugin installation directory (typically the repo root containing `tools/state/indexer.py`, or search `~/.claude/plugins/cache/bitwize-music/bitwize-music` for latest version directory)
- Run: `python3 ${CLAUDE_PLUGIN_ROOT}/tools/state/indexer.py rebuild`
- If rebuild fails, fall back to manual Glob scan: read config, glob `{content_root}/artists/{artist}/albums/*/*/README.md`
- Then read the newly created state.json

**If state.json exists**: Use it directly (much faster than scanning files).

### Step 2: Find the Album

Search `state.albums` keys for the album name:
- Case-insensitive match
- Match variations: "sample-album", "sample_album", "sample album" should all match the same slug

**If no matches found**:
- Tell user: "Album '[name]' not found"
- List available albums from `state.albums` (slug, genre, status)
- Suggest: "Did you mean one of these?" or "Use /bitwize-music:new-album to create it"

**If multiple matches found**:
- List all matches with full paths
- Ask user which one they want

### Step 3: Extract Album and Track Data

From the matched album entry in `state.albums`, extract:
- **Album status**: from `album.status`
- **Track count**: from `album.track_count`
- **Tracks completed**: from `album.tracks_completed`
- **Track details**: from `album.tracks` — each track has status, has_suno_link, sources_verified

Count tracks by status from `album.tracks`:
- Not Started: X tracks
- In Progress: Y tracks
- Generated: Z tracks
- Final: N tracks

### Step 4: Staleness Check (Optional)

Spot-check one track file's mtime against `track.mtime` in state. If stale:
- Run `python3 ${CLAUDE_PLUGIN_ROOT}/tools/state/indexer.py update`
- Re-read state.json

### Step 5: Update Session Context

After finding the album, update session context using the CLI command:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/tools/state/indexer.py session --album <album-slug> --phase <phase>
```

Optional flags:
- `--track <track-slug>` — set last track worked on
- `--add-action "description"` — append a pending action
- `--clear` — clear session data before applying new values

### Step 6: Determine Current Phase

Based on album and track statuses, identify the workflow phase:

| Album Status | Track Statuses | Current Phase |
|--------------|----------------|---------------|
| Concept | Most "Not Started" | Planning - Need to fill in album README and create tracks |
| In Progress | Mixed, some "Not Started" | Writing - Need to complete lyrics |
| In Progress | Some "Sources Pending" | Verification - Need human verification of sources |
| In Progress | All have lyrics | Ready to Generate - Run Ready to Generate checkpoint |
| In Progress | Some "Generated" | Generating - Continue generating on Suno |
| Complete | All "Final" | Mastering - Ready to master audio |
| Released | All "Final" | Released - Album is live |

### Step 7: Report to User

Present a clear status report:

```
📁 Album: [Album Title]
   Location: {content_root}/artists/{artist}/albums/{genre}/{album}/
   Status: [Album Status]

📊 Progress:
   - Tracks: [X completed / Y total]
   - Not Started: X
   - In Progress: Y
   - Generated: Z
   - Final: N

📍 Current Phase: [Phase Name]

✅ What's Done:
   - [List completed items]

⏭️ Next Steps:
   1. [Specific action 1]
   2. [Specific action 2]
   3. [Specific action 3]

Ready to continue? Tell me what you'd like to work on.
```

### Step 8: Recommend the Single Best Next Action

Pick ONE clear recommendation from the decision tree below. Don't list 5 options — pick the best one, include the skill name, and be specific about which track.

**Decision Tree** (evaluate top-to-bottom, first match wins):

```
Album Status = "Concept"
  → "Define the album concept. Run /bitwize-music:album-conceptualizer"

Album Status = "Research Complete"
  → Any tracks Sources Pending?
    YES → "Sources need verification. Run /bitwize-music:verify-sources [album]"
    NO  → "Ready to write! Pick a track and use /bitwize-music:lyric-writer"

Album has tracks with "Not Started"
  → "Write lyrics for [first not-started track]. Use /bitwize-music:lyric-writer"

Album has tracks with "In Progress" (lyrics partially written)
  → "Finish lyrics for [first in-progress track]. Use /bitwize-music:lyric-writer"

Album has tracks with "Sources Pending"
  → "Verify sources for [track]. Run /bitwize-music:verify-sources [album]"

All tracks have lyrics, none generated
  → "All lyrics complete! Run /bitwize-music:pre-generation-check then generate on Suno."

Some tracks generated, some not
  → "Generate [first un-generated track] on Suno. Use /bitwize-music:suno-engineer"

All tracks generated
  → "All tracks generated! Import audio with /bitwize-music:import-audio, then master with /bitwize-music:mastering-engineer"

Album Status = "Complete"
  → "Album is complete! Release with /bitwize-music:release-director"

Album Status = "Released"
  → "This album is released! Consider /bitwize-music:promo-director for promotional content"
  → Also suggest: "Start a new album? Check /bitwize-music:album-ideas list"
```

**Format the recommendation as:**
```
RECOMMENDED NEXT ACTION:
  [Clear, specific instruction with skill name and track name]

WHY:
  [One sentence explaining why this is the right next step]
```

### When No Album Specified (No Arguments)

If invoked without an album name:
1. Check session context (`state.session.last_album`) — resume that album
2. If no session context, find all in-progress albums
3. Prioritize: closest to completion > unblocked work > last worked on
4. If no albums exist, suggest `/bitwize-music:new-album`

Present a multi-album summary if multiple are in progress:
```
You have X albums. Here's the most actionable:

PRIORITY 1: [album-name] ([genre])
  Status: [status] | Progress: [X/Y tracks]
  → [Recommended action]

Also in progress:
  - [album-2] — [brief status]
```

---

## Examples

### Example 1: Album in Writing Phase

```
/bitwize-music:resume my-album

📁 Album: My Album
   Location: ~/bitwize-music/artists/bitwize/albums/rock/my-album/
   Status: In Progress

📊 Progress:
   - Tracks: 3 completed / 8 total
   - Not Started: 3
   - In Progress: 2
   - Final: 3

📍 Current Phase: Writing Lyrics

✅ What's Done:
   - Tracks 1-3 have final lyrics
   - Album concept and tracklist defined

⏭️ Next Steps:
   1. Complete lyrics for Track 4 (in progress)
   2. Complete lyrics for Track 5 (in progress)
   3. Write lyrics for Tracks 6-8

Ready to continue? Tell me which track you'd like to work on.
```

### Example 2: Album Ready for Generation

```
/bitwize-music:resume demo-album

📁 Album: Demo Album
   Location: ~/bitwize-music/artists/bitwize/albums/electronic/demo-album/
   Status: In Progress

📊 Progress:
   - Tracks: 8 / 8 total (all lyrics complete)
   - Final: 8

📍 Current Phase: Ready to Generate

✅ What's Done:
   - All 8 tracks have complete lyrics
   - All lyrics phonetically reviewed
   - Suno Style and Lyrics boxes filled

⏭️ Next Steps:
   1. Run Ready to Generate checkpoint (I'll verify everything)
   2. Start generating on Suno
   3. Log generation attempts

Shall I run the Ready to Generate checkpoint now?
```

### Example 3: Album Not Found

```
/bitwize-music:resume my-album

❌ Album 'my-album' not found.

Available albums:
- demo-album (electronic) - In Progress
- example-tracks (hip-hop) - Complete

Did you mean one of these? Or use /bitwize-music:new-album to create a new album.
```

---

## Implementation Notes

- **Always read config first** - Never assume paths
- **Use Glob tool** - Don't use bash find/ls
- **Case-insensitive matching** - "Sample-Album" should match "sample-album"
- **Handle missing albums gracefully** - List what exists, don't error
- **Be specific about next steps** - Don't just say "continue working", say exactly what to do
- **Include full paths** - User needs to know where files are located
- **Use emojis sparingly** - Only for section headers in the report

---

## Model

Use **Sonnet 4.5** - This is a coordination/reporting task, not creative work.
