---
name: suno-voice
description: Puts one of the user's saved Suno Voices on a track or a whole album so /bitwize-music:generate sings in it, takes it off again, lists the Voices on their Suno account, or gives them Suno's link to make a new one. Checks the Voice exists first; nothing is generated or charged. Use when the user says "use my <name> voice", "sing this album in <Voice>", "what voices do I have", "take the voice off track 3" or "make a new voice".
argument-hint: list | <album-name> [<track>] "<Voice name>" | <album-name> [<track>] --off | create
model: sonnet
effort: low
allowed-tools:
  - Read
  - bitwize-music-mcp
  - mcp__suno__*
---

## Your Task

**Input**: $ARGUMENTS

Work with the user's saved Suno Voices: list them, put one on a track or an album, take one off, or hand over Suno's link for making a new one.

Nothing here generates or costs anything. The Voice sings at the next `/bitwize-music:generate` of the track, at that command's usual cost.

---

# Suno Voice Skill

A track sings in a saved Voice when the **Voice** row of its `## Cover / Voice Setup` block names it (`templates/track.md` § Voice Selection). `/bitwize-music:generate` reads that row and finds the Voice's id on the user's Suno account. Background: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Covers and Voices.

## Step 1: Resolve

- `list` (or "what voices do I have") → Step 3.
- `create` (or "make a new voice") → Step 6.
- `<album> [<track>] "<Voice>"` → Step 4. No track means every track of the album that has lyrics.
- `<album> [<track>] --off` (or "take the voice off") → Step 5.

## Step 2: Check the Suno Server

Follow § Preflight in the reference doc: find `voices-list`, `voices-start` and `account-usage` on the connected Suno server, load their current definitions, and read `account-usage` once.

- Not connected → say a Voice is checked against the Suno account through Suno's MCP server, give the setup command from § Preflight, and stop.
- `features` lacks `voices` → say Suno's Voices need a Pro or Premier plan, and stop.

Taking a Voice off (Step 5) needs none of this.

## Step 3: List the Voices

`voices-list` (the user's own Voices, newest first). Show the names on one line each, no more than 20:

```
Your Voices on Suno (newest first):
  RTB · Missed Connections · ASCII · Mac · TayTay · Player Two
```

`next_cursor` set → say there are more and offer the next page. Voices they loved on suno.com are in `collection: "loved"`; show those when asked.

## Step 4: Put a Voice on a Track or an Album

1. **Find it.** `voices-list(query: <name>)`. Nothing → once more with `collection: "loved"`.
2. **Choose.** One match, or one whose name is exactly the one asked for (ignoring case) → that Voice. Several otherwise → show their names and ask which. None → say it is not on their Suno account and show their Voices (Step 3) so they can pick one. They can also make one with `/bitwize-music:suno-voice create` — say so, but do not call `voices-start` unless they ask.
3. **Write it.** `set_track_voice(album_slug, voice, track_slug, saved_from, vocal_identity)`:
   - `voice`: the Voice's `name`. Use its `id` instead when another of their Voices has the same name, or when the Voice is a public one found by id, so `/generate` finds exactly this Voice.
   - `saved_from`: `https://suno.com/song/<root_clip_id>` when `voices-list` gave a `root_clip_id`.
   - `vocal_identity`: the Voice's `description` when it has one.
   - `track_slug`: empty for the whole album.
4. **Report.**
   ```
   Track 03 now sings in RTB. The next /bitwize-music:generate uses it
   (10 credits for two takes, as usual). Takes made earlier keep their voice.
   ```
   For an album, name the tracks it went on, and the instrumental tracks it skipped. An `error` (an instrumental track, an unknown track) → show it.

A Voice carries its own gender, so the track's Vocal Gender is not sent with it. A Voice made on an older Suno model may need "Upgrade Voice to v6" on suno.com before it sings well.

## Step 5: Take a Voice Off

`set_track_voice(album_slug, "—", track_slug)`. The track then sings in the voice its Style Box describes. Say which tracks changed; `unchanged` ones had no Voice.

## Step 6: Make a New Voice

Only when the user asks for one.

1. Call `voices-start`. It takes no arguments.
2. A `url` comes back → give it to the user:
   ```
   Make your Voice on suno.com: <url>
   Record and verify it there. When it's ready, tell me its name and the
   track or album to use it on.
   ```
3. No `url` → say what Suno answered and stop. An account signed in with an API key gets a 409; Voices are made by a user signed in on suno.com.

Never ask the user for recordings or audio files: Suno takes them on that page. Once the Voice is ready it appears in `voices-list`, and Step 4 puts it on a track.

## Remember

1. **Check before writing** — a Voice goes in a track file only after `voices-list` has found it.
2. **Free** — nothing here generates or charges. Singing happens at `/generate`, with its own cost and go-ahead.
3. **The user names the Voice** — never pick one for them; with several matches, ask.
4. **`voices-start` only on request** — when a Voice is missing, offer it; call it only when they want to make one.
