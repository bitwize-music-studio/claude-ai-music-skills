# Suno Documentation Changelog

This file tracks all updates to the Suno reference documentation, including new features, behavior changes, and community discoveries.

---

## 2026-02-04 - V5 Best Practices Research Update

### Features
- **Personas**: Documented creation workflow, best practices, Persona+Cover combinations, December 2025 dominance update
- **Song Editor**: Section-level editing (remake, rewrite, extend, reorder, delete) without full regeneration
- **Bar Count Targeting**: Syntax for targeting specific bar counts per section (e.g., `[VERSE 1 8]`)
- **Creative Sliders**: Weirdness, Style Influence, Audio Influence — documented usage guidance

### Community Tips
- **Prompt fatigue / tag soup**: V5 dilutes attention with 8+ descriptors; sweet spot is 4–7
- **Top-Loaded Palette formula**: `[Mood] + [Energy] + [2 Instruments] + [Vocal Identity]`
- **Token biases**: Suno gravitates toward Neon, Echo, Ghost, Silver, Shadow — model preference, not creative choice
- **Producer's Prompt approach**: Narrative descriptions outperform flat tag lists in V5
- **Sustained notes**: `Loooove`, `Ohhhh` for vocal emphasis; ALL CAPS for shouting
- **Emotion arc mapping**: Different vocal qualities per section for dynamic performance
- **Language isolation**: One language per section for multilingual tracks prevents drift
- **Numbers**: Spell out numbers for reliable pronunciation

### Changes
- **V4.5 comparison note**: V4.5 may produce better results for heavy genres (metal, hardcore)
- **Ownership clarification**: Post-WMG deal — "commercial use rights" but not ownership; model deprecation planned for 2026
- **Catalog protection warning**: Download important generations before licensed models launch
- **V5 Voice Gender selector**: Advanced Options selector documented as most reliable gender control
- **IPA not supported**: Confirmed IPA is not natively supported by Suno
- **V5 context sensitivity**: Improved but phonetic spelling still required for homographs

### Documentation
- Updated v5-best-practices.md: Personas, Song Editor, bar count targeting, Creative Sliders, prompt fatigue, token biases, ownership/licensing, V4.5 comparison
- Updated tips-and-tricks.md: Personas workflow, Covers+Personas, Song Editor, Creative Sliders, catalog protection, expanded WMG context
- Updated voice-tags.md: Voice Gender selector, sustained notes, ALL CAPS, emotion arc mapping, Personas reference
- Updated structure-tags.md: Bar count targeting, performance cues rule, V5 reliability improvements
- Updated pronunciation-guide.md: V5 context sensitivity, IPA note, numbers guidance, multilingual track isolation
- Updated instrumental-tags.md: Producer's Prompt approach, tag soup warning, punctuation solo trick

**Sources**:
- https://suno.com/blog/personas (official - Personas)
- https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/suno-ai-personas-update-dec-2025-what-changed-how-to-use-it
- https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/song-editor-in-suno-v5-workflow
- https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/suno-v5-playbook-complete-guide
- https://www.soundverse.ai/blog/article/how-to-write-effective-prompts-for-suno-music-1128
- https://www.jgbeatslab.com/ai-music-lab-blog/suno-v5-vs-v3-prompting-guide
- https://www.digitalmusicnews.com/2025/12/22/suno-warner-music-deal-changes/
- https://www.prnewswire.com/news-releases/warner-music-group-and-suno-forge-groundbreaking-partnership-302626017.html
- https://hookgenius.app/learn/fix-suno-pronunciation/
- https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/suno-v5-multilingual-english-pronunciation-guide

---

## 2026-01-07 - Suno Studio, WMG Partnership, and Community Tips

### Official Features
- **Suno Studio** (Sept 25, 2025): Generative audio workstation with multitrack editor, MIDI export, Sample to Song feature (Premier plan)
- **Warner Music Group Partnership** (Nov 25, 2025): Download policy changes, licensed music models
- **Persistent Voice & Instrument Memory**: V5 maintains vocal characters and instruments across project generations
- **Granular Controls**: Tempo, key, dynamics, arrangement with optional automation
- **Style Library Bookmark**: Save and reuse style prompts via bookmark icon

### Community Tips
- **Sound effects in brackets**: Use `[laughter]`, `[whisper]`, `[screaming]` mid-line for vocal effects
- **Atmospheric effects technique**: Mention effects in both lyrics AND style box for stronger recognition
- **Accent simulation**: Phonetic lyrics + accent name in style box (e.g., "Russian accent")
- **Non-human character voices**: Overload style prompts with 5-8 adjectives to override human voice training

### Changes
- **Download limits**: Free plan has no downloads, Pro has monthly limits, Premier unlimited via Studio
- **Sample to Song**: Upload audio snippets and expand to full compositions
- **Pitch transpose**: Adjust pitch by semitones in Studio without regenerating

### Documentation
- Updated v5-best-practices.md: Added Suno Studio section, sound effects, atmosphere effects, V5 improvements table
- Updated tips-and-tricks.md: Added download limits, style bookmark feature
- Updated pronunciation-guide.md: Added accent simulation section
- Updated voice-tags.md: Added non-human character voices section
- Updated CHANGELOG.md: This entry

**Sources**:
- https://suno.com/blog (official - Suno Studio, WMG partnership)
- https://help.suno.com/en/articles/8105153 (official - V5 features)
- https://lilys.ai/en/notes/suno-ai-20260102/suno-ai-tricks-master-music (community)

---

## 2025-12-21 - Documentation Consolidation

### Documentation
- Consolidated Suno reference files: reduced from 2384 to 2039 lines
- Removed ~14% redundancy while maintaining clarity
- Updated v5-best-practices.md with latest guidance
- Updated tips-and-tricks.md with operational best practices

**Context**: Initial comprehensive documentation sprint complete

---

## 2025-12-06 - Initial V5 Documentation

### Documentation
- Created comprehensive V5 documentation suite
- Added pronunciation-guide.md (286 lines - homographs, tech terms, phonetic fixes)
- Added genre-list.md (145 lines - 500+ supported genres)
- Added instrumental-tags.md (192 lines - instruments, soloing, genre-specific)
- Added voice-tags.md (132 lines - vocal manipulation, textures, advanced workflows)
- Added structure-tags.md (172 lines - song sections, reliability notes)
- Added workspace-management.md (75 lines - organization guidance)

### V5 Features Documented
- 12-track stem extraction
- 8-minute generation limit
- V5 key improvements vs V4 (10x faster inference)
- Four-part prompt anatomy
- Genre-specific tips (hip-hop, punk, electronic, folk)
- Vocal control strategies
- Mix & Master targets by genre

**Sources**:
- Suno official announcements
- Community testing and feedback
- Direct usage experience

---

## Template for Future Entries

```markdown
## YYYY-MM-DD - [Title]

### New Version (if applicable)
- [Version] [beta|release] available ([availability])

### Features
- [Feature 1]: [Description]
- [Feature 2]: [Description]

### Changes
- [Behavior change 1]: [Description]
- [Behavior change 2]: [Description]

### Community Tips
- [Tip 1]: [Description]
- [Tip 2]: [Description]

### Bug Fixes / Known Issues
- [Issue]: [Description and workaround]

### Documentation
- [File added/updated]

**Sources**:
- [URL 1]
- [URL 2]
```

---

## How to Update This File

This changelog is maintained by:
1. **Manual updates**: When you discover Suno changes
2. **Community contributions**: Via pull requests

**To check for updates**:
- Monitor official Suno blog/changelog
- Track Reddit r/suno and r/aimusic
- Review YouTube tutorials
- Filter for high-signal updates
- Propose CHANGELOG entries for your review

---

## Changelog Conventions

- **Dates**: YYYY-MM-DD format (ISO 8601)
- **Sections**: New Version, Features, Changes, Community Tips, Bug Fixes, Documentation
- **Sources**: Always list URLs at the end
- **Confidence**: Note if community-reported (needs verification)
- **Order**: Most recent first (prepend new entries at top)

---

## Notes

- This is a living document - expect frequent updates as Suno evolves
- For migration guides between versions, see `/reference/suno/version-history/`
- For current best practices, see the appropriate version file (e.g., `v5-best-practices.md`)
