---
name: music-video
description: Makes a music video for a track through Suno's Sequences - shots laid out on the song's sections, a keyframe for each, a free animatic to judge the pacing, then generated clips for the shots the user chooses - and saves the animatic and the finished video beside the album's audio. Laying out and exporting are free; keyframes and clips spend Visuals credits, priced and approved step by step. Use when the user asks for a music video, a storyboard or an animatic for a track.
argument-hint: <album-name> <track> [--shape 16:9|1:1|9:16]
model: sonnet
effort: medium
allowed-tools:
  - Read
  - bitwize-music-mcp
  - mcp__suno__account-usage
  - mcp__suno__audio-analysis
  - mcp__suno__audio-download
  - mcp__suno__audio-retrieve
  - mcp__suno__characters-list
  - mcp__suno__sequence-create
  - mcp__suno__sequence-export
  - mcp__suno__sequence-generate
  - mcp__suno__sequence-get
  - mcp__suno__sequence-list
  - mcp__suno__sequence-update
  - mcp__suno__visuals-download
  - mcp__suno__visuals-models
  - mcp__suno__visuals-show
  - mcp__suno__visuals-wait
requirements:
  external:
    - name: ffmpeg
      purpose: Checking the video and putting the mastered audio under it
      install: "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
      notes: "Optional. Without it the video is saved as Suno makes it, with Suno's own audio"
---

## Your Task

**Input**: $ARGUMENTS

Take one track's approved take to a music video on Suno, a stage at a time: lay the shots out, make their keyframes, export an animatic, turn the shots the user chooses into clips, and save the result.

The user decides the look, who is on screen, which take of a shot to keep, and what to spend. You price, ask and wait.

---

# Music Video Skill

Suno's Sequences lay a music video out as a timeline of shots over a song. Each shot holds a still, its keyframe, until a generated clip replaces it, and the cut can be exported at any point. With only keyframes in it, the export is an **animatic**: the stills held in time with the song, to judge the pacing before paying for clips.

**What it costs**, in Visuals credits, a balance of its own beside song and download credits:

| Stage | Cost |
|-------|------|
| Laying the shots out, changing the cut, exporting, downloading | Free *(measured)* |
| A keyframe | Per shot: 1 on `image-1` (Fast). Suno's own default, `image-4`, is 50 |
| A clip | Per second: 15 on `video-1` (480p), 30 on `video-2` (720p). Charged by the whole second, rounded up: a 9.44-second shot is charged as 10 |

A whole song as clips costs thousands: three minutes at 480p is about 2,700. That is why the animatic comes first, and why most videos keep stills for most shots. Say so before any work, in Step 3.

Measured on a six-shot test: six keyframes cost 6 credits and a five-second clip 75, each charged when its call was made and ready in under a minute. Still unmeasured, and written from Suno's tool descriptions: characters, a shot that fails, and the rate-limit, refusal and unknown answers.

**Every paid call is sent for real once.** It goes out exactly as it was priced, with a key fixed beforehand, and it is sent again only where Step 6's table says so. A shot that holds a take, or is making one, is never made again unless the user asks for that and approves its price.

Background, the answers each tool gives, and what was and was not measured: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Visuals.

## Step 1: Plan

Expected format: `<album-name> <track> [--shape 16:9|1:1|9:16]`

If the album or the track is missing, show:

```
Usage: /music-video <album-name> <track> [--shape 16:9|1:1|9:16]

Example: /music-video sample-album 03
```

Call `get_music_video_plan(album_slug, track_slug, shape)`. The shape is `16:9` unless the user names another.

| Result | Do |
|--------|-----|
| `found: false`, or an `error` | Report it and stop |
| A blocking problem | Show its `detail` and stop. `no_keeper`: the user approves a take first |
| `no_master` | Say the video will carry Suno's own audio, and carry on |
| `video_exists` | Tell the user. The question whether to replace it comes in Step 9 |

## Step 2: Check the Suno Server

Find `sequence-create`, `sequence-generate`, `sequence-update`, `sequence-get`, `sequence-list`, `sequence-export`, `visuals-wait`, `visuals-download`, `visuals-models`, `audio-analysis`, `audio-retrieve`, `audio-download` and `account-usage` on a connected MCP server, and load their definitions.

Not there → say so and stop. Either Suno's server is not connected, or this session started before Suno added the tools and needs a restart.

Call `account-usage` and keep the three balances. Call `visuals-models` and keep each model's price: `credits_per_generation` for an image model, `credits_per_second` for a video model. Both calls are free.

**Then look for a Sequence this track already has**, before planning anything: one that is found and missed would be paid for twice.

1. `sequence-list(query: <sequence_title>)`. A page can be short, or empty, and still carry a `cursor`: pass it back until a page has none, ten pages at most.
2. For each one whose title is the `sequence_title`, `sequence-get(id, view: "full")`. It is this track's only if its `song_id` is `song.clip_id`. Tell the user if its `aspect` is not the shape asked for: the video is saved under the Sequence's shape.
3. Found one → ask whether to carry on with it or start another. To carry on, read each shot's `status` and follow **Carrying On** below. None → Step 3.

### Carrying On

A Sequence keeps what was made. Never make again what a shot already holds or is making:

| A shot reads | It | Do |
|--------------|----|-----|
| `gap` | Has nothing | It needs a keyframe (Step 6) |
| `processing` | Is being made, and is paid for | Wait for it: `visuals-wait` with its `generation_id`. Never start it again |
| `ready`, `media_type: image` | Has its keyframe | Leave it. It can become a clip (Step 8) if the user picks it |
| `ready`, `media_type: video` | Has its clip | Leave it |
| `failed` | Lost its generation | See Step 8, item 7 |

Go to the earliest step some shot still needs, and put **only the shots that need it** in that step's batches. Skip Steps 3 to 5, except `audio-retrieve` and the lock check in Step 3, which every run needs.

## Step 3: The Song, and What the Video Would Cost

1. `audio-retrieve(id: <song.clip_id>)`. Keep `metadata.duration`.
2. Find out whether the song is locked: `audio-download(id: <song.clip_id>, format: "mp3")` **without** `confirm`. `status: "ok"` → unlocked. `status: "requires_credit"` → locked: keep that for Step 7, where the first download happens, and spend nothing now. `rate_limited` → wait the seconds it names and call again. Any other refusal → report it and stop.
3. `audio-analysis(id: <song.clip_id>)`. While `status` is `processing`, call it again, six times at most; it usually takes about a minute. Keep `sections`, `bpm`, `time_signature`, and the `time_s` of the first beat whose `bar_position` is 1. The answer is long: do not repeat it to the user. If it ends `unavailable`, carry on with no sections.
4. `plan_music_video_shots(duration_s, sections, bpm, time_signature, first_downbeat_s, credits_per_second: <video-1's price>)`.
5. **Tell the user the scale before anything else.** For example:

   ```
   First Track (3:26) lays out as 22 shots.
   Keyframes for all of them: 22 Visuals credits on image-1.
   Every shot as a clip: 210 billed seconds, about 3,150 credits at 480p or 6,300 at 720p.
   You have 1,000.

   Three ways to go:
     1. An animatic: keyframes held as stills, in time with the song.
     2. Clips for a few shots you pick, stills for the rest.
     3. Every shot a clip.
   ```

   Ask which. Nothing has been spent, and nothing is made on Suno until Step 5.

## Step 4: The Look

Three things are the user's to choose, so ask unless they have said:

- **The look**: the style, the palette, anything that must not appear (text, faces, logos).
- **Who or what is on screen.** A performer, characters, or no one.
- **Whether anyone sings on screen**, and whether the words are burned in (`lyrics`).

A performer or a place that should look the same from shot to shot needs reference images that are already on Suno, one to three each: the asset ids of images made there, or the user's saved characters from `characters-list`. Without them, leave `characters` and `sets` out: each shot is then drawn from its prompt alone, and faces will not match between shots. Say so if the user wants a performer.

A set holds well *(measured)*: three shots citing one reference image showed the same objects and the same place. It also outweighs the prompt: a shot that asked for one object alone showed the several in the reference. So cite a set only in shots that should show what its images show.

Then draft the storyboard: one line a shot, saying what it shows, the framing and how the camera moves, all within the look. Show it as a table with each shot's number, start time, length and section, and change it until the user approves it. The lengths come from Step 3; to change them, plan again with another `max_shot_s`.

## Step 5: Lay It Out (free)

1. `get_music_video_plan(album_slug, track_slug, shape, shots: [{duration_s, notes, characters?, set?}], style, lyrics, characters, sets)`. A blocking `request_invalid` → show its `detail` and stop. Keep `request`. If `request` is null, stop and say what is missing; never put the arguments together yourself.
2. Call `sequence-create` with exactly the keys of `request` and `idempotency_key: "{album_slug}/{track_slug}/music-video/create/{UTC timestamp}"`, the time filled in once: a retry after an error sends the same string, so it cannot make a second Sequence. Keep the `sequence_id`, the `editor_url`, and every shot's `shot_id` with its number.

Tell the user the `editor_url`: they can rearrange, trim and retime the shots on suno.com at any point, and `sequence-get` reads what they changed.

## Step 6: Keyframes (paid)

One image a shot, made from a prompt: the look, then the shot's line from the storyboard. Name the characters and the set in the prompt as the Sequence names them.

1. **The model.** `image-1` unless the user asks for another. Always name it: left out, Suno uses `image-4` at 50 credits a shot.
2. **Price it. This spends nothing.** `sequence-generate` takes up to 8 shots a call, so split the shots into batches of 8 and write each batch down: the real call sends it unchanged. For each batch call `sequence-generate(id: <sequence_id>, step: "keyframes", model, shots: [{shot_id, prompt}], dry_run: true)`. Each answer carries `dry_run: true`, its price as `credits`, and for every shot the `model` it priced: check that it is the one you named. Add the batches up. If the model differs, the tool no longer lists `dry_run`, refuses it, or answers without `dry_run: true`, stop and tell the user. Never drop `dry_run` to get a call through.
3. **State the cost and wait.** "Keyframes for 22 shots on image-1: 22 Visuals credits. You have 1,000." The balance is the dry run's `visuals_credits_remaining`, which is today's, not the one read in Step 2. More than the balance → say so and stop. Do not generate until the user says go.
4. **Generate, once a batch.** Fix each batch's key before its first attempt and write it down: `"{album_slug}/{track_slug}/music-video/keyframes/{batch number}/{UTC timestamp}"`, the time filled in. Then send each batch exactly as it was priced, without `dry_run` and with its key. Add nothing the price did not cover.
5. **Read each shot's `status`** in the answer. One call can answer with several, and `moderation_limited` on any shot comes first.

   | Status | Do |
   |--------|-----|
   | `moderation_limited` | Stop the whole stage: send nothing more, not even shots still waiting. Tell the user. Do not retry |
   | `started` | It is being made and is paid for. Keep its `generation_id` |
   | `started`, with an `error` beside it | It started but is not in its shot yet. Wait for it like the others, then put the take in its shot with `sequence-update(id, shots: [{shot_id, asset_id}])`. Never make it again |
   | `rate_limited` | It did not start and was not charged. Wait `retry_after_seconds`, then send **only those shots**, with the prompts they were priced with, as a batch of their own with a new key. Three rounds at most; then tell the user which shots are still waiting |
   | `refused` | It did not start. Show the reason. If the prompt named a real artist, character or person, offer one revised prompt; once the user approves it, that shot goes alone: its own dry run, its own go-ahead, its own key. Never reword a prompt to get past moderation |
   | `unknown` | It may have started. Send that batch again, unchanged, **with the same key**, once: Suno replays what started instead of charging for it twice |
   | No answer at all, or a timeout | The same: the batch once more, unchanged, with the same key. If that fails too, read `account-usage`, tell the user what was spent, and stop |
   | The call refuses what the dry run priced | Stop and tell the user. Do not adjust and resend |

6. `visuals-wait(ids: <up to 8 generation ids, comma-separated>, view: "summary")`, again while `status` is `processing`, ten times at most. A job that answers `unread` was skipped by a rate limit: wait its `retry_after_seconds` and ask again.
7. **Let the user look.** Each take has a `suno_url`; `visuals-show(ids: <asset_id>)` lets you look at one to describe it or check it for stray marks. The first take to finish sits in the shot. The user may keep it, swap in the other take with `sequence-update(id, shots: [{shot_id, asset_id}])`, which is free, or have a shot made again, which is a new price and a new go-ahead. Never choose a take for them.

## Step 7: The Animatic (free)

1. `sequence-export(id: <sequence_id>)`. Keep the `id` it answers with. A `409` names a shot that is still being made or has `failed`: wait for it, or see Step 8's note on failed shots.
2. `visuals-wait(ids: <that id>, view: "summary")`, again while `processing`, ten times at most.
3. **If the song is locked (Step 3), ask now.** "Suno will only hand the video over once the song is unlocked, which costs one download credit. You have N." On a yes, `audio-download(id: <song.clip_id>, format: "mp3", confirm: true)`. On a no, give the user the `editor_url`, where the cut plays on suno.com, and carry on without saving files.
4. `visuals-download(id: <the export's asset_id>)`, again while it answers `processing`, six times at most. Then `save_music_video(album_slug, track_slug, link: <that url>, shape, kind: "animatic")`.
5. **The user watches it** and judges the pacing. Changes to the cut are free: `sequence-update` rewrites a shot's notes and moves, trims, splits, deletes and adds shots with `ops`, or the user does it at the `editor_url`. After changes, read the Sequence again with `sequence-get(id, view: "summary")`, since shots after an edit move, and export again.

If the user chose the animatic alone, go to Step 9.

## Step 8: Clips (paid by the second)

Only for the shots the user picked, and only once they are happy with the animatic.

1. **A prompt for each shot**: what happens in it and how the camera moves. It opens on the shot's keyframe. Add `lip_sync: false` to a shot where no one should sing or mouth the words.
2. **The model.** `video-1` unless the user asks for another. Always name it: left out, Suno uses the dearer one.
3. **Price it. This spends nothing.** In batches of 8, each written down: `sequence-generate(id, step: "clips", model, shots: [{shot_id, prompt, lip_sync?}], dry_run: true)`. Add up `credits`, and check that every shot was priced on the `model` you named. The answer's `notes` say what each shot is charged as: 9.44 seconds as 10. Say what that rounding comes to, but do not trim shots to save it: a trim shortens the video, moves every later shot off the music, and leaves the master too long to go under the picture.
4. **State the cost and wait.** "Clips for shots 1, 8 and 15 on video-1 (480p): 27 billed seconds, 405 Visuals credits. You have 978." The balance is the dry run's `visuals_credits_remaining`. More than the balance → say so, and offer fewer shots. Do not generate until the user says go. Any change to the shots, the prompts or the model is a new price and a new go-ahead.
5. **Generate, once a batch.** Fix each batch's key first: `"{album_slug}/{track_slug}/music-video/clips/{batch number}/{UTC timestamp}"`. Send each batch exactly as it was priced, with its key and without `dry_run`. Suno starts about ten generations a minute, so a second batch may come back `rate_limited`. Handle each shot's `status`, a timeout and a refusal as Step 6's table says.
6. **Wait.** Clips take minutes. `visuals-wait(ids, view: "summary")` again while `processing`, twenty times at most; then tell the user it is still running and how to carry on later: run this skill again, which finds the Sequence in Step 2 and waits for the shots still being made. It does not start them again.
7. **A shot that failed** reads `failed` in `sequence-get(id, view: "summary")`, with a `failure_reason` and a `hint`. Any `sequence-update(id)` call puts its keyframe back. Making it again is a new batch: a new price, a new go-ahead and a new key. Read `account-usage` and tell the user what the failed shot cost.
8. **Let the user choose** each shot's take, as in Step 6.

## Step 9: Export and Save

1. `sequence-export(id)`, `visuals-wait`, the lock question if it was not settled in Step 7, and `visuals-download`, as in Step 7.
2. `save_music_video(album_slug, track_slug, link, shape, kind: "video")`, with `replace: true` only when the user said to replace an earlier video. When the track has a mastered file as long as the video, the master goes under the picture. `saved: false` → report its `error` and stop; when it says the download stopped early, ask `visuals-download` for the link again and save once more. Nothing that goes wrong here is a reason to generate anything again: the cut stays on Suno, at the `editor_url`.

## Step 10: Report

Call `account-usage` again and compare with Step 2.

```
MUSIC VIDEO — [NN] [Title]

  Saved     /path/to/music_videos/03-track-name-16x9.mp4  (1920x1080, 3:26)
  Animatic  /path/to/music_videos/03-track-name-16x9-animatic.mp4
  Audio     the master
  Editor    https://suno.com/visual/cmp_...
  Spent     22 Visuals credits on keyframes, 405 on clips; 573 left
```

**Spent** comes from the balances, not from the quotes. If they differ, say so.

## Remember

1. **Say what it would cost before any work.** A whole song as clips is thousands of credits.
2. **Every paid call is priced first** with `dry_run: true`, stated, and waits for a go-ahead. A change is a new price.
3. **And sent for real once**, exactly as priced, with a key fixed beforehand. It is sent again only as Step 6's table allows, and a shot that holds or is making a take is never made again.
4. **Always name the model.** Suno's defaults are its dearest: 50 a keyframe, 30 a second.
5. **The look, the cast and every take are the user's to choose.**
6. **Never reword a prompt to get past moderation.** One revision, for a named artist, character or person, approved by the user.
7. **The animatic comes before clips.** The cut is free to change; clips are not.
8. **The keeper only.** The video is made for the approved take.
9. **Unlocking a song can cost a download credit.** Ask before `confirm: true`.
