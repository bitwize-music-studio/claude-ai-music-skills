# Suno Reference Documentation

Reference guides for Suno AI music generation.

## Guides

| Guide | Description |
|-------|-------------|
| [V5 Best Practices](v5-best-practices.md) | Comprehensive prompting guide for V5 |
| [Pronunciation Guide](pronunciation-guide.md) | Homographs, tech terms, fixes |
| [Tips & Tricks](tips-and-tricks.md) | Troubleshooting and operational techniques |
| [Structure Tags](structure-tags.md) | Song section tags reference |
| [Voice Tags](voice-tags.md) | Vocal manipulation and style tags |
| [Instrumental Tags](instrumental-tags.md) | Instruments and instrumental sections |
| [Genre List](genre-list.md) | 500+ music genres |
| [Workspace Management](workspace-management.md) | Manual workspace organization |
| [CHANGELOG](CHANGELOG.md) | Chronological log of Suno updates and doc changes |
| [Version History](version-history/) | Migration guides between Suno versions |

## When to Use Which Guide

| Task | Start Here |
|------|-----------|
| Writing a style prompt from scratch | [V5 Best Practices](v5-best-practices.md) |
| Checking lyrics for mispronunciation risks | [Pronunciation Guide](pronunciation-guide.md) |
| Adding section markers (`[Verse]`, `[Chorus]`, etc.) | [Structure Tags](structure-tags.md) |
| Controlling vocal style or vocal effects | [Voice Tags](voice-tags.md) |
| Adding specific instruments | [Instrumental Tags](instrumental-tags.md) |
| Finding the right genre/subgenre tag | [Genre List](genre-list.md) |
| Debugging a failed generation | [Tips & Tricks](tips-and-tricks.md) |

> **Related skill**: `/bitwize-music:suno-engineer` provides interactive guidance using these references.

## Suno Tag/Metatag Terminology

"Metatag" is often used loosely for all bracketed Suno keywords. This plugin distinguishes four categories, each with its own home doc:

| Category | Example | Lives in |
|----------|---------|----------|
| Structure tags | `[Verse]`, `[Chorus]`, `[Post-Chorus]` | [structure-tags.md](structure-tags.md) |
| Delivery/mood bracket tags | `[Whispered]`, `[Aggressive]` | [structure-tags.md](structure-tags.md) — "Custom Mood/Style Tags" |
| Style Box descriptors (prose, not brackets) | `gravelly, belting, Southern rock vocal` | [voice-tags.md](voice-tags.md), [instrumental-tags.md](instrumental-tags.md) |
| Inline lyrical metatags | `[Verse 1: Raspy older female vocal, husky contralto]` | [tips-and-tricks.md](tips-and-tricks.md#vocal-sounds-too-young-despite-maturedeep-descriptors) — escalation technique, not default |

Structure tags are mandatory in every section; the other three are optional accents — see each doc's usage guidance to avoid "tag soup"/prompt fatigue.

## Quick Links

- [Suno Website](https://suno.com)
- [How To Prompt Suno](https://howtopromptsuno.com)

## API Parameters

| Parameter | Description | Range |
|-----------|-------------|-------|
| `style` | Musical style/genre | 200-1000 chars |
| `prompt` | Lyrics in custom mode | 3000-5000 chars |
| `instrumental` | No vocals | true/false |
| `vocalGender` | Vocal type | "m" or "f" |
| `negativeTags` | Styles to avoid | Text |
| `styleWeight` | Style adherence | 0.00-1.00 |
| `weirdnessConstraint` | Creative deviation | 0.00-1.00 |
