# Plugin Migration Notes

This directory contains versioned migration notes that guide Claude through upgrade actions when users update to a new plugin version.

## How It Works

1. `state.json` stores two version fields:
   - `plugin_version` — the currently-installed version (refreshed on every state build, used for display)
   - `last_migrated_version` — the version through which migrations have been **processed** (only advances when migrations are acknowledged)
2. On session start (Step 4.5), Claude calls the `get_pending_migrations` MCP tool, which returns the migration notes between `last_migrated_version` and the installed version (already parsed and sorted)
3. Claude processes each pending note's actions in order
4. After processing, Claude calls the `acknowledge_migrations` MCP tool, which advances `last_migrated_version` so the same notes don't surface again

> **Why two fields?** A state rebuild refreshes `plugin_version` to the installed version, so comparing it against the manifest can never detect an upgrade (it always matches after any rebuild). `last_migrated_version` is preserved across rebuilds and only advances on explicit acknowledgment — see issue #320. **A rebuild never clears pending migrations; only `acknowledge_migrations` does.**

## When to Write a Migration

Create a migration note when a new version introduces:

- **Filesystem changes** — new directories, renamed files, moved content
- **Dependency changes** — new Python packages, removed venvs, tool upgrades
- **Template changes** — new templates that existing albums should adopt
- **Config changes** — new config keys, deprecated settings
- **Workflow changes** — significant process changes users should know about

Do NOT create migrations for:

- Bug fixes with no user-visible structural changes
- New skills (these are automatically discovered)
- Documentation-only updates

## File Format

Files are named by version: `0.44.0.md`, `0.45.0.md`, etc.

```yaml
---
version: "0.44.0"
summary: "Short description of what changed"
categories:
  - filesystem      # Directory/file structure changes
  - templates       # Template additions or modifications
  - dependencies    # Python packages, external tools
  - config          # Configuration file changes
  - workflow        # Process/workflow changes
actions:
  - type: auto              # Execute silently (safe, idempotent)
    description: "What this does"
    check: "command"        # Returns 0 if already done → skip
    command: "command"      # What to run

  - type: action            # Ask user first (potentially destructive)
    confirm: true
    description: "What this does"
    check: "command"        # Returns 0 if already done → skip

  - type: info              # Just announce (no action needed)
    description: "What changed"

  - type: manual            # Tell user what to do themselves
    instruction: "Steps to take"
---

[Markdown body with context for Claude — background, rationale, details]
```

## Action Types

| Type | Behavior | Use When |
|------|----------|----------|
| `auto` | Execute silently | Safe, idempotent operations (mkdir, cp) |
| `action` | Ask user, then execute | Potentially destructive (file moves, content migration) |
| `info` | Display to user | Informational, no action needed |
| `manual` | Show instructions | User must do it themselves (restart, external tool) |

## First-Time Users

A **brand-new install** is seeded with `last_migrated_version` = the installed version when its state is first built, so `get_pending_migrations` returns nothing — no historical migration bombardment.

A **pre-tracking state** (created before `last_migrated_version` existed) reads as `null`. Rather than silently skipping (the old behavior, which hid migrations users actually needed — see issue #320), `get_pending_migrations` surfaces the full backlog up to the installed version **once**, with `reason: "untracked"`. After Claude processes them and calls `acknowledge_migrations`, they stop surfacing.

## Checklist for New Migrations

- [ ] Version in filename matches `version` in frontmatter
- [ ] Summary is one line, descriptive
- [ ] Categories are from the allowed list
- [ ] Each action has a `type` field
- [ ] `auto` actions have `check` and `command`
- [ ] `action` actions have `confirm: true` and `check`
- [ ] `check` commands return non-zero if action is still needed
- [ ] Markdown body explains context for Claude
