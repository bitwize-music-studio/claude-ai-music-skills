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
| `audio-stems-create`, `twelve` (two takes of 12 stems) | 50 *(measured)* | 0 |
| `audio-stems-create`, `two` (vocals + instrumental) | 10 | 0 |
| Listen on the song's suno.com page | 0 | 0 |
| First `audio-download` of a song, MP3 or WAV | 0 | 1 *(measured)* |
| Any later download of that song, either format | 0 | 0 *(measured)* |
| Downloading the stems of a song that has been downloaded | 0 | 0 *(measured)* |
| Playing a file already on disk | 0 | 0 |
| `workspaces-create`, `workspaces-update-clips`, `workspaces-list` | 0 *(measured)* | 0 *(measured)* |

A `duration` of 60 seconds cost the same 10 credits as an open-ended song.

A terminal audition **is** a download. The take you keep costs one download credit either way; each rejected take you play in the terminal costs one more. The browser is free, which is why it is the default.

---

## Track File → `audio-create`

`get_generation_request(album, track)` builds the arguments from the track's Suno Inputs:

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

The sliders, `negative_style` and `vocal_gender` need the `controls.advanced` feature; `controls.variety` does not. The tool lists what needs it under `needs_grant` (`controls.weirdness`, `controls.style_influence`, `negative_style`, `vocal_gender`); drop those, and say so, when `account-usage` does not list the feature.

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

**Not used by the plugin yet**: covers, extensions, mashups, `reference_audio_ids` edits, speech, sounds, MIDI, `audio-listen`, `audio-analysis`, playlists, `audio-settings`.

**Not offered by the server**: deleting a song; Custom Models.

---

## Listening

`/bitwize-music:listen` opens a take's song page in your browser by default, because that is free. `--iterm2` shows the takes in panes beside the session instead, which is also free. `--terminal` plays the take through your speakers.

- Terminal copies are saved as `~/.bitwize-music/cache/takes/<clip_id>.mp3` and replayed from there at no cost. The folder is a cache and safe to delete.
- Playback needs `mpv` (recommended — it can start mid-song), `ffplay` (part of ffmpeg) or macOS's built-in `afplay`.
- `generation.listen_mode` sets the default (`browser`, `iterm2_browser` or `terminal`); `generation.listen_confirm_download: false` stops the question before a download credit is spent. See [config/README.md](../../config/README.md).

**iTerm2 panes** (`iterm2_browser`; measured on iTerm2 3.6.6)

- Needs macOS, iTerm2 3.6 or later and iTerm2's [Browser Plugin](https://iterm2.com/browser-plugin.html). Anywhere else — another terminal, tmux, an older iTerm2, no plugin, AppleScript refused — the takes open in the web browser and the tool says why.
- Each take opens as Suno's compact player, `https://suno.com/embed/<clip id>`, whose play button is at the top of the pane; on the full song page it is a scroll away. A share link from before MCP generation has no compact player and opens as the full page.
- The panes form a column to the right of the session, the first take on top, and iTerm2 shares the height evenly between them. The keyboard stays with the session.
- One click per take starts it: a browser never starts sound by itself, and iTerm2's AppleScript cannot press play, scroll a page or read its address.
- A browser pane takes its page only from a profile's Initial URL — a URL given as the pane's command closes the pane at once. So `open_song_page` writes one small profile per take to `~/Library/Application Support/iTerm2/DynamicProfiles/bitwize-music-listen.json` and waits the second or so iTerm2 needs to load it. `close_song_panes` closes the panes and removes that file; so does the next listen.
- There is one set of player panes per machine: listening from a second session closes the first session's panes.
- The pane is iTerm2's own browser, with its own Suno sign-in. If a player says the song is not available, sign in to Suno in that pane once, or use `--browser`.

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
