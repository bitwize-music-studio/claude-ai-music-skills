# Skills Reference

All 52 skills, invoked with `/bitwize-music:<skill-name>`. Claude also uses them automatically when relevant.

---

## Core Production

| Skill | Description |
|-------|-------------|
| `lyric-writer` | Write/review lyrics with prosody and rhyme checks |
| `album-conceptualizer` | Album concepts, tracklist architecture, 7 planning phases |
| `suno-engineer` | Technical Suno V5 prompting and generation settings |
| `pronunciation-specialist` | Prevent Suno mispronunciations with phonetic spelling |
| `album-art-director` | Album artwork concepts and multi-platform AI art prompts |
| `mix-engineer` | Per-stem audio polish (noise reduction, EQ, compression) |
| `mastering-engineer` | Audio mastering for streaming platforms (-14 LUFS) |

## Research System

The research system is coordinated by a lead `/researcher` skill that dispatches to 10 domain-specific sub-researchers. Each specialization handles source gathering, citation, and cross-verification for its domain.

| Skill | Domain |
|-------|--------|
| `researcher` | Lead coordinator — dispatches and synthesizes across specializations |
| `researchers-legal` | Court documents, indictments, plea agreements, sentencing |
| `researchers-gov` | DOJ/FBI/SEC press releases, agency statements |
| `researchers-journalism` | Investigative articles, interviews, news coverage |
| `researchers-tech` | Project histories, changelogs, developer interviews |
| `researchers-security` | Malware analysis, CVEs, attribution reports |
| `researchers-financial` | SEC filings, earnings calls, market data |
| `researchers-historical` | Archives, contemporary accounts, timelines |
| `researchers-biographical` | Personal backgrounds, motivations |
| `researchers-primary-source` | Subject's own words — tweets, blogs, forums |
| `researchers-verifier` | Quality control, citation validation, fact-checking |
| `document-hunter` | Automated browser-based retrieval from public archives |

## Quality Control

| Skill | Description |
|-------|-------------|
| `lyric-reviewer` | QC gate before Suno — 9-point checklist |
| `explicit-checker` | Scan lyrics for explicit content, verify flags |
| `plagiarism-checker` | Web search + LLM check for unintentional borrowing |
| `voice-checker` | Detect AI-sounding patterns in lyrics |
| `verify-sources` | Human source verification gate with timestamps |
| `validate-album` | Validate album structure, file locations, content integrity |
| `pre-generation-check` | Validate all gates before sending to Suno |

## Release & Distribution

| Skill | Description |
|-------|-------------|
| `promo-director` | Generate 15-second vertical promo videos |
| `promo-writer` | Platform-specific social media copy |
| `promo-reviewer` | Review and polish promo copy before release |
| `cloud-uploader` | Upload promo content to Cloudflare R2 or AWS S3 |
| `sheet-music-publisher` | Convert audio to sheet music, create printable songbooks |
| `release-director` | QA, distribution prep, platform uploads |

## Album Management

| Skill | Description |
|-------|-------------|
| `new-album` | Create album directory structure with templates |
| `resume` | Find album, show status, recommend next steps |
| `album-dashboard` | Visual progress overview with percentages |
| `next-step` | Analyze state, recommend optimal next action |
| `album-ideas` | Track and manage album idea backlog |
| `rename` | Rename album or track, update all paths |
| `import-audio` | Move audio files to correct album location |
| `import-track` | Move track markdown files to correct location |
| `import-art` | Place album art in audio and content directories |
| `clipboard` | Copy track content to system clipboard |

## Setup & Maintenance

| Skill | Description |
|-------|-------------|
| `setup` | Detect environment, install dependencies |
| `configure` | Interactive config file setup |
| `tutorial` | Guided album creation walkthrough |
| `session-start` | Verify setup, load state, report status |
| `test` | Run automated tests (14 categories) |
| `skill-model-updater` | Update Claude model references across skills |
| `genre-creator` | Create new genre documentation with mastering presets |
| `help` | Available skills, workflows, quick reference |
| `about` | Plugin version and information |
