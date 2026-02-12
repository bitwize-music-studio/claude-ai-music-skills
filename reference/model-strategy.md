# Model Selection Strategy

This document explains the rationale for which Claude model is assigned to each skill in the AI Music Skills plugin.

## Model Tiers Overview

| Model | Strengths | Cost | When to Use |
|-------|-----------|------|-------------|
| **Opus 4.5** | Highest creative quality, nuanced judgment, complex synthesis | ~15x | Output directly impacts music quality; errors are costly |
| **Sonnet 4.5** | Strong reasoning, good creativity, reliable coordination | ~5x | Most tasks; balance of capability and efficiency |
| **Haiku 4.5** | Fastest, pattern matching, rule-following | 1x | Simple operations; binary decisions; no judgment needed |

---

## Opus 4.5 Skills (6 skills)

These skills directly impact music quality or have high error costs.

### lyric-writer
**Why Opus**: Lyrics ARE the music for vocal tracks. This skill requires:
- Nuanced storytelling that connects emotionally
- Sophisticated rhyme schemes without lazy patterns
- Prosody mastery (stressed syllables on strong beats)
- Voice consistency across an album
- Balancing artistic expression with singability

A mediocre lyric ruins the track. There's no "good enough" - lyrics must be excellent. The cost of Opus is trivial compared to regenerating music because lyrics fell flat.

### suno-engineer
**Why Opus**: Style prompts directly control what Suno generates. This skill requires:
- Deep understanding of 64+ genre conventions
- Precise vocabulary for describing vocals, instruments, energy
- Knowledge of what Suno interprets literally vs. figuratively
- Ability to diagnose why a generation failed and adjust

Bad style prompts = bad music. Every regeneration costs time. Getting it right the first time with Opus pays for itself.

### album-conceptualizer
**Why Opus**: The album concept shapes everything downstream - tracklist, themes, arc, genre choices. This skill requires:
- Creative vision for cohesive album identity
- Understanding narrative arc across 8-15 tracks
- Genre knowledge to make informed style decisions
- Balancing artistic ambition with achievability

A weak concept produces a weak album. Spending Opus here prevents wasted effort on a fundamentally flawed foundation.

### lyric-reviewer
**Why Opus**: This is the quality gate before Suno generation. If issues slip through, they become embedded in the music. This skill requires:
- Catching subtle prosody problems
- Identifying lazy rhymes that sound acceptable but aren't
- Verifying source accuracy for documentary tracks
- Judging whether a line "works" or needs revision

Missing a problem here means regenerating after hearing it fail. Opus catches what Sonnet might miss.

### researchers-legal
**Why Opus**: Legal documents (indictments, plea agreements, sentencing memos) require:
- Precise interpretation of legal language
- Understanding what's alleged vs. proven vs. admitted
- Extracting quotes without misrepresentation
- Synthesizing complex procedural history

Errors in legal interpretation can produce defamatory lyrics or factual inaccuracies that damage credibility. The stakes are too high for Sonnet.

### researchers-verifier
**Why Opus**: The final automated gate before human review. This skill must:
- Cross-reference facts across multiple sources
- Catch subtle inconsistencies in dates, names, amounts
- Identify when quotes are paraphrased vs. verbatim
- Flag methodology gaps others missed

If the verifier misses something, errors reach the human reviewer or the public. This is the last line of defense before lyrics go into production.

---

## Sonnet 4.5 Skills (26 skills)

These skills require reasoning and moderate creativity but follow established patterns.

### album-art-director
**Why Sonnet**: Visual direction follows compositional principles (rule of thirds, color theory, visual hierarchy). Creative input needed, but more structured than lyric writing. Clear deliverable: an art prompt for image generation.

### album-ideas
**Why Sonnet**: Brainstorming and organizing album concepts. Requires creativity to suggest ideas but follows a simple status workflow. Not generating final output - just capturing and organizing possibilities.

### cloud-uploader
**Why Sonnet**: Coordinates file uploads to R2/S3 with correct paths and metadata. Requires understanding the folder structure and naming conventions. Technical but not complex enough for Opus, not simple enough for Haiku.

### configure
**Why Sonnet**: Guides users through configuration setup. Must understand what each setting does and suggest appropriate values. Conversational and adaptive, but following a clear structure.

### document-hunter
**Why Sonnet**: Automates searching public archives for documents. Requires judgment about search strategies and evaluating results. Technical automation with decision-making, not pure pattern matching.

### explicit-checker
**Why Sonnet**: Scans lyrics for explicit content. Moved from Haiku because context matters - "ass" in "bass guitar" isn't explicit, "ass" alone might be. Needs judgment about artistic intent and platform standards.

### mastering-engineer
**Why Sonnet**: Guides audio mastering with technical knowledge (-14 LUFS, true peak limits, genre-specific EQ). Follows established standards but needs to explain rationale and troubleshoot issues.

### promo-director
**Why Sonnet**: Coordinates video generation with creative decisions (visualization style, timing, text overlays). Technical workflow with aesthetic judgment. Not creating music, but creating promotional assets.

### promo-reviewer
**Why Sonnet**: Interactive review of social media copy across platforms. Requires judgment about tone, engagement, platform conventions, and character limit optimization. Revisions need creativity to punch up or shorten copy while preserving the user's voice. Not music content, but needs more than pattern matching.

### promo-writer
**Why Sonnet**: Generates platform-specific social media copy from album themes and lyrics. Requires adapting the same core message to each platform's conventions (tone, length, hashtag rules). Creative enough to need more than Haiku, but following established formulas and templates — not generating music content. Output is promotional copy, not the music itself.

### pronunciation-specialist
**Why Sonnet**: Scans for pronunciation risks. Moved from Haiku because edge cases need judgment - is "live" pronounced LIVE or LIV in this context? Names, technical terms, and homographs require understanding, not just pattern matching.

### release-director
**Why Sonnet**: Coordinates release across platforms with different requirements. Must track checklists, verify metadata, and adapt to platform-specific needs. Procedural but requires understanding the "why" behind each step.

### researcher
**Why Sonnet**: Coordinates specialized researchers and synthesizes their findings. Delegates complex legal work to Opus-powered researchers-legal. Orchestration role requiring judgment about which specialist to invoke.

### researchers-biographical
**Why Sonnet**: Researches personal backgrounds, interviews, motivations. Important for humanizing subjects but less legally sensitive than court documents. Sources are generally clearer than legal filings.

### researchers-financial
**Why Sonnet**: Navigates SEC filings, earnings calls, financial statements. Structured documents with established formats. Less interpretive complexity than legal proceedings.

### researchers-gov
**Why Sonnet**: Finds DOJ/FBI/SEC press releases and agency statements. Government communications are more straightforward than raw legal filings - they're already written for public consumption.

### researchers-historical
**Why Sonnet**: Archives, contemporary accounts, timeline reconstruction. Follows established historical research methods. Important for accuracy but less legally sensitive than court documents.

### researchers-journalism
**Why Sonnet**: Investigative articles, interviews, news coverage. Sources are pre-interpreted by professional journalists. Requires evaluating credibility but not legal interpretation.

### researchers-primary-source
**Why Sonnet**: Finds subject's own words (tweets, blogs, forums). Extracting and contextualizing quotes from clear source material. Less interpretation needed than legal documents.

### researchers-security
**Why Sonnet**: CVE databases, malware analysis, attribution reports. Technical security research with established terminology and formats. Structured information extraction.

### researchers-tech
**Why Sonnet**: Project histories, changelogs, developer interviews. Technical documentation is structured and clear. Following breadcrumbs through GitHub and mailing lists.

### resume
**Why Sonnet**: Finds albums and reports status. Requires understanding workflow state and suggesting next steps. Conversational and adaptive, but following established patterns.

### sheet-music-publisher
**Why Sonnet**: Coordinates transcription workflow with tool-specific guidance. Technical process requiring troubleshooting knowledge. Not creative output, but needs to explain and adapt.

### session-start
**Why Sonnet**: Runs the 8-step session startup procedure. Requires reading config, loading overrides, interpreting state cache, and producing contextual tips. Judgment needed to identify relevant status and recommendations.

### tutorial
**Why Sonnet**: Interactive guided album creation. Must be conversational, adaptive, and educational. Follows the 7-phase workflow but needs to meet users where they are.

### verify-sources
**Why Sonnet**: Guides the human source verification gate. Presents sources for review, captures timestamps, updates track files. Conversational workflow requiring judgment about completeness and source quality.

---

## Haiku 4.5 Skills (15 skills)

These skills perform simple, rule-based operations with no creative judgment.

### about
**Why Haiku**: Displays static information about the plugin. No reasoning needed - just retrieves and formats predetermined content.

### clipboard
**Why Haiku**: Copies track content to system clipboard. Pure extraction: find the section, copy the text, call the system clipboard command. No judgment required.

### help
**Why Haiku**: Displays available skills and quick reference. Static information retrieval and formatting. No decision-making beyond basic lookup.

### import-art
**Why Haiku**: Places album art in correct locations. Rule-based file operation: read config, determine paths, copy files. Binary success/failure.

### import-audio
**Why Haiku**: Moves audio files to correct album location. Path resolution following strict rules: `{audio_root}/{artist}/{album}/`. No judgment - just correct path construction.

### import-track
**Why Haiku**: Moves track markdown files to correct location. Same as import-audio - rule-based path resolution and file operations.

### new-album
**Why Haiku**: Creates album directory structure from templates. Follows a template exactly: create folders, copy files, replace placeholders. No creative decisions.

### setup
**Why Haiku**: Detects Python environment and checks for installed dependencies. Rule-based checks: run commands, parse output, show appropriate installation instructions. No judgment - just environment detection and templated guidance.

### skill-model-updater
**Why Haiku**: Updates model references when new Claude versions release. Pattern matching and replacement: find old model ID, replace with new. No judgment about which model to use (that's documented separately).

### test
**Why Haiku**: Runs predefined test suites. Executes checks and reports pass/fail. Tests are already defined - this just runs them and formats output.

### album-dashboard
**Why Haiku**: Generates a progress dashboard with completion percentages per phase. Counting tracks, checking fields, formatting output. Arithmetic and pattern matching, no judgment.

### next-step
**Why Haiku**: Analyzes album state and recommends the next action. Follows a decision tree: check status fields, match to the workflow sequence, output the recommendation. Rule-based routing.

### pre-generation-check
**Why Haiku**: Validates 6 pre-generation gates (sources, lyrics, pronunciation, explicit, style prompt, artist names). Each gate is a binary check — field present or not. No interpretation needed.

### rename
**Why Haiku**: Renames albums or tracks with path updates. Rule-based find-and-replace across file names, directory names, and internal references. No judgment - just string substitution and file operations.

### validate-album
**Why Haiku**: Validates album structure against expected format. Checklist validation with binary pass/fail for each item. No interpretation - either the file exists or it doesn't.

---

## Decision Framework

When assigning a model to a new skill:

```
Is the output the actual music content (lyrics, prompts)?
  YES → Opus (errors directly impact music quality)
  NO ↓

Is there significant legal/factual risk if errors occur?
  YES → Opus (errors can be defamatory or damage credibility)
  NO ↓

Does the task require creative judgment or synthesis?
  YES → Sonnet (reasoning + creativity)
  NO ↓

Is it purely pattern matching, file operations, or static info?
  YES → Haiku (fast, cheap, sufficient)
  NO → Sonnet (default for uncertain cases)
```

---

## Distribution Summary

| Tier | Count | Percentage | Purpose |
|------|-------|------------|---------|
| Opus 4.5 | 6 | 12.8% | Music-defining output, high error cost |
| Sonnet 4.5 | 26 | 55.3% | Reasoning, coordination, moderate creativity |
| Haiku 4.5 | 15 | 31.9% | Rule-based operations, no judgment |

The plugin reserves Opus for skills where quality directly impacts the music or where errors have significant consequences. Most work happens at Sonnet tier. Haiku handles mechanical operations where speed matters more than nuance.
