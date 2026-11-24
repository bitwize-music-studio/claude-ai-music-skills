---
name: session-start
description: Runs the session startup procedure - verifies setup, loads config and state, checks skill models, and reports project status. Use at the beginning of a fresh session.
model: sonnet
effort: low
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - WebSearch
  - WebFetch
  - bitwize-music-mcp
---

## Your Task

Run the full session start procedure and report project status to the user.

---

# Session Start Skill

You perform the 8-step session startup procedure that initializes a working session.

---

## Step 1: Verify Setup

Run the line for your platform once. Use its printed SDK status to decide
whether to continue with startup.

```bash
# macOS/Linux/WSL
(~/.bitwize-music/venv/bin/python3 -c "import mcp.server.mcpserver" 2>/dev/null || ~/.bitwize-music/venv/bin/python3 -c "import mcp.server.fastmcp" 2>/dev/null) && echo "SDK ready" || echo "SDK unavailable"
# Windows (Git Bash; cmd/PowerShell interpreter: %USERPROFILE%\.bitwize-music\venv\Scripts\python.exe)
(~/.bitwize-music/venv/Scripts/python.exe -c "import mcp.server.mcpserver" 2>/dev/null || ~/.bitwize-music/venv/Scripts/python.exe -c "import mcp.server.fastmcp" 2>/dev/null) && echo "SDK ready" || echo "SDK unavailable"
```

- `SDK ready` completes the dependency check. Continue to Step 1.5 to check
  whether the MCP tools are available. Keep this SDK result if MCP is offline.
- `SDK unavailable` means both imports failed in the plugin venv. Stop and
  recommend the installed `setup` skill with the `mcp` argument. Supported
  modules are `mcp.server.mcpserver` (2.x) and `mcp.server.fastmcp` (1.x from 1.28.1).
- If `~/.bitwize-music/config.yaml` is missing, stop for the configuration
  guidance in Step 2.

## Step 1.5: Health Check

When the plugin MCP server is available, call `health_check`. If it is
unavailable, show `Health: MCP unavailable` and continue.

**Venv results** (from `result.venv`):
- `status: "ok"` → continue silently
- `status: "stale"` → warn with mismatches and fix command, continue session
- `status: "no_venv"` → **stop** and suggest `/bitwize-music:setup`
- `status: "error"` → warn and continue

**Skill registration results** (from `result.skills`):
- `status: "ok"` → continue silently
- `status: "stale"` → warn: list missing and ghost skill names, show fix message
- `status: "no_cache"` → warn that plugin cache not found, continue

**Album slug collision results** (from `result.collisions`):
- `status: "ok"` → continue silently
- `status: "collision"` → warn: list each slug with its kept and shadowed genres, show the fix (rename one album with `/bitwize-music:rename` or move its directory, then run `rebuild_state`), continue session

## Step 1.6: Suno MCP (optional)

Two facts decide the Suno line: whether a Suno MCP server is **connected** (a tool named `audio-create` exists on any connected MCP server), and whether one is **registered** (the `suno` section of the `health_check` result from Step 1.5: `status` is `configured` or `missing`, with `servers[0].name`, `reminder` and `fix`). The server is optional, so none of this is a warning and none of it stops the session.

- Connected → read `account-usage` once (free) and show the plan and the downloads left: `Suno: connected — Premier Plan, 15 downloads left` (`suno_account.plan.name`, `suno_account.download_credits_remaining`). If that call fails, just `Suno: connected`
- Registered but not connected → `Suno: configured as "<servers[0].name>" but not connected — run /mcp and sign in`
- Missing, `reminder: true` → show how to add it, as its own short block after the Setup lines:

  ```
  Suno: not connected. /bitwize-music:generate and /bitwize-music:listen need Suno's MCP server. Add it once:
    claude mcp add --transport http suno https://api.suno.com/mcp
  then run /mcp and sign in. Add --scope user to have it in every project.
  (Hide this with generation.suno_mcp_reminder: false in your config.)
  ```

  Use the `fix` fields from the result rather than retyping them. In Codex, give the link in `fix.other_assistants` instead of the `claude` command.
- Missing, `reminder: false` → `Suno: not connected (optional)`

## Step 2: Load Config

Read `~/.bitwize-music/config.yaml`.

If the file is missing, recommend the installed `configure` skill. Continue
once the required workspace paths are configured.

## Step 3: Load Overrides

Resolve `paths.overrides` from the current config, using
`{content_root}/overrides` when the setting is unset. For plugin workflow
overrides, read `CLAUDE.md` only from that resolved directory, if present.
Show the file's path in the startup report if you read it.

Check for `{overrides}/pronunciation-guide.md` in the same directory and note
it if found.

## Step 4: Load State

When the plugin MCP server is available, query state through these tools:

- `get_config` — confirm the config loaded
- `list_albums` — album statuses
- `get_ideas` — idea counts
- `get_pending_verifications(summary_only=True)` — pending source verifications (count only)
- `get_session` — the last session's context

If the cache is missing, stale, corrupted, has a schema mismatch, or was built
for a different config, run `rebuild_state()` through MCP and query again.

Read `~/.bitwize-music/cache/state.json` directly only when the server is
unavailable. Use it for a read-only status report if it is readable and its
artist and content root match the current config. Otherwise, report state as
unavailable.

## Step 4.5: Check for Plugin Upgrades

If the plugin MCP server is unavailable, defer this check until it reconnects.
Otherwise, call `get_pending_migrations`. It compares the installed plugin
version against `last_migrated_version` in state (the last version whose
migrations were processed — distinct from `plugin_version`, which only records
the installed version for display) and returns the pending notes already
parsed and sorted.

1. **If `pending` and `malformed` are both empty** (`reason: "current"`, or
   `reason: "unknown"` when the installed version can't be read from
   plugin.json): No action needed.
2. **If `pending` is non-empty** (`reason: "upgrade"` or `"untracked"`): For each
   migration, process its `actions` in order:
   - `auto`: Execute silently (run `check` first — skip if it returns 0)
   - `action`: Show description, ask the user to confirm before executing
   - `info`: Display to the user
   - `manual`: Show the instruction to the user
3. **If `malformed` is non-empty**: those upgrade notes could not be parsed, so
   their actions are not in `pending`. Show each one to the user, never skip it
   silently:
   ```
   ⚠️ Upgrade note {file} could not be read: {reason}
      Its upgrade actions were not run. Open {path} and follow it by hand,
      and report the broken note to the plugin's maintainers.
   ```
   Ask the user before acknowledging while any are listed: acknowledging
   stops them surfacing.
4. **After processing all notes**, call `acknowledge_migrations` (no argument
   acknowledges everything up to the installed version) so the same notes do
   not surface again next session.
5. Report: "Upgraded to Y" with a summary of the actions taken, and any
   malformed notes.

> `reason: "untracked"` means the state predates migration tracking; the full
> backlog up to the installed version is surfaced once, then cleared by
> `acknowledge_migrations`. Do NOT just rebuild state to clear migrations —
> a rebuild preserves the pending status; only `acknowledge_migrations` records
> that you processed them.

## Step 5: (Removed)

Skill model checking is no longer part of session start. Skills use tier aliases (`opus`/`sonnet`/`haiku`) that auto-track the frontier model, and the test suite (`/bitwize-music:test`) enforces model/effort hygiene — so no manual model checking is needed when new Claude models are released.

## Step 6: Report Project Status

Report the available results from Step 4. For cached state, use the ideas,
albums, and session sections and count tracks with `sources_verified: Pending`.

### Album Ideas
From `get_ideas` — show count by status (Pending, In Progress, etc.)

### In-Progress Albums
From `list_albums`, the albums with status "In Progress", "Research Complete" or "Complete"

For each, show:
- Album name, genre, status
- Track progress (completed/total; completed = Final, as `tracks_completed` counts it)

### Pending Source Verifications
Show `total_pending_tracks` and `albums_with_pending_count` from
`get_pending_verifications(summary_only=True)` or the equivalent cached counts.

If any tracks are pending, warn that generation is blocked until their sources
are verified.

### Last Session Context
From `get_session`:
- Last album worked on
- Last phase
- Pending actions

## Step 7: Show Contextual Tips

When state is available, show one relevant tip:

| Condition | Tip |
|-----------|-----|
| No albums exist | "Try `/bitwize-music:tutorial` to create your first album" |
| Ideas exist but no albums | "You have album ideas! Use `/bitwize-music:album-ideas list` to review them" |
| In-progress albums exist | "Resume where you left off: `/bitwize-music:resume <album-name>`" |
| Overrides loaded | "Custom overrides loaded from {overrides}/" |
| Overrides missing | "Customize your workflow with override files — see `/reference/overrides/`" |
| Pending verifications | "Source verification needed before generation can proceed — run `/bitwize-music:verify-sources`" |

Also show one random general tip (rotate through these):
- "Ask 'what should I do next?' for workflow guidance"
- "Use `/bitwize-music:resume` to quickly jump back into an album"
- "The researcher skill coordinates 10 specialized sub-skills for deep research"
- "Check pronunciation before generating — Suno can't infer from context"
- "Use `/bitwize-music:clipboard` to copy lyrics/prompts for Suno"
- "With Suno's MCP server connected, `/bitwize-music:generate` makes the track from here and `/bitwize-music:listen` opens the takes for you"
- "Master your audio with `/bitwize-music:mastering-engineer` for professional results"

## Step 8: Ask

End with: "What would you like to work on?"

---

## Report Format

```
SESSION START
=============

Setup: Dependencies ready, config loaded
Health: [venv ok, skills ok, no collisions | warnings listed | MCP unavailable]
Suno: [connected | not connected (optional)]
Overrides: [path to the configured CLAUDE.md, if read]
State: [loaded via MCP | rebuilt | loaded from cache | unavailable]

ALBUM IDEAS
  Pending: X | In Progress: Y

IN-PROGRESS ALBUMS
  [album-name] (genre) - Status [X/Y tracks]
  [album-name] (genre) - Status [X/Y tracks]

PENDING VERIFICATIONS
  [N tracks across M albums, if any]

LAST SESSION
  Album: [name] | Phase: [phase]
  Pending: [actions]

TIP: [contextual tip]

What would you like to work on?
```

---

## Remember

1. **Don't skip steps** — Each step matters for session integrity
2. **Rebuild state if needed** — Stale state leads to wrong recommendations
3. **Be concise** — This is a status report, not a conversation
4. **Warn about verifications** — Unverified sources block generation
5. **One tip, not five** — Pick the most relevant tip for the current state
