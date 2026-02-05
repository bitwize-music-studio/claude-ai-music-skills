# Audio Mastering Workflow for Album Releases

This document defines the automated mastering workflow for preparing audio tracks for streaming release.

---

## Table of Contents

1. [Overview](#overview)
2. [Environment Setup](#environment-setup)
3. [Analysis Phase](#analysis-phase)
4. [Mastering Phase](#mastering-phase)
5. [Reference-Based Mastering](#reference-based-mastering)
6. [Common Issues & Fixes](#common-issues--fixes)
7. [Platform Targets](#platform-targets)
8. [Quality Checklist](#quality-checklist)
9. [Scripts Reference](#scripts-reference)

---

## Overview

### What This Workflow Does

1. **Analyzes** all tracks for loudness (LUFS), peak levels, spectral balance, and dynamic range
2. **Identifies problems** like tinniness, loudness inconsistency, and excessive dynamics
3. **Applies corrective EQ** to reduce harshness in the 2-6kHz range
4. **Normalizes loudness** to streaming standards (-14 LUFS)
5. **Limits peaks** to prevent clipping (-1.0 dBTP ceiling)
6. **Ensures album consistency** (< 1 dB LUFS variation across tracks)

### When to Use

- Before releasing an album to streaming platforms (Spotify, Apple Music, etc.)
- When tracks have inconsistent loudness levels
- When tracks sound "tinny," "harsh," or "thin"
- When preparing final masters from mixed WAV files

---

## Environment Setup

### Required Tools

**One-time setup** (shared venv in `{tools_root}`):

```bash
# Create shared virtual environment
mkdir -p ~/.bitwize-music
python3 -m venv ~/.bitwize-music/venv
source ~/.bitwize-music/venv/bin/activate

# Install Python audio libraries
pip install matchering pyloudnorm scipy numpy soundfile
```

**Note:** The Python scripts handle all analysis and processing. No additional system tools (SoX, ffmpeg) are required.

### Directory Structure

```
~/.bitwize-music/              # Shared tools location ({tools_root})
└── mastering-env/            # Shared Python virtual environment

target-folder/                # Your album's WAV folder ({audio_root}/{artist}/{album}/)
├── 01 - Track Name.wav       # Original mixed files (16 or 24-bit WAV)
├── 02 - Track Name.wav
├── ...
└── mastered/                 # Output folder (created automatically)
    ├── 01 - Track Name.wav   # Mastered files
    └── ...

# Scripts stay in plugin directory ({plugin_root}/tools/mastering/)
# Run with path argument - never copy into audio folders
```

---

## Analysis Phase

### Step 1: LUFS Analysis

Run the analysis script for accurate measurements:

```bash
source ~/.bitwize-music/venv/bin/activate
python3 {plugin_root}/tools/mastering/analyze_tracks.py {audio_root}/{artist}/{album}/
```

**Key Metrics:**

| Metric | Ideal Range | Problem If |
|--------|-------------|------------|
| LUFS | -14 to -16 | Varies > 2 dB across album |
| Peak dB | -1 to -3 | Above -0.5 (clipping risk) |
| LUFS Range | < 2 dB | > 3 dB (inconsistent album) |
| High-Mid Energy | 8-15% | > 20% (tinny) |

### Step 2: Identify Problem Tracks

After analysis, categorize tracks:

1. **Tinny tracks** (high-mid ratio > 0.6) → Need EQ cut at 2-6kHz
2. **Quiet tracks** (LUFS < average - 2dB) → Need gain boost
3. **Loud tracks** (LUFS > average + 2dB) → Need gain reduction
4. **High dynamic range** (crest factor > 12dB) → May need compression

---

## Mastering Phase

### Standard Mastering Command

```bash
source ~/.bitwize-music/venv/bin/activate
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_root}/{artist}/{album}/ --genre country
```

### Available Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--genre`, `-g` | none | Apply genre preset (see below) |
| `--target-lufs` | -14.0 | Target loudness (streaming standard) |
| `--ceiling` | -1.0 | True peak ceiling in dB |
| `--cut-highmid` | 0 | High-mid EQ cut in dB at 3.5kHz |
| `--cut-highs` | 0 | High shelf cut in dB at 8kHz |
| `--output-dir` | mastered | Output directory |
| `--dry-run` | false | Preview without writing files |

### Genre Presets

Use `--genre` for automatic settings:

```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --genre country
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --genre rock
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --genre jazz
```

**Available genres and their settings:**

| Category | Genres | LUFS | High-Mid Cut |
|----------|--------|------|--------------|
| Pop/Mainstream | pop, k-pop, hyperpop | -14 | -1.0 to -1.5 dB |
| Hip-Hop/Rap | hip-hop, rap, trap, drill, phonk, grime, nerdcore | -14 | -1.0 to -1.5 dB |
| R&B/Soul/Funk | rnb, soul, funk, disco, gospel | -14 | -1.5 dB |
| Rock | rock, indie-rock, alternative, grunge, garage-rock, surf-rock | -14 | -1.5 to -2.5 dB |
| Rock (Dynamic) | psychedelic-rock, progressive-rock, post-rock | -16 | -1.5 dB |
| Punk | punk, hardcore-punk, ska-punk, celtic-punk, emo | -14 | -2.0 to -2.5 dB |
| Metal | metal, thrash-metal, black-metal, doom-metal, metalcore, industrial | -14 | -2.5 to -3.0 dB |
| Electronic/Dance | electronic, edm, house, techno, trance, dubstep, drum-and-bass, synthwave, new-wave, dancehall | -14 | -1.0 to -1.5 dB |
| Ambient/Chill | ambient, lo-fi, chillwave, trip-hop, vaporwave, shoegaze | -14 to -16 | -1.0 to -1.5 dB |
| Folk/Country | folk, country, americana, bluegrass, indie-folk | -14 | -1.5 to -2.0 dB |
| Jazz/Blues | jazz, blues, swing, bossa-nova | -14 to -16 | none to -1.5 dB |
| Classical/Cinematic | classical, opera, cinematic | -16 to -18 | none |
| Latin/World | latin, afrobeats, reggae | -14 | -1.0 to -1.5 dB |

Run `python3 {plugin_root}/tools/mastering/master_tracks.py --help` for the full list of 60+ genre presets.

### Manual Presets

If you prefer manual control (replace `{audio_path}` with your album's audio folder):

**Clean (loudness only)**
```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/
```

**Gentle warmth**
```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --cut-highmid -2
```

**Warmer (for harsh mixes)**
```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --cut-highmid -3 --cut-highs -1.5
```

### Dry Run First

Always preview before processing:

```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --dry-run --cut-highmid -2
```

This shows what gain changes would be applied without writing files.

---

## Reference-Based Mastering

The `matchering` library enables mastering against a reference track. This matches the tonal balance and loudness of a professionally mastered song.

### How It Works

1. Provide your track and a reference track (a commercially mastered song in your genre)
2. Matchering analyzes both tracks' frequency response and loudness
3. It applies EQ and dynamics processing to match your track to the reference

### Basic Usage

```python
import matchering as mg

mg.process(
    target="my_track.wav",
    reference="professional_reference.wav",
    results=[
        mg.pcm16("mastered_output.wav"),
    ],
)
```

### Using reference_master.py

```bash
# Master a single track against a reference
python3 reference_master.py --reference pro_master.wav --target my_track.wav

# Master all WAVs in current directory against a reference
python3 reference_master.py --reference pro_master.wav

# Custom output directory
python3 reference_master.py --reference pro_master.wav --output-dir matched/
```

The script will:
1. Analyze the frequency response and loudness of your reference
2. Apply EQ and dynamics to match your tracks to that reference
3. Output 16-bit WAV files to the output directory

### Getting Reference Tracks

**Legal sources for reference tracks:**
- Your own purchased music (rip from CD or download)
- Streaming service downloads (where license permits)
- Bandcamp purchases (lossless FLAC/WAV available)
- Sample packs with master-quality examples

**Do NOT use:**
- Illegally downloaded music
- YouTube rips (lossy, transcoded)
- Spotify/Apple Music streams directly (DRM protected)

### Choosing a Good Reference

- Pick a commercially released track in the **same genre**
- Choose something with similar instrumentation/arrangement
- Avoid heavily compressed "loudness war" masters if you want dynamics
- The reference should represent your **target sound**, not just any pro master

### When to Use Reference Mastering

- When you want a specific commercial sound
- When starting a new genre and unsure of target loudness/EQ
- When matching an existing catalog's sound

---

## Common Issues & Fixes

### Issue 1: Track Won't Reach Target LUFS

**Symptom:** After mastering, track is 1-3 dB below target LUFS
**Cause:** Very high dynamic range (big transients hitting the limiter)
**Fix:** Use `fix_dynamic_track.py`:

```bash
python3 fix_dynamic_track.py "problem_track.wav"
```

### Issue 2: Tracks Still Sound Tinny After EQ

**Symptom:** High-mid cut applied but still harsh
**Cause:** Multiple resonant frequencies, not just 3.5kHz
**Fix:** Apply multiple EQ cuts

```bash
# Target multiple frequencies
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --cut-highmid -3
```

Or modify the script to apply cuts at 2.5kHz, 4kHz, and 5.5kHz.

### Issue 3: Bass Sounds Weak After Processing

**Symptom:** Low end feels thinner after mastering
**Cause:** High-mid cut can psychoacoustically reduce perceived bass
**Fix:** Add subtle low shelf boost (+1dB at 100Hz)

### Issue 4: Clipping on Streaming Platforms

**Symptom:** Distortion when played on Spotify/Apple Music
**Cause:** True peak above -1.0 dBTP (platforms add their own processing)
**Fix:** Use -1.5 or -2.0 dBTP ceiling

```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --ceiling -1.5
```

---

## Platform Targets

### Streaming Loudness Standards

| Platform | Target LUFS | Peak Ceiling | Notes |
|----------|-------------|--------------|-------|
| Spotify | -14 | -1.0 dBTP | Normalizes to -14, penalizes louder |
| Apple Music | -16 | -1.0 dBTP | Sound Check uses -16 |
| YouTube | -14 | -1.0 dBTP | Normalizes to -14 |
| Tidal | -14 | -1.0 dBTP | Normalizes to -14 |
| Amazon Music | -14 | -2.0 dBTP | More conservative peak |
| SoundCloud | -14 | -1.0 dBTP | Normalizes to -14 |

### Recommended Settings by Genre

| Genre | Target LUFS | High-Mid Cut | Notes |
|-------|-------------|--------------|-------|
| Pop/EDM | -14 | -1 to -2 dB | Bright is expected |
| Rock/Metal | -14 | -2 to -3 dB | Tame harshness |
| Hip-Hop/R&B | -14 | -1 dB | Keep presence |
| Jazz/Classical | -16 to -18 | 0 | Preserve dynamics |
| Folk/Acoustic | -14 to -16 | -1 to -2 dB | Natural warmth |
| Country | -14 | -2 dB | Tame brightness |

---

## Quality Checklist

### Before Mastering

- [ ] All tracks are WAV format (16 or 24-bit)
- [ ] No tracks are clipping (peaks below 0 dBFS)
- [ ] Track order/naming is finalized
- [ ] Mixes are approved (mastering won't fix bad mixes)

### After Mastering

- [ ] All tracks at target LUFS (±0.5 dB)
- [ ] True peaks below -1.0 dBTP
- [ ] LUFS range across album < 1 dB
- [ ] No audible distortion or artifacts
- [ ] Tonal balance consistent across tracks
- [ ] Fades/silence at start/end are correct
- [ ] A/B comparison with originals sounds like improvement

### Listening Tests

1. **Loudness test:** Play tracks in shuffle - no sudden volume jumps
2. **Translation test:** Check on multiple systems (headphones, speakers, car, phone)
3. **Fatigue test:** Listen to full album - no listener fatigue from harshness
4. **Reference test:** Compare to commercial releases in same genre

---

## Scripts Reference

Scripts are located in `{plugin_root}/tools/mastering/`. Run them with a path argument - never copy into audio folders.

### analyze_tracks.py

Full analysis script that measures:
- Integrated LUFS loudness
- True peak levels
- Spectral energy distribution by frequency band
- Tinniness ratio (high-mid to mid energy ratio)
- Dynamic range

**Usage:**
```bash
python3 {plugin_root}/tools/mastering/analyze_tracks.py {audio_path}/
```

### master_tracks.py

Main mastering script with:
- Parametric EQ for tinniness correction
- LUFS normalization using pyloudnorm
- Soft-knee peak limiting
- Batch processing of all tracks

**Usage:**
```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ [options]
```

### fix_dynamic_track.py

For tracks with excessive dynamic range:
- Gentle compression to tame transients
- EQ and limiting
- Gets difficult tracks to target LUFS

**Usage:**
```bash
python3 fix_dynamic_track.py input.wav [output.wav]
```

### reference_master.py

Reference-based mastering using matchering:
- Matches frequency response to a professional reference
- Matches loudness characteristics
- Batch processes all WAVs or single file

**Usage:**
```bash
python3 reference_master.py --reference pro_track.wav
python3 reference_master.py --reference pro_track.wav --target single_track.wav
```

---

## Quick Reference Commands

```bash
# One-time setup (shared venv)
mkdir -p ~/.bitwize-music
python3 -m venv ~/.bitwize-music/venv
source ~/.bitwize-music/venv/bin/activate
pip install matchering pyloudnorm scipy numpy soundfile

# For each album - run from anywhere, scripts stay in plugin:
source ~/.bitwize-music/venv/bin/activate

# Analyze tracks (pass audio folder path)
python3 {plugin_root}/tools/mastering/analyze_tracks.py {audio_root}/{artist}/{album}/

# Preview mastering (dry run)
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_root}/{artist}/{album}/ --dry-run --genre country

# Master with genre preset
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_root}/{artist}/{album}/ --genre country

# Or with manual settings
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_root}/{artist}/{album}/ --cut-highmid -2

# Verify results (mastered/ created inside album folder)
python3 {plugin_root}/tools/mastering/analyze_tracks.py {audio_root}/{artist}/{album}/mastered/

# Reference-based mastering (match a pro track)
python3 {plugin_root}/tools/mastering/reference_master.py --reference pro_track.wav

# List output folder
ls {audio_root}/{artist}/{album}/mastered/
```

**Note**: Scripts stay in plugin directory. Never copy `.py` files into audio folders.

---

## Troubleshooting

### "externally-managed-environment" error
Use a virtual environment:
```bash
python3 -m venv ~/.bitwize-music/venv
source ~/.bitwize-music/venv/bin/activate
```

### Very slow processing
Large files take time. For a 10-track album, expect 30-60 seconds total.

---

## Notes

- Always keep original files - mastering is destructive
- Trust your ears over the numbers
- When in doubt, use less processing (you can always add more)
- Different songs may need different treatment - one size doesn't fit all

---

## Related Skills

- **`/bitwize-music:mastering-engineer`** - Audio mastering guidance and automation
  - Uses this workflow document as reference
  - Runs mastering scripts automatically
  - Analyzes LUFS and provides recommendations
  - Applies genre-specific EQ presets

- **`/bitwize-music:release-director`** - Album release coordination
  - Verifies mastering is complete before release
  - Checks LUFS targets for streaming platforms
  - Manages final QA and distribution prep

## See Also

- **`/tools/mastering/`** - Python mastering scripts referenced in this workflow
  - `analyze_tracks.py` - LUFS/dynamics analysis
  - `master_tracks.py` - Automated mastering with genre presets
  - `fix_dynamic_track.py` - Fix high-dynamic-range tracks
  - `reference_master.py` - Match loudness to reference track

- **`/reference/workflows/release-procedures.md`** - Complete release workflow including mastering
- **`/skills/mastering-engineer/SKILL.md`** - Complete mastering engineer skill documentation
