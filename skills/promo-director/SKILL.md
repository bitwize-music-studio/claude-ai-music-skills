---
name: promo-director
description: Generates 15-second vertical promo videos for social media from mastered audio, and on request has Suno generate a video clip for a passage of a track (paid, in Visuals credits). Use after mastering is complete and before release, when the user wants social media content.
model: sonnet
effort: low
prerequisites:
  - mastering-engineer
  - album-art-director
allowed-tools:
  - Read
  - Bash
  - Glob
  - bitwize-music-mcp
  - mcp__suno__account-usage
  - mcp__suno__audio-download
  - mcp__suno__audio-listen
  - mcp__suno__audio-listen-wait
  - mcp__suno__audio-retrieve
  - mcp__suno__video-create
  - mcp__suno__visuals-download
  - mcp__suno__visuals-wait
requirements:
  external:
    - name: ffmpeg
      purpose: Video generation and audio visualization
      install: "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
      notes: "Requires showwaves, showfreqs, drawtext, gblur filters"
  python:
    - pillow
    - librosa
    - pyyaml
---

# Promo Director Skill

Generate professional promo videos for social media from mastered audio. Creates 15-second vertical videos (9:16, 1080x1920) optimized for Instagram Reels, Twitter, and TikTok.

## Purpose

After mastering audio, generate promotional videos that combine:
- Album artwork
- Audio waveform visualization (9 styles available)
- Track title + artist name
- Automatic color scheme extracted from artwork
- Intelligent segment selection (finds the most energetic 15 seconds)

## When to Use

- After mastering complete, before release
- User asks for a generated clip of a track from Suno (step 6: paid, and only on request)
- User says "generate promo videos" or "create promo videos for [album]"
- When album has mastered audio + artwork ready

## Position in Workflow

```
Generate → Master → **[Promo Videos]** → Release
```

Optional step between mastering-engineer and release-director.

## Workflow

### 1. Setup Verification

**Check ffmpeg:**
```bash
ffmpeg -filters | grep showwaves
```

Required filters: `showwaves`, `showfreqs`, `drawtext`, `gblur`

If missing:
```
Error: ffmpeg not found or missing required filters

Install ffmpeg:
  macOS: brew install ffmpeg
  Linux: apt install ffmpeg

After installing, run this command again.
```

**Check Python dependencies:**

Call `get_python_command()` to verify the venv exists. If `venv_exists` is false, show the warning and suggest `/bitwize-music:setup`.

### 2. Album Detection

**Resolve audio path via MCP:**

Call `resolve_path("audio", album_slug)` — returns the full audio directory path including artist folder.

Example result: `~/bitwize-music/audio/artists/bitwize/albums/electronic/sample-album/`

**Verify contents:**
- ✓ Mastered audio files (.wav, .mp3, .flac, .m4a)
- ✓ Album artwork (album.png or album.jpg)

If artwork missing:
```
Error: No album artwork found in {audio_root}/artists/{artist}/albums/{genre}/{album}/

Expected: album.png or album.jpg

Options:
  1. Use /bitwize-music:import-art to place artwork
  2. Specify path manually: --artwork /path/to/art.png

Which option?
```

### 3. User Preferences

**Check config defaults first:**

Read `promotion` section from `~/.bitwize-music/config.yaml` for defaults:
- `promotion.default_style` - Default visualization style
- `promotion.duration` - Default clip duration
- `promotion.include_sampler` - Whether to generate album sampler by default
- `promotion.sampler_clip_duration` - Seconds per track in sampler

If config section doesn't exist, use built-in defaults (pulse, 15s, sampler enabled, 12s clips).

**Ask: What to generate?**

Options (default from config or "both"):
1. Individual track promos (15s each) + Album sampler (all tracks)
2. Individual track promos only
3. Album sampler only

**Ask: Visualization style?**

Default from `promotion.default_style` or `pulse` if not set.

| Style | Best For | Description |
|-------|----------|-------------|
| `pulse` | Electronic, hip-hop | Oscilloscope/EKG style with heavy glow (default) |
| `bars` | Pop, rock | Fast reactive spectrum bars |
| `line` | Acoustic, folk | Classic clean waveform |
| `mirror` | Ambient, chill | Mirrored waveform with symmetry |
| `mountains` | EDM, bass-heavy | Dual-channel spectrum (looks like mountains) |
| `colorwave` | Indie, alternative | Clean waveform with subtle glow |
| `neon` | Synthwave, 80s | Sharp waveform with punchy neon glow |
| `dual` | Experimental | Two separate waveforms (dominant + complementary colors) |
| `circular` | Abstract, experimental | Vectorscope (wild circular patterns) |

**Default recommendation:**
- Electronic/Hip-Hop → `pulse`
- Rock/Pop → `bars`
- Folk/Acoustic → `line`
- Ambient/Chill → `mirror`

**Ask: Custom duration?**

Default: 15 seconds (optimal for Instagram/Twitter)

Options:
- 15s (recommended, Instagram Reels sweet spot)
- 30s (longer preview)
- 60s (full clip, less common)

**For sampler:**

Default: 12 seconds per track

Calculate total:
```
Total duration = (tracks * clip_duration) - ((tracks - 1) * crossfade)
Twitter limit: 140 seconds
```

If over 140s:
```
WARNING: Expected duration {duration}s exceeds Twitter limit (140s)

Recommendation: Reduce --clip-duration to {140 / tracks}s
```

### 4. Generation

**Individual track promos:**

```
generate_promo_videos(album_slug, style="pulse", duration=15)
```

**Single track only:**
```
generate_promo_videos(album_slug, style="pulse", track_filename="01-track-name.wav")
```

**Where the passage starts.** By default the generator picks the most energetic passage and starts it on the nearest beat. To start it somewhere else, add `start_s` to a single-track call:

```
generate_promo_videos(album_slug, track_filename="01-track-name.wav", start_s=47.2)
```

**Ask Suno where the hook is (optional, free).** When Suno's MCP server is connected and the track has a keeper generated through it, Suno's listening agent can name the passage: `get_suno_release_plan(album_slug)` gives each track's keeper `clip_id`; then ask

```
audio-listen(id: <clip_id>, question: "Where does the most recognisable 15-second passage of this song start - usually the first full chorus? Give the time of its first downbeat. End with a JSON block with these fields: start_s (seconds), section (a short name).")
```

and read the answer with `audio-listen-wait`. Offer it as a choice next to the automatic pick, and pass the chosen `start_s`. The mastered file keeps the take's timeline, so the time carries over. Five questions may be unanswered at once; 200 a day.

**Album sampler:**

```
generate_album_sampler(album_slug, clip_duration=12, crossfade=0.5)
```

**Handle errors:**

Common issues:
- **ffmpeg filter error** → Check ffmpeg install includes filters
- **Font not found** → Install dejavu fonts or specify custom font
- **Artwork extraction fails** → Use default cyan color scheme
- **librosa unavailable** → Fall back to 20% into track for segment selection
- **Audio file corrupt** → Skip track, report, continue with others

### 5. Results Summary

**Report generated files:**

```
## Promo Videos Generated

**Location:** {audio_root}/artists/{artist}/albums/{genre}/{album}/

**Individual Track Promos:**
- {audio_root}/artists/{artist}/albums/{genre}/{album}/promo_videos/
- 10 videos generated
- Format: 1080x1920 (9:16), H.264, 15s each
- Style: pulse
- File size: ~10-12 MB per video

**Album Sampler:**
- {audio_root}/artists/{artist}/albums/{genre}/{album}/album_sampler.mp4
- Duration: 114.5s (under Twitter 140s limit ✓)
- Format: 1080x1920 (9:16), H.264
- File size: 45.2 MB

**Next Steps:**
1. Review videos: Open promo_videos/ folder
2. Test on phone: Transfer one video and verify quality
3. Populate social copy: Fill in promo/ templates (twitter.md, instagram.md, etc.)
4. [Optional] Upload to cloud: /bitwize-music:cloud-uploader {album}
5. Ready for release workflow: /bitwize-music:release-director {album}
```


### 6. A Generated Clip through Suno (optional, paid)

Only when the user asks for it: "a generated clip", "an AI video for track 3", "a Suno clip". Never make one as part of the ordinary run. The videos above are made on this machine and cost nothing; this one is made by Suno's `video-create` and spends **Visuals credits by the second**, a balance of its own beside song and download credits. One clip, for one track, is 5 to 15 seconds long, and its soundtrack is that passage of the track's keeper. Background and prices: `${CLAUDE_PLUGIN_ROOT}/reference/suno/mcp-api-mapping.md` § Visuals.

**One rule runs through every step: a clip is paid for once.** From the moment `video-create` is sent for real, never send it again in this run, whatever happens afterwards. A new clip is a new price and a new go-ahead.

1. **Plan.** `get_promo_clip_plan(album_slug, track_slug)`. A blocking problem → show its `detail` and stop (`no_keeper`: the user approves a take first). `no_master`: say the clip will carry Suno's own audio. `clip_exists`: the track already has a generated clip, and there is one file a track; ask whether to replace it, and on a no, stop.
2. **Find Suno's tools.** Look for `video-create`, `visuals-wait`, `visuals-download`, `audio-retrieve`, `audio-download` and `account-usage` on a connected MCP server and load their definitions. Not there → say so and stop: either Suno's server is not connected, or this session started before Suno added the tools and needs a restart. Then `account-usage`: keep the three balances.
3. **The song.** `audio-retrieve(id: <song.clip_id>)` gives `metadata.duration`. Then find out whether the song is locked, because Suno will not hand over a video whose song is locked: `audio-download(id: <song.clip_id>, format: "mp3")` **without** `confirm`. `status: "ok"` → unlocked. `status: "requires_credit"` → locked: unlocking costs one download credit. Keep that for step 8 and spend nothing now. `processing` → call again, three times at most. `rate_limited` → wait the seconds it names and call again. Any other refusal → report it and stop.
4. **The passage.** Where it starts and how long it is, 5 to 15 whole seconds. Take the time the user names, or ask Suno's listening agent where the hook is (step 4 above). The price grows with every second.
5. **The prompt.** Draft one to three sentences: what is on screen, what happens, how the camera moves. Draw on the album's art direction and the track's concept. Three things are the user's to choose, so ask: the look, who or what is on screen, and whether anyone sings on screen. Show the prompt and change it until they approve it. When no one should sing or mouth the words, pass `singing: false`.
6. **Build the request.** `get_promo_clip_plan(album_slug, track_slug, prompt, start_s, duration_s, aspect, model, song_duration_s: <metadata.duration>)`. `model` is `video-1` (Fast, 480p) unless the user asks for `video-2` (Standard, 720p). A blocking `request_invalid` → show its `detail` and stop. Keep `request`. If `request` is null, stop and say what is missing. **Never put the arguments for `video-create` together yourself**: `request` always names its model, and a call without one is Suno's dearer model.
7. **Price it. This spends nothing.** Call `video-create` with exactly the keys of `request` and `dry_run: true`, and nothing else. The answer carries `dry_run: true`, the price as `credits`, and in `items[0]` the `model`, `duration_s`, `resolution` and `takes` it priced. Check that `model` and `duration_s` are the request's. If they are not, or the tool no longer lists `dry_run`, refuses it, or answers without `dry_run: true`, stop and tell the user. Never drop `dry_run` to get the call through.
8. **State the cost and wait.** Everything the clip will cost, in one line: "Two takes of a 15-second 480p clip of [Title] from 0:47: 225 Visuals credits (you have 600), and one download credit to unlock the song (you have 5)." Leave the download credit out when the song is unlocked. If the price is more than the balance, say so and stop. Do not generate until the user says go. A changed prompt, passage, length, model or anything else is a new request: back to step 6, a new price and a new go-ahead.
9. **Generate, once.**
   - If the song is locked, unlock it first: `audio-download(id: <song.clip_id>, format: "mp3", confirm: true)`. If that fails, stop before generating.
   - Fix the idempotency key now, before the first attempt, and write it down: `"{album_slug}/{track_slug}/promo-clip/{UTC timestamp}"` with the time filled in. Every attempt in this run sends that same string.
   - Call `video-create` with exactly the keys of `request` and that `idempotency_key`. Add nothing else: no `resolution`, no other model, nothing the price did not cover.
   - Keep the `id` it answers with.
10. **Wait.** `visuals-wait(ids: <that id>, view: "summary")`, again while `status` is `processing`, twenty times at most; then give the user the `id` and stop: the clip is still being made, and they can ask for it later. A job that answers `unread` was skipped by a rate limit: wait its `retry_after_seconds` and ask again.
11. **Let the user choose.** Give them each ready take's `suno_url` to watch. Never pick for them, and never save a take they have not chosen. If neither fits, say that another clip is a new price and a new go-ahead, and stop.
12. **Save the chosen take.** `visuals-download(id: <its asset_id>)` answers with a `url`; call it again while it answers `processing`, six times at most. Then `save_promo_clip(album_slug, track_slug, link: <that url>, start_s: <request.song_start_s>, song_duration_s: <metadata.duration>)`, with `replace: true` only when the user said in step 1 to replace the earlier clip. It saves `<track>_suno.mp4` in `promo_videos/`. When the track has a mastered file as long as the take, the same passage of the master goes under the picture.
13. **Report.** The path and the size. The audio: the master from `audio_start_s`, or Suno's own with `audio_note`. And from `account-usage`, the Visuals credits spent and left: if what was spent is not what was quoted, say so. `/bitwize-music:cloud-uploader` uploads the clip with the album's other promo videos.

| What happened | Do |
|---------------|-----|
| No response or a timeout from the real `video-create` | Send it **once** more with the **same** key, so it cannot be charged twice. If that fails too, read `account-usage`, tell the user what was spent, and stop |
| The real call refuses a request the dry run priced | Stop. Do not adjust and resend: tell the user, and a changed request goes back to step 6 |
| `400` with `reason: prompt_refused` | Show Suno's message and generate nothing more. If the prompt named a real artist, character or person, offer one revised prompt and take it back through steps 5 to 8. Never reword a prompt to get past moderation, and never send a prompt the user has not approved |
| `429 moderation_limited` | Stop and tell the user. Do not retry |
| `404` with `reason: song_unavailable`, or `409 song_not_ready` | Say so and stop |
| `404` from a Visuals tool | The Suno sign-in does not include Visuals. Say so and stop |
| One take ends `failed` | Offer the other and say which failed |
| Both takes end `failed` | Read `account-usage`, tell the user what was spent, and stop. Do not generate again |
| `visuals-download` answers `403` with reason `clip_not_unlocked` | The clip is made and paid for: never call `video-create` again. Unlock the song as step 9 says, asking first if that was not agreed, then call `visuals-download` once more. If it still refuses, give the user the take's `suno_url` and stop |
| `save_promo_clip` answers `saved: false` | The clip is made and paid for: never call `video-create` again. If the error says the download stopped early, ask `visuals-download` for the link again and save once more. Otherwise report the error with the take's `suno_url` |

Suno's price list when this was written: `video-1` 15 credits a second, `video-2` 30. So 5 seconds is 75 or 150, and 15 seconds is 225 or 450. Dry runs priced a 5-second `video-1` clip at 75 and a 15-second `video-2` clip at 450, two takes each. The dry run is the price that counts.


## Technical Reference

See [technical-reference.md](technical-reference.md) for:
- Output specifications (resolution, format, bitrate)
- Visualization styles (pulse, bars, line, etc.)
- Platform compatibility (Instagram, Twitter, TikTok)
- Dependencies (required and optional)
- Troubleshooting common issues
