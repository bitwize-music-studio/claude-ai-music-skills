# Changelog

All notable changes to claude-ai-music-skills.

This project uses [Conventional Commits](https://conventionalcommits.org/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `/bitwize-music:resume` skill - Dedicated skill for resuming work on albums
  - Takes album name as argument
  - Reads config to get paths
  - Uses Glob to find album across all genre folders
  - Reads album README and track files to assess status
  - Determines current workflow phase (Planning, Writing, Generating, Mastering, etc.)
  - Reports detailed status: location, progress, what's done, next steps
  - Lists available albums if target album not found
  - Handles case-insensitive matching and album name variations
  - Usage: `/bitwize-music:resume shell-no`

### Changed
- CLAUDE.md "Finding Albums" section now recommends `/bitwize-music:resume` skill as the primary approach
- "Resuming Work on an Album" section updated to prioritize the resume skill
- Skills table: Added `/bitwize-music:resume` at the top
- Session Start tip now mentions `/bitwize-music:resume <album-name>` instead of tutorial resume

### Fixed

## [0.8.2] - 2026-01-26

### Added
- "Resuming Work on an Album" section in CLAUDE.md with explicit instructions for finding albums when user mentions them

### Changed
- Session Start step 4 now includes explicit instructions to use Glob tool to find album READMEs
- Clearer scanning instructions: find `{content_root}/artists/*/albums/*/*/README.md`, read each, report status

### Fixed
- Improved album discovery workflow - Claude now has clear step-by-step instructions for finding albums when user says "let's work on [album]"
  - Always read config first to get content_root and artist name
  - Use Glob to search for album README files
  - Read album and track files to assess current state
  - Report location, status, and next actions
  - Common mistakes highlighted (don't assume paths, don't guess genre folders, always search fresh)

## [0.8.1] - 2026-01-26

### Added
- `/clipboard` skill - Copy track content (lyrics, style prompts) to system clipboard
  - Cross-platform support: macOS (pbcopy), Linux (xclip/xsel), WSL (clip.exe)
  - Content types: lyrics, style, streaming-lyrics, all (combined Suno inputs)
  - Auto-detects platform and clipboard utility
  - Config-aware path resolution
  - Usage: `/clipboard <content-type> <album-name> <track-number>`
- Workflow reference documentation in `/reference/workflows/`
  - `checkpoint-scripts.md` - Detailed checkpoint message templates
  - `album-planning-phases.md` - The 7 Planning Phases detailed guide
  - `source-verification-handoff.md` - Human verification procedures
  - `error-recovery.md` - Edge case recovery procedures
  - `release-procedures.md` - Album art generation and release steps
- `/reference/distribution.md` - Streaming lyrics format and explicit content guidelines

### Changed
- **CLAUDE.md refactored for performance** - Reduced from 50,495 to 34,202 characters (32% reduction)
  - Compressed checkpoint sections - Kept triggers/actions, moved verbose messages to `/reference/workflows/checkpoint-scripts.md`
  - Condensed Audio Mastering section - Brief overview with reference to existing `/reference/mastering/mastering-workflow.md`
  - Condensed Sheet Music section - Summary with reference to `/reference/sheet-music/workflow.md`
  - Condensed Album Art Generation - Core workflow with reference to `/reference/workflows/release-procedures.md`
  - Condensed 7 Planning Phases - Summary with reference to `/reference/workflows/album-planning-phases.md`
  - Condensed Human Verification Handoff - Triggers with reference to `/reference/workflows/source-verification-handoff.md`
  - Condensed Error Recovery - Quick reference with link to `/reference/workflows/error-recovery.md`
  - Condensed Distribution Guidelines - Combined streaming lyrics and explicit content with reference to `/reference/distribution.md`
  - Simplified Creating Content sections - Condensed album creation and file import workflows
  - Simplified Suno Generation Workflow - Streamlined process description
  - Architecture: CLAUDE.md now focuses on workflow orchestration (WHEN/WHY), detailed procedures in reference docs (HOW)

## [0.8.0] - 2026-01-26

### Added
- **Complete override support for 10 skills** - All creative/stylistic skills now support user customization via `{overrides}` directory
  - `album-art-director` → `album-art-preferences.md` (visual style, color palettes, composition)
  - `researcher` → `research-preferences.md` (source priorities, verification standards, research depth)
  - `release-director` → `release-preferences.md` (QA checklist, platform priorities, metadata standards, timeline)
  - `sheet-music-publisher` → `sheet-music-preferences.md` (page layout, notation, songbook formatting)
  - Previously added (0.7.x): explicit-checker, lyric-writer, suno-engineer, mastering-engineer, album-conceptualizer, pronunciation-specialist
  - All skills follow unified override pattern: check `{overrides}/[skill-file]`, merge with base, fail silently if missing
  - Complete documentation in config/README.md with examples for all 10 override files
- `/album-ideas` skill - Track and manage album concepts before creating directories
  - Commands: list, add, remove, status, show, edit
  - Organize by status: Pending, In Progress, Complete
  - Config-based location: `paths.ideas_file` (defaults to `{content_root}/IDEAS.md`)
  - Creates template file automatically on first use
  - Integrated into session start workflow (step 3: check album ideas)

### Changed
- CLAUDE.md session start now checks album ideas file (step 3) and mentions `/album-ideas list` for details
- `/configure` skill now prompts for `paths.ideas_file` during setup
- config/README.md expanded with comprehensive override system documentation (10 skills, full examples)
- Skills table in CLAUDE.md now includes `/album-ideas` skill

### Fixed
- Tests updated to validate override support in all 10 skills and album-ideas commands

## [0.7.1] - 2026-01-26

### Changed
- **BREAKING**: Refactored customization system to use unified overrides directory
  - Replaced `paths.custom_instructions` with `paths.overrides`
  - Replaced `paths.custom_pronunciation` with `paths.overrides`
  - Single directory now contains all override files: `~/music-projects/overrides/`
  - Override files: `CLAUDE.md`, `pronunciation-guide.md`, `explicit-words.md` (future), etc.
  - Benefits: self-documenting, easy discovery, future-proof, convention over configuration
  - **Note**: Released immediately after 0.7.0 to fix design before user adoption

### Fixed
- Config design now scales for future overrides without new config fields

## [0.7.0] - 2026-01-26 **[DEPRECATED - Use 0.7.1]**

### Added
- Custom instructions support (`paths.custom_instructions` config field)
  - Load user's custom Claude workflow instructions at session start
  - Defaults to `{content_root}/CUSTOM_CLAUDE.md` if not set in config
  - Supplements (doesn't override) base CLAUDE.md
  - Optional - fails silently if file doesn't exist
  - Prevents plugin update conflicts for user workflow preferences
- Custom pronunciation guide support (`paths.custom_pronunciation` config field)
  - Load user's custom phonetic spellings at session start
  - Defaults to `{content_root}/CUSTOM_PRONUNCIATION.md` if not set in config
  - Merges with base pronunciation guide, custom entries take precedence
  - Optional - fails silently if file doesn't exist
  - pronunciation-specialist adds discoveries to custom guide, never edits base
  - Prevents conflicts when plugin updates base pronunciation guide
- Mandatory homograph auto-fix in lyric-reviewer
  - Automatically detects and fixes homographs based on context
  - Reference table of 8 common homographs with phonetic fixes
  - No longer asks user "Option A or B?" - applies fix immediately
  - Explicit anti-pattern warning in documentation

### Changed
- `/configure` skill now prompts for custom_instructions and custom_pronunciation paths during setup
- `/pronunciation-specialist` now loads and merges both base and custom pronunciation guides
- `/lyric-reviewer` pronunciation check now links to mandatory auto-fix section
- CLAUDE.md session start procedure now loads custom instructions and custom pronunciation files
- Self-updating skills documentation clarified: pronunciation-specialist updates custom guide only

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
