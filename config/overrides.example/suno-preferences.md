# Suno Preferences

Customize Suno prompt generation for your style.

## Genre Mappings

Map your genre names to Suno-specific genre tags:

| My Genre | Suno Genres |
|----------|-------------|
| dark-electronic | dark techno, industrial, ebm, aggressive synths |
| chill-beats | lo-fi hip hop, chillhop, jazzhop, mellow |

## Default Settings

Applied to all prompts unless overridden:

- Model: V5
- Always include in style: atmospheric, polished production
- Default vocal style:

## Vocal Preferences

| Context | Vocal Description |
|---------|-------------------|
| Default male | male baritone, clear delivery |
| Default female | female alto, expressive |
| Aggressive | gritty, intense, powerful |
| Soft | breathy, intimate, gentle |

## Avoid

Never use these in style prompts:

- Genres:
- Descriptors:
- Production terms:

## Instrument Preferences

Preferred instruments by genre:

| Genre | Instruments |
|-------|-------------|
| | |

---

## How This Works

1. `/suno-engineer` loads this file at startup
2. Genre mappings translate your terms to Suno tags
3. Default settings are applied automatically
4. Avoidance rules filter out unwanted terms
