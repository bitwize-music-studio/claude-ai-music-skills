# Promotion Preferences Override Template

Optional override file for customizing promo video generation preferences per artist or project.

## Location

`{overrides}/promotion-preferences.md`

Default: `{content_root}/overrides/promotion-preferences.md`

## When to Use

Create this file if you want to:
- Override default visualization styles for specific genres
- Set custom durations for different album types
- Define platform-specific preferences
- Add album-specific visual treatments
- Document your promotion strategy

## Template

```markdown
# Promotion Preferences Override

## Default Settings

Override the plugin's default promotion settings for this artist/project.

### Video Generation
- **Default style:** pulse
  - Override: neon for dark electronic albums
  - Override: bars for high-energy rock
  - Override: line for acoustic/folk albums

- **Clip duration:** 15s
  - Override: 30s for ambient tracks (need longer build)
  - Override: 10s for punk/hardcore (short and punchy)

- **Sampler clips:** 12s each
  - Override: 8s for albums with 12+ tracks (fit in Twitter limit)
  - Override: 15s for albums with <6 tracks (more time per track)

### Platform Strategy

**Primary platforms:** Instagram Reels, Twitter
**Secondary platforms:** TikTok (manual upload later)
**Skip:** Facebook (older demographic, lower engagement)

**Posting schedule:**
- Pre-release (1 week): Album sampler
- Release day: Top 2 singles
- Week 1-2: Additional promos, spaced 2-3 days apart
- Ongoing: Reposts of best performers

### Album-Specific Overrides

**Dark electronic albums (industrial, techno):**
- Style: neon or pulse
- Duration: 15s (short attention span)
- Colors: Let auto-extraction work (usually gets good industrial colors)

**Ambient/chill albums:**
- Style: mirror or mountains
- Duration: 30s (longer build, meditative)
- Sampler: Skip (doesn't work for ambient, use individual promos only)

**Hip-hop albums:**
- Style: pulse or bars
- Duration: 15s (hook-focused)
- Sampler: Include (great for showcasing variety)

**True-story concept albums:**
- Style: pulse (professional, journalistic feel)
- Add text overlay: "Based on true events" (not in base script, manual edit)
- Duration: 30s (give time for story context)

### Branding Preferences

**Artist name display:**
- Position: Bottom center (current default is good)
- Font size: 48pt (current default)
- Override: None needed

**Title display:**
- Position: Bottom center, above artist name
- Font size: 64pt (current default)
- Override: 72pt for single-word titles (more impact)

**Track number display:**
- Show: No (current default)
- Override: Yes for concept albums with narrative arc

**Album name in video:**
- Include: No (not in current script)
- Future: Add for non-single releases

### Color Schemes

**Let auto-extraction work** unless artwork has problematic colors:
- Too dark (extraction fails): Use manual color override
- Too washed out: Increase saturation in artwork before generating
- Wrong mood: Consider different style (some styles don't use artwork colors)

**Manual overrides** (future feature):
- Dark albums: Force white/cyan waveform regardless of artwork
- Bright pop: Use extracted colors (usually works great)
- Monochrome artwork: Force complementary color wheel

### Quality Standards

**Before publishing any promo video:**
- [ ] Waveform reacts clearly to audio
- [ ] Title and artist name readable on phone screen
- [ ] Artwork visible and sharp (not too obscured)
- [ ] Colors match album aesthetic and mood
- [ ] First frame is compelling (auto-play thumbnail)
- [ ] Audio levels consistent across all promos

**Test on phone before batch-generating entire album.**

### Platform-Specific Notes

**Instagram Reels:**
- Prefer pulse, neon, or bars (high energy)
- 15-30s optimal (longer gets lower watch-through rate)
- First 3 seconds critical (loop point)

**Twitter:**
- Prefer pulse or colorwave (professional)
- Sampler performs well (full album preview)
- 15s individual promos for singles

**TikTok:**
- Prefer bars or neon (gen-z aesthetic)
- 15s only (30s+ gets skipped)
- Higher energy styles

### Workflow Notes

**When I say "generate promos"** without specifying style:
- Use default from this document for the album genre
- Generate both individual + sampler unless I specify otherwise
- Use pulse if genre isn't listed here

**When I say "quick test":**
- Generate only one video (first track)
- Use pulse style
- 15s duration
- Check quality before batch-generating rest

**When I say "Instagram-ready":**
- Generate individual promos only (skip sampler)
- Use high-energy style (pulse, neon, bars)
- 15s duration
- Verify on phone before publishing

## Example Override for Specific Artist

```markdown
# Promotion Preferences for "bitwize"

## Style Defaults by Genre

- **Industrial/Dark Electronic:** neon (bright against dark themes)
- **Glitch/Experimental:** circular or dual (abstract matches music)
- **Hip-Hop:** pulse (professional, clean)
- **Ambient:** mirror (meditative, symmetrical)

## Platform Strategy

Focus on Twitter and Instagram only. Skip TikTok (audience mismatch).

Post schedule:
- T-7 days: Sampler + "New album in 7 days"
- T-0 (release): Top single + streaming link
- T+2: Second single
- T+5: Deep cut from album
- T+7: Repost sampler + "Out now"

## Branding

- Keep artist name lowercase: "bitwize" not "Bitwize"
- Prefer dark backgrounds (matches aesthetic)
- Let color extraction work (usually gets good results)

## Quality Gates

Before publishing:
- [ ] Test on phone (desktop looks different)
- [ ] Waveform visible and reactive
- [ ] Text readable at phone size
- [ ] First frame compelling (dark + vivid waveform)
- [ ] Matches album aesthetic
```

---

## Usage by Promo Director Skill

The `/bitwize-music:promo-director` skill checks for this file at:
1. `{overrides}/promotion-preferences.md`

If file exists:
- Read preferences and apply as defaults
- Still ask user for confirmation on critical choices
- Use override values as suggestions/defaults

If file doesn't exist:
- Use plugin built-in defaults
- Ask user for all preferences

## Future Enhancements

Possible future additions to override system:
- Per-track style overrides (different styles per track on album)
- Custom color palettes (force specific hex colors)
- Text overlay templates (captions, quotes, lyrics)
- Branding overlays (logos, watermarks)
- Platform-specific variations (different styles per platform)
- A/B testing configurations (generate multiple versions)

---

## Related Documentation

- `/skills/promo-director/SKILL.md` - Main skill documentation
- `/skills/promo-director/visualization-guide.md` - Style descriptions
- `/reference/promotion/promo-workflow.md` - Complete workflow
- `config/config.example.yaml` - Base config with promotion section
