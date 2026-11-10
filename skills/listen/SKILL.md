---
name: listen
description: Opens a track's Suno takes in the browser or in iTerm2 panes beside the session, or plays takes and local audio in the terminal. Use when the user wants to hear a take, compare takes, audition a generation, or says "play it" or "let me hear it". Opening the song page is the default and is free; playing a new Suno take in the terminal uses one download credit.
argument-hint: <album-name> <track> [take N | all] [--browser | --iterm2 | --terminal] [--from m:ss] [--stage original|polished|mastered]
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

Let the user hear a track: open its Suno takes in the browser or in iTerm2 panes beside this session, or play takes and local audio through the computer's speakers. Then ask which take they want to keep.

You never choose a take. Audio never passes through you — you start a player and report what is playing.

---

# Listen Skill

For Suno takes the browser is the default, because listening on the song page is free. Two other ways are there for the asking, for one run or as the user's standing choice in `generation.listen_mode`:

- **iTerm2 panes** (`--iterm2`, or `listen_mode: iterm2_browser`) — Suno's compact player for each take, in panes beside this session, with the track's lyrics in a pane under them, so the user never leaves the terminal window. Free, like the browser. Needs macOS, iTerm2 3.6 or later and iTerm2's Browser Plugin.
- **Terminal** (`--terminal`, or `listen_mode: terminal`) — the take plays through the speakers from here, for one download credit.

Both fall back to the browser whenever they cannot be used. Local files always play in the terminal.

## What Listening Costs

Suno has no free audio feed for a terminal player, so playing a take here means downloading it.

| Way to listen | Cost |
|---------------|------|
| Song page in the browser | Free, unlimited |
| Compact player in an iTerm2 pane | Free, unlimited |
| A take in the terminal, first time | 1 Suno download credit |
| The same take again | Free (it is cached) |
| A file already on disk (imported, polished, mastered) | Free |
| Comparing files already on disk, passage by passage | Free |

The take that is kept needs that download credit anyway — its WAV import is then free. Only rejected takes played in the terminal cost extra. Details: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md`.

## Step 1: Work Out What to Play

Expected format: `<album-name> <track> [take N | all] [--browser | --iterm2 | --terminal] [--from m:ss] [--stage original|polished|mastered]`

Call `get_listen_plan(album_slug, track_slug)`.

**Target**
- `take N` or `all` → those rows of `takes`.
- `--stage X` → `local[X]`. If it is null, say there is no such file yet and stop.
- Neither → `default`:
  - `kind: "takes"` → those rows (the takes awaiting a decision).
  - `kind: "local"` → that file.
  - `kind: "none"` → "Nothing to play yet — generate the track first with `/bitwize-music:generate`." Stop.

**How**
- `--browser`, `--iterm2` or `--terminal` wins; otherwise use `mode` from the plan (`browser` unless the user's config says `iterm2_browser` or `terminal`).
- Local files always play in the terminal.
- A take whose `clip_id` is null is a share link from before MCP generation: it can be opened in the browser or in an iTerm2 pane, never played in the terminal.
- Terminal mode with `player: null` → say no audio player is installed (`brew install mpv`, or see the reference doc), then use the browser for takes.
- iTerm2 mode needs no check of your own: when the panes cannot be used, `open_song_page` opens the browser instead and says why.

## Step 2: Browser Mode and iTerm2 Mode

Call `open_song_page(urls)` with the chosen takes' `url`s (at most four), in take order. For iTerm2 mode add `where="iterm2_browser"`, `album_slug` and `track_slug`: the track's Lyrics Box then opens in one more pane under the takes. Leave the track out when the takes are instrumental versions.

The answer's `where` says where the takes went:

- `browser` → say which takes are open in the browser.
- `iterm2_browser` → each take is open as a compact player in a pane to the right of this session, the first take on top. Say which take is where, and that each needs one click on its play button — a browser never starts sound by itself:

  ```
  Both takes are open beside this session: take 1 on top, take 2 under it,
  and the lyrics below them. Click play on each one.
  ```

  `lyrics_pane: true` → the lyrics pane is open. It is plain text from the track file, not timed to the music, so never say it follows the song. The user scrolls it with the mouse wheel or the arrow keys, and `q` closes that pane alone. `lyrics_pane: false` → say why in a few words, from `lyrics_note` (for example, the Lyrics Box has no lyrics yet). An instrumental track needs no mention.

- `note` → the panes could not be used, so the takes went to the browser. Pass the reason on; it names the fix when there is one (for example, installing iTerm2's Browser Plugin).
- `failed` → no browser could be launched here; print those links for the user to open.

Opening panes again replaces the ones already open. All of this costs nothing and needs no Suno server. Go to Step 7.

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
| "compare", "compare from 0:45" | `compare_audio([<the paths, in take order>], start_s, length_s: 15)` — the same passage of each, back to back. Say what plays in which order. Needs the files on disk (cached takes or local stages) and `mpv` |
| "browser" | `stop_audio`, then Browser Mode |
| "beside me", "in iTerm2" | `stop_audio`, then iTerm2 Mode |
| "close the players" | `close_song_panes` |
| "keep take N", "neither" | Step 7 |

## Step 7: After Listening

When the user has heard the takes, ask which one to keep, or whether to regenerate. Do not recommend one. If they wonder whether a take sang every line or hit the tempo, `/bitwize-music:check-take` asks Suno's listening agent for free.

**The take they name is a version** (its `version` in the listen plan is `instrumental`): change that row's Rating to `✓` and stop there. A version is kept beside the track, so the Suno Link, the status and the like stay as they are. Offer `/bitwize-music:import-audio --from-suno <album> <track> --version instrumental`.

**They name a keeper:**

1. `stop_audio` if something is still playing, and `close_song_panes` if the takes were opened in iTerm2 panes.
2. In the track file, change that Generation Log row's Rating from `—` to `✓`.
3. `update_track_field(album_slug, track_slug, "suno-link", "<that take's URL>")`
4. `update_track_field(album_slug, track_slug, "status", "Final")`
5. If the listen plan's `like_keeper` is true and the take has a `clip_id`, call `audio-like(id: <clip_id>)` so the keeper shows as liked on suno.com. If a different take of this track carried the ✓ before, clear its like with `audio-unlike`. Never dislike a rejected take: a dislike is a rating only the user gives, it feeds Suno's taste profile, and it deletes nothing.
6. `prune_takes_cache(dry_run: false)` — the audition copies of a track that now has a keeper are no longer needed. Skip it when nothing was played in the terminal.
7. Offer `/bitwize-music:import-audio --from-suno <album> <track>`. It is free for a take that was played in the terminal.

**They reject them all:** `close_song_panes` if the takes were opened in iTerm2 panes. Add the reason to the Notes of those rows, then follow the Regeneration Workflow in CLAUDE.md — a style problem goes to `/bitwize-music:suno-engineer`, a lyrics problem to `/bitwize-music:lyric-writer`, bad luck is another `/bitwize-music:generate`.

**They have not decided:** leave everything as it is, open panes included.

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

**iTerm2 panes cannot be used** (the answer carries a `note`): the takes are already open in the browser. Say so, with the reason:
```
iTerm2 panes aren't available here ([reason]), so both takes are open in your browser instead.
```

## Remember

1. **Browser first for takes; iTerm2 panes or the terminal on request** — and both fall back to the browser whenever they cannot be used.
2. **One credit question per batch.** Never send `confirm: true` without a yes, a go-ahead from `/generate`, or `confirm_download: false`.
3. **A cached take replays free** — no Suno call, no question.
4. **Space out download calls** by about two seconds; Suno refuses bursts.
5. **You never pick the take.** Ask, then record what the user chose. A like on suno.com follows the user's choice; it never comes first.
6. **Close the player panes once the user has decided** — not before.
