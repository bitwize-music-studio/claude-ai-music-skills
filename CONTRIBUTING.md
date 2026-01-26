# Contributing to claude-ai-music-skills

Thank you for contributing! This document explains our development workflow.

## Development Workflow

We use a **PR-based workflow** with the following process:

### 1. Create a Feature Branch

```bash
# Create branch from main
git checkout main
git pull origin main
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
- [ ] Add quick tip to `skills/help/SKILL.md` Quick Tips section (if relevant)
- [ ] Update workflow diagram in `CLAUDE.md` (if part of main workflow)
- [ ] Add to Album Completion Checklist in `CLAUDE.md` (if part of release)
- [ ] Add reference docs in `/reference/` if complex
- [ ] Update `README.md` if user-facing feature

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

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Examples:**
```bash
git commit -m "feat: add sheet-music-publisher skill

Add comprehensive sheet music generation workflow...

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git commit -m "fix: correct audio path in import-audio skill

Was missing artist folder in path construction.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Commit types:**
| Type | Version Bump | Example |
|------|--------------|---------|
| `feat:` | MINOR | New feature/skill |
| `fix:` | PATCH | Bug fix |
| `feat!:` | MAJOR | Breaking change |
| `docs:` | None | Documentation only |
| `chore:` | None | Maintenance |

### 5. Update Version Files (if applicable)

For `feat:` or `fix:` commits, update version numbers:

**Files to update (BOTH must match):**
1. `.claude-plugin/plugin.json`
2. `.claude-plugin/marketplace.json`

**Version bumping:**
- `feat:` → Increment MINOR (0.3.0 → 0.4.0)
- `fix:` → Increment PATCH (0.3.0 → 0.3.1)
- `feat!:` → Increment MAJOR (0.3.0 → 1.0.0)

### 6. Push and Create PR

```bash
git push origin feat/your-feature-name
```

Then create PR on GitHub and fill out the PR template.

### 7. PR Review Process

**Automated checks (run on GitHub Actions):**
- JSON/YAML validation
- Version sync check (plugin.json vs marketplace.json)
- SKILL.md structure validation

**Required before merge:**
- [ ] All automated checks pass
- [ ] `/bitwize-music:test all` passes locally (run before submitting PR)
- [ ] Follows Conventional Commits
- [ ] Version files updated and synced (if applicable)
- [ ] CHANGELOG.md updated
- [ ] Documentation updated
- [ ] No breaking changes (unless MAJOR bump)

### 8. Merge and Release

Once approved:
1. Squash and merge (or merge commit)
2. Version automatically updates for users on next plugin use

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
