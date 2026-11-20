---
name: check-take
description: Checks a track's Suno takes against the track file by asking Suno's listening agent - which lyric lines are not sung or are changed, tempo, voice, excluded instruments, mix problems - and by reading back the settings Suno made each take with. Free and advisory; it never picks a take. Use after generating, or when the user asks "did it sing everything", "check the takes" or "is the tempo right".
argument-hint: <album-name> <track> [take N | all]
model: sonnet
effort: low
allowed-tools:
  - Read
  - bitwize-music-mcp
  - mcp__suno__audio-listen
  - mcp__suno__audio-listen-wait
  - mcp__suno__audio-retrieve
---

## Your Task

**Input**: $ARGUMENTS

Check a track's takes against its track file and report what differs. Suno's listening agent does the listening; you ask, collect and report.

You never choose a take and never rank takes. The report says what was heard; the user listens and decides.

---

# Check Take Skill

Asking Suno's agent about a song is free: nothing is made, changed or charged. The limits are five unanswered questions at a time and 200 questions a day. Reading a take's data, which holds the settings it was made with, is free too.

The agent is good, not infallible. Treat every flag as "listen here", never as proof. Background, and why Suno's lyric alignment is not used for this: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Take Check.

## Step 1: Plan

Expected format: `<album-name> <track> [take N | all]`

Call `get_take_check_plan(album_slug, track_slug)`.

- `found: false` → report the error and stop.
- `takes` is empty → "No Suno takes to check for [track] yet — generate it first. (Takes logged as older share links cannot be checked.)" Stop.
- Which takes: `take N` → that one; `all` → every entry in `takes`; neither → `default_takes`.
- When `/bitwize-music:generate` handed off to you and `enabled` is false, stop without a word: the user turned the automatic check off (`generation.take_check: false`). A direct request always runs.

## Step 2: Find the Tools

Look for `audio-listen` and `audio-listen-wait` on a connected MCP server and load their definitions. Not there → say the take check needs Suno's MCP server, give the setup command from the reference doc, and stop. There is no fallback.

Load `audio-retrieve` as well. Without it the check still runs; it only leaves the settings out.

## Step 3: Ask

For each take, for each entry in `questions`, in order: `audio-listen(id: <clip_id>, question: <the question, word for word>)`. Keep the `id` each call returns, with its take and question number.

- Never have more than five questions unanswered. Two takes with one or two questions each fit in one round; beyond that, work in rounds of five.
- `429 concurrency_limit_exceeded` → read some answers first, then carry on. `429 quota_exceeded` → the day's 200 questions are used; say so and stop.

Then read each answer with `audio-listen-wait(id)`. It returns after about 50 seconds whether or not the answer is ready: call it again while `status` is `processing`. On `error`, note the reason and use an empty string as that answer.

**The settings each take was made with.** While the answers come in, read each take once: `audio-retrieve(id: <clip_id>)`. Keep `metadata.duration` and whichever of `metadata.model`, `metadata.negative_style`, `metadata.max_mode` and `metadata.controls` are there. A take made as an edit carries only its model, and a take can carry none of them. If the call fails, carry on without them.

## Step 4: Evaluate

Once per take: `evaluate_take_check(album_slug, track_slug, clip_id, answers, duration_s, settings)`:

- `answers` — that take's answers word for word, one per question, in question order.
- `duration_s` — the take's `metadata.duration`, when you have it.
- `settings` — an object holding the `model`, `negative_style`, `max_mode` and `controls` you kept for that take, each exactly as Suno gave it. Leave it out when the take had none of them.

The tool holds the model against the one the Generation Log says went out with the take, and the other settings against what the track file asks for today, so a track edited since the take was made shows as a difference.

## Step 5: Report

```
TAKE CHECK — [NN] [Title]

Take 1 (row 3) — 2 things to check
  ⚠ Lyrics   line 2 sung with different words: "Paper boats are lined up on the sill"
             heard: 'all lined up' instead of 'are lined up'
  ⚠ Tempo    112 BPM measured, 96 asked
  ✓ Vocal    female lead — soft, breathy
  ✓ Settings as asked: v6; Variety Off; Max Mode on

Take 2 (row 4) — nothing flagged
  ✓ Lyrics   all 24 lines sung as written
  ✓ Tempo    95 BPM (asked 96)
  ✓ Settings as asked: v6; Variety Off; Max Mode on

These are the agent's observations — listen at the flagged spots before deciding.
```

- `warn` checks first, then `ok`. `info` checks (the key, an unread answer) go last, and only when they add something.
- A few lines per take. Quote each check's `detail`; do not turn it into a verdict of your own.
- No recommendation, no "take 2 is better", no ordering by quality.

## After the Report

- The user rejects a take over a flagged problem → the Regeneration Workflow in CLAUDE.md: a lyric or pronunciation problem goes to `/bitwize-music:lyric-writer` and `/bitwize-music:pronunciation-specialist`, a style problem to `/bitwize-music:suno-engineer`.
- A flag looks wrong to the user → the agent can mishear, and its answers vary a little from run to run. Offer to ask again: `/bitwize-music:check-take <album> <track> take N`.
- Nothing is written to the track file. The Generation Log stays the user's record.

## Error Handling

**Suno's server is not connected:**
```
The take check asks Suno's listening agent, so it needs Suno's MCP server:
  claude mcp add --transport http suno https://api.suno.com/mcp
then run /mcp and sign in.
```

**An answer has no readable result** (the report's `unread` check): say which lines were not checked and offer to ask again.

## Remember

1. **Advisory only.** Report what was heard; never pick, rank or reject a take.
2. **Word for word.** Questions go to Suno exactly as the plan gives them; answers go to `evaluate_take_check` exactly as Suno gave them.
3. **Five questions at a time, 200 a day** — and it is free. So is reading a take's settings.
4. **A flag is a place to listen**, not a verdict: the agent can be wrong.
