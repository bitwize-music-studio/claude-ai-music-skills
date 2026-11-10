---
name: generate
description: Generates a track on Suno through Suno's official MCP server. Runs the pre-generation gates, shows the cost, waits for a go-ahead, makes two takes, logs them and hands off to listening. Use when the user says "generate track N", "regenerate", or is ready to make audio. Falls back to the clipboard flow when the Suno server is not connected.
argument-hint: <album-name> <track-number-or-slug> [--no-listen]
model: sonnet
effort: medium
prerequisites:
  - suno-engineer
allowed-tools:
  - Read
  - Edit
  - bitwize-music-mcp
  - mcp__suno__*
---

## Your Task

**Input**: $ARGUMENTS

Generate one track on Suno through the Suno MCP server: check the gates, show what it will cost, get a go-ahead, generate, log the takes, and hand off to listening.

You never choose a take, mark one as the keeper, set a track `Final` or publish a song. The user listens and decides.

---

# Generate Skill

You run the generation hop — the one step that used to mean leaving the terminal for suno.com.

```
pre-generation-check → generate → listen → [user picks the keeper] → import-audio --from-suno
                          ↑
                    You are here
```

Setup, costs, the track-file mapping and the tool notes are in `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md`. Read it before your first Suno call in a session.

## Step 1: Resolve the Track

Expected format: `<album-name> <track-number-or-slug> [--no-listen]`

If arguments are missing, show:

```
Usage: /generate <album-name> <track> [--no-listen]

Example: /generate sample-album 03
```

One track per run. If the user asks for several, do them one at a time — each gets its own summary and its own go-ahead.

## Step 2: Run the Gates

Call `run_pre_generation_gates(album_slug, track_slug)`.

- **Any blocking gate failed** → show the failed gates and the fix for each, then stop. You fix nothing yourself.
- **Warnings only** → show them and continue.

## Step 3: Check the Suno Server

Follow § Preflight in `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md`:

1. Find `audio-create`, `audio-wait` and `account-usage` on a connected MCP server. Load their definitions now; do not rely on a parameter list you remember.
2. Not connected or not signed in → show the **Fallback** below and stop.
3. Call `account-usage` and keep `allowed_models`, `features`, `suno_account.credits_remaining` and `suno_account.download_credits_remaining`.

## Step 4: Build the Request

Call `get_generation_request(album_slug, track_slug)`.

| Result | Do |
|--------|-----|
| `found: false` | Report the error and stop |
| `supported: false` | List the blocking problems and stop. For `custom_model_unsupported`, show the **Fallback** |
| `track_status` is `Final` | Say the track already has an approved take and ask whether to regenerate. Stop unless the answer is yes |
| `request.model` is not in `allowed_models` | Say the plan does not include that model and stop |
| A key in `needs_grant` while `features` lacks `controls.advanced` | Remove that key from the request and remember to say so in the summary |
| Warnings in `problems` | Show them and continue |

Also call `get_listen_plan(album_slug, track_slug)` and keep `mode`, `confirm_download`, `player` and `iterm2` for the summary.

## Step 5: Show the Summary and Get a Go-Ahead

Nothing has been spent yet. Show exactly what will be sent and what it costs:

```
READY TO GENERATE — [NN] [Title]  ([album])

  Model      v6
  Takes      2 (one call always makes two)
  Max Mode   On — costs a multiple of the usual credits (2× on suno.com)
  Sliders    Weirdness 50 · Style Influence 50
  Duration   Auto
  Exclude    choir, crowd vocals
  Not sent   Variety High — no API equivalent; the Style Box is used as written
  Dropped    vocal_gender — your plan lacks advanced controls

  Cost       about 10 song credits (20 with Max Mode). You have 9,935.
  Then       open both takes in your browser (free).
             (Playing them here instead uses 2 download credits. You have 66.)

Go ahead?   yes · generate only · play here instead · without Max Mode · cancel
```

Rules for the summary:

- Leave out any line that does not apply (no Max Mode, nothing excluded, nothing dropped).
- **Max Mode** appears only when the request holds `max_mode: true`. Suno asks that Max Mode be turned on only at the user's request, so the user's yes to a summary that names it *is* that request. If they answer "without Max Mode", remove `max_mode` and proceed.
- **Then** follows the listen plan:
  - `--no-listen` → leave the line out.
  - `mode` is `browser` (the default) → the browser line above. Drop the "playing them here" note, and the "play here instead" answer, when `player` is null or fewer than 2 download credits are left.
  - `mode` is `iterm2_browser` and the plan's `iterm2.available` is true → the same line with "beside this session, in iTerm2 panes" in place of "in your browser". The note and the "play here instead" answer follow the browser rule.
  - `mode` is `iterm2_browser` but `iterm2.available` is false → the browser line above, with the plan's `iterm2.reason` in a clause.
  - `mode` is `terminal` → "play both takes here: 2 download credits. You have N. (Opening them in the browser instead is free.)", with "browser instead" among the answers.
  - `mode` is `terminal` but `player` is null → "open both takes in your browser (free) — no audio player is installed; install mpv to play here".
  - `mode` is `terminal` and fewer than 2 download credits are left → "open both takes in your browser (free) — you have N download credits left".
- A yes covers exactly what the **Then** line says. Terminal playback spends download credits only when the summary said so or the user answered "play here instead".
- Wait for an explicit answer. Silence is not a yes.

## Step 6: Generate

1. Fix an idempotency key **before** the first attempt: `{album_slug}/{track_slug}/{UTC timestamp}`, for example `sample-album/03-t-day-beach/2026-06-15T12:00:00Z`.
2. Call `audio-create` with the keys of `request` and the `idempotency_key`. Add nothing else.
3. The answer carries two ids in `clip_ids`. Tell the user the takes are generating.
4. Call `audio-wait` with every id in `ids` and `until: "complete"`. It returns after about 50 seconds whether or not the songs are finished; call it again while any is still pending. A song usually takes one to three minutes.
5. Call `account-usage` again. Credits spent = balance before − balance after.

| What happened | Do |
|---------------|-----|
| No response or a timeout from `audio-create` | Retry **once** with the **same** idempotency key |
| The call is rejected for an unknown argument | Remove that argument, tell the user, and retry once with a **new** key (the arguments changed) |
| `402` — out of credits | Call `account-upgrade`, show its link, and stop. Log nothing |
| `403` — model or feature not on the plan | Name what is missing. Offer to retry without it when it is `max_mode`, `controls`, `negative_style` or `vocal_gender`; otherwise show the **Fallback** |
| `400` — Suno's content check rejected the title, lyrics or style | Show Suno's message word for word and stop. The track's status does not change |
| One take ends with `status: error` | Log it as failed in Step 7 and carry on with the other |

Never call `audio-create` a second time for the same go-ahead except as the table says. Each successful call spends credits.

## Step 7: Log the Takes

Call `log_generation(album_slug, track_slug, model, clips, notes)`:

- `model` — the model that was sent (`default` if none was).
- `clips` — one entry per clip id: `{"clip_id": ..., "status": "complete" or "error", "duration_s": the clip's metadata.duration, "error": the reason for a failed take}`.
- `notes` — `via MCP, N credits`, plus `, Max Mode` when it was used.

Then, unless the track is already `Generated`: `update_track_field(album_slug, track_slug, "status", "Generated")`.

## Step 8: Report and Hand Off

```
GENERATED — [NN] [Title]

  Take 1 (row 3)   3:14   https://suno.com/song/...
  Take 2 (row 4)   3:20   https://suno.com/song/...

  Spent 10 song credits. 9,925 left.
```

Then continue straight into `/bitwize-music:listen` for those two rows, in the way chosen in Step 5. If that was the terminal, the download credits were approved there — do not ask again.

Skip the hand-off when the user passed `--no-listen` or answered "generate only".

## Approving a Take

Approval is the user's call and is not part of generating. When they name the keeper, now or later:

1. In the track file, change that Generation Log row's Rating from `—` to `✓`.
2. `update_track_field(album_slug, track_slug, "suno-link", "<that take's URL>")`
3. `update_track_field(album_slug, track_slug, "status", "Final")`
4. Offer `/bitwize-music:import-audio --from-suno <album> <track>`. It is free for a take that was played in the terminal.

When they reject both takes, add the reason to the Notes of those rows, then follow the Regeneration Workflow in CLAUDE.md: a style problem goes to `/bitwize-music:suno-engineer`, a lyrics problem to `/bitwize-music:lyric-writer`, and plain bad luck is another `/generate`.

## Fallback

When the Suno server is not connected, or the track needs something it does not offer:

```
I can't generate this one from here: [reason].

To connect Suno (one time):
  claude mcp add --transport http suno https://api.suno.com/mcp
  then run /mcp and sign in

Or generate it on suno.com now:
  /bitwize-music:clipboard suno [album] [track]
```

## Remember

1. **Gates, then cost, then a go-ahead** — in that order, every time.
2. **One call makes two takes and spends credits.** One go-ahead covers one call.
3. **Send only what `get_generation_request` returned.** The mapping lives in that tool, not in your head.
4. **The live tool definition wins.** Suno's server is in beta and its arguments change.
5. **You never pick a take, mark a keeper, set `Final` or publish.** A human listens first.
