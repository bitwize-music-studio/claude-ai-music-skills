# AI Music Skills - Claude Instructions

This is an AI music generation workflow using Suno. Skills contain domain expertise; this file contains workflow rules and structure that apply every session.

---

## ⚠️ CRITICAL: Finding Albums When User Mentions Them

**WHENEVER the user mentions an album name**, use the resume skill:
```
/bitwize-music:resume my-album
```

**If skill unavailable**, manual approach:
1. Read `~/.bitwize-music/cache/state.json` — search `state.albums` keys (case-insensitive)
2. If cache missing/stale: read config → glob `{content_root}/artists/{artist}/albums/*/*/README.md` → rebuild cache with `rebuild_state()` MCP tool

**DO NOT**: search from cwd, use complex globs, assume paths, or use `ls`/`find`.

---

## Configuration & Path Resolution

Config is **always** at: `~/.bitwize-music/config.yaml`

**ALWAYS read config fresh before** moving/creating files, resolving path variables, or using artist name in paths. Never assume or remember values.

**Path variables** (from config):
- `{content_root}` = `paths.content_root`
- `{audio_root}` = `paths.audio_root`
- `{documents_root}` = `paths.documents_root`
- `{tools_root}` = `~/.bitwize-music`
- `{plugin_root}` = the directory containing this CLAUDE.md file (= `${CLAUDE_PLUGIN_ROOT}` in skills)
- `[artist]` = `artist.name`

**IMPORTANT — Mirrored path structure**:
```
{content_root}/artists/[artist]/albums/[genre]/[album]/   # Album files (in git)
{audio_root}/artists/[artist]/albums/[genre]/[album]/     # Mastered audio
{documents_root}/artists/[artist]/albums/[genre]/[album]/ # PDFs (not in git)
```
Audio and document paths include `[artist]/` after the root. Common mistake: omitting the artist folder.

First-time setup: `cp config/config.example.yaml ~/.bitwize-music/config.yaml` — see `config/README.md`.

---

## MCP Server — Preferred Data Access

The `bitwize-music-mcp` server is the **preferred way to query project state**. Use MCP tools instead of reading files directly — they're faster (single call vs multiple file reads) and return structured data.

**Use MCP tools for:**
- **Albums/tracks** → `list_albums`, `find_album`, `get_track` (not reading state.json or globbing for READMEs)
- **Skills** → `list_skills`, `get_skill` (not reading individual SKILL.md files)
- **Ideas** → `get_ideas` (not reading IDEAS.md)
- **Pending verifications** → `get_pending_verifications`
- **Config** → `get_config` (not reading config.yaml for simple lookups)
- **Session context** → `get_session`, `update_session`
- **Cross-scope search** → `search`
- **Stale cache** → `rebuild_state`

**Fall back to direct file access only when:** MCP server is unavailable, you need to edit files (MCP is read-only), or you need raw file content not exposed through MCP (e.g., full lyrics, research docs).

---

## Session Start

At the beginning of a fresh session:

1. **Verify setup** — Quick dependency check:
   ```bash
   python3 -c "import mcp" 2>&1 >/dev/null && echo "✅ MCP ready" || echo "❌ MCP missing"
   ```
   - If MCP missing → **Stop immediately** and suggest: `/bitwize-music:setup mcp`
   - If config missing → suggest: `/bitwize-music:configure`
   - Don't proceed with session start until setup is complete
2. **Load config** — Read `~/.bitwize-music/config.yaml`. If missing, tell user to run `/bitwize-music:configure`.
3. **Load overrides** — Check `paths.overrides` (default: `{content_root}/overrides`):
   - `{overrides}/CLAUDE.md` → incorporate instructions
   - `{overrides}/pronunciation-guide.md` → merge with base guide
   - Skip silently if missing (overrides are optional)
4. **Load state via MCP** — Use MCP tools to query project state:
   - `get_config` → verify config is loaded
   - `list_albums` → get album statuses
   - `get_ideas` → get idea counts
   - `get_pending_verifications` → check for pending source verifications
   - `get_session` → resume last session context
   - If MCP returns errors about missing/stale cache → `rebuild_state()` MCP tool
4.5. **Check for plugin upgrades** — Compare `plugin_version` in state.json vs `.claude-plugin/plugin.json`:
   - If `plugin_version` is null → first run, set to current version, skip migrations
   - If stored < current → read `{plugin_root}/migrations/*.md` for applicable versions, process actions
   - If versions match → no action
5. **Check skill models** — Run `/bitwize-music:skill-model-updater check`
6. **Report from MCP state**:
   - Album ideas (from `get_ideas`)
   - In-progress albums (status: "In Progress", "Research Complete", "Complete")
   - Pending source verifications (from `get_pending_verifications`)
   - Last session context (from `get_session`)
7. **Show contextual tips** based on state:
   - No albums → suggest `/bitwize-music:tutorial`
   - Ideas exist → suggest `/bitwize-music:album-ideas list`
   - In-progress albums → suggest `/bitwize-music:resume [album-name]`
   - Overrides loaded → note it; missing → suggest creating them (see `config/README.md` for override file reference)
   - Pending verifications → warn and suggest `/bitwize-music:verify-sources`
   - One contextual tip from: resume, researcher, pronunciation, clipboard, mastering (pick based on most relevant album state)
8. **Ask**: "What would you like to work on?"

---

## Core Principles

**Be a collaborator, not a yes-man.** Push back when ideas don't work. The goal is good music, not agreement.

**Preserve exact casing and spelling.** "bitwize" stays "bitwize" — never auto-capitalize user-provided names, titles, or text.

**Ask when unsure.** Word choice, style, structure, Suno settings — don't guess.

**Pronunciation hard rule**: Suno CANNOT infer pronunciation from context. When any homograph is found (live, read, lead, wound, close, bass, tear, wind, etc.), **ASK** the user which pronunciation is intended — never assume. Fix with phonetic spelling in Suno lyrics only. See `/skills/lyric-writer/SKILL.md` and `/reference/suno/pronunciation-guide.md` for full rules.

**After writing or revising lyrics**, run the 13-point quality checklist from `/skills/lyric-writer/SKILL.md`. Report violations without being asked.

**When user says "let's work on [track]"**, scan full lyrics for issues BEFORE doing anything else: weak lines, prosody problems, POV/tense inconsistencies, twin verses, missing hook, factual errors, flow/pronunciation risks.

---

## Workflow Overview

Concept → Research → Write (+Suno Prompt) → QC/Verify → Generate → [Polish] → Master → Promo Videos (optional) → Promo Copy (optional) → **Release**

**Critical**: Research must complete before writing for source-based content. Human source verification is required before generation — never skip this gate.

### Key Routing Rules

- **Album mentioned** → `/bitwize-music:resume`
- **"Make a new album"** → IMMEDIATELY use `/bitwize-music:new-album` BEFORE any discussion
- **Writing lyrics** → apply `/bitwize-music:lyric-writer` expertise (auto-invokes suno-engineer)
- **Planning album** → apply `/bitwize-music:album-conceptualizer` (7 planning phases required)
- **Suno prompts** → apply `/bitwize-music:suno-engineer` expertise (usually auto-invoked by lyric-writer; use directly only for re-prompting)
- **Research needed** → apply `/bitwize-music:researcher` standards
- **Polishing audio / fixing Suno artifacts** → apply `/bitwize-music:mix-engineer` expertise
- **Mastering audio** → apply `/bitwize-music:mastering-engineer` standards
- **Album art** → apply `/bitwize-music:album-art-director`
- **Writing promo copy** → apply `/bitwize-music:promo-writer` expertise
- **Releasing** → apply `/bitwize-music:release-director`

- **Checking for plagiarism** → `/bitwize-music:plagiarism-checker` (web search + LLM knowledge)
- **Verifying sources** → `/bitwize-music:verify-sources` (human verification gate)
- **"What skills do X?"** → `list_skills` / `get_skill` MCP tools (not reading SKILL.md files)

Skills contain the deep expertise. See `/reference/SKILL_INDEX.md` for the full decision tree.

### Source Verification Gate

1. Capture sources FIRST — every source must be a clickable markdown link `[Name](URL)`
2. Save RESEARCH.md and SOURCES.md to album directory (never cwd)
3. After adding sources → status: `❌ Pending` → human verifies via `/bitwize-music:verify-sources` → `✅ Verified (DATE)`
4. Block generation if verification incomplete — `/bitwize-music:pre-generation-check` enforces this

### Status Tracking

**Track statuses** (in order):
`Not Started` → `Sources Pending` → `Sources Verified` → `In Progress` → `Generated` → `Final`

- `Not Started`: No work begun on this track
- `Sources Pending`: Sources gathered, awaiting human verification
- `Sources Verified`: Human confirmed all sources via `/bitwize-music:verify-sources`
- `In Progress`: Lyrics being written or revised
- `Generated`: Track generated on Suno, audio exists
- `Final`: Approved and ready for mastering

**Album statuses** (in order):
`Concept` → `Research Complete` → `Sources Verified` → `In Progress` → `Complete` → `Released`

- `Concept`: Initial planning, album README created
- `Research Complete`: All research done, sources gathered (documentary albums)
- `Sources Verified`: Human verified all track sources
- `In Progress`: Active writing/generation work
- `Complete`: All tracks Final, ready for mastering/release
- `Released`: Published to streaming platforms

**Transition rules**: Album status advances when ALL tracks reach the corresponding level. A single unverified track keeps the album from advancing past "Research Complete".

See `/reference/state-schema.md` for the full state cache schema.

---

## Content Structure

Albums: `{content_root}/artists/[artist]/albums/[genre]/[album]/`
Templates: `{plugin_root}/templates/` — use for all new content
Research staging: `{content_root}/research/` (move to album directory once album exists)

**Album directory layout:**
```
{album}/
├── README.md
├── SOURCES.md        # (documentary albums)
├── RESEARCH.md       # (documentary albums)
├── tracks/
│   ├── 01-track-name.md
│   └── ...
└── promo/            # Social media copy
    ├── campaign.md
    ├── twitter.md
    ├── instagram.md
    ├── tiktok.md
    ├── facebook.md
    └── youtube.md
```

Track files: zero-padded (`01-`, `02-`). Import with `/bitwize-music:import-track`, `/bitwize-music:import-audio`.

`promo_videos/` in `{audio_root}` holds video files (unchanged). `promo/` in album directory holds social media copy (text).

Currently supports **Suno** (default). Service-specific template sections marked with `<!-- SERVICE: suno -->`.

---

## Versioning & Development

[Semantic Versioning](https://semver.org/) with [Conventional Commits](https://conventionalcommits.org/).

| Prefix | Version Bump |
|--------|--------------|
| `feat:` | MINOR |
| `fix:` | PATCH |
| `feat!:` | MAJOR |
| `docs:`, `chore:` | None |

**Co-author line**: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

**Version files (must stay in sync)**: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`

**Release process**: Update CHANGELOG.md `[Unreleased]` → `[0.x.0 - DATE]`, update version in both plugin files, update README "What's New" table if notable. Commit: `chore: release 0.x.0`

**Development workflow**: Feature branch → Conventional Commits → `/bitwize-music:test all` → PR → Merge. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Mid-Session Rules

**Workflow file changes take effect immediately.** Re-read after any edit to CLAUDE.md or templates.

**Lessons learned protocol**: When you discover a technical issue during production (pronunciation error, rhyme violation, wrong assumption):
1. Fix the immediate issue
2. Sweep the album for the same issue
3. Propose a rule to prevent recurrence: "I found [issue]. Here's a rule: [rule]. Should I add it to [location]?"

**Self-updating skills**: When a skill discovers something new, it adds to the relevant reference file. User-specific content (pronunciations) goes to `{overrides}/` directory.
