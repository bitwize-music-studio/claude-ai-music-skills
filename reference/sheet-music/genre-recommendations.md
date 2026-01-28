# Sheet Music Genre Recommendations

Guide to which genres transcribe well and which present challenges.

---

## Overview

Automated transcription works by detecting pitched notes in audio. The clearer and more distinct the notes, the better the result.

**Best results**: Single instruments, clear melodies, acoustic recordings.

**Worst results**: Dense arrangements, heavy distortion, layered synths.

---

## Excellent Results (90-95% Accuracy)

### Solo Piano

**Why it works**: Single instrument, clear attack, well-defined pitches.

**Expected quality**: Near-perfect transcription, minimal editing needed.

**Tips**: Use sustain pedal notation in MuseScore for final polish.

---

### Singer-Songwriter / Acoustic

**Why it works**: Simple arrangements, voice + guitar/piano, clear melody.

**Expected quality**: 85-95% accurate, mostly minor rhythm fixes.

**Tips**: Focus on vocal melody; guitar can be simplified to chords.

---

### Classical (Solo or Chamber)

**Why it works**: Trained performers, clear articulation, standard notation.

**Expected quality**: 90-95% for solo, 80-90% for small ensembles.

**Tips**: Use stem separation for chamber music. Solo works need minimal editing.

---

### Folk / Americana

**Why it works**: Acoustic instruments, traditional song structures, clear vocals.

**Expected quality**: 85-95% accuracy.

**Tips**: Fiddle parts may need octave correction. Banjo rolls can confuse rhythm detection.

---

## Good Results (75-90% Accuracy)

### Pop (Vocal-Forward)

**Why it works**: Melody-driven, vocals usually prominent in mix.

**Expected quality**: 80-90% for melody, bass may need work.

**Tips**: Focus on vocal line and bass. Ignore pad/synth layers.

---

### Country

**Why it works**: Clear song structure, prominent vocals, traditional instruments.

**Expected quality**: 80-90% accuracy.

**Tips**: Pedal steel can confuse transcription - ignore or simplify. Twangy guitar may need cleaning.

---

### Jazz Standards

**Why it works**: Melodic focus, clear head/solo structure.

**Expected quality**: 80-90% for melody, improvised sections harder.

**Tips**: Transcribe the head (main melody) only. Solos are for advanced manual transcription.

---

### Indie Folk

**Why it works**: Often sparse arrangements, emotional vocals, acoustic instruments.

**Expected quality**: 80-90% accuracy.

**Tips**: Multi-layered harmonies may confuse - extract main vocal line.

---

### R&B (Ballads)

**Why it works**: Prominent vocal melody, relatively clean production.

**Expected quality**: 75-85% accuracy.

**Tips**: Melisma (vocal runs) can be challenging - simplify for playability.

---

## Moderate Results (60-80% Accuracy)

### Rock

**Why it works**: Strong melody lines, defined song structure.

**Challenges**: Distorted guitars, dense arrangements.

**Expected quality**: 70-80% for melody/bass, rhythm guitar harder.

**Tips**: Use stem separation. Focus on vocal + bass. Power chords can be approximated.

---

### Blues

**Why it works**: Simple chord progressions, prominent vocals.

**Challenges**: Guitar bends, vibrato, improvisation.

**Expected quality**: 70-85% accuracy.

**Tips**: Bend notation may need manual addition. Shuffle rhythm needs checking.

---

### Gospel

**Why it works**: Vocal-driven, chord-based accompaniment.

**Challenges**: Multiple vocal parts, call-and-response.

**Expected quality**: 70-80% accuracy.

**Tips**: Focus on lead vocal and bass. Choir parts may need significant cleanup.

---

### Musical Theater

**Why it works**: Clear vocal lines, orchestral backing.

**Challenges**: Complex orchestration, key/tempo changes.

**Expected quality**: 70-85% for vocal line.

**Tips**: Piano reduction is the goal - don't try to capture full orchestration.

---

## Challenging (50-70% Accuracy)

### Hip-Hop / Rap

**Why it works**: Some melodic hooks.

**Challenges**: Rhythm-focused, speech-like vocals, heavy production.

**Expected quality**: 50-70% for hooks, rap verses don't transcribe to pitched notation.

**Tips**: Only transcribe sung hooks/choruses. Beats don't translate to piano well.

---

### Metal

**Why it works**: Strong riffs, defined song structure.

**Challenges**: Heavy distortion, double bass drums, screamed vocals.

**Expected quality**: 50-70% accuracy.

**Tips**: Use stem separation. Focus on clean sections. Riffs may be approximatable.

---

### Electronic / EDM

**Why it works**: Some have clear melodies.

**Challenges**: Synth layers, sound design focus, non-traditional pitches.

**Expected quality**: 50-70% for melodic content.

**Tips**: Only transcribe tracks with clear vocal or lead synth melodies. Ambient sections won't work.

---

### Progressive Rock

**Why it works**: Complex but melodic.

**Challenges**: Tempo changes, odd time signatures, long tracks.

**Expected quality**: 60-75% accuracy.

**Tips**: Work in sections. Manually adjust time signatures. Focus on memorable themes.

---

## Poor Results (Below 50% Accuracy)

### Ambient / Drone

**Why it fails**: No clear melody, sustained textures, sound design focus.

**Recommendation**: Not suitable for sheet music transcription.

---

### Noise / Industrial

**Why it fails**: Non-pitched content, distortion, experimental.

**Recommendation**: Not suitable for traditional notation.

---

### Black Metal

**Why it fails**: Blast beats, tremolo picking, shrieked vocals, lo-fi production.

**Recommendation**: Extremely difficult. Only attempt with extensive manual editing.

---

### Dubstep / Bass Music

**Why it fails**: Sub-bass focus, sound design, drops are noise-like.

**Recommendation**: Transcribe intro/melodic sections only, if any exist.

---

### Avant-Garde / Experimental

**Why it fails**: Unconventional structures, extended techniques, microtones.

**Recommendation**: Requires specialized notation beyond standard transcription.

---

## Genre Decision Matrix

| Genre | Auto-Transcribe? | Manual Effort | Recommendation |
|-------|------------------|---------------|----------------|
| Solo Piano | Yes | Low | Excellent candidate |
| Singer-Songwriter | Yes | Low | Excellent candidate |
| Folk | Yes | Low | Excellent candidate |
| Pop (vocal) | Yes | Medium | Good candidate |
| Country | Yes | Medium | Good candidate |
| Jazz | Yes | Medium | Heads only |
| Rock | Yes | Medium-High | Use stem separation |
| Metal | Maybe | High | Focus on clean sections |
| Hip-Hop | Maybe | High | Hooks/choruses only |
| Electronic | Maybe | High | Melodic tracks only |
| Ambient | No | N/A | Skip |
| Noise | No | N/A | Skip |

---

## Tips for Challenging Genres

### Use Stem Separation

For dense mixes, separate vocals/bass/other first:

```bash
demucs track.wav
# Transcribe vocals.wav and bass.wav separately
```

### Lower Sensitivity

For noisy tracks, reduce AnthemScore sensitivity to capture only the loudest notes.

### Transcribe Sections

Don't transcribe the entire track - focus on memorable sections (hooks, intros, themes).

### Accept Simplification

Sheet music doesn't need to capture every detail. A playable piano reduction is the goal, not a perfect replica.

### Know When to Skip

Some tracks aren't worth transcribing. Dense instrumentals without clear melody are better left as audio.

---

## Quality Expectations by Use Case

| Use Case | Acceptable Accuracy | Effort Level |
|----------|---------------------|--------------|
| Personal reference | 60-70% | Low |
| Cover performance | 80-90% | Medium |
| Licensing package | 90%+ | High |
| Publishing for sale | 95%+ | Very High |

Match your effort to the end use. A quick reference transcription doesn't need the same polish as sheet music for sale.
