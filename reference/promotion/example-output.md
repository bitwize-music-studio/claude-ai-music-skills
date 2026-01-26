# Promo Video Example Output

Visual examples and technical details of generated promo videos.

## Overview

This document shows what to expect when generating promo videos with the `/bitwize-music:promo-director` skill.

## Example: Test Album

**Album:** Test Album (3 tracks)
**Style:** pulse
**Duration:** 15 seconds per video
**Artwork:** Blue/orange color scheme

### Output Structure

```
/path/to/album/
├── 01-test-track.wav
├── 02-another-track.wav
├── 03-third-track.wav
├── album-art.png
├── promo_videos/
│   ├── 01-test-track_promo.mp4  (973 KB)
│   ├── 02-another-track_promo.mp4  (976 KB)
│   └── 03-third-track_promo.mp4  (973 KB)
└── album_sampler.mp4  (not generated in this test)
```

### Technical Specifications

**Video:**
- Resolution: 1080x1920 (9:16 vertical)
- Codec: H.264 (High Profile)
- Frame rate: 30 fps
- Pixel format: yuv420p
- Duration: 15.00 seconds
- Bitrate: ~530 kbps

**Audio:**
- Codec: AAC-LC
- Sample rate: 44.1 kHz
- Channels: Stereo
- Bitrate: 191 kbps

**File sizes:**
- Individual promos: 970-980 KB each (~65 KB/second)
- Album sampler (10 tracks): ~45-50 MB (~115 seconds)

### Visual Breakdown

**Frame composition (vertical 9:16):**

```
┌─────────────────┐
│                 │  Top third: Blurred album artwork (background)
│   [Artwork]     │  Center: Sharp album artwork overlay
│                 │
├─────────────────┤
│                 │  Middle: Audio waveform visualization
│  ╱╲╱╲╱╲╱╲╱╲╱╲   │  - Pulse style: Centered oscilloscope with glow
│ ╱  ╲  ╱  ╲  ╱  │  - Color: Complementary color from artwork
│                 │  - Height: 600px (fills space)
├─────────────────┤
│                 │  Bottom: Text overlays
│  "Track Title"  │  - Title: 64pt, white, drop shadow
│     "bitwize"   │  - Artist: 48pt, white 80% opacity
│                 │
└─────────────────┘
```

### Color Extraction

**Source artwork:** Blue/orange gradient
- Dominant color detected: RGB(32, 160, 224) - Blue
- Complementary color: RGB(234, 125, 71) - Orange (hex: 0xea7d47)
- Waveform uses complementary color for high contrast

**Visual effect:**
- Blue artwork background → Orange waveform (complementary)
- Creates visual pop without clashing
- Color wheel rotation (180°) ensures harmony

### Waveform Style: Pulse

**Technical implementation:**
1. Generate base waveform (centered line, complementary color)
2. Split into 3 layers
3. Apply Gaussian blur:
   - Layer 1: Original (sharp)
   - Layer 2: Blur sigma 8 (tight glow)
   - Layer 3: Blur sigma 25 (wide glow)
4. Blend with screen mode (additive light)
5. Result: Multi-layer glow effect (oscilloscope/EKG aesthetic)

**Reactivity:**
- Waveform responds to audio in real-time
- Peaks show louder moments
- Smooth motion (30 fps)
- Symmetrical (centered around middle)

### Performance Results

**Generation time (without librosa):**
- Single video (15s): ~5-8 seconds
- Batch (3 videos): ~20-25 seconds
- Total throughput: ~3-4 seconds per video

**With librosa (intelligent segment selection):**
- Add ~2-3 seconds per video for audio analysis
- Total: ~6-10 seconds per video

**Platform compatibility:**
- ✅ Instagram Reels - Plays perfectly
- ✅ Twitter - Native playback
- ✅ TikTok - Uploads without issues
- ✅ Facebook - Compatible
- ✅ YouTube Shorts - Works

## Example: Different Styles

### Pulse (Electronic/Hip-Hop)
**Best for:** Electronic, hip-hop, bass-heavy tracks
**Look:** Oscilloscope/EKG with heavy multi-layer glow
**Colors:** Uses complementary color from artwork
**Reactivity:** High (shows every beat)
**File size:** ~65 KB/sec (970 KB for 15s)

**Visual characteristics:**
- Centered waveform
- 3-layer glow (sigma 8, 25)
- Smooth, professional
- Clean and polished

### Bars (Pop/Rock)
**Best for:** Pop, rock, high-energy tracks
**Look:** Fast reactive spectrum bars
**Colors:** White (doesn't use artwork)
**Reactivity:** Very high (frequency analysis)
**File size:** ~60 KB/sec (900 KB for 15s)

**Visual characteristics:**
- Frequency spectrum
- Logarithmic scale
- Responds to bass/treble separately
- Classic "visualizer" aesthetic

### Line (Acoustic/Folk)
**Best for:** Acoustic, folk, singer-songwriter
**Look:** Classic clean waveform
**Colors:** White (simple)
**Reactivity:** Very high (time-domain)
**File size:** ~55 KB/sec (825 KB for 15s)

**Visual characteristics:**
- Minimal processing
- Shows every vocal nuance
- Clean and simple
- Let the music speak

### Mirror (Ambient/Chill)
**Best for:** Ambient, chill, downtempo
**Look:** Mirrored waveform (top/bottom symmetry)
**Colors:** Uses complementary color
**Reactivity:** Medium (smooth blur)
**File size:** ~70 KB/sec (1050 KB for 15s)

**Visual characteristics:**
- Symmetrical top/bottom
- Soft glow
- Meditative, balanced
- Calming aesthetic

### Neon (Synthwave/80s)
**Best for:** Synthwave, 80s revival, electronic
**Look:** Sharp waveform with punchy glow
**Colors:** Uses complementary color (bright)
**Reactivity:** High (tight blur)
**File size:** ~65 KB/sec (975 KB for 15s)

**Visual characteristics:**
- Bright, punchy
- Tight glow (sigma 2)
- Addition blend mode (brighter)
- Retro-futuristic

## Example: Album Sampler

**Format:** All tracks in one video with crossfades
**Duration:** (tracks × 12s) - ((tracks-1) × 0.5s)
**Example:** 10 tracks = 115 seconds (under Twitter 140s limit)

**Structure:**
```
Track 1: 12s
  ├─ Crossfade 0.5s
Track 2: 12s
  ├─ Crossfade 0.5s
Track 3: 12s
  ... (continues)
```

**Visual treatment:**
- Same waveform style throughout (consistency)
- Title changes for each track
- Smooth video/audio crossfades
- Color scheme consistent (extracted once from album art)

**File size:** ~400 KB/sec
- 10 tracks (115s): ~45 MB
- Under platform limits (Instagram 4GB, Twitter 512MB)

## Common Use Cases

### Case 1: Singles Release
**Goal:** Promote 2-3 key tracks on Instagram/Twitter
**Generate:** Individual promos only (`--tracks-only`)
**Style:** pulse or neon (high energy)
**Duration:** 15s (optimal engagement)
**Output:** 2-3 videos (~1 MB each)

### Case 2: Full Album Preview
**Goal:** Show entire album in one video for Twitter
**Generate:** Album sampler only (`--sampler-only`)
**Style:** pulse (professional)
**Clip duration:** 10-12s per track
**Output:** 1 video (~40-50 MB)

### Case 3: Complete Campaign
**Goal:** Videos for all tracks + sampler for variety
**Generate:** Both (default)
**Style:** Match to genre
**Output:** 10 individual promos + 1 sampler (~60 MB total)

### Case 4: A/B Testing
**Goal:** Test different styles to see what performs
**Generate:** Same track, multiple styles
**Styles:** pulse, neon, bars
**Test:** Post one per day, track engagement
**Learn:** Which style resonates with audience

## Quality Checklist

Before publishing any promo video, verify:

**Technical:**
- [ ] Resolution: 1080x1920 (9:16)
- [ ] Frame rate: 30 fps
- [ ] Codec: H.264 (not H.265)
- [ ] Pixel format: yuv420p
- [ ] Duration: Expected length (15s, 30s, etc.)
- [ ] Audio: AAC, 192 kbps, stereo

**Visual:**
- [ ] Waveform reacts to audio
- [ ] Colors match album aesthetic
- [ ] Artwork visible and sharp
- [ ] Text readable on phone screen
- [ ] First frame compelling (thumbnail)
- [ ] No artifacts or glitches

**Content:**
- [ ] Correct track title
- [ ] Correct artist name
- [ ] Title capitalization matches style
- [ ] No typos in text overlays

**Platform:**
- [ ] File size under limit (512 MB Twitter, 4 GB Instagram)
- [ ] Plays on phone (test before batch)
- [ ] Looks good in vertical orientation
- [ ] Loop point smooth (for short form)

## Troubleshooting Examples

### Issue: Waveform Not Visible
**Symptoms:** Video plays but waveform is barely visible
**Cause:** Colors too similar to background
**Fix:** Try different style (neon, bars) or adjust artwork brightness

### Issue: Text Unreadable
**Symptoms:** Title/artist name hard to read on phone
**Cause:** Text too small or poor contrast
**Fix:** Increase TITLE_FONT_SIZE in script, or use brighter background

### Issue: Colors Look Wrong
**Symptoms:** Waveform color doesn't match album aesthetic
**Cause:** Color extraction picked wrong color
**Fix:** Try different style or adjust artwork (remove gradients)

### Issue: File Too Large
**Symptoms:** Video over 100 MB for 15s
**Cause:** High CRF (quality) or high resolution artwork
**Fix:** Increase CRF to 25-28, or resize artwork to 3000x3000

### Issue: Won't Upload to Platform
**Symptoms:** Platform rejects video file
**Cause:** Codec incompatibility (H.265 or wrong pixel format)
**Fix:** Re-encode with H.264 and yuv420p

## Performance Benchmarks

**Hardware:** Typical modern laptop (example: Intel i7, 16GB RAM)

**Single video (15s):**
- Style pulse: 5-8 seconds
- Style bars: 4-6 seconds
- Style circular: 10-15 seconds (slowest)

**Batch (10 videos):**
- Style pulse: 60-90 seconds total
- Style bars: 50-70 seconds total
- Parallel factor: ~1.2x (some ffmpeg optimization)

**Album sampler (10 tracks, 115s):**
- Clip generation: 60-90 seconds
- Concatenation: 20-30 seconds
- Total: 80-120 seconds

**Bottlenecks:**
- ffmpeg filter processing (CPU-bound)
- Disk I/O (reading audio, writing video)
- Color extraction (negligible, <1s)

**Optimization tips:**
- Use SSD for temp files (faster I/O)
- Close other apps (more CPU available)
- Use faster preset (-preset fast vs medium)
- Lower quality for drafts (-crf 28 vs 23)

---

## Example Console Output

```
$ python3 tools/promotion/generate_promo_video.py --batch /path/to/album --style pulse

Found 10 tracks
  librosa not installed, using fallback (20% into track)
  Install with: pip install librosa
  Extracting colors from artwork...
  Dominant: (42, 187, 255) -> Complementary: (255, 170, 42) (hex: 0xffaa2a)
Generating: 01-track_promo.mp4
  ✓ 01-track_promo.mp4
Generating: 02-track_promo.mp4
  ✓ 02-track_promo.mp4
Generating: 03-track_promo.mp4
  ✓ 03-track_promo.mp4
...
Generating: 10-track_promo.mp4
  ✓ 10-track_promo.mp4
```

**Success indicators:**
- ✓ Green checkmarks for each video
- No error messages
- Files appear in promo_videos/ directory
- File sizes in expected range (~1 MB each)

---

## Related Documentation

- `/skills/promo-director/SKILL.md` - Skill workflow
- `/skills/promo-director/visualization-guide.md` - Style gallery
- `/reference/promotion/promo-workflow.md` - Complete workflow
- `/reference/promotion/platform-specs.md` - Platform requirements
