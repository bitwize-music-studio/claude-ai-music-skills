# Testing Plan for claude-ai-music-skills

Comprehensive testing checklist before marketplace release.

## Codex discovery and MCP session state

Activate a Python 3.11+ venv with the plugin requirements installed. On
macOS, Linux, or WSL, use `make venv` and `source .venv/bin/activate`. The
discovery probe uses `~/.bitwize-music/venv` if it exists, so install the
requirements there as well.

```bash
npm ci --prefix tests/e2e/codex --no-audit --no-fund
python3 tests/e2e/codex_plugin_discovery_check.py --codex tests/e2e/codex/node_modules/.bin/codex
python3 tests/e2e/codex_session_resume_check.py --codex tests/e2e/codex/node_modules/.bin/codex --venv .venv
```

On Windows, activate `.venv\Scripts\activate.bat` (cmd) or
`.venv\Scripts\Activate.ps1` (PowerShell). Use `python` and append `.cmd` to
the Codex executable path above.

The session probe uses temporary `HOME` and `CODEX_HOME` directories and a
music workspace outside the plugin. It links the dependency venv into
`HOME` using a directory junction on Windows.

Both probes should exit 0. The discovery probe checks the canonical skill
list and starts MCP from the installed copy. The session probe checks that the
installed copy contains the workflow reference files. It exercises the MCP
startup queries, album lookup and progress, and session persistence. It compares
the synthetic album and track files before and after the checks. CI runs both
probes on Linux and Windows without model turns.

### Manual conversational acceptance

Use a temporary `HOME` and `CODEX_HOME` (`USERPROFILE` too on Windows).
Install the plugin there and use a music workspace outside the plugin.
Sign in with a dedicated test account in that Codex home. Start a fresh Codex
session so the MCP server starts in the same environment.

1. Start with no config. Invoke `setup` to check dependencies, then
   `configure setup` with no settings. Confirm it asks for the required
   fields and waits for your answers before creating the config file.
   On native Windows, check the displayed PowerShell installation commands
   with a plugin installed under a path that contains spaces.
2. Provide an artist and content, audio, documents, and overrides paths. Use a
   path containing spaces and an overrides directory outside the content root.
   Check that the YAML preserves the values and the artist's casing. Change
   only the audio path with `configure edit` and compare the other fields.
3. Put instructions for different status-report markers in the configured
   overrides `CLAUDE.md` and in the music workspace's `CLAUDE.md`. Invoke
   `session-start` in a fresh session without mentioning either marker.
   Check that it reads the installed `reference/plugin-rules.md`, calls
   `health_check(runtime="codex")` and the Step 4 MCP queries, and shows only
   the configured marker. Repeat with the overrides directory absent and confirm
   startup continues.
4. Create two synthetic albums. Give the first `Research Complete` status and
   a track awaiting source verification. Give the second `In Progress` status
   and more completed tracks. Invoke `resume` for the first album by name in
   a fresh session and confirm the configured override file is read before album
   lookup. In another fresh session, invoke `resume` without a name. Check that it uses
   `get_session().session.last_album` and recommends the `verify-sources`
   skill for the first album.
   Check that `~/.bitwize-music/cache/state.json` records the first album as
   `last_album`, `Verification` as `last_phase`, and a fresh `updated_at`.
5. Disconnect the plugin's MCP server and invoke `session-start`. Check that
   it reports state from the cache and defers migration checks. Resume the
   first album by name and then from saved context in separate sessions. Each
   run should report the verification step and leave the saved context intact.
   A recommendation can name the skill. If it includes a command, expect
   `$bitwize-music:verify-sources`.
   With no config, check that the skill recommends `configure`. For an unknown
   album, check that it reports the lookup failure and leaves saved context intact.
6. Verify album and track files have the same contents after startup and
   resume. Record the commit, host, CLI and model settings, and observed tool
   results.

---

## Prerequisites

- Claude Code installed and working
- Python 3.8+ installed
- Git configured
- A test directory outside the plugin repo (e.g., `~/test-music-plugin/`)

---

## Phase 1: Fresh Install Testing

### 1.1 Clone Install (Primary Method)

```bash
# Create clean test directory
mkdir -p ~/test-music-plugin
cd ~/test-music-plugin

# Clone fresh copy
git clone https://github.com/bitwize-music-studio/claude-ai-music-skills.git
cd claude-ai-music-skills

# Start Claude Code
claude
```

**Verify:**
- [ ] Claude loads without errors
- [ ] The plugin's rules load at session start in the music workspace (ask Claude whether it has "bitwize-music: rules for every session"); elsewhere it has only a one-line pointer
- [ ] Skills are available (type `/` and check menu)

### 1.2 Plugin Install (Marketplace Method)

```bash
# In a different directory (not inside the cloned repo)
cd ~/test-music-plugin

# Add marketplace and install
claude
```

Then in Claude Code:
```
/plugin marketplace add bitwize-music-studio/claude-ai-music-skills
/plugin install bitwize-music@claude-ai-music-skills
```

**Verify:**
- [ ] Plugin installs without errors
- [ ] Skills appear in `/` menu
- [ ] Can invoke skills (e.g., `/tutorial help`)

---

## Phase 2: Configuration Testing

### 2.1 Initial Config Setup

```bash
cd ~/test-music-plugin/claude-ai-music-skills

# Copy example config
mkdir -p ~/.bitwize-music
cp config/config.example.yaml ~/.bitwize-music/config.yaml
```

Edit `~/.bitwize-music/config.yaml`:
```yaml
artist:
  name: "test-artist"

paths:
  content_root: "~/test-music-plugin/content"
  audio_root: "~/test-music-plugin/audio"
  documents_root: "~/test-music-plugin/documents"
  tools_root: "~/.bitwize-music"
  plugin_root: "."

urls:
  soundcloud: "https://soundcloud.com/test"

generation:
  service: suno
```

Create directories:
```bash
mkdir -p ~/test-music-plugin/content/artists
mkdir -p ~/test-music-plugin/audio
mkdir -p ~/test-music-plugin/documents
mkdir -p ~/.bitwize-music
```

**Verify:**
- [ ] Config loads on session start
- [ ] No errors about missing paths
- [ ] Claude reports paths correctly

### 2.2 Path Resolution

In Claude Code, ask: "What are my configured paths?"

**Verify:**
- [ ] content_root resolves correctly
- [ ] audio_root resolves correctly
- [ ] documents_root resolves correctly
- [ ] tools_root resolves correctly

---

## Phase 3: Core Workflow Testing

### 3.1 Tutorial Skill

```
/tutorial help
```

**Verify:**
- [ ] Help message displays correctly
- [ ] Shows all three commands (new-album, resume, help)

```
/tutorial resume
```

**Verify:**
- [ ] Scans content_root for albums
- [ ] Reports "no albums found" (expected for fresh install)

### 3.2 Album Creation

```
/tutorial new-album
```

Walk through Phase 1-2 only (Foundation + Concept):
- Artist: "Test Artist" (new)
- Genre: "electronic"
- Album name: "Test Album"
- Type: "Thematic"

**Verify:**
- [ ] Creates artist directory: `{content_root}/artists/test-artist/`
- [ ] Creates album directory: `{content_root}/artists/test-artist/albums/electronic/test-album/`
- [ ] Creates album README.md
- [ ] Creates tracks/ subdirectory

### 3.3 Lyric Writer

Create a test track file, then:
```
/lyric-writer {content_root}/artists/test-artist/albums/electronic/test-album/tracks/01-test-track.md
```

Ask it to write a simple verse.

**Verify:**
- [ ] Skill loads correctly
- [ ] Writes lyrics with section tags
- [ ] Runs automatic review (rhyme, prosody, pronunciation)

### 3.4 Pronunciation Specialist

```
/pronunciation-specialist {content_root}/artists/test-artist/albums/electronic/test-album/tracks/01-test-track.md
```

**Verify:**
- [ ] Scans for pronunciation risks
- [ ] Reports findings (or "no issues" if clean)

### 3.5 Explicit Checker

```
/explicit-checker {content_root}/artists/test-artist/albums/electronic/test-album/
```

**Verify:**
- [ ] Scans all tracks in album
- [ ] Reports explicit content status

### 3.6 Suno Engineer

Ask Claude to help with Suno prompts for a track.

**Verify:**
- [ ] Generates Style Box content
- [ ] Generates Lyrics Box content
- [ ] Uses V5 best practices

---

## Phase 4: Research Workflow Testing

### 4.1 Researcher Skill

```
/researcher "test topic for research"
```

**Verify:**
- [ ] Skill loads correctly
- [ ] Searches for sources
- [ ] Returns formatted results

### 4.2 Document Hunter (Requires Playwright)

First, set up Playwright:
```bash
pip install playwright beautifulsoup4 requests
playwright install chromium
```

Then:
```
/document-hunter "test case name"
```

**Verify:**
- [ ] Creates download directory in documents_root
- [ ] Searches free sources
- [ ] Reports what was found

### 4.3 Document Storage Path

After document-hunter runs:

**Verify:**
- [ ] PDFs saved to `{documents_root}/[artist]/[album]/`
- [ ] manifest.json created alongside PDFs
- [ ] No PDFs in content_root (git-safe)

---

## Phase 5: Mastering Workflow Testing

### 5.1 Shared Venv Setup

```bash
# One-time setup
mkdir -p ~/.bitwize-music
python3 -m venv ~/.bitwize-music/venv
source ~/.bitwize-music/venv/bin/activate
pip install matchering pyloudnorm scipy numpy soundfile
deactivate
```

**Verify:**
- [ ] Venv created successfully
- [ ] All packages install without errors

### 5.2 Mastering Scripts

Create a test folder with a WAV file:
```bash
mkdir -p ~/test-music-plugin/test-master
# Copy any WAV file here for testing
```

```bash
cd ~/test-music-plugin/test-master
source ~/.bitwize-music/venv/bin/activate

# Copy scripts from plugin
cp ~/test-music-plugin/claude-ai-music-skills/tools/mastering/*.py .

# Run analysis
python3 analyze_tracks.py
```

**Verify:**
- [ ] analyze_tracks.py runs without errors
- [ ] LUFS readings displayed

```bash
# Run mastering (dry run first)
python3 master_tracks.py --dry-run

# If dry run OK, run actual mastering
python3 master_tracks.py
```

**Verify:**
- [ ] master_tracks.py runs without errors
- [ ] Creates mastered/ subdirectory
- [ ] Output files at target LUFS (-14)

### 5.3 Audio Output Path

When mastering a real album:

**Verify:**
- [ ] Mastered files go to `{audio_root}/[artist]/[album]/`
- [ ] Album art saved alongside mastered files

---

## Phase 6: Git Safety Testing

### 6.1 PDF Blocking

```bash
cd ~/test-music-plugin/claude-ai-music-skills

# Create a fake PDF in content area
touch ~/test-music-plugin/content/artists/test-artist/test.pdf

# Try to add it
cd ~/test-music-plugin/content
git init  # if not already a repo
git add .
git status
```

**Verify:**
- [ ] PDF is NOT staged (blocked by .gitignore)

### 6.2 Primary Sources Blocking

```bash
mkdir -p ~/test-music-plugin/content/artists/test-artist/albums/electronic/test-album/primary-sources
touch ~/test-music-plugin/content/artists/test-artist/albums/electronic/test-album/primary-sources/doc.pdf

git add .
git status
```

**Verify:**
- [ ] primary-sources/ directory is NOT staged

---

## Phase 7: Skill Inventory Check

Run each skill and verify it loads:

| Skill | Command | Works |
|-------|---------|-------|
| tutorial | `/tutorial help` | [ ] |
| lyric-writer | `/lyric-writer --help` | [ ] |
| album-conceptualizer | (invoke during album creation) | [ ] |
| suno-engineer | (invoke during track work) | [ ] |
| pronunciation-specialist | `/pronunciation-specialist [file]` | [ ] |
| lyric-reviewer | `/lyric-reviewer [file]` | [ ] |
| explicit-checker | `/explicit-checker [album]` | [ ] |
| album-art-director | (invoke during art creation) | [ ] |
| mastering-engineer | (invoke during mastering) | [ ] |
| release-director | (invoke during release) | [ ] |
| researcher | `/researcher "topic"` | [ ] |
| document-hunter | `/document-hunter "case"` | [ ] |
| researchers:legal | `/researchers:legal "case"` | [ ] |
| researchers:gov | `/researchers:gov "topic"` | [ ] |
| researchers:journalism | `/researchers:journalism "topic"` | [ ] |
| researchers:tech | `/researchers:tech "topic"` | [ ] |
| researchers:security | `/researchers:security "topic"` | [ ] |
| researchers:financial | `/researchers:financial "topic"` | [ ] |
| researchers:historical | `/researchers:historical "topic"` | [ ] |
| researchers:biographical | `/researchers:biographical "person"` | [ ] |
| researchers:primary-source | `/researchers:primary-source "subject"` | [ ] |
| researchers:verifier | `/researchers:verifier [album]` | [ ] |
| skill-model-updater | `/skill-model-updater check` | [ ] |

---

## Phase 8: Edge Cases

### 8.1 Missing Config

```bash
# Remove config
rm ~/.bitwize-music/config.yaml

# Start Claude Code
claude
```

**Verify:**
- [ ] Claude prompts user to set up config
- [ ] Doesn't crash or error out

### 8.2 Invalid Paths

Edit paths.yaml with non-existent path:
```yaml
paths:
  content_root: "/nonexistent/path"
```

**Verify:**
- [ ] Claude handles gracefully
- [ ] Offers to create directory or warns user

### 8.3 Empty Album

Create album structure with no tracks:
```bash
mkdir -p ~/test-music-plugin/content/artists/test-artist/albums/electronic/empty-album/tracks
```

Run `/tutorial resume`

**Verify:**
- [ ] Detects album correctly
- [ ] Reports 0 tracks

---

## Phase 9: End-to-End Workflow

Complete one full album cycle (abbreviated):

1. [ ] `/tutorial new-album` - Create album concept
2. [ ] Write 2 test tracks with `/lyric-writer`
3. [ ] Run `/pronunciation-specialist` on both tracks
4. [ ] Run `/lyric-reviewer` on both tracks
5. [ ] Run `/explicit-checker` on album
6. [ ] (Simulate) Mark tracks as Generated
7. [ ] Run mastering on test WAVs
8. [ ] Verify output in `{audio_root}/[artist]/[album]/`

---

## Phase 10: Cleanup

After testing:

```bash
# Remove test directories
rm -rf ~/test-music-plugin/content
rm -rf ~/test-music-plugin/audio
rm -rf ~/test-music-plugin/documents

# Optionally remove shared venv (or keep for future use)
# rm -rf ~/.bitwize-music

# Remove test plugin install
# /plugin uninstall bitwize-music@claude-ai-music-skills
```

---

## Release Checklist

Before publishing:

- [ ] All Phase 1-9 tests pass
- [ ] No error messages during normal operation
- [ ] All 23 skills load correctly
- [ ] Documentation matches actual behavior
- [ ] .gitignore blocks sensitive files
- [ ] Example configs are complete and commented

---

## Quick Test Script

For rapid re-testing, run this sequence:

```bash
#!/bin/bash
# quick-test.sh

set -e

echo "=== Testing Plugin ==="

# Setup
cd ~/test-music-plugin/claude-ai-music-skills
mkdir -p ~/.bitwize-music
cp config/config.example.yaml ~/.bitwize-music/config.yaml

# Create test paths
mkdir -p ~/test-music-plugin/{content/artists,audio,documents}

# Test mastering venv
source ~/.bitwize-music/venv/bin/activate
python -c "import matchering, pyloudnorm, scipy, numpy, soundfile; print('Packages OK')"
deactivate

echo "=== Basic tests passed ==="
echo "Now run 'claude' and test skills manually"
```

---

## Reporting Issues

If tests fail:
1. Note the exact command/action that failed
2. Capture error message
3. Check which phase failed
4. Report at: https://github.com/bitwize-music-studio/claude-ai-music-skills/issues
