# bitwize-music: rules for every session

An AI music workflow on Suno. Skills hold the expertise; these rules hold in every session. `{plugin_root}` is the plugin's folder.

## Finding albums

Whenever the user names an album, run `/bitwize-music:resume <album>`. Without it: `find_album` / `list_albums` MCP tools, else read `~/.bitwize-music/cache/state.json` and `rebuild_state()` if it is stale. Never search from the working directory, guess paths, or use `ls`/`find`. Album slugs are unique across genres; resolve a collision `health_check` reports before trusting a lookup.

## Config and paths

Config is always `~/.bitwize-music/config.yaml`. Read it fresh (`get_config`) before creating or moving files or putting the artist name in a path; never assume values. `{content_root}`, `{audio_root}`, `{documents_root}` = `paths.*`; `[artist]` = `artist.name`. Paths mirror each other, artist folder included:

```
{content_root}/artists/[artist]/albums/[genre]/[album]/    # album files (git)
{audio_root}/artists/[artist]/albums/[genre]/[album]/      # audio
{documents_root}/artists/[artist]/albums/[genre]/[album]/  # PDFs (not git)
```

New content starts from `{plugin_root}/templates/`. Track files are zero-padded (`01-`). Research is staged in `{content_root}/research/` until the album exists. No config yet: `/bitwize-music:configure`.

## Data access

Query state through the `bitwize-music-mcp` tools (`list_albums`, `find_album`, `get_track`, `get_ideas`, `get_pending_verifications`, `get_config`, `get_session`, `search`, `list_skills`/`get_skill`), not by reading files. Read files directly only to edit them, for content the tools don't return, or when the server is down.

## Suno

Suno's MCP server is optional and the user adds it. Without it, generation falls back to `/bitwize-music:clipboard`.
- **Never spend Suno credits of any kind without a go-ahead that states the cost**: generating, stems, a download that answers `requires_credit`, any image or video (Visuals credits are a separate balance). Reading the library and account is free.
- **Never pick a take or image, mark a keeper, set a track `Final`, or change a song's visibility.** The user listens or looks first.
- **The live tool definitions win.** Suno still adds tools and changes arguments; a session lists the tools from its start, so restart before calling one missing. Costs and mapping: `{plugin_root}/reference/suno/mcp-api-mapping.md`.

## Session start

In a fresh session, before other work, follow `/bitwize-music:session-start` (setup check, health check, config, overrides including `{overrides}/CLAUDE.md`, state, pending migrations, status report, then ask what to work on). If the MCP server is unusable, stop and suggest `/bitwize-music:setup mcp`.

## Core principles

- **A collaborator, not a yes-man.** Push back when an idea doesn't work. The goal is good music.
- **Keep the user's exact casing and spelling.** "bitwize" stays "bitwize".
- **Ask when unsure** about word choice, style, structure or Suno settings.
- **Pronunciation is a hard rule.** Suno can't infer it from context. For any homograph (live, read, lead, wound, close, bass, tear, wind…) ask which is meant, never assume, and fix it with phonetic spelling in the Suno lyrics only. See `{plugin_root}/reference/suno/pronunciation-guide.md`.
- **After writing or revising lyrics**, run the lyric-writer quality checklist and report violations unasked.
- **"Let's work on [track]"**: scan the whole lyric first for weak lines, prosody, POV/tense slips, twin verses, a missing hook, factual errors, pronunciation risks.

## Workflow and routing

Concept → Research → Write (+ Suno prompt) → Refine → QC/verify → Generate → Polish → Master → Promo → Release. For source-based albums, research comes before writing, and **human source verification comes before generation, always**. Target duration: the track's, else the album's (set in planning phase 3), else the genre default.

- Album named → `resume`. "Make a new album" → `new-album` immediately, before discussing. Promote an idea → `promote-idea`
- Plan an album → `album-conceptualizer` (7 phases). Research → `researcher`. Verify sources → `verify-sources`
- Write lyrics → `lyric-writer` (calls `suno-engineer`). Refine → `lyric-refiner`. Re-prompt Suno → `suno-engineer`
- Generate (covers, Voices, spoken word, `--midi` too) → `generate`. Hear takes → `listen`. Check a take → `check-take`
- Fix one thing in a take → `edit-take`. A take that stops early → `extend-take`. Sounds and loops → `sound-effects`. Voices → `suno-voice`
- Import the keeper → `import-audio --from-suno`
- Polish → `mix-engineer`. Master → polish first, then `mastering-engineer`, unless the user says master only / skip polish / already polished, or `polished/` exists
- Album art → `album-art-director` (Codex or Suno generation costs: state it and wait). Lyric video → `lyric-video`. Music video → `music-video` (clips can cost thousands of Visuals credits: say so first). Promo clips and videos → `promo-director`. Promo copy → `promo-writer`
- Release → `release-director`. DistroKid/SoundCloud forms → `release-kit`
- Plagiarism → `plagiarism-checker`. AI-sounding text → `voice-checker`. Which skill does X → `list_skills`/`get_skill`

All are `/bitwize-music:<name>`. Full decision tree: `{plugin_root}/reference/SKILL_INDEX.md`.

## Gates and statuses

- **Sources**: every source is a markdown link `[Name](URL)`, saved in the album's RESEARCH.md / SOURCES.md (never the working directory), `❌ Pending` until the human verifies with `verify-sources`. `pre-generation-check` blocks generation until then.
- **Track**: Not Started → Sources Pending → Sources Verified → In Progress → Generated → Final. Only `Final` with a ✓ keeper in the Generation Log.
- **Album**: Concept → (Research Complete → Sources Verified, documentary only) → In Progress → Complete → Released. It advances when all tracks reach the level; `update_track_field` advances it to Complete when the last track goes Final.
- **A rejected take**: log the reason in the Generation Log; status stays Generated. Fix the style (`suno-engineer`), the lyrics (`lyric-writer` + `pronunciation-specialist`), one flaw (`edit-take`, up to five places), or regenerate as is.

Statuses, regeneration and recovery: `{plugin_root}/reference/workflows/status-tracking.md`, `{plugin_root}/reference/workflows/error-recovery.md`.

## Mid-session

- Workflow files and templates take effect when edited: re-read them.
- **Lessons learned**: fix the issue, sweep the album for the same issue, then propose a rule: "I found [issue]. Here's a rule: [rule]. Should I add it to [location]?"
- New user-specific knowledge (pronunciations) goes to `{overrides}/`; general discoveries go to the relevant reference file.
