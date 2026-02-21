# Changelog

All notable changes to claude-ai-music-skills.

This project uses [Conventional Commits](https://conventionalcommits.org/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Mastering genre confirmation** — mastering-engineer skill now asks to confirm the genre preset before mastering and checks if any tracks need different treatment
- **`check_venv_health` MCP tool** — compares installed package versions against `requirements.txt` pins; integrated into session start to warn about version drift after plugin upgrades
- **Configurable debug logging** — new `logging` section in config.yaml enables file-based debug logging with rotation; silent by default, opt-in for development/troubleshooting
- **`reset_mastering` MCP tool** — removes `mastered/` and/or `polished/` subfolders so the mastering pipeline can be re-run cleanly; dry-run safe by default, `originals/` and `stems/` are protected
- **`cleanup_legacy_venvs` MCP tool** — detects and removes stale per-tool venvs (`mastering-env`, `promotion-env`, `cloud-env`) left over from pre-0.40.0; dry-run safe by default
- **Dev mode docs** — CONTRIBUTING.md section explaining how to avoid cached plugin conflicts when using `--plugin-dir`

### Removed
- **Redundant requirements files** — removed `requirements-mastering.txt`, `requirements-mixing.txt`, `requirements-promo.txt`, `requirements-research.txt`, `requirements-sheet-music.txt`, and `tools/cloud/requirements.txt`; the unified `requirements.txt` covers all dependencies

### Fixed
- **Stale venv references** — updated `config/README.md`, `TESTING.md`, `reference/mastering/mastering-workflow.md`, and `skills/test/test-definitions.md` to reference unified `venv/` instead of legacy `mastering-env/`
- **Migration 0.40.0** — added missing `cloud-env` cleanup action
- **CI installs full dependencies** — `test.yml` now uses `requirements.txt` instead of the removed `requirements-mastering.txt`

## [0.62.0] - 2026-02-21

### Added
- **`develop` branch model** — two-branch workflow with `develop` for active work and `main` for stable releases; plugin distribution channels via branch-based marketplace
- **Plugin version in about skill** — `/bitwize-music:about` now reads and displays version from plugin.json dynamically

### Changed
- **CI targets Python 3.11 only** — dropped 3.9/3.10/3.12 matrix; not a library, runs in user's venv
- **CI triggers** — pushes run on `develop` only; `main` validated via PR gate
- **CONTRIBUTING.md** — updated for develop/main branch model, release process, co-author line

### Fixed
- **Test count badge** — corrected 2235 → 2238 (3 skipped tests collected by CI)

## [0.61.0] - 2026-02-21

### Added
- **`originals/` audio layout** — raw WAV files now stored in `originals/` subdirectory to keep album audio root clean; all tools (mastering, mixing, promotion, import-audio) updated with backward-compatible fallback to album root for legacy albums
- **`migrate_audio_layout` MCP tool** — migrates pre-existing albums from root-level WAVs to `originals/` layout (dry-run safe by default, single album or batch)
- **Fade-out support** — `apply_fade_out()` in mastering pipeline with exponential/linear curves; `fade_out` parameter in `master_track()`, track file parser, and track template (`| **Fade Out** | — |`)
- **Mix polish character effects** — `apply_saturation()` (tanh waveshaping), `apply_lowpass()` (Butterworth), `apply_stereo_width()` (mid-side processing) in mix_tracks.py; genre presets updated for 50+ genres with per-stem saturation, lowpass, and stereo width settings
- **29 new tests** — 6 for `migrate_audio_layout`, plus mastering and mixing coverage

### Changed
- **CLAUDE.md** — updated audio path structure documentation to reflect `originals/` layout
- **import-audio skill** — imports now target `originals/` subdirectory
- **mastering-engineer skill** — updated pre-flight check to look in `originals/` first
- **mix-engineer skill** — updated audio directory convention docs

## [0.60.0] - 2026-02-21

### Added
- **Suno stem discovery** — `discover_stems()` maps Suno's exported filenames (`0 Lead Vocals.wav`, `1 Backing Vocals.wav`) to polish pipeline stem roles via keyword-based matching + multi-file combining
- **Mastering auto-recovery** — `master_album` Stage 5 auto-detects recoverable dynamic range failures (LUFS too low + peak at ceiling) and applies `fix_dynamic()` from raw source files before re-verifying
- **`fix_dynamic()` reusable helper** — extracted core fix logic into a function that accepts pipeline settings (target LUFS, EQ, ceiling) instead of hardcoded values
- **12 new tests** — 7 unit tests for `fix_dynamic()`, 5 pipeline tests for auto-recovery scenarios

### Fixed
- **`fix_dynamic_track` MCP tool** — now uses shared `fix_dynamic()` instead of inline code

## [0.59.0] - 2026-02-20

### Added
- **`mix-engineer` skill** — automated per-stem audio polish pipeline for Suno output cleanup
- **`tools/mixing/mix_tracks.py`** — core DSP module: spectral gating noise reduction, Butterworth highpass, parametric EQ, high shelf, envelope-following compression, click detection/interpolation, mid-side stereo enhancement, stem remixing with per-stem gain
- **`tools/mixing/mix-presets.yaml`** — genre presets for 50+ genres with per-stem processing settings and deep-merge user override support
- **`polish_audio` MCP tool** — process stems or full mixes with genre presets
- **`analyze_mix_issues` MCP tool** — spectral analysis for noise floor, muddiness, harshness, clicks, sub-rumble
- **`polish_album` MCP tool** — 3-stage pipeline (analyze → polish → verify)
- **`source_subfolder` parameter on `master_audio`** — read WAVs from a subfolder (e.g., "polished") for polish → master chaining
- **89 unit tests** for mix_tracks.py — 16 test classes covering all DSP functions, pipeline modes, preset loading, numerical stability, and override merging
- **`requirements-mixing.txt`** — standalone dependency file for mixing tools

### Fixed
- **Python 3.9 compat** — replaced `str | None` union syntax with `Optional[str]` in server.py
- **Lint** — removed unused `reachable` variable in URL checking
- **README badges** — updated skills count (49→50), test count (1969→2183), added mix-engineer to workflow table and skills reference

## [0.58.0] - 2026-02-16

### Added
- **`ship` skill** — automates full code release pipeline (branch → commit → PR → CI → merge → version bump → release → cleanup)

### Fixed
- **Unused import** — removed `parse_frontmatter` from server.py imports (ruff F401)
- **Bandit false positives** — added `nosec` annotations for parameterized SQL and validated URL open in server.py
- **README version badge** — updated from 0.56.0 to match plugin.json 0.57.0

## [0.57.0] - 2026-02-16

### Added
- **PostgreSQL database integration** — 8 new MCP tools for social media post management (`db_init`, `db_list_tweets`, `db_create_tweet`, `db_update_tweet`, `db_delete_tweet`, `db_search_tweets`, `db_sync_album`, `db_get_tweet_stats`)
- **Database config section** — `database:` in config.yaml for PostgreSQL credentials with password masking in state
- **Portable schema** — `tools/database/schema.sql` with migrations directory for future changes
- **n8n workflow export** — `tools/n8n/n8n-auto-post-twitter.json` for automated Twitter/X posting (sanitized, no credentials)
- **`tools/database/`** — connection helper, schema, README with setup instructions
- **`tools/n8n/`** — workflow exports with setup docs, credential notes, and API cost info

## [0.56.0] - 2026-02-16

### Added
- **9 artist deep-dives** — production-level sonic profiles for trance (t.A.T.u., Cascada, ATB, Alice Deejay, Ian Van Dahl), pop (Ace of Base, Aqua, La Bouche), and electronic (Eiffel 65) with members, discography, musical analysis, Suno prompt keywords, and reference tracks
- **Trance artists INDEX.md** — quick-reference Suno keywords and reference tracks for all 5 trance artists
- **Pop/Electronic INDEX updates** — added new artists to existing genre INDEX files

### Fixed
- **Suno auto-fill SPA routing** — userscript now detects Next.js client-side navigation via History API monkey-patching (pushState/replaceState + popstate); button injects on `/create`, removes on other pages, never duplicates

## [0.55.0] - 2026-02-15

### Added
- **`count_syllables` MCP tool** — syllable counts per line with section tracking, consistency analysis (stdev > 3 = UNEVEN), and summary stats
- **`analyze_readability` MCP tool** — Flesch Reading Ease scoring, vocabulary richness, and grade level assessment for lyrics
- **`analyze_rhyme_scheme` MCP tool** — rhyme scheme detection (AABB/ABAB/XAXA) with section awareness, self-rhyme and repeated end word detection
- **`validate_section_structure` MCP tool** — section tag validation, balanced verse lengths (diff > 2 lines flagged), empty/duplicate/missing section detection, content-before-first-tag warning
- **`_count_syllables_word` helper** — vowel cluster heuristic for syllable counting (silent 'e', consonant-'le' endings, y-as-vowel)
- **`_get_rhyme_tail` / `_words_rhyme` helpers** — suffix-based rhyme detection from last vowel cluster to end of word, with silent-e handling and plural tolerance
- **85 unit tests** for lyrics analysis tools (`test_server_lyrics.py`) — 13 test classes covering all helpers and MCP tools with edge cases, boundary conditions, and bug-catching coverage

## [0.54.0] - 2026-02-14

### Added
- **`extract_distinctive_phrases` MCP tool** — extracts 4-7 word n-grams from lyrics with section awareness, filters ~75 common song cliches and stopword-only phrases, ranks by section priority (chorus/hook > verse), returns pre-formatted web search suggestions for plagiarism checking
- **`_COMMON_SONG_PHRASES` constant** — frozenset of ~75 ubiquitous lyric cliches filtered during phrase extraction (love/heartbreak, night/time, pain/struggle, fire/light, generic emotional)
- **`plagiarism-checker` skill** — scans lyrics for phrases that may match existing songs using web search and LLM knowledge; standalone quality check (not a pre-generation gate) with HIGH/MEDIUM/LOW risk findings and CLEAR/NEEDS REVIEW/REWRITE REQUIRED verdicts
- **~35 unit tests** for distinctive phrase extraction (`test_server_lyrics.py`) — covers `_tokenize_lyrics_with_sections` helper, `_extract_distinctive_ngrams` helper, and `extract_distinctive_phrases` MCP tool

## [0.53.0] - 2026-02-14

### Added
- **`check_cross_track_repetition` MCP tool** — scans all tracks in an album for words and phrases repeated across multiple tracks; tokenizes lyrics into words and 2-4 word n-grams, filters stopwords and common song vocabulary, flags items appearing in N+ tracks (configurable threshold)
- **70 unit tests** for cross-track repetition analysis (`test_server_lyrics.py`) — covers helpers (`_tokenize_lyrics_by_line`, `_ngrams_from_lines`), tool edge cases (slug normalization, unreadable files, stopword filtering, sort order, summary structure), and realistic multi-section lyrics

## [0.52.1] - 2026-02-14

### Fixed
- **Album sampler track titles** — `get_track_title()` now converts slug format to readable titles (e.g., "ocean-of-tears" → "Ocean Of Tears"), matching individual promo video behavior
- **Album sampler MCP title resolution** — `generate_album_sampler` MCP tool now pre-resolves proper titles from state cache (markdown metadata) and passes them to the sampler, so titles match exactly what's in track files

## [0.52.0] - 2026-02-14

### Added
- **`get_python_command` MCP tool** — returns venv Python path, plugin root, and ready-to-use command template; prevents skills from hitting system Python which lacks dependencies
- **4 new tests** for `get_python_command` (venv exists, venv missing, plugin root, usage template)

### Changed
- **Skills migrated from bare python3 to MCP tools** — mastering-engineer (12 refs), promo-director (2 refs), sheet-music-publisher (9 refs), session-start (1 ref) now use MCP tools instead of bash python3 commands
- **Skills without MCP equivalents use `get_python_command`** — cloud-uploader (4 refs), test-definitions (1 ref) now call `get_python_command()` first to get the venv path
- **CLAUDE.md** — indexer rebuild references updated to `rebuild_state()` MCP tool
- **genre-presets.md** — all python3 CLI examples replaced with MCP tool calls

## [0.51.0] - 2026-02-14

### Fixed
- **`resolve_path` mirrored structure** — audio and documents paths now use `{root}/artists/{artist}/albums/{genre}/{album}/` matching the content structure (was flat `{root}/{artist}/{album}/`)
- **Genre lookup for audio/documents** — `resolve_path` MCP tool and `paths.py` utility now look up genre from state cache for all path types (was only content/tracks)
- **`_resolve_audio_dir` genre support** — mastering/QC MCP tools now resolve genre from state cache instead of using flat paths
- **`validate_album_structure` wrong-location check** — detects old flat audio structure as misplaced files
- **`rename_album` path construction** — uses mirrored structure for audio and documents directories
- **`upload_to_cloud.py` path finder** — tries mirrored structure first with glob fallback
- **35 documentation files** — updated all path references from flat to mirrored structure

### Added
- **Per-track stems subfolders** — `import-audio` skill now extracts stems into `stems/{track-slug}/` subfolders preventing filename collisions across tracks
- **Stems file type detection** — `import-audio` skill detects zip files and routes to stems extraction workflow
- **Track slug derivation** — stems import infers track from zip filename, user argument, or prompts

## [0.50.0] - 2026-02-13

### Added
- `master_album` MCP tool — end-to-end mastering pipeline (analyze → QC → master → verify → QC → status update) in a single call
- Technical Audio QC tool (`qc_tracks.py`) with 7 checks: mono compatibility, phase correlation, clipping, click/pop detection, silence, format validation, spectral balance
- `qc_audio` MCP tool for running QC from skills
- QC gates integrated into mastering-engineer workflow (pre and post mastering)

## [0.49.0] - 2026-02-13

### Added
- **K-pop genre research** — 27 artist deep-dive files covering all major K-pop acts across 4 generations (BTS, BLACKPINK, Stray Kids, NewJeans, aespa, (G)I-DLE, ATEEZ, IVE, LE SSERAFIM, SEVENTEEN, EXO, Girls' Generation, Big Bang, SHINee, TWICE, Red Velvet, 2NE1, TVXQ, Dreamcatcher, ENHYPEN, TXT, ITZY, Epik High, IU, Zion.T, Crush, DEAN) with members, discography, musical analysis, Suno prompt keywords, and reference tracks
- **K-pop artist INDEX** — `genres/k-pop/artists/INDEX.md` quick-reference with Suno keywords and reference tracks for all 27 artists
- **K-pop artist blocklist** — 25 entries added to `reference/suno/artist-blocklist.md` with sonic description alternatives
- **K-pop Suno V5 tips** — comprehensive K-pop section in `reference/suno/v5-best-practices.md` covering style prompts, group vocal sound, Korean-English code-switching, switch-up technique, and common issues
- **Enhanced K-pop README** — expanded with entertainment company sounds (SM, YG, JYP, HYBE, ADOR, Cube, KQ), additional subgenres, industry terms glossary, and artist cross-references

## [0.48.0] - 2026-02-12

### Added
- **`/promo-writer` skill** — generates platform-specific social media copy (Twitter, Instagram, TikTok, Facebook, YouTube) from album themes, track concepts, and streaming lyrics; campaign strategy first, then native per-platform posts with character counts and hashtag compliance (Sonnet tier)
- **Social media best practices reference** — `reference/promotion/social-media-best-practices.md` with per-platform content strategy, algorithm notes, music discovery mechanics, hashtag strategies, indie artist tactics, and cross-platform release rollout templates
- **Copy formulas reference** — `skills/promo-writer/copy-formulas.md` with 6 hook formulas, CTA templates, post structure skeletons, hashtag recipes by genre/phase, and tone adaptation guide
- **Promotion preferences override** — `config/overrides.example/promotion-preferences.md` for customizing tone, platform priorities, messaging themes, hashtag preferences, and AI music positioning

### Fixed
- **Twitter hashtag count** — corrected from "2-3 per tweet" to "1-2 per tweet" in platform-rules.md and promo-reviewer SKILL.md (researched best practice)
- **Twitter hashtag rules** — added "never start with hashtag" (algorithm penalty), tag rotation (spam detection), and Tags to Avoid section (#MusicPromotion, #FollowBack, #Like4Like)
- **Release director promo references** — replaced "manual creative step" with promo-writer reference in QA item 9 and Distribution Prep item 6
- **Promo reviewer workflow** — updated diagram, When to Use, and empty-files message to reference promo-writer as option

## [0.47.0] - 2026-02-11

### Added
- **9 processing MCP tools** — `analyze_audio`, `master_audio`, `fix_dynamic_track`, `master_with_reference`, `transcribe_audio`, `fix_sheet_music_titles`, `create_songbook`, `generate_promo_videos`, `generate_album_sampler` — wrap Python processing scripts for direct MCP invocation with lazy dep checking and structured JSON responses
- **Suno auto-fill clipboard type** — `format_for_clipboard` now supports `"suno"` content type returning JSON with title, style, and lyrics for browser auto-fill
- **Tampermonkey userscript** — `tools/userscripts/suno-autofill.user.js` auto-fills Suno's create page from clipboard JSON with adaptive field detection and React-compatible input simulation
- **Album streaming block** — album template frontmatter now includes `streaming:` dict with soundcloud, spotify, apple_music, youtube_music, amazon_music keys for listen page generation

### Fixed
- **Pillow CVE-2026-25990** — bumped pillow 10.4.0 → 12.1.1
- **CI lint/security scope** — ruff and bandit now scan `servers/` in addition to `tools/`
- **Ruff warnings** — fixed pre-existing unused imports, variables, and f-string prefix issues in server.py

### Removed
- **Legacy URL fields** — removed `soundcloud_url` and `spotify_url` flat fields from album template (replaced by `streaming:` block)

## [0.46.0] - 2026-02-11

### Changed
- **Complete MCP migration** — migrated remaining 3 skills (`tutorial`, `validate-album`, `sheet-music-publisher`) to use MCP tools instead of manual file access; all 46 skills now use MCP tools where applicable
- **`tutorial`** — config reads → `get_config()`, album scanning → `list_albums()` + `get_album_progress()`
- **`validate-album`** — manual config + `find` command → `get_config()` + `find_album()` + `validate_album_structure()`
- **`sheet-music-publisher`** — config read + manual override loading → `get_config()` + `find_album()` + `resolve_path("audio")` + `load_override()`

## [0.45.0] - 2026-02-11

### Added
- **`/promo-reviewer` skill** — interactive post-by-post review of social media copy in album `promo/` files with approve/revise/shorten/punch-up/hashtag/tone actions, character limit enforcement, and write-back (Sonnet tier)
- **Platform rules reference** — `skills/promo-reviewer/platform-rules.md` with per-platform character limits, hashtag conventions, and tone guidelines

### Fixed
- **SKILL_INDEX alphabetical order** — `pre-generation-check` now correctly sorted before `promo-director`
- **model-strategy.md completeness** — added missing `verify-sources` (Sonnet) and `rename` (Haiku) subsections; counts now match actual skill inventory
- **SKILL_INDEX model sections** — added missing `/verify-sources` to Sonnet list and `/setup` to Haiku list
- **Cross-file count consistency** — all four count locations (SKILL_INDEX, model-strategy, distribution table, README) now agree: 6 Opus, 25 Sonnet, 15 Haiku = 46 total

### Changed
- **Skills count at 46** — up from 45 (added `/promo-reviewer`)

## [0.44.0] - 2026-02-10

### Added
- **Rename MCP tools** — `rename_album` and `rename_track` tools handle slug, title, and directory renames across all mirrored path trees (content, audio, documents) with state cache updates
- **`/rename` skill** — interactive wrapper for renaming albums or tracks with confirmation and error handling (Haiku tier)
- **Plugin migration system** — versioned `migrations/` directory with auto, action, info, and manual migration types; session-start checks for upgrades and processes migration actions
- **Promo templates** — 6 per-platform social media copy templates (`campaign.md`, `twitter.md`, `instagram.md`, `tiktok.md`, `facebook.md`, `youtube.md`) in new `templates/promo/` directory
- **Track template frontmatter** — YAML frontmatter with `title`, `track_number`, `explicit`, `suno_url` fields
- **Suno parenthetical warning** — track template now warns that Suno sings parenthetical directions literally
- **Migration tests** — validation suite for migration file format, YAML frontmatter, version matching, and action types
- **Promo template tests** — validates all 6 templates exist and contain required sections
- **32 rename tests** — `TestRenameAlbum` (15), `TestRenameTrack` (12), `TestDeriveTitleFromSlug` (5)

### Changed
- **Social media copy** moved from inline SOURCES.md sections to dedicated `promo/` directory in album content
- **Promo workflow reference** updated to reflect `promo/` directory separation from video files
- **Album art director** description broadened for use during planning, not just post-Final
- **Clipboard skill** heading detection updated to match new track template structure (`### Lyrics Box` / `### Style Box`)
- **Mastering engineer** now requires explicit path resolution step before mastering workflow
- **Test suite at 1585 tests** — up from 1553 in 0.43.1
- **Skills count at 45** — up from 44 (added `/rename`)

### Fixed
- **CONTRIBUTING.md** — added migration checklist item for PRs with filesystem/template/config changes

## [0.43.1] - 2026-02-06

### Added
- **Test count badge validation** — CI step in `test.yml` verifies README badge matches actual pytest count
- **Pre-commit hook check 11/11** — local badge sync validation before commit
- **Version-sync workflow** now triggers on `tests/**` changes and validates test badge presence

### Fixed
- **README model strategy** — updated Opus 4.5 → Opus 4.6, corrected skill counts (24 Sonnet, 14 Haiku)

## [0.43.0] - 2026-02-06

### Added
- **MCP server expanded to 30 tools** — 21 new tools across path resolution, content extraction, text analysis, validation, and album operations
- **3 content analysis tools** — `check_explicit_content`, `extract_links`, `get_lyrics_stats` for pre-generation checks
- **10 content/validation tools** — `extract_section`, `update_track_field`, `format_for_clipboard`, `validate_album_structure`, `get_album_full`, `search`, `check_pronunciation_enforcement`, `load_override`, `get_reference`, `create_album_structure`
- **8 path/query tools** — `resolve_path`, `resolve_track_file`, `list_track_files`, `list_tracks`, `get_album_progress`, `run_pre_generation_gates`, `scan_artist_names`, `check_homographs`
- **160 integration tests** — full end-to-end pipeline tests (real files → indexer → state.json → StateCache → MCP tool), 5+ per tool
- **309 MCP unit tests** — edge cases, error paths, word boundaries, path traversal protection

### Changed
- **MCP server renamed** — `state-server` → `bitwize-music-server` to reflect expanded scope
- **Test suite at 843 tests** — up from 494 in 0.42.0

## [0.42.0] - 2026-02-06

### Added
- **verify-sources skill** — new `/verify-sources` skill for human source verification workflow
- **State schema documentation** — formal `reference/state-schema.md` documenting state.json structure
- **Path resolver utility** — `tools/shared/paths.py` eliminates manual path construction
- **222 new unit tests** — indexer (121), MCP server (90), path resolver (11); suite now at 494
- **Coverage reporting** — pytest-cov with HTML artifact upload in CI
- **README badges** — version and skills count badges with CI sync validation
- **Badge sync in CI** — version-sync workflow now validates README badges match actual values

### Fixed
- **Resume skill** — merged next-step decision tree into resume (Step 8) for single-skill navigation
- **Lyric reviewer checklist** — heading corrected from 13-Point to 14-Point (matches actual items)
- **Lyric workflow test** — regex now matches writer's `Quality Check (N-Point)` format
- **README/CLAUDE.md alignment** — fixed trigger phrases, co-author line, status definitions
- **Import-audio** — added MP3 file handling guidance and supported formats list

### Changed
- **MCP server logging** — structured logging throughout StateCache for debugging
- **Config quick-start** — added 3-field quick-start block to config.example.yaml
- **Overrides docs** — consolidated to single source of truth in config/README.md
- **SKILL_INDEX** — updated navigation references, added verify-sources

## [0.41.6] - 2026-02-06

### Fixed
- **Tweet template DM issue** — moved @bitwizemusic after hashtags in tweet templates so tweets are public instead of becoming DMs

## [0.41.5] - 2026-02-06

### Fixed
- **MCP server config portability** — .mcp.json now uses `${HOME}` and `${CLAUDE_PLUGIN_ROOT}` environment variables instead of hardcoded absolute paths, making the config portable across different installations

## [0.41.4] - 2026-02-05

### Fixed
- **MCP server environment** — .mcp.json now explicitly passes CLAUDE_PLUGIN_ROOT env variable to server process, fixing "missing env variable" startup failures

## [0.41.3] - 2026-02-05

### Fixed
- **MCP server startup** — .mcp.json now uses venv Python (`~/.bitwize-music/venv/bin/python3`) instead of system Python, fixing server initialization failures

## [0.41.2] - 2026-02-05

### Changed
- **Setup skill simplified** — only recommends unified venv approach, removed confusing system-wide install options
- **Setup checks venv** — verifies ~/.bitwize-music/venv contents instead of system Python packages
- **No optional components** — all dependencies install together, clearer messaging

## [0.41.1] - 2026-02-05

### Fixed
- **Setup skill** — runs dependency checks sequentially to prevent sibling tool call cancellation, removes incorrect mcp.__version__ access
- **Pre-commit hook** — pip-audit check now correctly captures exit code and handles errors properly

## [0.41.0] - 2026-02-05

### Added
- **Pre-commit dependency security scan** — pip-audit automatically checks requirements.txt for known vulnerabilities before commit
- **Hook installation guide** — README and install script in hooks/ directory for easy setup

### Fixed
- **Security vulnerabilities** — updated mcp (1.2.0 → 1.23.0) and pypdf (4.3.1 → 6.6.2) to resolve 10 CVEs

## [0.40.0] - 2026-02-05

### Added
- **Unified venv for all plugin tools** — single `~/.bitwize-music/venv` for MCP server, mastering, cloud uploads, and document hunting. Automatic detection with fallback to system Python. Works on Linux, macOS, Windows, and WSL.
- **MCP server wrapper script** — `servers/state-server/run.py` handles platform-specific venv paths (Windows: `Scripts/python.exe`, Unix: `bin/python3`)
- **Single requirements.txt** — consolidated all dependencies into one file with clear sections for each feature

### Changed
- **MCP server environment variable convention** — server now checks `CLAUDE_PLUGIN_ROOT` first (standard), then `PLUGIN_ROOT` (legacy), then derives from file location
- **Installation simplified** — one venv setup installs everything: `python3 -m venv ~/.bitwize-music/venv && pip install -r requirements.txt`
- **MCP .mcp.json** — simplified configuration by removing redundant `PLUGIN_ROOT` env variable

### Removed
- **Separate requirements files** — removed `requirements-mcp.txt` and `requirements-cloud.txt` in favor of unified `requirements.txt`
- **Multiple venvs** — no longer need separate `mcp-env`, `cloud-env`, or `mastering-env` directories

## [0.39.0] - 2026-02-05

### Added
- **Setup skill** — `/bitwize-music:setup` detects Python environment, checks dependencies, and provides installation commands specific to your system (externally-managed vs user-managed Python)
- **Session start setup check** — automatic MCP dependency verification on session start with immediate setup guidance if missing

### Changed
- **MCP server naming** — renamed `bitwize-music-state` → `bitwize-music-mcp` to support future MCP tools beyond state cache
- **MCP error handling** — improved dependency error message with user-install, pipx, and venv instructions for externally-managed Python environments
- **MCP documentation** — added setup instructions to README and server README for Ubuntu/Debian systems

## [0.38.0] - 2026-02-05

### Added
- **MCP server: bitwize-music-state** — bundled MCP server exposing state cache as tools for instant structured responses. Wraps `tools/state/indexer.py` with 9 tools: `find_album`, `list_albums`, `get_track`, `get_session`, `update_session`, `rebuild_state`, `get_config`, `get_ideas`, `get_pending_verifications`. In-memory caching with lazy loading and staleness detection. Server auto-starts when plugin enabled via `.mcp.json`. Requires Python 3.10+, `mcp[cli]>=1.2.0`.
- **Plugin tests: SKILL.md structure validation** — checks all skills have required sections (task description, procedural content, closing guidance, agent title). Accepts common alternatives (## Workflow, ## Step 1, ## Commands, ## Domain Expertise, etc.). Runs as part of pre-commit check #11.
- **CI: plugin tests job** — runs full `run_tests.py` suite (449 tests) in CI, guarded against fork PRs
- **Suno: v5-best-practices.md updates** — Personas workflow, Song Editor, bar count targeting, Creative Sliders, prompt fatigue warning (4-7 descriptor sweet spot), token biases, WMG ownership/licensing, V4.5 comparison note
- **Suno: tips-and-tricks.md updates** — Personas+Covers combo, Song Editor reference, Creative Sliders, catalog protection warning
- **Suno: voice-tags.md updates** — V5 Voice Gender selector, sustained notes technique, emotion arc mapping
- **Suno: structure-tags.md updates** — bar count targeting syntax, performance cues rule, V5 reliability improvements
- **Suno: pronunciation-guide.md updates** — V5 context sensitivity note, IPA not supported, numbers guidance, multilingual track isolation
- **Suno: instrumental-tags.md updates** — Producer's Prompt narrative approach, tag soup warning

### Fixed
- **Plugin manifest: duplicate hooks reference** — removed explicit `hooks/hooks.json` reference from plugin.json since it's loaded automatically by Claude Code

## [0.37.1] - 2026-02-04

### Changed
- **CI: SHA-pinned action references** — all workflow `uses:` directives now reference exact commit SHAs instead of mutable version tags (checkout v4.3.1, setup-python v5.6.0)
- **CI: fork PR protection** — `test` and `lint` jobs skip for fork PRs to prevent untrusted code execution via modified requirements/test files
- **CI: security gates tests** — unit tests now depend on `security` job (pip-audit) completing first
- **CI: explicit read-only permissions** — all non-release workflows now declare `permissions: { contents: read }`
- **CI: GITHUB_OUTPUT delimiter syntax** — all output variables use heredoc delimiters to prevent injection via newlines
- **CI: dead code fix** — model-updater curl error message now reachable under `set -e`
- **CI: fixed-string grep** — auto-release uses `grep -qF` so semver dots aren't regex wildcards
- **CI: heredoc replaced with printf** — model-updater PR body uses `printf %s` instead of unquoted heredoc for variable expansion

## [0.37.0] - 2026-02-04

### Added
- **Security: temp file cleanup** — atexit handlers and `0o600` permissions on temp files in promo video generators
- **Security: path traversal validation** — `Path.relative_to()` containment checks in mastering tools
- **Security: state cache permissions** — `0o700` on cache directory, `0o600` on temp files in indexer
- **Security: album name validation** — character validation before `rglob` in cloud uploader prevents glob injection
- **Security: CI model-updater hardening** — character whitelist and length validation on fetched model IDs
- **Security: session input validation** — length limits, null byte checks, action count cap in state indexer
- **Mastering: pre-flight check** — new Step 1 verifies WAV files exist before mastering workflow
- **Album-conceptualizer: type decision criteria** — guidance for choosing between Documentary, Character Study, Thematic
- **Album-conceptualizer: energy mapping example** — concrete visual example and pacing problems checklist
- **Resume: Research Phase** — suggests `/researcher` and `/document-hunter` for documentary albums
- **Checkpoint scripts: required actions** — action checklists before each checkpoint message template
- **Source verification: human checklist** — 6 concrete items for verifying sources (URL, quotes, dates, context, etc.)
- **Pronunciation guide: enforcement workflow** — full table enforcement process, verification format, rules
- **Researcher: evidence chain format** — example documentation format for connecting sources

### Changed
- **Lyric-reviewer: homograph handling unified** — now verifies decisions from lyric-writer instead of independently re-determining pronunciation (fixes contradiction)
- **Lyric-reviewer: 13-point checklist** — added section length, rhyme scheme, density/pacing, verse-chorus echo checks (was 9)
- **Suno-engineer: parenthetical contradictions fixed** — removed instructions to use parentheticals in lyrics box (Suno sings them)
- **Suno-engineer: genre specificity guidance** — added 2-3 descriptor limit with "too much" anti-pattern example
- **Suno-engineer: album context lookup** — explicit instructions for finding album README from track path
- **Bass homograph standardized** — `bayss` (music) across lyric-writer, lyric-reviewer, pronunciation-specialist
- **New-album: documentary parsing** — documents both 2-arg and 3-arg formats, always asks about true-story status
- **Pronunciation-specialist: standard Override Support section** — restructured to match pattern used by other skills
- **Researcher: state cache + Glob approach** — replaced `find`/`cat` commands with state cache lookup per CLAUDE.md
- **Researcher: smart album detection** — checks for single in-progress album before asking user
- **Mastering-engineer: version-safe plugin detection** — `[0-9]*` pattern replaces `0.*` (works post-1.0)
- **Mastering-engineer: step renumbering** — 6 steps with new pre-flight check
- **Lyric-writer: trim strategy** — specific guidance on what to cut when sections exceed limits
- **Lyric-writer: pronunciation check split** — table enforcement elevated from parenthetical to explicit sub-item
- **Lyric-writer: twin verses example** — concrete before/after showing reworded vs developing V2
- **Track template: pronunciation enforcement note** — bold warning that table is mandatory checklist, not documentation
- **Track template: keeper marker documented** — explains ✓ in Generation Log Rating column
- **Album template: verification deduplication** — removed per-track table, points to track files as single source of truth
- **Album template: art filename convention** — documents expected filenames and locations for album art
- **Suno LUFS targets clarified** — renamed section, added note these are Suno outputs not mastering targets
- **Style Prompt terminology standardized** — consistent "Style Prompt" (content) vs "Style Box" (UI) across Suno docs
- **Test skill: section renumbering** — fixed duplicate section 9, renumbered 10-14
- **Resume: plugin root resolution** — explains how to find plugin directory when state cache needs rebuild
- **Clipboard: shell-safe example** — `printf '%s'` replaces `echo` for lyrics with special characters
- **Cross-references added** — release-procedures→distribution.md, error-recovery→mastering-workflow.md
- **Homograph drift prevention** — canonical source notes added to all 3 skills with homograph tables
- **Researcher sub-skills: override inheritance** — all 10 sub-skills now reference parent override preferences

## [0.36.0] - 2026-02-03

### Added
- **CI: CLAUDE.md size check** — validates CLAUDE.md stays under 40K characters (matches pre-commit hook)
- **CI: Skill frontmatter validation** — validates required fields (name, description, model) and model ID format pattern
- **Reference: status-tracking.md** — new reference doc for track/album status workflows (split from CLAUDE.md)

### Changed
- **CLAUDE.md trimmed** — reduced from 40.2K to 33.2K chars by moving skills table to SKILL_INDEX.md, lyrics checklist to lyric-writer SKILL.md, and status tracking to reference file
- **Model validation uses pattern** — skill frontmatter check now uses regex `^claude-(opus|sonnet|haiku)-\d+-\d+-\d{8}$` instead of hardcoded model IDs, allowing new model versions without updating checks
- **Plugin tests check SKILL_INDEX.md** — skill documentation test now checks SKILL_INDEX.md instead of CLAUDE.md (since skills table was moved there)

## [0.35.0] - 2026-02-03

### Added
- **`tools/shared/media_utils.py`** — shared module for color extraction, audio analysis, and ffmpeg helpers (extracted from promotion tools)
- **`tools/shared/text_utils.py`** — shared module for track naming utilities (extracted from sheet-music tools)

### Fixed
- **Bare `except:` clauses** — replaced 6 instances across sheet-music tools with specific exception types (`FileNotFoundError`, `subprocess.SubprocessError`, `TypeError`, etc.)
- **Unguarded `import yaml`** — added `try/except ImportError` with helpful message in `create_songbook.py` and `transcribe.py` to match project convention
- **Dead code** — removed unused `above_thresh`/`mask` duplication in `master_tracks.py:soft_clip()`, removed unused `BG_COLOR`/`WAVEFORM_COLOR` constants from promotion tools
- **Unused import** — removed `ProgressBar` import from `reference_master.py`
- **Resource leak** — `generate_album_sampler.py` now uses `Image.open()` as context manager
- **Broad exception handling** — narrowed `except Exception` to specific types in `create_songbook.py`

### Changed
- **Deduplicated promotion tools** — extracted 7 functions from `generate_promo_video.py` and `generate_album_sampler.py` into `tools/shared/media_utils.py` (-274 lines)
- **Deduplicated mastering tools** — `fix_dynamic_track.py` now imports `apply_eq` and `soft_clip` from `master_tracks.py` (gains safety guards: Nyquist, Q factor, stability checks)
- **Deduplicated sheet-music tools** — `strip_track_number` extracted to `tools/shared/text_utils.py`
- **PR template** — fixed Co-Authored-By from "Claude Sonnet 4.5" to "Claude Opus 4.5"
- **Skill counts** — fixed Sonnet (21→22) and Haiku (11→10) counts in `model-strategy.md` and `SKILL_INDEX.md`
- **README.md** — fixed stale `paths.yaml` reference to `~/.bitwize-music/config.yaml`, removed false `content_root` default claim
- **CONTRIBUTING.md** — added `SKILL_INDEX.md` and `model-strategy.md` to new skill checklist, clarified version bumps happen at release time

## [0.34.1] - 2026-02-03

### Fixed
- **Mastering summary crash** — `master_tracks.py` summary section crashed with `TypeError` when unpacking `(name, dict)` tuples as plain dicts
- **Album sampler crossfade offsets** — `concatenate_with_crossfade` hardcoded 12-second clip duration instead of using actual `--clip-duration` value, causing audio gaps/overlaps
- **ffprobe crash on failure** — `get_audio_duration` in promo video and album sampler tools now checks `returncode` before parsing output
- **CI expression injection** — moved all `${{ steps.*.outputs.* }}` interpolations in `auto-release.yml` and `model-updater.yml` into `env:` blocks to prevent shell injection via crafted inputs
- **Broad `git add -A` in model-updater** — replaced with targeted file additions to prevent accidental staging of temp files
- **`echo -e` portability** — replaced with `printf '%b'` in model-updater workflow
- **Release notes `echo` fragility** — replaced with `printf '%s\n'` in auto-release to avoid flag interpretation

## [0.34.0] - 2026-02-02

### Added
- **Python version matrix** — CI tests now run across Python 3.9, 3.10, 3.11, 3.12 with pip caching
- **Security scanning** — bandit static analysis in lint job, pip-audit dependency audit as new security job
- **Mastering tests in CI** — 47 mastering tests now run in the test pipeline alongside state/shared tests

### Fixed
- **Path traversal prevention** — upload_to_cloud.py and transcribe.py validate resolved paths stay within expected roots
- **Atomic state writes** — indexer.py uses tempfile + fsync to prevent corruption on crash
- **Python 3.9 compatibility** — `Path | None` → `Optional[Path]` in master_tracks.py
- **analyze_tracks divide-by-zero** — guard total_energy division in spectral analysis
- **Model updater safety** — validates model ID date format and skips downgrades

### Changed
- **Documentation sanitized** — replaced real album names with generic examples across 19 files

## [0.33.0] - 2026-02-01

### Added
- **Pronunciation Table Enforcement rule** — every entry in a track's Pronunciation Notes table must be applied as phonetic spelling in Suno lyrics. The table is a checklist of required substitutions, not documentation. Added full process, verification format, common failures, and anti-pattern examples to lyric-writer SKILL.md. Added to quality check #3 and pitfalls checklist.

## [0.32.0] - 2026-02-01

### Changed
- **CLAUDE.md deduplicated and trimmed to under 40KB** — consolidated 4 checkpoint sections into single table, slimmed Model Strategy to table with doc reference, condensed Lessons Learned, removed redundant sections (Quick Reference, Using Skills for Research, standalone Watch Your Rhymes, CORRECT APPROACH block). No information lost — all content consolidated or referenced elsewhere.

## [0.31.0] - 2026-02-01

### Changed
- **Verse-chorus echo check** replaces chorus lead-in rule — expanded from single-line check to full phrase deduplication. Now compares last 2 lines of every verse against first 2 lines of the chorus, flagging exact phrases, shared rhyme words, restated hooks, and shared signature imagery. Covers all verse-to-chorus and bridge-to-chorus transitions.

## [0.30.0] - 2026-02-01

### Added
- **No Invented Contractions rule** — Suno only handles standard pronoun/auxiliary contractions (they'd, wouldn't). Invented forms (signal'd, TV'd, network'd) will mispronounce or skip. Added to Pronunciation section, quality check #3, and pitfalls checklist.

## [0.29.0] - 2026-02-01

### Changed
- **Density/pacing reframed as Suno verse length limits** — replaced abstract syllable-density metrics with practical line counts per verse by genre and BPM. All 67 genre READMEs updated to `Density/pacing (Suno)` with default lines/verse, max safe limits, and BPM-aware guidance.
- **New BPM-aware fallback table** — universal verse length limits when genre README doesn't specify (4 lines at <80 BPM, 6 at 94-110, 6-8 at 110-140)
- **Default 4 lines/verse** unless genre and tempo justify more — shifted from permissive 8-line defaults to conservative 4-line baseline
- **Red flag: 8-line verse at BPM under 100** — now flagged as too dense for Suno
- **Streaming lyrics exception** documented — distributor text can have longer blocks but breaks must match Suno structure
- **Quality check #10 now hard fail** — trim or split any verse over the genre's Suno limit before presenting

## [0.28.0] - 2026-02-01

### Added
- **Genre-specific lyric density/pacing norms** — all 67 genre READMEs now include density character, syllables/line range, max topics/verse, typical BPM, and genre-specific pacing notes under Lyric Conventions
- **Chorus lead-in rule** — the line before a chorus must not duplicate the chorus hook, phrase, or rhyme word. Prevents flat chorus entries.
- **Quality checks expanded to 12** — #10 density/pacing (genre-aware), #11 chorus lead-in, #12 pitfalls checklist
- **4 new pitfalls checklist items** — verse too dense for BPM, too many proper nouns per verse, density mismatch with Musical Direction, chorus lead-in repeats chorus

### Changed
- **Lyric density architecture**: Genre READMEs now own density/pacing norms. SKILL.md keeps universal rules + quick-reference table by genre family.

## [0.27.0] - 2026-02-01

### Added
- **Lessons Learned Protocol** — 5-step process for turning production issues into preventive rules. When technical issues are discovered (pronunciation errors, rhyme violations, formatting problems), fix immediately, sweep the album, draft a rule, present to user, and log the lesson.

## [0.26.0] - 2026-02-01

### Added
- **Strict homograph handling for Suno pronunciation** — "context is clear" is never acceptable for homographs. Hard process: identify, ASK user (never guess), fix with phonetic spelling in Suno lyrics only, document in track pronunciation table.
- **Full homograph table** — live, read, lead, wound, close, bass, tear, wind with both pronunciations and phonetic spellings

## [0.25.0] - 2026-02-01

### Added
- **Genre-specific lyric conventions for all 67 genres** — research-backed rhyme schemes, verse structures, rhyme quality expectations, key rules, and anti-patterns added to every genre README under a new "Lyric Conventions" section
- **Genre-aware quality checks** — rhyme scheme check (#8) and flow check (#9) now verify conventions match the genre instead of enforcing hip-hop couplets universally
- **Quick-reference rhyme table in lyric-writer** — compact summary of all genre families' default schemes, replacing 190 lines of inlined genre tables with a pointer to genre READMEs

### Changed
- **Architecture**: Genre READMEs now own lyric conventions (rhyme, structure, rules). Lyric-writer SKILL.md keeps universal craft rules + quick-reference table.

## [0.24.0] - 2026-02-01

### Added
- **Section length guardrails by genre** — per-section line limits for 12 genre families (all 67 genres) to prevent Suno from rushing, compressing, or skipping lyrics. Covers Hip-Hop, Pop, Rock, Punk, Metal, Country/Folk, Electronic, Ambient, R&B, Jazz, Reggae, and Ballad.
- **Section length enforcement rules** — hard limits that must be trimmed before presenting drafts (hip-hop verse max 8 lines, any chorus max 6 lines, electronic verse max 6 lines, punk kept tight)
- **Section length added to quality checks** — now check #7 in both lyric-writer Automatic Quality Check and CLAUDE.md master workflow, plus added to Lyric Pitfalls Checklist

## [0.23.0] - 2026-01-31

### Added
- **Song length guidance for lyric writer** — word count targets by genre (150–250 pop, 200–350 rock/folk, 300–500 hip-hop), default structure (2 verses + chorus + bridge), and hard limits to prevent 800+ word songs that cause Suno to rush or skip sections
- **Length check added to lyric reviewer** — 9-point checklist (was 8-point) now includes word count validation with warning/critical severity levels
- **Suno best practices updated** — "Keep Lyrics Concise" note in Lyric Formatting section explaining shorter lyrics generate better results

## [0.22.0] - 2026-01-31

### Added
- **3 documentary/storytelling hip-hop deep-dives** — focused on narrative architecture, political documentary craft, and storytelling technique:
  - **Kendrick Lamar** — concept album mastery, vocal personas, jazz-funk-West Coast fusion, nonlinear timelines (GKMC, TPAB, DAMN., GNX)
  - **Run the Jewels** — El-P/Killer Mike dual-MC interplay, industrial political hip-hop, humor + protest balance (RTJ1-4)
  - **Immortal Technique** — politically charged documentary rap, "Dance with the Devil" narrative craft, fierce independence
- Hip-hop genre INDEX.md and README.md updated with all 3 artists

### Fixed
- **Removed artist/person names from Suno prompt keywords** in Ben Folds deep-dives — replaced "Ben Folds Five style", "Ben Folds solo style", "Ben Folds style", "Paul Buckmaster strings", "Nick Hornby storytelling", and "yMusic chamber rock" with descriptive style keywords (both deep-dive files and piano-rock INDEX.md)

## [0.21.1] - 2026-01-31

### Added
- **46 artist deep-dives** across 11 genres — comprehensive reference files (265-554 lines each) with overview, members, discography, musical analysis, Suno prompt keywords, and reference tracks:
  - **Punk** (8 new): Bad Religion, Blink-182, Descendents, Me First and the Gimme Gimmes, Mest, Propagandhi, Rancid, The Offspring
  - **Rock** (9): Fountains of Wayne, Hoobastank, Incubus, Jeff Buckley, Linkin Park, Phil Collins, Polaris, Toto, Weezer
  - **Country** (9): Alan Jackson, Dolly Parton, Garth Brooks, George Strait, Johnny Cash, Randy Travis, Sturgill Simpson, Tyler Childers, Willie Nelson
  - **Synthwave** (4): FM-84, GUNSHIP, The Midnight, Timecop1983
  - **Piano-Rock** (2): Billy Joel, Elton John
  - **Pop** (2): Carly Rae Jepsen, Taylor Swift
  - **Folk** (2): Israel Kamakawiwo'ole, Mumford & Sons
  - **Celtic-Punk** (1): Dropkick Murphys
  - **Electronic** (1): Daft Punk
  - **Hip-Hop** (1): Brock Berrigan
  - **Ambient** (1): Enya
- **11 genre INDEX.md files** — lightweight keyword indexes for all genres with deep-dives (rock, country, synthwave, electronic, folk, celtic-punk, hip-hop, ambient, pop); punk and piano-rock indexes expanded with new artists
- **Genre README updates** — Deep Dive and Keywords links added to artist tables across all 11 genres; Garth Brooks added to country README

## [0.21.0] - 2026-01-31

### Added
- **Artist reference indexes** — New `genres/[genre]/artists/INDEX.md` files for punk (127 lines) and piano-rock (84 lines) providing extracted Suno prompt keywords and reference tracks without loading full deep-dives (~2,900 lines across 6 files)
- **Lazy-loading guidance in CLAUDE.md** — New rule: read `artists/INDEX.md` first for Suno keywords; only read full deep-dive when detailed history/analysis is needed

### Changed
- **Genre README Artists tables** — Deep Dive column now includes `[Keywords]` shortcut links to INDEX.md alongside existing deep-dive links (punk, piano-rock)
- **CLAUDE.md directory structure** — Added `INDEX.md` to both plugin and content directory trees; updated deep-dive creation rule to require INDEX.md updates

## [0.20.2] - 2026-01-31

### Added
- **Genre overview files** — New genre READMEs for piano-rock, piano-pop, and singer-songwriter (67 genres total, up from 64)
- **Artist deep-dive references** — 6 comprehensive artist files in `genres/[genre]/artists/`:
  - `punk/artists/nofx.md` — Members, 15 albums, Fat Wreck Chords, farewell tour, Suno keywords
  - `punk/artists/lagwagon.md` — Members, 9 albums, Derrick Plourde, Tony Sly, Joey Cape solo work
  - `punk/artists/green-day.md` — Members, 14 albums, Gilman Street, American Idiot phenomenon
  - `punk/artists/masked-intruder.md` — Anonymous concept, 3 albums, gimmick analysis
  - `piano-rock/artists/ben-folds-five.md` — Members, 4 albums, Chapel Hill scene, production
  - `piano-rock/artists/ben-folds-solo.md` — 8 solo albums, orchestral work, collaborations

### Changed
- **Genre directory structure** — Artist deep-dives now live in `genres/[genre]/artists/` subdirectories instead of alongside genre READMEs
- **Genre README Artists tables** — Added "Deep Dive" column with links to artist reference files (punk, piano-rock)
- **CLAUDE.md** — Added `genres/` to plugin root directory tree, documented `artists/` subdirectory pattern, added deep-dive linking rule to Key Rules

## [0.20.1] - 2026-01-30

### Changed
- **README** — Added Claude Code Max plan ($200/month) recommendation callout for new users

## [0.20.0] - 2026-01-29

### Added
- **Python logging module** across all 15 tool files — `tools/shared/logging_config.py` with `ColorFormatter` (TTY-aware colored output via `Colors` class) and `setup_logging()`. Errors/warnings/status go to stderr via `logger`, formatted tables and data summaries stay as `print()`. `--verbose`/`--quiet` CLI flags added where argparse exists.
- **Progress indicators** — `tools/shared/progress.py` with `ProgressBar` class (TTY-aware █/░ bar). Added to 7 batch-processing tools: `master_tracks.py`, `analyze_tracks.py`, `reference_master.py`, `upload_to_cloud.py`, `generate_promo_video.py`, `generate_album_sampler.py`, `transcribe.py`.
- **Retry logic for cloud uploads** — `retry_upload()` in `upload_to_cloud.py` with exponential backoff (1s/2s/4s), `--retries` CLI arg (default: 3). Retries on `ClientError` (except 403/404), `ConnectionError`, `Timeout`.
- **Concurrent processing** — `-j`/`--jobs` CLI arg in 4 tools: `master_tracks.py` and `analyze_tracks.py` (`ProcessPoolExecutor`), `transcribe.py` and `generate_promo_video.py` (`ThreadPoolExecutor`). Default: 1 (sequential), 0 = auto (CPU count).
- **State cache cleanup command** — `python tools/state/indexer.py cleanup` removes albums from cache whose paths no longer exist on disk. Supports `--dry-run`.
- **New shared modules** — `tools/shared/logging_config.py`, `tools/shared/progress.py`, `tools/shared/__init__.py`
- **Test coverage improvements** — 180 tests (up from 137), 91% coverage. New test files: `test_logging_config.py` (13 tests), `test_progress.py` (14 tests). New test classes in `test_indexer.py`: `TestCmdCleanup`, `TestCmdRebuild`, `TestCmdValidate`, `TestCmdShow`, `TestCmdUpdate`. Edge case tests added to `test_parsers.py`.
- **Dev tooling** — `requirements-test.txt` (pytest, pyyaml, ruff, pytest-cov), `ruff.toml` config, CI workflow updated with test and lint jobs

## [0.19.3] - 2026-01-29

### Changed
- **Venv-first messaging** across all tools and skills — error messages in `upload_to_cloud.py` and `generate_promo_video.py` now show venv setup commands instead of bare `pip install`. Cloud-uploader and promo-director SKILL.md docs updated to present venv as the primary (not alternative) approach.

## [0.19.2] - 2026-01-29

### Fixed
- **Cloud upload album discovery** in `upload_to_cloud.py` — added recursive glob fallback when standard flat path (`{audio_root}/{artist}/{album}`) doesn't exist. Handles audio directories that mirror the content structure with genre folders (e.g., `artists/bitwize/albums/rock/shell-no/`). Reports all checked paths on failure.

## [0.19.1] - 2026-01-29

### Fixed
- **Cloud upload path resolution** in `upload_to_cloud.py` — when `--audio-root` override already includes the artist path, the script no longer doubles it (e.g., `.../bitwize/albums/rock/bitwize/shell-no`). Now tries standard path first, then falls back to direct `{override}/{album}` lookup.

## [0.19.0] - 2026-01-29

### Added
- **Per-feature requirements files** - Install only what you need:
  - `requirements-mastering.txt` - Audio mastering (matchering, pyloudnorm, scipy, numpy, soundfile)
  - `requirements-promo.txt` - Promo videos (pillow, librosa)
  - `requirements-sheet-music.txt` - Sheet music (pypdf, reportlab, pyyaml)
  - `requirements.txt` - Cloud uploads (boto3)
  - `requirements-research.txt` - Document hunting (playwright)
- **Model tier consistency test** in `run_tests.py` - Validates SKILL.md model assignments match model-strategy.md, reports tier distribution, detects `disable-model-invocation` flags
- **Cross-references** added to reference docs (v5-best-practices, distribution, pronunciation-guide, checkpoint-scripts) linking related skills and docs
- **Task-oriented guide table** in `reference/suno/README.md` - "When to Use Which Guide" quick lookup

### Fixed
- **Security: ffmpeg command injection** in `generate_promo_video.py` - Switched from `text=` (injectable via title/artist strings) to `textfile=` parameter with temp files
- **Silent audio crash** in `master_tracks.py` - Added guards for `-inf` LUFS from silent/near-silent audio, skips instead of crashing
- **Case-insensitive WAV discovery** in `master_tracks.py` - Now finds `.WAV` and `.wav` files
- **PIL file handle leak** in `generate_promo_video.py` - `Image.open()` now uses `with` block
- **Shallow copy bug** in `indexer.py` - `existing_state.copy()` replaced with `copy.deepcopy()` to prevent nested dict mutation
- **Race conditions** in `indexer.py` - Added `try/except OSError` around 4 `stat()` calls where files could be deleted between glob and stat
- **Whitespace in Suno Link parsing** in `parsers.py` - Added `.strip()` and en-dash to exclusion list
- **Sources Verified false positive** in `parsers.py` - Reordered matching to check "pending" before "verified", preventing "NOT verified" matching as verified
- **Model tier test substring matching** in `run_tests.py` - Used exact `### heading` regex instead of substring match (prevented "about" matching in prose, "researcher" matching "researchers-legal")

### Changed
- **SKILL_INDEX.md** realigned all 38 skills with model-strategy.md (added missing Opus/Sonnet skills, corrected tier assignments)
- **Album template** (`templates/album.md`) - Replaced hardcoded artist text with generic guidance, renamed distributor heading
- Removed `disable-model-invocation: true` from `release-director` and `skill-model-updater` skills
- Test runner timeout now configurable via `BITWIZE_TEST_TIMEOUT` env var (default: 60s)
- Removed redundant `import re` in `run_tests.py`

## [0.18.0] - 2026-01-29

### Added
- **State cache layer** (`tools/state/`) - JSON index of all project state for fast session startup
  - `parsers.py` - Markdown parsing functions for album READMEs, track files, IDEAS.md
  - `indexer.py` - CLI tool with `rebuild`, `update`, `validate`, `show`, `session` commands
  - State cached at `~/.bitwize-music/cache/state.json` (always rebuildable from markdown)
  - Schema versioning with migration chain for plugin upgrades
  - Atomic writes for crash safety
  - Incremental updates (only re-parse files with newer mtime)
- **`session` CLI command** for `indexer.py` - Update session context in state.json
  - `--album`, `--track`, `--phase` to set context
  - `--add-action` to append pending actions
  - `--clear` to reset session data
- **`__main__.py`** for `tools/state/` - Enables `python3 -m tools.state` invocation
- **State cache tests** - 57 tests across parsers and indexer
  - `test_parsers.py` - 29 unit tests including flexible column tracklist parsing
  - `test_indexer.py` - 28 integration tests for build, update, validate, migrate, session, script invocation
  - Test fixtures for album README, track files, and IDEAS.md
  - Regression tests: script invocation (`python3 tools/state/indexer.py --help`), module invocation, package invocation
- **State test category** in test runner (`/bitwize-music:test state`)
  - Validates state tool files exist
  - Checks schema version constant
  - Runs parser unit tests as subprocess

### Changed
- Session Start in CLAUDE.md now uses state cache instead of scanning markdown files
  - Reduces startup from 50-220 file reads to 2-3 file reads
  - Falls back to full rebuild if cache missing, corrupted, or schema changed
  - Shows last session context (album, phase, pending actions)
- Resume skill now reads from state cache instead of glob + individual file reads
  - Reduces per-invocation from 15-50 file reads to 1-2 file reads
  - Updates session context via `indexer.py session` command
  - Includes optional staleness check with incremental update
- CLAUDE.md "Finding Albums" section now references state cache as primary lookup before Glob fallback
- CLAUDE.md "Resuming Work" section updated to describe state cache workflow
- CLAUDE.md Session Start step 2 uses full `python3 {plugin_root}/tools/state/indexer.py` paths consistently

### Fixed
- **Critical**: `indexer.py` now runnable as `python3 tools/state/indexer.py` (was failing with `ModuleNotFoundError`)
  - Added `sys.path` fixup at top of file (same pattern as test files)
  - CLAUDE.md and resume SKILL.md both documented the broken form
- `documents_root` default now derives from `content_root` instead of CWD
  - `audio_root` default also derives from `content_root`
  - Prevents wrong paths when running from a different directory
- Tracklist parser now handles variable column counts (3+ columns)
  - Previously required exactly 5 columns; silently returned 0 tracks if template changed
  - Extracts track number (first col), title (second col), status (last col)
  - Emits warning if Tracklist section exists but no rows matched
- `state.session` was dead code — no write mechanism existed
  - Added `session` CLI command to `indexer.py`
  - Resume skill step 5 now calls `indexer.py session` to persist context

## [0.17.1] - 2026-01-28

### Changed
- Revised model assignments for 6 skills with comprehensive rationale for all 38 skills
  - Promoted to Opus: album-conceptualizer, lyric-reviewer
  - Promoted to Sonnet: pronunciation-specialist, explicit-checker
  - Moved to Haiku: skill-model-updater, test
- Simplified skill-model-updater to auto-detect tiers from existing model fields instead of maintaining a hardcoded tier list
- Updated model-strategy.md with per-skill rationale and decision framework

## [0.17.0] - 2026-01-28

### Added
- **Test automation runner** (`tools/tests/run_tests.py`) - Validates skills, templates, references, links, terminology, consistency
- **Genre INDEX.md** - Searchable, categorized guide to all 64 genres with quick reference tables
- **Quick-start guides** (`reference/quick-start/`) - first-album.md, true-story-album.md, bulk-releases.md
- **Override documentation** (`reference/overrides/`) - how-to-customize.md, override-index.md
- **Release documentation** (`reference/release/`) - platform-comparison.md, distributor-guide.md, metadata-by-platform.md, rights-and-claims.md
- **Cross-platform guides** (`reference/cross-platform/`) - wsl-setup-guide.md, tool-compatibility-matrix.md
- **Model strategy documentation** (`reference/model-strategy.md`) - Complete rationale for skill model assignments
- **Terminology glossary** (`reference/terminology.md`) - Standardized definitions for all key terms
- **Skill index** (`reference/SKILL_INDEX.md`) - Decision tree, prerequisites, skill sequences
- **Mastering reference docs** - genre-specific-presets.md, loudness-measurement.md, mastering-checklist.md
- **Sheet music reference docs** - genre-recommendations.md, troubleshooting.md
- **Workflow docs** - importing-audio.md
- **Skill supporting docs** for clipboard, album-ideas, configure, help, about
- **Researcher skill guides** for all 10 specialized researchers (legal, gov, journalism, security, financial, historical, biographical, tech, primary-source, verifier)

### Changed
- Expanded error-recovery.md from 52 to 316 lines with 12 detailed recovery scenarios
- Enhanced config.example.yaml with comprehensive inline documentation and platform examples
- Updated CLAUDE.md model strategy section to reference new documentation

## [0.16.0] - 2026-01-28

### Added
- Enhanced all 64 genre documentation files to Gold standard quality
  - 3+ paragraph overviews with historical context and scene development
  - 8+ subgenres with detailed descriptions and reference artists
  - 12+ artists with filled tables (no placeholder entries)
  - 12+ reference tracks with rich contextual descriptions
  - Comprehensive Suno prompt keywords for AI music generation
  - Coverage spans origins through modern revival movements

## [0.15.0] - 2026-01-28

### Added
- Example override files in `config/overrides.example/` for all 11 documented overrides
  - CLAUDE.md, pronunciation-guide.md, suno-preferences.md, lyric-writing-guide.md
  - explicit-words.md, mastering-presets.yaml, album-planning-guide.md
  - album-art-preferences.md, research-preferences.md, release-preferences.md
  - sheet-music-preferences.md
- `requirements:` field in skill frontmatter for skills with external dependencies
  - mastering-engineer, promo-director, document-hunter, cloud-uploader
- Test to verify skills with external deps have requirements field
- Root `requirements.txt` consolidating all Python dependencies by feature (mastering, promo videos, sheet music, cloud uploads, document hunting)
- Regression test for README skill count matching actual skill directory count
- Regression test to prevent accidental skill.json files (standard is SKILL.md)
- Genre validation test to catch mismatched genre references
- "What's New" section in README showing recent version highlights

### Changed
- Replaced emojis with text indicators in all logging output ([OK], [FAIL], [WARN])
  - Python tools: generate_promo_video.py, validate_help_completeness.py, transcribe.py, create_songbook.py
  - GitHub workflows: test.yml, model-updater.yml, auto-release.yml, version-sync.yml
- Standardized co-author line in CONTRIBUTING.md to use "Claude Opus 4.5" (was inconsistently using Sonnet)

### Fixed
- README.md skill count corrected from 32 to 38
- Removed accidental `skill.json` from resume skill (SKILL.md is the standard format)

## [0.14.3] - 2026-01-27

### Changed
- Promo video titles now use Title Case instead of ALL CAPS when derived from filenames
- Album sampler now saved in `promo_videos/` folder alongside track promos (was at album root)
- Cloud uploader puts all promos in same folder (`{artist}/{album}/promos/`)

### Fixed
- Cloud uploader documentation clarifies flat path structure (no genre folder in cloud paths)
- Config README updated with all current settings (promotion, sheet_music, cloud sections)

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
