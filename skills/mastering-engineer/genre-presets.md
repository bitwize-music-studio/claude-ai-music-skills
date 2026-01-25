# Genre-Specific Mastering Presets

Detailed mastering settings by genre.

---

## Platform Targets Reference

### Spotify
- **Target**: -14 LUFS integrated
- **True peak**: -1.0 dBTP
- **What happens**: Tracks louder than -14 turned down, quieter turned up
- **Strategy**: Master to -14, maintain dynamics

### Apple Music
- **Target**: -16 LUFS integrated
- **True peak**: -1.0 dBTP
- **What happens**: "Sound Check" normalizes playback
- **Strategy**: Master to -14 (won't be turned up, preserves dynamics)

### YouTube
- **Target**: -13 to -15 LUFS
- **True peak**: -1.0 dBTP
- **What happens**: Normalization to -14 LUFS
- **Strategy**: -14 LUFS works perfectly

### SoundCloud
- **Target**: No normalization
- **Strategy**: -14 LUFS for consistency with streaming platforms

### Bandcamp
- **Target**: No normalization (listener controls volume)
- **Strategy**: -14 LUFS, but can go louder (-12) if genre appropriate

---

## Genre Presets

### Hip-Hop / Rap
**LUFS target**: -12 to -14 LUFS
**Dynamics**: Moderate compression, punchy transients
**EQ focus**: Sub-bass presence (40-60 Hz), vocal clarity (2-4 kHz)
**Tools command**: `python3 master_tracks.py --genre hip-hop`

**Characteristics**:
- Strong low end
- Clear vocals
- Punchy kick/snare

### Rock / Alternative
**LUFS target**: -12 to -14 LUFS
**Dynamics**: Wide dynamic range, preserve peaks
**EQ focus**: Guitar presence (800 Hz - 3 kHz), avoid harsh highs
**Tools command**: `python3 master_tracks.py --genre rock`

**Characteristics**:
- Guitar energy
- Drum impact
- Vocal cut-through

### Electronic / EDM
**LUFS target**: -10 to -12 LUFS (can go louder)
**Dynamics**: Heavy compression, consistent energy
**EQ focus**: Sub-bass (30-50 Hz), sparkle on top (10+ kHz)
**Tools command**: `python3 master_tracks.py --genre edm`

**Characteristics**:
- Massive bass
- Sustained energy
- Bright, polished highs

### Folk / Acoustic
**LUFS target**: -14 to -16 LUFS
**Dynamics**: Preserve natural dynamics
**EQ focus**: Warmth (200-500 Hz), natural highs
**Tools command**: `python3 master_tracks.py --genre folk`

**Characteristics**:
- Natural, intimate
- Wide dynamic range
- Minimal processing

### Country
**LUFS target**: -13 to -14 LUFS
**Dynamics**: Moderate, radio-ready
**EQ focus**: Vocal clarity, steel guitar presence
**Tools command**: `python3 master_tracks.py --genre country`

**Characteristics**:
- Clear vocals
- Instrument separation
- Warm, polished

### Jazz / Classical
**LUFS target**: -16 to -18 LUFS
**Dynamics**: Preserve full dynamic range
**EQ focus**: Natural tonal balance, minimal EQ
**Tools command**: `python3 master_tracks.py --genre jazz`

**Characteristics**:
- Wide dynamics
- Natural room sound
- Uncompressed peaks

---

## Problem-Solving

### Problem: Track Won't Reach -14 LUFS

**Cause**: High dynamic range (classical, acoustic, lots of quiet parts)

**Symptoms**:
```
Track: acoustic-ballad.wav
Integrated LUFS: -18.5
True Peak: -3.2 dBTP
```

**Solution**:
```bash
python3 fix_dynamic_track.py "acoustic-ballad.wav"
```
- Applies moderate compression
- Raises quiet parts
- Preserves natural feel

**Alternative**: Accept quieter LUFS (-16 to -18) if genre appropriate

### Problem: Track Sounds Harsh/Bright

**Cause**: Suno often generates bright vocals/highs

**Solution**:
```bash
python3 master_tracks.py --cut-highmid -3
```
- Increase high-mid cut to -3 dB
- Reduces harshness at 2-4 kHz

### Problem: Bass Too Loud/Muddy

**Cause**: Suno can over-generate low end

**Solution**:
```bash
python3 master_tracks.py --genre [genre] --cut-lows -2
```
- Genre preset with low cut
- Clears mud below 60 Hz

**Check**: Some genres (hip-hop, EDM) need strong bass

### Problem: Album Sounds Inconsistent

**Cause**: Different tracks mastered separately

**Solution**:
1. Master entire album together (all files in one folder)
2. Check LUFS range: Should be <1 dB variation
3. Adjust outliers with adjusted targets

### Problem: Track Clips After Mastering

**Cause**: True peak limiter set wrong

**Solution**:
```bash
python3 master_tracks.py --true-peak -1.5
```
- Targets -1.5 dBTP instead of -1.0
- More headroom for encoding

### Problem: Track Sounds Squashed/Lifeless

**Cause**: Over-compression trying to hit LUFS target

**Solution**:
```bash
python3 master_tracks.py --target-lufs -16
```
- Masters to -16 instead of -14
- Preserves dynamics

---

## Loudness Myths

### Myth: Louder is Better
**Reality**: Streaming platforms normalize. Squashing dynamics for loudness hurts sound quality with no benefit.

### Myth: -14 LUFS is Too Quiet
**Reality**: Platforms turn it up. You preserve dynamics, platform handles level.

### Myth: Mastering Fixes Bad Mix
**Reality**: Mastering optimizes good audio. Can't rescue fundamentally flawed tracks.

### Myth: All Tracks Should Be Identical LUFS
**Reality**: Small variations (<1 dB) create natural album flow. Perfect matching sounds robotic.

### Myth: True Peak Can Exceed 0.0 dBTP
**Reality**: Will clip after MP3/AAC encoding. Always keep headroom.
