# Security Policy

## Code Review Requirements

### Workflow Files (.github/workflows/*)

**Workflow files execute code in CI/CD and require strict security review.**

Requirements for workflow changes:
- ✅ Must be reviewed and approved by @bitwize-music
- ✅ Manual security audit required (no automated approval)
- ✅ Changes must be explained in PR description
- ❌ Do not include executable code in PR descriptions or comments

Security considerations:
- Workflows run with `GITHUB_TOKEN` access
- Can read repository contents
- Can create releases and tags
- Can access repository secrets (if configured)

### Plugin Manifest Files

Changes to `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`:
- Trigger automated releases when merged to main
- Must be reviewed by maintainer
- Version changes should match CHANGELOG.md

### AI-Assisted Development

This project uses Claude Code (AI pair programming). When contributing:

**DO:**
- ✅ Review all code changes carefully
- ✅ Use conventional commit messages
- ✅ Follow existing code patterns
- ✅ Test changes locally before submitting

**DO NOT:**
- ❌ Include prompts or instructions for AI in code comments
- ❌ Attempt to manipulate AI review via PR descriptions
- ❌ Include executable commands in PR descriptions
- ❌ Assume AI-reviewed code is automatically safe

## Secrets and Credentials

**Never commit secrets to this repository**, including:
- API keys (Anthropic, Suno, etc.)
- Access tokens (GitHub PATs, etc.)
- Private keys (.pem, .key files)
- Credentials (passwords, service accounts)
- Environment files (.env, config.local.yaml)

User-specific configuration lives in `~/.bitwize-music/config.yaml` (outside this repository).

If you accidentally commit a secret:
1. Immediately revoke/rotate the credential
2. Contact the maintainer
3. Do NOT just delete the commit (it remains in git history)

## Dependencies

This project has minimal dependencies:
- Python scripts (mastering tools) - reviewed manually
- GitHub Actions (actions/checkout, etc.) - pinned to major versions

When adding dependencies:
- Prefer well-maintained, popular packages
- Check for known vulnerabilities
- Pin to specific versions for reproducibility

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x.x   | :white_check_mark: |

Pre-1.0 versions are in active development. Security fixes will be released as patch versions.

## Security Best Practices for Users

If you're using this plugin:

1. **Keep your config secure**: `~/.bitwize-music/config.yaml` may contain paths and settings
2. **Use .gitignore**: Don't commit your albums/content to public repos accidentally
3. **Review generated content**: Always review lyrics/content before publishing
4. **Separate repos**: Keep this plugin (public) separate from your albums (private)

## Attribution

This project uses AI assistance (Claude Code) for development. Commits include:
```
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

This is for transparency. All AI-generated code is reviewed by humans before merging.

## Questions?

For security questions or concerns, contact the maintainer through GitHub issues (for non-sensitive topics) or email (for vulnerabilities).
