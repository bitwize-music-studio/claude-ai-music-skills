# Journalism Source Extraction Guide

Find original reporting, extract quotes, and evaluate credibility.

---

## Finding Original Reporting

### Identify the First Reporter

Most stories are picked up and rewritten. Find who broke it:

1. **Check publication dates**: Earliest wins
2. **Look for "first reported by"**: Later articles often credit
3. **Search for exclusives**: `"[topic]" exclusive OR "first reported"`
4. **Check bylines**: Same reporter often follows stories

### Search Patterns
```
"[topic]" investigation site:propublica.org
"[topic]" "documents show" OR "records reveal"
"[person]" interview OR "told reporters"
"[topic]" site:reuters.com/investigates
```

### Avoid Aggregation
Watch for signs of rewrites:
- "According to reports..."
- "...as first reported by [outlet]"
- No named sources, no documents cited
- Identical quotes appearing across outlets

---

## Source Credibility Evaluation

### Strong Indicators
| Factor | What to Look For |
|--------|-----------------|
| **Named author** | Known beat reporter, track record |
| **Multiple sources** | "Three people familiar" > "a source" |
| **Documents cited** | "According to court filings..." |
| **Subject response** | "Company declined to comment" shows due diligence |
| **Corrections noted** | Transparency about errors |

### Weak Indicators
| Factor | Concern |
|--------|---------|
| **No byline** | Can't evaluate author credibility |
| **Single anonymous source** | Unverifiable |
| **No documents** | Claims without evidence |
| **No response sought** | One-sided |
| **Opinion mixed with fact** | Unclear what's verified |

### Outlet Tiers
**Tier 1**: ProPublica, Reuters Investigates, NYT investigations, WSJ
**Tier 2**: Major newspapers, wire services (AP, Reuters, AFP)
**Tier 3**: Quality magazines, trade publications
**Tier 4**: Blogs, opinion sites (verify against higher tiers)

---

## Extracting Quotes

### Types of Quotes

**Direct quote** (in quotation marks):
> "I never saw a dime," Smith told investigators.

**Paraphrase** (attributed but not exact words):
> Smith claimed he received no money from the scheme.

**Background** (attributed to anonymous source):
> A person familiar with the matter said Smith denied involvement.

### Quote Extraction Process
1. Copy quote exactly, including punctuation
2. Note who said it and to whom
3. Record source URL and date
4. Note context (responding to what question?)
5. Check if quote appears elsewhere (cross-reference)

### Lyric-Worthy Quotes
Look for:
- **Admissions**: "I knew it was wrong..."
- **Defiance**: "I'd do it again..."
- **Regret**: "If I could go back..."
- **Denials**: "I had no idea..."
- **Emotion**: Anything showing character

---

## Archive Tools for Paywalled Content

### Legal Access Methods

**Library databases**:
- Many libraries offer ProQuest, Nexis
- Academic libraries often have remote access

**Archive services**:
- Archive.org Wayback Machine (some captures)
- Archive.today (user-submitted snapshots)
- Google Cache (recent articles)

**Free tiers**:
- NYT: Some free articles monthly
- WSJ: First paragraphs often visible
- Register for free accounts

### Archiving Your Sources
Always create backups:
1. Archive.org: `https://web.archive.org/save/[URL]`
2. Archive.today: `https://archive.today/[URL]`
3. Screenshot critical passages
4. Note access date in citations

---

## Handling Corrections and Updates

### Check for Updates
Before citing any article:
```
"[article title]" correction OR update
"[topic]" after:[original date]
```

### When Stories Conflict
Document both versions:
```markdown
## Discrepancy: Settlement Amount
- **WSJ (Jan 5)**: Reports $150M settlement
- **Bloomberg (Jan 6)**: Reports $175M settlement
- **Resolution**: Using SEC filing ($150M)
```

### Following Developing Stories
Track same author/outlet for follow-ups:
```
author:"[name]" "[topic]"
site:[outlet] "[topic]" after:[date]
```

---

## Attribution in Research

### Proper Citation Format
```markdown
**Source**: [Outlet Name]
**Title**: "[Exact headline]"
**Author**: [Name]
**Date**: [Publication date]
**URL**: [Link]
**Archive**: [Archive.org link]
**Accessed**: [Date you accessed]
```

### In-Text Attribution
- Named source: `According to John Smith, CFO of Acme Corp...`
- Anonymous: `A person familiar with the matter said...`
- Document: `Court records show...`
- Multiple: `Three former employees told Reuters...`
