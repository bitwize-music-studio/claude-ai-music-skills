# Promo Video Visualization Styles

Guide to the 9 available visualization styles for promo videos. Each style uses ffmpeg filters to create unique audio-reactive visuals.

## Style Gallery

### 1. Pulse (Default)

**Best for:** Electronic, hip-hop, bass-heavy tracks

**Description:**
- Oscilloscope/EKG style waveform
- Centered, highly reactive
- Heavy multi-layer glow effect (3 blur layers)
- Clean and professional
- Color extracted from album artwork

**Technical:**
```
showwaves → split 3 layers → gblur (sigma 8, 25) → blend with screen mode
```

**Use when:**
- Need professional, polished look
- Electronic or hip-hop genre
- Want strong visual impact without being distracting
- Album art has good color palette

---

### 2. Bars

**Best for:** Pop, rock, high-energy tracks

**Description:**
- Fast reactive spectrum bars
- Frequency-domain visualization
- Highly responsive to beat
- Classic club/visualizer aesthetic
- White color (doesn't use artwork colors)

**Technical:**
```
showfreqs → line mode → sqrt scale → log frequency scale
```

**Use when:**
- Need maximum beat reactivity
- Pop or rock genre
- Want classic "music visualizer" look
- Artwork colors don't fit video aesthetic

---

### 3. Line

**Best for:** Acoustic, folk, singer-songwriter

**Description:**
- Classic clean waveform
- Time-domain, centered
- Minimal processing
- Highly reactive, shows every nuance
- White color (clean and simple)

**Technical:**
```
showwaves → cline mode → sqrt scale → centered
```

**Use when:**
- Acoustic or folk genre
- Want to show vocal/instrument detail
- Minimal, clean aesthetic preferred
- Let the music speak for itself

---

### 4. Mirror

**Best for:** Ambient, chill, downtempo

**Description:**
- Mirrored waveform (top and bottom symmetrical)
- Soft glow effect
- Meditative, balanced aesthetic
- Creates visual symmetry
- Uses complementary color from artwork

**Technical:**
```
showwaves → split → flip bottom → vstack → gblur → blend
```

**Use when:**
- Ambient or chill genre
- Want symmetrical, balanced look
- Softer, less aggressive aesthetic
- Calming, meditative vibe

---

### 5. Mountains

**Best for:** EDM, bass-heavy, cinematic

**Description:**
- Dual-channel frequency spectrum
- Looks like mountain ranges
- Mirrored top/bottom
- Soft glow, ethereal
- Uses complementary color from artwork

**Technical:**
```
showfreqs → line mode → split → flip → vstack → gblur → blend
```

**Use when:**
- EDM or cinematic genre
- Want dramatic, epic visual
- Frequency content is interesting (wide spectrum)
- Prefer smoother motion over sharp reactivity

---

### 6. Colorwave

**Best for:** Indie, alternative, dream pop

**Description:**
- Clean waveform with subtle glow
- Single complementary color
- Softer than pulse, more refined than line
- Balanced opacity blend
- Modern, polished look

**Technical:**
```
showwaves → split → gblur (sigma 4) → blend with screen mode at 50% opacity
```

**Use when:**
- Indie or alternative genre
- Want refined, polished aesthetic
- Not too aggressive, not too minimal
- Artwork has good complementary color

---

### 7. Neon

**Best for:** Synthwave, 80s revival, electronic

**Description:**
- Sharp waveform with punchy glow
- Bright neon aesthetic
- Tight blur (sigma 2), high intensity
- Addition blend mode (brighter than screen)
- Retro-futuristic vibe

**Technical:**
```
showwaves → split → gblur (sigma 2) → blend with addition mode at 60% opacity
```

**Use when:**
- Synthwave or 80s genre
- Want bright, punchy, retro aesthetic
- High energy, attention-grabbing
- Artwork has vibrant colors

---

### 8. Dual

**Best for:** Experimental, avant-garde, electronic

**Description:**
- Two separate waveforms (top and bottom)
- Top: complementary color (bright)
- Bottom: dominant color (from artwork)
- Bottom waveform flipped
- Contrasting colors create visual tension

**Technical:**
```
Two showwaves → different colors → flip bottom → vstack
```

**Use when:**
- Experimental or avant-garde genre
- Want visual contrast and tension
- Artwork has strong color palette
- Prefer unique, distinctive look

---

### 9. Circular

**Best for:** Abstract, experimental, glitch

**Description:**
- Audio vectorscope (Lissajous patterns)
- Creates wild circular/spiral patterns
- Phase correlation visualization
- Unpredictable, mesmerizing
- White on black (doesn't use artwork colors)

**Technical:**
```
avectorscope → lissajous_xy mode → sqrt scale → padded to center
```

**Use when:**
- Abstract or experimental genre
- Want completely unique aesthetic
- Stereo field is interesting (wide mix)
- Prefer abstract over literal waveform
- Glitch, IDM, or experimental electronic

---

## Genre Recommendations

| Genre | Primary Choice | Alternative |
|-------|---------------|-------------|
| Electronic | pulse | neon, colorwave |
| Hip-Hop | pulse | bars |
| Pop | bars | pulse |
| Rock | bars | line |
| Folk | line | mirror |
| Acoustic | line | colorwave |
| Ambient | mirror | mountains |
| EDM | pulse | mountains, neon |
| Synthwave | neon | pulse |
| Jazz | line | bars |
| Classical | line | colorwave |
| Metal | bars | pulse |
| Indie | colorwave | line |
| Country | line | bars |
| Experimental | circular | dual |

## Color Theory

**How colors are extracted:**

1. Dominant color: Most saturated color from album artwork (filtered to avoid black/white)
2. Complementary color: Opposite on color wheel (180° hue rotation), boosted saturation/lightness
3. Analogous colors: ±30° on color wheel (used in "dual" style)

**Which styles use colors:**

**Artwork colors:**
- pulse (complementary)
- mirror (complementary)
- mountains (complementary)
- colorwave (complementary)
- neon (complementary)
- dual (dominant + complementary)

**Fixed colors (white):**
- bars
- line
- circular

**Why use white:**
- Universal compatibility (works with any artwork)
- Maximum contrast on dark background
- Classic "visualizer" aesthetic
- Less processing (faster rendering)

## Performance Considerations

**Rendering speed (slowest to fastest):**

1. **circular** - Most complex (vectorscope calculations)
2. **dual** - Two waveform passes
3. **pulse** - Three blur layers + blending
4. **mountains** - Frequency analysis + multiple processing steps
5. **mirror** - Split + flip + blur
6. **neon** - Two layers + blur
7. **colorwave** - Two layers + blur
8. **bars** - Frequency analysis only
9. **line** - Simplest (single waveform pass)

**Typical rendering times (15s video):**
- Fast (line, bars): ~20-30 seconds
- Medium (colorwave, neon, mirror): ~30-45 seconds
- Slow (pulse, mountains, dual): ~45-60 seconds
- Very slow (circular): ~60-90 seconds

**Batch processing (10 tracks):**
- Fast styles: ~5-7 minutes total
- Medium styles: ~7-10 minutes total
- Slow styles: ~10-15 minutes total

## Customization

**To add custom style:**

Edit `tools/promotion/generate_promo_video.py`:

```python
elif style == "custom":
    viz_filter = f"""[0:a]showwaves=s={WIDTH}x{viz_height}:mode=cline:scale=sqrt:colors={color2}:rate={FPS}[wave]"""
```

**Parameters to adjust:**

- `mode`: cline (centered line), line (from bottom), p2p (peak-to-peak)
- `scale`: sqrt (balanced), lin (linear), log (logarithmic), cbrt (cubic root)
- `colors`: Hex color (0xRRGGBB)
- `rate`: Frame rate (30 recommended)
- `gblur sigma`: Blur amount (2-25, higher = more blur)
- `blend mode`: screen (additive light), addition (brighter), normal

## Platform-Specific Considerations

**Instagram Reels:**
- Prefer pulse, bars, or neon (high energy)
- Avoid circular (too abstract for Instagram audience)
- Short attention span: reactivity matters

**Twitter:**
- Prefer pulse or colorwave (professional)
- Avoid overly complex styles (small preview thumbnails)
- Clean, readable aesthetic works best

**TikTok:**
- Prefer bars, pulse, or neon (gen-z aesthetic)
- High energy, attention-grabbing
- Avoid minimal styles (line, mirror)

**Artist website:**
- Any style works
- Consider matching to album aesthetic
- Circular or dual for art/experimental projects

## Examples by Use Case

**"I want maximum attention on Instagram"**
→ Use `neon` or `pulse` - High energy, bright, eye-catching

**"I want professional, polished promo for Twitter"**
→ Use `pulse` or `colorwave` - Clean, refined, modern

**"I want to show off my artwork colors"**
→ Use `pulse`, `dual`, or `colorwave` - Extracts colors from art

**"I want classic visualizer aesthetic"**
→ Use `bars` or `line` - Timeless, recognizable

**"I want something unique and different"**
→ Use `circular` or `dual` - Stands out, memorable

**"I want fast rendering for quick turnaround"**
→ Use `line` or `bars` - Fastest render times

**"I want ambient, chill vibe"**
→ Use `mirror` or `mountains` - Soft, meditative

## Testing Recommendations

**Before batch-generating all tracks:**

1. Generate one test video with your preferred style
2. View on phone (most common viewing device)
3. Check:
   - Waveform reactivity (too much/too little?)
   - Color scheme (matches album aesthetic?)
   - Readability (title/artist clear?)
   - Artwork visibility (not obscured by waveform?)
4. Adjust if needed, then batch-generate all tracks

**Quick test command:**
```bash
python3 tools/promotion/generate_promo_video.py \
  track-01.wav album.png "Track Title" \
  --style pulse \
  -o test.mp4
```

## Advanced Techniques

**Combine multiple videos:**

For variety, use different styles per track:
- Intros/outros: line or mirror (minimal)
- Choruses: pulse or neon (high energy)
- Bridges: colorwave or mountains (transitional)

**Style progression:**

For album sampler, consider style transitions:
- Start calm: mirror → colorwave
- Build energy: pulse → bars → neon
- Peak intensity: dual or circular
- Wind down: colorwave → line

**Match tempo:**

Some styles work better with tempo:
- Fast (140+ BPM): bars, neon, pulse
- Medium (90-140 BPM): pulse, colorwave, line
- Slow (<90 BPM): mirror, mountains, line
