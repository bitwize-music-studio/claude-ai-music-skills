# WSL2 Setup Guide for Claude AI Music Skills

Complete guide for running the plugin on Windows using WSL2 (Windows Subsystem for Linux).

---

## Prerequisites

- Windows 10 version 2004+ or Windows 11
- WSL2 enabled (WSL1 works but WSL2 recommended)
- Ubuntu 22.04 LTS or newer (recommended distro)

---

## Initial WSL2 Setup

### Install WSL2

```powershell
# In PowerShell (Admin)
wsl --install
# Restart computer when prompted
```

### Verify Installation

```bash
# In WSL terminal
wsl --version
cat /etc/os-release
```

---

## Installing Required Tools

### Core Dependencies

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Python 3.8+ (usually pre-installed)
python3 --version
pip3 --version

# If pip missing
sudo apt install python3-pip -y
```

### Audio Mastering Dependencies

```bash
# Create virtual environment
mkdir -p ~/.bitwize-music
python3 -m venv ~/.bitwize-music/venv
source ~/.bitwize-music/venv/bin/activate

# Install Python packages
pip install matchering pyloudnorm scipy numpy soundfile

# Install system audio library (required by soundfile)
sudo apt install libsndfile1 -y
```

### Document Hunter Dependencies (Playwright)

```bash
pip install playwright
playwright install chromium

# Install system dependencies for Chromium
playwright install-deps chromium
```

### Promo Video Dependencies

```bash
# Install ffmpeg
sudo apt install ffmpeg -y

# Verify filters available
ffmpeg -filters 2>/dev/null | grep -E "showwaves|drawtext"

# Python packages
pip install pillow pyyaml
```

---

## Path Configuration

### Windows/WSL Path Interop

WSL can access Windows files via `/mnt/c/`, `/mnt/d/`, etc.

**Recommended setup**: Keep content in WSL filesystem for better performance.

```yaml
# ~/.bitwize-music/config.yaml
paths:
  content_root: ~/bitwize-music           # WSL filesystem (fast)
  audio_root: ~/bitwize-music/audio       # WSL filesystem
  documents_root: ~/bitwize-music/documents
```

**Alternative**: Access Windows folders (slower but convenient):

```yaml
paths:
  content_root: /mnt/c/Users/YourName/Music/bitwize-music
  audio_root: /mnt/c/Users/YourName/Music/bitwize-music/audio
```

### Path Translation

| Windows Path | WSL Path |
|--------------|----------|
| `C:\Users\Name\Music` | `/mnt/c/Users/Name/Music` |
| `D:\Projects` | `/mnt/d/Projects` |
| `~` in WSL | `/home/username` |

---

## Clipboard Setup

WSL uses `clip.exe` to copy to Windows clipboard.

### Verify Clipboard Works

```bash
# Test clipboard
echo "test" | clip.exe

# Then Ctrl+V in any Windows app to verify
```

The `/bitwize-music:clipboard` skill auto-detects WSL and uses `clip.exe`.

### Troubleshooting Clipboard

If `clip.exe` not found:

```bash
# Check if Windows interop is enabled
cat /proc/sys/fs/binfmt_misc/WSLInterop

# If missing, add to /etc/wsl.conf:
[interop]
enabled = true
appendWindowsPath = true

# Then restart WSL
wsl --shutdown  # Run in PowerShell
```

---

## Audio File Handling

### Performance Considerations

**Best practice**: Work with audio files in WSL filesystem (`~/`), not Windows mounts (`/mnt/`).

```bash
# Copy audio files to WSL
cp /mnt/c/Users/Name/Downloads/*.wav ~/bitwize-music/audio/artist/album/

# Work on them in WSL
source ~/.bitwize-music/venv/bin/activate
python3 tools/mastering/master_tracks.py ~/bitwize-music/audio/artist/album/
```

### Moving Mastered Files to Windows

```bash
# Copy back to Windows when done
cp ~/bitwize-music/audio/artist/album/mastered/*.wav /mnt/c/Users/Name/Music/

# Or use Windows Explorer to access WSL files:
# Navigate to: \\wsl$\Ubuntu\home\username\bitwize-music\
```

### Accessing WSL Files from Windows

Windows Explorer path: `\\wsl$\Ubuntu\home\<username>\`

---

## Common WSL-Specific Issues

### Issue: Slow File Operations on /mnt/

**Symptom**: Mastering or analysis takes much longer than expected.

**Cause**: Cross-filesystem operations between WSL and Windows are slow.

**Fix**: Move files to WSL filesystem:

```bash
# Instead of working directly on /mnt/c/...
cp -r /mnt/c/Users/Name/album/ ~/working/album/
# Process in WSL
# Copy back when done
```

### Issue: Permission Denied on /mnt/

**Symptom**: Can't write to Windows folders from WSL.

**Fix**: Check folder permissions in Windows, or use sudo (not recommended).

Better: Work in WSL filesystem and copy results to Windows.

### Issue: soundfile Import Error

**Symptom**: `ImportError: libsndfile not found`

**Fix**:

```bash
sudo apt install libsndfile1 libsndfile1-dev -y
pip uninstall soundfile && pip install soundfile
```

### Issue: Playwright Browser Fails

**Symptom**: Chromium crashes or can't start.

**Fix**:

```bash
# Install all dependencies
playwright install-deps chromium

# If still failing, try headless mode explicitly
# (document-hunter skill handles this automatically)
```

### Issue: GUI Apps Won't Run

**Symptom**: MuseScore or AnthemScore won't launch.

**Note**: WSL2 on Windows 11 supports GUI apps (WSLg). Windows 10 requires workarounds.

**Windows 11 fix**:

```bash
# Ensure WSLg is enabled
sudo apt install x11-apps -y
xclock  # Should open a window

# Install GUI apps
sudo apt install musescore -y
```

**Windows 10 alternative**: Run GUI apps in Windows, use WSL for CLI tools only.

---

## Recommended WSL Configuration

Create `/etc/wsl.conf`:

```ini
[interop]
enabled = true
appendWindowsPath = true

[automount]
enabled = true
options = "metadata,umask=22,fmask=11"

[network]
generateResolvConf = true
```

Then restart WSL:

```powershell
# In PowerShell
wsl --shutdown
```

---

## Quick Setup Checklist

- [ ] WSL2 installed with Ubuntu 22.04+
- [ ] Python 3.8+ and pip installed
- [ ] Virtual environment created at `~/.bitwize-music/venv/`
- [ ] Audio dependencies installed (matchering, pyloudnorm, etc.)
- [ ] libsndfile1 installed for audio processing
- [ ] ffmpeg installed for promo videos
- [ ] Config file at `~/.bitwize-music/config.yaml` with WSL paths
- [ ] Clipboard working (`echo test | clip.exe`)
- [ ] (Optional) Playwright + Chromium for document-hunter

---

## See Also

- [Tool Compatibility Matrix](tool-compatibility-matrix.md) - What works on each platform
- [Mastering Workflow](/reference/mastering/mastering-workflow.md) - Audio mastering guide
- [Promo Workflow](/reference/promotion/promo-workflow.md) - Video generation
