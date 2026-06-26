# Mix Engineer Skill for Ableton

**Description**: Polishes raw audio by processing per-stem WAVs (vocals, drums, bass, guitar, keyboard, strings, brass, woodwinds, percussion, synth, other) with targeted cleanup, EQ, and compression, then remixing into a polished stereo WAV ready for mastering.

**Use Case**: After recording/importing stems and before mastering stage.

---

## Core Principles

### Stems First
Processing each stem independently is far more effective than processing a full mix. You can apply targeted settings that would be impossible on a mixed signal.

### Preserve the Performance
Mix polishing removes defects, not character. Be conservative with processing. Over-processing sounds worse than under-processing.

### Non-Destructive
All processing writes to a `polished/` folder — originals are never modified. The user can always go back.

### Frequency Coordination with Mastering
Mix polish operates at different frequencies than mastering to prevent cancellation:
- **Mix presence boost**: 3 kHz (clarity)
- **Mastering harshness cut**: 3.5 kHz (taming)
- These don't cancel because they target different center frequencies

---

## Per-Stem Processing Chains

### Vocals (Lead)
1. **Noise reduction** (strength 0.5) — removes hiss and artifacts
2. **Presence boost** (+2 dB at 3 kHz) — vocal clarity
3. **High tame** (-2 dB shelf at 7 kHz) — de-ess sibilance
4. **Gentle compress** (-15 dB threshold, 2.5:1) — dynamic consistency

### Backing Vocals
1. **Noise reduction** (strength 0.5)
2. **Presence boost** (+1 dB at 3 kHz) — half of lead's boost
3. **High tame** (-2.5 dB shelf at 7 kHz) — more aggressive de-essing
4. **Stereo width** (1.3×) — spread behind lead
5. **Gentle compress** (-14 dB threshold, 3:1, 8ms attack) — tighter than lead

### Drums
1. **Click removal** (threshold 6σ) — removes digital clicks/pops
2. **Gentle compress** (-12 dB threshold, 2:1, fast 5ms attack) — transient control

### Bass
1. **Highpass** (30 Hz Butterworth) — sub-rumble removal
2. **Mud cut** (-3 dB at 200 Hz) — low-mid cleanup
3. **Gentle compress** (-15 dB threshold, 3:1) — consistent bottom end

### Guitar
1. **Highpass** (80 Hz Butterworth) — remove sub-bass
2. **Mud cut** (-2.5 dB at 250 Hz) — guitar boxiness zone
3. **Presence boost** (+1.5 dB at 3 kHz, Q 1.2) — pick articulation
4. **High tame** (-1.5 dB shelf at 8 kHz) — brightness control
5. **Stereo width** (1.15×) — moderate spread
6. **Gentle compress** (-14 dB threshold, 2.5:1, 12ms attack)

### Keyboard
1. **Highpass** (40 Hz Butterworth) — preserves piano bass notes
2. **Mud cut** (-2 dB at 300 Hz) — low-mid cleanup
3. **Presence boost** (+1 dB at 2.5 kHz, Q 0.8) — avoids vocal zone
4. **High tame** (-1.5 dB shelf at 9 kHz) — brightness control
5. **Stereo width** (1.1×) — slight spread
6. **Gentle compress** (-16 dB threshold, 2:1, 15ms attack) — light

### Strings
1. **Highpass** (35 Hz Butterworth) — very low for cello/bass range
2. **Mud cut** (-1.5 dB at 250 Hz, Q 0.8) — gentle
3. **Presence boost** (+1 dB at 3.5 kHz) — above vocals
4. **High tame** (-1 dB shelf at 9 kHz) — gentle
5. **Stereo width** (1.25×) — wide for orchestral spread
6. **Gentle compress** (-18 dB threshold, 1.5:1, 20ms attack) — lightest

### Brass
1. **Highpass** (60 Hz Butterworth) — sub-rumble removal
2. **Mud cut** (-2 dB at 300 Hz) — low-mid cleanup
3. **Presence boost** (+1.5 dB at 2 kHz) — brass "bite"
4. **High tame** (-2 dB shelf at 7 kHz) — aggressive, brass is piercing
5. **Gentle compress** (-14 dB threshold, 2.5:1, 10ms attack)

### Woodwinds
1. **Highpass** (50 Hz Butterworth) — sub-rumble removal
2. **Mud cut** (-1.5 dB at 250 Hz, Q 0.8) — gentle
3. **Presence boost** (+1 dB at 2.5 kHz) — reed/breath articulation
4. **High tame** (-1 dB shelf at 8 kHz) — preserve breathiness
5. **Gentle compress** (-16 dB threshold, 2:1, 15ms attack)

### Percussion
1. **Highpass** (60 Hz Butterworth) — sub-rumble removal
2. **Click removal** (threshold 6σ) — digital clicks/pops
3. **Presence boost** (+1 dB at 4 kHz) — highest of all stems
4. **High tame** (-1 dB shelf at 10 kHz) — preserve shimmer
5. **Stereo width** (1.2×) — wider than drums
6. **Gentle compress** (-15 dB threshold, 2:1, 8ms attack)

### Synth
1. **Highpass** (80 Hz Butterworth) — avoid bass competition
2. **Mid boost** (+1 dB at 2 kHz, wide Q 0.8) — body/presence
3. **High tame** (-1.5 dB shelf at 9 kHz) — control digital brightness
4. **Stereo width** (1.2×) — pad spread
5. **Gentle compress** (-16 dB threshold, 2:1, 15ms attack) — light

### Other (catch-all)
1. **Noise reduction** (strength 0.3) — lighter than vocals
2. **Mud cut** (-2 dB at 300 Hz) — low-mid cleanup
3. **High tame** (-1.5 dB shelf at 8 kHz) — brightness control

---

## Workflow

### Step 1: Pre-Flight Check
Before polishing, verify:
1. **Audio files exist** in the project
2. **Stems available** — check for individual track exports
3. If no audio files: "No audio files found. Import or record audio first."

### Step 2: Analyze Mix Issues
Call analysis tool to detect:
- Noise floor level
- Low-mid energy (muddiness indicator)
- High-mid energy (harshness indicator)
- Click/pop count
- Sub-bass rumble

Report findings to user with plain-English explanations.

### Step 3: Choose Settings
**Stems are always preferred.** Auto-detect stems — if individual tracks exist, process stems. If not, fall back to full-mix mode.

### Step 4: Dry Run (Preview)
Show what processing would be applied without writing files.

### Step 5: Polish
Apply processing and create `polished/` folder with processed files.

### Step 6: Verify
Check polished output:
- No clipping (peak < 0.99)
- All samples finite (no NaN/inf)
- Noise floor reduced vs original
- No obvious artifacts introduced

### Step 7: Hand Off to Mastering
After polish is verified, call mastering skill with source pointing to polished folder.

---

## Quality Standards

### Before Handoff to Mastering
- [ ] All stems processed (or full mix if no stems)
- [ ] No clipping in polished output
- [ ] Noise floor reduced vs originals
- [ ] No obvious processing artifacts
- [ ] All samples finite (no NaN/inf corruption)
- [ ] Polished files written to polished/ folder

---

## Common Mistakes

### Don't: Over-process
**Wrong:** noise_reduction: 0.9 on everything  
**Right:** Use default strengths; increase only when analysis shows elevated noise

### Don't: Skip analysis
**Wrong:** Apply polish without looking at issues first  
**Right:** Analyze → review → polish

### Don't: Run mastering on raw files after polishing
**Wrong:** Master from raw files, ignoring polished output  
**Right:** Master from polished/ folder

### Don't: Process stems and full mix
**Wrong:** Polish stems, then also polish the full mix  
**Right:** Choose one mode. Stems is always preferred when available.

---

## Remember

1. **Stems first** — always prefer per-stem processing when available
2. **Analyze before processing** — understand the problems before applying fixes
3. **Be conservative** — default settings are calibrated for typical output
4. **Non-destructive** — originals always preserved
5. **Coordinate with mastering** — presence boost at 3 kHz, mastering cuts at 3.5 kHz
6. **Genre matters** — hip-hop needs more bass, rock needs less mud
7. **Dry run first** — preview before committing
8. **Your deliverable**: Polished WAV files → mastering-engineer takes it from there
