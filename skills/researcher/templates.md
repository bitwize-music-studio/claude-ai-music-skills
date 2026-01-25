# Research Templates & Examples

Reference templates for documentation, verification, and citations.

---

## Verification Matrix Format

```
FACT: [Statement being verified]
SOURCE 1: [Citation] - PRIMARY/SECONDARY
SOURCE 2: [Citation] - PRIMARY/SECONDARY
SOURCE 3: [Citation] - PRIMARY/SECONDARY
VERIFIED: ✅/⚠️/❌ [X sources, Y primary, alignment status]
```

**Example**:
```
FACT: USIA found liable for the Great Molasses Flood (1925)
SOURCE 1: Court verdict by Hugh Ogden (1925) - PRIMARY
SOURCE 2: Boston Globe coverage (Jan 16, 1919) - PRIMARY
SOURCE 3: Stephen Puleo "Dark Tide" (2003) - SECONDARY
SOURCE 4: Engineering investigation reports - PRIMARY
VERIFIED: ✅ 4 sources, 3 primary, dates align
```

---

## Citation Formats

### Court Documents
```
[Case Name]
[Court], [Jurisdiction]
[Document Type], Filed [Date]
Pages [X-Y]
Retrieved: [date]
Archive: [location]
```

### Historical Records
```
[Publication] - [Topic]
[Date Range]
[Description]
Retrieved: [date]
Archive: [location]
```

### Page-Level Citations
- Not just "the indictment says" but "Indictment p.47 ¶112"
- Not just "trial testimony" but "Transcript Day 23, p.1847-1849, Lines 12-28"

---

## RESEARCH.md Format

Every section must include:
1. **Fact Statement**
2. **Primary Source Citation** (full academic format)
3. **Verification Matrix** (3+ sources)
4. **Page Numbers** for key quotes
5. **Context** (what document section is about)
6. **Confidence Level** (High/Medium/Low)
7. **Discrepancies** (if any)
8. **Unresolved Questions**

### Example Entry

```markdown
## Track 01: The Tank - Fact Sheet

### FACT 1: Tank collapsed January 15, 1919 at approximately 12:40 PM

**Primary Source 1: Boston Globe**
- Source: Boston Globe, January 16, 1919 (front page)
- Direct quote: "Giant tank burst shortly after noon"
- Context: Contemporary newspaper account, day after disaster
- Confidence: HIGH (primary source)

**Primary Source 2: Court records**
- Dorr et al. v. USIA trial documents
- Multiple witness testimonies establish time
- Hugh Ogden's report references "midday"

**Primary Source 3: Stephen Puleo "Dark Tide"**
- Pages 1-5: "12:40 in the afternoon"
- Cites primary sources including survivor interviews
- Confidence: HIGH (extensively sourced secondary)

**VERIFICATION STATUS: ✅ TRIPLE-CONFIRMED**
- All 3 sources align: January 15, 1919, midday
- No discrepancies found
- Confidence: VERY HIGH
```

---

## SOURCES.md Format

```markdown
## Legal Sources

### 1. [Case Name] - Court Records

**Full Citation**:
[Full case citation]

**Document**: [Document type]
**Filed**: [Date]
**Pages**: [Page count]
**Outcome**: [Result]

**Retrieved**: [date]
**Archive**: [Location]

**Key Sections Used**:
- [Section 1 description]
- [Section 2 description]
```

---

## Discrepancy Documentation

```
DISCREPANCY FOUND:

FACT: [What fact has conflicting information]
SOURCE A: [Version 1]
SOURCE B: [Version 2]
SOURCE C: [Version 3 if applicable]

RESOLUTION: [Which version to use and why]
CONFIDENCE: [High/Medium/Low]
ACTION NEEDED: [What to verify further]
```

---

## Counter-Evidence Documentation

```
DEFENSE CLAIM: [What the opposing argument is]

SUPPORTING EVIDENCE:
- [Evidence point 1]
- [Evidence point 2]

CONTRADICTORY EVIDENCE:
- [Counter-evidence point 1]
- [Counter-evidence point 2]

RESOLUTION: [How this was resolved - court ruling, expert consensus, etc.]
CONFIDENCE: [Assessment of claim validity]
```

---

## Unresolved Questions Format

```
UNRESOLVED:
- [Question 1]
- [Question 2]

IMPACT: [Minor/Moderate/Major] - [Why]
MITIGATION: [How to handle in lyrics/narrative]
```

---

## Confidence Levels

| Level | Definition | Requirements |
|-------|------------|--------------|
| **HIGH** | 3+ primary sources, all align | Can state as fact |
| **MEDIUM** | 3+ sources, mix primary/secondary | Use "reportedly" or similar |
| **LOW** | Only secondary sources or conflicts | Flag for review |
| **UNVERIFIED** | Single source or no primary | Do not use without caveat |
