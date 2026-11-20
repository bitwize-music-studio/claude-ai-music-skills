# bitwize-music: contributor instructions

This repository is the **bitwize-music** plugin for Claude Code and OpenAI Codex: an AI music workflow on Suno (skills in `skills/`, the `bitwize-music-mcp` server in `servers/`, tools in `tools/`, references in `reference/`, templates in `templates/`). This file is for working **on** the plugin. Claude Code reads it through `CLAUDE.md`; Codex reads it directly.

Here `{plugin_root}` is the repository root.

---

## The rules plugin users get

Plugin users never see this file or `CLAUDE.md`: Claude Code doesn't load a `CLAUDE.md` from a plugin's folder. The rules a user's session follows are in **`reference/plugin-rules.md`**, which the `SessionStart` hook `hooks/session_rules.py` adds to every session whose working directory is inside the music workspace (`content_root`, `audio_root` or `documents_root` in `~/.bitwize-music/config.yaml`). Elsewhere the hook adds a one-line pointer to that file, or, with no config yet, a one-line note to run `/bitwize-music:configure`.

- **Change a workflow rule in `reference/plugin-rules.md`**, not here. When working in this repo, follow it too: `CLAUDE.md` imports it for Claude Code.
- **It must stay under 9,000 characters** with `{plugin_root}` filled in. Claude Code keeps SessionStart output whole only below 10,000; longer output becomes a 2 KB preview. `tests/unit/hooks/test_session_rules.py` enforces the limit. Put detail in the skill or reference file it belongs to and link it with `{plugin_root}/…`.
- **Skills must stand alone.** A rule a skill depends on, such as the Suno credit go-ahead, belongs in that skill as well.
- The full session-start procedure lives in `skills/session-start/SKILL.md`; statuses and the regeneration workflow in `reference/workflows/status-tracking.md`.

## Templates

New content is created from `templates/`. Service-specific template sections are marked `<!-- SERVICE: suno -->`; Suno is the only service today.

---

## Versioning & Development

[Semantic Versioning](https://semver.org/) with [Conventional Commits](https://conventionalcommits.org/).

| Prefix | Version Bump |
|--------|--------------|
| `feat:` | MINOR |
| `fix:` | PATCH |
| `feat!:` | MAJOR |
| `docs:`, `chore:`, `ci:` | None |

**Co-author line**: use the model actually running the session, e.g. `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

**Version files (must stay in sync)**: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `.codex-plugin/plugin.json`

**Release process**: Update CHANGELOG.md `[Unreleased]` → `[0.x.0] - DATE`, update the version in all three plugin files, and add `migrations/0.x.0.md` when the release changes config, dependencies, files or workflow (see `migrations/README.md`). Commit: `chore: release 0.x.0`. Merging the release PR into `main` runs `auto-release.yml`, which tags the release, publishes it from the CHANGELOG section and bumps `develop` to the next `-dev` version.

**Development workflow**: Feature branch off `develop` → Conventional Commits → `/bitwize-music:test all` → PR into `develop` → Release: merge `develop` → `main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

**Release PRs use a merge commit — never squash or rebase.** When merging `develop` → `main`, use a **merge commit**. Squashing collapses develop's history into a single new commit on `main`, permanently diverging the two branches so every *subsequent* release PR conflicts. (Feature PRs *into* `develop` may squash freely.) If `develop` and `main` have already diverged from a past squash, reconcile on `develop` with `git merge -s ours origin/main` (keeps develop's tree, records `main` as an ancestor) before merging.

**Pre-push gate**: **ALWAYS run `make check` before `git push`.** This runs the same `ruff` + `bandit` + `mypy` + `pytest` suite that CI runs in the Lint and Tests jobs (see `Makefile` + `.github/workflows/test.yml`). `make lint` alone is fine for a quick type-check. Running targeted `pytest tests/unit/…` and file-scoped `ruff check` is NOT equivalent — `make` spins up `.venv` from `requirements.txt + requirements-test.txt`, so mypy also sees the real runtime packages. That is a stricter view than CI's Lint job, which installs only `requirements-test.txt`; environment-dependent typing is pinned so the two agree, and a red local mypy is a real finding. If `make check` fails, fix the root cause; do not push and hope CI catches a different picture.

**External contributor PRs**: When the user mentions merging, reviewing, or having merged a PR from a non-maintainer (anyone other than @bitwize-music), check the Contributors section of README.md. If the PR author is not listed, proactively offer to add them using the same `<a href>` avatar block format as existing entries. Do this without being asked.
