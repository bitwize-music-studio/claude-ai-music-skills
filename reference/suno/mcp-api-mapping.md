# Suno MCP: Setup, Costs and Track-File Mapping

Suno runs an official MCP server (beta since October 2026). When it is connected, the plugin can generate a track, play the takes and import the keeper without a trip to suno.com. When it is not, everything falls back to the clipboard flow and nothing breaks.

> **Related skills**: `/bitwize-music:generate`, `/bitwize-music:listen`, `/bitwize-music:import-audio`
> **Related docs**: [models.md](models.md), [creative-sliders.md](creative-sliders.md), [tips-and-tricks.md](tips-and-tricks.md)

Everything marked *measured* was tested on a Premier account. The server is in beta and its tools change — treat the live tool definitions as the authority over this page.

---

## Setup

The plugin does not ship the Suno server; you add it to your own Claude Code once:

```bash
claude mcp add --transport http suno https://api.suno.com/mcp
```

Then run `/mcp` in a session and sign in to your Suno account. Name the server `suno` as above — the skills pre-approve tools under that name. Songs made this way use your plan's credits and land in your Suno library.

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
| `audio-stems-create`, `twelve` (two takes of 12 stems) | 50 *(measured)* | 0 |
| `audio-stems-create`, `two` (vocals + instrumental) | 10 | 0 |
| Listen on the song's suno.com page | 0 | 0 |
| First `audio-download` of a song, MP3 or WAV | 0 | 1 *(measured)* |
| Any later download of that song, either format | 0 | 0 *(measured)* |
| Downloading the stems of a song that has been downloaded | 0 | 0 *(measured)* |
| Playing a file already on disk | 0 | 0 |

A `duration` of 60 seconds cost the same 10 credits as an open-ended song.

A terminal audition **is** a download. The take you keep costs one download credit either way; each rejected take you play in the terminal costs one more. The browser is free, which is why it is the default.

---

## Track File → `audio-create`

`get_generation_request(album, track)` builds the arguments from the track's Suno Inputs:

| Track file | Argument | Notes |
|---|---|---|
| Title | `title` | ≤ 256 characters |
| Lyrics Box | `lyrics` | ≤ 5000. Kept for instrumentals: tags-only lyrics were accepted and not sung *(measured)* |
| Style Box | `style` | ≤ 1000. Used word for word — both takes came back with `metadata.style` identical to the input *(measured)* |
| Exclude Styles | `negative_style` | ≤ 1000. `(none)` or an untouched placeholder sends nothing. Old-style `no drums` items are sent bare (`drums`), with a warning to fix the file |
| `instrumental: true` | `instrumental` | Frontmatter and the Track Details row must agree |
| Model `v6` / `v6-wild` / `v6-mini` | `model` | `Custom: <name>` is not offered — use suno.com |
| Max Mode `On` | `max_mode: true` | `Off` sends nothing. Suno asks that Max Mode be turned on only at the user's request, so `/generate` names it and its cost before asking for the go-ahead |
| Vocal Gender | `vocal_gender` | `male` / `female`; `—` sends nothing; never sent for an instrumental |
| Duration `m:ss` | `duration` | Seconds, 15–360, a hard cap. `Auto` sends nothing |
| Weirdness / Style Influence 0–100 | `controls.weirdness` / `controls.style_influence` | Sent as 0–1 |
| Variety | — | No equivalent; the Style Box is always used as written |

`controls`, `negative_style` and `vocal_gender` need the `controls.advanced` feature. The tool lists them under `needs_grant`; drop them, and say so, when `account-usage` does not list the feature.

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

**Not used by the plugin yet**: covers, extensions, mashups, `reference_audio_ids` edits, speech, sounds, MIDI, `audio-listen`, `audio-analysis`, workspaces, playlists, `audio-settings`.

**Not offered by the server**: deleting a song; Custom Models.

---

## Listening

`/bitwize-music:listen` opens a take's song page in your browser by default, because that is free. `--terminal` plays the take through your speakers instead.

- Terminal copies are saved as `~/.bitwize-music/cache/takes/<clip_id>.mp3` and replayed from there at no cost. The folder is a cache and safe to delete.
- Playback needs `mpv` (recommended — it can start mid-song), `ffplay` (part of ffmpeg) or macOS's built-in `afplay`.
- `generation.listen_mode` sets the default (`browser` or `terminal`); `generation.listen_confirm_download: false` stops the question before a download credit is spent. See [config/README.md](../../config/README.md).

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
