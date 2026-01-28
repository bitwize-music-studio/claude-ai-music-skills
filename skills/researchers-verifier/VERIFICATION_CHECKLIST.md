# Verification Methodology Guide

Systematic approach to fact-checking research before human review.

---

## Verification Philosophy

### Your Role
- **You are**: Quality control, consistency checker, error catcher
- **You are not**: Replacing human judgment, re-doing research

### Core Principle
Trust but verify. Even good researchers make mistakes. Your job is to catch them before they become problems.

---

## The Verification Workflow

### Phase 1: Source Audit
For every cited source:
1. Test the URL (does it load?)
2. Verify archive exists (backup)
3. Confirm content matches citation
4. Note any access issues

### Phase 2: Quote Check
For every direct quote:
1. Open the source document
2. Search for exact quote text
3. Verify page/paragraph reference
4. Check surrounding context

### Phase 3: Fact Cross-Reference
For key facts (dates, numbers, names):
1. Find fact in primary source
2. Cross-check against secondary sources
3. Note any discrepancies
4. Document resolution

### Phase 4: Internal Consistency
Across all research files:
1. Track citations match SOURCES.md
2. SOURCES.md lists all cited sources
3. No orphan or missing sources
4. Dates/facts consistent across files

---

## Cross-Reference Requirements

### Minimum Standards
| Fact Type | Minimum Sources |
|-----------|-----------------|
| Key dates | 2 independent sources |
| Dollar amounts | Primary source (filing, release) |
| Direct quotes | Original source |
| Controversial claims | 2+ reputable sources |
| Background facts | 1 reliable source |

### When Sources Conflict
1. Document both versions
2. Note which source is higher tier
3. Identify possible explanation (timezone, rounding)
4. Recommend which to use, with reasoning

---

## Citation Validation

### Required Citation Elements
- Source name/outlet
- Title or description
- Author (if applicable)
- Date published
- URL (clickable)
- Archive URL (backup)

### What Must Be Cited
- Names, titles, organizations
- Numbers, statistics, amounts
- Dates and timeline events
- Direct quotes
- Legal outcomes
- Technical specifications

### What Doesn't Need Citation
- General knowledge
- Narrative framing
- Emotional interpretation
- Creative elements

---

## Red Flags to Catch

### Critical Issues (Must Fix)
- [ ] Source URL returns 404, no archive
- [ ] Quote not found in cited source
- [ ] Major factual contradiction between sources
- [ ] Key claim with no citation
- [ ] Source tier too low for claim type

### Warnings (Should Fix)
- [ ] Archive missing but URL works
- [ ] Paraphrase in quotation marks
- [ ] Minor date format inconsistency
- [ ] Could cite higher-tier source
- [ ] Orphan source in bibliography

### Informational (Nice to Fix)
- [ ] Only one archive (suggest adding second)
- [ ] Timeline could be more detailed
- [ ] Formatting inconsistency
- [ ] Better source available but not critical

---

## Source Hierarchy Reminder

When evaluating source quality:

**Tier 1** (Court docs, official filings, government releases)
- Use for: Legal outcomes, official facts, statements

**Tier 2** (Investigative journalism, official statements)
- Use for: Verified reporting, attributed quotes

**Tier 3** (News coverage, trade publications)
- Use for: Background, context, reactions

**Tier 4** (Wikipedia, blogs)
- Use for: Starting points only, must verify against higher tiers

---

## Verification Report Template

```markdown
# Verification Report
**Album**: [Name]
**Date**: [Date]
**Sources Reviewed**: [Count]

## Status: [READY / NEEDS FIXES / MAJOR ISSUES]

## Critical Issues
[List with location, problem, required fix]

## Warnings
[List with location, recommendation]

## Verification Summary
- URLs tested: X/Y passing
- Quotes verified: X/Y confirmed
- Dates cross-checked: X/Y consistent
- Citations complete: X/Y have sources
- Archives created: X/Y backed up

## Recommendation
[Ready for human review / Return to researcher with fixes]
```

---

## Common Mistakes to Avoid

### Don't Re-Research
If source missing: Flag it, don't find it yourself
If fact needs verification: Document gap, don't fill it

### Don't Judge Content
Your job: "Is this cited correctly?"
Not your job: "Is this claim reasonable?"

### Don't Skip Steps
Every URL must be tested
Every quote must be checked
Every date must be cross-referenced

### Don't Assume
Same name might be spelled differently
Same event might have different dates
Same amount might be expressed differently

---

## Handoff to Human Review

### Your Deliverable
Clean verification report with:
- Clear status (ready/not ready)
- All issues categorized by severity
- Specific locations for each issue
- Recommended fixes

### Human's Job (Not Yours)
- Content accuracy judgment
- Ethical implications
- Tone appropriateness
- Final approval
