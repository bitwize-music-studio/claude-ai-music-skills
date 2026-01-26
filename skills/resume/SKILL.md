# Resume Album Work

**Purpose**: Find an album and resume work where you left off.

**Usage**:
```
/bitwize-music:resume <album-name>
/bitwize-music:resume shell-no
/bitwize-music:resume "shell no"
```

**When to use**: When user wants to continue working on an existing album.

---

## Instructions

When this skill is invoked with an album name:

### Step 1: Read Configuration

Read `~/.bitwize-music/config.yaml` to get:
- `paths.content_root` - Where album files live
- `artist.name` - Artist name for path construction

If config missing, tell user to run `/bitwize-music:configure` first.

### Step 2: Find the Album

Use Glob to search for album README files:

```
Pattern: {content_root}/artists/{artist}/albums/*/*/README.md
```

This searches all genre folders for album READMEs.

**Filter the results**:
- Look for album name in the file path (case-insensitive)
- Match variations: "shell-no", "shell_no", "shell no" should all match

**If no matches found**:
- Tell user: "Album '[name]' not found"
- List available albums (all READMEs found)
- Suggest: "Did you mean one of these?" or "Use /bitwize-music:new-album to create it"

**If multiple matches found**:
- List all matches with full paths
- Ask user which one they want

### Step 3: Read Album Status

Once album is located, read the README to determine:
- **Album status**: Concept, In Progress, Complete, Released
- **Track count**: How many tracks total
- **Tracklist**: Track titles and order

### Step 4: Check Track Status

Glob for track files in the album's tracks directory:

```
Pattern: {album_path}/tracks/*.md
```

Read each track file to check:
- **Status field**: Not Started, Sources Pending, Verified, In Progress, Generated, Final
- **Suno Link**: Present or missing
- **Lyrics**: Complete or incomplete

Count tracks by status:
- Not Started: X tracks
- In Progress: Y tracks
- Generated: Z tracks
- Final: N tracks

### Step 5: Determine Current Phase

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

### Step 6: Report to User

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

### Step 7: Offer Specific Next Actions

Based on the phase, suggest concrete next steps:

**Planning Phase**:
- "Let's fill in the album concept and tracklist"
- "Run the 7 Planning Phases to finalize details"

**Writing Phase**:
- "Which track should we write next?"
- "Track X needs lyrics - shall we work on that?"

**Verification Phase**:
- "Tracks X, Y, Z need source verification"
- "Please review and verify sources before we proceed"

**Ready to Generate Phase**:
- "All lyrics complete! Ready to generate on Suno?"
- "Shall I run the Ready to Generate checkpoint?"

**Generating Phase**:
- "Tracks X, Y need generation on Suno"
- "Have you generated any new tracks? Let me know URLs to log"

**Mastering Phase**:
- "All tracks generated! Ready to master?"
- "Do you have WAV files downloaded from Suno?"

---

## Examples

### Example 1: Album in Writing Phase

```
/bitwize-music:resume shell-no

📁 Album: Shell No
   Location: ~/bitwize-music/artists/bitwize/albums/electronic/shell-no/
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
/bitwize-music:resume shell-no

📁 Album: Shell No
   Location: ~/bitwize-music/artists/bitwize/albums/electronic/shell-no/
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
- shell-no (electronic) - In Progress
- linux-legends (hip-hop) - Complete

Did you mean one of these? Or use /bitwize-music:new-album to create a new album.
```

---

## Implementation Notes

- **Always read config first** - Never assume paths
- **Use Glob tool** - Don't use bash find/ls
- **Case-insensitive matching** - "Shell-No" should match "shell-no"
- **Handle missing albums gracefully** - List what exists, don't error
- **Be specific about next steps** - Don't just say "continue working", say exactly what to do
- **Include full paths** - User needs to know where files are located
- **Use emojis sparingly** - Only for section headers in the report

---

## Model

Use **Sonnet 4.5** - This is a coordination/reporting task, not creative work.
