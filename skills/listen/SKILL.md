---
name: listen
description: Plays a track's Suno takes or local audio in the terminal, or opens the song page in the browser. Use when the user wants to hear a take, compare takes, audition a generation, or says "play it" or "let me hear it". Playing a new Suno take in the terminal uses one download credit; the browser is free.
argument-hint: <album-name> <track> [take N | all] [--browser | --terminal] [--from m:ss] [--stage original|polished|mastered]
model: sonnet
effort: medium
allowed-tools:
  - Read
  - Edit
  - Bash
  - bitwize-music-mcp
  - mcp__suno__*
---

## Your Task

**Input**: $ARGUMENTS

Let the user hear a track: play its Suno takes or its local audio through the computer's speakers, or open the takes in the browser. Then ask which take they want to keep.

You never choose a take. Audio never passes through you — you start a player and report what is playing.

---

# Listen Skill

The terminal is the default. The browser is the alternative the user can ask for, and the fallback when the terminal cannot be used.

## What Listening Costs

Suno has no free audio feed for a terminal player, so playing a take here means downloading it.

| Way to listen | Cost |
|---------------|------|
| Song page in the browser | Free, unlimited |
| A take in the terminal, first time | 1 Suno download credit |
| The same take again | Free (it is cached) |
| A file already on disk (imported, polished, mastered) | Free |

The take that is kept needs that download credit anyway — its WAV import is then free. Only rejected takes played in the terminal cost extra. Details: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md`.

## Step 1: Work Out What to Play

Expected format: `<album-name> <track> [take N | all] [--browser | --terminal] [--from m:ss] [--stage original|polished|mastered]`

Call `get_listen_plan(album_slug, track_slug)`.

**Target**
- `take N` or `all` → those rows of `takes`.
- `--stage X` → `local[X]`. If it is null, say there is no such file yet and stop.
- Neither → `default`:
  - `kind: "takes"` → those rows (the takes awaiting a decision).
  - `kind: "local"` → that file.
  - `kind: "none"` → "Nothing to play yet — generate the track first with `/bitwize-music:generate`." Stop.

**How**
- `--browser` or `--terminal` wins; otherwise use `mode` from the plan.
- Local files always play in the terminal.
- A take whose `clip_id` is null is a share link from before MCP generation: it can only be opened in the browser.
- Terminal mode with `player: null` → say no audio player is installed (`brew install mpv`, or see the reference doc), then use the browser for takes.

## Step 2: Browser Mode

Call `open_song_page(urls)` with the chosen takes' `url`s (at most four).

- `opened` → say which takes are open in the browser.
- `failed` → no browser could be launched here; print those links for the user to open.

This costs nothing and needs no Suno server. Go to Step 7.

## Step 3: Terminal Mode — Local File or Cached Take

A local file, or a take with `cached: true`, plays at once: `play_audio(path, start_s)` with the file path or the take's `cache_path`. Go to Step 5.

## Step 4: Terminal Mode — Take Not Cached Yet

1. Run § Preflight in `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md`. If the Suno server is not available, say so and use Browser Mode.
2. For each take to play that is not cached, call `audio-download(id: <clip_id>, format: "mp3")` **without** `confirm`. Leave about two seconds between download calls.

   | Answer | Do |
   |--------|-----|
   | `status: "ok"` | Free. Save it now (step 4) |
   | `status: "requires_credit"` | Count it. Ask the credit question (step 3) before going further |
   | `status: "processing"` | Call `audio-download` again |
   | `rate_limited` | Wait `retry_after_seconds`, then call again |
   | Any other refusal | Report it and use Browser Mode for the takes not saved yet |

3. **The credit question.** Ask once for all the takes that answered `requires_credit`:

   ```
   Playing 2 takes here downloads them: 2 of your 66 download credits.
   (The take you keep needs its credit anyway. Opening them in the browser is free.)

   Play here, or open in the browser?
   ```

   - Skip the question when the go-ahead in `/bitwize-music:generate` already covered these takes, or when `confirm_download` is `false` — then just report the credits used and left afterwards.
   - Fewer download credits left than takes to play → say so and use Browser Mode.
   - On yes: call `audio-download` again for each of those takes with `confirm: true`.

4. **Save each link** to the take's `cache_path`, exactly as the plan gave it:

   ```bash
   mkdir -p "$(dirname "{cache_path}")" \
     && curl -fsSL --max-time 300 -o "{cache_path}.part" "{url}" \
     && mv "{cache_path}.part" "{cache_path}"
   ```

   Quote the URL — it contains `&`. Links last an hour, so save right away. If `curl` fails, remove the `.part` file, report the error and offer the browser.

5. Play the first take: `play_audio(cache_path, start_s)`.

## Step 5: Report What Is Playing

`play_audio` returns as soon as the player has started. Report, then end your turn — the audio keeps playing.

```
▶ Take 1 of 2 — [Title] (3:14), playing in mpv

  Say:  next · stop · from 1:30 · browser

  For keyboard control, run it yourself in another terminal tab:
    [command from play_audio]
```

Pass on anything in `warnings` (for example, `afplay` cannot start mid-song).

`--from m:ss` is `start_s` in seconds.

## Step 6: Follow-ups

| The user says | Do |
|---------------|-----|
| "next", "play take 2" | `play_audio` with that take's `cache_path` — it is already saved, so no Suno call |
| "stop" | `stop_audio` |
| "from 1:30" | `play_audio(path, start_s=90)` on what was playing |
| "resume" | `stop_audio` reported `position_s` — `play_audio(path, start_s=<that>)` |
| "browser" | `stop_audio`, then Browser Mode |
| "keep take N", "neither" | Step 7 |

## Step 7: After Listening

When the user has heard the takes, ask which one to keep, or whether to regenerate. Do not recommend one.

**They name a keeper:**

1. `stop_audio` if something is still playing.
2. In the track file, change that Generation Log row's Rating from `—` to `✓`.
3. `update_track_field(album_slug, track_slug, "suno-link", "<that take's URL>")`
4. `update_track_field(album_slug, track_slug, "status", "Final")`
5. Offer `/bitwize-music:import-audio --from-suno <album> <track>`. It is free for a take that was played in the terminal.

**They reject them all:** add the reason to the Notes of those rows, then follow the Regeneration Workflow in CLAUDE.md — a style problem goes to `/bitwize-music:suno-engineer`, a lyrics problem to `/bitwize-music:lyric-writer`, bad luck is another `/bitwize-music:generate`.

**They have not decided:** leave everything as it is.

## Error Handling

**No audio player installed:**
```
No audio player found, so I can't play this here.
Install one (macOS: brew install mpv), or I can open the take in your browser.
```

**No takes and no local audio:**
```
Nothing to play for [track] yet. Generate it first: /bitwize-music:generate [album] [track]
```

**Suno refused the download** (`quota_exhausted`, `daily_limit_exceeded`, `plan_required`): say what Suno said and open the take in the browser instead.

## Remember

1. **Terminal first, browser on request** — and the browser is the fallback whenever the terminal cannot be used.
2. **One credit question per batch.** Never send `confirm: true` without a yes, a go-ahead from `/generate`, or `confirm_download: false`.
3. **A cached take replays free** — no Suno call, no question.
4. **Space out download calls** by about two seconds; Suno refuses bursts.
5. **You never pick the take.** Ask, then record what the user chose.
