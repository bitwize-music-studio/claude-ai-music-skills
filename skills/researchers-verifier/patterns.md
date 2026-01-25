# Common Verification Patterns

Patterns and issues encountered during verification.

---

## Pattern 1: Broken Citation Chain

**Problem**: Track lyrics cite "DOJ press release (March 2024)" but no such source in SOURCES.md

**How to catch**:
1. Extract all citations from track files
2. Cross-reference against SOURCES.md
3. Flag orphans

**Fix**:
- Research agent finds missing source
- OR citation corrected to existing source

---

## Pattern 2: Date Conflicts

**Problem**: Source A says "January 8", Source B says "January 9" for same event

**How to catch**:
1. Build timeline from all sources
2. Flag same event with different dates
3. Note timezone or announcement vs. occurrence

**Fix**:
- Determine which is correct (timezone, etc.)
- Document discrepancy in research
- Choose one for lyrics with note

---

## Pattern 3: Unsupported Claims

**Problem**: Research states "largest fine in history" with no citation

**How to catch**:
1. Scan research for superlatives
2. Check for citation
3. Flag if uncited

**Fix**:
- Find source supporting claim
- OR remove/soften claim ("one of the largest")

---

## Pattern 4: Inaccessible Sources

**Problem**: URL returns 404, no archive exists

**How to catch**:
1. Test every URL
2. Check for archive links
3. Flag if both fail

**Fix**:
- Find alternate source with same info
- OR create archive if content elsewhere
- OR remove claim if unsourceable

---

## Pattern 5: Paraphrased "Quotes"

**Problem**: Quotation marks around text that's not verbatim from source

**How to catch**:
1. Open source document
2. Search for exact quote text
3. Flag if not found or paraphrased

**Fix**:
- Find actual quote, OR
- Remove quotation marks and attribute as paraphrase

---

## Common Mistakes to Avoid

### 1. Don't Re-Research
Your job: Verify existing research
NOT: Find new sources or re-do research

**If you find**: Missing source for claim
**You do**: Flag it for researcher to find
**You DON'T**: Go find the source yourself

### 2. Don't Judge Content
Your job: Check technical accuracy
NOT: Judge if claim is reasonable

**If you find**: "Largest cyberattack in history" with citation
**You do**: Verify citation exists and supports claim
**You DON'T**: Judge if claim is hyperbolic

### 3. Don't Skip Archives
Archives are critical. Always check:
- Archive exists
- Archive works
- Archive captured content (not just paywall)

### 4. Don't Assume Consistency
Check EVERYTHING, even if it seems obvious:
- Same person's name spelled differently
- Date written different formats
- Amounts in millions vs. billions
