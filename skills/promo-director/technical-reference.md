# Promo Director - Technical Reference

Technical specifications, dependencies, and troubleshooting for the promo-director skill.

---

## Technical Details

### Output Specifications

**Format:**
- Resolution: 1080x1920 (9:16 vertical)
- Codec: H.264 (libx264)
- Audio: AAC, 192 kbps
- Pixel format: yuv420p (universal compatibility)
- Frame rate: 30 fps

**File sizes:**
- Individual promo (15s): ~10-12 MB
- Album sampler (10 tracks, 115s): ~45-50 MB

### Visualization Styles

**Implementation:**

All styles use ffmpeg filter chains:
- `showwaves` - Time-domain waveform
- `showfreqs` - Frequency spectrum
- `avectorscope` - Phase correlation (circular)
- `gblur` - Gaussian blur for glow effects
- `blend` - Layer blending for multi-layer glows

**Color extraction:**

Uses PIL to extract dominant color from album artwork:
1. Resize to 100x100 for speed
2. Filter out very dark/light pixels
3. Quantize color space (32 levels per channel)
4. Pick most saturated of top 5 colors
5. Generate complementary color (rotate 180° on hue wheel)
6. Use for waveform visualization

**Segment selection:**

With librosa (recommended):
1. Load audio (mono, 22050 Hz)
2. Compute RMS energy over time
3. Find 15s window with highest average energy
4. Usually captures chorus or drop

Without librosa (fallback):
- Start at 20% into track (skips intro, gets to meat)

### Platform Compatibility

**Instagram Reels:**
- ✓ 1080x1920 (9:16)
- ✓ Max 90s (our 15s clips fit easily)
- ✓ H.264 codec

**Twitter:**
- ✓ 1080x1920 (9:16)
- ✓ Max 2:20 (140s)
- ✓ File size < 512 MB (our files ~10-50 MB)

**TikTok:**
- ✓ 1080x1920 (9:16)
- ✓ 15-60s (our 15s clips optimal)
- ✓ H.264 codec

**Facebook:**
- ✓ 1080x1920 (9:16)
- ✓ Various durations accepted
- ✓ H.264 codec

## Dependencies

### Required

**ffmpeg:**
- Version: 4.0+
- Filters: showwaves, showfreqs, drawtext, gblur
- Install: `brew install ffmpeg` (macOS), `apt install ffmpeg` (Linux)

**Python 3.8+**

**Python packages:**
- `pillow` - Image processing (color extraction)
- `pyyaml` - Config file reading

### Optional

**Python packages:**
- `librosa` - Audio analysis (intelligent segment selection)
- `numpy` - Required by librosa

**Graceful degradation:**
- If PIL unavailable → Use default cyan color scheme
- If librosa unavailable → Use 20% into track as start point
- If custom font unavailable → Use system default

## Invocation Examples

**Basic (everything):**
```
/bitwize-music:promo-director my-album
```

**Tracks only:**
```
/bitwize-music:promo-director my-album --tracks-only
```

**Sampler only:**
```
/bitwize-music:promo-director my-album --sampler-only
```

**Custom style:**
```
/bitwize-music:promo-director my-album --style neon
```

**Custom duration:**
```
/bitwize-music:promo-director my-album --duration 30
```

## Integration with Other Skills

### Handoff FROM

**mastering-engineer:**

After mastering complete:
```
## Mastering Complete

**Next Steps:**
1. [Optional] Generate promo videos: /bitwize-music:promo-director my-album
2. Begin release workflow: /bitwize-music:release-director my-album
```

### Handoff TO

**release-director:**

After promo generation:
```
Promo videos generated successfully.

**Optional:** Upload to cloud storage: /bitwize-music:cloud-uploader my-album

Ready for release workflow: /bitwize-music:release-director my-album
```

## Future Enhancements

**Not in initial port (defer to future versions):**

- Twitter campaign automation (tweet generation, scheduling)
- n8n workflow integration
- Automatic platform uploads (Instagram, Twitter APIs)
- Analytics tracking (view counts, engagement)
- Custom branding overlays (logos, watermarks)
- Platform-specific optimizations (1:1 for Twitter, 16:9 for YouTube)
- Batch processing multiple albums
- Template system for recurring visual styles

## Troubleshooting

**"ffmpeg not found"**
- Install: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)
- Verify: `ffmpeg -version`

**"showwaves filter not found"**
- ffmpeg compiled without filter support
- Reinstall with full filters: `brew reinstall ffmpeg --with-all`

**"Font not found"**
- Install dejavu fonts: `apt install fonts-dejavu` (Linux)
- macOS: System fonts should work automatically
- Override with: `--font-path /path/to/font.ttf`

**"Color extraction failed"**
- Activate venv: `source ~/.bitwize-music/promotion-env/bin/activate`
- Install PIL in venv: `pip install pillow`
- Or accept default cyan color scheme (still works)

**"librosa not found" (warning, not error)**
- Activate venv: `source ~/.bitwize-music/promotion-env/bin/activate`
- Install in venv: `pip install librosa numpy`
- Or continue with fallback (20% into track)
- Quality still good, just less intelligent segment selection

**Videos generated but won't play**
- Check codec: Should be H.264, not HEVC
- Check pixel format: Should be yuv420p
- Re-encode if needed: `ffmpeg -i bad.mp4 -c:v libx264 -pix_fmt yuv420p fixed.mp4`

**File sizes too large**
- Normal: 10-12 MB per 15s video
- If much larger: Check artwork resolution (should be ≤3000px)
- Reduce artwork size: `convert album.png -resize 3000x3000\> album.png`

**"Expected duration exceeds Twitter limit"**
- For samplers with many tracks
- Solution: Reduce --clip-duration to fit 140s limit
- Example: 15 tracks → 140/15 = ~9s per track

## Model Recommendation

**Sonnet 4.5** - This skill coordinates workflow and runs scripts. Creative output is in the videos themselves (generated by ffmpeg), not by the LLM.

## Version History

- v0.12.0 - Initial implementation (ported from ../music/tools/promotion/)
  - Individual track promos
  - Album sampler generation
  - 9 visualization styles
  - Config integration
  - Automatic color extraction
  - Intelligent segment selection
