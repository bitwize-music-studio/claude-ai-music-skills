# SEC Filing Guide

Navigate EDGAR and understand key filing types for documentary research.

---

## EDGAR Basics

### Company Search
**URL**: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany

Search by:
- Company name
- Ticker symbol
- CIK (Central Index Key) number

### Full-Text Search
**URL**: https://efts.sec.gov/LATEST/search-index

Search within filing text for:
- Person names
- Keywords
- Specific phrases

---

## Key Filing Types

### Annual and Quarterly Reports

| Filing | Frequency | What It Contains |
|--------|-----------|-----------------|
| **10-K** | Annual | Complete financial picture, risk factors, legal proceedings |
| **10-Q** | Quarterly | Interim financials, updates |
| **20-F** | Annual | Foreign company equivalent of 10-K |

### Material Events (8-K)

Filed within 4 business days of material events:

| Item | Event Type | Lyric Value |
|------|------------|-------------|
| 1.01 | Material agreements | Deals, settlements |
| 1.03 | Bankruptcy | Company collapse |
| 1.05 | Cybersecurity incidents | Breach disclosures |
| 2.06 | Asset impairments | Write-downs |
| 5.02 | Executive departures | Leadership changes |
| 8.01 | Other events | Catch-all |

### Proxy Statements

| Filing | What It Contains |
|--------|-----------------|
| **DEF 14A** | Executive compensation, board info, shareholder votes |
| **DEFA14A** | Additional proxy materials |

### IPO and Offerings

| Filing | What It Contains |
|--------|-----------------|
| **S-1** | IPO registration, company history |
| **424B** | Final prospectus with pricing |

### Insider Trading

| Filing | What It Contains |
|--------|-----------------|
| **Form 4** | Insider buys/sells within 2 days |
| **13D/13G** | 5%+ ownership stakes |
| **13F** | Institutional holdings |

---

## Reading 10-K Filings

### Key Sections

**Item 1: Business**
- What the company does
- Market position
- Competition

**Item 1A: Risk Factors** (Gold for controversy research)
- What could go wrong
- New risks = new problems
- Compare year-over-year for changes

**Item 3: Legal Proceedings**
- Active lawsuits
- Investigations
- Regulatory matters

**Item 7: MD&A (Management Discussion)**
- Management's narrative
- Explanation of results
- Forward-looking statements

**Item 8: Financial Statements**
- Balance sheet, income statement, cash flow
- Auditor's opinion

**Notes to Financial Statements**
- Where details hide
- Contingent liabilities
- Related party transactions

---

## Finding Breach/Incident Disclosures

### 8-K Item 1.05 (Cybersecurity)
As of December 2023, material cyber incidents require 8-K filing.

Search: `"Item 1.05" OR "cybersecurity incident" type:8-K`

### Risk Factor Changes
Compare 10-K risk factors year-over-year:
- New cyber risks = recent incidents
- New litigation risks = pending cases
- New regulatory risks = investigations

### MD&A Mentions
Search quarterly 10-Qs for:
- "Cyber" or "security incident"
- "Investigation" or "inquiry"
- One-time charges related to incidents

---

## Executive Compensation Research

### DEF 14A Sections
- **Summary Compensation Table**: Total pay for top 5 execs
- **Pay Ratio**: CEO pay vs. median employee
- **Golden Parachutes**: Severance terms
- **Clawback Policies**: Can company recover pay?

### What to Extract
- CEO pay during crisis periods
- Bonuses despite poor performance
- Severance for executives who departed
- Stock awards timing

---

## Financial Analysis for Lyrics

### Key Metrics
| Metric | What It Means | Lyric Use |
|--------|--------------|-----------|
| Revenue decline | Business shrinking | "Revenue fell 40%" |
| Net loss | Losing money | "Billion-dollar loss" |
| Impairment | Writing down assets | "Goodwill evaporated" |
| Going concern | May not survive | "Going concern warning" |
| Restatement | Fixing past errors | "Had to restate the books" |

### Stock Price Context
Track stock around key dates:
- Yahoo Finance historical data
- Google Finance charts
- Note: pre/post event moves

---

## Search Tips

### EDGAR Search Operators
```
company:"Tesla"
type:8-K
"cybersecurity incident"
filed:[2023-01-01 TO 2023-12-31]
```

### Finding Specific Events
```
"Item 5.02" "departure" type:8-K     # Executive departures
"Item 1.05" type:8-K                  # Cyber incidents
"Item 1.03" "bankruptcy" type:8-K     # Bankruptcies
"restatement" type:10-K               # Financial restatements
```

---

## Archiving Filings

SEC filings are persistent, but archive anyway:
1. Download original filing (HTML or PDF)
2. Save to album documents folder
3. Note CIK, filing date, accession number
4. Create archive.org backup of EDGAR URL
