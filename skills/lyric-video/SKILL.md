---
name: lyric-video
description: Makes a lyric video for a track through Suno's MCP server - the album cover held under the track's approved take, with the words burned in as they are sung - and saves it beside the album's audio with the mastered audio under it. Rendering was free when measured. Use when the user asks for a lyric video, a video with the lyrics on screen, or a video of a song for YouTube.
argument-hint: <album-name> <track> [--shape 16:9|1:1|9:16] [--asset <Suno image id>] [--suno-audio] [--replace]
model: sonnet
effort: low
allowed-tools:
  - Read
  - bitwize-music-mcp
  - mcp__suno__account-usage
  - mcp__suno__audio-download
  - mcp__suno__audio-retrieve
  - mcp__suno__video-assemble
  - mcp__suno__visuals-download
  - mcp__suno__visuals-upload-complete
  - mcp__suno__visuals-upload-create
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

Make a lyric video for one track: plan it, give Suno the picture, have Suno render the video, and save it beside the album's audio.

You never pick a take. The video is made for the track's approved take, and only for that one.

---

# Lyric Video Skill

Suno's `video-assemble` holds a picture under a song and burns the words in as they are sung, lit word by word. This skill has it do that with the album's cover and the track's keeper.

Measured on songs of 52 to 97 seconds: rendering and waiting spent no credit of any kind, and each video was ready in under a minute. Downloading was free too for the two whose song was already unlocked. Suno's own description says stills and rendering are free. Check it every run all the same: Step 2 reads the balances and Step 7 reads them again.

Background, the answers each tool gives and what was measured: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Visuals.

## Step 1: Plan

Expected format: `<album-name> <track> [--shape 16:9|1:1|9:16] [--asset <Suno image id>] [--suno-audio] [--replace]`

If the album or the track is missing, show:

```
Usage: /lyric-video <album-name> <track> [--shape 16:9|1:1|9:16]

Example: /lyric-video sample-album 03
```

Call `get_lyric_video_plan(album_slug, track_slug, shape)`, with `asset_id` as well when the user passed `--asset`: an album with no cover is only blocked without one. The shape is `16:9` unless the user names another.

| Result | Do |
|--------|-----|
| `found: false`, or an `error` | Report it and stop |
| A blocking problem | Show each one with its `detail` and stop. `no_keeper`: the user approves a take first. `instrumental`: there are no words to show. `no_cover`: the album needs a cover, or the user names an image already on Suno with `--asset` |
| `no_master` | Say the video will carry Suno's own audio, and carry on |
| `video_exists` | Ask whether to replace the earlier video, unless the user passed `--replace`. No → stop |
| `ffmpeg_missing` | Say the video will be saved as Suno makes it, and carry on |

## Step 2: Check the Suno Server

Find `video-assemble`, `visuals-wait`, `visuals-download`, `audio-retrieve`, `audio-download` and `account-usage` on a connected MCP server, and load their definitions. Without `--asset`, find `visuals-upload-create` and `visuals-upload-complete` too.

Not there → say so and stop. Either Suno's server is not connected (the setup command is in the reference doc), or this session started before Suno added the tools and needs a restart.

Call `account-usage` and keep the three balances: `credits_remaining`, `download_credits_remaining` and `visuals_credits_remaining`.

## Step 3: The Song

1. `audio-retrieve(id: <song.clip_id>)`. Keep `metadata.duration`.
2. Find out whether the song is locked, because Suno renders a video for a locked song but will not hand it over. Call `audio-download(id: <song.clip_id>, format: "mp3")` **without** `confirm`. Do not save what it returns, and spend nothing yet.

   | Answer | Do |
   |--------|-----|
   | `status: "ok"` | The song is unlocked. Nothing was spent |
   | `status: "requires_credit"` | The song is locked: unlocking it costs one download credit. Keep the balance (`credits_remaining` in the answer) and carry on. The question comes in Step 5, once nothing else can stop the video |
   | `status: "processing"` | Call `audio-download` again, three times at most |
   | `rate_limited` | Wait the `retry_after_seconds` it names, then call again |
   | Any other refusal (`quota_exhausted`, `daily_limit_exceeded`, `no_permission`, …) | Report it and stop. Do not retry |

   A keeper whose WAV was downloaded from Suno for a download credit is already unlocked. One exported through Suno Studio is not.

## Step 4: The Picture

With `--asset <id>`, that image on Suno is the picture: go to Step 5.

Otherwise the picture is made from the album's cover and uploaded:

1. `prepare_lyric_video_still(album_slug, shape)`. It writes a JPEG of the video's shape with the whole cover in the middle. Keep `still.path` and `still.bytes`.
2. `visuals-upload-create(content_type: "image/jpeg", bytes: <still.bytes>)`.
   - **`403` with reason `upload_consent_required`** → Suno asks every account, once, to accept a notice before its first upload: that the user has the rights to what they upload. It is theirs to accept. Never accept it for them, and never look for a way around it. Tell them to start an image upload under Visuals on suno.com, accept the notice there, and run this again. Mention `--asset` for an image that is already on Suno. Stop.
   - Otherwise the answer holds the upload's asset id, an `upload_url`, `upload_fields` and `expires_at`.
3. Send the file to `upload_url` as a multipart form, every `upload_fields` entry first and the file last as `file`:

   ```bash
   curl -sS -o /dev/null -w '%{http_code}' --form-string 'key=…' --form-string 'policy=…' … -F 'file=@<still.path>' '<upload_url>'
   ```

   Each field goes in with `--form-string`, which sends its value as it is; `-F` would read a value that starts with `@` or `<` as a file to send. Only the file itself takes `-F`. The address and the fields are credentials for this one upload: do not repeat them in your reply. A `2xx` code is success; anything else → report the code and stop.
4. `visuals-upload-complete(id: <the asset id>)`, then `visuals-wait(ids: <that id>)` until it is `ready`, six times at most. An upload that ends `failed` says why in `error` (`moderated`, `invalid_file` or `processing_failed`): report it and stop.

The upload steps follow Suno's tool descriptions. They were not measured: the test account had not accepted the notice.

## Step 5: Assemble

1. **If the song is locked (Step 3), ask now.** "The video can be made free, but Suno will only hand it over once the song is unlocked, which costs one download credit. You have N." On a yes, `audio-download(id: <song.clip_id>, format: "mp3", confirm: true)`. On a no, stop before rendering anything.
2. `get_lyric_video_plan(album_slug, track_slug, shape, asset_id: <the picture's id>, duration_s: <metadata.duration>)`. Its `request` holds the arguments for `video-assemble`. A blocking `request_invalid` → show its `detail` and stop. A `request` that is null means the picture's id or the song's length did not arrive: stop and say which.
3. Say what is about to happen in one line: "Suno will render a 16:9 lyric video of [Title] (3:26). It was free when measured and takes about a minute. It leaves a Sequence in your Suno library." No go-ahead is needed for a call that spends nothing.
4. Call `video-assemble` with the keys of `request` and `idempotency_key: "{album_slug}/{track_slug}/lyric-video/{UTC timestamp}"`. Add nothing else. Keep the `id` and the `editor_url` it answers with. Make the key once and keep it: every retry in this run uses the same one.
5. `visuals-wait(ids: <that id>)`. It returns after about 50 seconds whether or not the video is ready: call it again while `status` is `processing`, ten times at most, then give the user the `id` and the `editor_url` and stop. A job that answers `unread` was skipped by a rate limit: wait its `retry_after_seconds` and ask again. A job that ends `failed` → report it and stop.

| What happened | Do |
|---------------|-----|
| No response or a timeout from `video-assemble` | Retry **once** with the **same** idempotency key, which finishes the same video instead of starting another |
| `404` from a Visuals tool | The Suno sign-in does not include Visuals. Say so and stop |
| `400`: a clip is still being made | The picture was not ready. Wait for it with `visuals-wait`, then call again with the same key |

## Step 6: Save

1. `visuals-download(id: <the video's asset_id>)`. It answers with a `url`; call it again while it answers `processing`, six times at most.

   A `403` with reason `clip_not_unlocked` means the song is still locked. The video is made and stays made: do not render it again. Unlock the song as Step 5 item 1 says, asking first, then call `visuals-download` once more. If it still refuses, give the user the video's `suno_url` and stop.
2. `save_lyric_video(album_slug, track_slug, link: <that url>, shape)`. Add `master_audio: false` when the user passed `--suno-audio`, and `replace: true` only when the user said to replace the earlier video.

   It fetches the file, checks that it is a whole video, and saves it under the album's `lyric_videos/`. When the track has a mastered file as long as the video, the master goes under the picture; the picture itself is copied untouched.

   `saved: false` → report its `error` and stop. One exception: when the error says the download stopped early, ask `visuals-download` for the link again and call `save_lyric_video` once more.

## Step 7: Report

Call `account-usage` again and compare the three balances with Step 2.

```
LYRIC VIDEO — [NN] [Title]

  Saved    /path/to/lyric_videos/03-track-name-16x9.mp4  (1920x1080, 3:26, 41 MB)
  Audio    the master
  On Suno  https://suno.com/visual/ast_...
  Editor   https://suno.com/visual/cmp_...
  Spent    nothing — all three balances are unchanged
```

- **Audio**: "the master", or "Suno's own audio" followed by `audio_note` when there is one.
- **Spent**: if a balance moved, say which one and by how much. Never say "nothing" without having compared.
- **Editor** is the `editor_url` from Step 5, where the user can open the cut on suno.com.

Tell the user once: watch it through before publishing. The words and their timing are Suno's reading of the take, not the track file's Lyrics Box. Every sung line was shown on the takes tested, but nothing here checks the picture.

## Remember

1. **The keeper only.** The video is made for the approved take. You never pick one.
2. **Free when measured, and checked every run.** Read the balances before and after, and report any that moved.
3. **Suno's upload notice is the user's to accept.** Never accept it for them.
4. **The words are the take's.** The video shows what was sung, so a Lyrics Box changed since the take was made does not change it.
5. **An earlier video is kept** unless the user says to replace it.
6. **Unlocking a song can cost a download credit.** Ask before calling `audio-download` with `confirm: true`.
