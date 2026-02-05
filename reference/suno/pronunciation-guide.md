# Pronunciation Guide for Suno Lyrics

Suno's text-to-speech engine can mispronounce words, especially homographs (same spelling, different pronunciation) and technical terms. This guide helps identify problem words and provides solutions.

> **Related skill**: `/bitwize-music:pronunciation-specialist` (automated scanning for pronunciation risks)
> **Related docs**: [v5-best-practices.md](v5-best-practices.md)

## Why This Matters

Suno reads lyrics literally. It doesn't understand context the way humans do. When it sees "live," it picks one pronunciation — and it might be wrong for your meaning.

**V5 Note**: V5 improved context sensitivity for pronunciation, but our rule stands: **never trust context for homographs**. The improvement is incremental, not reliable enough to skip phonetic spelling.

**IPA Note**: IPA (International Phonetic Alphabet) is **not natively supported** by Suno despite community requests. Use the phonetic spelling approaches documented below instead.

**Example**: "LiveJournal confessions" was sung as "LIV-journal" (like a live performance) instead of "LYVE-journal" (like alive).

## Homographs Reference

Words spelled the same but pronounced differently depending on meaning.

### High-Risk Homographs

| Word | Pronunciation A | Pronunciation B | Example Context |
|------|-----------------|-----------------|-----------------|
| **live** | /lɪv/ (LIV) - live performance, live show | /laɪv/ (LYVE) - alive, living, to reside | See detailed "live" section below |
| **read** | /riːd/ (REED) - present tense | /rɛd/ (RED) - past tense | "I read it yesterday" = RED |
| **lead** | /liːd/ (LEED) - guide, metal band | /lɛd/ (LED) - the metal | "Lead pipes" = LED |
| **wind** | /wɪnd/ (WIND) - breeze | /waɪnd/ (WYND) - turn, coil | "Wind the clock" = WYND |
| **close** | /kloʊs/ (KLOHS) - near | /kloʊz/ (KLOHZ) - shut | "Close the door" = KLOHZ |
| **tear** | /tɪr/ (TEER) - from crying | /tɛr/ (TAIR) - rip | "Tear the page" = TAIR |
| **bow** | /boʊ/ (BOH) - ribbon, weapon | /baʊ/ (BOW) - bend, ship front | "Take a bow" = BOW |
| **bass** | /beɪs/ (BAYSS) - instrument, low freq | /bæs/ (BASS) - the fish | Usually BAYSS in music |
| **row** | /roʊ/ (ROH) - line, propel boat | /raʊ/ (ROW) - argument | "Row of seats" = ROH |
| **sow** | /soʊ/ (SOH) - plant seeds | /saʊ/ (SOW) - female pig | "Sow the seeds" = SOH |
| **wound** | /wuːnd/ (WOOND) - injury | /waʊnd/ (WOWND) - coiled | "Wound around" = WOWND |
| **minute** | /ˈmɪnɪt/ (MIN-it) - 60 seconds | /maɪˈnjuːt/ (my-NOOT) - tiny | "Minute details" = my-NOOT |
| **resume** | /rɪˈzuːm/ (ri-ZOOM) - continue | /ˈrɛzjʊmeɪ/ (REZ-oo-may) - CV | Usually ri-ZOOM |
| **object** | /ˈɒbdʒɪkt/ (OB-jekt) - thing | /əbˈdʒɛkt/ (ob-JEKT) - protest | "I object" = ob-JEKT |
| **project** | /ˈprɒdʒɛkt/ (PROJ-ekt) - plan | /prəˈdʒɛkt/ (pro-JEKT) - throw | "Project your voice" = pro-JEKT |
| **record** | /ˈrɛkərd/ (REK-ord) - noun | /rɪˈkɔːrd/ (ri-KORD) - verb | "Record a song" = ri-KORD |
| **present** | /ˈprɛzənt/ (PREZ-ent) - gift, here | /prɪˈzɛnt/ (pri-ZENT) - give | "Present the award" = pri-ZENT |
| **content** | /ˈkɒntɛnt/ (KON-tent) - stuff | /kənˈtɛnt/ (kon-TENT) - satisfied | "I'm content" = kon-TENT |
| **desert** | /ˈdɛzərt/ (DEZ-ert) - sandy place | /dɪˈzɜːrt/ (di-ZURT) - abandon | "Desert the cause" = di-ZURT |
| **refuse** | /ˈrɛfjuːs/ (REF-yoos) - garbage | /rɪˈfjuːz/ (ri-FYOOZ) - decline | "I refuse" = ri-FYOOZ |

### Detailed: "live" Pronunciation Fixes

The word "live" is one of the most common pronunciation problems in Suno. **Always clarify which meaning is intended.**

#### LYVE (rhymes with "five") - alive, living, to reside

| Intended | Problem | Fix Options |
|----------|---------|-------------|
| "live your life" | May say LIV | Use "lyve your life" or rewrite to "living your life" |
| "live and breathe" | May say LIV | Use "lyve and breathe" or "alive and breathing" |
| "I live here" | May say LIV | Use "I lyve here" or "I'm living here" or "I reside here" |
| "LiveJournal" | May say LIV-journal | Use "Life-journal" or "Lyve-journal" |
| "live wire" | May say LIV wire | Use "lyve wire" |
| "alive" | Usually fine | No fix needed |
| "living" | Usually fine | No fix needed |

#### LIV (rhymes with "give") - live performance, live show, broadcasting

| Intended | Problem | Fix Options |
|----------|---------|-------------|
| "live performance" | May say LYVE | Use "liv performance" or rewrite to "performing live" |
| "live show" | May say LYVE | Use "liv show" or "concert" |
| "live broadcast" | May say LYVE | Use "liv broadcast" or "broadcasting now" |
| "live audience" | May say LYVE | Use "liv audience" or "studio audience" |
| "going live" | May say LYVE | Use "going liv" or "on air now" |
| "live stream" | May say LYVE | Use "liv stream" or "streaming now" |

#### Quick Decision Guide

Ask yourself: **Does it rhyme with "five" or "give"?**

- "I want to **live** my dreams" → LYVE (rhymes with five) → use "lyve" or "living"
- "We're going **live** on air" → LIV (rhymes with give) → use "liv" or rewrite

### Medium-Risk Homographs

| Word | Pronunciations | Notes |
|------|---------------|-------|
| **alternate** | ALL-ter-nit (adj) / ALL-ter-nayt (verb) | Context usually clear |
| **attribute** | AT-trib-yoot (noun) / a-TRIB-yoot (verb) | Context usually clear |
| **combine** | KOM-byne (noun, farm) / kom-BYNE (verb) | Rare noun usage |
| **complex** | KOM-pleks (noun) / kom-PLEKS (adj) | Usually adjective |
| **conduct** | KON-dukt (noun) / kon-DUKT (verb) | Context usually clear |
| **conflict** | KON-flikt (noun) / kon-FLIKT (verb) | Usually noun |
| **console** | KON-sole (noun) / kon-SOLE (verb) | Tech context = noun |
| **contract** | KON-trakt (noun) / kon-TRAKT (verb) | Context usually clear |
| **contrast** | KON-trast (noun) / kon-TRAST (verb) | Context usually clear |
| **convert** | KON-vert (noun) / kon-VERT (verb) | Usually verb |
| **convict** | KON-vikt (noun) / kon-VIKT (verb) | Context usually clear |
| **decrease** | DEE-krees (noun) / dee-KREES (verb) | Context usually clear |
| **digest** | DY-jest (noun) / dy-JEST (verb) | Context usually clear |
| **discount** | DIS-count (noun) / dis-COUNT (verb) | Context usually clear |
| **exploit** | EKS-ploit (noun) / eks-PLOIT (verb) | Tech context = noun |
| **extract** | EKS-trakt (noun) / eks-TRAKT (verb) | Context usually clear |
| **impact** | IM-pakt (noun) / im-PAKT (verb) | Usually noun |
| **import** | IM-port (noun) / im-PORT (verb) | Context usually clear |
| **incline** | IN-klyne (noun) / in-KLYNE (verb) | Context usually clear |
| **increase** | IN-krees (noun) / in-KREES (verb) | Context usually clear |
| **insert** | IN-sert (noun) / in-SERT (verb) | Context usually clear |
| **insult** | IN-sult (noun) / in-SULT (verb) | Context usually clear |
| **invalid** | IN-va-lid (adj, not valid) / in-VA-lid (noun, sick person) | Rare noun |
| **misprint** | MIS-print (noun) / mis-PRINT (verb) | Rare word |
| **moderate** | MOD-er-it (adj) / MOD-er-ayt (verb) | Context usually clear |
| **perfect** | PER-fekt (adj) / per-FEKT (verb) | "Perfect the art" = verb |
| **permit** | PER-mit (noun) / per-MIT (verb) | Context usually clear |
| **pervert** | PER-vert (noun) / per-VERT (verb) | Usually noun |
| **produce** | PROD-oos (noun) / pro-DOOS (verb) | "Fresh produce" = noun |
| **progress** | PROG-ress (noun) / pro-GRESS (verb) | Context usually clear |
| **protest** | PRO-test (noun) / pro-TEST (verb) | Context usually clear |
| **rebel** | REB-el (noun) / ri-BEL (verb) | "I rebel" = verb |
| **recount** | REE-count (noun) / ree-COUNT (verb) | Context usually clear |
| **refund** | REE-fund (noun) / ree-FUND (verb) | Context usually clear |
| **reject** | REE-jekt (noun) / ri-JEKT (verb) | Usually verb |
| **relay** | REE-lay (noun) / ree-LAY (verb) | Context usually clear |
| **segment** | SEG-ment (noun) / seg-MENT (verb) | Usually noun |
| **separate** | SEP-er-it (adj) / SEP-er-ayt (verb) | Context usually clear |
| **subject** | SUB-jekt (noun) / sub-JEKT (verb) | "Subject to" = verb |
| **survey** | SUR-vay (noun) / sur-VAY (verb) | Context usually clear |
| **suspect** | SUS-pekt (noun) / sus-PEKT (verb) | Context usually clear |
| **torment** | TOR-ment (noun) / tor-MENT (verb) | Context usually clear |
| **transfer** | TRANS-fer (noun) / trans-FER (verb) | Context usually clear |
| **transport** | TRANS-port (noun) / trans-PORT (verb) | Context usually clear |
| **upset** | UP-set (noun/adj) / up-SET (verb) | Usually adjective |

## Tech Terms & Brand Names

### Compound Brand Names

| Term | Correct | Wrong | Fix |
|------|---------|-------|-----|
| LiveJournal | LYVE-journal | LIV-journal | Write "Life-journal" or rewrite |
| YouTube | YOU-toob | yoo-TOOB | Usually fine, but watch for emphasis |
| GitHub | GIT-hub | GITH-ub | Usually fine |
| MySpace | MY-space | MICE-pace | Usually fine |
| GeoCities | JEE-oh-cities | GEO-cities | Usually fine |
| CompuServe | kom-pyu-SERV | Usually fine | - |
| SoundCloud | SOUND-cloud | Usually fine | - |
| Usenet | YOOZ-net | YOOS-net | Either acceptable |

### Acronyms & Initialisms

#### Suno-Specific Spelling for Correct Pronunciation

Some terms need special spelling in lyrics to get Suno to pronounce them correctly:

| Term | Correct Pronunciation | Write As | Notes |
|------|----------------------|----------|-------|
| GNU | "guh-NEW" (hard G) | **guh-new** | Without this, Suno may say "G-N-U" or "new" |
| Debian | "DEB-ee-un" | **Deb-Ian** | Hyphen ensures three syllables |

#### Letter-by-Letter Acronyms

Use periods between letters to force Suno to spell them out:
- **S.L.S.** not "SLS"
- **L.K.M.L.** not "LKML"
- **B.D.F.L.** not "BDFL"
- **D.F.S.G.** not "DFSG"
- **A.P.I.** not "API"

Without periods, Suno may try to pronounce letter-acronyms as words.

#### Standard Acronym Pronunciations

| Term | Pronunciation | Notes |
|------|--------------|-------|
| SQL | "sequel" or "S-Q-L" | Both used, "sequel" more common |
| GUI | "gooey" | Not "G-U-I" |
| API | "A-P-I" | Spell it out |
| URL | "U-R-L" or "earl" | Spell out preferred |
| GIF | "jif" or "gif" | Contested - avoid if possible |
| IEEE | "eye-triple-E" | Not "I-E-E-E" |
| BIOS | "BY-ose" | Not "B-I-O-S" |
| ASCII | "ASK-ee" | Not "A-S-C-I-I" |
| SCSI | "scuzzy" | Not "S-C-S-I" |
| WYSIWYG | "WIZ-ee-wig" | The what-you-see acronym |
| FAQ | "fak" or "F-A-Q" | Both used |
| PNG | "ping" or "P-N-G" | Both used |
| JPEG | "JAY-peg" | Not "J-P-E-G" |
| MIDI | "MID-ee" | Not "M-I-D-I" |
| WiFi | "WY-fy" | Not "wiff-ee" |
| SaaS | "sass" | Not "S-A-A-S" |
| LED | "L-E-D" | Spell it out |
| RAM | "ram" | Like the animal |
| ROM | "rom" | Rhymes with Tom |
| DOS | "doss" | Not "D-O-S" |
| LAN | "lan" | Rhymes with pan |
| WAN | "wan" | Rhymes with John |

### Tech Words

| Term | Correct | Common Mistake |
|------|---------|---------------|
| Linux | LIN-ucks | LINE-ucks |
| data | DAY-ta or DAT-a | Both acceptable |
| cache | "cash" | "catch" or "cash-ay" |
| daemon | DEE-mon | DAY-mon |
| byte | "bite" | - |
| pixel | PIK-sel | - |
| router | ROW-ter (US) or ROOT-er (UK) | Context-dependent |
| admin | AD-min | Not "add-MEEN" |
| sudo | "SOO-doo" or "SOO-doh" | Not "pseudo" |
| root | "root" | - |
| kernel | KER-nel | - |
| chmod | "ch-mod" or "change-mod" | - |
| grep | "grep" (rhymes with step) | - |
| wget | "w-get" or "double-you-get" | - |
| regex | "REJ-eks" | Not "REE-jeks" |
| tuple | "TUP-el" or "TOO-pel" | Both used |

## Fixes & Workarounds

### Option 1: Rewrite (Preferred)

Find alternative phrasing that avoids the problem word entirely.

**Before**: "LiveJournal confessions in abandoned rooms"
**After**: "Old blog confessions in abandoned rooms"

**Before**: "I read your message yesterday"
**After**: "I saw your message yesterday"

### Option 2: Phonetic Spelling

Write the word how it sounds. Looks weird in lyrics but works.

| Original | Phonetic | Use When |
|----------|----------|----------|
| LiveJournal | Life-journal | Brand pronunciation critical |
| read (past) | red | Past tense ambiguous |
| lead (metal) | led | Metal meaning needed |
| wound (coil) | wownd | Coil meaning needed |
| live (alive) | lyve | Alive/living meaning (rhymes with "five") |
| live (performance) | liv | Live show/broadcast meaning (rhymes with "give") |

### Option 3: Hyphenation

Break syllables to guide pronunciation. Can help with sustained notes too.

| Original | Hyphenated | Effect |
|----------|-----------|--------|
| live (alive) | li-ive | Forces long 'i' |
| read (present) | ree-ead | Forces long 'e' |
| wind (coil) | wi-ind | Forces long 'i' |

### Option 4: Context Padding

Add words that make the pronunciation obvious.

**Before**: "Live broadcast from the scene"
**After**: "Broadcasting live from the scene" (verb form clearer)

**Before**: "The lead singer"
**After**: "Leading the band" (verb form avoids ambiguity)

### Option 5: Accept It

Sometimes the mispronunciation isn't jarring enough to matter, or there's no good fix. Document the risk and move on.

## Pronunciation Table Enforcement Workflow

The Pronunciation Notes table in each track file is a **mandatory checklist**, not passive documentation. Every entry MUST be applied as phonetic spelling in the Suno Lyrics Box.

### Process

1. **Before finalizing any track**: Read the Pronunciation Notes table top to bottom
2. **For each entry**: Search the Suno Lyrics Box for the standard spelling
3. **Replace** with the phonetic version from the table
4. **Verify** every occurrence is fixed — check all verses, choruses, bridges, and outros
5. **Common failure**: Word added to table but never applied to lyrics, or phonetic in one verse but missed in chorus/bridge

### Verification Format

After applying all phonetics, document verification:

```markdown
| Word | Standard | Phonetic | Applied? |
|------|----------|----------|----------|
| Ramos | Ramos | Rah-mohs | ✓ All 4 occurrences |
| live | live | lyve | ✓ V1, V2, Chorus |
| FBI | FBI | F-B-I | ✓ Bridge |
```

### Rules

- The table is the source of truth — if it says phonetic, the Suno lyrics MUST use phonetic
- Streaming/distributor lyrics always keep standard English spelling
- When adding a new word to the table, immediately apply it to all Suno lyrics
- Run this check as the final step before generation, after all other edits are complete

## Numbers

Always **spell out numbers** in Suno lyrics — Suno handles written-out numbers more reliably than digits.

| Write | Not |
|-------|-----|
| twenty-one | 21 |
| nineteen eighty-four | 1984 |
| three hundred | 300 |

**Exception**: Year abbreviations like `'93` work well and avoid the "ninety-three" producer tag filter issue.

---

## Multilingual Tracks

For songs with lyrics in multiple languages:

- **Use one language per section** — mixing languages within a section causes pronunciation drift
- Add `all lyrics in [language], no English` to the style prompt for non-English sections to prevent the model reverting to English
- V5 improved multilingual fluency, but section isolation remains the most reliable approach

**Example**:
```
[Verse 1 - Spanish]
Spanish lyrics here...

[Chorus - English]
English chorus here...
```

Style prompt: Include both language indicators: "bilingual, Spanish verse, English chorus"

---

## Quick Reference Card

```
HIGH-RISK WORDS (always check):
live, read, lead, wind, close, tear, bow, bass, wound

TECH TERMS (verify pronunciation):
- Compound brands: LiveJournal, YouTube, GitHub
- Acronyms: SQL, GUI, GIF, IEEE, ASCII
- Tech words: Linux, cache, daemon, router

FIX PRIORITY:
1. Rewrite (different word)
2. Phonetic spelling (looks weird, works)
3. Hyphenation (break syllables)
4. Context padding (add clarifying words)
5. Accept (document and move on)

DOCUMENT RISKS:
Add "Pronunciation Risks" section to Production Notes
if a word can't be fixed but might mispronounce.
```

## Accent Simulation

Suno doesn't have direct accent controls, but you can simulate accents:

### Technique

1. **Rewrite lyrics phonetically** as spoken in target accent
   - NOT dictionary spelling
   - Spell words as they sound in the accent

2. **Add accent name to style box**
   - Example: "Russian accent"
   - Example: "Jamaican accent"
   - Example: "Southern drawl"

3. **Use ChatGPT for conversion** (optional)
   - Prompt: "Rewrite these lyrics phonetically for a [accent] accent"

### Examples

**Standard**: "I'm going to the store"
**Russian accent**: "Ahm go-ink to da store"
**Jamaican accent**: "Mi ah go ah di store"
**Southern US**: "Ahm goin' to tha store"

**Note**: Results vary by accent complexity. Simple accents (Russian, Irish) work better than complex regional dialects.

---

## Testing

When in doubt:
1. Say the line out loud both ways
2. Ask: "If Suno picks wrong, is the song ruined?"
3. If yes, fix it. If no, document and move on.

---

## Related Skills

- **`/bitwize-music:pronunciation-specialist`** - Automated pronunciation scanning for lyrics
  - Scans for homographs, proper nouns, acronyms, tech terms
  - Uses this guide as reference
  - Suggests phonetic fixes automatically

- **`/bitwize-music:lyric-writer`** - Lyric writing with automatic pronunciation checks
  - Includes automatic pronunciation scanning after every draft
  - Applies rules from this guide during review process

- **`/bitwize-music:lyric-reviewer`** - Pre-generation QC gate
  - 13-point checklist includes pronunciation verification
  - Verifies homograph decisions and phonetic spelling application before Suno generation

## See Also

- **`/reference/suno/v5-best-practices.md`** - Overall Suno V5 prompting guide, style box construction
- **`/reference/suno/structure-tags.md`** - Section tags for organizing lyrics ([Verse], [Chorus], etc.)
- **`/skills/lyric-writer/SKILL.md`** - Complete lyric writing workflow and quality standards
- **`/skills/pronunciation-specialist/SKILL.md`** - Detailed pronunciation specialist skill documentation
