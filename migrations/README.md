# Plugin Migration Notes

This directory contains versioned migration notes that guide Claude through upgrade actions when users update to a new plugin version.

## How It Works

1. `state.json` stores `plugin_version` — the last version the user ran
2. On session start (Step 4.5), Claude compares stored vs current version
3. If versions differ, Claude reads applicable migration files and processes actions
4. After processing, `plugin_version` updates to current via `indexer.py rebuild`

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

When `plugin_version` is `null` (new install or pre-upgrade-system), the session start procedure sets it to the current version and **skips all migrations**. This prevents historical migration bombardment.

## Checklist for New Migrations

- [ ] Version in filename matches `version` in frontmatter
- [ ] Summary is one line, descriptive
- [ ] Categories are from the allowed list
- [ ] Each action has a `type` field
- [ ] `auto` actions have `check` and `command`
- [ ] `action` actions have `confirm: true` and `check`
- [ ] `check` commands return non-zero if action is still needed
- [ ] Markdown body explains context for Claude
