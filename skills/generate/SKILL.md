---
name: generate
description: Generates a track on Suno through Suno's official MCP server - a song, a cover of another Suno song, a track sung in a saved Voice, a spoken-word piece, or a sketch that plays a MIDI score. Runs the pre-generation gates, shows the cost, waits for a go-ahead, makes two takes, logs them and hands off to listening. Use when the user says "generate track N", "regenerate", or is ready to make audio. Falls back to the clipboard flow when the Suno server is not connected.
argument-hint: <album-name> [track-number-or-slug] [--midi [file]] [--no-listen] [--no-check]
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

Expected format: `<album-name> [track-number-or-slug] [--midi [file]] [--no-listen] [--no-check]`

If arguments are missing, show:

```
Usage: /generate <album-name> <track> [--midi [file]] [--no-listen] [--no-check]

Example: /generate sample-album 03
```

`--midi` makes the track from a MIDI file: see **From a MIDI Score** before Step 4.

With a track, this run generates that one track. With an album and no track, go to **Album Mode** below: every track that is ready, after one summary and one go-ahead. If the user names a few tracks, do them one at a time — each gets its own summary and its own go-ahead.

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

Call `get_generation_request(album_slug, track_slug)`. It reads what kind of request the track makes and names the Suno tool to send it to in `tool`: a song (`audio-create`), a cover (`audio-covers-create`) or spoken word (`speech-create`). The differences are under **Covers, Voices and Spoken Tracks**.

| Result | Do |
|--------|-----|
| `found: false` | Report the error and stop |
| `supported: false` | List the blocking problems and stop. For `custom_model_unsupported` or `cover_source_not_on_suno`, show the **Fallback** |
| `tool` is not `audio-create` | Find that tool and load its definition as in Step 3. `features` lacks `generate.cover` (a cover) or `speech` (spoken word) → say the plan does not include it and stop |
| `voice` is set | `voices-list(query: <voice.name>)`; nothing found → once more with `collection: "loved"`. One match, or one whose name is exactly the Voice's → add its `id` to the request as `voice_id`. Several otherwise → ask which. None, or `features` lacks `voices` → name the Voice, say it was not found on the Suno account, point to `/bitwize-music:suno-voice` (it lists their Voices, and gives Suno's link to make a new one when they ask), and stop |
| `track_status` is `Final` | Say the track already has an approved take and ask whether to regenerate. Stop unless the answer is yes |
| `request.model` is not in `allowed_models` | Say the plan does not include that model and stop |
| A key in `needs_grant` while `features` lacks `controls.advanced` | Remove that key from the request and remember to say so in the summary. A dotted name such as `controls.weirdness` is a key inside `controls`; `controls.variety` is never listed and stays |
| Warnings in `problems` | Show them and continue |

Also call `get_listen_plan(album_slug, track_slug)` and keep `mode`, `confirm_download`, `player` and `iterm2` for the summary.

## Step 4b: The Album's Workspace

Each album's takes live in a Suno workspace of their own, so they are easy to find on suno.com. Call `get_album_workspace(album_slug)`. Skip this step when `enabled` is false (`generation.suno_workspaces: false` in the config).

- `workspace` set → call `workspaces-list(query: <workspace.name>)` and look for `workspace.id` among the answers. Found → `request.workspace_id` is already set; nothing more to do. Not found → the workspace was deleted on suno.com: say so and offer "create it again" or "carry on without". Never recreate it silently. For "carry on without", drop `workspace_id` from `request` for this run.
- `workspace` null → plan to create one in Step 6: keep `suggested_name` and `batches`, and add the **Workspace** line to the summary.

## Step 5: Show the Summary and Get a Go-Ahead

Nothing has been spent yet. Show exactly what will be sent and what it costs:

```
READY TO GENERATE — [NN] [Title]  ([album])

  Model      v6
  Takes      2 (one call always makes two)
  Max Mode   On — costs a multiple of the usual credits (2× on suno.com)
  Variety    Off — the Style Box is used as written
  Sliders    Weirdness 50 · Style Influence 50
  Duration   Auto
  Exclude    choir, crowd vocals
  Dropped    vocal_gender — your plan lacks advanced controls

  Cost       about 10 song credits (20 with Max Mode). You have 9,935.
  Workspace  create "Album Title" on suno.com and file the takes there (free),
             and file its 4 earlier takes
  Then       open both takes in your browser (free).
             (Playing them here instead uses 2 download credits. You have 66.)

Go ahead?   yes · generate only · play here instead · without Max Mode · without a workspace · cancel
```

Rules for the summary:

- Leave out any line that does not apply (no Max Mode, nothing excluded, nothing dropped).
- **Variety** is shown whenever the request holds `controls`, from `request.controls.variety`: 0 Off, 1 Normal, 2 High, 3 Extra, 4 Max. Above Off, say "Suno rewrites the Style Box before generating" instead.
- Anything in `ignored` goes on a **Not sent** line with its setting, value and reason — a cover, a spoken track and a score each leave some settings behind.
- Name what kind it is when it is not a plain song: a `Cover of` line with `cover.source_url`, a `Voice` line with the Voice's name, `Audio influence` among the sliders, or `Spoken word` with the script's length and `Backing music On/Off` in place of the model lines.
- **Max Mode** appears only when the request holds `max_mode: true`. Suno asks that Max Mode be turned on only at the user's request, so the user's yes to a summary that names it *is* that request. If they answer "without Max Mode", remove `max_mode` and proceed.
- **Then** follows the listen plan:
  - `--no-listen` → leave the line out.
  - `mode` is `browser` (the default) → the browser line above. Drop the "playing them here" note, and the "play here instead" answer, when `player` is null or fewer than 2 download credits are left.
  - `mode` is `iterm2_browser` and the plan's `iterm2.available` is true → the same line with "beside this session, in iTerm2 panes" in place of "in your browser". The note and the "play here instead" answer follow the browser rule.
  - `mode` is `iterm2_browser` but `iterm2.available` is false → the browser line above, with the plan's `iterm2.reason` in a clause.
  - `mode` is `terminal` → "play both takes here: 2 download credits. You have N. (Opening them in the browser instead is free.)", with "browser instead" among the answers.
  - `mode` is `terminal` but `player` is null → "open both takes in your browser (free) — no audio player is installed; install mpv to play here".
  - `mode` is `terminal` and fewer than 2 download credits are left → "open both takes in your browser (free) — you have N download credits left".
- **Workspace** appears only when Step 4b planned one. Add "and file its N earlier takes" when `clips` is not empty. "Without a workspace" skips it for this run, and the answers list carries that option only when the line is shown.
- A yes covers exactly what the **Then** and **Workspace** lines say. Terminal playback spends download credits only when the summary said so or the user answered "play here instead".
- Wait for an explicit answer. Silence is not a yes.

## Step 6: Generate

1. Fix an idempotency key **before** the first attempt: `{album_slug}/{track_slug}/{UTC timestamp}`, for example `sample-album/03-t-day-beach/2026-06-15T12:00:00Z`.
   If Step 4b planned a workspace, make it first: `workspaces-create(name: <suggested_name>)`, then `set_album_workspace(album_slug, <its id>, <its name>)`, then one `workspaces-update-clips(id: <its id>, add: <list>)` per list in `batches` for the earlier takes (check `skipped`). Put `workspace_id: <its id>` into the request. If `workspaces-create` fails, say so and generate without one; the takes can be filed later.
2. Call the tool named in `tool` with the keys of `request`, the `voice_id` from Step 4 when the track names a Voice, and the `idempotency_key`. Add nothing else.
3. The answer carries two ids in `clip_ids`. Tell the user the takes are generating.
4. Call `audio-wait` with every id in `ids` and `until: "complete"`. It returns after about 50 seconds whether or not the songs are finished; call it again while any is still pending. A song usually takes one to three minutes.
5. Call `account-usage` again. Credits spent = balance before − balance after.

| What happened | Do |
|---------------|-----|
| No response or a timeout from the create call | Retry **once** with the **same** idempotency key |
| The call is rejected for an unknown argument | Remove that argument, tell the user, and retry once with a **new** key (the arguments changed) |
| `402` — out of credits | Call `account-upgrade`, show its link, and stop. Log nothing |
| `403` — model or feature not on the plan | Name what is missing. Offer to retry without it when it is `max_mode`, `controls`, `negative_style` or `vocal_gender`; otherwise show the **Fallback** |
| `400` — Suno's content check rejected the title, lyrics or style | Show Suno's message word for word and stop. The track's status does not change |
| One take ends with `status: error` | Log it as failed in Step 7 and carry on with the other |

Never send the create call a second time for the same go-ahead except as the table says. Each successful call spends credits.

## Step 7: Log the Takes

Call `log_generation(album_slug, track_slug, model, clips, notes)`:

- `model` — the model that was sent (`default` if none was; `speech` for a spoken track).
- `clips` — one entry per clip id: `{"clip_id": ..., "status": "complete" or "error", "duration_s": the clip's metadata.duration, "error": the reason for a failed take}`.
- `notes` — `via MCP, N credits`, plus `, Max Mode` when it was used, `, cover` for a cover, `, Voice <name>` when one sang, `, spoken` for a spoken track and `, from a MIDI score` for a score.

Then, unless the track is already `Generated`: `update_track_field(album_slug, track_slug, "status", "Generated")`.

## Step 8: Report and Hand Off

```
GENERATED — [NN] [Title]

  Take 1 (row 3)   3:14   https://suno.com/song/...
  Take 2 (row 4)   3:20   https://suno.com/song/...

  Filed in workspace "Album Title" (new, with 4 earlier takes).
  Spent 10 song credits. 9,925 left.
```

Leave the workspace line out when none was used; drop the parenthesis when the workspace already existed.

Then continue straight into `/bitwize-music:listen` for those two rows, in the way chosen in Step 5. If that was the terminal, the download credits were approved there — do not ask again.

Skip the hand-off when the user passed `--no-listen` or answered "generate only".

**Take check.** Once the takes are open, run `/bitwize-music:check-take <album> <track>` for those two rows and show its report. It asks Suno's listening agent whether each take sings the lyrics as written and matches the tempo, voice and exclusions; it is free and takes about a minute, so the user reads it while listening. Skip it when the user passed `--no-check` or its plan says `enabled: false` (`generation.take_check: false`). Then ask which take to keep. The report informs that choice; it never makes it.

## Approving a Take

Approval is the user's call and is not part of generating. When they name the keeper, now or later:

1. In the track file, change that Generation Log row's Rating from `—` to `✓`.
2. `update_track_field(album_slug, track_slug, "suno-link", "<that take's URL>")`
3. `update_track_field(album_slug, track_slug, "status", "Final")`
4. If the listen plan's `like_keeper` is true and the take has a `clip_id`, call `audio-like(id: <clip_id>)` so the keeper shows as liked on suno.com. If a different take of this track carried the ✓ before, clear its like with `audio-unlike`. Never dislike a rejected take: a dislike is a rating only the user gives, it feeds Suno's taste profile, and it deletes nothing.
5. Offer `/bitwize-music:import-audio --from-suno <album> <track>`. It is free for a take that was played in the terminal.

When they reject both takes, add the reason to the Notes of those rows, then follow the Regeneration Workflow in CLAUDE.md: a style problem goes to `/bitwize-music:suno-engineer`, a lyrics problem to `/bitwize-music:lyric-writer`, and plain bad luck is another `/generate`.

## Album Mode

`/bitwize-music:generate <album>` with no track generates every track that is ready, after one go-ahead.

1. Check the Suno server as in Step 3, then call `get_album_generation_plan(album_slug)`.
2. `generate` is empty → say why and stop: list the `blocked` tracks with their reasons and the `skipped` ones.
3. Workspace: as in Step 4b. The plan carries `workspace` and `suggested_workspace_name`.
4. Show one summary and get one go-ahead. It covers every call in the list and nothing else:

   ```
   READY TO GENERATE — [Album]  (5 of 12 tracks)

     01 First Track      20 credits (Max Mode)
     02 Second Track     10 credits
     05 Fifth Track      10 credits (cover)
     ...
     Blocked   03 Third — gates: Sources Verified
     Skipped   04 Fourth — already has takes

     Calls     5, one per track (10 takes)
     Cost      about 70 song credits. You have 9,915.

   Go ahead?   yes · cancel
   ```

   Name Max Mode on each track that asks for it: Suno wants Max Mode only at the user's request, and a yes to a list that names it is that request. Name each track's `kind` when it is a cover or spoken word. Wait for an explicit yes.
5. On a yes, take the tracks in `generate` one after another: Step 4 (`get_generation_request`, with its Voice lookup), Step 6 (one call to the track's `tool` with the track's own idempotency key, then `audio-wait`) and Step 7 (`log_generation`, status `Generated`). A MIDI score is never part of Album Mode. Start a track only when the one before is logged. At a `402` stop the batch and report what was done; any other failure on one track is reported and the batch carries on.
6. Report every track's takes and the credits spent (balance before − balance after). Then run `/bitwize-music:check-take` for each generated track unless `--no-check`, and offer `/bitwize-music:listen <album> <track>` track by track.

## Covers, Voices and Spoken Tracks

The track file says which kind it is; Steps 2 to 8 apply to all of them. Two takes, 10 song credits each call (measured for every kind).

- **Cover** (`kind: cover`) — the track's Cover / Voice Setup block holds a song address in **Source audio** (`https://suno.com/song/<id>`). The Style Box is the new style, and the Lyrics Box is what gets sung: a cover sent no lyrics comes back instrumental, so a vocal track still needs its words. **Audio Influence** in that block says how closely to follow the source. Measured: a cover at Audio Influence 70 kept its source's tempo although the new style named another, so lower it when the tempo should change. A source that is not on Suno cannot be covered from here — the user uploads it on suno.com and pastes its address.
- **Voice** — the track names a saved Voice (Suno's Voices need a Pro or Premier plan). The Voice carries its own gender, so Vocal Gender is not sent, and a Voice cannot sing an instrumental track.
- **Spoken word** (`kind: speech`) — the frontmatter says `spoken: true`. The Lyrics Box is the script, spoken word for word with its section tags taken out; the Style Box holds delivery tags ("calm narrator, warm, close microphone"); `Backing Music: On` in Generation Settings keeps music under the voice. There is no model, Max Mode or slider to send, and Suno words the delivery tags its own way, so the two clips can differ a good deal (measured: 20 and 50 seconds from one short script). Tell the user to hear both.

## From a MIDI Score

`--midi [file]` has Suno play a melody the user wrote. A score plays only on `v6-wild` and goes out with a description built from the Style Box; Suno takes no lyrics, exclusions, sliders or duration with it.

1. `get_midi_score_plan(album_slug, track_slug, midi_path)`. With no file named it uses the track's own `.mid` under `sheet-music/source/` (`/bitwize-music:sheet-music-publisher` § MIDI From Suno saves one there). `supported: false` → show the problem and stop. The gates in Step 2 still run, with one difference: Lyrics Reviewed, Pronunciation Resolved, Homograph Check, Lyric Length and Performance Cues check words that a score does not send, so when they are the only gates failing, say so and carry on — a melody can be sketched before its lyrics exist. Every other gate blocks as usual.
2. Say what will come back before anything is uploaded. `sketch: false` (an instrumental track): the takes are the track. `sketch: true` (a vocal track): the takes are instrumental sketches of the melody, and the track's lyrics are sung over the chosen sketch in a second step that costs another 10 credits.
3. Upload the file, which is free: `midi-upload-create`; then send the file to its `upload_url` as a multipart form, every `upload_fields` entry first and the file last as `file` — `curl -sS -o /dev/null -w '%{http_code}' -F 'key=…' -F 'policy=…' … -F 'file=@<midi.path>' '<upload_url>'`, where `204` is success; then `midi-upload-complete(id: <midi_upload_id>)`. The address and fields are credentials for this one upload: do not show them.
4. `get_generation_request(album_slug, track_slug, midi_upload_id: <that id>)` returns `kind: midi`. Carry on from Step 4b: summary with its **Not sent** lines, go-ahead, one `audio-create`, the log, listening. The song stays `queued` until Suno's copyright check on the score passes.

For a vocal track, when the user has chosen a sketch: put its song address in **Source audio** of the track's Cover / Voice Setup block (add the block from `templates/track.md` if the track has none) and run `/bitwize-music:generate` again. That covers the sketch with the Style Box and Lyrics Box. Do not mark a sketch ✓ — it is not the track.

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
2. **One call makes two takes and spends credits.** One go-ahead covers one call — or, in Album Mode, exactly the calls its summary listed.
3. **Send only what `get_generation_request` returned.** The mapping lives in that tool, not in your head.
4. **The live tool definition wins.** Suno's server is in beta and its arguments change.
5. **You never pick a take, mark a keeper, set `Final` or publish.** A human listens first.
6. **Each album's takes are filed in its own workspace**, made at the first generation and recorded in the album README. Creating and filing are free; nothing is deleted or published.
