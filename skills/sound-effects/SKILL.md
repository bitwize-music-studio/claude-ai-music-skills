---
name: sound-effects
description: Makes a sound effect, a one-shot or a loop for an album through Suno's MCP server - rain for an intro, a riser, a vinyl crackle bed, a drum loop at a track's tempo. Shows the cost and waits for a go-ahead. Use when the user asks for "a sound of...", "an ambience", "a loop", "a sting" or "a sound effect" rather than a song.
argument-hint: <album-name> "<what the sound is>" [--loop] [--fit <track>] [--title "<name>"]
model: sonnet
effort: low
allowed-tools:
  - Read
  - Bash
  - bitwize-music-mcp
  - mcp__suno__*
---

## Your Task

**Input**: $ARGUMENTS

Make a short sound for an album through Suno's MCP server: build the request, show what it costs, get a go-ahead, send it, file the two sounds, and let the user hear them.

You never choose between the two sounds. The user listens and decides.

---

# Sound Effects Skill

Suno's Sounds makes short audio from a description — an effect, a one-shot or a seamless loop, not a song. One call makes **two** sounds of about 20 seconds and costs **1 song credit each** (measured).

The two can differ in kind. Measured: asked for "soft rain on a window", one was rain and the other had a piano melody in it. Both get heard before either is used. Background: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Sounds.

## Step 1: Resolve

Expected format: `<album-name> "<what the sound is>" [--loop] [--fit <track>] [--title "<name>"]`

- The description says what is heard, in a few plain words: "rain on a tin roof", "vinyl crackle", "a single wooden door knock", "boom bap drums". To keep music out of an effect, say so: "rain on a window, no music".
- `--loop` asks for a seamless loop; without it the sound is a one-shot.
- `--fit <track>` gives the sound that track's tempo and key. Use it for musical material: a drum loop, a bass riff, a riser. Leave it off for an effect or an ambience — a tempo and a key pull the result toward music.

## Step 2: Check the Suno Server

Follow § Preflight in the reference doc: find `sounds-create`, `audio-wait` and `account-usage`, load their current definitions, and read `account-usage`. Not connected → say this needs Suno's MCP server and stop; on suno.com it is Sounds. Suno offers Sounds from the Pro plan up.

## Step 3: Build the Request

`get_sound_request(album_slug, description, loop, fit_track, title)`.

- `found: false`, or a blocking problem → show it and stop.
- `nothing_to_fit` (a warning) → the track names no tempo and no key. Say so and carry on unfitted.

## Step 4: Show the Summary and Get a Go-Ahead

```
READY TO MAKE A SOUND — [Album]

  Sound      rain on a window, no music
  Kind       loop
  Fitted     96 BPM, G (from 03 Third Track)
  Makes      2 sounds of about 20 seconds
  Cost       2 song credits. You have 9,841.
  After      open both (free).

Go ahead?   yes · cancel
```

Leave out **Fitted** when nothing is fitted. Wait for an explicit yes. Silence is not a yes.

## Step 5: Send It

1. Fix an idempotency key before the first attempt: `{album_slug}/sound/{UTC timestamp}`.
2. Call `sounds-create` with the keys of `request` and the `idempotency_key`. Add nothing.
3. Two ids come back in `clip_ids`. Call `audio-wait` with both and `until: "complete"`.
4. `sounds-create` takes no workspace. If the tool's answer had a `workspace`, file the two there: `workspaces-update-clips(id: <workspace.id>, add: [<both ids>])`. Filing is free.
5. Call `account-usage` again. Credits spent = balance before − balance after.

## Step 6: Let the User Hear Them

Report both, and open their song pages with `open_song_page`, as `/bitwize-music:listen` opens takes — that is free:

```
SOUNDS — rain on a window (loop)

  1   0:20   https://suno.com/song/...
  2   0:20   https://suno.com/song/...

  Spent 2 song credits. 9,839 left.
```

If the user wonders what one of them holds, Suno's listening agent says for free: `audio-listen(id, question: "What is heard in this clip? Is there any music or voice in it?")`, then `audio-listen-wait`.

## Step 7: Save One (on Request)

When the user wants a sound on disk, download it as `/bitwize-music:import-audio` § Importing From Suno step C does: `audio-download(id, format: "wav")` without `confirm` first. A `requires_credit` answer needs the user's yes, because it spends a download credit. Save it to the matching path in `save.files` — `sounds/` under the album's audio folder, which the mastering tools never read.

Nothing in the plugin mixes a sound into a track. The file is for a DAW or a video edit.

## Remember

1. **Cost first, then a go-ahead, then one call.** Two sounds, two credits.
2. **Hear both.** They can differ in kind.
3. **Fit only musical material to a track.**
4. **You never choose between them.**
