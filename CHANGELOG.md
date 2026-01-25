# Changelog

All notable changes to claude-ai-music-skills.

This project uses [Conventional Commits](https://conventionalcommits.org/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `/validate-album` skill - Validates album structure, file locations, catches path issues
- `/test e2e` - End-to-end integration test that creates test album and exercises full workflow
- `/import-audio` skill - Moves audio files to correct `{audio_root}/{artist}/{album}/` location
- `/import-track` skill - Moves track .md files to correct album location with numbering
- `/import-art` skill - Places album art in both audio and content folders
- `/new-album` skill - Creates album directory structure with all templates
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
