---
name: skill-model-updater
description: Audits that all skills use model tier aliases (opus/sonnet/haiku) and valid effort levels, and migrates any pinned model IDs to aliases. Use to verify model/effort hygiene across skills.
argument-hint: <"check" | "migrate" | "migrate --dry-run">
model: haiku
allowed-tools:
  - Read
  - Edit
  - Glob
  - Grep
---

## Your Task

**Command**: $ARGUMENTS

Skills declare their model with a **tier alias** (`opus` / `sonnet` / `haiku`) so
they automatically track the frontier model of that tier — no per-release version
bumps. This skill verifies that hygiene and fixes drift.

Based on the command:
1. **check** — Scan all skills, report any pinned model IDs, missing/invalid effort
2. **migrate** — Convert any pinned `model:` IDs to the matching tier alias
3. **migrate --dry-run** — Show what migrate would change without editing

---

# Skill Model Updater

You keep model/effort frontmatter consistent across all skill files. **You do not
look up or assign model versions** — aliases resolve to the current frontier model
automatically. The deliberate choice is the *tier* and the *effort level*.

---

## Rules

**Model field** — every skill should use a tier alias:
- `opus` / `sonnet` / `haiku` — preferred (auto-tracks the frontier)
- `inherit` / `default` — accepted special values
- A pinned ID (`claude-opus-4-8`, …) is **drift** — flag it; `migrate` rewrites it
  to the matching tier alias (preserve the tier — never change opus→sonnet)

**Effort field** — reasoning depth, tier-dependent:
- Allowed values: `low`, `medium`, `high`, `xhigh`, `max`
- **Opus/Sonnet** skills MUST set `effort:` (these tiers honor it)
- **Haiku** skills MUST NOT set `effort:` — Haiku ignores it, so it is a misleading
  no-op
- `xhigh` is honored only on Opus 4.7/4.8 (falls back to `high` on Sonnet); `max` is
  honored on all Opus/Sonnet tiers. See
  [effort docs](https://code.claude.com/docs/en/model-config.md#adjust-effort-level)
- Effort assignments are deliberate per-skill choices — see
  `${CLAUDE_PLUGIN_ROOT}/reference/model-strategy.md`. **Never auto-assign effort**;
  report missing effort for a human to decide.

---

## Workflow

### Check Mode

1. Glob all `skills/*/SKILL.md` files
2. Extract the `model:` and `effort:` fields from each YAML frontmatter
3. Derive the tier (does the model string contain opus / sonnet / haiku?)
4. Flag, per skill:
   - `model:` is a pinned ID rather than an alias → **drift**
   - opus/sonnet skill with no `effort:` → **missing effort**
   - haiku skill with an `effort:` → **unsupported effort**
   - `effort:` value not in the allowed set → **invalid effort**
5. Optionally scan `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` for the
   `Co-Authored-By: Claude …` line and note if the model name looks stale
6. Report

**Output format:**
```
SKILL MODEL / EFFORT AUDIT
==========================
✓ lyric-writer: opus / max
✓ researcher: sonnet / high
✓ import-audio: haiku / (none)
⚠ some-skill: claude-opus-4-7 (pinned → should be alias `opus`)
⚠ other-skill: sonnet / (missing effort)

Summary: 52/54 clean, 1 pinned, 1 missing effort
```

### Migrate Mode

1. Run the check scan
2. For each skill whose `model:` is a pinned ID:
   - Read the SKILL.md
   - Replace the pinned ID with the matching tier alias (preserve the tier)
3. Do **not** add or change `effort:` — report missing/invalid effort for a human
4. Report changes made

### Dry Run Mode

`migrate --dry-run` — same as migrate but only reports proposed changes; edit nothing.

---

## Error Handling

- **No `model:` field** → report "⚠ [skill]: no model specified"; do not add one
- **Unknown tier** (no opus/sonnet/haiku substring) → report "? [skill]: unknown
  model '[id]'"; do not migrate
- **Invalid YAML frontmatter** → report "✗ [skill]: invalid frontmatter"; skip it

---

## Remember

- **Aliases, not versions** — never look up model IDs; `opus`/`sonnet`/`haiku`
  always resolve to the current frontier model. New releases need no edits here.
- **Preserve the tier** — migration only changes pinned→alias within the same tier.
- **Never auto-assign effort** — it's a deliberate per-skill choice; only report gaps.
- **Haiku has no effort** — flag any effort field on a haiku skill.
- **Rationale** — see `${CLAUDE_PLUGIN_ROOT}/reference/model-strategy.md` for tier
  and effort assignments.
