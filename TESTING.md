# Testing Plan for claude-ai-music-skills

Comprehensive testing checklist before marketplace release.

## Codex startup and resume

With Codex CLI and a dependency venv installed, run:

```bash
python3 tests/e2e/codex_plugin_discovery_check.py
python3 tests/e2e/codex_session_resume_check.py --venv "$HOME/.bitwize-music/venv"
```

The second probe uses temporary `HOME` and `CODEX_HOME` directories and an
unrelated music-project cwd. It verifies all 53 skills through Codex's host API,
then exercises configuration, Codex health diagnostics, source-verification
state, album lookup/progress, and persisted session updates through MCP. It
asserts that the synthetic album and track files remain unchanged. CI runs this
without starting a model turn. Use `--venv .venv` for a developer environment or
`--codex /path/to/codex` to check a particular CLI version.

To additionally exercise the installed setup, configure, startup, and resume
skills with authenticated startup and resume model turns:

```bash
python3 tests/e2e/codex_session_resume_check.py --venv .venv --model-check
```

This uses account usage. The optional check copies existing `auth.json` into
the temporary Codex home with private permissions, leaves normal Codex settings
unchanged, and checks actual MCP calls and the source-verification recommendation.
Startup and resume must each supply their own evidence. Resume must query session
context, update the expected album and phase, and persist a fresh session timestamp;
startup calls or recommendations cannot satisfy the resume checks.
The isolated invocation preapproves only synthetic state queries and session
updates so the noninteractive `never` approval policy can run the workflow.
It performs dependency inspection and `configure show`; it does not install
packages or exercise every interactive configuration response. These checks
cover the startup/resume slice, not the full downstream music-production pipeline.

### Minimal configuration and overrides acceptance — 2026-10-03

An authenticated, one-off acceptance run passed on macOS arm64, Python 3.11.5,
and Codex CLI 0.160.0, using plugin version 0.102.0-dev at commit
`7bd0509fb53cf8e7610365f95f0869bb2f1f9f09`. It reused the synthetic workspace
and local plugin installation helpers above, with temporary `HOME` and
`CODEX_HOME`, the project `.venv`, and a cwd outside the installed plugin.
This was separate from the automated `--model-check` probe.

| Case | Procedure and observed evidence |
|---|---|
| Initial configuration | Remove the fixture config and invoke `$bitwize-music:configure setup` without settings. The model requested artist/content/audio/documents settings, and the config file remained absent until answers were supplied. |
| Save after answers | Supply values through `codex exec resume` in the same conversation. Read the saved YAML: artist casing `probeArtist` and all supplied paths matched exactly, including paths containing spaces and an overrides directory outside the content root. |
| Specified edit | Invoke `$bitwize-music:configure edit` to change only `paths.audio_root`. Read the YAML and compare all remaining values against the previous config: only the requested path changed. |
| Configured overrides | Put a unique startup-report marker in the configured overrides `CLAUDE.md`, a pronunciation guide alongside it, and a different marker in the foreign cwd's `CLAUDE.md`. Invoke `$bitwize-music:session-start` in a fresh conversation without disclosing either marker. The configured marker appeared, the cwd marker did not, the configured album was reported, and the actual health call selected `runtime="codex"`. |
| Missing overrides | Rename the configured overrides directory away and start another fresh conversation. Startup still reported the configured album and optional override files as absent, selected Codex health diagnostics, and included neither marker. |

No failed MCP calls occurred. Synthetic album/track bytes remained unchanged,
and the temporary authentication copy was explicitly removed. The successful
configuration and overrides cases required no additional product changes or
regression tests. This covers conversational setup, a specified edit, and the
two override cases; it does not establish every optional/reset/overwrite branch
or a native question-widget interaction.

The same source revision also passed `make check` (exit 0): Ruff, the scoped
encoding check, Bandit, mypy (72 source files), and pytest (4683 passed,
13 skipped, coverage 90.05%). The optional `numba` import now has type
`ModuleType | None`, resolving both existing mypy errors without changing the
compression algorithm. All six existing compressor tests passed separately;
a one-off forced-missing-numba check selected the fallback and matched the JIT
envelope and stereo compression results within `rtol=atol=1e-12`.

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
- [ ] CLAUDE.md is recognized (check session start behavior)
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
