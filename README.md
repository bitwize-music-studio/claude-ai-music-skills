# Claude AI Music Skills

I love music but never learned an instrument. AI became the creative outlet that was always out of reach. This project started as a way to go deep on Claude Code plugin architecture, agentic workflows, multi-model orchestration, and MCP tooling. Music was the domain because it was personal.

What it actually does: a Claude Code plugin that turns a conversation into a full album production pipeline. You describe what you want to make, and it handles concept development, lyrics, [Suno](https://suno.com) prompts (an AI music generation platform), audio mastering, and release prep — with quality gates and source verification at every stage.

![Version](https://img.shields.io/github/v/release/bitwize-music-studio/claude-ai-music-skills?label=version&color=blue)

> [!NOTE]
> Active development happens on the `develop` branch — `main` only receives tested, stable releases. If you run into issues, [open an issue](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues) or submit a PR.

---

## Example Workflow

```
You:    "Let's make an album about the 2016 Bangladesh Bank heist"
Claude: Creates album structure, runs 7-phase concept planning

You:    "Start the research"
Claude: Dispatches legal, financial, and security researchers in parallel
        Gathers DOJ filings, SWIFT documentation, malware analysis
        Cross-verifies sources, flags claims that need human review

You:    "Sources look good. Let's write track 1"
Claude: Drafts lyrics, checks prosody and rhyme schemes
        Scans for pronunciation risks, suggests phonetic fixes
        Builds Suno V5 style prompt with genre tags and vocal direction

You:    "Track sounds great, here's the WAV"
Claude: Imports audio, splits stems, polishes per-stem
        Masters to -14 LUFS for streaming
        Generates promo video and social media copy
```

Concept to released album. You generate on Suno, everything else happens in the terminal.

---

## Install

```bash
/plugin marketplace add bitwize-music-studio/claude-ai-music-skills
/plugin install bitwize-music@claude-ai-music-skills
```

Then run `/bitwize-music:setup` to detect your environment and install dependencies. Run `/bitwize-music:configure` to set your artist name and workspace paths.

**Platform**: Linux or macOS (Windows users: use WSL). Python 3.10+ for the MCP server and audio tools.

---

## Architecture

This is where the engineering lives. The plugin is a case study in how far you can push Claude Code's plugin system.

### Skill System (52 Skills)

Each skill is a self-contained markdown file with a YAML frontmatter that declares its model, description, and when it should activate. Skills range from simple clipboard operations to multi-step creative workflows. Claude routes to skills automatically based on context, or you invoke them directly with `/bitwize-music:<name>`.

The lyric-writer knows prosody rules, rhyme scheme analysis, and Suno's pronunciation quirks. The mastering-engineer knows loudness targets per platform and genre-specific EQ curves. The researcher coordinates parallel sub-agents across 10 domain specializations.

See [docs/skills.md](docs/skills.md) for the full reference.

### Multi-Model Orchestration

Skills declare which Claude model they need. Creative work that directly impacts music quality runs on Opus. Coordination and reasoning tasks use Sonnet. Mechanical operations (imports, validation, clipboard) run on Haiku.

| Tier | Model | Skills | Rationale |
|------|-------|--------|-----------|
| Creative | Opus 4.6 | 6 | Lyrics, Suno prompts, album concepts, legal/verification research — output quality defines the music |
| Reasoning | Sonnet 4.6 | 29 | Research coordination, pronunciation analysis, most workflows |
| Mechanical | Haiku 4.5 | 17 | Imports, validation, clipboard, help — speed over creativity |

This project pushes Claude Code hard — multi-agent research, real-time audio analysis, sub-agent orchestration across model tiers. It works best on the Max plan. The standard Pro plan will hit rate limits during multi-track sessions.

See [reference/model-strategy.md](reference/model-strategy.md) for per-skill rationale.

### MCP Server (80+ Tools)

A Python MCP server exposes 80+ tools for instant state queries, audio analysis, lyrics processing, and database operations. The server is the plugin's nervous system — skills call MCP tools instead of reading files directly, which keeps responses fast and state consistent.

Key tool categories:
- **State management** — album/track lookups, session context, cache rebuild
- **Lyrics analysis** — syllable counting, readability scoring, rhyme detection, section validation, cross-track repetition
- **Audio processing** — mastering, stem analysis, QC checks, promo video generation
- **Database** — tweet/promo content management via PostgreSQL

### Research System

For documentary and true-story albums, the research system coordinates parallel investigation across 10 domain-specific sub-agents. A lead researcher dispatches to specialists (legal, financial, security, government, journalism, etc.), each trained on where to find primary sources in their domain. A verification agent cross-checks all claims before human review.

The full pipeline: gather sources, verify citations, require human sign-off, then — and only then — allow lyrics generation. Every claim in the music traces back to a captured, verified source.

### Quality Gates

Nothing ships without passing gates:
- **Lyrics**: 13-point checklist (rhyme, prosody, pronunciation, POV consistency, factual accuracy)
- **Pre-generation**: Sources verified, explicit flags set, style prompt complete, artist names cleared
- **Audio**: 7-point QC (loudness, clipping, silence, phase, stereo width, frequency balance, dynamic range)
- **Structure**: Album directory validation, file location checks, content integrity

### Genre Coverage

72 genre directories with production guides, mastering presets, artist deep-dives, and Suno-specific tips. From afrobeats to vaporwave, each genre includes subgenre breakdowns, lyric conventions, and reference artists.

### CI/CD

5 GitHub Actions workflows: test suite (2,482 tests), security scanning (bandit + pip-audit), static validation, auto-release from changelog, and PR target enforcement. Dependabot watches pip and Actions versions weekly.

---

## Project Structure

```
skills/              52 skill definitions (markdown + YAML frontmatter)
servers/             MCP server (Python, 80+ tools)
tools/               Audio mastering, promo videos, sheet music, cloud uploads
reference/           46+ docs — Suno guides, mastering workflows, genre references
genres/              72 genre directories with production guides
templates/           Album, track, artist, research templates
tests/               2,482 tests across 14 categories
config/              Example config and setup docs
```

---

## Detailed Documentation

| Topic | Location |
|-------|----------|
| All 52 skills | [docs/skills.md](docs/skills.md) |
| Configuration | [docs/configuration.md](docs/configuration.md) |
| Troubleshooting | [docs/troubleshooting.md](docs/troubleshooting.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Model strategy | [reference/model-strategy.md](reference/model-strategy.md) |
| Skill decision tree | [reference/SKILL_INDEX.md](reference/SKILL_INDEX.md) |
| Suno V5 best practices | [reference/suno/v5-best-practices.md](reference/suno/v5-best-practices.md) |
| The story behind bitwize-music | [bitwizemusic.com/behind-the-music](https://www.bitwizemusic.com/behind-the-music/) |

---

## Contributors

<a href="https://github.com/bitwize-music"><img src="https://images.weserv.nl/?url=github.com/bitwize-music.png&h=60&w=60&fit=cover&mask=circle" width="60" height="60" alt="@bitwize-music"></a>
<a href="https://github.com/markus-michalski"><img src="https://images.weserv.nl/?url=github.com/markus-michalski.png&h=60&w=60&fit=cover&mask=circle" width="60" height="60" alt="@markus-michalski"></a>

If you make something with this, I'd genuinely love to hear it — [@bitwizemusic](https://x.com/bitwizemusic) on X or [open a discussion](https://github.com/bitwize-music-studio/claude-ai-music-skills/discussions).

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=bitwize-music-studio/claude-ai-music-skills&type=Date)](https://star-history.com/#bitwize-music-studio/claude-ai-music-skills&Date)

---

## License

CC0 — Public Domain. Do whatever you want with it.

## Disclaimer

Artist and song references in the genre documentation are for educational and reference purposes only. This plugin does not encourage creating infringing content. Users are responsible for ensuring their generated content complies with applicable laws and platform terms of service.
