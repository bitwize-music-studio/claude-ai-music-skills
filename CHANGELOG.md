# Changelog

All notable changes to claude-ai-music-skills.

This project uses [Conventional Commits](https://conventionalcommits.org/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

### Changed

### Fixed

## [0.14.2] - 2026-01-27

### Fixed
- Promo videos now read track titles from markdown frontmatter when `--album` specified
  - Uses actual title from `{content_dir}/tracks/*.md` instead of filename
  - Falls back to uppercase filename conversion if markdown not found
- Improved special character escaping for ffmpeg drawtext filter
  - Handles apostrophes, quotes, backticks, colons, semicolons, brackets, ampersands
  - Prevents ffmpeg errors on tracks with special characters in titles

## [0.14.1] - 2026-01-27

### Fixed
- Add missing YAML frontmatter to `promo-director` and `resume` skills (skills weren't appearing in Claude Code)
- Add `--batch-artwork` and `--album` flags to promo video generator for better artwork discovery
  - `--batch-artwork /path/to/art.png` - explicit artwork path
  - `--album my-album` - checks content directory for artwork via config
  - Better error messages showing where artwork was searched

## [0.14.0] - 2026-01-27

### Added
- `/bitwize-music:cloud-uploader` skill for uploading promo videos to Cloudflare R2 or AWS S3
  - Uses boto3 S3-compatible API (works with both R2 and S3)
  - Dry-run mode for previewing uploads
  - Public/private upload options
  - Path organization: `{bucket}/{artist}/{album}/promos/`
  - Comprehensive setup guide in `/reference/cloud/setup-guide.md`
  - Config section added to `config/config.example.yaml`

## [0.13.0] - 2026-01-26

### Added
- **promo-director skill**: Generate professional promo videos for social media from mastered audio
  - Creates 15-second vertical videos (9:16, 1080x1920) optimized for Instagram Reels, Twitter, TikTok
  - 9 visualization styles: pulse, bars, line, mirror, mountains, colorwave, neon, dual, circular
  - Automatic color extraction from album artwork (dominant + complementary colors)
  - Intelligent audio segment selection using librosa (falls back to 20% into track)
  - Batch processing: individual track promos + album sampler video
  - Config integration: reads artist name from `~/.bitwize-music/config.yaml`
  - Robust artwork detection: finds album.png, album-art.png, artwork.png, cover.png, etc.
  - Multi-font path discovery (works on Linux/macOS)
  - Platform-optimized output: H.264, AAC, yuv420p, 30fps
  - Album sampler with crossfades (fits Twitter's 140s limit)
- **Promo video tools**: 3 Python scripts in `tools/promotion/`
  - `generate_promo_video.py` - Core video generator with 9 styles
  - `generate_album_sampler.py` - Multi-track sampler video
  - `generate_all_promos.py` - Batch wrapper for complete campaigns
- **Promo video documentation**:
  - `skills/promo-director/SKILL.md` - Complete skill workflow
  - `skills/promo-director/visualization-guide.md` - Style gallery with genre recommendations
  - `reference/promotion/promo-workflow.md` - End-to-end workflow guide
  - `reference/promotion/platform-specs.md` - Instagram, Twitter, TikTok, Facebook, YouTube specs
  - `reference/promotion/ffmpeg-reference.md` - Technical ffmpeg documentation
  - `reference/promotion/example-output.md` - Visual examples and benchmarks
  - `reference/promotion/promotion-preferences-override.md` - Override template
- **Config support for promo videos**: Added `promotion` section to `config/config.example.yaml`
  - `default_style` - Default visualization style (pulse, bars, etc.)
  - `duration` - Default video duration (15s, 30s, 60s)
  - `include_sampler` - Generate album sampler by default
  - `sampler_clip_duration` - Seconds per track in sampler (12s default)
- **Workflow integration**: Added promo videos as optional step 8 (between Master and Release)
  - Updated CLAUDE.md workflow: Concept → Research → Write → Generate → Master → **Promo Videos** → Release
  - Added to Album Completion Checklist
  - Added "Promo Videos (Optional)" section to CLAUDE.md
- **Plugin keywords**: Added promo-videos, social-media, video-generation to plugin.json
- **Skill documentation safeguards**: Added validation and documentation to prevent skills being forgotten
  - `tools/validate_help_completeness.py` - Cross-platform Python script that checks all skills are documented
  - Validates skills appear in CLAUDE.md skills table
  - Validates skills appear in skills/help/SKILL.md
  - Integrated into `/bitwize-music:test consistency` suite
  - Added "Adding a New Skill - Complete Checklist" to CONTRIBUTING.md with 15-item checklist
  - Lists all required files, recommended updates, testing steps, and common mistakes

### Changed
- **import-art compatibility**: All promo scripts now check for multiple artwork naming patterns
  - album.png, album.jpg (standard import-art output)
  - album-art.png, album-art.jpg (alternative from import-art content location)
  - artwork.png, artwork.jpg, cover.png, cover.jpg (fallbacks)
  - Scripts check both album directory and parent directory
  - Clear error messages when artwork not found

### Fixed

## [0.12.1] - 2026-01-26

### Fixed
- **Critical**: Fixed mastering-engineer skill to run scripts from plugin directory instead of copying them to audio folders
  - Scripts now use dynamic plugin path finding (version-independent)
  - Uses `find` command to locate latest plugin version automatically
  - Scripts invoked with audio path as argument instead of cd-ing to audio folder
  - Removed all instructions to copy scripts (cp command)
  - Added "Important: Script Location" section with CRITICAL warning
  - Added Common Mistakes section with 5 error patterns:
    - Don't copy scripts to audio folders
    - Don't hardcode plugin version number
    - Don't run scripts without path argument
    - Don't forget to activate venv
    - Don't use wrong path for mastered verification
  - Updated "Per-Album Session" workflow to use dynamic paths
  - Added regression test to prevent recurrence

**Root cause**: Previous documentation implied scripts lived in audio folder by saying "navigate to folder, run python3 analyze_tracks.py", causing Claude to copy scripts first. Plugin version numbers in cache path (0.12.0, 0.13.0, etc.) meant hardcoded paths would break after updates.

**Impact**: Audio folders now stay clean (only audio files), scripts always use latest version, plugin updates don't break mastering workflow.

## [0.12.0] - 2026-01-26

### Added
- **Quick Win #1**: Added `/bitwize-music:resume` skill to README.md Skills Reference table (Setup & Maintenance section)
- **Quick Win #2**: Comprehensive Troubleshooting section in README.md with 8 common issue categories
  - Config Not Found with setup instructions
  - Album Not Found When Resuming with debug steps
  - Path Resolution Issues with correct structure examples
  - Python Dependency Issues for mastering
  - Playwright Setup for document hunter
  - Plugin Updates Breaking Things
  - Skills Not Showing Up
  - Still Stuck? with GitHub issue link
- **Quick Win #3**: Getting Started Checklist in README.md with step-by-step setup instructions
  - Appears before Quick Start section for better onboarding flow
  - Includes all required steps: plugin install, config setup, optional dependencies
  - Each step has code examples and explanations
- **Quick Win #5**: Model Strategy section in README.md explaining Claude model usage
  - Table showing Opus 4.5 for critical creative outputs (lyrics, Suno prompts)
  - Sonnet 4.5 for most tasks (planning, research)
  - Haiku 4.5 for pattern matching (pronunciation scanning)
  - Rationale for model choices (quality vs cost optimization)
  - Reference to /skill-model-updater for checking models
- **Quick Win #6**: Visual workflow diagram in README.md "How It Works" section
  - ASCII box diagram showing full pipeline: Concept → Research → Write → Generate → Master → Release
  - Specific actions listed under each phase
  - Improves at-a-glance understanding of workflow
- **Quick Win #7**: Common Mistakes sections added to 4 path-handling skills
  - skills/new-album/SKILL.md: 5 mistake patterns (config reading, path construction, genre categories)
  - skills/import-audio/SKILL.md: 5 mistake patterns (artist in path, audio_root vs content_root)
  - skills/import-track/SKILL.md: 6 mistake patterns (tracks subdirectory, track number padding)
  - skills/import-art/SKILL.md: 6 mistake patterns (dual locations, filename conventions)
  - Each mistake includes Wrong/Right code examples and "Why it matters" explanation
  - 22 total mistake examples preventing most common path-related errors
- **Quick Win #9**: Enhanced config.example.yaml with inline examples throughout
  - Artist name examples ("bitwize", "my-band", "dj-shadow-clone")
  - Genre choice examples for each section
  - Path pattern examples (~/music-projects, ".", absolute paths)
  - Platform URL examples (Apple Music, Twitter added)
  - Notes about writability, file types, and use cases
  - All sections use "Examples:" or "Example:" format consistently
- **Quick Win #10**: Cross-references added to 4 key reference documentation files
  - reference/suno/pronunciation-guide.md: Related Skills and See Also sections
  - reference/suno/v5-best-practices.md: Related Skills and See Also sections
  - reference/suno/structure-tags.md: Related Skills and See Also sections
  - reference/mastering/mastering-workflow.md: Related Skills and See Also sections
  - Each cross-reference links to related skills and documentation for better navigation
- Test coverage: 15 new regression tests added to skills/test/SKILL.md
  - Tests for all 10 quick wins
  - Verifies README sections exist and have required content
  - Verifies template consistency
  - Verifies Common Mistakes sections in skills
  - Verifies config examples present
  - Verifies cross-references in reference docs

### Changed
- **Quick Win #4**: templates/ideas.md status values standardized from "Idea | Ready to Plan | In Progress" to "Pending | In Progress | Complete"
  - Now consistent with album-ideas skill documentation
  - Added status explanations (Pending: idea captured, In Progress: actively working, Complete: released or archived)

## [0.11.0] - 2026-01-26

### Added
- New `/bitwize-music:help` skill - comprehensive quick reference for all skills, workflows, and tips
  - Skills organized by category (Album Creation, Research, QC, Production, File Management, System)
  - Common workflow guides (new album, true-story albums, resuming work)
  - Quick tips reference (config, pronunciation, explicit content, mastering, status flows)
  - Key documentation paths
  - Getting help section with navigation tips
- Added help skill to CLAUDE.md skills table
- Added help skill to README.md Setup & Maintenance section

## [0.10.1] - 2026-01-26

### Fixed
- Removed reference to non-existent `/bitwize-music:help` skill in session startup productivity tips
- Updated tip to simply suggest asking "what should I do next?" for guidance

## [0.10.0] - 2026-01-26

### Added
- Session startup contextual tips system in CLAUDE.md
  - Smart, contextual one-liners based on detected user state
  - 6 conditional tip categories: tutorial (new users), album ideas, resume, overrides customization, overrides loaded confirmation, verification warning
  - 6 rotating general productivity tips for feature discovery
  - Tips show right feature at right time without overwhelming users
- Comprehensive test suite for session startup tips
  - Tests verify all 6 conditional tip categories are documented
  - Tests verify productivity tips reference actual skills
  - Tests verify correct skill command format
  - Tests verify path variables used instead of hardcoded paths

### Changed
- Session Start section in CLAUDE.md now shows contextual tips after status summary
- Session startup tips replace single static tip with comprehensive contextual guidance
- Final session startup prompt now asks "What would you like to work on?"

## [0.9.1] - 2026-01-26

### Changed
- Updated all documentation examples to use generic album names (my-album, demo-album) instead of "shell-no"
  - Changed examples in /resume skill documentation
  - Changed examples in CLAUDE.md "Finding Albums" section
  - Changed examples in "Resuming Work" section
  - Changed examples in "Creating a New Album" section

## [0.9.0] - 2026-01-26

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
