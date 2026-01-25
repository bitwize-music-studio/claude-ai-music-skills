# Suno V4 → V5 Migration Guide

**V5 Release Date**: October 2024
**Availability**: All plans
**Status**: Stable

---

## Summary of Changes

Suno V5 represents a major upgrade over V4 with significantly faster generation, improved audio quality, and expanded capabilities.

### Major Improvements
- **10x faster inference**: Generations complete much quicker
- **12-track stem extraction**: Up from 10 tracks in V4
- **8-minute generation limit**: Up from 4 minutes in V4
- **Improved prompt interpretation**: Better understanding of natural language descriptions
- **Enhanced vocal quality**: More consistent and natural-sounding vocals
- **Better genre accuracy**: More faithful reproduction of specified genres

### Key Behavior Changes
- **Prompt structure matters more**: V5 is more literal and precise
- **Vocals-first ordering**: Best results when vocal description comes first in style prompt
- **Section tags more reliable**: Better handling of `[Verse]`, `[Chorus]`, etc.
- **Negative prompting improved**: V5 respects "no [element]" prompts better

---

## Breaking Changes

**None - V4 prompts work in V5**

However, V4 prompts may not take full advantage of V5's capabilities. Consider rewriting for optimal results.

---

## New Features

### Extended Generation Length

**V4**: Maximum 4 minutes
**V5**: Maximum 8 minutes

```
No changes needed - V5 automatically supports longer generations
```

### Enhanced Stem Extraction

**V4**: 10 tracks
**V5**: 12 tracks

Available stems include:
- Vocals, Lead Vocals, Backing Vocals
- Drums, Kick, Snare, Hi-hats
- Bass, Guitar, Piano, Synth, Other

To use:
1. Generate track in V5
2. Click **More Actions (...)**
3. Select **Get Stems** > **Original**
4. Download 12 separate track files

### Improved Prompt Understanding

**V5 is more literal** - say exactly what you want:

**V4 style** (vague):
```
"Energetic song with good vocals"
```

**V5 style** (specific):
```
"Male vocalist, energetic delivery, clear pronunciation.
Upbeat indie rock, driving drums, jangly guitars.
Clean production, bright mix."
```

### Better Negative Prompting

**V4**: Negative prompts sometimes ignored
**V5**: More consistent exclusion of unwanted elements

**Example**:
```
Style: "Acoustic folk, warm, intimate, no drums, no electric instruments"
```

V5 better respects the "no drums, no electric instruments" directive.

---

## Changed Behaviors

### 1. Prompt Structure

**V4**: Flexible ordering, somewhat forgiving
**V5**: Structured approach yields better results

**Recommended V5 structure**:
```
[Vocal description first]. [Genre/instrumentation]. [Production notes]
```

**Example**:
```
V4: "Rock song with male vocals, energetic, distorted guitars"
V5: "Male vocalist, powerful, gritty. Hard rock, distorted guitars, pounding drums. Raw production."
```

### 2. Artist Name References

**V4**: Artist names sometimes worked
**V5**: Artist names filtered more aggressively

**Migration**:
- **Don't use**: "Sounds like The Beatles"
- **Do use**: "British Invasion pop, jangly guitars, close harmonies, vintage production"

### 3. Section Tag Reliability

**V4**: Section tags (`[Verse]`, `[Chorus]`) occasionally ignored
**V5**: Better adherence to section tags

**Best practice in V5**:
- Use section tags liberally
- Keep intros short (V5 tends to extend them)
- `[End]` tag now more reliable for clean endings

### 4. Extending Tracks

**V4**: Extending could change style significantly
**V5**: Better style consistency when extending

**Still recommended**: Review extended sections carefully for coherence

---

## Deprecated Features

### Artist Name Prompting (Gradually Deprecated)

**Status**: Still partially works in V5 but discouraged

**Old approach** (V4):
```
"Sounds like Nine Inch Nails"
```

**New approach** (V5):
```
"Dark industrial rock, aggressive synths, distorted vocals, electronic percussion"
```

**Why**: Describing style directly gives V5 clearer instructions and avoids potential copyright issues.

---

## Migration Checklist

### For Existing Tracks

- [ ] **Test V4 prompts in V5**: Most work, but may not be optimal
- [ ] **Review vocal placement**: Put vocal description first for best results
- [ ] **Rewrite artist references**: Use descriptive style instead
- [ ] **Adjust negative prompts**: V5 handles these better - may need fewer items
- [ ] **Update stem extraction workflows**: Account for 12 tracks instead of 10

### For New Tracks

- [ ] **Use V5 prompt structure**: Vocals > Genre/Instruments > Production
- [ ] **Be literal and specific**: V5 takes you at your word
- [ ] **Leverage negative prompting**: More effective in V5
- [ ] **Test longer generations**: Try 6-8 minute tracks if appropriate
- [ ] **Use section tags consistently**: V5 respects them better

### For Saved Personas

- [ ] **Review saved prompts**: Update for V5 structure
- [ ] **Remove artist name references**: Replace with descriptive language
- [ ] **Add vocal details**: V5 benefits from more vocal specificity
- [ ] **Test each persona**: Verify it works as expected in V5

---

## Prompt Conversion Examples

### Example 1: Rock Track

**V4 prompt**:
```
Style: "Rock song, male singer, guitar solo"
```

**V5 optimized**:
```
Style: "Male vocalist, powerful, clear. Alternative rock, distorted guitars, steady drums. [Guitar Solo] at 2:30. Modern production, punchy mix."
```

### Example 2: Electronic Track

**V4 prompt**:
```
Style: "EDM, like deadmau5, progressive house"
```

**V5 optimized**:
```
Style: "No vocals. Progressive house, layered synths, driving bassline, crisp percussion. Gradual build-ups, melodic breakdowns. Clean production, wide stereo."
```

### Example 3: Folk Track

**V4 prompt**:
```
Style: "Acoustic folk with female vocals, storytelling"
```

**V5 optimized**:
```
Style: "Female vocalist, warm, intimate, clear storytelling. Acoustic folk, fingerpicked guitar, subtle harmonies. Organic production, close-miked feel, no drums."
```

---

## Performance Comparison

### Generation Speed

| Metric | V4 | V5 | Improvement |
|--------|----|----|-------------|
| 2-minute track | ~120s | ~12s | 10x faster |
| 4-minute track | ~240s | ~24s | 10x faster |
| 8-minute track | N/A | ~48s | New capability |

### Audio Quality (Subjective)

| Aspect | V4 | V5 | Notes |
|--------|----|----|-------|
| Vocal clarity | Good | Excellent | More consistent pronunciation |
| Genre accuracy | Good | Excellent | Better style adherence |
| Stereo imaging | Good | Excellent | Wider, more detailed |
| Artifacts | Occasional | Rare | Fewer glitches |
| Consistency | Good | Excellent | Less variation between takes |

---

## Common Migration Issues

### Issue 1: V4 Prompts Sound Different in V5

**Cause**: V5 interprets prompts more literally

**Solution**: Rewrite prompts to be more specific and structured

### Issue 2: Vocals Not Prominent Enough

**Cause**: V5 requires explicit vocal direction

**Solution**: Put vocal description first, add details (projection, clarity, style)

### Issue 3: Unwanted Elements Still Present

**Cause**: Negative prompting may need adjustment

**Solution**: Be specific: "no drums" rather than "no percussion" if you want some percussion but no drums

### Issue 4: Intros Too Long

**Cause**: V5 tends to extend intros

**Solution**: Use `[Intro]` tag and keep intro lyrics/content brief, or start directly with `[Verse]`

### Issue 5: Style Not Matching Expectation

**Cause**: Artist name references don't work well in V5

**Solution**: Describe the sonic qualities directly instead of referencing artists

---

## Resources

### V5-Specific Documentation
- [V5 Best Practices](../v5-best-practices.md) - Complete V5 prompting guide
- [Pronunciation Guide](../pronunciation-guide.md) - Handle tricky words in V5
- [Tips and Tricks](../tips-and-tricks.md) - Operational guidance for V5

### Community Resources
- Reddit r/suno: Community discoveries and troubleshooting
- YouTube: Search "Suno V5 tips" for video tutorials
- Discord: discord.gg/suno for real-time help

---

## Quick Reference Card

```
V5 PROMPT FORMULA
─────────────────
[Vocal description]. [Genre/instrumentation]. [Production notes]

VOCAL FIRST
─────────────
Male/Female/No vocals
Voice quality (warm, gritty, smooth, powerful)
Delivery (energetic, intimate, aggressive, laid-back)

GENRE & INSTRUMENTS
───────────────────
Primary genre + descriptors
Key instruments (be specific)
Tempo/feel (optional)

PRODUCTION
──────────
Production style (raw, polished, vintage, modern)
Mix characteristics (bright, warm, punchy, spacious)
What to avoid (no [element])

SECTION TAGS
────────────
[Intro] [Verse] [Pre-Chorus] [Chorus]
[Bridge] [Outro] [Instrumental] [End]

LENGTH
──────
Up to 8 minutes (double V4's 4-minute limit)

STEMS
─────
12 tracks available (up from 10 in V4)
```

---

## Notes

- This guide reflects community knowledge and testing
- V5 continues to evolve - check [CHANGELOG.md](../CHANGELOG.md) for updates
- For new V6+ features, see corresponding version-history files
- When in doubt, test and iterate - V5 is very consistent with good prompts

---

**Last Updated**: 2026-01-07
**Next Version**: See [CHANGELOG.md](../CHANGELOG.md) for V6 announcements
