# Suno Documentation Changelog

This file tracks all updates to the Suno reference documentation, including new features, behavior changes, and community discoveries.

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
