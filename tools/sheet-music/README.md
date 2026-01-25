# Sheet Music Tools

Python scripts for automated sheet music generation and songbook creation.

## Overview

These tools work together to convert mastered audio (WAV files) into publishing-ready sheet music PDFs and KDP songbooks.

## Prerequisites

### External Software
- **AnthemScore** ($42 Professional) - [lunaverus.com](https://www.lunaverus.com/)
- **MuseScore** (Free) - [musescore.org](https://musescore.org/)

### Python Dependencies
```bash
pip install pypdf reportlab pyyaml
```

See `../../skills/sheet-music-publisher/REQUIREMENTS.md` for detailed setup instructions.

---

## Scripts

### 1. transcribe.py

**Purpose**: Batch convert WAV files to sheet music using AnthemScore CLI

**Usage**:
```bash
# By album name (reads config)
python3 transcribe.py shell-no

# By path
python3 transcribe.py /path/to/mastered/

# Single file
python3 transcribe.py track.wav

# Options
python3 transcribe.py shell-no --pdf-only      # Skip MusicXML
python3 transcribe.py shell-no --xml-only      # Skip PDF
python3 transcribe.py shell-no --midi          # Also generate MIDI
python3 transcribe.py shell-no --treble        # Treble clef only
python3 transcribe.py shell-no --dry-run       # Preview only
```

**Output**:
- PDF files (publishing-ready)
- MusicXML files (editable in MuseScore)
- Optional: MIDI files (playback verification)

**Location**: `{audio_root}/{artist}/{album}/sheet-music/`

**Features**:
- Cross-platform OS detection (macOS, Linux, Windows)
- Auto-detects AnthemScore installation
- Config-aware (resolves album names via ~/.bitwize-music/config.yaml)
- Batch processing (all WAVs in directory)
- Progress reporting
- Graceful error handling with install instructions

**Performance**: ~30-60 seconds per track

---

### 2. fix_titles.py

**Purpose**: Strip track number prefixes from MusicXML titles and re-export PDFs

**Why needed**: AnthemScore uses filenames as titles, which includes track numbers (e.g., "01 - Song Name"). This script removes them for clean, professional PDFs.

**Usage**:
```bash
# Fix titles and re-export PDFs
python3 fix_titles.py /path/to/sheet-music/

# Preview only
python3 fix_titles.py /path/to/sheet-music/ --dry-run

# Only fix XML, skip PDF export
python3 fix_titles.py /path/to/sheet-music/ --xml-only
```

**What it does**:
1. Reads each MusicXML file
2. Finds `<work-title>` tag
3. Strips track number prefix (e.g., "01 - ", "02. ", "1 - ")
4. Saves updated MusicXML
5. Re-exports PDF via MuseScore CLI

**Before**:
```xml
<work-title>01 - Ocean of Tears</work-title>
```

**After**:
```xml
<work-title>Ocean of Tears</work-title>
```

**Features**:
- Cross-platform MuseScore detection
- Batch processing (all XML files in directory)
- Only processes files starting with digits
- Safe dry-run mode
- Clear progress reporting

---

### 3. create_songbook.py

**Purpose**: Combine individual track PDFs into a KDP-ready songbook

**Usage**:
```bash
# Basic (auto-detects metadata from config)
python3 create_songbook.py /path/to/sheet-music/ \
  --title "Album Name Songbook"

# Full options
python3 create_songbook.py /path/to/sheet-music/ \
  --title "Shell No Songbook" \
  --artist "bitwize" \
  --cover /path/to/album.png \
  --website "bitwizemusic.com" \
  --page-size letter \
  --year 2025 \
  --section-headers
```

**Auto-detected (from config)**:
- `--artist` → `config['artist']['name']`
- `--cover` → `{audio_root}/{artist}/{album}/album.png`
- `--website` → `config['urls']['soundcloud']` (or other URLs)
- `--page-size` → `config['sheet_music']['page_size']`

**Output**: Combined PDF with:
- Title page (with album art if available)
- Copyright page (legal boilerplate)
- Table of contents (track names + page numbers)
- All tracks in order
- Professional formatting

**Page Sizes**:
- `letter` (8.5×11) - Standard US
- `9x12` - Professional sheet music
- `6x9` - Compact/travel

**Features**:
- Config integration (auto-detects artist, cover art, website)
- Auto-excludes existing songbook PDFs (only processes track PDFs)
- Leader dots in TOC
- Clean track name display (strips numbers)
- Optional section headers between tracks
- KDP-ready output

**Output Location**: `{source_dir}/{Title}.pdf`

Example: `/path/to/sheet-music/Shell_No_Songbook.pdf`

---

## Complete Workflow

### Step 1: Transcribe
```bash
python3 transcribe.py shell-no
# Output: 10 PDFs + 10 XMLs in {audio_root}/bitwize/shell-no/sheet-music/
```

### Step 2: Polish (Optional)
```bash
# Open XMLs in MuseScore, manually fix errors, add dynamics
open -a "MuseScore 4" {audio_root}/bitwize/shell-no/sheet-music/*.xml
```

### Step 3: Clean Titles
```bash
python3 fix_titles.py {audio_root}/bitwize/shell-no/sheet-music/
# Updates XML titles, re-exports PDFs
```

### Step 4: Create Songbook
```bash
python3 create_songbook.py {audio_root}/bitwize/shell-no/sheet-music/ \
  --title "Shell No Songbook"
# Output: Shell_No_Songbook.pdf
```

---

## Integration with Skill

These scripts are called by the `/bitwize-music:sheet-music-publisher` skill, which:
1. Verifies software installation
2. Guides user through track selection
3. Runs transcribe.py
4. Prompts for MuseScore polish (optional)
5. Runs fix_titles.py
6. Prompts for songbook creation (optional)
7. Runs create_songbook.py if requested

**Recommended**: Use the skill for guided workflow. Use scripts directly for advanced/custom usage.

---

## File Naming Convention

### Input (Mastered Audio)
```
{audio_root}/{artist}/{album}/
├── 01-ocean-of-tears.wav
├── 02-run-away.wav
└── 03-t-day-beach.wav
```

### Output (Sheet Music)
```
{audio_root}/{artist}/{album}/sheet-music/
├── 01-ocean-of-tears.pdf
├── 01-ocean-of-tears.xml
├── 02-run-away.pdf
├── 02-run-away.xml
├── 03-t-day-beach.pdf
├── 03-t-day-beach.xml
└── Shell_No_Songbook.pdf  (combined)
```

**Key points**:
- Source WAVs: Keep track numbers in filename
- Individual PDFs: Track numbers preserved in filename
- XML titles: Track numbers stripped (clean display)
- Songbook: No track numbers in titles (professional)

---

## Troubleshooting

### AnthemScore Not Found
```bash
# Check installation
ls -l "/Applications/AnthemScore.app/Contents/MacOS/AnthemScore"  # macOS
which anthemscore                                                  # Linux
where anthemscore                                                  # Windows
```

**Fix**: Install AnthemScore from [lunaverus.com](https://www.lunaverus.com/)

### MuseScore Not Found
```bash
# Check installation
ls -l "/Applications/MuseScore 4.app/Contents/MacOS/mscore"  # macOS
which musescore                                               # Linux
where mscore                                                  # Windows
```

**Fix**: Install MuseScore from [musescore.org](https://musescore.org/)

### Python Dependencies Missing
```bash
pip install pypdf reportlab pyyaml
```

### Album Name Not Resolved
```bash
# Make sure config exists
cat ~/.bitwize-music/config.yaml

# Verify paths
# Check: paths.audio_root, artist.name
```

**Fallback**: Use direct path instead of album name:
```bash
python3 transcribe.py /full/path/to/mastered/
```

---

## Advanced Usage

### Transcribe Only Specific Tracks
```bash
# Create temp directory with just the WAVs you want
mkdir temp-transcribe
cp {audio_root}/{artist}/{album}/01-track.wav temp-transcribe/
cp {audio_root}/{artist}/{album}/05-track.wav temp-transcribe/
python3 transcribe.py temp-transcribe/
```

### Custom Output Location
```bash
python3 transcribe.py shell-no --output /custom/output/path/
```

### Generate Only MusicXML (Skip PDF)
```bash
python3 transcribe.py shell-no --xml-only
# Faster, if you plan to edit everything in MuseScore anyway
```

### Songbook Without Cover Art
```bash
python3 create_songbook.py /path/to/sheet-music/ \
  --title "Album Songbook" \
  --artist "Artist" \
  # No --cover flag = text-only title page
```

---

## Cross-Platform Notes

### macOS
- AnthemScore: `/Applications/AnthemScore.app/...`
- MuseScore: `/Applications/MuseScore 4.app/...`
- Homebrew installs may be in `/opt/homebrew/bin/`

### Linux
- AnthemScore: `/usr/bin/anthemscore` or `/usr/local/bin/anthemscore`
- MuseScore: `/usr/bin/musescore` or `/usr/bin/mscore`
- Package manager installs detected automatically

### Windows
- AnthemScore: `C:\Program Files\AnthemScore\AnthemScore.exe`
- MuseScore: `C:\Program Files\MuseScore 4\bin\MuseScore4.exe`
- Use PowerShell or Command Prompt

**All scripts auto-detect OS and find software** - no manual configuration needed for standard installs.

---

## See Also

- **Complete Workflow Guide**: `../../reference/sheet-music/workflow.md`
- **AnthemScore CLI Reference**: `../../skills/sheet-music-publisher/anthemscore-reference.md`
- **MuseScore Tips**: `../../skills/sheet-music-publisher/musescore-reference.md`
- **KDP Publishing Guide**: `../../skills/sheet-music-publisher/publishing-guide.md`
- **Requirements & Setup**: `../../skills/sheet-music-publisher/REQUIREMENTS.md`
