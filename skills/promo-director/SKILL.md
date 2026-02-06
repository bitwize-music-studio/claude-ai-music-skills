---
name: promo-director
description: Generates 15-second vertical promo videos for social media from mastered audio. Use after mastering is complete and before release, when the user wants social media content.
model: claude-sonnet-4-5-20250929
prerequisites:
  - mastering-engineer
  - album-art-director
allowed-tools:
  - Read
  - Bash
  - Glob
requirements:
  external:
    - name: ffmpeg
      purpose: Video generation and audio visualization
      install: "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
      notes: "Requires showwaves, showfreqs, drawtext, gblur filters"
  python:
    - pillow
    - librosa
    - pyyaml
---

# Promo Director Skill

Generate professional promo videos for social media from mastered audio. Creates 15-second vertical videos (9:16, 1080x1920) optimized for Instagram Reels, Twitter, and TikTok.

## Purpose

After mastering audio, generate promotional videos that combine:
- Album artwork
- Audio waveform visualization (9 styles available)
- Track title + artist name
- Automatic color scheme extracted from artwork
- Intelligent segment selection (finds the most energetic 15 seconds)

## When to Use

- After mastering complete, before release
- User says "generate promo videos" or "create promo videos for [album]"
- When album has mastered audio + artwork ready

## Position in Workflow

```
Generate → Master → **[Promo Videos]** → Release
```

Optional step between mastering-engineer and release-director.

## Workflow

### 1. Setup Verification

**Check ffmpeg:**
```bash
ffmpeg -filters | grep showwaves
```

Required filters: `showwaves`, `showfreqs`, `drawtext`, `gblur`

If missing:
```
Error: ffmpeg not found or missing required filters

Install ffmpeg:
  macOS: brew install ffmpeg
  Linux: apt install ffmpeg

After installing, run this command again.
```

**Check Python dependencies:**
```bash
python3 -c "import PIL, yaml"
```

Optional (for smart segment detection):
```bash
python3 -c "import librosa, numpy"
```

If missing:
```
Python dependencies missing. Create venv?

  mkdir -p ~/.bitwize-music/promotion-env
  python3 -m venv ~/.bitwize-music/promotion-env
  source ~/.bitwize-music/promotion-env/bin/activate
  pip install pillow pyyaml librosa numpy

Which option:
  1. I'll install manually (show commands above)
  2. Create venv automatically
```

### 2. Album Detection

**Read config:**
```python
import yaml
from pathlib import Path

config_path = Path.home() / ".bitwize-music" / "config.yaml"
config = yaml.safe_load(open(config_path))

audio_root = Path(config['paths']['audio_root']).expanduser()
artist = config['artist']['name']
```

**Locate album:**
```
Album path: {audio_root}/{artist}/{album_name}/
```

**Verify contents:**
- ✓ Mastered audio files (.wav, .mp3, .flac, .m4a)
- ✓ Album artwork (album.png or album.jpg)

If artwork missing:
```
Error: No album artwork found in {audio_root}/{artist}/{album}/

Expected: album.png or album.jpg

Options:
  1. Use /bitwize-music:import-art to place artwork
  2. Specify path manually: --artwork /path/to/art.png

Which option?
```

### 3. User Preferences

**Check config defaults first:**

Read `promotion` section from `~/.bitwize-music/config.yaml` for defaults:
- `promotion.default_style` - Default visualization style
- `promotion.duration` - Default clip duration
- `promotion.include_sampler` - Whether to generate album sampler by default
- `promotion.sampler_clip_duration` - Seconds per track in sampler

If config section doesn't exist, use built-in defaults (pulse, 15s, sampler enabled, 12s clips).

**Ask: What to generate?**

Options (default from config or "both"):
1. Individual track promos (15s each) + Album sampler (all tracks)
2. Individual track promos only
3. Album sampler only

**Ask: Visualization style?**

Default from `promotion.default_style` or `pulse` if not set.

| Style | Best For | Description |
|-------|----------|-------------|
| `pulse` | Electronic, hip-hop | Oscilloscope/EKG style with heavy glow (default) |
| `bars` | Pop, rock | Fast reactive spectrum bars |
| `line` | Acoustic, folk | Classic clean waveform |
| `mirror` | Ambient, chill | Mirrored waveform with symmetry |
| `mountains` | EDM, bass-heavy | Dual-channel spectrum (looks like mountains) |
| `colorwave` | Indie, alternative | Clean waveform with subtle glow |
| `neon` | Synthwave, 80s | Sharp waveform with punchy neon glow |
| `dual` | Experimental | Two separate waveforms (dominant + complementary colors) |
| `circular` | Abstract, experimental | Vectorscope (wild circular patterns) |

**Default recommendation:**
- Electronic/Hip-Hop → `pulse`
- Rock/Pop → `bars`
- Folk/Acoustic → `line`
- Ambient/Chill → `mirror`

**Ask: Custom duration?**

Default: 15 seconds (optimal for Instagram/Twitter)

Options:
- 15s (recommended, Instagram Reels sweet spot)
- 30s (longer preview)
- 60s (full clip, less common)

**For sampler:**

Default: 12 seconds per track

Calculate total:
```
Total duration = (tracks * clip_duration) - ((tracks - 1) * crossfade)
Twitter limit: 140 seconds
```

If over 140s:
```
WARNING: Expected duration {duration}s exceeds Twitter limit (140s)

Recommendation: Reduce --clip-duration to {140 / tracks}s
```

### 4. Generation

**Individual track promos:**

Run from plugin directory:
```bash
cd ${CLAUDE_PLUGIN_ROOT}
python3 tools/promotion/generate_promo_video.py \
  --batch {audio_root}/{artist}/{album}/ \
  --style pulse \
  -o {audio_root}/{artist}/{album}/promo_videos/
```

Progress:
```
Found 10 tracks
  Analyzing audio for most energetic segment...
  Found energetic segment at 45.2s
  Extracting colors from artwork...
  Dominant: (42, 187, 255) -> Complementary: (255, 170, 42) (hex: 0xffaa2a)
Generating: 01-track_promo.mp4
  ✓ 01-track_promo.mp4
Generating: 02-track_promo.mp4
  ✓ 02-track_promo.mp4
...
```

**Album sampler:**

Run from plugin directory:
```bash
cd ${CLAUDE_PLUGIN_ROOT}
python3 tools/promotion/generate_album_sampler.py \
  {audio_root}/{artist}/{album}/ \
  --artwork {audio_root}/{artist}/{album}/album.png \
  --clip-duration 12 \
  -o {audio_root}/{artist}/{album}/album_sampler.mp4
```

Progress:
```
Album Sampler Generator
=======================
Tracks: 10
Clip duration: 12s
Crossfade: 0.5s
Expected duration: 114.5s
Twitter limit: 140s

Found 10 tracks
Extracting colors from artwork...
  Using color: 0xffaa2a
[1/10] Track Name...
  OK
[2/10] Another Track...
  OK
...
Concatenating 10 clips with 0.5s crossfades...

Created: {audio_root}/{artist}/{album}/album_sampler.mp4
  Duration: 114.5s
  Size: 45.2 MB
```

**Handle errors:**

Common issues:
- **ffmpeg filter error** → Check ffmpeg install includes filters
- **Font not found** → Install dejavu fonts or specify custom font
- **Artwork extraction fails** → Use default cyan color scheme
- **librosa unavailable** → Fall back to 20% into track for segment selection
- **Audio file corrupt** → Skip track, report, continue with others

### 5. Results Summary

**Report generated files:**

```
## Promo Videos Generated

**Location:** {audio_root}/{artist}/{album}/

**Individual Track Promos:**
- {audio_root}/{artist}/{album}/promo_videos/
- 10 videos generated
- Format: 1080x1920 (9:16), H.264, 15s each
- Style: pulse
- File size: ~10-12 MB per video

**Album Sampler:**
- {audio_root}/{artist}/{album}/album_sampler.mp4
- Duration: 114.5s (under Twitter 140s limit ✓)
- Format: 1080x1920 (9:16), H.264
- File size: 45.2 MB

**Next Steps:**
1. Review videos: Open promo_videos/ folder
2. Test on phone: Transfer one video and verify quality
3. [Optional] Upload to cloud: /bitwize-music:cloud-uploader {album}
4. Ready for release workflow: /bitwize-music:release-director {album}
```


## Technical Reference

See [technical-reference.md](technical-reference.md) for:
- Output specifications (resolution, format, bitrate)
- Visualization styles (pulse, bars, line, etc.)
- Platform compatibility (Instagram, Twitter, TikTok)
- Dependencies (required and optional)
- Troubleshooting common issues
