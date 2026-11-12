# Suno MCP: Setup, Costs and Track-File Mapping

Suno runs an official MCP server (beta since October 2026). When it is connected, the plugin can generate a track, play the takes and import the keeper without a trip to suno.com. When it is not, everything falls back to the clipboard flow and nothing breaks.

> **Related skills**: `/bitwize-music:generate`, `/bitwize-music:listen`, `/bitwize-music:check-take`, `/bitwize-music:edit-take`, `/bitwize-music:extend-take`, `/bitwize-music:sound-effects`, `/bitwize-music:suno-voice`, `/bitwize-music:import-audio`
> **Related docs**: [models.md](models.md), [creative-sliders.md](creative-sliders.md), [tips-and-tricks.md](tips-and-tricks.md)

Everything marked *measured* was tested on a Premier account. The server is in beta and its tools change — treat the live tool definitions as the authority over this page.

---

## Setup

The plugin does not ship the Suno server; you add it to your own Claude Code once:

```bash
claude mcp add --transport http suno https://api.suno.com/mcp
```

Then run `/mcp` in a session and sign in to your Suno account. Name the server `suno` as above — the skills pre-approve tools under that name. Add `--scope user` to the command to have the server in every project; without it, it belongs to the project you ran the command in. Songs made this way use your plan's credits and land in your Suno library.

Session start checks for the server (`health_check` reads Claude Code's and Codex's MCP registrations for any server on `api.suno.com`) and shows these steps while none is registered. `generation.suno_mcp_reminder: false` in your config turns that reminder off.

Other assistants: see Suno's [connection guide](https://help.suno.com/en/articles/14551425).

---

## Preflight

Every skill that uses Suno tools runs these checks first:

1. **Find the tools.** Look for `audio-create`, `audio-wait` and `account-usage` on any connected MCP server (a tool search for `suno audio-create` finds them). Do not assume the `mcp__suno__` prefix — the user may have named the server differently.
2. **Not found** → the server is not configured. Give the setup command above and offer the fallback below.
3. **Found, but a call returns an authentication error** → tell the user to run `/mcp` and sign in.
4. **Read the account once** with `account-usage`: `allowed_models`, `features`, `suno_account.credits_remaining` and `suno_account.download_credits_remaining`.
5. **Trust the live tool definition.** Send only arguments the tool lists today. If a call is rejected for an unknown argument, drop that argument, tell the user, and retry once.

---

## What Things Cost

Suno keeps two balances: **song credits** and **download credits** (Free 7 lifetime, Pro 20 a month, Premier 60 a month).

| Action | Song credits | Download credits |
|---|---|---|
| `audio-create` — one call makes **two** songs | 10 *(measured)* | 0 |
| `audio-create` with Max Mode | a multiple of that (2× on suno.com) | 0 |
| `audio-create` editing a take (`reference_audio_ids`) — two edited takes | 10 *(measured)* | 0 |
| `audio-create` making an instrumental version of a take — two takes | 10 *(measured)* | 0 |
| `audio-create` in a saved Voice (`voice_id`) — two songs | 10 *(measured)* | 0 |
| `audio-create` playing a MIDI score (`midi_upload_id`) — two songs | 10 *(measured)* | 0 |
| `audio-covers-create` — two covers | 10 *(measured)* | 0 |
| `audio-extensions-create` — two continuations | 10 *(measured)* | 0 |
| `audio-full-song` — joining a continuation to what came before | 0 *(measured)* | 0 |
| `speech-create` — two spoken clips | 10 *(measured)* | 0 |
| `sounds-create` — two sounds of about 20 seconds | 2 *(measured)* | 0 |
| `midi-upload-create`, `midi-upload-complete`, `voices-list` | 0 *(measured)* | 0 |
| `audio-midi` of a stem made with Get Stems | 0 *(measured)* | 0 |
| `audio-stems-create`, `twelve` (two takes of 12 stems) | 50 *(measured)* | 0 |
| `audio-stems-create`, `two` (vocals + instrumental) | 10 | 0 |
| Listen on the song's suno.com page | 0 | 0 |
| First `audio-download` of a song, MP3 or WAV | 0 | 1 *(measured)* |
| Any later download of that song, either format | 0 | 0 *(measured)* |
| Downloading the stems of a song that has been downloaded | 0 | 0 *(measured)* |
| Playing a file already on disk | 0 | 0 |
| `workspaces-create`, `workspaces-update-clips`, `workspaces-list` | 0 *(measured)* | 0 *(measured)* |
| `audio-listen` question, `audio-lyrics-alignment`, `audio-analysis` | 0 *(measured)* | 0 *(measured)* |
| `audio-like`, `audio-unlike` | 0 *(measured)* | 0 *(measured)* |
| `playlists-create`, `playlists-add-clips`, `playlists-list-clips` | 0 *(measured)* | 0 *(measured)* |

A `duration` of 60 seconds cost the same 10 credits as an open-ended song.

A terminal audition **is** a download. The take you keep costs one download credit either way; each rejected take you play in the terminal costs one more. The browser is free, which is why it is the default.

---

## Track File → Request

`get_generation_request(album, track)` reads what kind of request the track makes, names the Suno tool for it in `tool`, and builds that tool's arguments:

| Kind | When | Tool |
|---|---|---|
| `song` | Any other track | `audio-create` |
| `cover` | **Source audio** in the Cover / Voice Setup block holds a `https://suno.com/song/<id>` address | `audio-covers-create` |
| `speech` | The frontmatter says `spoken: true` | `speech-create` |
| `midi` | The tool is given a `midi_upload_id` (`/bitwize-music:generate --midi`) | `audio-create` |

Anything the track file sets that the kind's tool cannot carry comes back under `ignored`, with the reason, and `/bitwize-music:generate` shows it before the go-ahead. A song maps like this:

| Track file | Argument | Notes |
|---|---|---|
| Title | `title` | ≤ 256 characters |
| Lyrics Box | `lyrics` | ≤ 5000. Kept for instrumentals: tags-only lyrics were accepted and not sung *(measured)* |
| Style Box | `style` | ≤ 1000. Used as written when Variety is Off. `metadata.style` always echoes what was sent, so it cannot show whether Variety rewrote it |
| Exclude Styles | `negative_style` | ≤ 1000. `(none)` or an untouched placeholder sends nothing. Old-style `no drums` items are sent bare (`drums`), with a warning to fix the file |
| `instrumental: true` | `instrumental` | Frontmatter and the Track Details row must agree |
| Model `v6` / `v6-wild` / `v6-mini` | `model` | `Custom: <name>` is not offered — use suno.com |
| Max Mode `On` | `max_mode: true` | `Off` sends nothing. Suno asks that Max Mode be turned on only at the user's request, so `/generate` names it and its cost before asking for the go-ahead |
| Vocal Gender | `vocal_gender` | `male` / `female`; `—` sends nothing; never sent for an instrumental |
| Duration `m:ss` | `duration` | Seconds, 15–360, a hard cap. `Auto` sends nothing |
| Weirdness / Style Influence 0–100 | `controls.weirdness` / `controls.style_influence` | Sent as 0–1 |
| Variety `Off` / `Normal` / `High` / `Extra` / `Max` | `controls.variety` | 0–4. Always sent, and `Off` (0) when the row is blank or the section is missing: left out, Suno applies the model's own default, which is Normal on v6 and v6-mini and rewrites the Style Box |

The sliders, `negative_style` and `vocal_gender` need the `controls.advanced` feature; `controls.variety` does not. The tool lists what needs it under `needs_grant` (`controls.weirdness`, `controls.style_influence`, `controls.audio_influence`, `negative_style`, `vocal_gender`); drop those, and say so, when `account-usage` does not list the feature.

### Covers and Voices

Both come from the track's **Cover / Voice Setup** block (`templates/track.md`). A cell still holding the template's bracketed placeholder counts as empty.

| Track file | Argument | Notes |
|---|---|---|
| Source audio: a `https://suno.com/song/<id>` address | `id` on `audio-covers-create` | The song to cover — your own, or one suno.com lets you remix. A share link (`suno.com/s/…`) carries no id, and audio that is not on Suno cannot be covered from here: both stop the request rather than quietly making an original |
| Style Box | `style` | The **new** style |
| Lyrics Box | `lyrics` | What gets sung. A cover sent no lyrics comes back instrumental, so an instrumental track sends none and a vocal track must have them |
| Audio Influence `70`, `70%` or `0.7` | `controls.audio_influence` | Likeness to the source for a cover, to the Voice for a song. Sent only when there is one of the two |
| Voice: the saved Voice's name | `voice_id` | The tool returns `voice: {name}`; the skill finds the id with `voices-list(query)` — own Voices first, then `collection: "loved"` — and adds it. Vocal Gender is not sent with a Voice, and a Voice on an instrumental track is refused |

`audio-covers-create` has no `instrumental` and no `vocal_gender`; the rest (model, Max Mode, duration, exclusions, sliders, workspace) goes along as for a song.

**Putting a Voice on a track.** `/bitwize-music:suno-voice` finds the Voice with `voices-list(query)` (own, then `collection: "loved"`) and only then calls the plugin's `set_track_voice`, which writes the **Voice** row, adds the block above Suno Inputs when the track has none, and records the song the Voice was made from (`root_clip_id`). With no track named it covers every track of the album that has lyrics and lists the instrumental ones it skipped. `"—"` takes the Voice off. Free: nothing is generated until `/generate`.

**Making a new Voice.** `voices-start` takes no arguments and returns a suno.com `url` where the user records and verifies the Voice; it then appears in `voices-list`. Suno's rule is never to ask the user for recordings or files. The plugin calls it only when the user asks to make a Voice. Not measured.

*Measured:* a cover of a 52-second take in a new style made two covers of 62 and 65 seconds for 10 credits; they took the source's title and came back with `metadata.cover_audio_id`. At Audio Influence 70 the cover kept the source's tempo (about 95 BPM measured) although the new style asked for 80. A song sent with a `voice_id` cost the same 10 credits and came back with `metadata.voice_id`.

### Spoken Word

`spoken: true` in a track's frontmatter sends it to `speech-create`.

| Track file | Argument | Notes |
|---|---|---|
| Lyrics Box | `script` | Spoken word for word. Section tags and bracketed cues are taken out; blank lines between paragraphs stay. ≤ 5000 characters |
| Style Box | `style` | Delivery tags ("calm narrator, warm, close microphone"), and the style of the music bed when there is one |
| Backing Music `On` (Generation Settings) | `backing_music: true` | Off unless the row says On |
| Vocal Gender, Duration, Exclude Styles, Voice | `vocal_gender`, `duration`, `negative_style`, `voice_id` | As for a song |

Speech has no model, no Max Mode and no `controls`, so those settings are listed under `ignored`.

*Measured:* one call made two clips for 10 credits, 20 and 50 seconds long from the same four-sentence script. Suno reworded the delivery tags for each ("calm narrator, warm, close microphone" became "tense and strident delivery" on one and "deep bass register, flat affectless monotone" on the other), which is why the two differ. The listening agent heard the script word for word and no music.

### A MIDI Score

`/bitwize-music:generate <album> <track> --midi [file]` has Suno play a melody from a MIDI file.

1. `get_midi_score_plan` checks the file — a MIDI header, at most 256 KB — and without a file uses the track's own under `sheet-music/source/`, where MIDI From Suno saves a transcription.
2. The upload is three free steps: `midi-upload-create` (no arguments) answers `{midi_upload_id, upload_url, upload_fields, max_bytes}`; the file goes to `upload_url` as a multipart form with every field first and the file last as `file` (HTTP `204` on success); `midi-upload-complete(id)` checks it.
3. `get_generation_request(album, track, midi_upload_id)` builds the request: `midi_upload_id`, a `description` made from the Style Box ("An instrumental that plays my melody, in this style: …"), `instrumental: true` and `model: "v6-wild"`, the only model that plays a score.

A score is sent in Suno's simple mode, which takes a description and nothing else of the track's: no lyrics, no style field, no exclusions, no Max Mode, no sliders. So a score makes an **instrumental**. For an instrumental track the takes are the track. For a vocal track they are sketches: put the chosen sketch's address in Source audio and generate again, and the cover sings the Lyrics Box over it.

*Measured:* a two-track, 3 KB score of about 55 seconds made two instrumentals of 64 seconds for 10 credits; `metadata.lyrics` read `[Instrumental]` and Suno wrote the style from the description. The listening agent heard solo guitar carrying the melody; the bass and brushed snare the description also named were not heard. Covering a sketch with lyrics was not measured as a chain — each call was, on its own.

---

## Tool Notes

**Generation**
- `audio-create` answers `{"clip_ids": [a, b], "id": a, "status": "submitted"}`. There is no way to ask for one song.
- Wait with `audio-wait`, passing every id in `ids` and `until: "complete"`. It returns after about 50 seconds whether or not the songs are done; call it again while any is pending.
- Pass an `idempotency_key` and reuse it on a retry, so a timeout cannot charge twice.
- Clip data (`audio-wait`, `audio-retrieve`, the library tools) carries `song_url` — the suno.com page — and no audio link.

**Downloads**
- `audio-download` without `confirm` answers `requires_credit` when the download would spend a download credit. Ask the user, then call again with `confirm: true`.
- `processing` means the file is being prepared: call `audio-download` again.
- Leave a second or two between calls. A burst is refused with `rate_limited` and a `retry_after_seconds`.
- Links last one hour. WAV is 16-bit / 48 kHz stereo; MP3 is about 184 kbps.

**Stems**
- `audio-stems-create` answers `{"id": "stemgrp_…", "status": "pending", "stems": [{"name", "audio_id", "take", "status", "duration"}, …]}`. Poll `audio-stems-retrieve` with the source clip id and that group id until `status` leaves `pending` — about a minute and a half for a one-minute song.
- `twelve` names its parts `vocals`, `backing_vocals`, `drums`, `bass`, `guitar`, `keyboard`, `percussion`, `strings`, `synth`, `fx`, `brass`, `woodwinds`, each as take 1 and take 2. Import one take; the two are separate renderings and do not sum together.
- A part the song lacks still arrives, as a near-silent stem. The mix tools skip those on their own.
- Each stem is a song in the Suno library. They are not filed in a workspace automatically.

**Workspaces**
- `audio-create` takes `workspace_id`; the two new songs are filed there at creation. `/bitwize-music:generate` gets the id from `get_album_workspace` (the album README's `suno_workspace` block) and creates the workspace, named after the album, the first time.
- `workspaces-update-clips(id, add, remove)` files up to 50 songs per call and answers `skipped` for any it could not move; a song is in at most one workspace, so adding moves it. `workspaces-list(query)` finds a workspace by name. Nothing deletes or renames a workspace. See [workspace-management.md](workspace-management.md).

**Likes**
- Approving a take likes it on suno.com (`audio-like`), so keepers collect under Liked Songs; a keeper that is replaced is un-liked (`audio-unlike`). `generation.like_keeper: false` turns this off.
- The plugin never sends `dislike: true`: that rating is the user's to give. It is not a way to delete either — a dislike sent through the server left the song in the library *(measured)*, and the server has no tool that deletes a song, a workspace or a playlist. Delete on suno.com.

**Playlists and publishing** (`/bitwize-music:release-director`, only on request)
- `get_suno_release_plan` lists each track's approved take in track order and what is missing; `set_album_playlist` records the playlist in the album README (`suno_playlist`), so a later run updates it instead of making another.
- `playlists-create` answers `{id, name, playlist_url, visibility, clip_count}`. `playlists-add-clips` takes 100 ids per call and keeps the order given *(measured)*; re-adding is the only way to reorder. Visibility is fixed at creation; no tool renames or deletes a playlist.
- `audio-settings(visibility: "public")` publishes a song. The plugin calls it only when the user asks to publish, one confirmed list at a time; Suno allows 100 publishes a day.

**Whole albums** — `/bitwize-music:generate <album>` reads `get_album_generation_plan`: the tracks that pass the gates and map to a request, the blocked ones with the reason, the ones that already have takes, and an estimate (10 credits a call, 20 with Max Mode). One go-ahead covers the listed calls; they run one after another.

**MIDI** — `audio-midi(id)` transcribes a song to a multi-track `.mid`: 10 song credits, none for a stem made with Get Stems or a song transcribed before; it needs a plan with Studio. `get_suno_midi_plan` names the keeper and the target file under `sheet-music/source/`.

**Promo passage** — the promo generator starts its passage on the nearest beat on its own; `generate_promo_videos(..., start_s)` takes a chosen start, and Suno's listening agent can name the hook's first downbeat for free (see `/bitwize-music:promo-director`).

**Not used by the plugin yet**: mashups, uploading audio to cover a file that is not on Suno (`audio-upload-create`), `audio-lyrics-alignment`, `audio-analysis`, and the other uses of `reference_audio_ids` (sampling, remastering).

**Not offered by the server**: deleting a song; Custom Models.

---

## Listening

`/bitwize-music:listen` opens a take's song page in your browser by default, because that is free. `--iterm2` shows the takes in panes beside the session instead, which is also free, with the track's Lyrics Box in a plain pane under them. The lyrics are not timed to the music: the plugin cannot see where Suno's player is. `--terminal` plays the take through your speakers.

- Terminal copies are saved as `~/.bitwize-music/cache/takes/<clip_id>.mp3` and replayed from there at no cost. The folder is a cache and safe to delete.
- Playback needs `mpv` (recommended — it can start mid-song), `ffplay` (part of ffmpeg) or macOS's built-in `afplay`.
- "Compare" plays the same passage of two to four files back to back (`compare_audio`): two takes, or a track's original, polished and mastered files. It needs `mpv`, the one player that takes several files with one start point and length.
- `prune_takes_cache` clears audition copies once a track has a keeper; copies of takes still awaiting a decision are kept. `/bitwize-music:listen` runs it when a keeper is named.
- `generation.listen_mode` sets the default (`browser`, `iterm2_browser` or `terminal`); `generation.listen_confirm_download: false` stops the question before a download credit is spent. See [config/README.md](../../config/README.md).

**iTerm2 panes** (`iterm2_browser`; measured on iTerm2 3.6.6)

- Needs macOS, iTerm2 3.6 or later and iTerm2's [Browser Plugin](https://iterm2.com/browser-plugin.html). Anywhere else — another terminal, tmux, an older iTerm2, no plugin, AppleScript refused — the takes open in the web browser and the tool says why.
- Each take opens as Suno's compact player, `https://suno.com/embed/<clip id>`, whose play button is at the top of the pane; on the full song page it is a scroll away. A share link from before MCP generation has no compact player and opens as the full page.
- The panes form a column to the right of the session, the first take on top, and iTerm2 shares the height evenly between them. The keyboard stays with the session.
- One click per take starts it: a browser never starts sound by itself, and iTerm2's AppleScript cannot press play, scroll a page or read its address.
- A browser pane takes its page only from a profile's Initial URL — a URL given as the pane's command closes the pane at once. So `open_song_page` writes one small profile per take to `~/Library/Application Support/iTerm2/DynamicProfiles/bitwize-music-listen-<pane id>.json` and waits the second or so iTerm2 needs to load it. `close_song_panes` closes the panes and removes that file; so does the next listen in the same session.
- Each Claude Code session has its own player panes, told apart by the iTerm2 pane the session runs in. Listening, or closing the players, in one session leaves another session's panes open. A session's files go once none of its panes is open any more ([#625](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/625)).
- The pane is iTerm2's own browser, with its own Suno sign-in. If a player says the song is not available, sign in to Suno in that pane once, or use `--browser`.

---

## Editing a Take

`/bitwize-music:edit-take` changes part of a take and keeps the rest: a word or a line, a cut or added line, a redone time range, an instrument added or dropped. It is the cheap fix for a take that is nearly right.

- **The call**: `audio-create` with the take in `reference_audio_ids`, a `description` that names the song by title ("In Paper Boats, change "…" to "…"."), and optionally `model` and `workspace_id`. `get_edit_request` builds it. Nothing else may go along: `duration`, `instrumental` and `vocal_gender` make Suno regenerate the whole song, `lyrics` and `style` are refused next to a `description`, and an id or link in the description is not allowed.
- **Two ways to say what changes**: the user's words, or the difference between the lyrics the take was made with (`audio-retrieve` → `metadata.lyrics`) and the track's Lyrics Box now — the way a pronunciation or wording fix made in the track file reaches a take.
- **More than five changed places** and Suno re-sings the whole song as a cover. The tool warns; regenerate instead.

*Measured, one word changed in a 55-second take:* one call made **two** edited takes for **10 song credits** in under a minute. Both kept the source's title and its length to the hundredth of a second, came back with `metadata.lyrics` updated and `metadata.description` holding the instruction, and were filed in the `workspace_id` given. The listening agent heard the new word in both; one of them also kept a quirk of the source take ("all lined up" for "are lined up"), which is what keeping the audio means.

### An Instrumental Version

The same call takes the vocals off a take: `get_edit_request(…, version: "instrumental")` writes "In <Title>, remove all the vocals to make an instrumental version. Keep everything else as it is."

- The two takes are logged with "instrumental version of take N" in their notes. Those words make them **versions**: `parse_generation_log` reports `version`, they are never the track's keeper, the take check leaves them out, and a ✓ on one marks the version to import.
- `get_suno_import_plan(album, track, version: "instrumental")` plans that import to `versions/<track>-instrumental.wav`, beside the album's audio and outside the folder the mastering tools read.

*Measured:* two takes for 10 credits, both 55.17 seconds against the source's 55.16, titled "<Title> (Instrumental)" by Suno, with no voice heard on either.

**An a cappella is not offered.** The same request for an a cappella returned one take of the source's length with no voice on it — the instrumental again — and one of 35 seconds, sung afresh with its guitar. The vocals stem of a stem split is the a cappella.

---

## Extending a Take

`/bitwize-music:extend-take` keeps a take up to a point and generates what follows: more of a song that stopped early, or a new second half.

- **The call**: `audio-extensions-create` with `id` (the take), `continue_at` (seconds into it), and `lyrics`, `style`, `negative_style`, `model`, `max_mode`, `controls` and `workspace_id` from the track. `get_extension_request` builds it. No `duration` is sent — it would cap the new ending — and the tool has no `vocal_gender`.
- **The words** are the track's Lyrics Box from a named section to the end (`from_section: "Verse 2"`, or `"Chorus #2"` for the second Chorus), so they have passed the track's checks. With no section named, no lyrics are sent and Suno writes on by itself.
- **The answer holds only the continuation.** `audio-full-song(id: <continuation>)` joins it to what came before, free, and returns a new song. Each of the two continuations ends its own chain, so each is joined and the two whole songs are logged as takes.
- A joined song is **not** filed in the workspace its parts are in, and `audio-full-song` takes no workspace: file it with `workspaces-update-clips`.

*Measured, a 55-second take carried on from 0:46 with a two-line verse:* one call made two continuations of 51 seconds for 10 credits (`metadata.extend_audio_id`, `metadata.continue_at`); each joined into a whole song of 97 seconds (`metadata.concat_clip_ids`) in the same voice, with the new verse sung about 14 seconds in. 0:46 fell inside a phrase, and the listening agent heard the cut — carry on from the end of a line. The joined song's `metadata.lyrics` is the source's whole lyrics followed by the continuation's, including the lines after the cut that are no longer sung.

---

## Sounds

`/bitwize-music:sound-effects` makes an effect, a one-shot or a loop: `sounds-create` with a `description` (≤ 500 characters), `loop`, and optionally `tempo`, `key` and `title`. `get_sound_request` builds it, takes the tempo and key from a track's Style Box when asked to fit the sound to it, and names the `sounds/` folder under the album's audio for saving.

- Two sounds of about 20 seconds for 1 credit each. The model and the length are Suno's choice. Sounds need Suno's Pro plan or higher.
- `sounds-create` takes no workspace; the skill files the two sounds afterwards.
- A sound is an ordinary song in the library: it opens, downloads and is listened to like one.

*Measured:* "soft rain on a window, gentle and steady" as a loop made one clip of rain and one with a piano melody over a soft background — hear both. A guitar loop asked for at 96 BPM in G was measured at 96 BPM; the listening agent named its key as D major, so the key is not confirmed.

---

## Take Check

`/bitwize-music:check-take` holds a take against its track file, and `/bitwize-music:generate` runs it on the two new takes while you listen. It reports; it never picks a take.

- **How**: `get_take_check_plan` numbers the lyric lines and writes the questions; the skill puts them to Suno's listening agent (`audio-listen`, read with `audio-listen-wait`); `evaluate_take_check` reads the JSON block the agent ends its answer with. A question holds 2,000 characters, so long lyrics are split across questions; only the first asks about the sound.
- **What it checks**: lyric lines not sung, sung with different words or hard to understand, with what was heard instead; tempo against the BPM in the Style Box (a tempo measured at double or half the one asked for counts as a match — a relaxed 96 BPM song is often measured at 190); the voice against Vocal Gender; Exclude Styles items that turn up among the instruments; problems the agent names; a clean ending; length against the track's Target Duration.
- **Limits**: five unanswered questions at a time, 200 a day. An answer arrives in under a minute.
- `generation.take_check: false` stops `/generate` from running it; the skill still runs on request.

**Why the listening agent** *(measured on a 52-second test song)*:

- `audio-lyrics-alignment` returned a transcript that left out the first two sung lines and stretched the third across their place, with every word marked `success` and `p_align: 1`. A local Whisper transcription of the same audio heard all four lines. A check built on alignment would have raised a false "two lines missing".
- The agent placed all four lines correctly, noticed "Kettle" sounding like "Cattle" (the local transcription heard the same) and, on the other take, "all lined up" for "are lined up".
- `audio-analysis` has the same tempo and key, but it returns every beat of the song — 164 entries for 52 seconds — which is too much to pass through a model for a check. It is the right tool for cutting video to the beat.

The agent is not infallible: asked twice about one take, it agreed with itself on the changed line and differed on whether the chorus repeats. One of its answers closed its JSON block with a stray backtick; the evaluator reads that too. Treat a flag as a place to listen.

---

## Fallback

When the server is missing, not signed in, lacks a feature, or the track uses a Custom Model:

1. `/bitwize-music:clipboard suno <album> <track>` copies the title, Style Box, Exclude Styles and lyrics.
2. Paste into suno.com (the [auto-fill userscript](../../tools/userscripts/README.md) fills the form).
3. Add a Generation Log row by hand and set the Suno Link.

---

## Sources

- [Suno MCP](https://suno.com/mcp) · [What is Suno MCP (Beta)?](https://help.suno.com/en/articles/14551361) · [Connecting it](https://help.suno.com/en/articles/14551425) · [FAQ](https://help.suno.com/en/articles/14486145)
- [Download limits](https://help.suno.com/en/articles/13614785) — "Streaming and sharing on Suno remain unlimited on every plan"; one song is one download whatever the format; stems count as part of the song's download.
