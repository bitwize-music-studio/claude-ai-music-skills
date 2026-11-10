---
name: edit-take
description: Fixes one thing in a Suno take without re-rolling the song - a word or a line, a cut or added line, a time range redone, an instrument added or dropped - and keeps the rest of the take's audio; also makes an instrumental version of a take. Shows the cost and waits for a go-ahead. Use when the user likes a take but something in it is wrong ("fix the word in line 3", "drop the synth", "redo the bridge"), to apply a lyric or pronunciation fix made in the track file to a take worth keeping, or when they want the take without its vocals.
argument-hint: <album-name> <track> [take N] ["what to change" | instrumental]
model: sonnet
effort: medium
allowed-tools:
  - Read
  - Edit
  - bitwize-music-mcp
  - mcp__suno__*
---

## Your Task

**Input**: $ARGUMENTS

Change part of one take through Suno's MCP server and keep the rest of it: build the edit, show what it costs, get a go-ahead, send it, log the two edited takes, and hand off to listening.

You never choose a take, mark a keeper or set a track `Final`. The user listens and decides.

---

# Edit Take Skill

An edit is the cheap fix for a take that is nearly right. Suno keeps the take's audio and changes only what the instruction names. Measured on a one-minute song: the edited takes had the source's exact length, sang the new word, and left the rest as it was. It is still a generation: one call makes **two** edited takes and costs **10 song credits**.

Two ways to say what changes:

- **In words** — `"drop the synth"`, `"redo 0:45 to 1:00 with more energy"`, `"change 'the light is gone' to 'the light came home'"`.
- **From the track file** — no words given: the edit brings the take in line with the Lyrics Box as it stands now. This is how a pronunciation or wording fix made in the track file reaches a take.

Past five changed places Suno re-sings the whole song as a cover; from there `/bitwize-music:generate` is the better tool. Background: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Editing a Take.

## Step 1: Resolve

Expected format: `<album-name> <track> [take N] ["what to change" | instrumental]`

Find the album and track as `/bitwize-music:generate` does. The word `instrumental` in place of an instruction asks for a version of the take, not a change to it: go to **An Instrumental Version**. If the words to change include new sung words, treat them like any new lyric: run `check_homographs` on them and ask about each homograph before going on.

## Step 2: Check the Suno Server

Follow § Preflight in the reference doc: find `audio-create`, `audio-wait`, `audio-retrieve` and `account-usage`, load their current definitions, and read `account-usage`. Not connected → say an edit needs Suno's MCP server and stop; on suno.com the same edit is made in the song's editor.

## Step 3: Build the Edit

- **In words**: `get_edit_request(album_slug, track_slug, take: N, instruction: "<the user's words>")`.
- **From the track file**: call `get_edit_request(album_slug, track_slug, take: N)` once to learn the take's `source.clip_id`, then `audio-retrieve(id: <that clip id>)`, then `get_edit_request(album_slug, track_slug, take: N, take_lyrics: <metadata.lyrics>)`.

Leave `take` at 0 when the user named none: the tool picks the keeper, or the only take there is.

| Result | Do |
|--------|-----|
| `found: false` | Report the error and stop |
| `take_ambiguous` | Ask which take, then call again with `take` |
| `needs_instruction` on the first call of the track-file path | Expected; carry on with `audio-retrieve` |
| `nothing_to_change` | The Lyrics Box already matches the take; ask what to change |
| Any other blocking problem | Show it and stop |
| `edit_rewrites_song` (a warning) | Say that Suno will re-sing the whole song, and ask whether to edit anyway or regenerate |

## Step 4: Show the Summary and Get a Go-Ahead

```
READY TO EDIT — [NN] [Title], take 2

  Change     "Waiting for the day to hold still"
        to   "Waiting for the tide to hold still"
  Sent as    In [Title], change "…" to "…".
  Keeps      the rest of the take's audio
  Makes      2 edited takes
  Cost       about 10 song credits. You have 9,915.
  Then       open both edited takes (free) and check them.

Go ahead?   yes · cancel
```

- In words mode, show the instruction in place of the Change lines.
- Wait for an explicit yes. Silence is not a yes.

## Step 5: Send It

1. Fix an idempotency key before the first attempt: `{album_slug}/{track_slug}/edit/{UTC timestamp}`.
2. Call `audio-create` with the keys of `request` and the `idempotency_key`. Add nothing: `duration`, `instrumental` and `vocal_gender` make Suno regenerate the whole song, and `lyrics` and `style` are refused next to a `description`.
3. The answer carries two ids in `clip_ids`. Call `audio-wait` with both and `until: "complete"`; call it again while either is pending. An edit usually finishes within a minute.
4. Call `account-usage` again. Credits spent = balance before − balance after.

Failures are handled as in `/bitwize-music:generate` Step 6: one retry with the same key after a timeout; a new key if an argument had to be dropped; `402` is out of credits; `403` means the song may not be remixed or the plan lacks a feature; `400` is Suno's content check or a mixed-mode request. Never send a second call for one go-ahead except as that table says.

## Step 6: Log and Hand Off

1. `log_generation(album_slug, track_slug, <the track's model>, clips, notes: "edit of take N: <a few words>, via MCP, 10 credits")`, with each clip's id, status and length.
2. Report:

   ```
   EDITED — [NN] [Title], take 2

     Take 5 (row 5)   0:55   https://suno.com/song/...
     Take 6 (row 6)   0:55   https://suno.com/song/...

     Spent 10 song credits. 9,905 left.
   ```

3. Continue into `/bitwize-music:listen` for the two new rows, then `/bitwize-music:check-take` for them, as `/bitwize-music:generate` Step 8 does.

The track's status does not change, and the original take stays in the log. If the user keeps an edited take, approval works as always (`/bitwize-music:listen` Step 7). When the edit was given in words and changed sung words, update the Lyrics Box and Streaming Lyrics to what the keeper sings.

## An Instrumental Version

`/bitwize-music:edit-take <album> <track> [take N] instrumental` takes the vocals off a take and keeps the rest — a version to release beside the song, or to put under a video.

1. Step 2 as above, then `get_edit_request(album_slug, track_slug, take: N, version: "instrumental")`. `already_instrumental`, `source_is_a_version` and `version_unsupported` are blocking: show the problem and stop.
2. Summary, go-ahead and sending are Steps 4 and 5: 10 song credits for two takes. In the summary write `Makes  2 instrumental versions of take N` and `Keeps  everything but the vocals`.
3. Log with `notes: "<log_notes from the tool>, via MCP, 10 credits"`. Those words mark the rows as versions: they are never taken for the track's keeper, the take check leaves them out, and the track's status does not change.
4. Open both (`/bitwize-music:listen <album> <track> take <rows>`). Measured: both came back at the source's exact length with no voice on them. A version whose length differs from the source's was made again, not lifted out of the take — say so when it happens.
5. When the user picks one, mark that row ✓ and do nothing else: no Suno Link, no status change, no like. Then `/bitwize-music:import-audio --from-suno <album> <track> --version instrumental` saves it as `versions/<track>-instrumental.wav`.

**An a cappella is not offered this way.** Measured: the same request for an a cappella returned the instrumental once more and a shorter, re-sung song with its guitar. The vocals stem is the a cappella: `/bitwize-music:import-audio --from-suno <album> <track> --stems` saves it as `stems/<track>/0 Lead Vocals.wav`.

## Remember

1. **An edit is a generation**: cost first, then a go-ahead, then one call.
2. **Send only what `get_edit_request` returned**, plus the idempotency key.
3. **Two edited takes come back**; the original is untouched.
4. **More than five changed places is a re-sing**, not an edit — say so before spending.
5. **You never pick a take, mark a keeper or set `Final`.**
6. **A version is kept beside the track, never as it**: its ✓ marks the one to import and changes nothing else.
