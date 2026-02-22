# Contributing to claude-ai-music-skills

Thank you for contributing! This document explains our development workflow.

## Branch Model

We use a **two-branch model** with `develop` as the integration branch and `main` as the stable release branch:

- **`develop`** — active development, receives feature branch PRs, version tagged with `-dev` suffix (e.g., `0.62.0-dev`)
- **`main`** — stable releases only, receives merges from `develop` when ready to release

CI runs on pushes to `develop` and on PRs into both branches. Direct pushes to `main` skip CI (already validated by the PR gate).

**Plugin distribution channels** (both use `marketplace.json`, branch separation handles the split):
- Stable: `/plugin marketplace add bitwize-music-studio/claude-ai-music-skills` (from `main`)
- Dev: `/plugin marketplace add https://github.com/bitwize-music-studio/claude-ai-music-skills.git#develop`

## Development Workflow

We use a **PR-based workflow** with the following process:

### 1. Create a Feature Branch

```bash
# Create branch from develop
git checkout develop
git pull origin develop
git checkout -b feat/your-feature-name  # or fix/, docs/, chore/
```

**Branch naming conventions:**
- `feat/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `chore/` - Maintenance tasks

### 2. Make Your Changes

Follow the existing code patterns and documentation style.

**Key files to update:**
- If adding a skill: Create `/skills/your-skill/SKILL.md`
- If changing workflow: Update `CLAUDE.md`
- If user-facing: Update `README.md`
- Always: Update `CHANGELOG.md` under "Unreleased"

#### Adding a New Skill - Complete Checklist

When adding a new skill, you MUST update all of these files:

**Required (skill won't work without these):**
- [ ] Create `/skills/your-skill/SKILL.md` with skill documentation
- [ ] Add entry to `CLAUDE.md` skills table (alphabetically in correct category)
- [ ] Add entry to `skills/help/SKILL.md` in appropriate category
- [ ] Add entry to `skills/help/SKILL.md` Common Workflows section (if applicable)
- [ ] Update `CHANGELOG.md` under "Unreleased" → "Added"

**Recommended:**
- [ ] Add entry to `reference/SKILL_INDEX.md` (alphabetical table + decision tree + skill categories)
- [ ] Add entry to `reference/model-strategy.md` under appropriate model tier
- [ ] Add quick tip to `skills/help/SKILL.md` Quick Tips section (if relevant)
- [ ] Update workflow diagram in `CLAUDE.md` (if part of main workflow)
- [ ] Add to Album Completion Checklist in `CLAUDE.md` (if part of release)
- [ ] Add reference docs in `/reference/` if complex
- [ ] Update `README.md` Skills Reference tables (add to appropriate section: Core Production, Research, Quality Control, Release, or Setup & Maintenance)

**Testing:**
- [ ] Run `/bitwize-music:test all` to ensure no regressions
- [ ] Test skill invocation: `/bitwize-music:your-skill`
- [ ] Verify skill appears in `/bitwize-music:help` output
- [ ] Check skill in skills table works as expected

**Common mistakes to avoid:**
- ❌ Forgetting to add skill to help system
- ❌ Not updating CHANGELOG.md
- ❌ Adding to CLAUDE.md but not help/SKILL.md
- ❌ Inconsistent naming between files
- ❌ Breaking alphabetical order in lists

### 3. Test Your Changes

Run the automated test suite:

```bash
# Run all tests
/bitwize-music:test all

# Or run specific categories
/bitwize-music:test skills
/bitwize-music:test workflow
```

All tests must pass before submitting PR.

### 4. Commit Your Changes

We use [Conventional Commits](https://conventionalcommits.org/).

**Format:**
```
<type>(<scope>): <description>

<body>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

**Examples:**
```bash
git commit -m "feat: add sheet-music-publisher skill

Add comprehensive sheet music generation workflow...

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git commit -m "fix: correct audio path in import-audio skill

Was missing artist folder in path construction.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

**Commit types:**
| Type | Version Bump | Example |
|------|--------------|---------|
| `feat:` | MINOR | New feature/skill |
| `fix:` | PATCH | Bug fix |
| `feat!:` | MAJOR | Breaking change |
| `docs:` | None | Documentation only |
| `chore:` | None | Maintenance |

### 5. Push and Create PR

```bash
git push origin feat/your-feature-name
```

Then create a PR targeting **`develop`** (not `main`).

### 6. PR Review Process

**Automated checks (run on GitHub Actions):**
- JSON/YAML validation
- Version sync check (plugin.json vs marketplace.json)
- SKILL.md structure validation

**Required before merge to `develop`:**
- [ ] All automated checks pass
- [ ] `/bitwize-music:test all` passes locally (run before submitting PR)
- [ ] Follows Conventional Commits
- [ ] CHANGELOG.md updated under "Unreleased"
- [ ] Documentation updated
- [ ] No breaking changes (unless MAJOR bump)
- [ ] Migration note added if applicable (see below)

#### When to Add a Migration Note

If your PR introduces filesystem changes (new directories, moved files), dependency changes, template changes that affect existing albums, or config changes, add a migration file in `migrations/`:

1. Create `migrations/<version>.md` (use the version this will ship in)
2. Add YAML frontmatter with `version`, `summary`, `categories`, `actions`
3. Add markdown body with context
4. See `migrations/README.md` for format details and action types

### 7. Release to Stable

When `develop` is ready to release:

1. Create a PR from `develop` → `main`
2. Update version files (drop `-dev` suffix):
   - `.claude-plugin/plugin.json`
   - `.claude-plugin/marketplace.json`
3. Move CHANGELOG.md entries from "Unreleased" to a versioned heading
4. Merge PR to `main`
5. After merge, bump `develop` to the next `-dev` version (e.g., `0.63.0-dev`)

**Version bumping:**
- `feat:` → Increment MINOR (0.3.0 → 0.4.0)
- `fix:` → Increment PATCH (0.3.0 → 0.3.1)
- `feat!:` → Increment MAJOR (0.3.0 → 1.0.0)

**Files that must stay in sync:**
- `.claude-plugin/plugin.json` — plugin version
- `.claude-plugin/marketplace.json` — marketplace version

## Testing

### Running Tests Locally

```bash
# All tests
/bitwize-music:test all

# Specific categories
/bitwize-music:test config      # Configuration tests
/bitwize-music:test skills      # Skill structure tests
/bitwize-music:test workflow    # Workflow documentation
/bitwize-music:test consistency # Cross-reference checks
/bitwize-music:test quality     # Code quality
```

### Adding New Tests

When fixing bugs, add a regression test:

1. Open `skills/test/SKILL.md`
2. Find the appropriate category
3. Add a test that would have caught the bug
4. Verify it fails before your fix
5. Verify it passes after your fix

## Development Mode (--plugin-dir)

When developing with `--plugin-dir`, Claude Code sets `CLAUDE_PLUGIN_ROOT` to your local repo, so `run.py` launches the dev `server.py`. However, if the plugin is also **installed** (cached at `~/.claude/plugins/cache/bitwize-music/`), the cached MCP server may run instead of (or alongside) the dev one, since both register the same `bitwize-music-mcp` server ID.

**Before testing with `--plugin-dir`:**

```bash
# Option A: Remove the cached plugin
rm -rf ~/.claude/plugins/cache/bitwize-music

# Option B: Uninstall first
/plugin uninstall bitwize-music
```

**Then run Claude with your dev repo:**

```bash
claude --plugin-dir /path/to/claude-ai-music-skills
```

`CLAUDE_PLUGIN_ROOT` will point to your dev repo and `run.py` will use the dev `server.py`.

**After dev testing**, re-install the plugin normally to restore the cached version.

## Code Style

- **Python scripts:** Follow PEP 8
- **Markdown:** Use 2-space indentation for lists
- **YAML:** Use 2-space indentation
- **Line length:** 120 characters max for code, no limit for docs

## Questions?

- Check existing skills in `/skills/` for examples
- Read `CLAUDE.md` for workflow documentation
- Open an issue for clarification

## License

By contributing, you agree to license your contribution under the CC0-1.0 license.
