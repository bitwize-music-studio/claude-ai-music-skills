---
name: test
description: Run automated tests to validate plugin integrity
argument-hint: [all | config | skills | templates | workflow | suno | research | mastering | sheet-music | release | consistency | terminology | behavior | quality]
model: claude-sonnet-4-5-20250929
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

## Your Task

**Input**: $ARGUMENTS

Run automated tests to validate plugin integrity. Execute each test methodically and report results clearly.

**Default**: Run all tests if no argument provided.

---

# Plugin Test Suite

You are the plugin's automated test runner. Execute each test, track pass/fail, and report actionable results.

## Output Format

```
════════════════════════════════════════
CATEGORY: Test Category Name
════════════════════════════════════════

[PASS] Test name
[FAIL] Test name
       → Problem: what's wrong
       → File: path/to/file:line
       → Fix: specific fix instruction

────────────────────────────────────────
Category: X passed, Y failed
────────────────────────────────────────
```

At the end:
```
════════════════════════════════════════
FINAL RESULTS
════════════════════════════════════════
config:       X passed, Y failed
skills:       X passed, Y failed
templates:    X passed, Y failed
...
────────────────────────────────────────
TOTAL:        X passed, Y failed, Z skipped
════════════════════════════════════════
```

---

# TEST CATEGORIES

## 1. CONFIG TESTS (`/test config`)

Tests for the configuration system.

### TEST: config.example.yaml exists
```
Glob: config/config.example.yaml
```

### TEST: config.example.yaml is valid YAML
```bash
python3 -c "import yaml; yaml.safe_load(open('config/config.example.yaml'))"
```

### TEST: config.example.yaml has all required sections
Read config/config.example.yaml and verify these top-level keys exist:
- `artist:`
- `paths:`
- `urls:`
- `generation:`

### TEST: config.example.yaml has all required fields
Verify these fields exist:
- `artist.name`
- `paths.content_root`
- `paths.audio_root`
- `paths.documents_root`
- `generation.service`

### TEST: config.example.yaml has all optional fields documented
Verify these optional fields exist and are documented:
- `paths.overrides` (overrides directory for skill customization)
- `paths.ideas_file` (album ideas tracking file)

### TEST: config.example.yaml has inline examples (quick win #9)
Read config/config.example.yaml.
Verify it includes commented examples for:
- artist.name (examples of artist names)
- artist.genres (examples of genre choices)
- artist.style (examples of style descriptions)
- paths.content_root (path pattern examples)
- paths.audio_root (path pattern examples, notes about writability)
- paths.documents_root (examples, use case notes)
- paths.overrides (examples, override file examples)
- paths.ideas_file (location examples)
- urls section (platform URL examples including Apple Music, Twitter)
- generation.service (explanation of current vs future support)
- sheet_music section (options explained with context)
Verify inline comments use "Examples:" or "Example:" format

### TEST: config/README.md exists and documents all settings
1. Read config/README.md
2. Verify it documents each setting from config.example.yaml
3. Check Settings Reference table is complete

### TEST: Config location consistently documented as ~/.bitwize-music
Search these files for config path references:
- CLAUDE.md
- README.md
- config/README.md
- skills/configure/SKILL.md
- skills/tutorial/SKILL.md

All should reference `~/.bitwize-music/config.yaml` or `~/.bitwize-music/`

### TEST: Config must be read before path operations (regression)
Read CLAUDE.md "When to Read Config" section.
Verify it includes:
1. "ALWAYS read" instruction before moving/creating files
2. "ALWAYS read" instruction before resolving paths
3. "Do not assume or remember values" instruction
4. Reference to context summarization as reason to re-read

This test was added after paths were incorrectly resolved because config values were assumed instead of read.

### TEST: No references to old config files
Search entire repo (excluding .git/) for deprecated references:
- `config/paths.yaml`
- `config/artist.md`
- `paths.example.yaml`
- `artist.example.md`

---

## 2. SKILLS TESTS (`/test skills`)

Tests for skill definitions and documentation.

### TEST: All skill directories have SKILL.md
```bash
for dir in skills/*/; do
  [[ -f "${dir}SKILL.md" ]] || echo "MISSING: ${dir}SKILL.md"
done
```

### TEST: All skills have valid YAML frontmatter
For each skills/*/SKILL.md:
1. First line is `---`
2. Has closing `---`
3. Contains required fields

### TEST: All skills have required frontmatter fields
Each SKILL.md must have:
- `name:` (required)
- `description:` (required)
- `model:` (required)
- `allowed-tools:` (required, must be array)

### TEST: All model references are valid
Valid models:
- `claude-sonnet-4-5-20250929`
- `claude-opus-4-5-20251101`
- `claude-haiku-4-5-20251001`

### TEST: Skill count in README matches actual
1. Count: `ls -1 skills/ | wc -l`
2. Find in README: "collection of **XX specialized skills**"
3. Must match

### TEST: All skills documented in CLAUDE.md
Extract skill names from skills/ directory.
Each must appear in CLAUDE.md skill table (except researcher sub-skills which are documented separately).

### TEST: All skills documented in README.md
Each skill must appear in README.md skill tables.

### TEST: /resume skill documented in README (quick win #1)
Read README.md Skills Reference section.
Verify `/bitwize-music:resume` appears in the Setup & Maintenance table.
Verify description includes: "Resume work on an album - finds album, shows status and next steps"

### TEST: /configure skill has all commands
Read skills/configure/SKILL.md and verify these are documented:
- `setup`
- `edit`
- `show`
- `validate`
- `reset`

### TEST: /test skill covers all categories
This skill should document tests for: config, skills, templates, workflow, suno, research, mastering, sheet-music, release, consistency, terminology, behavior, quality

### TEST: /album-ideas skill exists
```
Glob: skills/album-ideas/SKILL.md
```

### TEST: /album-ideas skill has all commands documented
Read skills/album-ideas/SKILL.md and verify these commands are documented:
- `list` - Show all album ideas
- `add` - Add new album idea
- `remove` - Remove album idea
- `status` - Update idea status
- `show` - Show details for specific idea
- `edit` - Edit existing idea

### TEST: /clipboard skill exists
```
Glob: skills/clipboard/SKILL.md
```

### TEST: /clipboard skill has platform detection
Read skills/clipboard/SKILL.md and verify:
1. Documents platform detection (macOS, Linux, WSL)
2. Lists clipboard tools: pbcopy, xclip, xsel, clip.exe
3. Has error handling for missing clipboard utility
4. Provides install instructions for each platform

### TEST: /clipboard skill has all content types documented
Read skills/clipboard/SKILL.md and verify these content types are documented:
- `lyrics` - Suno Lyrics Box
- `style` - Suno Style Box
- `streaming-lyrics` - Streaming Lyrics for distributors
- `all` - Combined Style + Lyrics

### TEST: /clipboard skill has correct argument format
Read skills/clipboard/SKILL.md and verify:
1. `argument-hint` matches format: `<content-type> <album-name> <track-number>`
2. Examples show correct usage pattern
3. Error handling for missing arguments is documented

### TEST: Override support documented in skills
Verify these skills have "Override Support" section in their SKILL.md:
- `skills/explicit-checker/SKILL.md` → loads `explicit-words.md`
- `skills/lyric-writer/SKILL.md` → loads `lyric-writing-guide.md`
- `skills/suno-engineer/SKILL.md` → loads `suno-preferences.md`
- `skills/mastering-engineer/SKILL.md` → loads `mastering-presets.yaml`
- `skills/album-conceptualizer/SKILL.md` → loads `album-planning-guide.md`
- `skills/pronunciation-specialist/SKILL.md` → loads `pronunciation-guide.md`
- `skills/album-art-director/SKILL.md` → loads `album-art-preferences.md`
- `skills/researcher/SKILL.md` → loads `research-preferences.md`
- `skills/release-director/SKILL.md` → loads `release-preferences.md`
- `skills/sheet-music-publisher/SKILL.md` → loads `sheet-music-preferences.md`

Each should have:
1. Section titled "## Override Support"
2. Subsection "### Loading Override" with steps
3. Subsection "### How to Use Override" with behavior
4. Reference to loading override in "Remember" section

---

## 3. TEMPLATES TESTS (`/test templates`)

Tests for template files.

### TEST: All required templates exist
These files must exist:
- `templates/album.md`
- `templates/track.md`
- `templates/artist.md`
- `templates/research.md`
- `templates/sources.md`

### TEST: Templates referenced in CLAUDE.md exist
Search CLAUDE.md for `/templates/` references.
Each referenced template must exist.

### TEST: IDEAS.md template uses consistent status values (quick win #4)
Read templates/ideas.md.
Verify **Status** field uses format: "Pending | In Progress | Complete"
Should NOT use: "Idea | Ready to Plan | In Progress"
Verify it includes status explanations (Pending, In Progress, Complete)

### TEST: album.md template has required sections
Read templates/album.md and verify it has:
- YAML frontmatter skeleton
- Concept section
- Tracklist section
- Production Notes section
- Album Art section

### TEST: track.md template has required sections
Read templates/track.md and verify it has:
- Status field
- Suno Inputs section (Style Box, Lyrics Box)
- Generation Log section
- Streaming Lyrics section

### TEST: sources.md template has Downloaded Documents section
Read templates/sources.md and verify "Downloaded Documents" section exists.

---

## 4. WORKFLOW TESTS (`/test workflow`)

Tests for album creation workflow documentation.

### TEST: 7 planning phases documented in CLAUDE.md
Read CLAUDE.md "Building a New Album" section.
Verify all 7 phases are documented:
1. Foundation
2. Concept Deep Dive
3. Sonic Direction
4. Structure Planning
5. Album Art
6. Practical Details
7. Confirmation

### TEST: Album status values documented
Verify CLAUDE.md documents these album statuses:
- Concept
- Research Complete
- Sources Verified
- In Progress
- Complete
- Released

### TEST: Track status values documented
Verify CLAUDE.md documents these track statuses:
- Not Started
- Sources Pending
- Sources Verified
- In Progress
- Generated
- Final

### TEST: Directory structure documented
Verify CLAUDE.md documents the directory structure:
- `{content_root}/artists/[artist]/albums/[genre]/[album]/`
- `{audio_root}/[artist]/[album]/`
- `{documents_root}/[artist]/[album]/`

### TEST: Audio path structure has concrete example (regression)
Read CLAUDE.md "Mirrored structure" section.
Verify it includes:
1. A concrete example with actual paths (e.g., `~/bitwize-music/audio/bitwize/shell-no/`)
2. The phrase "includes artist!" to emphasize artist folder is required
3. A "Common mistake" warning about missing artist folder

This test was added after a bug where audio files were placed at `{audio_root}/[album]/` instead of `{audio_root}/[artist]/[album]/`.

### TEST: Importing external audio files documented (regression)
Read CLAUDE.md "Importing External Audio Files" section.
Verify it includes:
1. Trigger for audio/WAV files in Downloads or external locations
2. Explicit instruction that path "MUST include artist folder"
3. Example showing correct path: `{audio_root}/[artist]/[album]/`
4. "CRITICAL" warning about including artist folder

This test was added after audio files were repeatedly moved to `{audio_root}/[album]/` without the artist folder.

### TEST: Session start procedure documented
Read CLAUDE.md "Session Start" section.
Verify step 1 is loading configuration.
Verify step 1b is loading overrides (if present).
Verify step 3 is checking album ideas file.
Verify it mentions /configure when config missing.
Verify it mentions /bitwize-music:album-ideas for detailed ideas list.

### TEST: Session startup contextual tips system documented
Read CLAUDE.md "Session Start" section after the 6 status check steps.
Verify section exists: "Show contextual tips based on detected state:"
Verify all conditional tip categories are documented:
- If no albums exist → tutorial tip
- If IDEAS.md has content → album-ideas tip
- If in-progress albums exist → resume tip
- If overrides don't exist → customization tip
- If overrides loaded → confirmation message
- If pending source verifications exist → verification warning

### TEST: Session startup general productivity tips exist
Read CLAUDE.md "Session Start" section.
Verify section exists: "Always show one general productivity tip (rotate randomly):"
Verify it contains at least 4 different productivity tips.
Verify tips reference actual skills (e.g., /bitwize-music:resume, /bitwize-music:researcher).

### TEST: Session startup ends with question
Read CLAUDE.md "Session Start" section.
Verify final instruction says: "Finally, ask:" followed by "What would you like to work on?"

### TEST: Contextual tips use correct skill commands
Read CLAUDE.md session startup tips section.
Verify all skill references use correct format:
- `/bitwize-music:tutorial` (not /tutorial)
- `/bitwize-music:album-ideas` (not /album-ideas)
- `/bitwize-music:resume` (not /resume)
- `/bitwize-music:researcher` (not /researcher)
- `/bitwize-music:pronunciation-specialist` (not /pronunciation-specialist)
- `/bitwize-music:clipboard` (not /clipboard)

### TEST: Contextual tips reference overrides path variable
Read CLAUDE.md session startup tips section.
Verify overrides tips use `{overrides}` path variable (not hardcoded path).

### TEST: Checkpoints documented
Verify these checkpoints exist in CLAUDE.md:
- Ready to Generate Checkpoint
- Album Generation Complete Checkpoint
- Ready to Master Checkpoint
- Ready to Release Checkpoint

---

## 5. SUNO TESTS (`/test suno`)

Tests for Suno integration documentation.

### TEST: Suno reference directory exists
```
Glob: reference/suno/
```

### TEST: Required Suno reference files exist
These must exist:
- `reference/suno/v5-best-practices.md`
- `reference/suno/pronunciation-guide.md`
- `reference/suno/tips-and-tricks.md`
- `reference/suno/structure-tags.md`
- `reference/suno/voice-tags.md`
- `reference/suno/instrumental-tags.md`
- `reference/suno/genre-list.md`

### TEST: /suno-engineer skill exists
```
Glob: skills/suno-engineer/SKILL.md
```

### TEST: /pronunciation-specialist skill exists
```
Glob: skills/pronunciation-specialist/SKILL.md
```

### TEST: Pronunciation guide has phonetic examples
Read reference/suno/pronunciation-guide.md.
Verify it has examples for:
- Names
- Acronyms
- Tech terms
- Homographs

### TEST: Suno pronunciation guide has cross-references (quick win #10)
Read reference/suno/pronunciation-guide.md.
Verify "## Related Skills" section exists with:
- /bitwize-music:pronunciation-specialist reference
- /bitwize-music:lyric-writer reference
- /bitwize-music:lyric-reviewer reference
Verify "## See Also" section exists with:
- /reference/suno/v5-best-practices.md reference
- /reference/suno/structure-tags.md reference
- /skills/lyric-writer/SKILL.md reference
- /skills/pronunciation-specialist/SKILL.md reference

### TEST: Suno v5-best-practices has cross-references (quick win #10)
Read reference/suno/v5-best-practices.md.
Verify "## Related Skills" section exists with:
- /bitwize-music:suno-engineer reference
- /bitwize-music:lyric-writer reference
- /bitwize-music:lyric-reviewer reference
Verify "## See Also" section exists with:
- /reference/suno/pronunciation-guide.md reference
- /reference/suno/structure-tags.md reference
- /reference/suno/genre-list.md reference
- /reference/suno/voice-tags.md reference
- /reference/suno/tips-and-tricks.md reference
- /skills/suno-engineer/SKILL.md reference

### TEST: Suno structure-tags has cross-references (quick win #10)
Read reference/suno/structure-tags.md.
Verify "## Related Skills" section exists with:
- /bitwize-music:lyric-writer reference
- /bitwize-music:suno-engineer reference
- /bitwize-music:lyric-reviewer reference
Verify "## See Also" section exists with:
- /reference/suno/v5-best-practices.md reference
- /reference/suno/pronunciation-guide.md reference
- /reference/suno/voice-tags.md reference
- /skills/lyric-writer/SKILL.md reference

### TEST: Mastering workflow has cross-references (quick win #10)
Read reference/mastering/mastering-workflow.md.
Verify "## Related Skills" section exists with:
- /bitwize-music:mastering-engineer reference
- /bitwize-music:release-director reference
Verify "## See Also" section exists with:
- /tools/mastering/ scripts listed
- /reference/workflows/release-procedures.md reference
- /skills/mastering-engineer/SKILL.md reference

### TEST: Explicit content word list documented
Read CLAUDE.md "Explicit Content Guidelines" section.
Verify explicit words table exists.

### TEST: /explicit-checker skill exists
```
Glob: skills/explicit-checker/SKILL.md
```

### TEST: Artist/band name warning documented
Read skills/suno-engineer/SKILL.md.
Verify it has "Artist/Band Name Warning" section that:
- States NEVER use artist/band names
- Lists examples of forbidden names
- Provides style description alternatives

### TEST: CLAUDE.md mentions artist names forbidden
Verify CLAUDE.md Suno Reference section mentions artist names are forbidden.

### TEST: No band names in Suno example prompts (regression)
Search skills/suno-engineer/SKILL.md for common band/artist name patterns in example prompts.
Common violations to check for:
- "[Band] style" (e.g., "NOFX style", "Metallica style")
- "sounds like [Band]"
- Direct band name references

If found, report as FAIL with:
→ Problem: Band name in example prompt violates Suno policy
→ File: skills/suno-engineer/SKILL.md:[line]
→ Fix: Replace with descriptive style terms (e.g., "NOFX style" → "melodic punk rock, fast-paced, political, skate punk")

This test was added after band names appeared in example style prompts.

### TEST: Lyrics box warning documented
Read skills/suno-engineer/SKILL.md.
Verify it has "Lyrics Box Warning" section that:
- States Suno literally sings everything in lyrics box
- Lists what NOT to put (parentheticals, stage directions)
- Shows correct format for instrumental sections

---

## 6. RESEARCH TESTS (`/test research`)

Tests for research workflow.

### TEST: /researcher skill exists
```
Glob: skills/researcher/SKILL.md
```

### TEST: All researcher sub-skills exist
These must exist:
- `skills/researchers-legal/SKILL.md`
- `skills/researchers-gov/SKILL.md`
- `skills/researchers-tech/SKILL.md`
- `skills/researchers-journalism/SKILL.md`
- `skills/researchers-security/SKILL.md`
- `skills/researchers-financial/SKILL.md`
- `skills/researchers-historical/SKILL.md`
- `skills/researchers-biographical/SKILL.md`
- `skills/researchers-primary-source/SKILL.md`
- `skills/researchers-verifier/SKILL.md`

### TEST: /document-hunter skill exists
```
Glob: skills/document-hunter/SKILL.md
```

### TEST: Source verification workflow documented
Read CLAUDE.md "Sources & Verification" section.
Verify it documents:
- Source hierarchy
- Track status workflow (Pending → Verified)
- Human verification handoff triggers

### TEST: documents_root path documented
Verify CLAUDE.md and config docs explain `{documents_root}` path variable.

### TEST: Research files must be saved to album directory (regression)
Read CLAUDE.md "Sources & Verification" section.
Verify it includes:
1. Rule about saving RESEARCH.md and SOURCES.md to album directory
2. Path format: `{content_root}/artists/{artist}/albums/{genre}/{album}/`
3. "Never save to current working directory" warning

Read skills/researcher/SKILL.md.
Verify it includes:
1. "Determine Album Location (REQUIRED)" section
2. Instructions to read config first
3. Instructions to find album directory
4. "CRITICAL" warning about never saving to current working directory

This test was added after research files were saved to /tmp or working directory instead of album folder.

---

## 7. MASTERING TESTS (`/test mastering`)

Tests for audio mastering workflow.

### TEST: Mastering tools directory exists
```
Glob: tools/mastering/
```

### TEST: Required mastering scripts exist
These must exist:
- `tools/mastering/analyze_tracks.py`
- `tools/mastering/master_tracks.py`

### TEST: Mastering workflow documentation exists
```
Glob: reference/mastering/mastering-workflow.md
```

### TEST: /mastering-engineer skill exists
```
Glob: skills/mastering-engineer/SKILL.md
```

### TEST: /mastering-engineer skill uses dynamic plugin path (regression)
Read skills/mastering-engineer/SKILL.md.
Verify it includes:
1. "Important: Script Location" section with CRITICAL warning
2. Dynamic plugin directory finding using find command with sort -V
3. All script invocations use "$PLUGIN_DIR/tools/mastering/script.py" format
4. Scripts receive audio path as argument (not run from audio directory)
5. NO instructions to copy scripts to audio folders
6. "Common Mistakes" section with subsection "Don't: Copy scripts to audio folders"
7. "Common Mistakes" section with subsection "Don't: Hardcode plugin version number"

This test was added after a bug where scripts were copied to audio folders instead of being run from plugin directory, breaking after plugin updates.

### TEST: /import-audio skill exists
```
Glob: skills/import-audio/SKILL.md
```

### TEST: /import-audio skill reads config first
Read skills/import-audio/SKILL.md.
Verify it includes:
1. Step to read `~/.bitwize-music/config.yaml` marked as REQUIRED
2. Extracts `paths.audio_root` and `artist.name`
3. CRITICAL warning about including artist folder
4. Example showing correct path structure

### TEST: /import-audio skill has Common Mistakes section (quick win #7)
Read skills/import-audio/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes these subsections:
- Don't skip reading config
- Don't forget to include artist in path
- Don't use hardcoded artist name
- Don't assume current working directory
- Don't mix up content_root and audio_root
Each subsection should have Wrong/Right examples and "Why it matters" explanation

### TEST: /import-track skill exists
```
Glob: skills/import-track/SKILL.md
```

### TEST: /import-track skill reads config first
Read skills/import-track/SKILL.md.
Verify it includes:
1. Step to read `~/.bitwize-music/config.yaml` marked as REQUIRED
2. Extracts `paths.content_root` and `artist.name`
3. Finds album to determine genre folder
4. Example showing correct path: `{content_root}/artists/{artist}/albums/{genre}/{album}/tracks/`

### TEST: /import-track skill has Common Mistakes section (quick win #7)
Read skills/import-track/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes these subsections:
- Don't skip reading config
- Don't search from wrong location
- Don't forget the tracks/ subdirectory
- Don't use hardcoded artist name
- Don't skip track number validation
- Don't assume album location without searching
Each subsection should have Wrong/Right examples and "Why it matters" explanation

### TEST: /import-art skill exists
```
Glob: skills/import-art/SKILL.md
```

### TEST: /import-art skill handles both destinations
Read skills/import-art/SKILL.md.
Verify it includes:
1. Step to read `~/.bitwize-music/config.yaml` marked as REQUIRED
2. Copies to audio folder: `{audio_root}/{artist}/{album}/`
3. Copies to content folder: `{content_root}/artists/{artist}/albums/{genre}/{album}/`
4. CRITICAL warning about including artist folder in audio path

### TEST: /import-art skill has Common Mistakes section (quick win #7)
Read skills/import-art/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes these subsections:
- Don't skip reading config
- Don't forget to include artist in audio path
- Don't place art in only one location
- Don't mix up the filenames
- Don't search from wrong location
- Don't forget to create directories
Each subsection should have Wrong/Right examples and "Why it matters" explanation

### TEST: /new-album skill exists
```
Glob: skills/new-album/SKILL.md
```

### TEST: /new-album skill reads config first
Read skills/new-album/SKILL.md.
Verify it includes:
1. Step to read `~/.bitwize-music/config.yaml` marked as REQUIRED
2. Extracts `paths.content_root` and `artist.name`
3. Creates correct path: `{content_root}/artists/{artist}/albums/{genre}/{album}/tracks/`
4. Copies templates from plugin directory

### TEST: /new-album skill has Common Mistakes section (quick win #7)
Read skills/new-album/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes these subsections:
- Don't skip reading config
- Don't use current working directory
- Don't hardcode artist name
- Don't forget path structure
- Don't use wrong genre category
Each subsection should have Wrong/Right examples and explanation

### TEST: /new-album skill offers interactive planning option
Read skills/new-album/SKILL.md confirmation message.
Verify it includes:
1. "Option 1 - Interactive (Recommended)" section
2. Reference to "7 Planning Phases"
3. "Option 2 - Manual" section as alternative
4. Encourages interactive approach for guided workflow

### TEST: Shared venv path documented correctly
Search for mastering venv references.
All should point to `~/.bitwize-music/mastering-env` (not per-folder venv).

### TEST: Target loudness documented
Read CLAUDE.md mastering section or reference/mastering/.
Verify it specifies:
- LUFS target: -14
- True Peak: -1.0 dBTP

---

## 8. SHEET MUSIC TESTS (`/test sheet-music`)

Tests for sheet music generation workflow.

### TEST: /sheet-music-publisher skill exists
```
Glob: skills/sheet-music-publisher/SKILL.md
```

### TEST: Sheet music tools exist
These scripts must exist:
- `tools/sheet-music/transcribe.py`
- `tools/sheet-music/fix_titles.py`
- `tools/sheet-music/create_songbook.py`

### TEST: Sheet music scripts are executable
```bash
test -x tools/sheet-music/transcribe.py
test -x tools/sheet-music/fix_titles.py
test -x tools/sheet-music/create_songbook.py
```

### TEST: Sheet music reference documentation exists
These files must exist:
- `skills/sheet-music-publisher/REQUIREMENTS.md`
- `skills/sheet-music-publisher/anthemscore-reference.md`
- `skills/sheet-music-publisher/musescore-reference.md`
- `skills/sheet-music-publisher/publishing-guide.md`
- `tools/sheet-music/README.md`
- `reference/sheet-music/workflow.md`

### TEST: Sheet music requirements documented in skill frontmatter
Read skills/sheet-music-publisher/SKILL.md frontmatter.
Verify it has `requirements:` section with:
- `external:` listing AnthemScore and MuseScore
- `python:` listing pypdf, reportlab, pyyaml

### TEST: Sheet music requirements documented in CLAUDE.md
Read CLAUDE.md "Sheet Music Generation (Optional)" section.
Verify it documents:
- AnthemScore requirement ($42 Professional)
- MuseScore requirement (Free)
- Python dependencies
- Links to software downloads

### TEST: Sheet music scripts have config integration
Read tools/sheet-music/transcribe.py.
Verify it includes:
1. `read_config()` function
2. `resolve_album_path()` function
3. Reads `~/.bitwize-music/config.yaml`
4. Extracts `paths.audio_root` and `artist.name`

Read tools/sheet-music/create_songbook.py.
Verify it includes:
1. `read_config()` function
2. Auto-detects artist from config
3. Auto-detects cover art
4. Auto-detects website from config

### TEST: Sheet music scripts have OS detection
Read tools/sheet-music/transcribe.py.
Verify it includes:
1. `find_anthemscore()` function with platform detection
2. Paths for macOS, Linux, Windows
3. `show_install_instructions()` function

Read tools/sheet-music/fix_titles.py.
Verify it includes:
1. `find_musescore()` function with platform detection
2. Paths for macOS, Linux, Windows
3. `show_install_instructions()` function

### TEST: Sheet music output path includes artist folder
Read tools/sheet-music/transcribe.py.
Verify output directory is constructed as:
`{audio_root}/{artist}/{album}/sheet-music/`

Verify it INCLUDES artist folder (not `{audio_root}/{album}/sheet-music/`)

### TEST: Sheet music documented in CLAUDE.md workflow
Read CLAUDE.md.
Verify "Sheet Music Generation (Optional)" section exists.
Verify it shows workflow position: "Generate → Master → [Sheet Music] → Release"

### TEST: Sheet music in Album Completion Checklist
Read CLAUDE.md "Album Completion Checklist" section.
Verify it includes:
`- [ ] Sheet music generated (optional)`

### TEST: Sheet music skill in skills table
Read CLAUDE.md skills table.
Verify `/bitwize-music:sheet-music-publisher` is listed.

### TEST: Config has sheet_music section
Read config/config.example.yaml.
Verify `sheet_music:` section exists with:
- `page_size:` (letter, 9x12, or 6x9)
- `section_headers:` (boolean)

### TEST: No hardcoded AnthemScore/MuseScore paths
Search tools/sheet-music/*.py for hardcoded paths outside of the OS detection arrays.
Should NOT find paths like `/Applications/` or `C:\Program Files\` except in the detection functions.

### TEST: Sheet music scripts handle missing software gracefully
Read tools/sheet-music/transcribe.py.
Verify that if `find_anthemscore()` returns None:
1. Shows install instructions
2. Exits with non-zero status
3. Does not proceed with transcription

Read tools/sheet-music/fix_titles.py.
Verify that if `find_musescore()` returns None:
1. Shows install instructions
2. Offers `--xml-only` option
3. Exits with non-zero status (if not --xml-only)

---

## 9. RELEASE TESTS (`/test release`)

Tests for release workflow.

### TEST: /release-director skill exists
```
Glob: skills/release-director/SKILL.md
```

### TEST: Album completion checklist documented
Read CLAUDE.md "Album Completion Checklist" section.
Verify checklist items exist.

### TEST: Post-release actions documented
Read CLAUDE.md "Post-Release Immediate Actions" section.
Verify it documents SoundCloud upload, announcements.

### TEST: Streaming lyrics format documented
Read CLAUDE.md "Streaming Lyrics Format" section.
Verify format rules are documented.

### TEST: Album art workflow documented
Read CLAUDE.md "Album Art Generation" section.
Verify it documents:
- When to generate
- Prompt location
- File naming standards

---

## 9. CONSISTENCY TESTS (`/test consistency`)

Cross-reference and consistency checks.

### TEST: All skills documented in help system
Run the validation script:
```bash
python3 tools/validate_help_completeness.py
```

This checks:
1. All skills have SKILL.md file
2. All skills are listed in CLAUDE.md skills table
3. All skills are listed in skills/help/SKILL.md

If this test fails:
- Add missing skill to CLAUDE.md skills table (alphabetically)
- Add missing skill to skills/help/SKILL.md (in appropriate category)
- Update CHANGELOG.md

**Note:** This is critical - if a skill isn't in the help system, users can't discover it!

### TEST: No deprecated terminology
Search entire repo for:
- `media_root` (should be `audio_root`)
- `paths.media_root` (should be `paths.audio_root`)

### TEST: Path variables consistent
Verify these path variables are used consistently:
- `{content_root}`
- `{audio_root}`
- `{documents_root}`
- `{tools_root}`
- `{plugin_root}`

### TEST: All internal markdown links valid
Search for markdown links `[text](path)` where path starts with `/` or `./`.
Verify target files exist.

### TEST: plugin.json matches documentation
Read .claude-plugin/plugin.json.
Verify `name` and `author.name` match README install command.

### TEST: .gitignore has required entries
Read .gitignore. Verify it includes:
- `artists/`
- `research/`
- `*.pdf`
- `primary-sources/`
- `mastering-env/`
- `TESTING.md`

---

## 10. TERMINOLOGY TESTS (`/test terminology`)

Consistent language across docs.

### TEST: Casing preservation instruction exists
Search for "Preserve exact casing" or "preserve.*casing" in:
- CLAUDE.md
- skills/configure/SKILL.md
- skills/tutorial/SKILL.md

All three must have this instruction.

### TEST: No hardcoded user-specific paths
Search for paths that should be variables:
- `/Users/` (except in examples clearly marked)
- `/home/` (except in examples)
- `C:\` (except in examples)

### TEST: Consistent service name
All references should use `suno` (lowercase) not `Suno` when referring to the config value.

### TEST: Consistent plugin name
Plugin should be referred to as:
- `claude-ai-music-skills` (in plugin.json name)
- `bitwize-music@claude-ai-music-skills` (install command)

### TEST: Consistent brand casing
Search for "Bitwize Music" (title case) - should not exist.
Brand should always be "bitwize-music" (lowercase with hyphen).

---

## 11. BEHAVIOR TESTS (`/test behavior`)

Scenario-based tests verifying correct instructions.

### TEST: Missing config recommends /configure
Read CLAUDE.md session start section.
Verify it mentions `/configure` as Option 1 when config missing.

Read skills/tutorial/SKILL.md.
Verify it mentions `/configure` when config missing.

### TEST: Album creation requires planning phases first
Read CLAUDE.md "Building a New Album" section.
Verify it states planning phases must complete before writing.

### TEST: Source verification required before generation
Read CLAUDE.md "Sources & Verification" section.
Verify it states human verification required before production.

### TEST: Tutorial skill checks config first
Read skills/tutorial/SKILL.md.
Verify it reads config as first step.

### TEST: Automatic lyrics review documented
Read CLAUDE.md "Automatic Lyrics Review" section.
Verify it lists all check types:
- Rhyme check
- Prosody check
- Pronunciation check
- POV/Tense check
- Source verification
- Structure check
- Pitfalls check

---

## 12. QUALITY TESTS (`/test quality`)

Code quality and best practices.

### TEST: No TODO/FIXME in production files
Search for `TODO|FIXME|XXX|HACK` in:
- CLAUDE.md
- README.md
- config/README.md
- skills/*/SKILL.md

(Exclude test definitions)

### TEST: No empty markdown links
Search for `\[\]\(\)` (empty link text and href).

### TEST: No malformed markdown links
Search for:
- `\[.*\]\([^)]*$` (unclosed parens)
- `\[.*\][^(\[]` (missing parens after bracket)

### TEST: All code blocks have language specified
Search for triple backticks without language:
```
^```$
```
(Should be ```bash, ```yaml, ```markdown, etc.)

### TEST: README has required sections
Read README.md and verify these sections exist:
- What Is This
- Installation
- Quick Start
- Skills reference tables
- Configuration
- Requirements

### TEST: README has Troubleshooting section (quick win #2)
Read README.md.
Verify "## Troubleshooting" section exists.
Verify it includes these subsections:
- Config Not Found
- Album Not Found When Resuming
- Path Resolution Issues
- Python Dependency Issues (Mastering)
- Playwright Setup (Document Hunter)
- Plugin Updates Breaking Things
- Skills Not Showing Up
- Still Stuck?

### TEST: README has Getting Started Checklist (quick win #3)
Read README.md.
Verify "## Getting Started Checklist" section exists.
Verify it appears before "## Quick Start" section.
Verify it includes:
- Install plugin step
- Create config directory step
- Copy config template step
- Edit config step
- Optional mastering dependencies step
- Optional document hunter dependencies step
- Start Claude and begin step

### TEST: README has Model Strategy section (quick win #5)
Read README.md.
Verify "## Model Strategy" section exists.
Verify it includes:
- Table showing model/when used/skills mapping
- Opus 4.5 for critical creative outputs
- Sonnet 4.5 for most tasks
- Haiku 4.5 for pattern matching
- "Why different models?" explanation
- Reference to /skill-model-updater check command

### TEST: README has visual workflow diagram (quick win #6)
Read README.md "## How It Works" section.
Verify it includes ASCII box diagram showing:
- Concept → Research → Write → Generate → Master → Release
- Specific actions under each phase
- Visual representation (not just text list)

### TEST: CLAUDE.md has required sections
Read CLAUDE.md and verify these sections exist:
- Project Overview
- Configuration
- Session Start
- Core Principles
- Skills table
- Directory Structure
- Workflow

---

## 13. E2E TESTS (`/test e2e`)

End-to-end integration test that creates a test album and exercises the full workflow.

### TEST: E2E - Full album workflow

**This test creates temporary files and cleans them up afterward.**

#### Phase 1: Setup
```
1. Read ~/.bitwize-music/config.yaml
2. Extract content_root, audio_root, artist
3. Run: /new-album _e2e-test-album electronic
4. Verify: {content_root}/artists/{artist}/albums/electronic/_e2e-test-album/ exists
5. Verify: README.md created from template
6. Verify: tracks/ directory exists
```

#### Phase 2: Track Creation
```
1. Create test track: Write {album_path}/tracks/01-test-track.md (minimal content)
2. Verify: Track file exists in correct location
3. Verify: NOT in working directory
```

#### Phase 3: Research Files
```
1. Create RESEARCH.md in {album_path}/
2. Create SOURCES.md in {album_path}/
3. Verify: Files in album directory
4. Verify: Files NOT in working directory or /tmp
```

#### Phase 4: Audio Import
```
1. Create dummy WAV: touch /tmp/_e2e-test.wav
2. Run: /import-audio /tmp/_e2e-test.wav _e2e-test-album
3. Verify: Audio in {audio_root}/{artist}/_e2e-test-album/
4. Verify: Artist folder present in path
5. Verify: NOT at {audio_root}/_e2e-test-album/ (wrong - missing artist)
```

#### Phase 5: Art Import
```
1. Create dummy image: touch /tmp/_e2e-test.png
2. Run: /import-art /tmp/_e2e-test.png _e2e-test-album
3. Verify: Art in {audio_root}/{artist}/_e2e-test-album/album.png
4. Verify: Art in {album_path}/album-art.png
```

#### Phase 6: Validation
```
1. Run: /validate-album _e2e-test-album
2. Verify: All structure checks pass
3. Verify: Audio path check passes (artist folder present)
```

#### Phase 7: Cleanup
```
1. Remove: {content_root}/artists/{artist}/albums/electronic/_e2e-test-album/
2. Remove: {audio_root}/{artist}/_e2e-test-album/
3. Remove: /tmp/_e2e-test.*
4. Verify: No test files remain
```

### Output Format
```
═══════════════════════════════════════════════════════════
E2E TEST SUITE
═══════════════════════════════════════════════════════════

PHASE 1: SETUP
──────────────
[PASS] Config loaded: content_root={path}, audio_root={path}, artist={name}
[PASS] /new-album created _e2e-test-album
[PASS] Album directory exists at correct location
[PASS] README.md created
[PASS] tracks/ directory exists

PHASE 2: TRACK CREATION
───────────────────────
[PASS] Track file created: tracks/01-test-track.md
[PASS] Track in album directory (not working dir)

PHASE 3: RESEARCH FILES
───────────────────────
[PASS] RESEARCH.md created in album directory
[PASS] SOURCES.md created in album directory
[PASS] Files NOT in working directory

PHASE 4: AUDIO IMPORT
─────────────────────
[PASS] /import-audio executed successfully
[PASS] Audio at {audio_root}/{artist}/_e2e-test-album/
[PASS] Artist folder present in path

PHASE 5: ART IMPORT
───────────────────
[PASS] /import-art executed successfully
[PASS] Art in audio folder
[PASS] Art in content folder

PHASE 6: VALIDATION
───────────────────
[PASS] /validate-album passed all checks

PHASE 7: CLEANUP
────────────────
[PASS] Album directory removed
[PASS] Audio directory removed
[PASS] Temp files removed

═══════════════════════════════════════════════════════════
E2E TEST: 17/17 CHECKS PASSED
═══════════════════════════════════════════════════════════
```

### Failure Handling

If any phase fails:
1. Report the failure with details
2. Still run cleanup phase
3. Report cleanup status
4. Exit with failure summary

### TEST: /validate-album skill exists
```
Glob: skills/validate-album/SKILL.md
```

### TEST: /validate-album reads config first
Read skills/validate-album/SKILL.md.
Verify it includes:
1. Step to read `~/.bitwize-music/config.yaml` marked as REQUIRED
2. Extracts content_root, audio_root, and artist
3. Checks audio path includes artist folder
4. Reports actionable fix commands for issues

---

# RUNNING TESTS

## Commands

| Command | Description |
|---------|-------------|
| `/test` or `/test all` | Run all tests |
| `/test config` | Configuration system tests |
| `/test skills` | Skill definitions and docs |
| `/test templates` | Template file tests |
| `/test workflow` | Album workflow documentation |
| `/test suno` | Suno integration tests |
| `/test research` | Research workflow tests |
| `/test mastering` | Mastering workflow tests |
| `/test sheet-music` | Sheet music generation tests |
| `/test release` | Release workflow tests |
| `/test consistency` | Cross-reference checks |
| `/test terminology` | Consistent language tests |
| `/test behavior` | Scenario-based tests |
| `/test quality` | Code quality checks |
| `/test e2e` | End-to-end integration test |

## Adding New Tests

When bugs are found:
1. Identify which category the test belongs to
2. Add a test that would have caught the bug
3. Run `/test [category]` to verify test fails
4. Fix the bug
5. Run `/test [category]` to verify test passes
6. Commit both the fix and the new test

**Rule:** Every bug fix should add a regression test.

---

# EXECUTION TIPS

- Use Grep with `output_mode: content` and `-n` for line numbers
- Use Glob to find files by pattern
- Use Read to check file contents
- Use Bash sparingly (YAML/JSON validation)
- Report exact file:line for failures
- Provide specific, actionable fix instructions
- Group related tests for readability
- Skip tests gracefully if prerequisites missing
