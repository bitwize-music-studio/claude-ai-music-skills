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
**MCP command**: `master_audio(album_slug, genre="hip-hop")`

**Characteristics**:
- Strong low end
- Clear vocals
- Punchy kick/snare

### Rock / Alternative
**LUFS target**: -12 to -14 LUFS
**Dynamics**: Wide dynamic range, preserve peaks
**EQ focus**: Guitar presence (800 Hz - 3 kHz), avoid harsh highs
**MCP command**: `master_audio(album_slug, genre="rock")`

**Characteristics**:
- Guitar energy
- Drum impact
- Vocal cut-through

### Electronic / EDM
**LUFS target**: -10 to -12 LUFS (can go louder)
**Dynamics**: Heavy compression, consistent energy
**EQ focus**: Sub-bass (30-50 Hz), sparkle on top (10+ kHz)
**MCP command**: `master_audio(album_slug, genre="edm")`

**Characteristics**:
- Massive bass
- Sustained energy
- Bright, polished highs

### Folk / Acoustic
**LUFS target**: -14 to -16 LUFS
**Dynamics**: Preserve natural dynamics
**EQ focus**: Warmth (200-500 Hz), natural highs
**MCP command**: `master_audio(album_slug, genre="folk")`

**Characteristics**:
- Natural, intimate
- Wide dynamic range
- Minimal processing

### Country
**LUFS target**: -13 to -14 LUFS
**Dynamics**: Moderate, radio-ready
**EQ focus**: Vocal clarity, steel guitar presence
**MCP command**: `master_audio(album_slug, genre="country")`

**Characteristics**:
- Clear vocals
- Instrument separation
- Warm, polished

### Jazz / Classical
**LUFS target**: -16 to -18 LUFS
**Dynamics**: Preserve full dynamic range
**EQ focus**: Natural tonal balance, minimal EQ
**MCP command**: `master_audio(album_slug, genre="jazz")`

**Characteristics**:
- Wide dynamics
- Natural room sound
- Uncompressed peaks

### Soundtrack / Film Theme Songs
**LUFS target**: -14 LUFS (power ballads: -13 LUFS; intimate film ballads: -15 LUFS)
**Dynamics**: Moderate compression — vocal always intelligible and forward; preserve dynamic arc from quiet verse to full-belt chorus; avoid over-compressing orchestral builds
**EQ focus**: Vocal presence (2-5 kHz), orchestral warmth (200-600 Hz), gentle high-mid cut to control brass brightness without losing sparkle
**MCP command**: `master_audio(album_slug, genre="soundtrack")`

**Characteristics**:
- Voice absolutely upfront — this is a song, not underscore; lyrics must be heard
- Power ballads (-13 LUFS) compete with mainstream pop — aggressive but controlled limiting
- Bond-style themes: wide dynamic range, brass transients need headroom, tremolo guitar clarity at 2-4 kHz
- Disco soundtracks: punchy kick at 60-80 Hz, four-on-the-floor energy; treat like Funk at -14 LUFS
- Intimate Golden Age ballads (-15 LUFS): preserve natural room acoustic, minimal processing
- Needle drops use their original mastering — no remastering needed for compilation context

### Musicals / Musical Theater
**LUFS target**: -16 LUFS (contemporary rock musicals: -14 LUFS)
**Dynamics**: Wide dynamic range preserved — intimate ballads must stay quiet, showstoppers can soar; avoid over-compression that flattens the emotional arc
**EQ focus**: Vocal intelligibility (1-4 kHz), pit orchestra warmth (200-600 Hz), gentle high-mid cut to tame bright Suno-generated brass
**MCP command**: `master_audio(album_slug, genre="musicals")`

**Characteristics**:
- Voice always upfront and intelligible — lyrics carry the drama
- Wide dynamic swing between ballad passages and full-company numbers
- Pit orchestra body in 200-600 Hz range needs warmth without muddiness
- Brass and strings must coexist without harshness above 4 kHz
- Contemporary/rock musicals (Hamilton style) can push to -14 LUFS with more compression
- Cast album aesthetic: theatrical room ambience preserved, not over-dried

### Schlager
**LUFS target**: -12 to -14 LUFS
**Dynamics**: Moderate-to-heavy compression, radio-ready loudness
**EQ focus**: Vocal presence (2-5 kHz), bass drum punch (60-100 Hz), bright top end (8-12 kHz for shimmer)
**MCP command**: `master_audio(album_slug, genre="schlager")`

**Characteristics**:
- Vocals dominant and upfront
- Kick drum punchy and defined
- Bright, polished, singalong-ready
- Synthesizer and brass clarity
- Party tracks can push to -11 LUFS

### Middle Eastern Pop
**LUFS target**: -14 LUFS (mahraganat: -12 LUFS)
**Dynamics**: Moderate compression, preserve vocal ornamentations and melismatic runs
**EQ focus**: Vocal presence (1-4 kHz), oud/qanun body (200-600 Hz), darbuka attack (3-5 kHz), gentle high-mid cut to tame synth harshness
**MCP command**: `master_audio(album_slug, genre="middle-eastern-pop")`

**Characteristics**:
- Melismatic vocals need headroom — avoid over-compressing ornamental runs
- Quarter-tone melodies require careful limiting to avoid pitch artifacts
- Darbuka and riq transients should remain crisp and defined
- Raï tracks: slightly more aggressive compression, accordion warmth preserved
- Mahraganat: louder target (-12 LUFS), heavier compression, bass-forward mix

### Chanson
**LUFS target**: -14 to -16 LUFS
**Dynamics**: Light compression, preserve natural dynamics and rubato phrasing
**EQ focus**: Vocal transparency (1-4 kHz), accordion warmth (200-800 Hz), gentle high cut above 12 kHz for vintage warmth
**MCP command**: `master_audio(album_slug, genre="chanson")`

**Characteristics**:
- Voice is absolute center — pristine clarity without harshness
- Accordion/guitar body preserved, not thinned out
- Room ambience and intimacy maintained
- Dynamic range wider than pop — quiet passages stay quiet
- Nouvelle chanson with electronic elements can target -14 LUFS; traditional acoustic chanson sits at -15 to -16

### Children's Music
**LUFS target**: -14 LUFS (lullabies: -16 LUFS)
**Dynamics**: Light compression, consistent volume critical for playback in cars and classrooms
**EQ focus**: Vocal clarity (2-4 kHz), warmth (200-500 Hz), gentle high-mid cut to avoid harshness on small speakers
**MCP command**: `master_audio(album_slug, genre="childrens-music")`

**Characteristics**:
- Vocals must be clear, warm, and front-center at all times
- Avoid harsh sibilance — small ears are sensitive to high frequencies
- Lullabies target -16 LUFS with minimal compression for gentle dynamics
- Singalong/action songs can sit at -14 LUFS with moderate compression
- Low dynamic range preferred — avoid sudden volume jumps (safety for children's playback)
- Ukulele and xylophone brightness tamed without losing sparkle

### Bollywood
**LUFS target**: -14 LUFS (classical filmi/ghazal: -15 LUFS; bhangra/item numbers: -13 LUFS)
**Dynamics**: Moderate compression; preserve vocal ornamentation (meend glides and taan runs need headroom); allow natural dynamic arc from intimate verse to full-orchestra chorus
**EQ focus**: Vocal clarity (2-5 kHz), tabla and dholak attack (3-5 kHz), string warmth (200-600 Hz), gentle high-mid cut to tame Suno-generated brightness in orchestral layers
**MCP command**: `master_audio(album_slug, genre="bollywood")`

**Characteristics**:
- Playback vocal is always the center — strings, tabla, and harmonium exist to support it, never overwhelm
- Ornamental vocal runs (meend, taan) require headroom — over-compression smears them into muddy sustain
- Tabla transients should remain crisp and defined; dholak body (150-250 Hz) needs warmth without muddiness
- Classical filmi tracks (-15 LUFS): preserve the wide dynamic range between intimate vocal passages and full orchestral moments
- Bhangra and item numbers (-13 LUFS): more compression acceptable, dhol punch at 60-100 Hz, bright top end for dancefloor energy
- Sitar and bansuri harmonics sit in 1.5-4 kHz range — avoid over-cutting here or they disappear in the mix
- Contemporary Bollywood pop with electronic production: treat sub-bass and EDM elements like mainstream pop; maintain vocal warmth on top

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
```
fix_dynamic_track(album_slug, track_filename="acoustic-ballad.wav")
```
- Applies moderate compression
- Raises quiet parts
- Preserves natural feel

**Alternative**: Accept quieter LUFS (-16 to -18) if genre appropriate

### Problem: Track Sounds Harsh/Bright

**Cause**: Suno often generates bright vocals/highs

**Solution**:
```
master_audio(album_slug, cut_highmid=-3.0)
```
- Increase high-mid cut to -3 dB
- Reduces harshness at 2-4 kHz

### Problem: Bass Too Loud/Muddy

**Cause**: Suno can over-generate low end

**Solution**:
```
master_audio(album_slug, genre="hip-hop")
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
```
master_audio(album_slug, ceiling_db=-1.5)
```
- Targets -1.5 dBTP instead of -1.0
- More headroom for encoding

### Problem: Track Sounds Squashed/Lifeless

**Cause**: Over-compression trying to hit LUFS target

**Solution**:
```
master_audio(album_slug, target_lufs=-16.0)
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
