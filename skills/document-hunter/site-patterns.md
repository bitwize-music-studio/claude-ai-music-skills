# Site-Specific Patterns

Automation strategies for each document source.

---

## 1. DocumentCloud (https://www.documentcloud.org/)

- Nonprofit document archive
- Journalists upload PACER docs after purchasing
- **Critical**: SvelteKit/React app - PDF links only appear AFTER JavaScript renders

**Automation Strategy**:
1. Load page with `wait_until='networkidle'`
2. Wait additional 5 seconds for JavaScript to finish rendering
3. Query rendered DOM for links (`query_selector_all('a')`)
4. Find S3 bucket URLs (pattern: `s3.documentcloud.org/documents/*/...pdf`)
5. Download from S3 directly (faster than clicking)

**Success Rate**: High (tested with historical court documents)

---

## 2. CourtListener / RECAP (https://www.courtlistener.com/)

- Crowdsourced PACER archive
- Search by: case number, docket, party names

**Automation**:
1. Navigate to search page
2. Search by case number or party names
3. Navigate to docket page
4. Check which docs are free (RECAP uploaded)
5. Download available documents

---

## 3. Scribd (https://www.scribd.com/)

- User-uploaded documents
- Many journalists upload court docs

**Automation**:
1. Search by case name
2. Filter for documents (not books)
3. Identify court docs by title/description
4. Download or scrape content

**Note**: May require free account

---

## 4. Justia (https://www.justia.com/)

- Free legal database
- Good for appellate opinions

**Automation**:
1. Search by case number or party names
2. Navigate to case page
3. Download opinions and key filings

---

## 5. Court Websites

Example: `cand.uscourts.gov/cases-of-interest/`

**Automation**:
1. Navigate to court's "cases of interest" or "notable cases"
2. Search for case name
3. Check for document downloads

---

## 6. Government Agencies

### DOJ (justice.gov)
- Press releases link to indictments/complaints
- URL pattern: `justice.gov/usao/[district]/press-releases`

### SEC (sec.gov)
- Litigation releases at `sec.gov/litigation`
- Complaints and settlements publicly available

**Automation**:
1. Search press releases for case name
2. Extract PDF links from release
3. Download directly

---

## 7. Legal Publisher Sites

### CCH (business.cch.com)
- Some case documents hosted
- Search by case name + "PDF"

---

## Python Code Template

```python
from playwright.sync_api import sync_playwright
import os
import json
from datetime import datetime

def hunt_documents(case_name, case_number, output_dir):
    """
    Systematically search all free sources for court documents.
    """
    manifest = {
        "case_name": case_name,
        "case_number": case_number,
        "search_date": datetime.now().isoformat(),
        "sources_searched": [],
        "documents_found": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (research bot)"
        )
        page = context.new_page()

        # Search each source
        for source_func in [search_documentcloud, search_courtlistener,
                           search_scribd, search_government]:
            try:
                results = source_func(page, case_name, output_dir)
                manifest["documents_found"].extend(results)
            except Exception as e:
                print(f"Error: {e}")

        browser.close()

    # Save manifest
    manifest_path = os.path.join(output_dir, "metadata", "document-manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest


def search_documentcloud(page, case_name, output_dir):
    """Search DocumentCloud for case documents."""
    results = []

    page.goto("https://www.documentcloud.org/app", timeout=30000)
    page.wait_for_selector('input[type="search"]', timeout=10000)

    # Search
    page.fill('input[type="search"]', case_name)
    page.press('input[type="search"]', 'Enter')
    page.wait_for_load_state('networkidle')

    # Wait for JS rendering
    page.wait_for_timeout(5000)

    # Extract document links
    doc_links = page.query_selector_all('a[href*="/documents/"]')

    for link in doc_links[:10]:
        href = link.get_attribute('href')
        title = link.inner_text()

        # Navigate to document, find PDF, download
        # ... (implementation details)

    return results


def search_courtlistener(page, case_number, output_dir):
    """Search CourtListener for RECAP documents."""
    results = []

    page.goto(f"https://www.courtlistener.com/?q={case_number}")
    page.wait_for_load_state('networkidle')

    # Find and download free documents
    # ... (implementation details)

    return results
```

---

## RECAP Extension

The RECAP browser extension crowdsources PACER documents to CourtListener.

**Location**: `/tools/extensions/recap-extension/`

**Setup**:
```bash
cd tools/extensions
curl -L "https://github.com/freelawproject/recap-chrome/releases/download/2.8.6/chrome-release.zip" -o recap.zip
unzip recap.zip -d recap-extension
rm recap.zip
```

**Usage**: Script auto-loads RECAP extension when launching Chromium.

---

## Known Issues

### SEC.gov
- Has Akamai WAF (blocks automation)
- **Alternative**: Use DOJ press releases which link to the same documents

### Scribd
- May require account for some downloads
- Rate limiting possible

### Court Websites
- Layout varies by court
- May require custom selectors
