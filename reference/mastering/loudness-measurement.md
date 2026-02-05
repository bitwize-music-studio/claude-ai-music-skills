# Loudness Measurement Guide

How to measure and verify loudness for streaming platforms.

---

## Key Metrics

### Integrated LUFS (Loudness Units Full Scale)

**What it measures**: Average perceived loudness over the entire track.

**Target**: -14 LUFS for streaming platforms.

**Why it matters**: Streaming services normalize all tracks to the same loudness. If your track is louder than -14 LUFS, they turn it down. If quieter, some platforms turn it up.

```
Too loud (-10 LUFS) → Platform reduces volume → Sounds worse
Too quiet (-20 LUFS) → May not be normalized up → Sounds quiet
Just right (-14 LUFS) → No processing → Sounds as intended
```

### True Peak (dBTP)

**What it measures**: The actual peak level after digital-to-analog conversion.

**Target**: -1.0 dBTP maximum.

**Why it matters**: Digital peaks can exceed 0 dBFS during playback due to inter-sample peaks. Keeping below -1.0 dBTP prevents distortion when converting to lossy formats (MP3, AAC).

```
True Peak > 0 dBTP → Clipping on playback → Audible distortion
True Peak at -0.5 dBTP → May clip after encoding → Risk of distortion
True Peak at -1.0 dBTP → Safe headroom → Clean playback
```

### Dynamic Range

**What it measures**: Difference between loudest and quietest parts.

**Target**: Depends on genre (see below).

**Why it matters**: Over-compressed music sounds fatiguing. Under-compressed music has jarring volume changes.

| Genre | Typical Dynamic Range |
|-------|----------------------|
| Classical | 15-25 dB |
| Jazz/Folk | 10-15 dB |
| Rock/Pop | 6-12 dB |
| EDM/Hip-Hop | 4-8 dB |

---

## Measurement Tools

### Free Tools

**analyze_tracks.py (included)**

Our analysis script provides all essential metrics:

```bash
source ~/.bitwize-music/venv/bin/activate
python3 {plugin_root}/tools/mastering/analyze_tracks.py /path/to/audio/
```

Output includes:
- Integrated LUFS
- True Peak
- LUFS Range
- Tinniness ratio

---

**Youlean Loudness Meter (FREE)**

Website: [youlean.co/youlean-loudness-meter](https://youlean.co/youlean-loudness-meter/)

- VST/AU plugin for DAWs
- Standalone app available
- Real-time LUFS metering
- Histogram visualization
- Platform presets (Spotify, Apple, YouTube)

**How to use**:
1. Load audio file (standalone) or insert on master bus (DAW)
2. Select platform preset (e.g., "Spotify")
3. Play entire track
4. Check "Integrated" reading matches target

---

**dpMeter (FREE)**

Website: [tb-software.com/TBProAudio](https://www.tb-software.com/TBProAudio/dpmeter.html)

- VST/AU/AAX plugin
- True Peak metering
- K-metering support
- Lightweight, CPU-efficient

---

**Orban Loudness Meter (FREE)**

Website: [orban.com](https://www.orban.com/meter)

- Standalone Windows app
- Broadcast-standard metering
- EBU R128 compliant

---

### Paid Tools

**iZotope Insight 2 ($199)**

- Comprehensive metering suite
- Spectrogram, loudness, intelligibility
- Industry standard
- Integrates with iZotope RX

---

**Nugen Audio MasterCheck Pro ($199)**

- Streaming platform simulation
- Codec preview (hear what Spotify encoding does)
- True Peak limiting
- Batch processing

---

**HOFA 4U+ Meter (Freemium)**

Website: [hofa-plugins.de](https://hofa-plugins.de/plugins/4u-meter/)

- Free basic version
- Goniometer, spectrum, loudness
- Clean interface

---

## Platform-Specific Requirements

### Spotify

| Metric | Target |
|--------|--------|
| Integrated LUFS | -14 |
| True Peak | -1.0 dBTP |
| Sample Rate | 44.1 kHz |
| Bit Depth | 16-bit minimum |

**Normalization behavior**: Tracks louder than -14 LUFS are turned down. Tracks quieter may be turned up (if user enables "Loud" mode).

---

### Apple Music

| Metric | Target |
|--------|--------|
| Integrated LUFS | -16 (Sound Check) |
| True Peak | -1.0 dBTP |
| Sample Rate | 44.1-192 kHz |
| Bit Depth | 16-24 bit |

**Note**: Apple's Sound Check targets -16 LUFS, but mastering to -14 LUFS is still recommended for consistency across platforms.

---

### YouTube

| Metric | Target |
|--------|--------|
| Integrated LUFS | -14 |
| True Peak | -1.0 dBTP |
| Sample Rate | 48 kHz preferred |

**Normalization behavior**: YouTube normalizes to -14 LUFS. Louder content gets turned down.

---

### SoundCloud

| Metric | Target |
|--------|--------|
| Integrated LUFS | -14 |
| True Peak | -1.0 dBTP |
| Format | WAV or FLAC preferred |

**Normalization behavior**: SoundCloud normalizes by default.

---

### Amazon Music

| Metric | Target |
|--------|--------|
| Integrated LUFS | -14 |
| True Peak | -2.0 dBTP |
| Sample Rate | 44.1 kHz |

**Note**: Amazon recommends more conservative -2.0 dBTP ceiling.

---

### Tidal

| Metric | Target |
|--------|--------|
| Integrated LUFS | -14 |
| True Peak | -1.0 dBTP |
| Format | FLAC for HiFi tier |

---

## How to Measure

### Using analyze_tracks.py

```bash
# Activate environment
source ~/.bitwize-music/venv/bin/activate

# Analyze a folder
python3 {plugin_root}/tools/mastering/analyze_tracks.py /path/to/mastered/

# Example output:
# Track                  | LUFS   | Peak   | High-Mid | Status
# ---------------------- | ------ | ------ | -------- | ------
# 01 - Track One.wav     | -14.2  | -1.1   | 0.45     | OK
# 02 - Track Two.wav     | -13.5  | -0.8   | 0.62     | PEAK HIGH
```

---

### Using ffmpeg (command line)

```bash
ffmpeg -i track.wav -af loudnorm=print_format=summary -f null -
```

Output:
```
Input Integrated:    -14.2 LUFS
Input True Peak:     -1.1 dBTP
Input LRA:           7.2 LU
```

---

### Using sox (command line)

```bash
sox track.wav -n stats
```

Look for "Pk lev dB" (peak level) and calculate loudness from RMS.

---

## Interpreting Results

### Good Results

```
LUFS: -14.0 to -14.5  (within target range)
Peak: -1.0 to -1.5 dBTP  (safe headroom)
Range: < 1 dB across album  (consistent)
```

### Problem Indicators

| Reading | Problem | Fix |
|---------|---------|-----|
| LUFS > -12 | Too loud | Re-master with lower gain |
| LUFS < -16 | Too quiet | Re-master with higher gain |
| Peak > -0.5 dBTP | Clipping risk | Lower ceiling to -1.5 dBTP |
| Album range > 2 dB | Inconsistent | Re-master outlier tracks |

---

## Verification Workflow

1. **Analyze all tracks** with `analyze_tracks.py`
2. **Check LUFS** - All tracks within 0.5 dB of -14 LUFS
3. **Check peaks** - All tracks below -1.0 dBTP
4. **Listen test** - Play album in shuffle, no volume jumps
5. **Compare** - Check against commercial reference

```bash
# Full verification command
source ~/.bitwize-music/venv/bin/activate
python3 {plugin_root}/tools/mastering/analyze_tracks.py /path/to/mastered/

# Expected: All tracks show "OK" status
```

---

## Quick Reference

| Platform | LUFS Target | True Peak |
|----------|-------------|-----------|
| Spotify | -14 | -1.0 dBTP |
| Apple Music | -16 | -1.0 dBTP |
| YouTube | -14 | -1.0 dBTP |
| SoundCloud | -14 | -1.0 dBTP |
| Amazon Music | -14 | -2.0 dBTP |
| Tidal | -14 | -1.0 dBTP |

**Safe universal target**: -14 LUFS, -1.0 dBTP
