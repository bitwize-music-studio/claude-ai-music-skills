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
- All generations remain accessible in your library
- Paid accounts have monthly download quotas
- Premier users maintain unlimited downloads via Suno Studio
- New models trained on licensed WMG catalog (opt-in artists)

**Workaround for Pro users**:
- Prioritize which tracks to download
- Use Suno Studio for unlimited downloads (upgrade to Premier)
- Stream from library without downloading

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
