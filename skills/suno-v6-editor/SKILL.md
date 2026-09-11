---
name: suno-v6-editor
description: Create precise Suno V6 edit, extend, remix, and revision instructions. Use after a generation exists and the user wants to change a section while preserving successful parts.
---

# Suno V6 Editor

Convert vague feedback into a narrow, reversible edit instruction for an existing Suno V6 generation. Prefer editing a promising track over regenerating its entire arrangement when the problem is localized.

## Safety and rights gate

For remix, mashup, sampling, isolation, or audio-reference tasks, first establish that every source is user-owned, licensed, royalty-cleared, or the user's own Suno output. Do not help reconstruct commercial songs, imitate named artists, or use unlicensed recordings.

## Diagnose before editing

Classify the request as one of:

- `replace_section`
- `lyric_or_word_edit`
- `arrangement_edit`
- `instrument_swap`
- `vocal_edit`
- `extend`
- `remix`
- `mashup`
- `sample_and_rebuild`

Then identify:

1. The target section: timestamps, section name, or unambiguous musical description.
2. The single primary change.
3. The elements that must remain unchanged.
4. The expected transition in and out of the edited region.
5. The version identifier and decision after listening.

Do not bundle unrelated changes. If feedback includes multiple problems, produce a prioritized edit queue and start with the highest-impact edit.

## Required output

### Edit card

```yaml
source_version: TRACK-03-v1
operation: replace_section
target: "breakdown, approximately 2:08–2:38"
primary_change: "replace bright lead with warm pads and a plucked motif"
preserve:
  - tempo
  - key feel
  - bassline
  - drum groove
  - overall arrangement timing
transition_goal: "gradual, smooth return to the main groove"
```

### Natural-language edit instruction

Use this pattern:

```text
Keep the entire track unchanged except for [target section]. [Make one primary change]. Preserve [elements to preserve]. Ensure [transition goal]. Keep the result original; do not imitate named artists or recreate existing songs.
```

### Listening test

Provide 3–6 concrete checks for the edited result.

### Revision log entry

```markdown
| Version | Parent | Change | Result | Decision |
|---|---|---|---|---|
| TRACK-03-v2 | TRACK-03-v1 | Replaced breakdown lead | Smoother, less aggressive | Keep for A/B test |
```

## When to regenerate instead

Recommend a new generation rather than an edit when:

- The whole track misses the intended genre or use case.
- Multiple core elements are wrong: tempo, harmony, bass, drums, vocal identity, and arrangement.
- The reference or creative direction has fundamentally changed.
- The user needs several unrelated section changes.

## Extension rules

For `extend`, state precisely what to continue and what to introduce:

```text
Extend from the final groove into a 90-second DJ-friendly outro. Preserve the current BPM, bassline, drum texture, harmonic palette, and restrained deep-house mood. Gradually remove melodic elements, keep the kick and percussion stable, then end with a clean, smooth fade-ready resolution. Keep it fully original.
```

## Example

```text
Keep the entire track unchanged except for the breakdown from approximately 2:08 to 2:38. Replace the bright lead synth with warm airy pads and a soft plucked motif. Preserve the current tempo, bassline, drum groove, minor-key feel, vocal absence, and arrangement timing. Make the return to the main groove gradual and elegant. Keep the result fully original; do not imitate named artists or recreate existing songs.
```
