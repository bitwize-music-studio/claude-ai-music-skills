# TEST CATEGORIES

## 1. CONFIG TESTS (`/test config`)

Tests for the configuration system.

### TEST: config.example.yaml exists
```
Glob: config/config.example.yaml
```

### TEST: config.example.yaml is valid YAML
```bash
~/.bitwize-music/venv/bin/python3 -c "import yaml; yaml.safe_load(open('${CLAUDE_PLUGIN_ROOT}/config/config.example.yaml'))"
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
- docs/configuration.md
- config/README.md
- skills/configure/SKILL.md
- skills/tutorial/SKILL.md

All should reference `~/.bitwize-music/config.yaml` or `~/.bitwize-music/`

(README.md no longer documents the config path directly — it points readers to docs/configuration.md instead.)

### TEST: Config must be read before path operations (regression)
Read CLAUDE.md "Configuration & Path Resolution" section (formerly "When to Read Config").
Verify it includes:
1. "ALWAYS read" instruction before moving/creating files
2. "ALWAYS read" instruction before resolving paths
3. "Never assume or remember values" instruction

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
- `model:` (required — tier alias preferred, see below)
- `effort:` (required on Opus/Sonnet skills; omit on Haiku — see below)
- `allowed-tools:` (required, must be array)

### TEST: Skills with external deps have requirements field
Skills that require external tools or Python packages should have `requirements:` in frontmatter.

Required for:
- `mastering-engineer` - needs matchering, pyloudnorm, scipy, numpy, soundfile
- `promo-director` - needs ffmpeg, pillow, librosa
- `sheet-music-publisher` - needs AnthemScore, MuseScore, pypdf, reportlab
- `document-hunter` - needs Playwright, chromium
- `cloud-uploader` - needs boto3

Check with:
```bash
for skill in mastering-engineer promo-director sheet-music-publisher document-hunter cloud-uploader; do
  if ! grep -q "^requirements:" "skills/$skill/SKILL.md"; then
    echo "MISSING: skills/$skill/SKILL.md needs requirements field"
  fi
done
```

### TEST: All model references are valid
Each skill's `model:` field MUST use a **tier alias** so it automatically tracks
the frontier model of that tier (no per-release edits):
```
opus | sonnet | haiku
```
The special values `inherit` / `default` are also accepted. Pinned model IDs
(e.g. `claude-opus-4-8`) are **rejected** — use an alias.

Examples of valid models:
- `opus`
- `sonnet`
- `haiku`

Check with:
```bash
for f in skills/*/SKILL.md; do
  model=$(grep -E '^model:' "$f" | sed 's/model: *//')
  if ! echo "$model" | grep -qE '^(opus|sonnet|haiku|inherit|default)$'; then
    echo "INVALID: $f has model: $model"
  fi
done
```

### TEST: Effort levels are valid and correctly scoped
Skills may set an `effort:` field (reasoning depth). Rules:
- If present, the value must be one of: `low`, `medium`, `high`, `xhigh`, `max`.
- **Opus/Sonnet** skills must set an effort level (these tiers honor it).
- **Haiku** skills must NOT set effort — Haiku does not support it, so the field
  would be a misleading no-op.

`xhigh` is only honored on Opus 4.7/4.8; on Sonnet it gracefully falls back to
`high`. `max` is honored on all Opus/Sonnet tiers. See the
[effort docs](https://code.claude.com/docs/en/model-config.md#adjust-effort-level).

Check with:
```bash
for f in skills/*/SKILL.md; do
  model=$(grep -E '^model:' "$f" | sed 's/model: *//')
  effort=$(grep -E '^effort:' "$f" | sed 's/effort: *//')
  case "$model" in
    *opus*|*sonnet*) [ -z "$effort" ] && echo "MISSING effort: $f" ;;
    *haiku*) [ -n "$effort" ] && echo "UNSUPPORTED effort on haiku: $f" ;;
  esac
  if [ -n "$effort" ] && ! echo "$effort" | grep -qE '^(low|medium|high|xhigh|max)$'; then
    echo "INVALID effort: $f has effort: $effort"
  fi
done
```

### TEST: Skill count in README matches actual
1. Count: `ls -1 skills/ | wc -l`
2. Find in README: "### Skill System (XX Skills)" heading (the old "collection of **XX specialized skills**" phrasing is gone)
3. Must match

### TEST: All skills documented in CLAUDE.md
DROPPED — CLAUDE.md has no comprehensive skill table anymore; it lists only a curated subset of skills in "### Key Routing Rules" by design (as of this sweep, 24 of 53 skills — including 10 researcher sub-skills — aren't named there today, and that's expected: CLAUDE.md is a curated router, not a completeness list). The authoritative version of this claim is "All skills documented in help system" below, which runs `tools/validate_help_completeness.py`: it requires every skill to be referenced in skills/help/SKILL.md, and separately checks CLAUDE.md only for ghost references (a `/bitwize-music:{name}` mention pointing at a skill that no longer exists) — it does not require CLAUDE.md to reference every skill. Keeping both risks a manual-read verdict contradicting the script's verdict for the same repo state.

### TEST: All skills documented in README.md
README.md no longer has skill tables — they moved to `docs/skills.md`. Extract skill names from skills/ directory and verify each appears (as `` `skill-name` ``) in one of `docs/skills.md`'s tables (Core Production, Research System, Quality Control, Release & Distribution, Album Management, Setup & Maintenance).

### TEST: /resume skill documented (quick win #1)
Read `docs/skills.md`. Verify `resume` appears in the "Album Management" table (not "Setup & Maintenance" — it moved tables) with description "Find album, show status, recommend next steps".

### TEST: /configure skill has all commands
Read skills/configure/SKILL.md and verify these are documented:
- `setup`
- `edit`
- `show`
- `validate`
- `reset`

### TEST: /test skill covers all categories
This skill should document tests for: config, skills, templates, workflow, suno, research, mastering, sheet-music, release, consistency, terminology, behavior, quality, e2e (14 categories total)

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
- `all` - All Suno inputs (Style + Exclude + Lyrics combined)
- `suno` - JSON object for Suno auto-fill (added since the original 4-type list; verify it's documented too)

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

**Exception**: `skills/explicit-checker/SKILL.md` merges overrides automatically via the `check_explicit_content` MCP tool — it has "## Override Support" but documents this with a "### Override File Format" subsection instead of "### Loading Override" / "### How to Use Override" steps, and references overrides in "Remember" via "Override additions"/"Override removals" bullets. Accept this structure for explicit-checker only; require the full 4-part structure for the other 9 skills.

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
Search CLAUDE.md for `{plugin_root}/templates/` references (CLAUDE.md now references the templates directory generically rather than naming individual files).
Verify the templates/ directory exists and contains the required template files (album.md, track.md, artist.md, research.md, sources.md).

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
CLAUDE.md has no "Building a New Album" section. Verify instead:
1. CLAUDE.md "Key Routing Rules" contains the line: `**Planning album** → apply /bitwize-music:album-conceptualizer (7 planning phases required)`
2. `skills/album-conceptualizer/SKILL.md` documents all 7 phases under "## Building the Album: The 7 Planning Phases":
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
- `{audio_root}/artists/[artist]/albums/[genre]/[album]/`
- `{documents_root}/artists/[artist]/albums/[genre]/[album]/`

### TEST: Audio path structure has concrete example (regression)
Read CLAUDE.md "Mirrored structure" section.
Verify it includes:
1. A concrete example with actual paths (e.g., `~/bitwize-music/audio/artists/bitwize/albums/electronic/sample-album/`)
2. The phrase "includes artist!" to emphasize artist folder is required
3. A "Common mistake" warning about missing artist folder

This test was added after a bug where audio files were placed at `{audio_root}/[album]/` instead of the full mirrored path.

### TEST: Importing external audio files documented (regression)
Read CLAUDE.md "Importing External Audio Files" section.
Verify it includes:
1. Trigger for audio/WAV files in Downloads or external locations
2. Explicit instruction that path "MUST use mirrored structure"
3. Example showing correct path: `{audio_root}/artists/[artist]/albums/[genre]/[album]/`
4. "CRITICAL" warning about using full mirrored path

This test was added after audio files were repeatedly moved to `{audio_root}/[album]/` without the artist folder.

### TEST: Session start procedure documented
Read CLAUDE.md "Session Start" section (numbered steps 1, 1.5, 2, 3, 4, 4.5, 5, 6, 7, 8).
Verify step 2 is "Load config" (reads `~/.bitwize-music/config.yaml`).
Verify step 3 is "Load overrides" (checks `paths.overrides`, if present).
Verify step 4 ("Load state via MCP") calls `get_ideas` to get idea counts.
Verify it mentions `/bitwize-music:configure` when config missing (step 1 and step 2).
Verify step 7 mentions `/bitwize-music:album-ideas list` when ideas exist.

### TEST: Session startup contextual tips system documented
Read CLAUDE.md "Session Start" section, step 7.
Verify section exists: "**Show contextual tips** based on state:"
Verify all conditional tip categories are documented:
- No albums → tutorial tip
- Ideas exist → album-ideas tip
- In-progress albums → resume tip
- Overrides loaded → note it; missing → suggest creating them
- Pending verifications → verification warning
- One contextual tip from: resume, researcher, pronunciation, clipboard, mastering (pick based on most relevant album state)

(The old "If IDEAS.md has content" framing is gone — ideas are now sourced from the `get_ideas` MCP tool, not a direct IDEAS.md file check.)

### TEST: Session startup general productivity tips exist
DROPPED — the standalone "Always show one general productivity tip (rotate randomly)" section no longer exists. It was merged into step 7's "One contextual tip from: resume, researcher, pronunciation, clipboard, mastering" bullet — there is no separate rotating productivity-tips system anymore. No current doc makes this claim.

### TEST: Session startup ends with question
Read CLAUDE.md "Session Start" section.
Verify the final step (8) is: `**Ask**: "What would you like to work on?"`

### TEST: Contextual tips use correct skill commands
Read CLAUDE.md "Session Start" section, step 7.
Verify these skill references use correct `/bitwize-music:` prefix format:
- `/bitwize-music:tutorial` (not /tutorial)
- `/bitwize-music:album-ideas` (not /album-ideas)
- `/bitwize-music:resume` (not /resume)

Note: `researcher`, `pronunciation`, `clipboard`, and `mastering` appear only as bare topic labels in the "One contextual tip from: ..." bullet, not as full `/bitwize-music:` command invocations — that's expected, since the bullet names topics to choose from rather than commands to run.

### TEST: Contextual tips reference overrides path variable
Read CLAUDE.md "Session Start" section, step 3 ("Load overrides").
Verify overrides references use the `{overrides}` path variable (e.g. `{overrides}/CLAUDE.md`, `{overrides}/pronunciation-guide.md`), not a hardcoded path.

### TEST: Checkpoints documented
CLAUDE.md no longer names checkpoints directly. Verify instead:
1. `reference/workflows/checkpoint-scripts.md` documents these checkpoints:
   - Ready to Generate Checkpoint
   - Album Generation Complete Checkpoint
   - Ready to Master Checkpoint
   - Ready to Release Checkpoint
2. At least one skill (e.g. `skills/explicit-checker/SKILL.md`) references the "Ready to Generate Checkpoint" by name.

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
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/v5-best-practices.md reference
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/structure-tags.md reference
- ${CLAUDE_PLUGIN_ROOT}/skills/lyric-writer/SKILL.md reference
- ${CLAUDE_PLUGIN_ROOT}/skills/pronunciation-specialist/SKILL.md reference

### TEST: Suno v5-best-practices has cross-references (quick win #10)
Read reference/suno/v5-best-practices.md.
Verify "## Related Skills" section exists with:
- /bitwize-music:suno-engineer reference
- /bitwize-music:lyric-writer reference
- /bitwize-music:lyric-reviewer reference
Verify "## See Also" section exists with:
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/pronunciation-guide.md reference
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/structure-tags.md reference
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/genre-list.md reference
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/voice-tags.md reference
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/tips-and-tricks.md reference
- ${CLAUDE_PLUGIN_ROOT}/skills/suno-engineer/SKILL.md reference

### TEST: Suno structure-tags has cross-references (quick win #10)
Read reference/suno/structure-tags.md.
Verify "## Related Skills" section exists with:
- /bitwize-music:lyric-writer reference
- /bitwize-music:suno-engineer reference
- /bitwize-music:lyric-reviewer reference
Verify "## See Also" section exists with:
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/v5-best-practices.md reference
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/pronunciation-guide.md reference
- ${CLAUDE_PLUGIN_ROOT}/reference/suno/voice-tags.md reference
- ${CLAUDE_PLUGIN_ROOT}/skills/lyric-writer/SKILL.md reference

### TEST: Mastering workflow has cross-references (quick win #10)
Read reference/mastering/mastering-workflow.md.
Verify "## Related Skills" section exists with:
- /bitwize-music:mastering-engineer reference
- /bitwize-music:release-director reference
Verify "## See Also" section exists with:
- ${CLAUDE_PLUGIN_ROOT}/tools/mastering/ scripts listed
- ${CLAUDE_PLUGIN_ROOT}/reference/workflows/release-procedures.md reference
- ${CLAUDE_PLUGIN_ROOT}/skills/mastering-engineer/SKILL.md reference

### TEST: Explicit content word list documented
Read `reference/distribution.md` "Explicit Content Guidelines" section (moved out of CLAUDE.md).
Verify the "Explicit Words (require Explicit = Yes)" table exists.

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
DROPPED — CLAUDE.md no longer has a "Suno Reference" section, and no top-level mention of artist-name-forbidden remains anywhere in CLAUDE.md (it was trimmed out along with other domain detail that now lives solely in skill files). The guidance itself is not gone — it's fully covered by "Artist/band name warning documented" (skills/suno-engineer/SKILL.md) above. Keeping both would require CLAUDE.md to duplicate content it no longer duplicates by design.

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
CLAUDE.md's "Sources & Verification" section was renamed to "### Source Verification Gate". Verify:
1. CLAUDE.md "Source Verification Gate" documents the Pending → Verified track status flow and that generation is blocked until verification is complete
2. `reference/workflows/source-verification-handoff.md` documents the human verification handoff triggers (its "When to Stop and Request Verification" section) and the Track Status Workflow
3. `skills/researcher/SKILL.md` "Core Principles" documents source-priority/hierarchy guidance (e.g. "Primary Sources Are Mandatory")

### TEST: documents_root path documented
Verify CLAUDE.md and config docs explain `{documents_root}` path variable.

### TEST: Research files must be saved to album directory (regression)
Read CLAUDE.md "Source Verification Gate" section (formerly "Sources & Verification").
Verify it includes:
1. Rule about saving RESEARCH.md and SOURCES.md to album directory (never cwd)
2. Path format for the album directory: `{content_root}/artists/[artist]/albums/[genre]/[album]/` — documented in CLAUDE.md's "Content Structure" section

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
- `tools/mastering/qc_tracks.py`

### TEST: Mastering workflow documentation exists
```
Glob: reference/mastering/mastering-workflow.md
```

### TEST: /mastering-engineer skill exists
```
Glob: skills/mastering-engineer/SKILL.md
```

### TEST: /mastering-engineer skill uses MCP tools, not direct script invocation (regression)
The plugin-path problem this test guarded against (scripts copied to audio folders, hardcoded `$PLUGIN_DIR` paths breaking after updates) was solved architecturally: mastering-engineer no longer shells out to `tools/mastering/*.py` at all. Read skills/mastering-engineer/SKILL.md and verify:
1. "## Path Resolution (REQUIRED)" section resolves the audio path via the `resolve_path("audio", album_slug)` MCP tool — no manual path construction
2. The mastering workflow uses MCP tools (`analyze_audio`, `qc_audio`, `master_audio`, `master_album`) rather than `bash python3 tools/mastering/*.py` invocations
3. "## Common Mistakes" section has subsection "❌ Don't: Run Python scripts via bash" warning against calling `tools/mastering/*.py` directly (system Python lacks the venv's dependencies) and directing to the equivalent MCP tool instead
4. NO instructions to copy scripts to audio folders anywhere in the skill

This test was added after a bug where scripts were copied to audio folders instead of being run from plugin directory, breaking after plugin updates. The fix has since evolved from "always invoke via a dynamically-found $PLUGIN_DIR" to "never invoke the scripts directly — use MCP tools," which sidesteps the plugin-path problem entirely.

### TEST: /import-audio skill exists
```
Glob: skills/import-audio/SKILL.md
```

### TEST: /import-audio skill resolves paths via MCP (regression)
The skill no longer reads config manually — it resolves paths via MCP instead. Read skills/import-audio/SKILL.md and verify it includes:
1. "## Step 2: Resolve Audio Path via MCP" calling `resolve_path("audio", album_slug)`
2. CRITICAL warning: "Always use `resolve_path` — never construct paths manually"
3. Example showing the resolved path includes the artist folder (mirrored structure)
4. Error handling for "Config file missing" pointing to `/configure`

### TEST: /import-audio skill has Common Mistakes section (quick win #7)
Read skills/import-audio/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes these subsections:
- ❌ Don't: Manually read config and construct paths
- ❌ Don't: Mix up content_root and audio_root
Each subsection should have Wrong/Right examples and a "Why it matters" explanation

### TEST: /import-track skill exists
```
Glob: skills/import-track/SKILL.md
```

### TEST: /import-track skill resolves paths via MCP (regression)
The skill no longer reads config manually — it resolves paths via MCP instead. Read skills/import-track/SKILL.md and verify it includes:
1. "## Step 2: Find Album and Resolve Path via MCP" calling `find_album(album_name)` then `resolve_path("tracks", album_slug)`
2. Example showing correct path: `{content_root}/artists/{artist}/albums/{genre}/{album}/tracks/{XX}-{track-name}.md`
3. Error handling for "Config file missing" pointing to `/configure`

### TEST: /import-track skill has Common Mistakes section (quick win #7)
Read skills/import-track/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes these subsections:
- ❌ Don't: Manually read config and search for albums
- ❌ Don't: Forget the tracks/ subdirectory
- ❌ Don't: Skip track number validation
- ❌ Don't: Assume album location without searching
Each subsection should have Wrong/Right examples and a "Why it matters" explanation

### TEST: /import-art skill exists
```
Glob: skills/import-art/SKILL.md
```

### TEST: /import-art skill handles both destinations
Read skills/import-art/SKILL.md.
Verify it includes:
1. "## Step 2: Find Album and Resolve Paths via MCP" calling `resolve_path("audio", album_slug)` and `resolve_path("content", album_slug)` (no manual config read)
2. Copies to audio folder: `{audio_path}/album.png`
3. Copies to content folder: `{content_path}/album-art.{ext}`
4. CRITICAL warning that `resolve_path` includes the artist folder automatically

### TEST: /import-art skill has Common Mistakes section (quick win #7)
Read skills/import-art/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes these subsections:
- ❌ Don't: Manually read config and construct paths
- ❌ Don't: Place art in only one location
- ❌ Don't: Mix up the filenames
- ❌ Don't: Search for albums manually
- ❌ Don't: Forget to create directories
Each subsection should have Wrong/Right examples and a "Why it matters" explanation

### TEST: /new-album skill exists
```
Glob: skills/new-album/SKILL.md
```

### TEST: /new-album skill creates album via MCP (regression)
The skill no longer reads config manually or copies templates itself — a single MCP call handles everything. Read skills/new-album/SKILL.md and verify it includes:
1. "## Step 2: Create Album via MCP" calling `create_album_structure(album_slug, genre, documentary)`
2. Description of the resulting path: `{content_root}/artists/{artist}/albums/{genre}/{album-name}/`
3. Error handling for "Config file missing" pointing to `/configure`

### TEST: /new-album skill has Common Mistakes section (quick win #7)
Read skills/new-album/SKILL.md.
Verify "## Common Mistakes" section exists.
Verify it includes:
- ❌ Don't: Create directories manually (Wrong/Right example, explaining `create_album_structure` handles config, paths, and templates automatically)
- ✅ Do: Use the specific genre slug (examples of valid genre slugs)

### TEST: /new-album skill offers interactive planning option
Read skills/new-album/SKILL.md confirmation message.
Verify it includes:
1. "Option 1 - Interactive (Recommended)" section
2. Reference to "7 Planning Phases"
3. "Option 2 - Manual" section as alternative
4. Encourages interactive approach for guided workflow

### TEST: Shared venv path documented correctly
Search for mastering venv references.
All should point to `~/.bitwize-music/venv` (not per-folder venv).

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
- `tools/sheet-music/prepare_singles.py` (renamed from `fix_titles.py`)
- `tools/sheet-music/create_songbook.py`

### TEST: Sheet music scripts are executable
```bash
test -x tools/sheet-music/transcribe.py
test -x tools/sheet-music/prepare_singles.py
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

### TEST: Sheet music requirements documented
CLAUDE.md has no "Sheet Music Generation (Optional)" section — this detail lives entirely in the skill's own docs now. Read `skills/sheet-music-publisher/REQUIREMENTS.md` and verify it documents:
- AnthemScore requirement ($42 Professional recommended)
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

Read tools/sheet-music/prepare_singles.py (renamed from fix_titles.py).
Verify it includes:
1. `find_musescore()` function with platform detection
2. Paths for macOS, Linux, Windows
3. `show_install_instructions()` function

### TEST: Sheet music output path includes artist folder
Read tools/sheet-music/transcribe.py.
Verify output directory is constructed as:
`{audio_root}/artists/{artist}/albums/{genre}/{album}/sheet-music/`

Verify it INCLUDES artist folder (not `{audio_root}/{album}/sheet-music/`)

### TEST: Sheet music workflow position documented
CLAUDE.md's Workflow Overview line (`Concept → Research → Write ... → Master → Promo Videos (optional) → Promo Copy (optional) → Release`) does not mention sheet music at all, and there is no "Sheet Music Generation (Optional)" CLAUDE.md section or sheet-music-publisher routing rule. Sheet music's position is documented only via its own skill: verify `skills/sheet-music-publisher/SKILL.md` frontmatter `description:` states "Use after mastering when the user wants sheet music or a songbook for their album."

### TEST: Sheet music in Album Completion Checklist
DROPPED — no current doc states this. CLAUDE.md has no "Album Completion Checklist" section, and the actual checklist content (now `reference/workflows/release-procedures.md` "### 1. Verify Completion Checklist") does not include a sheet-music line item. Sheet music is documented purely as an optional, on-request, post-mastering skill (see "Sheet music workflow position documented" above) — nothing currently claims it belongs on the release checklist.

### TEST: Sheet music skill in skills table
CLAUDE.md has no skills table anymore. Read `docs/skills.md` "Release & Distribution" table and verify `sheet-music-publisher` is listed.

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

Read tools/sheet-music/prepare_singles.py (renamed from fix_titles.py).
Verify that if `find_musescore()` returns None (and `--xml-only` was not passed):
1. Shows install instructions
2. Warns and continues without exiting — PDFs are copied from source instead of exported via MuseScore (this behavior changed from the old fix_titles.py, which exited non-zero; prepare_singles.py now degrades gracefully)
3. `--xml-only` remains available as a flag that skips the MuseScore lookup entirely

---

## 9. RELEASE TESTS (`/test release`)

Tests for release workflow.

### TEST: /release-director skill exists
```
Glob: skills/release-director/SKILL.md
```

### TEST: Album completion checklist documented
CLAUDE.md has no "Album Completion Checklist" section. Read `reference/workflows/release-procedures.md` "### 1. Verify Completion Checklist" and verify checklist items exist (all tracks Final with Suno Links, album art generated, audio mastered, streaming lyrics filled in).

### TEST: Post-release actions documented
CLAUDE.md has no "Post-Release Immediate Actions" section. Verify instead:
1. `reference/workflows/release-procedures.md` "### 3. Upload to Platforms" documents uploading to SoundCloud/distributor and adding platform URLs to the album README
2. `reference/workflows/checkpoint-scripts.md` "## Post-Release Message" documents the release announcement template

### TEST: Streaming lyrics format documented
CLAUDE.md has no "Streaming Lyrics Format" section — it moved to `reference/distribution.md`. Read `reference/distribution.md` "## Streaming Lyrics Format" / "### Format Rules" and verify format rules are documented.

### TEST: Album art workflow documented
CLAUDE.md has no "Album Art Generation" section — it moved to `reference/workflows/release-procedures.md`. Read that file's "## Album Art Generation" section and verify it documents:
- When to generate ("### When to Generate Album Art")
- Prompt location ("### Workflow" step 1, "Verify Prompt Exists" — prompt lives in the album README's "Album Art" section)
- File naming standards ("### File Naming Standards")

---

## 10. CONSISTENCY TESTS (`/test consistency`)

Cross-reference and consistency checks.

### TEST: All skills documented in help system
Run the validation script (call `get_python_command()` first for the venv path):
```bash
$PYTHON "$PLUGIN_DIR/tools/validate_help_completeness.py"
```

This checks:
1. All skills have a SKILL.md file
2. Every skill is referenced (`/bitwize-music:{name}`) in skills/help/SKILL.md — help must document every skill
3. CLAUDE.md is a curated router, not a completeness list — the script only fails if CLAUDE.md references a `/bitwize-music:{name}` skill that doesn't exist (a ghost reference); it does not require every skill to appear there

If this test fails:
- Add missing skill to skills/help/SKILL.md (in appropriate category)
- Fix or remove any CLAUDE.md reference to a nonexistent skill
- Update CHANGELOG.md

**Note:** This is critical - if a skill isn't in the help system, users can't discover it!

### TEST: No deprecated terminology
Search entire repo for:
- `media_root` (should be `audio_root`)
- `paths.media_root` (should be `paths.audio_root`)

Exclude `tests/plugin/test_terminology.py` — it defines these deprecated terms as detection patterns for its own automated check; matches there are the detector itself, not violations.

### TEST: Path variables consistent
Verify these path variables are used consistently:
- `{content_root}`
- `{audio_root}`
- `{documents_root}`
- `{tools_root}`
- `${CLAUDE_PLUGIN_ROOT}`

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
- `venv/`
- `TESTING.md`

### TEST: No skill.json files exist (standard is SKILL.md)
```bash
find skills -name "skill.json" -type f
```
Should return zero results. All skills must use SKILL.md format.

This test was added after an accidental skill.json was found in the resume skill.

### TEST: Genre references match genres/ directory
1. List valid genres:
   ```bash
   ls -1 genres/
   ```
2. Search for genre references in templates and documentation:
   - `templates/album.md` - genre field examples
   - `skills/new-album/SKILL.md` - genre parameter
   - `CLAUDE.md` - genre examples
3. Any genre referenced in examples must exist in `genres/` directory
4. Common issues to catch:
   - `hiphop` vs `hip-hop` (hyphenation)
   - `synth-wave` vs `synthwave` (hyphenation)
   - References to genres without documentation

---

## 11. TERMINOLOGY TESTS (`/test terminology`)

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
Prose and headings use "Suno" (brand casing). Config values, slugs, file names, tags, and URLs use lowercase "suno". Identifiers are exempt from casing complaints. Flag only prose that uses lowercase "suno" or config values that use "Suno".

### TEST: Consistent plugin name
Plugin should be referred to as:
- `bitwize-music` (in plugin.json name)
- `bitwize-music@bitwize-music` (install command)

### TEST: Consistent brand casing
Search for "Bitwize Music" (title case) - should not exist.
Brand should always be "bitwize-music" (lowercase with hyphen).

---

## 12. BEHAVIOR TESTS (`/test behavior`)

Scenario-based tests verifying correct instructions.

### TEST: Missing config recommends /configure
Read CLAUDE.md "Session Start" section.
Verify it mentions `/bitwize-music:configure` when config is missing (step 1: "If config missing → suggest: `/bitwize-music:configure`"; step 2: "Load config ... If missing, tell user to run `/bitwize-music:configure`"). (The old "as Option 1" numbered-options framing is gone — it's now a bulleted fallback under each relevant step.)

Read skills/tutorial/SKILL.md.
Verify it mentions `/configure` when config missing.

### TEST: Album creation requires planning phases first
CLAUDE.md has no "Building a New Album" section. Read `reference/workflows/album-planning-phases.md` and verify it states: "**Before writing any lyrics or creating tracks**, work through these phases with the user" (also see its Phase 7 "Required before writing" checklist).

### TEST: Source verification required before generation
CLAUDE.md's "Sources & Verification" section was renamed to "### Source Verification Gate". Verify it states human verification is required before generation (item 4: "Block generation if verification incomplete — `/bitwize-music:pre-generation-check` enforces this").

### TEST: Tutorial skill checks config first
Read skills/tutorial/SKILL.md.
Verify it reads config as first step.

### TEST: Automatic lyrics review documented
CLAUDE.md has no "Automatic Lyrics Review" section. The closest current equivalents are `skills/lyric-reviewer/SKILL.md` "## The 14-Point Checklist" (see also `skills/lyric-reviewer/checklist-reference.md`) and CLAUDE.md's "Core Principles" bullet ("When user says 'let's work on [track]', scan full lyrics for issues BEFORE doing anything else..."). Verify the 14-point checklist includes, by name:
- Rhyme Check
- Prosody Check
- Pronunciation Check
- POV/Tense Check
- Structure Check

"Source verification" and "Pitfalls check" don't exist as named checklist items — the closest analogs are the checklist's "Documentary Check" and "Factual Check" (conditional, source/claim verification). Don't fail the test solely for the absence of those two exact names.

---

## 13. QUALITY TESTS (`/test quality`)

Code quality and best practices.

### TEST: No TODO/FIXME in production files
Search for `TODO|FIXME|XXX|HACK` in:
- CLAUDE.md
- README.md
- config/README.md
- skills/*/SKILL.md

(Exclude test definitions)

Search ONLY the four files/globs listed above. Code files (tools/, servers/) are OUT of scope — detection patterns in code (e.g. gates.py's `[TODO]` regex, or terminology-checker pattern lists) are not findings.

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
README.md was restructured around a shorter narrative + a "Detailed Documentation" table pointing to docs/. Read README.md and verify these sections exist:
- Intro/"What it actually does" paragraph (no heading — the opening paragraphs after the title)
- "## Install"
- "## Architecture" (with subsections: Skill System, Multi-Model Orchestration, MCP Server, Research System, Quality Gates, Genre Coverage, CI/CD)
- "## Project Structure"
- "## Detailed Documentation" (table linking to docs/skills.md, docs/configuration.md, docs/troubleshooting.md, etc.)

(The old "What Is This / Installation / Quick Start / Skills reference tables / Configuration / Requirements" headings no longer exist by those names — skill tables and configuration detail moved to docs/skills.md and docs/configuration.md respectively.)

### TEST: Troubleshooting doc has required subsections (quick win #2)
README.md no longer has a "## Troubleshooting" section — it moved to `docs/troubleshooting.md`. Read `docs/troubleshooting.md` and verify it includes these subsections:
- Config Not Found
- Album Not Found When Resuming
- Path Resolution Issues
- Python Dependency Issues (Mastering)
- Playwright Setup (Document Hunter)
- Plugin Updates Breaking Things
- Skills Not Showing Up
- Still Stuck?

### TEST: README Install section has setup steps (quick win #3)
README.md has neither "Getting Started Checklist" nor "Quick Start" — both were replaced by a single "## Install" section. Read README.md "## Install" and verify it includes:
- The `/plugin marketplace add` and `/plugin install` commands
- A mention of `/bitwize-music:setup` (detect environment, install dependencies)
- A mention of `/bitwize-music:configure` (set artist name and workspace paths)

(Drop the "must appear before Quick Start" ordering assertion — there is no separate Quick Start section to order against.)

### TEST: Model Strategy documented (quick win #5)
README.md has no "## Model Strategy" heading — it has "### Multi-Model Orchestration" under "## Architecture" instead, which links out to `reference/model-strategy.md` for the full per-skill rationale. Verify:
- README.md "### Multi-Model Orchestration" includes a table showing Tier / Model / Skill count / Rationale, covering Opus, Sonnet, and Haiku tiers
- `reference/model-strategy.md` exists and explains the rationale per tier (don't assert specific model version numbers like "4.5" — tiers use aliases that float to the current frontier model, so pinned versions in a test would itself go stale)

### TEST: README has workflow illustration (quick win #6)
README.md has no "## How It Works" section or ASCII box diagram — it has "## Example Workflow" instead, showing a terminal-style You:/Claude: dialogue transcript. Read README.md "## Example Workflow" and verify it illustrates the pipeline (concept → research → write → generate → master → release) through example dialogue, not a text list.

### TEST: README skill count matches actual (regression)
1. Count skill directories: `ls -1 skills/ | wc -l`
2. Read README.md and extract the number from "### Skill System (XX Skills)" (the old "collection of **XX specialized skills**" phrasing is gone)
3. The counts must match exactly
4. Also cross-check against "skills/              XX skill definitions" in "## Project Structure" and "All XX skills" in the "## Detailed Documentation" table — all three numbers must agree

This test was added after the README claimed 32 skills when there were actually 38.

### TEST: CLAUDE.md has required sections
Read CLAUDE.md and verify these top-level (`##`) sections exist:
- ⚠️ CRITICAL: Finding Albums When User Mentions Them
- Configuration & Path Resolution
- MCP Server — Preferred Data Access
- Session Start
- Core Principles
- Workflow Overview
- Content Structure
- Versioning & Development
- Mid-Session Rules

(The old "Project Overview / Configuration / Skills table / Directory Structure / Workflow" names no longer exist as headings — CLAUDE.md has no comprehensive skills table at all now, and "Directory Structure" content lives under "Content Structure".)

---

## 14. E2E TESTS (`/test e2e`)

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
3. Verify: Audio in {audio_root}/artists/{artist}/albums/electronic/_e2e-test-album/
4. Verify: Full mirrored path structure present
5. Verify: NOT at {audio_root}/_e2e-test-album/ (wrong - missing structure)
```

#### Phase 5: Art Import
```
1. Create dummy image: touch /tmp/_e2e-test.png
2. Run: /import-art /tmp/_e2e-test.png _e2e-test-album
3. Verify: Art in {audio_root}/artists/{artist}/albums/electronic/_e2e-test-album/album.png
4. Verify: Art in {album_path}/album-art.png
```

#### Phase 6: Validation
```
1. Run: /validate-album _e2e-test-album
2. Verify: All structure checks pass
3. Verify: Audio path check passes (full mirrored structure present)
```

#### Phase 7: Cleanup
```
1. Remove: {content_root}/artists/{artist}/albums/electronic/_e2e-test-album/
2. Remove: {audio_root}/artists/{artist}/albums/electronic/_e2e-test-album/
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
[PASS] Audio at {audio_root}/artists/{artist}/albums/electronic/_e2e-test-album/
[PASS] Full mirrored path structure present

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
