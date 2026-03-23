# Visual Styles & References

Reference tables for album art visual direction.

---

## Photography Styles

| Style | Effect | Use For |
|-------|--------|---------|
| **Editorial photography** | Professional, magazine-quality | Documentary, true crime |
| **Portrait photography** | Subject-focused, intimate | Character studies |
| **Street photography** | Candid, urban, raw | Hip-hop, gritty rock |
| **Fashion photography** | Stylized, dramatic lighting | Pop, R&B, high-concept |
| **Documentary photography** | Authentic, journalistic | True stories, historical |
| **Fine art photography** | Artistic, intentional | Concept albums, experimental |

---

## Illustration Styles

| Style | Effect | Use For |
|-------|--------|---------|
| **Digital illustration** | Clean, modern, versatile | Tech topics, contemporary |
| **Vintage poster art** | Retro, nostalgic | Historical, throwback |
| **Comic book art** | Bold, dramatic, action | Narrative, dynamic |
| **Minimalist illustration** | Simple, iconic | Abstract concepts |
| **Surrealist painting** | Dreamlike, symbolic | Experimental, avant-garde |
| **Technical illustration** | Precise, detailed | Tech, engineering topics |

---

## Artistic Movements

| Movement | Aesthetic | Use For |
|----------|-----------|---------|
| **Film noir** | High contrast, shadows, mystery | Crime, thriller themes |
| **Cyberpunk** | Neon, futuristic, gritty | Tech, dystopian |
| **Art deco** | Geometric, luxury, golden age | Sophisticated, classic |
| **Brutalism** | Raw, concrete, stark | Industrial, harsh |
| **Vaporwave** | Retro-futuristic, pastels, surreal | Electronic, ironic |
| **Minimalism** | Simple, essential, clean | Abstract, meditative |

---

## Color Psychology

### Emotional Color Palettes

**Dark/Serious (True Crime, Heavy Topics)**:
- Black, charcoal, deep navy
- Desaturated colors
- Minimal bright accents
- High contrast

**Energetic/Aggressive (Rock, Hip-Hop)**:
- Red, orange, electric blue
- High saturation
- Bold combinations
- Sharp contrasts

**Calm/Introspective (Folk, Ambient)**:
- Earth tones (brown, tan, moss green)
- Pastels (soft pink, blue, cream)
- Low saturation
- Gentle gradients

**Futuristic/Electronic (EDM, Synth)**:
- Neon (cyan, magenta, electric purple)
- Deep blacks for contrast
- Glowing effects
- Synthetic feel

**Nostalgic/Vintage (Country, Classic)**:
- Faded colors (sepia, washed denim)
- Warm yellows and oranges
- Muted reds and greens
- Film grain texture

---

## Genre Visual Language

### Hip-Hop/Rap
- Bold typography, street photography
- Gold, black, red color schemes
- Urban environments, luxury items
- High contrast, dramatic lighting

### Electronic/EDM
- Geometric shapes, fractals
- Neon colors, glowing elements
- Abstract, futuristic
- Motion blur, energy

### Rock/Alternative
- Raw, gritty textures
- Band photography (live or candid)
- Analog aesthetics (film grain, vintage)
- Muted or saturated colors

### Folk/Acoustic
- Natural imagery, landscapes
- Warm earth tones
- Handmade aesthetics, organic
- Intimate, close-up details

### Country
- Americana imagery (roads, fields, skylines)
- Vintage trucks, boots, guitars
- Sunset colors, dusty tones
- Nostalgic, authentic

---

## Platform Specifications

### Size Requirements

**Streaming platforms**:
- **Minimum**: 3000 x 3000 px
- **Recommended**: 4000 x 4000 px
- **Format**: PNG or JPEG, RGB color space
- **Aspect ratio**: 1:1 (square)

**SoundCloud**:
- 800 x 800 px minimum
- Displays well at small sizes

**distributor** (Spotify, Apple Music, etc.):
- 3000 x 3000 px minimum
- 72 DPI minimum (300 DPI recommended)
- RGB color mode
- No blurriness or pixelation

### Thumbnail Test

**Critical**: Art must work at 200x200px or smaller

**Test**:
1. Shrink art to thumbnail size
2. Can you still tell what it is?
3. Does it stand out in a grid?
4. Is text readable (if any)?

**If no**: Simplify. Reduce detail. Increase contrast.

---

## AI Art Platforms

*Note: AI art platforms evolve rapidly. Capabilities change frequently.*

| Platform | Prompt Style | Strengths | Best For |
|----------|-------------|-----------|----------|
| **Midjourney** | Tag-based, comma-separated | Artistic composition, stylized results | Stylized album art, abstract concepts |
| **Leonardo.ai** | Natural language sentences | Photorealism, cinematic quality, fine control | Photorealistic covers, cinematic scenes |
| **DALL-E** | Conversational sentences | Ease of use, text rendering | Beginners, text-heavy designs |
| **Stable Diffusion** | Weighted tags + extensive negatives | Maximum control, local/free, LoRA support | Technical users, batch generation |

### Midjourney
- Discord-based, subscription required
- Prompt format: `/imagine [prompt] --ar 1:1 --v 6`
- Strong artistic interpretation — sometimes adds creative elements beyond the prompt
- `--style raw` for more literal, less stylized results

### Leonardo.ai
- Web-based, free tier available
- **Separate prompt and negative prompt fields** — key differentiator from Midjourney
- Multiple models: **Phoenix** (versatile), **Kino XL** (cinematic), **SDXL** (stable diffusion based)
- Presets (Cinematic, Dynamic, Photography) significantly affect output
- Alchemy mode for higher quality at the cost of generation credits
- More predictable and controllable than Midjourney — natural language prompts iterate faster

### DALL-E
- Integrated in ChatGPT, API available
- Conversational prompts — describe what you want in plain English
- No negative prompt support — state what you want, not what to avoid
- Better text rendering in images than most alternatives

### Stable Diffusion
- Open source, local or cloud deployment (ComfyUI / Automatic1111)
- LoRA models for specific artistic styles
- Most control via CFG scale, samplers, schedulers
- Steeper learning curve but maximum flexibility

### Choosing a Platform

- **Midjourney**: Maximum artistic quality, less control. Good default for stylized art.
- **Leonardo.ai**: Photorealistic/cinematic with precise include/exclude control. Natural language iteration.
- **DALL-E**: Lowest barrier to entry. Best text rendering.
- **Stable Diffusion**: Full control, local generation, model fine-tuning.
