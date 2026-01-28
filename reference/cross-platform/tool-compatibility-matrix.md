# Tool Compatibility Matrix

What works on each platform for the Claude AI Music Skills plugin.

---

## Platform Support Overview

| Platform | Support Level | Notes |
|----------|---------------|-------|
| **macOS** | Full | Primary development platform |
| **Linux** (native) | Full | Tested on Ubuntu 22.04+ |
| **WSL2** | Full | See [WSL Setup Guide](wsl-setup-guide.md) |
| **WSL1** | Partial | Works but slower, some limitations |
| **Windows (native)** | Not Supported | Use WSL |

---

## Feature Compatibility Matrix

### Core Features (No Dependencies)

| Feature | macOS | Linux | WSL2 | Requirements |
|---------|-------|-------|------|--------------|
| Album planning | Yes | Yes | Yes | None |
| Lyric writing | Yes | Yes | Yes | None |
| Suno prompts | Yes | Yes | Yes | None |
| Research skills | Yes | Yes | Yes | None |
| Album validation | Yes | Yes | Yes | None |
| Configuration | Yes | Yes | Yes | None |

### Clipboard Skill

| Platform | Utility | Install |
|----------|---------|---------|
| macOS | `pbcopy` | Built-in |
| Linux | `xclip` | `sudo apt install xclip` |
| Linux (alt) | `xsel` | `sudo apt install xsel` |
| WSL2 | `clip.exe` | Built-in (Windows interop) |

**Notes**:
- SSH sessions: Clipboard unavailable (use X11 forwarding or copy manually)
- Headless Linux: xclip requires X11 display, use xsel with `--clipboard`

### Audio Mastering

| Feature | macOS | Linux | WSL2 | Requirements |
|---------|-------|-------|------|--------------|
| LUFS analysis | Yes | Yes | Yes | Python packages |
| Track mastering | Yes | Yes | Yes | Python packages |
| Reference mastering | Yes | Yes | Yes | Python packages |
| Genre presets | Yes | Yes | Yes | Python packages |

**Python Requirements**:

```bash
pip install matchering pyloudnorm scipy numpy soundfile
```

**System Requirements**:

| Platform | Additional Packages |
|----------|---------------------|
| macOS | None (soundfile bundles libsndfile) |
| Linux | `sudo apt install libsndfile1` |
| WSL2 | `sudo apt install libsndfile1` |

### Promo Video Generation

| Feature | macOS | Linux | WSL2 | Requirements |
|---------|-------|-------|------|--------------|
| Generate promos | Yes | Yes | Yes | ffmpeg, Python |
| All visualizations | Yes | Yes | Yes | ffmpeg with filters |
| Album sampler | Yes | Yes | Yes | ffmpeg, Python |
| Smart segments | Yes | Yes | Yes | + librosa, numpy |

**Requirements**:

```bash
# System
# macOS: brew install ffmpeg
# Linux/WSL: sudo apt install ffmpeg

# Python
pip install pillow pyyaml
pip install librosa numpy  # Optional: for smart segment selection
```

**Required ffmpeg Filters**:

```bash
# Verify these filters are available
ffmpeg -filters 2>/dev/null | grep -E "showwaves|showfreqs|drawtext|gblur"
```

### Document Hunter (Playwright)

| Feature | macOS | Linux | WSL2 | Requirements |
|---------|-------|-------|------|--------------|
| Browser automation | Yes | Yes | Partial | Playwright + Chromium |
| PDF downloads | Yes | Yes | Partial | Playwright + Chromium |

**Requirements**:

```bash
pip install playwright
playwright install chromium

# Linux/WSL only: install system dependencies
playwright install-deps chromium
```

**WSL Notes**:
- Works in headless mode
- GUI mode requires WSLg (Windows 11) or X11 server (Windows 10)

### Sheet Music Generation

| Feature | macOS | Linux | WSL2 | Requirements |
|---------|-------|-------|------|--------------|
| Auto transcription | Yes | Yes | Partial | AnthemScore |
| PDF export | Yes | Yes | Partial | AnthemScore |
| Notation editing | Yes | Yes | Partial | MuseScore |
| Songbook creation | Yes | Yes | Yes | pypdf, reportlab |

**Software Requirements**:

| Tool | macOS | Linux | WSL2 |
|------|-------|-------|------|
| AnthemScore | Native | Native | Run in Windows |
| MuseScore | Native | Native | WSLg or Windows |

**Notes**:
- AnthemScore: $42 (Professional edition), Windows/Mac/Linux
- MuseScore: Free, open source
- WSL2: Run GUI apps in Windows, use WSL for CLI scripts

---

## Python Version Requirements

| Feature | Minimum Python | Recommended |
|---------|----------------|-------------|
| Core plugin | 3.8 | 3.10+ |
| Audio mastering | 3.8 | 3.10+ |
| Promo videos | 3.8 | 3.10+ |
| Document hunter | 3.8 | 3.10+ |
| Sheet music tools | 3.8 | 3.10+ |

---

## External Tool Requirements

### ffmpeg

| Feature | Required |
|---------|----------|
| Promo videos | Yes |
| Video encoding | Yes |
| Audio extraction | Optional |

**Install**:

```bash
# macOS
brew install ffmpeg

# Linux/WSL
sudo apt install ffmpeg
```

### AnthemScore

| Feature | Required |
|---------|----------|
| Audio-to-sheet-music | Yes |
| CLI batch transcription | Yes |

**Location by Platform**:

| Platform | Path |
|----------|------|
| macOS | `/Applications/AnthemScore.app/Contents/MacOS/AnthemScore` |
| Linux | `~/AnthemScore/AnthemScore` or as installed |
| WSL | Run in Windows, copy output to WSL |

### MuseScore

| Feature | Required |
|---------|----------|
| Notation editing | Yes |
| PDF re-export | Yes |

**Install**:

```bash
# macOS
brew install --cask musescore

# Linux (may be older version)
sudo apt install musescore

# For latest version, download from musescore.org
```

---

## Known Limitations by Platform

### macOS

- None significant

### Linux

- Clipboard requires X11 display (or use xsel for headless)
- Some older distros may have outdated ffmpeg

### WSL2

- GUI apps require Windows 11 (WSLg) or X11 server on Windows 10
- File operations on `/mnt/` slower than native filesystem
- Some Playwright features may require additional setup
- AnthemScore/MuseScore: Run in Windows, use CLI tools in WSL

### WSL1

- Slower than WSL2
- Limited Linux kernel compatibility
- Some npm/Python packages may have issues
- Recommend upgrading to WSL2

---

## Quick Dependency Check

Run this to verify your setup:

```bash
# Python
python3 --version

# Clipboard
if command -v pbcopy >/dev/null; then echo "macOS clipboard: OK"
elif command -v clip.exe >/dev/null; then echo "WSL clipboard: OK"
elif command -v xclip >/dev/null; then echo "Linux clipboard: OK"
else echo "Clipboard: MISSING"; fi

# ffmpeg
ffmpeg -version 2>/dev/null | head -1 || echo "ffmpeg: MISSING"

# Python packages (if venv activated)
python3 -c "import soundfile" 2>/dev/null && echo "soundfile: OK" || echo "soundfile: MISSING"
python3 -c "import matchering" 2>/dev/null && echo "matchering: OK" || echo "matchering: MISSING"
python3 -c "import PIL" 2>/dev/null && echo "pillow: OK" || echo "pillow: MISSING"
```

---

## See Also

- [WSL Setup Guide](wsl-setup-guide.md) - Complete WSL2 configuration
- [Mastering Workflow](/reference/mastering/mastering-workflow.md) - Audio processing
- [Promo Workflow](/reference/promotion/promo-workflow.md) - Video generation
- [Sheet Music Workflow](/reference/sheet-music/workflow.md) - Transcription
