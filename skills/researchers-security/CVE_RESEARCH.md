# CVE and Security Research Guide

Navigate vulnerability databases and security research sources.

---

## CVE Databases

### MITRE CVE
**URL**: https://cve.mitre.org/

- Authoritative CVE assignments
- Basic vulnerability descriptions
- Links to references

**Search**: https://cve.mitre.org/cve/search_cve_list.html

### NVD (NIST)
**URL**: https://nvd.nist.gov/

- Enhanced CVE data with CVSS scores
- CPE (affected products) listings
- Better search interface

**Search by keyword**: https://nvd.nist.gov/vuln/search

### Exploit-DB
**URL**: https://www.exploit-db.com/

- Proof-of-concept exploits
- Links to CVEs
- Historical exploit archive

---

## Understanding CVE Data

### CVE Identifier Format
`CVE-YYYY-NNNNN`
- YYYY: Year assigned (not necessarily year discovered)
- NNNNN: Sequential number

### CVSS Scores
| Score | Severity | Example Impact |
|-------|----------|----------------|
| 9.0-10.0 | Critical | Remote code execution, no auth |
| 7.0-8.9 | High | Significant data breach risk |
| 4.0-6.9 | Medium | Limited exploitation |
| 0.1-3.9 | Low | Minor impact |

### Key Fields
- **Description**: What the vulnerability is
- **Affected Products**: Versions/systems impacted
- **CVSS Vector**: Technical details of exploitability
- **References**: Vendor advisories, patches, write-ups

---

## Security Disclosure Timelines

### Standard Disclosure Flow
1. **Discovery**: Researcher finds vulnerability
2. **Report**: Vendor notified (private)
3. **Patch Development**: Vendor creates fix
4. **Coordinated Disclosure**: CVE assigned, advisory published
5. **Patch Release**: Fix available
6. **Public Details**: Full technical write-up (after patch)

### Timeline for Research
- **Zero-day**: Exploited before patch exists
- **N-day**: Exploited after disclosure but before patch widely deployed
- **Disclosure date**: When CVE published (key date for lyrics)
- **Patch date**: When fix released

---

## Security Research Sources

### Vendor Advisories
- **Microsoft**: https://msrc.microsoft.com/
- **Apple**: https://support.apple.com/en-us/HT201222
- **Google**: https://security.googleblog.com/
- **Cisco**: https://tools.cisco.com/security/center

### Security Company Research
| Company | URL | Specialty |
|---------|-----|-----------|
| Mandiant | mandiant.com/resources/blog | APT groups, incident response |
| CrowdStrike | crowdstrike.com/blog | Nation-state, ransomware |
| Kaspersky | securelist.com | Malware analysis |
| Cisco Talos | blog.talosintelligence.com | Threat intelligence |
| Microsoft | microsoft.com/security/blog | Windows threats |

### Independent Researchers
- **Krebs on Security**: krebsonsecurity.com
- **Troy Hunt**: troyhunt.com
- **Google Project Zero**: googleprojectzero.blogspot.com
- **ZDI Blog**: zerodayinitiative.com/blog

---

## Malware Analysis Resources

### Malware Databases
- **VirusTotal**: virustotal.com (file/URL analysis)
- **MalwareBazaar**: bazaar.abuse.ch (malware samples)
- **YARA Rules**: github.com/Yara-Rules

### Threat Intelligence
- **MITRE ATT&CK**: attack.mitre.org (techniques, tactics)
- **AlienVault OTX**: otx.alienvault.com (IOC sharing)
- **Malpedia**: malpedia.caad.fkie.fraunhofer.de (malware encyclopedia)

### APT Group Tracking
MITRE ATT&CK Groups: https://attack.mitre.org/groups/

**Naming conventions** (same group, different names):
- APT29 = Cozy Bear = The Dukes
- APT28 = Fancy Bear = Strontium
- Lazarus Group = Hidden Cobra = Guardians of Peace

---

## Researching Incidents

### Incident Research Workflow
1. **Initial reports**: News coverage, vendor disclosure
2. **CVE lookup**: What vulnerabilities exploited
3. **Technical analysis**: Security company write-ups
4. **Attribution**: Government statements, security research
5. **Impact**: Victim statements, SEC filings

### Key Questions
- What CVE(s) were exploited?
- Who discovered/reported?
- What was the attack vector?
- Who was attributed? With what confidence?
- What was the impact (data, systems, costs)?

---

## For Lyrics

### Technical Terms That Sound Good
| Term | Meaning | Lyric Use |
|------|---------|-----------|
| Zero-day | Unknown vulnerability | "Zero-day in the wild" |
| CVE | Vulnerability identifier | "CVE-2017-0144, EternalBlue" |
| Exploit | Attack code | "Dropped the exploit" |
| Patch | Security fix | "Unpatched systems" |
| IOC | Indicator of compromise | "IOCs all over the network" |
| Attribution | Identifying attacker | "Attribution's a guessing game" |

### Numbers for Authenticity
- CVE numbers (CVE-2017-0144)
- CVSS scores (9.8 critical)
- Days from disclosure to exploit
- Systems affected counts
