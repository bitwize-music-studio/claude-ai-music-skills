# Model Selection Strategy

This document explains how Claude models are assigned to skills in the AI Music Skills plugin.

## Model Tiers

The plugin uses three Claude models, each optimized for different types of tasks:

### Opus 4.5 (`claude-opus-4-5-20251101`)

**Use for**: Critical creative outputs where quality directly impacts the final music product.

Opus is Claude's most capable model with the strongest creative writing, complex reasoning, and nuanced judgment. The cost is higher, but the investment pays off for tasks where output quality is paramount.

**Characteristics**:
- Highest creative quality and originality
- Best at complex, multi-step reasoning
- Superior nuance in tone, style, and voice
- Most accurate at synthesizing complex information

### Sonnet 4.5 (`claude-sonnet-4-5-20250929`)

**Use for**: Most tasks requiring reasoning, coordination, or moderate creativity.

Sonnet balances capability with efficiency. It handles planning, research coordination, technical guidance, and structured creative tasks well.

**Characteristics**:
- Strong reasoning and analysis
- Good creative output for structured tasks
- Efficient for multi-step workflows
- Reliable for technical and procedural work

### Haiku 4.5 (`claude-haiku-4-5-20251001`)

**Use for**: Fast, simple tasks that follow clear rules or patterns.

Haiku is optimized for speed and efficiency. Perfect for validation, pattern matching, and straightforward operations where creative judgment isn't needed.

**Characteristics**:
- Fastest response time
- Most cost-effective
- Excellent for rule-based tasks
- Good for simple transformations and lookups

---

## Complete Skill Assignments

### Opus 4.5 Skills (4 skills)

| Skill | Description | Rationale |
|-------|-------------|-----------|
| `lyric-writer` | Write/review lyrics with prosody and quality checks | Core creative output - lyrics define the music. Requires nuanced storytelling, rhyme craft, emotional resonance, and prosody mastery. Poor lyrics ruin tracks. |
| `suno-engineer` | Technical Suno V5 prompting, genre selection | Style prompts directly control music generation. Requires deep understanding of genre conventions, vocal descriptions, and Suno's interpretation. |
| `researchers-legal` | Court documents, indictments, plea agreements | Legal documents require precise interpretation and synthesis. Missing nuance in plea agreements or indictments can lead to factual errors that damage credibility. |
| `researchers-verifier` | Quality control, citation validation, fact-checking | Final verification gate before human review. Must catch subtle inconsistencies across sources. Errors here propagate to lyrics and public claims. |

### Sonnet 4.5 Skills (25 skills)

| Skill | Description | Rationale |
|-------|-------------|-----------|
| `album-conceptualizer` | Album concepts, tracklist architecture | Planning requires structure and creativity, but follows established patterns. Sonnet handles the 7-phase workflow effectively. |
| `album-art-director` | Visual concepts for album artwork | Visual direction follows clear principles (composition, color theory). Creative but more structured than lyric writing. |
| `album-ideas` | Track and manage album ideas | Idea management is organizational with light creative input. Sonnet handles brainstorming and tracking well. |
| `configure` | Set up or edit plugin configuration | Technical/procedural task following clear steps. No creative judgment needed. |
| `document-hunter` | Automated document search/download | Primarily technical automation and coordination. Creative judgment not required. |
| `lyric-reviewer` | QC gate before Suno generation | Checklist-based review following established criteria. Catches issues but doesn't require Opus-level creativity. |
| `mastering-engineer` | Audio mastering guidance, loudness optimization | Technical guidance following established standards (-14 LUFS, etc.). Procedural with clear targets. |
| `promo-director` | Generate promo videos for social media | Technical workflow with creative elements. Follows templates and specifications. |
| `release-director` | Album release coordination, QA, distribution | Coordination and checklist management. Important but procedural. |
| `researcher` | Source verification, fact-checking, coordinates specialists | Research coordination and methodology. Delegates complex legal research to Opus-powered researchers-legal. |
| `researchers-biographical` | Personal backgrounds, interviews, motivations | Background research is important but less legally sensitive than court documents. |
| `researchers-financial` | SEC filings, earnings calls, analyst reports | Financial documents have clear structure. Less interpretive complexity than legal documents. |
| `researchers-gov` | DOJ/FBI/SEC press releases, agency statements | Government press releases are more straightforward than raw legal filings. |
| `researchers-historical` | Archives, contemporary accounts, timeline reconstruction | Historical research follows established methods. Less legally sensitive. |
| `researchers-journalism` | Investigative articles, interviews, coverage | Journalism synthesis is important but sources are pre-interpreted by journalists. |
| `researchers-primary-source` | Subject's own words: tweets, blogs, forums | Extracting quotes and context. Clear source material. |
| `researchers-security` | Malware analysis, CVEs, attribution reports | Technical security research with established terminology. |
| `researchers-tech` | Project histories, changelogs, developer interviews | Technical documentation is structured and clear. |
| `resume` | Find an album and resume work | Status checking and coordination. Organizational task. |
| `sheet-music-publisher` | Convert audio to sheet music, create songbooks | Technical workflow with clear specifications. |
| `skill-model-updater` | Update model references in skills | Pattern matching and replacement. Technical maintenance. |
| `test` | Run automated tests to validate plugin | Test execution and reporting. Procedural. |
| `tutorial` | Interactive guided album creation | Guidance and conversation. Follows established workflow phases. |
| `cloud-uploader` | Upload promo videos to cloud storage | Technical operation following clear steps. |

### Haiku 4.5 Skills (9 skills)

| Skill | Description | Rationale |
|-------|-------------|-----------|
| `about` | About bitwize and this plugin | Static information display. No reasoning needed. |
| `clipboard` | Copy track content to system clipboard | Simple extraction and system call. Pattern matching only. |
| `explicit-checker` | Scan lyrics for explicit content | Pattern matching against word lists. Binary yes/no decisions. |
| `help` | Show available skills and quick reference | Static information display. No reasoning needed. |
| `import-art` | Place album art in correct locations | File operations following clear rules. |
| `import-audio` | Move audio files to correct album location | File operations with path resolution. Rule-based. |
| `import-track` | Move track .md files to correct album location | File operations with path resolution. Rule-based. |
| `new-album` | Create album directory structure with templates | Directory creation following templates. Rule-based. |
| `pronunciation-specialist` | Scan lyrics for pronunciation risks | Pattern matching against known risky words. Lookup-based with clear rules. |
| `validate-album` | Validate album structure, file locations | Checklist validation. Binary pass/fail decisions. |

---

## Decision Framework

When assigning a model to a new skill, ask these questions:

### Use Opus 4.5 when:

1. **Output defines the music** - Lyrics, Suno prompts
2. **Legal/factual accuracy is critical** - Court document interpretation
3. **Quality gate for public content** - Final verification before release
4. **Creative nuance matters** - Tone, voice, emotional resonance
5. **Errors are costly to fix** - Regenerating music, retracting claims

### Use Sonnet 4.5 when:

1. **Task requires reasoning but follows patterns** - Album planning, research coordination
2. **Technical guidance with clear targets** - Mastering specs, release procedures
3. **Moderate creativity within structure** - Visual concepts, video direction
4. **Multi-step workflows** - Tutorials, configuration, testing
5. **Coordination across skills** - Researcher orchestrating specialists

### Use Haiku 4.5 when:

1. **Pattern matching only** - Word lists, pronunciation risks
2. **Rule-based operations** - File moves, directory creation
3. **Binary decisions** - Pass/fail validation, yes/no checks
4. **Static information** - Help text, about pages
5. **Simple transformations** - Clipboard operations

---

## Override Guidance

Users on the Claude Code Max subscription have access to all model tiers. In some cases, users may want to override the default model:

### When to consider upgrading to Opus:

- **album-conceptualizer**: For unusually complex or experimental album concepts
- **lyric-reviewer**: When reviewing source-based documentary lyrics with legal sensitivity
- **researchers-journalism**: For investigative pieces requiring synthesis of conflicting accounts

### When Haiku might suffice:

- **resume**: If only checking status (no complex decision-making)
- **configure**: For straightforward configuration updates
- **test**: For running pre-defined test suites

### How to override:

Model assignments are in each skill's SKILL.md frontmatter. To change:

1. Edit `skills/[skill-name]/SKILL.md`
2. Change the `model:` field
3. Test to verify quality meets expectations

**Note**: Overriding to lower-tier models may reduce output quality. Overriding to higher-tier models increases cost but may improve results for edge cases.

---

## Researcher Skill Models

The research skills warrant special explanation since they span different model tiers:

### Why researchers-legal uses Opus:

Legal documents (indictments, plea agreements, sentencing memos) require:
- Precise interpretation of legal language
- Understanding implied vs. explicit claims
- Synthesis of complex procedural history
- Extraction of lyric-worthy quotes without misrepresentation

Errors in legal interpretation can lead to defamatory lyrics or factual inaccuracies that damage credibility.

### Why researchers-verifier uses Opus:

The verifier is the final automated gate before human review. It must:
- Cross-reference facts across multiple sources
- Catch subtle inconsistencies in dates, names, amounts
- Identify when quotes are paraphrased vs. verbatim
- Flag methodology gaps

Missing verification issues means errors reach the human reviewer (or worse, the public).

### Why other researchers use Sonnet:

Government press releases, journalism, financial filings, and technical documentation are:
- More structured and pre-interpreted
- Less legally sensitive
- Following established formats
- Less prone to misinterpretation

The coordinator (`researcher`) also uses Sonnet because it orchestrates rather than interprets.

---

## Cost Considerations

Model costs increase with capability:

| Model | Relative Cost | Use Sparingly |
|-------|---------------|---------------|
| Haiku 4.5 | 1x (baseline) | No - use freely |
| Sonnet 4.5 | ~5x | No - default choice |
| Opus 4.5 | ~15x | Yes - reserve for critical tasks |

The plugin assigns Opus to only 4 of 38 skills (10.5%) to balance quality and cost. These four skills directly impact music output quality.

---

## Updating This Document

When adding new skills:

1. Apply the decision framework above
2. Add the skill to the appropriate tier table with rationale
3. If the choice isn't obvious, document the tradeoff considered

When Claude releases new models:

1. Run `/bitwize-music:skill-model-updater check` to identify outdated references
2. Evaluate if tier assignments should change based on new model capabilities
3. Update this document with new model IDs
