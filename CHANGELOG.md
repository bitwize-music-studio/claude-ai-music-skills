# Changelog

All notable changes to claude-ai-music-skills.

This project uses [Conventional Commits](https://conventionalcommits.org/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- CODEOWNERS file to protect workflow files and critical configuration
- SECURITY.md with security policy and AI-assisted development guidelines

### Changed

### Fixed

## [0.6.1] - 2026-01-25

### Added

### Changed

### Fixed
- Auto-release workflow now extracts release notes from versioned section instead of [Unreleased]

## [0.6.0] - 2026-01-25

### Added

### Changed
- CHANGELOG.md is now manually maintained (no automated commits) for security and quality
- Auto-release workflow verifies CHANGELOG was updated instead of attempting to modify it

### Fixed

## [0.5.1] - 2026-01-25

### Added
- Automated release workflow - GitHub Actions automatically creates tags and releases when version files are updated on main
- `/sheet-music-publisher` skill - Convert audio to sheet music, create KDP-ready songbooks
  - AnthemScore CLI integration for automated transcription
  - MuseScore integration for polishing and PDF export
  - Cross-platform OS detection (macOS, Linux, Windows)
  - Config-aware path resolution
  - Automatic cover art detection for songbooks
  - Tools: transcribe.py, fix_titles.py, create_songbook.py
  - Comprehensive documentation (REQUIREMENTS.md, reference guides, publishing guide)
- `/validate-album` skill - Validates album structure, file locations, catches path issues
- `/test e2e` - End-to-end integration test that creates test album and exercises full workflow
- `/import-audio` skill - Moves audio files to correct `{audio_root}/{artist}/{album}/` location
- `/import-track` skill - Moves track .md files to correct album location with numbering
- `/import-art` skill - Places album art in both audio and content folders
- `/new-album` skill - Creates album directory structure with all templates
- `/about` skill - About bitwize and links to bitwizemusic.com
- `/configure` skill for interactive setup
- `/test` skill for automated plugin validation (13 test categories)
- GitHub issue templates (bug reports, feature requests)
- Suno Persona field in album template for consistent vocal style
- Comprehensive Suno V5 best practices guide
- Artist name → style description reference (200+ artists)
- Pronunciation guide with phonetic spellings
- Shared `tools_root` at `~/.bitwize-music/` for mastering venv
- `documents_root` config for PDF/primary source storage
- Core skills: lyric-writer, researcher, album-conceptualizer, suno-engineer
- Specialized researcher sub-skills (legal, gov, journalism, tech, security, financial, historical, biographical, primary-source, verifier)
- Album/track/artist templates
- Mastering workflow with Python tools
- Release director workflow
- Tutorial skill for guided album creation

### Changed
- Config lives at `~/.bitwize-music/config.yaml` (outside plugin dir)
- Audio/documents paths mirror content structure: `{root}/{artist}/{album}/`
- Mastering scripts accept path argument instead of being copied into audio folders
- Researcher skill saves RESEARCH.md/SOURCES.md to album directory, not working directory
- All path-sensitive operations read config first (enforced)
- Brand casing standardized to `bitwize-music` (lowercase)

### Fixed
- Audio files being saved to wrong location (missing artist folder)
- Research files being saved to working directory instead of album directory
- Mastering scripts mixing .py files with .wav files in audio folders
- User-provided names now preserve exact casing (no auto-capitalization)
- Skill references in docs now use full `/bitwize-music:` prefix (required for plugin skills)
- Researcher skill names aligned with folder names (colon → hyphen in frontmatter)
