# Suno Reference Documentation

Reference guides for Suno AI music generation.

## Guides

| Guide | Description |
|-------|-------------|
| [Best Practices](best-practices.md) | Comprehensive prompting guide for the current model family |
| [Model Catalog](models.md) | v6 / v6-wild / v6-mini / Custom Models — tiers, defaults, when to use which |
| [Suno MCP](mcp-api-mapping.md) | Suno's official MCP server — setup, what each action costs, how a track file maps to a generation |
| [Creative Sliders](creative-sliders.md) | Weirdness, Style Influence, Audio Influence — deep dive |
| [Pronunciation Guide](pronunciation-guide.md) | Homographs, tech terms, fixes |
| [Tips & Tricks](tips-and-tricks.md) | Troubleshooting and operational techniques |
| [100 Expert Tips](100-expert-tips.md) | Community craft advice: workflow, Style Box craft, lyrics, vocals, spoken word, noise, mastering, video, rights |
| [Structure Tags](structure-tags.md) | Song section tags reference |
| [Voice Tags](voice-tags.md) | Vocal manipulation and style tags |
| [Instrumental Tags](instrumental-tags.md) | Instruments and instrumental sections |
| [Genre List](genre-list.md) | 500+ music genres |
| [Workspace Management](workspace-management.md) | Manual workspace organization |
| [CHANGELOG](CHANGELOG.md) | Chronological log of Suno updates and doc changes |

## When to Use Which Guide

| Task | Start Here |
|------|-----------|
| Writing a style prompt from scratch | [Best Practices](best-practices.md) |
| Checking lyrics for mispronunciation risks | [Pronunciation Guide](pronunciation-guide.md) |
| Adding section markers (`[Verse]`, `[Chorus]`, etc.) | [Structure Tags](structure-tags.md) |
| Controlling vocal style or vocal effects | [Voice Tags](voice-tags.md) |
| Adding specific instruments | [Instrumental Tags](instrumental-tags.md) |
| Finding the right genre/subgenre tag | [Genre List](genre-list.md) |
| Debugging a failed generation | [Tips & Tricks](tips-and-tricks.md) |
| Picking a model or Generation Settings | [Model Catalog](models.md) |
| Generating, listening or importing without leaving the terminal | [Suno MCP](mcp-api-mapping.md) |

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

Suno's official MCP server (beta since October 2026) takes the parameters below. [mcp-api-mapping.md](mcp-api-mapping.md) has the full mapping from a track file, what each action costs, and setup.

| Parameter | Description | Range |
|-----------|-------------|-------|
| `style` | Style Box | up to 1000 chars |
| `lyrics` | Lyrics Box | up to 5000 chars |
| `negative_style` | Exclude Styles | up to 1000 chars |
| `instrumental` | No vocals | true/false |
| `vocal_gender` | Vocal type | `male` or `female` |
| `model` | Model label | `v6`, `v6-wild`, `v6-mini` |
| `max_mode` | Max Mode | true/false |
| `duration` | Target length, a hard cap | 15-360 seconds |
| `controls.style_influence` | Style Influence | 0.00-1.00 |
| `controls.weirdness` | Weirdness | 0.00-1.00 |

Names such as `prompt`, `vocalGender`, `negativeTags`, `styleWeight` and `weirdnessConstraint`, and model identifiers such as `V6` / `V6_WILD` / `V6_MINI`, come from third-party resellers, not Suno — do not use them.
