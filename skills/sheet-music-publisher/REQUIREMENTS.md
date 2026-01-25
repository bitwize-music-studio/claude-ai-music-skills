# Sheet Music Publisher - Software Requirements

This document lists all external software and dependencies needed for sheet music generation.

## Required Software

### 1. AnthemScore (Audio Transcription)

**Purpose**: Converts audio files (WAV) to sheet music notation

**Cost**: $31-107 (one-time purchase, no subscription)
- **Lite**: $31 - Basic transcription, no editing
- **Professional**: $42 - Full editing + CLI ← **Recommended**
- **Studio**: $107 - Lifetime updates

**Free Trial**:
- 30 seconds per song
- 100 total transcriptions
- All features available

**Download**: [https://www.lunaverus.com/](https://www.lunaverus.com/)

**Platforms**:
- macOS (10.13+)
- Windows (7, 8, 10, 11)
- Linux (Ubuntu, Fedora, Arch)

**Installation Locations**:
```
macOS:    /Applications/AnthemScore.app/Contents/MacOS/AnthemScore
Linux:    /usr/bin/anthemscore or /usr/local/bin/anthemscore
Windows:  C:\Program Files\AnthemScore\AnthemScore.exe
```

**Why Professional Edition?**
- CLI access (required for batch processing)
- Spectrogram editing
- Better accuracy controls
- Only $11 more than Lite

---

### 2. MuseScore (Notation Editing)

**Purpose**: Edit transcriptions, fix errors, export final PDFs

**Cost**: **FREE** (open source)

**Download**: [https://musescore.org/](https://musescore.org/)

**Platforms**:
- macOS (10.12+)
- Windows (7, 8, 10, 11)
- Linux (AppImage, Ubuntu/Debian, Fedora, Arch)

**Installation Locations**:
```
macOS:    /Applications/MuseScore 4.app/Contents/MacOS/mscore
          /Applications/MuseScore 3.app/Contents/MacOS/mscore
Linux:    /usr/bin/musescore or /usr/bin/mscore
Windows:  C:\Program Files\MuseScore 4\bin\MuseScore4.exe
```

**Current Versions**:
- MuseScore 4 (latest, recommended)
- MuseScore 3 (stable, still supported)

**Why Required?**
- Re-export PDFs after title cleanup
- Manual polishing (fix wrong notes, add dynamics)
- Professional formatting

---

## Python Dependencies

**For songbook creation only** (optional feature):

```bash
pip install pypdf reportlab pyyaml
```

**Breakdown**:
- `pypdf` - PDF manipulation (combine tracks into songbook)
- `reportlab` - Generate title page, copyright page, TOC
- `pyyaml` - Read config file for auto-detection

**Not needed if you only want individual track PDFs.**

---

## Installation Guide

### Quick Setup (macOS)

```bash
# 1. Install AnthemScore
# Download from https://www.lunaverus.com/ and install

# 2. Install MuseScore (via Homebrew)
brew install --cask musescore

# 3. Install Python dependencies
pip install pypdf reportlab pyyaml

# 4. Verify installation
ls -l "/Applications/AnthemScore.app/Contents/MacOS/AnthemScore"
ls -l "/Applications/MuseScore 4.app/Contents/MacOS/mscore"
python3 -c "import pypdf, reportlab, yaml; print('✓ All dependencies installed')"
```

### Quick Setup (Linux - Ubuntu/Debian)

```bash
# 1. Install AnthemScore
# Download from https://www.lunaverus.com/ and install

# 2. Install MuseScore
sudo apt update
sudo apt install musescore

# 3. Install Python dependencies
pip install pypdf reportlab pyyaml

# 4. Verify installation
which anthemscore
which musescore
python3 -c "import pypdf, reportlab, yaml; print('✓ All dependencies installed')"
```

### Quick Setup (Windows)

```powershell
# 1. Install AnthemScore
# Download from https://www.lunaverus.com/ and install

# 2. Install MuseScore
# Download from https://musescore.org/ and install

# 3. Install Python dependencies
pip install pypdf reportlab pyyaml

# 4. Verify installation (PowerShell)
Test-Path "C:\Program Files\AnthemScore\AnthemScore.exe"
Test-Path "C:\Program Files\MuseScore 4\bin\MuseScore4.exe"
python -c "import pypdf, reportlab, yaml; print('✓ All dependencies installed')"
```

---

## What Each Tool Does

### Workflow Overview

```
1. WAV file
   ↓
2. AnthemScore (automated transcription)
   ↓
3. PDF + MusicXML generated
   ↓
4. MuseScore (optional manual polish)
   ↓
5. Title cleanup (MuseScore CLI re-exports PDFs)
   ↓
6. create_songbook.py (Python: combines PDFs)
   ↓
7. Final songbook PDF (KDP-ready)
```

### Tool Responsibilities

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| AnthemScore | WAV audio | PDF + MusicXML | Automated transcription |
| MuseScore (GUI) | MusicXML | Polished MusicXML | Fix errors, add dynamics |
| MuseScore (CLI) | MusicXML | PDF | Re-export after title cleanup |
| create_songbook.py | Multiple PDFs | Combined PDF | KDP-ready songbook |

---

## Cost Summary

| Item | Cost | Required? |
|------|------|-----------|
| AnthemScore Professional | $42 (one-time) | Yes |
| MuseScore | Free | Yes |
| Python dependencies | Free | Only for songbooks |
| **Total** | **$42** | **Minimum** |

**Alternatives:**
- Use AnthemScore free trial (limited to 30 sec/song, 100 songs total)
- Skip songbook creation (saves Python dependencies)

---

## Troubleshooting

### "AnthemScore not found"

**Check installation:**
```bash
# macOS
ls -l "/Applications/AnthemScore.app/Contents/MacOS/AnthemScore"

# Linux
which anthemscore

# Windows
where anthemscore
```

**If not found:**
1. Verify AnthemScore is installed
2. Check installation location matches expected path
3. Add to PATH if installed to custom location

### "MuseScore not found"

**Check installation:**
```bash
# macOS
ls -l "/Applications/MuseScore 4.app/Contents/MacOS/mscore"

# Linux
which musescore

# Windows
where mscore
```

**If not found:**
1. Verify MuseScore is installed
2. Check version (4 or 3)
3. Add to PATH if needed

### "Python dependencies missing"

```bash
# Install
pip install pypdf reportlab pyyaml

# Verify
python3 -c "import pypdf; import reportlab; import yaml; print('OK')"
```

---

## Optional: Add Custom Paths to Config

If you installed software to non-standard locations, you can add custom paths to `~/.bitwize-music/config.yaml`:

```yaml
# Future enhancement (not yet implemented)
tools:
  anthemscore: "/custom/path/to/AnthemScore"
  musescore: "/custom/path/to/mscore"
```

**Current behavior**: Scripts auto-detect standard install locations. If you have a non-standard install, add the executable to your PATH.

---

## Summary

**Minimum setup for sheet music generation:**
1. Purchase AnthemScore Professional ($42)
2. Install MuseScore (free)
3. Install Python dependencies (free): `pip install pypdf reportlab pyyaml`

**Total cost: $42 one-time**

**Free trial option**: Use AnthemScore free trial for testing (30 sec/song limit)

**Ready to use**: Once installed, the `/bitwize-music:sheet-music-publisher` skill auto-detects everything.
