# Mastering Checklist

Complete quality assurance checklist for audio mastering.

---

## Pre-Mastering Checks

Complete these before starting the mastering process.

### Source Files

- [ ] All tracks are WAV format (16 or 24-bit)
- [ ] No MP3 or compressed source files
- [ ] Sample rate is consistent (44.1kHz or 48kHz)
- [ ] Bit depth is consistent across tracks
- [ ] Files are not already mastered (avoid double-processing)

### Mix Quality

- [ ] No tracks are clipping (peaks below 0 dBFS)
- [ ] No obvious mix problems (bad balance, phase issues)
- [ ] Mixes are final and approved (mastering won't fix bad mixes)
- [ ] Headroom exists (peaks around -3 to -6 dBFS ideal)

### Organization

- [ ] Track order is finalized
- [ ] File naming is correct (e.g., "01 - Track Name.wav")
- [ ] Working directory is clean (only source WAVs)
- [ ] Backup of original files exists

### Environment

- [ ] Virtual environment activated
- [ ] Required packages installed (pyloudnorm, scipy, numpy, soundfile)
- [ ] Scripts accessible in plugin directory

```bash
# Verify environment
source ~/.bitwize-music/mastering-env/bin/activate
python3 -c "import pyloudnorm; print('Ready')"
```

---

## During Mastering

Verify these while processing.

### Analysis Phase

- [ ] Run `analyze_tracks.py` on source files
- [ ] Note current LUFS levels for each track
- [ ] Identify problem tracks (too loud, too quiet, tinny)
- [ ] Choose appropriate genre preset or manual settings

```bash
python3 {plugin_root}/tools/mastering/analyze_tracks.py /path/to/source/
```

### Preview Phase

- [ ] Run dry-run first to preview changes
- [ ] Review proposed gain adjustments
- [ ] Confirm EQ settings are appropriate for genre
- [ ] No warnings or errors in output

```bash
python3 {plugin_root}/tools/mastering/master_tracks.py /path/to/source/ --dry-run --genre rock
```

### Processing Phase

- [ ] Process with confirmed settings
- [ ] All files complete without errors
- [ ] Output directory created (`mastered/`)
- [ ] Same number of files in output as input

```bash
python3 {plugin_root}/tools/mastering/master_tracks.py /path/to/source/ --genre rock
ls /path/to/source/mastered/
```

---

## Post-Mastering QA

Complete quality verification after processing.

### Technical Verification

- [ ] All tracks at target LUFS (within 0.5 dB of -14)
- [ ] True peaks below -1.0 dBTP
- [ ] LUFS range across album < 1 dB
- [ ] No files corrupted or truncated

```bash
# Verify mastered files
python3 {plugin_root}/tools/mastering/analyze_tracks.py /path/to/source/mastered/
```

### Sonic Verification

- [ ] No audible distortion or digital artifacts
- [ ] No pumping or unnatural dynamics
- [ ] Tonal balance consistent across tracks
- [ ] No excessive brightness or harshness
- [ ] Low end intact (not weakened by EQ)

### Structural Verification

- [ ] Fades at start/end are correct
- [ ] No unexpected silence gaps
- [ ] Track beginnings are clean (no clicks)
- [ ] Track endings complete (not cut off)

### Comparison Tests

- [ ] A/B comparison with originals shows improvement
- [ ] Mastered versions sound "bigger" without distortion
- [ ] Commercial reference comparison sounds competitive

---

## Listening Tests

Critical listening on multiple systems.

### Loudness Test

- [ ] Play album tracks in shuffle order
- [ ] No sudden volume jumps between tracks
- [ ] Consistent perceived loudness throughout

### Translation Test

- [ ] Headphones (studio quality)
- [ ] Near-field monitors
- [ ] Laptop/phone speakers
- [ ] Car stereo (if available)
- [ ] Consumer earbuds

**Listen for**: Does the balance hold across systems? Any harshness on small speakers?

### Fatigue Test

- [ ] Listen to full album front-to-back
- [ ] No listener fatigue from harshness
- [ ] Enjoyable listening experience

### Reference Test

- [ ] Compare to 2-3 commercial releases in same genre
- [ ] Similar loudness level
- [ ] Similar tonal balance
- [ ] Professional quality achieved

---

## Common Issues & Fixes

### Issue: Tracks Don't Reach Target LUFS

**Symptom**: After mastering, track is 1-3 dB below -14 LUFS.

**Cause**: Very high dynamic range (big transients hitting the limiter).

**Fix**:
```bash
python3 {plugin_root}/tools/mastering/fix_dynamic_track.py "problem_track.wav"
```

---

### Issue: Still Sounds Harsh After EQ

**Symptom**: High-mid cut applied but still harsh.

**Cause**: Multiple resonant frequencies, not just 3.5kHz.

**Fix**: Apply stronger cut
```bash
python3 {plugin_root}/tools/mastering/master_tracks.py /path/ --cut-highmid -4
```

---

### Issue: Bass Sounds Weak

**Symptom**: Low end feels thinner after mastering.

**Cause**: High-mid cut can psychoacoustically reduce perceived bass.

**Fix**: Use less aggressive high-mid cut or add manual low shelf boost.

---

### Issue: Clipping Reports on Platforms

**Symptom**: Distortion when played on Spotify/Apple Music.

**Cause**: True peak above -1.0 dBTP.

**Fix**:
```bash
python3 {plugin_root}/tools/mastering/master_tracks.py /path/ --ceiling -1.5
```

---

### Issue: Album Sounds Inconsistent

**Symptom**: Some tracks noticeably louder or different tone.

**Cause**: Different source qualities or genre mismatch.

**Fix**: Master outlier tracks individually with custom settings.

---

### Issue: File Corruption

**Symptom**: Output file won't play or shows errors.

**Cause**: Interrupted processing or disk space issue.

**Fix**: Delete corrupted file, check disk space, re-run mastering.

---

## Final Approval

Before delivering mastered files:

- [ ] All checklist items above verified
- [ ] Files named correctly for distribution
- [ ] Mastered folder contains only final files
- [ ] Original source files preserved separately
- [ ] Ready for platform upload

---

## Quick Verification Commands

```bash
# Full analysis of mastered files
python3 {plugin_root}/tools/mastering/analyze_tracks.py /path/to/mastered/

# Check file count
ls -la /path/to/mastered/*.wav | wc -l

# Quick loudness check with ffmpeg (per file)
ffmpeg -i track.wav -af loudnorm=print_format=summary -f null - 2>&1 | grep -E "(Integrated|True Peak)"

# List file sizes (check for truncation)
ls -lh /path/to/mastered/
```

---

## Checklist Summary

| Phase | Key Checks |
|-------|------------|
| Pre-Mastering | WAV format, no clipping, files organized |
| During | Dry-run first, no errors, correct settings |
| Post | LUFS verified, peaks safe, listening tests passed |
| Final | All items verified, ready for distribution |
