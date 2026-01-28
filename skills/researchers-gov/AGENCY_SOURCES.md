# Government Agency Sources Guide

Navigate federal agency websites and find official announcements.

---

## Department of Justice (DOJ)

### Press Releases
**Main**: https://www.justice.gov/news
**By topic**: https://www.justice.gov/news?keys=[keyword]

### US Attorney Offices
Each district has its own news page:
- SDNY: https://www.justice.gov/usao-sdny/news
- EDVA: https://www.justice.gov/usao-edva/news
- Pattern: `justice.gov/usao-[district]/news`

### Key Divisions
| Division | URL | Focus |
|----------|-----|-------|
| Criminal | justice.gov/criminal | White collar, organized crime |
| National Security | justice.gov/nsd | Espionage, terrorism |
| Civil Rights | justice.gov/crt | Civil rights violations |
| Antitrust | justice.gov/atr | Competition law |

### Search Tips
```
"[defendant name]" site:justice.gov
"pleaded guilty" site:justice.gov/usao-sdny
"sentenced" "[company]" site:justice.gov
```

---

## FBI

### Press Releases
**Main**: https://www.fbi.gov/news/press-releases
**Field offices**: https://www.fbi.gov/contact-us/field-offices

### Cyber Division
**URL**: https://www.fbi.gov/investigate/cyber

- Attribution statements
- Wanted posters for hackers
- Technical advisories

### Most Wanted
**URL**: https://www.fbi.gov/wanted

- Cyber's Most Wanted
- White-collar criminals
- Reward information

---

## SEC (Securities)

### Press Releases
**URL**: https://www.sec.gov/news/pressreleases

### Litigation Releases
**URL**: https://www.sec.gov/litigation/litreleases

- More detailed than press releases
- Case-specific information
- Settlement terms

### EDGAR (Filings)
**URL**: https://www.sec.gov/cgi-bin/browse-edgar

- Company filings (10-K, 8-K, etc.)
- Full-text search available

---

## CISA (Cybersecurity)

### Advisories
**URL**: https://www.cisa.gov/news-events/cybersecurity-advisories

### Alerts
**URL**: https://www.cisa.gov/news-events/alerts

### Known Exploited Vulnerabilities
**URL**: https://www.cisa.gov/known-exploited-vulnerabilities-catalog

---

## Treasury/OFAC (Sanctions)

### Press Releases
**URL**: https://home.treasury.gov/news/press-releases

### Sanctions List Search
**URL**: https://sanctionssearch.ofac.treas.gov/

- Search designated individuals/entities
- Sanctions reasons and dates

---

## FTC (Consumer Protection)

### Press Releases
**URL**: https://www.ftc.gov/news-events/news/press-releases

### Cases and Proceedings
**URL**: https://www.ftc.gov/legal-library/browse/cases-proceedings

---

## Setting Up Alerts

### RSS Feeds
Most agency news pages offer RSS:
- DOJ: https://www.justice.gov/feeds
- FBI: Check individual pages for RSS icons
- SEC: https://www.sec.gov/rss

### Google Alerts
Create alerts for:
- `site:justice.gov "[company name]"`
- `site:sec.gov "[executive name]"`
- `"indicted" OR "charged" "[topic]"`

---

## Historical Research

### Wayback Machine
Government sites restructure frequently. Use:
```
https://web.archive.org/web/*/justice.gov/*[keyword]*
```

### Government Archives
**National Archives**: https://www.archives.gov/
**GPO**: https://www.govinfo.gov/
**Congress.gov**: https://www.congress.gov/

---

## Reading Government Releases

### Standard Structure (DOJ/FBI)
1. **Headline**: Action taken (charged, sentenced, etc.)
2. **Lead paragraph**: Who, what, when, where
3. **Official quote**: AG, USAO, FBI SAC statement
4. **Details**: Scheme description
5. **Penalties**: What they face/received
6. **Credits**: Investigating agencies

### What to Extract
- **Official quotes**: Dramatic statements for lyrics
- **Numbers**: Verified figures (amounts, victims, sentences)
- **Timeline**: Dates mentioned
- **Related cases**: Often linked at bottom
