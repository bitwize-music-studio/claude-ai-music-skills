# Suno Tips & Tricks

Operational techniques and troubleshooting for Suno. For prompting guidance, see [v5-best-practices.md](v5-best-practices.md).

---

## Lyrics Not Audible

**Common causes:**
- Suno's randomization sometimes produces clips that won't sing
- Overly complex style prompts
- Long musical introductions burying vocals

**Solutions:**

1. **Simplify prompts** - fewer tags, clearer instructions
2. **Use `[Short Instrumental Intro]`** instead of `[Intro]`
3. **Describe vocals explicitly**: "clear and prominent vocals"
4. **Introduce vocals early** with a hook or "(Ahh ahh ahh)"

---

## Extending Songs

### Basic Workflow

1. Click **EXTEND** on the clip
2. Each extension generates ~1 minute, creates 2 clips
3. Pick the best, extend again

### Extend From Timestamp

Use the timestamp window to continue from an earlier point:
- Song ended too soon
- Mistake in text or singing
- Want a style change
- Want instrumental lead-in before lyrics

### Best Practice

Generate multiple versions for each section:
1. Extend verse 1 + chorus 1 (multiple versions)
2. Pick best, extend verse 2 + chorus 2
3. Continue to bridge, final chorus
4. This catches issues early

---

## Lyrics Go Wrong After Extending

When Suno sings random words, repeats sections, or generates gibberish:

1. Go back to an earlier clip and regenerate
2. Use Extend From Time to select an earlier timestamp
3. Create multiple extension versions and pick the best

---

## Replace Section Feature (Pro/Premier)

Edit lyrics or insert instrumental sections within a 10-30 second segment:

```
[Verse]
What a maze

[Instrumental]
[drum break]
```

Useful for:
- Fine-tuning specific lyrics
- Adding guitar solos or breaks
- Fixing small mistakes without regenerating

---

## Layering Styles

Create complex tracks by combining prompts:

```
Prompt 1: "Ethereal pop, dreamy synths, soft vocals"
Prompt 2: "R&B hip-hop fusion, smooth singer, trap beats"
Prompt 3: "Electronic elements, glitch effects, pulsing bassline"
```

---

## Working with Splice Samples

A powerful workflow for better vocals:

1. Upload a vocal sample from Splice
2. Use **Extend** to add different lyrics
3. Or use **Cover** to reimagine in a different style
4. Apply voice tags to manipulate the sound
5. Get stems and delete unwanted vocals

---

## Save Style Prompts

Reuse successful style prompts without copy-pasting:

1. After generation, click **bookmark icon** next to style prompt
2. Name and save the style
3. Access saved styles via **library book icon** (bottom-left of style box)
4. Select from saved library for future compositions

**Use Cases**:
- Maintain consistency across album tracks
- Build a library of genre-specific templates
- Quickly iterate on proven formulas

---

## Download Limits (Nov 2025 Update)

**Effective**: November 25, 2025

As part of the Warner Music Group partnership, download policies changed:

| Plan | Download Limit |
|------|----------------|
| **Free** | No downloads |
| **Pro** | Monthly download limit (varies by plan) |
| **Premier** | Unlimited downloads in Suno Studio |

**Key Points**:
- All generations remain accessible in your library (for now — see Catalog Protection Warning above)
- Paid accounts have monthly download quotas
- Premier users maintain unlimited downloads via Suno Studio
- New models trained on licensed WMG catalog planned for 2026
- Ownership revised: subscribers get "commercial use rights" but are "generally not considered the owner"
- Suno will not take a revenue share from monetization

**Workaround for Pro users**:
- Prioritize which tracks to download within your monthly quota
- Use Suno Studio for unlimited downloads (upgrade to Premier)
- Stream from library without downloading

---

## Personas for Vocal Consistency

Personas (Pro/Premier) save a song's vocal identity for reuse across tracks — the most reliable way to maintain a consistent voice across an album.

### Creating and Using Personas

1. **Generate** a track with the vocal style you want
2. **Save as Persona** from the song's menu
3. **Apply** the Persona when generating new songs — it carries the vocal character
4. Keep style prompts **simple** (1–2 genres) when using Personas; the Persona handles vocal identity

### Combining Personas with Covers

A powerful technique for remixing:

1. Generate a song with a Persona
2. Use **Cover** to transform into a different genre
3. The Persona's vocal identity carries through the genre shift
4. Layer multiple Covers for complex genre-bending results

**Note**: December 2025 update made Personas more dominant in the mix. If results sound overprocessed, simplify your style prompt or lower Style Influence.

---

## Song Editor (V5)

Edit individual sections without regenerating the entire track:

| Action | What It Does |
|--------|-------------|
| **Remake** | Regenerate one section with the same prompt |
| **Rewrite** | Change lyrics/melody for one section |
| **Extend** | Add bars at the end of a section |
| **Reorder** | Rearrange sections in the timeline |
| **Delete** | Remove a section (transitions auto-handled) |

**Tips**:
- Extend 1–2 bars into/out of a chorus for smooth transitions
- Keep total extensions to 2–3 times max per song to avoid quality degradation
- Section rewrite preserves the role/intent while changing content

See [v5-best-practices.md](v5-best-practices.md) for the full Song Editor workflow.

---

## Creative Sliders

Quick reference for V5's generation sliders:

- **Weirdness**: Higher = more experimental. Lower = predictable hooks.
- **Style Influence**: Higher = tighter genre adherence. Lower = looser fusion.
- **Audio Influence**: Controls uploaded audio's weight (only visible with uploads).

Start with defaults, adjust after hearing the first generation.

---

## Catalog Protection Warning

**Current models will be deprecated** when Suno launches licensed models (trained on WMG catalog) in 2026. Download all important generations now — content created on current models may become inaccessible.

**Action items**:
- Download WAV files for all tracks you want to keep
- Premier users: use Suno Studio for unlimited downloads
- Pro users: prioritize downloads within your monthly quota
- Keep local backups of all generated content

---

## Banned Words & Producer Tags

Suno filters words matching artist/producer names:

| Word | Issue | Workaround |
|------|-------|------------|
| **ninety-three** | Producer tag "ninetythree" | Use `'93` or rephrase |

If you hit a filter error, try alternate spellings or rephrase.

---

## Quality Checklist

**Before generating:**
- [ ] Style prompt is specific but not overcomplicated
- [ ] Vocals are described clearly
- [ ] Intro is short (won't bury vocals)
- [ ] Structure tags are reliable (see [structure-tags.md](structure-tags.md))
- [ ] Lyrics are clear and not overly complex

**After generating:**
- [ ] Vocals are audible and clear
- [ ] Lyrics match what was written
- [ ] Song structure makes sense
- [ ] No awkward transitions
- [ ] Ending is clean
