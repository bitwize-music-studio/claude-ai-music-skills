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
| **Windows (native)** | Core (best-effort) | MCP server, state cache, non-audio workflow (albums, tracks, ideas, research docs, status tracking), and the ffmpeg audio pipeline (mixing/mastering/codec preview) — the full test suite runs on windows-latest in CI. Promo video works but its CI coverage is mock-only (see below). AnthemScore/MuseScore (sheet music) not supported natively; use WSL2 |

> **What "CI-tested" does and does not mean here.** The full suite, the MCP stdio
> boot check, and the ffmpeg-gated *audio* tests (ADM validation, codec preview,
> mastering samples) genuinely execute on windows-latest. Promo **video** is
> different: all 62 of its tests mock `subprocess`, so no real render happens in
> CI on any OS. That gap hid a total failure — until the filtergraph escaping fix,
> every promo video and sampler clip failed on native Windows, because ffmpeg ate
> the backslashes in an unquoted `fontfile=C:\Windows\...`. It is now confirmed
> working by rendering a real frame on a windows-latest runner, but treat the
> "works" below as verified-by-hand rather than continuously guarded.

---

## Feature Compatibility Matrix

### Core Features (No Dependencies)

| Feature | macOS | Linux | WSL2 | Windows (native) | Requirements |
|---------|-------|-------|------|------------------|--------------|
| Album planning | Yes | Yes | Yes | Yes | None |
| Lyric writing | Yes | Yes | Yes | Yes | None |
| Suno prompts | Yes | Yes | Yes | Yes | None |
| Research skills | Yes | Yes | Yes | Yes | None |
| Album validation | Yes | Yes | Yes | Yes | None |
| Configuration | Yes | Yes | Yes | Yes | None |

These have no external dependencies and are covered by the full suite plus the
MCP stdio boot check on windows-latest.

### Clipboard Skill

| Platform | Utility | Install |
|----------|---------|---------|
| macOS | `pbcopy` | Built-in |
| Linux | `xclip` | `sudo apt install xclip` |
| Linux (alt) | `xsel` | `sudo apt install xsel` |
| WSL2 | `clip.exe` | Built-in (Windows interop) |
| Windows (native) | `clip.exe` — **unverified** | Built-in, but the skill is a bash snippet |

**Notes**:
- SSH sessions: Clipboard unavailable (use X11 forwarding or copy manually)
- Headless Linux: xclip requires X11 display, use xsel with `--clipboard`
- Windows (native): `clip.exe` exists, but the clipboard skill is written as a
  bash snippet, so it depends on a bash being present (e.g. Git Bash). Not
  covered by any test — treat as unverified rather than supported.

### Audio Mastering

| Feature | macOS | Linux | WSL2 | Windows (native) | Requirements |
|---------|-------|-------|------|------------------|-----------------|
| LUFS analysis | Yes | Yes | Yes | Yes | Python packages |
| Track mastering | Yes | Yes | Yes | Yes | Python packages |
| Reference mastering | Yes | Yes | Yes | Yes | Python packages |
| Genre presets | Yes | Yes | Yes | Yes | Python packages |

The ffmpeg-gated audio tests (ADM validation, codec preview, mastering samples)
really execute on windows-latest — ffmpeg is installed there and CI asserts both
`ffmpeg` and `ffprobe` resolve on PATH, so these cannot silently degrade to skips.

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

| Feature | macOS | Linux | WSL2 | Windows (native) | Requirements |
|---------|-------|-------|------|------------------|---------------------|
| Generate promos | Yes | Yes | Yes | Yes¹ | ffmpeg, Python |
| All visualizations | Yes | Yes | Yes | Yes¹ | ffmpeg with filters |
| Album sampler | Yes | Yes | Yes | Yes¹ | ffmpeg, Python |
| Smart segments | Yes | Yes | Yes | Yes¹ | + librosa, numpy |

¹ Verified by rendering a real frame on a windows-latest runner, **not** by
continuous CI — all 62 promo-video tests mock `subprocess`, so no real render is
guarded on any OS. Two Windows-specific fixes were required to get here, and
neither would have been caught by the existing tests:

- `find_font()` had no Windows candidates, so it returned `None` on every
  Windows host and there was no font to draw with.
- Paths were interpolated into the `drawtext` filtergraph unescaped. ffmpeg
  treats `:` as its option separator and `\` as an escape, so
  `fontfile=C:\Windows\Fonts\arialbd.ttf` was mangled to `C:WindowsFontsarialbd.ttf`
  and the whole graph was rejected. Paths now go through `escape_filter_path()`,
  which emits `'C\:/Windows/Fonts/arialbd.ttf'` — quoting alone is not enough,
  because the graph splits on `:` before quotes are processed.

**Requirements**:

```bash
# System
# macOS: brew install ffmpeg
# Linux/WSL: sudo apt install ffmpeg
# Windows (native): choco install ffmpeg

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

| Feature | macOS | Linux | WSL2 | Windows (native) | Requirements |
|---------|-------|-------|------|------------------|-----------------------|
| Browser automation | Yes | Yes | Partial | Untested | Playwright + Chromium |
| PDF downloads | Yes | Yes | Partial | Untested | Playwright + Chromium |

Playwright supports Windows natively, so this is expected to work — but nothing
in the Python suite exercises it on any platform, so it is marked untested rather
than supported.

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

| Feature | macOS | Linux | WSL2 | Windows (native) | Requirements |
|---------|-------|-------|------|------------------|------------------|
| Auto transcription | Yes | Yes | Partial | No — use WSL2 | AnthemScore |
| PDF export | Yes | Yes | Partial | No — use WSL2 | AnthemScore |
| Notation editing | Yes | Yes | Partial | No — use WSL2 | MuseScore |
| Songbook creation | Yes | Yes | Yes | Yes | pypdf, reportlab |

Songbook creation is pure Python (pypdf/reportlab) and runs anywhere. The other
three shell out to AnthemScore/MuseScore, which stay WSL2-recommended by the
support-tier decision. The discovery code *does* know the Windows install
locations, but no runner has either tool, so those branches are exercised only
by tests that patch `platform.system()` — real native-Windows sheet music is
unproven.

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
| Core plugin | 3.10+ (per requirements.txt) | 3.10+ |
| Audio mastering | 3.10+ (per requirements.txt) | 3.10+ |
| Promo videos | 3.10+ (per requirements.txt) | 3.10+ |
| Document hunter | 3.10+ (per requirements.txt) | 3.10+ |
| Sheet music tools | 3.10+ (per requirements.txt) | 3.10+ |

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

# Windows (native) — same mechanism CI uses
choco install ffmpeg
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
