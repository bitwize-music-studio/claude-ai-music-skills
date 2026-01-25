# Verification Checklists

Detailed checklists for each verification domain.

---

## 1. Source Accessibility

**For each source cited:**
- [ ] URL loads successfully
- [ ] Page contains expected content
- [ ] No 404s, paywalls blocking content
- [ ] Archive link exists and works
- [ ] Archive captures relevant content

**Common issues:**
- Broken links
- Content moved/deleted
- Paywall added since research
- Archive incomplete

**Output format:**
```markdown
### Source Accessibility Check
- ✓ [Source 1]: Accessible, archived
- ⚠ [Source 2]: 404 error - archive.org link works
- ✗ [Source 3]: Paywall blocks content, no archive
```

---

## 2. Quote Verification

**For each quote:**
- [ ] Quote exists in source
- [ ] Quote is verbatim (not paraphrased)
- [ ] Quote has proper attribution
- [ ] Page/paragraph citation provided
- [ ] Context is accurate

**How to check:**
- Open source document
- Search for exact quote text
- Verify page number/paragraph
- Read surrounding context

**Common issues:**
- Paraphrasing presented as quote
- Quote from different source than cited
- Missing context changes meaning
- Typographical errors in transcription

**Output format:**
```markdown
### Quote Verification
- ✓ "Seven minutes flat" - Found in Maersk Statement, p. 3
- ⚠ "Worst attack since 2008" - Paraphrased, not direct quote
- ✗ "Never saw it coming" - Not found in cited source
```

---

## 3. Date Consistency

**Check across all sources:**
- [ ] Event dates match across sources
- [ ] Timeline is chronologically coherent
- [ ] Date formats are consistent
- [ ] No contradictions
- [ ] Gaps in timeline noted

**How to check:**
- Extract all dates mentioned
- Build unified timeline
- Flag discrepancies
- Note which source has which date

**Common issues:**
- Different sources cite different dates
- Timezone confusion (arrest happened "Jan 8" in US, "Jan 9" in UK)
- Confusion between announced vs. occurred
- Fiscal year vs. calendar year

**Output format:**
```markdown
### Date Consistency Check
- ✓ Arrest date: Jan 8, 2024 (FBI, DOJ, WSJ agree)
- ⚠ Indictment date: DOJ says "Jan 10", NYT says "Jan 11" (timezone issue)
- ✗ Settlement date: SEC says "March 15", Bloomberg says "March 17" (conflict)
```

---

## 4. Factual Cross-Verification

**For key facts:**
- [ ] Same fact across multiple sources
- [ ] Numbers/amounts match
- [ ] Names/titles consistent
- [ ] No contradictions
- [ ] Conflicts documented

**What to verify:**
- Dollar amounts (fraud, settlement, fine)
- Victim counts
- Sentence lengths
- Job titles
- Company names
- Technical details

**Common issues:**
- "Approximately" vs. exact figures
- Gross vs. net amounts
- "Up to X years" vs. actual sentence
- Name spelling variations
- Title changes over time

**Output format:**
```markdown
### Fact Cross-Verification
- ✓ Settlement: $150M (SEC, DOJ, WSJ all cite same)
- ⚠ Victim count: DOJ says "over 100", WSJ says "127" (DOJ rounded)
- ✗ Sentence: DOJ release says "10 years", court doc says "120 months" (same, different units)
```

---

## 5. Citation Completeness

**For each claim in research:**
- [ ] Source identified
- [ ] URL provided
- [ ] Date accessed noted
- [ ] Page/section cited (for long docs)
- [ ] Author/publisher named

**What should be cited:**
- Names, titles, organizations
- Numbers, statistics, amounts
- Dates and timelines
- Direct quotes
- Legal outcomes
- Technical specifications

**What doesn't need citation:**
- General knowledge
- Emotional interpretation
- Creative framing

**Output format:**
```markdown
### Citation Completeness
- ✓ "Tank collapsed January 15, 1919" - Cited with court records, newspaper accounts
- ⚠ "2.3 million gallons of molasses" - Cited but secondary source
- ✗ "Fastest industrial flood in history" - Claim needs support
```

---

## 6. Archive Verification

**For each source:**
- [ ] Archive.org link created
- [ ] Archive.today link created (optional)
- [ ] Archive captures full content
- [ ] Archive date is recent

**How to verify:**
- Click archive links
- Confirm content matches live source
- Check capture date

**Common issues:**
- Archive captures paywall, not content
- Archive incomplete (missing images, PDFs)
- Archive from years ago, not current
- No archive created

**Output format:**
```markdown
### Archive Status
- ✓ [Source 1]: archive.org + archive.today, complete capture
- ⚠ [Source 2]: archive.org only, PDF not captured
- ✗ [Source 3]: No archive created
```

---

## 7. Source Hierarchy Compliance

**Check that sources follow hierarchy:**
- [ ] Primary sources used when available
- [ ] Secondary sources cite primary
- [ ] Tier noted in research
- [ ] Conflicts favor higher-tier sources

**Reminder of hierarchy:**
1. Court docs, government releases, official filings
2. Investigative journalism, expert analysis
3. General news, trade publications
4. Wikipedia (background only)

**Common issues:**
- Relying on news when court doc available
- Wikipedia cited for facts (should be starting point only)
- Single secondary source, no primary
- Blog post treated as authoritative

**Output format:**
```markdown
### Source Hierarchy Check
- ✓ Used DOJ press release (Tier 1) for arrest date
- ⚠ Used NYT article (Tier 2) when court doc available (Tier 1)
- ✗ Cited Wikipedia for dollar amount (should verify against SEC filing)
```

---

## 8. Cross-Reference Validation

**Check internal consistency:**
- [ ] Track file cites match RESEARCH.md
- [ ] SOURCES.md lists all cited sources
- [ ] Lyric citations point to documented sources
- [ ] No orphan sources (in bibliography but not cited)
- [ ] No missing sources (cited but not in bibliography)

**Output format:**
```markdown
### Cross-Reference Check
- ✓ All track citations point to sources in SOURCES.md
- ⚠ Track 5 cites "Bloomberg interview" not in SOURCES.md
- ✗ SOURCES.md lists 3 sources not cited anywhere
```

---

## Error Severity Levels

| Level | Definition | Action Required |
|-------|------------|-----------------|
| **Critical** | Will cause Suno problems or legal risk | Must fix before generation |
| **Warning** | Quality issue, impacts song | Should fix, can proceed with caution |
| **Info** | Nitpick, optional improvement | Nice to have, not blocking |

### Critical Examples
- Source URL 404 with no archive
- Quote not found in cited source
- Major factual contradiction
- Missing citation for key claim
- Uncited source in track lyrics

### Warning Examples
- Archive missing but URL works
- Paraphrased quote with quotation marks
- Minor date formatting inconsistency
- Source not in hierarchy order
- Orphan source in bibliography

### Info Examples
- Archive.today link missing (archive.org exists)
- Could cite higher-tier source
- Timeline could be more detailed
- Formatting inconsistency
