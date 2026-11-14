---
name: extend-take
description: Carries a Suno take on from a point in its audio - more of a song that stopped early, or a new second half for a take that went wrong late - and joins the result into whole songs. Shows the cost and waits for a go-ahead. Use when the user says a take "ends too soon", "cut off the last chorus", "extend it", "add the bridge to this take" or "keep the first half and redo the rest".
argument-hint: <album-name> <track> [take N] --at <m:ss | end> [--from "<section>"]
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

Carry one take on through Suno's MCP server: build the continuation, show what it costs, get a go-ahead, send it, join each continuation into a whole song, log the whole songs, and hand off to listening.

You never choose a take, mark a keeper or set a track `Final`. The user listens and decides.

---

# Extend Take Skill

An extension keeps a take up to a point and generates what follows. Use it when the first part of a take is worth keeping: it stopped before the last chorus, its ending went wrong, or the song needs a verse it does not have. Suno returns only the new part; joining it to the old part is free.

Measured on a one-minute song: one call made **two** continuations for **10 song credits**, and each joined, free, into its own whole song in the same voice. Carried on from the middle of a phrase, the join could be heard — so the point to carry on from is the end of a line. Background: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Extending a Take.

## Step 1: Resolve

Expected format: `<album-name> <track> [take N] --at <m:ss | end> [--from "<section>"]`

Find the album and track as `/bitwize-music:generate` does. Two things are needed; ask for whichever is missing.

- **Where to carry on from** — a time in the take, at the end of a sung line. `end` means the take's whole length, which keeps its last chord or fade in the middle of the longer song; to replace an ending, carry on from before it. If the user names a line instead of a time ("after 'there's a light to hold'"), ask Suno's listening agent, which is free: `audio-listen(id: <the take's clip id>, question: "At what time, in seconds, does the line \"…\" end? End with a JSON block with the field line_ends_at_s.")`, then `audio-listen-wait`. Say the time back and let the user correct it; the agent can be off.
- **What follows** — a section of the track's Lyrics Box. The continuation is sent that section and everything after it. New words go into the Lyrics Box first, through `/bitwize-music:lyric-writer`, so they pass the same checks as the rest of the track; after that they are a section like any other.

## Step 2: Check the Suno Server

Follow § Preflight in the reference doc: find `audio-extensions-create`, `audio-full-song`, `audio-wait` and `account-usage`, load their current definitions, and read `account-usage`. `features` lacks `generate.extend` → say the plan does not include extensions and stop. Not connected → say an extension needs Suno's MCP server and stop; on suno.com it is the song's Extend button.

## Step 3: Build the Request

First `run_pre_generation_gates(album_slug, track_slug)`: the continuation sings words from the Lyrics Box, and they may have changed since the take was made. A blocking gate stops an extension as it stops a generation; show the failed gates and stop.

Then `get_extension_request(album_slug, track_slug, take: N, continue_at: "<time>", from_section: "<section>")`. Leave `take` at 0 when the user named none: the tool picks the keeper, or the only take there is.

| Result | Do |
|--------|-----|
| `found: false` | Report the error and stop |
| `take_ambiguous` | Ask which take, then call again with `take` |
| `needs_continue_at`, `take_length_unknown` | Ask for the time (Step 1) |
| `section_not_found`, `section_ambiguous` | Show `sections` and ask which |
| `no_section_named` (a warning) | Say Suno will write the words itself, show `sections`, and ask whether to name one |
| `continue_from_end` (a warning) | Say the take's ending stays in the middle of the song; ask whether to carry on from before it instead |
| Any other blocking problem | Show it and stop |
| `voice` is set | Find its id as `/bitwize-music:generate` Step 4 does and add it to the request as `voice_id` |
| A key in `needs_grant` while `features` lacks `controls.advanced` | Remove it from the request and say so in the summary |

## Step 4: Show the Summary and Get a Go-Ahead

```
READY TO EXTEND — [NN] [Title], take 2

  Keeps      take 2 up to 2:10 (of 2:31)
  Then       Verse 3 to the end of the Lyrics Box
  Style      the track's own, Variety Off
  Makes      2 continuations, each joined into a whole song (joining is free)
  Cost       about 10 song credits (20 with Max Mode). You have 9,853.
  After      open both whole songs (free) and check them.

Go ahead?   yes · without Max Mode · cancel
```

- `credits` in the tool's answer is the estimate. Name Max Mode when the request holds it; "without Max Mode" removes `max_mode`.
- Wait for an explicit yes. Silence is not a yes.

## Step 5: Send It and Join

1. Fix an idempotency key before the first attempt: `{album_slug}/{track_slug}/extend/{UTC timestamp}`.
2. Call `audio-extensions-create` with the keys of `request`, the `voice_id` if there is one, and the `idempotency_key`. Add nothing: a `duration` would cap the new ending.
3. The answer carries two ids in `clip_ids`, one continuation each. Call `audio-wait` with both and `until: "complete"`; call it again while either is pending.
4. Join each one: `audio-full-song(id: <continuation id>)` with its own idempotency key (`…/join-1/…`, `…/join-2/…`). Each answer is a new song id; `audio-wait` for both. Suno's tool text says to join the one you want. Joining both is what lets the user compare whole songs, costs nothing, and was measured to work.
5. If the album has a workspace (`request.workspace_id`), file the two joined songs in it: `workspaces-update-clips(id: <that id>, add: [<both joined ids>])`. The continuations are filed already; a joined song is not.
6. Call `account-usage` again. Credits spent = balance before − balance after.

Failures are handled as in `/bitwize-music:generate` Step 6. If one join fails, say so and log the other whole song; `audio-full-song` may be asked again for the same continuation up to three times.

## Step 6: Log and Hand Off

1. `log_generation(album_slug, track_slug, <the track's model>, clips, notes: "<log_notes from the tool>, via MCP, N credits")` with the two **joined** songs: their ids, status and length. The continuations alone are not logged — nobody keeps half a song.
2. Report:

   ```
   EXTENDED — [NN] [Title], take 2 from 2:10

     Take 5 (row 5)   3:40   https://suno.com/song/...
     Take 6 (row 6)   3:44   https://suno.com/song/...

     Spent 10 song credits. 9,843 left.
   ```

3. Continue into `/bitwize-music:listen` for the two new rows — tell the user to listen across the join, and give its time — then `/bitwize-music:check-take` for them, as `/bitwize-music:generate` Step 8 does.

The track's status does not change, and the original take stays in the log. If the user keeps an extended take, approval works as always (`/bitwize-music:listen` Step 7).

## Remember

1. **An extension is a generation**: cost first, then a go-ahead, then one call.
2. **Carry on from the end of a line.** The middle of a phrase leaves a cut that can be heard.
3. **The words come from the Lyrics Box**, so they have been checked. New words are written there first.
4. **Join both continuations and log the whole songs.** Joining is free.
5. **You never pick a take, mark a keeper or set `Final`.**
