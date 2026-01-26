# ffmpeg Technical Reference for Promo Videos

Technical documentation for the ffmpeg commands and filters used in promo video generation.

## Core Command Structure

```bash
ffmpeg -y \
  -ss {start_time} -t {duration} -i {audio_file} \
  -loop 1 -i {artwork_file} \
  -filter_complex '{complex_filter}' \
  -map '[final]' -map '0:a' \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 192k \
  -pix_fmt yuv420p \
  -t {duration} -r 30 \
  {output_file}
```

## Parameter Breakdown

### Input Parameters

**`-y`**
- Overwrite output file without asking

**`-ss {start_time}`**
- Seek to start time before reading input (fast seek)
- Format: seconds (e.g., 45.2) or HH:MM:SS
- Placed before `-i` for input seeking (faster than output seeking)

**`-t {duration}`**
- Duration to process from input
- Format: seconds (15) or HH:MM:SS
- Used twice: once for input clip, once for output duration

**`-i {audio_file}`**
- Input audio file (WAV, MP3, FLAC, M4A supported)
- Stream 0 in filter complex

**`-loop 1 -i {artwork_file}`**
- Input image (PNG, JPG supported)
- Loop image to create video stream
- Stream 1 in filter complex

### Filter Complex

The complex filter graph processes audio and video streams:

```
[1:v] Process artwork → [bg], [art]
[bg][art] Overlay → [base]
[0:a] Generate waveform → [wave]
[base][wave] Overlay → [withwave]
[withwave] Add title text → [withtitle]
[withtitle] Add artist text → [final]
```

### Output Parameters

**`-map '[final]'`**
- Map final video stream from filter complex
- Output video: artwork + waveform + text

**`-map '0:a'`**
- Map audio stream from input 0 (original audio)
- Passthrough audio with video

**`-c:v libx264`**
- Video codec: H.264 (universal compatibility)
- Alternative: libx265 (H.265/HEVC, smaller but less compatible)

**`-preset medium`**
- Encoding speed/quality trade-off
- Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
- faster = quicker encode, larger file
- slower = longer encode, smaller file
- medium = good balance

**`-crf 23`**
- Constant Rate Factor (quality setting)
- Range: 0-51 (lower = better quality, larger file)
- 18: Visually lossless
- 23: High quality (default, recommended)
- 28: Medium quality
- 32+: Low quality (not recommended)

**`-c:a aac`**
- Audio codec: AAC (universal compatibility)
- Alternative: libmp3lame (MP3)

**`-b:a 192k`**
- Audio bitrate: 192 kbps (high quality)
- Alternatives: 128k (medium), 256k (very high)

**`-pix_fmt yuv420p`**
- Pixel format: 4:2:0 chroma subsampling
- Required for universal compatibility (older devices, QuickTime)
- Alternative: yuv444p (better quality, less compatible)

**`-r 30`**
- Frame rate: 30 fps
- Alternative: 24 (cinematic), 60 (smooth)
- 30 fps recommended for social media

---

## Filter Detailed Breakdown

### Artwork Processing

```
[1:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,
     crop={WIDTH}:{HEIGHT},
     gblur=sigma=30,
     colorbalance=bs=-.1:bm=-.1:bh=-.1[bg]
```

**`scale=1080:1920:force_original_aspect_ratio=increase`**
- Scale artwork to fill frame
- force_original_aspect_ratio=increase: Scale up, may crop
- Ensures artwork covers full background

**`crop=1080:1920`**
- Crop to exact output size
- Centers crop automatically

**`gblur=sigma=30`**
- Gaussian blur with sigma (strength) 30
- Creates soft background
- Range: 1 (subtle) to 50+ (very blurred)

**`colorbalance=bs=-.1:bm=-.1:bh=-.1`**
- Darken slightly (-.1 on shadows, midtones, highlights)
- Makes waveform/text pop more
- Range: -1.0 to 1.0

### Artwork Overlay

```
[1:v]scale={WIDTH-200}:-1:force_original_aspect_ratio=decrease[art]
```

**`scale=880:-1`**
- Scale artwork to 880px wide (1080 - 200px padding)
- Height: -1 (maintain aspect ratio)
- force_original_aspect_ratio=decrease: Scale down, maintain aspect

**`[bg][art]overlay=(W-w)/2:(H-h)/2-200[base]`**
- Overlay sharp artwork on blurred background
- X: (W-w)/2 - Center horizontally
- Y: (H-h)/2-200 - Center vertically, shift up 200px
- Creates layered effect: blurred bg + sharp artwork

### Waveform Generation

#### showwaves Filter

```
[0:a]showwaves=s={WIDTH}x{viz_height}:mode=cline:scale=sqrt:colors={color}:rate={FPS}[wave]
```

**`s=1080x600`**
- Size: width x height pixels
- viz_height typically 600px (large, visible)

**`mode=cline`**
- Centered line waveform
- Alternatives:
  - point: Individual sample points
  - line: Line from bottom
  - p2p: Peak-to-peak
  - cline: Centered line (recommended)

**`scale=sqrt`**
- Amplitude scaling
- Options:
  - lin: Linear (natural)
  - log: Logarithmic (compresses)
  - sqrt: Square root (balanced, recommended)
  - cbrt: Cubic root (more compression)

**`colors={hex_color}`**
- Color in hex: 0xRRGGBB
- Example: 0xffaa2a (orange)
- Can use color names: red, blue, etc.

**`rate=30`**
- Update rate (fps)
- Match output frame rate

#### showfreqs Filter

```
[0:a]showfreqs=s={WIDTH}x{viz_height}:mode=line:ascale=sqrt:fscale=log:colors={color}:win_size=2048:overlap=0.5[wave]
```

**`mode=line`**
- Line graph mode
- Alternatives: bar, dot

**`ascale=sqrt`**
- Amplitude scale (same as showwaves)

**`fscale=log`**
- Frequency scale: logarithmic
- Alternatives:
  - lin: Linear frequency (bass compressed)
  - log: Logarithmic (balanced, recommended)

**`win_size=2048`**
- FFT window size
- Larger = more frequency resolution, less time resolution
- Range: 256-8192
- 2048 recommended for music

**`overlap=0.5`**
- Window overlap (0.0-1.0)
- Higher = smoother but slower
- 0.5 = good balance

#### avectorscope Filter (Circular)

```
[0:a]avectorscope=s=600x600:mode=lissajous_xy:scale=sqrt:draw=line:zoom=1.5:rc=255:gc=255:bc=255[wave_raw]
```

**`s=600x600`**
- Square output (will be padded to frame)

**`mode=lissajous_xy`**
- Lissajous mode (XY phase correlation)
- Creates circular/spiral patterns
- Alternatives:
  - lissajous: Classic Lissajous
  - lissajous_xy: XY correlation (recommended)

**`scale=sqrt`**
- Same as showwaves

**`draw=line`**
- Draw mode: connected lines
- Alternative: dot (points)

**`zoom=1.5`**
- Zoom level (1.0 = normal)
- Higher = larger patterns

**`rc=255:gc=255:bc=255`**
- RGB color (white in this case)
- Full control over color channels

### Blur and Blending (Glow Effects)

```
[wave_core]split=3[c1][c2][c3];
[c2]gblur=sigma=8[glow1];
[c3]gblur=sigma=25[glow2];
[c1][glow1]blend=all_mode=screen[layer1];
[layer1][glow2]blend=all_mode=screen[wave]
```

**`split=3`**
- Split stream into 3 copies
- Core + 2 blur layers

**`gblur=sigma=8`**
- Gaussian blur, tight glow
- sigma controls blur strength

**`gblur=sigma=25`**
- Gaussian blur, wide glow
- Creates soft outer glow

**`blend=all_mode=screen`**
- Blend mode: screen (additive light)
- Alternatives:
  - addition: Brighter, more intense
  - normal: Standard alpha blend
  - multiply: Darker
  - screen: Additive (recommended for glow)

**`all_opacity=0.5`**
- Blend opacity (0.0-1.0)
- Optional, controls glow intensity

### Text Overlays

```
drawtext=text='{title}':
         fontfile={font_path}:
         fontsize=64:
         fontcolor=#ffffff:
         x=(w-text_w)/2:
         y=h-130:
         shadowcolor=black:shadowx=2:shadowy=2
```

**`text='{title}'`**
- Text to display
- Must escape: colons (\:), percent (\%), backslash (\\)
- Apostrophes removed (break ffmpeg parsing)

**`fontfile={path}`**
- Path to TrueType font file (.ttf)
- Example: /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf

**`fontsize=64`**
- Font size in points
- Title: 64pt (large)
- Artist: 48pt (smaller)

**`fontcolor=#ffffff`**
- Text color (hex or color name)
- #ffffff = white
- Can use rgba(255,255,255,0.8) for transparency

**`x=(w-text_w)/2`**
- X position: centered
- w = video width
- text_w = text width (calculated)

**`y=h-130`**
- Y position: 130px from bottom
- h = video height

**`shadowcolor=black:shadowx=2:shadowy=2`**
- Drop shadow
- Color: black
- Offset: 2px right, 2px down
- Makes text readable over busy backgrounds

---

## Common Modifications

### Change Video Duration

```bash
# 30 second video instead of 15
-t 30
```

### Change Resolution

```bash
# 720p vertical instead of 1080p
WIDTH = 720
HEIGHT = 1280
```

### Change Frame Rate

```bash
# 24 fps (cinematic) instead of 30
-r 24
rate=24  # in showwaves
```

### Change Quality

```bash
# Higher quality (larger file)
-crf 18

# Lower quality (smaller file)
-crf 28
```

### Change Audio Bitrate

```bash
# 256 kbps (higher quality)
-b:a 256k

# 128 kbps (smaller file)
-b:a 128k
```

### Change Encoding Speed

```bash
# Faster encoding (larger file)
-preset fast

# Slower encoding (smaller file)
-preset slow
```

### Add Fade In/Out

```bash
# Add to filter complex
fade=in:0:30,fade=out:420:30  # 30 frame fade in/out
```

---

## Troubleshooting

### "Unknown filter 'showwaves'"

ffmpeg compiled without filter support.

**Check available filters:**
```bash
ffmpeg -filters | grep show
```

**Reinstall with filters:**
```bash
# macOS
brew reinstall ffmpeg

# Linux
apt install ffmpeg
```

### "No such filter: 'drawtext'"

Font support not compiled in.

**Check:**
```bash
ffmpeg -filters | grep drawtext
```

**Reinstall with libfreetype:**
```bash
# macOS
brew reinstall ffmpeg --with-freetype

# Linux
apt install ffmpeg libfreetype6-dev
```

### "Invalid pixel format"

Using incompatible pixel format.

**Fix:**
```bash
-pix_fmt yuv420p
```

### Video Won't Play on Some Devices

Likely codec/format issue.

**Re-encode for compatibility:**
```bash
ffmpeg -i input.mp4 \
  -c:v libx264 -profile:v baseline -level 3.0 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  compatible.mp4
```

### Colors Look Washed Out

Colorspace issue.

**Add colorspace tag:**
```bash
-colorspace bt709 -color_primaries bt709 -color_trc iec61966-2-1
```

### File Size Too Large

**Increase compression:**
```bash
-crf 28  # Instead of 23
```

**Or reduce bitrate:**
```bash
-b:v 2M  # 2 Mbps video bitrate
```

### Encoding Too Slow

**Use faster preset:**
```bash
-preset fast  # Instead of medium
```

**Or reduce resolution:**
```bash
-vf scale=720:1280
```

### Audio Out of Sync

Usually caused by input seeking issues.

**Try output seeking instead:**
```bash
# Move -ss after inputs
ffmpeg -i audio.wav -loop 1 -i art.png -ss 45 -t 15 ...
```

---

## Performance Optimization

### Fast Preview

For quick tests, use ultrafast preset:
```bash
-preset ultrafast -crf 30
```

### Batch Processing

Use xargs or GNU parallel for multiple videos:
```bash
ls *.wav | parallel python3 generate_promo_video.py {} art.png
```

### GPU Acceleration (if available)

Use hardware encoding:
```bash
-c:v h264_videotoolbox  # macOS
-c:v h264_nvenc         # NVIDIA GPU
-c:v h264_qsv           # Intel Quick Sync
```

Note: May reduce quality slightly, but much faster.

---

## Advanced Techniques

### Multi-Layer Glow

```bash
# Split into 4+ layers for intense glow
split=5[c1][c2][c3][c4][c5];
[c2]gblur=sigma=4[g1];
[c3]gblur=sigma=12[g2];
[c4]gblur=sigma=25[g3];
[c5]gblur=sigma=50[g4];
[c1][g1]blend=all_mode=screen[l1];
[l1][g2]blend=all_mode=screen[l2];
[l2][g3]blend=all_mode=screen[l3];
[l3][g4]blend=all_mode=screen[final]
```

### Color Cycling

Animate waveform color:
```bash
# Use geq filter for HSV color cycling
geq='r=128+128*sin(T):g=128+128*sin(T+2*PI/3):b=128+128*sin(T+4*PI/3)'
```

### Particle Effects

Combine waveform with particles:
```bash
# Overlay particle video on top of waveform
[base][particles]overlay=0:0[final]
```

### Custom Fonts

Use any TrueType font:
```bash
fontfile=/path/to/your/font.ttf
```

---

## Filter Cheat Sheet

| Filter | Purpose | Example |
|--------|---------|---------|
| scale | Resize video | scale=1080:1920 |
| crop | Cut to size | crop=1080:1920 |
| pad | Add borders | pad=1080:1920:0:0 |
| overlay | Layer videos | overlay=x:y |
| showwaves | Audio waveform | showwaves=s=1080x600:mode=cline |
| showfreqs | Audio spectrum | showfreqs=mode=line:fscale=log |
| avectorscope | Phase scope | avectorscope=mode=lissajous_xy |
| gblur | Gaussian blur | gblur=sigma=10 |
| blend | Composite layers | blend=all_mode=screen |
| drawtext | Add text | drawtext=text='Hello':fontsize=64 |
| fade | Fade in/out | fade=in:0:30 |
| split | Duplicate stream | split=3[a][b][c] |
| vflip | Flip vertical | vflip |
| hflip | Flip horizontal | hflip |

---

## Reference Links

**ffmpeg Documentation:**
- Official docs: https://ffmpeg.org/ffmpeg-filters.html
- Wiki: https://trac.ffmpeg.org/wiki

**Filters:**
- showwaves: https://ffmpeg.org/ffmpeg-filters.html#showwaves
- showfreqs: https://ffmpeg.org/ffmpeg-filters.html#showfreqs
- drawtext: https://ffmpeg.org/ffmpeg-filters.html#drawtext

**Guides:**
- H.264 encoding: https://trac.ffmpeg.org/wiki/Encode/H.264
- AAC encoding: https://trac.ffmpeg.org/wiki/Encode/AAC
