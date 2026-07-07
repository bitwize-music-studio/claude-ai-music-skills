# Suno Documentation Changelog

This file tracks all updates to the Suno reference documentation, including new features, behavior changes, and community discoveries.

---

## 2026-07-07 - V5.5 Mid-Year Research Sweep

Deep multi-source research pass (Suno primary docs + community guides, adversarially fact-checked). Headline: the genuinely new/vetted material since the April V5.5 update is **feature-driven**, not a new prompt grammar. Most third-party "V5.5 prompt-grammar" tips failed verification and were **not adopted** (see Refuted below).

### Features
- **Stem separation overhauled** (June 11, 2026) into three selectable modes: **Auto Split** (the classic 12-category model), **Split from Mix** (pull one instrument/voice out → 2 stems: the target + everything-else), and **Advanced Split** (extract one instrument chosen from ~100; Premier, per-extraction credit cost). The system now *generatively regenerates* each stem rather than frequency-carving the mix, so pulls are cleaner.

### Changes
- **Descriptor-count guidance reframed.** The "4-7 descriptor sweet spot" is a starting heuristic, **not a Suno-official rule** — real style boxes routinely run ~10 focused descriptors. The advisory pre-generation gate now flags only genuine synonym-pile bloat (**>12**, was >7) and no longer mislabels sparse boxes. The failure mode is *duplication*, not count.
- **Negative prompting clarified.** Suno's dedicated **Exclude Styles** field (Custom Mode → Advanced Options, Pro/Premier) is the reliable path; inline `no X` in the main style prompt is a weaker free-tier fallback. Added group-vocal suppression vocabulary (choir, crowd vocals, backing vocals, gang vocals, call-and-response, vocal harmonies, layered vocals). Exclusion is probabilistic — it shifts odds, not a hard filter.
- **Audio Influence × Voices.** When using Voices (voice cloning), keep Audio Influence high (~0.70–0.85) for voice resemblance.
- **Subtle-descriptor claim softened.** "V5.5 honors subtle descriptors more reliably" is engine-reported, not independently verified — reworded from a factual claim to a hedged one.
- **Performance-Cue formatting.** Cues are now written as a short comma-free phrase: `[Outro - chant fading]`, not `[Outro - chant, fading]`. Convention change only — the gate detects cues by the ` - ` separator, so behavior is unchanged.
- **Corrected V5 release date** in the V4→V5 migration guide (was "October 2024"; now "September 2025" to match the repo's own Suno Studio / v5-generation dating).

### Refuted / Not Adopted
Adversarial verification (majority-refute to kill) rejected these widely-circulated claims; do **not** re-add them:
- **"4-7 descriptors is the optimal/required count"** — traces to a single commercial guide; no evidence-based number exists (reframed as a heuristic).
- **Four-layer style template** ending in 2-3 `no` negatives — unsupported.
- **Per-section parameterized tags** like `[Verse: whispered vocals, acoustic only]` — unsupported (this plugin already rejected them as tag soup).
- **Inline `no autotune`/`no reverb` in the style field** as a reliable mechanism — the dedicated Exclude Styles field is the real one.
- **"V5.5 honors subtle production descriptors better than v4.5"** — refuted for lack of evidence (softened, not removed).
- **"V5.5 follows structural metatags more reliably"** — unsupported.

### Documentation
- v5-best-practices.md: Stem Extraction (3 modes), Keep It Simple (descriptor reframe), V5.5 table (subtle-descriptor hedge), Negative Prompting (dedicated field + group vocals), V5 Key Improvements table (stem row).
- suno-engineer/SKILL.md: descriptor-mix guidance, Exclude Styles, workflow steps, quality checklist.
- creative-sliders.md: Audio Influence × Voices; softened 4-7 cross-refs.
- structure-tags.md, voice-tags.md, templates/track.md: comma-free Performance Cue convention.
- pre-generation-check/SKILL.md + handlers/gates.py: descriptor gate >12 threshold; comma-free cue example.
- mix-engineer/SKILL.md: split-mode cross-reference.
- version-history/v5-changes.md: corrected V5 date.

**Sources**:
- https://suno.com/release-notes (official - stem-separation overhaul, Creative Sliders)
- https://suno.com/blog/stem-separation-updates (official - Advanced Split / Split from Mix / Auto Split)
- https://help.suno.com/en/articles/12702337 (official - stem separation)
- https://help.suno.com/en/articles/6141377 (official - Creative Sliders behavior)
- https://help.suno.com/en/articles/11362369 (official - Voices; "Audio Influence slider up fairly high")
- https://suno.com/release-notes/introducing-v5-5-voices-custom-models-and-my-taste (official - V5.5 launch)
- https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/stop-suno-adding-crowd-vocals-choirs-backing-voices (community - group-vocal exclusion)
- https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/how-to-use-suno-s-advanced-sliders-weirdness-style-audio-influence (community - sliders)
- Refuted-claim sources (recorded for traceability): blakecrosley.com/guides/suno, songaifarm.com/blog/suno-prompts-v5-5, hookgenius.app/learn/suno-v5-5-guide, learnstemlab.com/suno-ai-song-control-metatags-guide

---

## 2026-04-12 - V5.5 Research Update

### Features
- **Voices** (Pro/Premier, 4 credits/creation, 18+): voice cloning from 15s–4min of singing with spoken-phrase consent verification; activation requires a broad training-consent opt-in
- **Custom Models** (Pro/Premier, up to 3/account): fine-tune private V5.5 on ≥6 original tracks; 2–5 minute build time
- **My Taste** (all tiers including free): passive preference learning that shapes the style autogenerate feature

### Changes
- **Engine**: improved phrasing nuance, instrument separation, dynamic range, vocal expressiveness — subtle descriptors land more reliably
- **Backward compatibility**: style box (1,000 chars), lyrics box (5,000 chars), metatags, structure tags, sliders, negative prompting all unchanged from V5. No deprecated patterns.
- **Optional prompting adjustments**: drop gender/register descriptors when using Voices; drop generic production language when using Custom Models

### Documentation
- Retitled v5-best-practices.md to cover V5 and V5.5
- Added V5.5 Update summary section at top of v5-best-practices.md
- Added Voices & Custom Models section to v5-best-practices.md
- Added V5.5 personalization summary to tips-and-tricks.md
- Updated suno-engineer skill description to reflect V5/V5.5 scope

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
