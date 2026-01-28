---
name: skill-model-updater
description: Update model references in skill files when new Claude models are released
argument-hint: <"check" | "update" | "update --dry-run">
model: claude-haiku-4-5-20251001
disable-model-invocation: true
allowed-tools:
  - Read
  - Edit
  - Glob
  - Grep
  - WebSearch
  - WebFetch
---

## Your Task

**Command**: $ARGUMENTS

Based on the command:
1. **check** - Discover current models, scan all skills, report status
2. **update** - Update outdated models to current versions
3. **update --dry-run** - Show what would be updated without making changes

---

# Skill Model Updater

You maintain model currency across all skill files, ensuring skills use the latest Claude models.

---

## Step 1: Discover Current Models

**Before checking or updating skills, you MUST first discover current model IDs.**

### Discovery Method

1. **Search for current Anthropic models:**
   ```
   WebSearch: "Anthropic Claude model IDs 2025" OR "Claude API models list current"
   ```

2. **Fetch official documentation:**
   ```
   WebFetch: https://docs.anthropic.com/en/docs/about-claude/models
   ```

3. **Extract current model IDs** for each tier:
   - **Opus** (most capable) - Look for `claude-opus-*` or `claude-*-opus-*`
   - **Sonnet** (balanced) - Look for `claude-sonnet-*` or `claude-*-sonnet-*`
   - **Haiku** (fast) - Look for `claude-haiku-*` or `claude-*-haiku-*`

4. **Identify the latest version** of each tier by date suffix (e.g., `20250514` > `20250114`)

### Expected Output Format

After discovery, report:
```
CURRENT CLAUDE MODELS (discovered)
==================================
Source: docs.anthropic.com/en/docs/about-claude/models
Date checked: [today's date]

Opus:   claude-opus-4-5-20251101
Sonnet: claude-sonnet-4-5-20250929
Haiku:  claude-haiku-4-5-20251001
```

**Shorthand aliases** (always valid, resolve to current):
- `opus` → current opus model
- `sonnet` → current sonnet model
- `haiku` → current haiku model

---

## Skill Tier Assignments

Skills are assigned tiers based on their function:

### Opus Tier (Critical Creative)
These skills produce core content that defines quality:
- `lyric-writer` - Lyrics are the product
- `suno-engineer` - Prompts determine music output
- `researchers-legal` - Complex legal document synthesis
- `researchers-verifier` - High-stakes quality control

### Sonnet Tier (Standard)
Most skills that require reasoning but not maximum creativity:
- `album-conceptualizer`
- `album-art-director`
- `researcher`
- `release-director`
- `mastering-engineer`
- `document-hunter`
- `lyric-reviewer`
- All other researcher specialists

### Haiku Tier (Fast Pattern Matching)
Simple scanning tasks:
- `pronunciation-specialist`
- `explicit-checker`

---

## Workflow

### Check Mode

```bash
/skill-model-updater check
```

1. **Discover current models** (Step 1 above) - WebSearch/WebFetch Anthropic docs
2. Glob for all `skills/*/SKILL.md` files
3. Extract `model:` field from YAML frontmatter
4. Compare against discovered current models
5. Report status for each skill

**Output format:**
```
SKILL MODEL AUDIT
=================

Current Models (discovered from docs.anthropic.com):
- Opus: claude-opus-4-5-20251101
- Sonnet: claude-sonnet-4-5-20250929
- Haiku: claude-haiku-4-5-20251001

Skill Status:
✓ lyric-writer: claude-opus-4-5-20251101 (current)
✓ researcher: claude-sonnet-4-5-20250929 (current)
⚠ album-art-director: claude-sonnet-4-20250114 (outdated → claude-sonnet-4-5-20250929)
✓ pronunciation-specialist: claude-haiku-4-5-20251001 (current)

Summary: 19/20 skills current, 1 needs update
```

### Update Mode

```bash
/skill-model-updater update
```

1. **Discover current models** (Step 1 above)
2. Run check to identify outdated skills
3. For each outdated skill:
   - Read the SKILL.md file
   - Update the `model:` field to discovered current version
   - Preserve the skill's tier (don't change opus to sonnet)
4. Report changes made

**Output format:**
```
SKILL MODEL UPDATE
==================

Models discovered from docs.anthropic.com:
- Opus: claude-opus-4-5-20251101
- Sonnet: claude-sonnet-4-5-20250929
- Haiku: claude-haiku-4-5-20251001

Updated 1 skill:
- album-art-director: claude-sonnet-4-20250114 → claude-sonnet-4-5-20250929

All skills now current.
```

### Dry Run Mode

```bash
/skill-model-updater update --dry-run
```

Same as update but only reports what would change without editing files.

---

## Model Detection Logic

### Identifying Outdated Models

A model is outdated if:
1. It's an older version of a current model family (e.g., `claude-sonnet-4-20250114` vs `claude-sonnet-4-5-20250929`)
2. It's a deprecated model (e.g., `claude-3-opus-20240229`)

### Preserving Tier Intent

When updating, preserve the skill's intended tier:
- If skill uses any opus model → update to current opus
- If skill uses any sonnet model → update to current sonnet
- If skill uses any haiku model → update to current haiku
- If skill uses shorthand (`opus`, `sonnet`, `haiku`) → leave as-is (always resolves to current)

---

## When New Models Release

This skill discovers models automatically, so no manual mapping updates needed.

When Anthropic releases new models:

1. **Run check** - `/skill-model-updater check` will discover new models automatically
2. **Review changes** - Verify discovered models are correct
3. **Run update** - `/skill-model-updater update` to propagate changes
4. **Update CLAUDE.md** - If tier assignments change, update "Model Strategy" section manually

---

## Example: Full Update Cycle

```markdown
User: "New Claude models released, update skills"

1. Run check (discovers models automatically):
   /skill-model-updater check

   Output:
   - Discovered from docs.anthropic.com: Opus 4.5, Sonnet 4, Haiku 3.5
   - 3 skills using outdated sonnet (20250114 → 20250514)
   - 1 skill using deprecated opus (claude-3-opus → claude-opus-4-5)

2. Run dry-run:
   /skill-model-updater update --dry-run

   Output shows proposed changes

3. Run update:
   /skill-model-updater update

   Output confirms 4 skills updated

4. Verify:
   /skill-model-updater check

   Output: All 21 skills current
```

---

## Error Handling

### Missing Model Field
If a SKILL.md has no `model:` field:
- Report as "⚠ [skill]: No model specified"
- Do not add one automatically (requires manual decision)

### Unknown Model
If a SKILL.md has an unrecognized model:
- Report as "? [skill]: Unknown model '[model-id]'"
- Do not update (requires manual review)

### Invalid YAML
If a SKILL.md has malformed frontmatter:
- Report as "✗ [skill]: Invalid YAML frontmatter"
- Do not attempt to update

---

## Remember

- **Check before update** - Always know what will change
- **Preserve tiers** - Don't accidentally downgrade opus skills to sonnet
- **Update this skill first** - Model mapping must be current before propagating
- **Shorthand is safe** - `opus`, `sonnet`, `haiku` always resolve to current versions
