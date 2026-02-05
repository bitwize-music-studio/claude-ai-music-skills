# Git Hooks

This directory contains git hooks for the bitwize-music plugin.

## Installation

To install the pre-commit hook:

```bash
# From plugin root
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Or use the install script:

```bash
bash hooks/install.sh
```

## Pre-commit Hook

Runs 11 validation checks before allowing commits:

1. **Ruff linter** - Code style and quality
2. **JSON/YAML validation** - Config file syntax
3. **CLAUDE.md size** - Keep under 40K characters
4. **Version sync** - plugin.json and marketplace.json match
5. **Skill frontmatter** - All skills have valid YAML frontmatter
6. **CHANGELOG format** - Has [Unreleased] section
7. **Merge conflict markers** - No unresolved conflicts
8. **Large file check** - No files >500KB
9. **Security scan** - Bandit (code) + pip-audit (dependencies)
10. **Unit tests** - pytest on tools/*/tests/
11. **Plugin tests** - Full plugin validation suite

### Security Scan Requirements

The security scan checks for:
- **Code vulnerabilities** using bandit
- **Dependency vulnerabilities** using pip-audit

Install both tools:
```bash
pip install bandit pip-audit
```

### Bypass Hook

If you need to bypass the pre-commit hook (not recommended):
```bash
git commit --no-verify
```

## Hook Development

When updating hooks in this directory, remember to:
1. Test the hook locally by copying to `.git/hooks/`
2. Update this README if adding new checks
3. Keep the hook fast (< 30 seconds for most commits)
