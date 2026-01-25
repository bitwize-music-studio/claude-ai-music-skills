## Description

<!-- Brief description of changes -->

## Type of Change

- [ ] feat: New feature (minor version bump)
- [ ] fix: Bug fix (patch version bump)
- [ ] docs: Documentation only
- [ ] chore: Maintenance (no version bump)
- [ ] BREAKING CHANGE (major version bump)

## Checklist

### Before Submitting

- [ ] I have read the [CONTRIBUTING.md](../CONTRIBUTING.md) guidelines
- [ ] My commit message follows [Conventional Commits](https://conventionalcommits.org/)
- [ ] I included the co-author line: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`
- [ ] I have run `/bitwize-music:test` and all relevant tests pass
- [ ] I have updated CHANGELOG.md under "Unreleased" section

### Version Updates (if applicable)

- [ ] I have updated `.claude-plugin/plugin.json` version
- [ ] I have updated `.claude-plugin/marketplace.json` version
- [ ] Both version files match

### Documentation

- [ ] I have updated CLAUDE.md if workflow changed
- [ ] I have updated README.md if user-facing changes
- [ ] I have added/updated skill documentation if applicable

### Testing

**Required local testing (run before submitting):**
- [ ] `/bitwize-music:test all` - All tests pass locally
- [ ] Manual testing completed (describe below if applicable)

**Automated CI checks (run automatically):**
- JSON/YAML validation
- Version sync check
- SKILL.md structure validation

**Manual testing details:**
<!-- If applicable, describe manual testing performed -->

## Related Issues

Closes #<!-- issue number -->
