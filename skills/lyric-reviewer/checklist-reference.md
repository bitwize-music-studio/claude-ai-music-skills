# 14-Point Checklist Reference

Detailed criteria for each lyric review checkpoint.

---

## 1. Rhyme Check

**What to scan:**
- Line endings across all verses/choruses
- Repeated end words
- Self-rhymes (love/love)
- Overused patterns (heart/apart, fire/desire, night/light, moon/June)

**Severity:**
- **Warning**: Self-rhyme, repeated end word
- **Info**: Predictable/lazy rhyme

**Output format:**
```
### Rhyme Check
- [✗] V1:L2-L4: Self-rhyme "street/street"
- [⚠] V2:L1-L3: Predictable "fire/desire"
- [✓] Chorus: No issues
```

---

## 2. Prosody Check

**What to scan:**
- Multi-syllable words
- Natural stress alignment with beat positions
- Inverted word order forced for rhyme

**How to check:**
- Speak the lyric aloud
- Would you naturally emphasize those syllables?
- Does "to-NIGHT" or "a-BOUT" sound wrong?

**Severity:**
- **Warning**: Clear stress misalignment
- **Info**: Subtle/debatable prosody issue

**Output format:**
```
### Prosody Check
- [✗] V1:L3: "reservoir" stress on wrong beat
- [⚠] Bridge:L2: Inverted word order "the truth he knew"
- [✓] Chorus: Natural flow
```

---

## 3. Pronunciation Check

**What to scan:**
- **Proper nouns** (names, places, brands)
- **Homographs** (live, lead, read, wind, tear, bass, close, bow, wound)
- **Acronyms** (FBI, GPS, RICO → F-B-I, G-P-S, Ree-koh)
- **Tech terms** (Linux, SQL → Lin-ucks, sequel)
- **Numbers** (1993 → '93 or nineteen ninety-three)
- **Foreign names** (Jose → Ho-zay, Sinaloa → Sin-ah-lo-ah)

**Critical Check**: Compare Pronunciation Notes table against Lyrics Box
- If name in Notes table, must be phonetic in Lyrics Box
- If phonetic only in Notes but spelled normally in Lyrics Box = FAIL

**Severity:**
- **Critical**: Unphonetic proper noun in Lyrics Box (will mispronounce)
- **Critical**: Homograph without clarification
- **Warning**: Acronym not spelled out
- **Info**: Number could be written cleaner

**Output format:**
```
### Pronunciation Check
- [✗] CRITICAL: "Jose Diaz" in Lyrics Box not phonetic (Notes says "Ho-say Dee-ahz")
- [✗] CRITICAL: "live" is homograph - needs "lyve" or "liv"
- [⚠] V2:L3: "FBI" should be "F-B-I"
- [✓] Numbers: Using '93 format correctly
```

### Homograph Detection

**Always flag these words in Lyrics Box:**

| Word | Must clarify | Options |
|------|-------------|---------|
| live | Always | lyve (alive) or liv (performance) |
| read | If past tense | red |
| lead | If metal | led |
| wind | If coil/turn | wined |
| close | If shut | clohz |
| tear | If rip | tare |
| bass | If fish | bass (rhymes with "pass") |
| wound | If coiled | wownd |
| bow | If bend | bow (rhymes with "cow") |

---

## 4. POV/Tense Check

**What to scan:**
- Pronouns per section (I/me/we vs he/she/they vs you)
- Tense consistency (past vs present)
- Unmotivated shifts

**Allowed patterns:**
- Third-person verses, first-person chorus (common)
- Past tense story, present tense reflection
- Intentional shift for emotional effect

**Severity:**
- **Warning**: Inconsistent POV within section
- **Warning**: Tense jumping without clear reason
- **Info**: Could be intentional but flag for review

**Output format:**
```
### POV/Tense Check
- [✗] V1: Shifts from "he" (L1-3) to "you" (L4)
- [⚠] Bridge: Past tense but chorus is present
- [✓] Verses: Consistent third-person
```

---

## 5. Structure Check

**What to scan:**
- Section tags present ([Verse], [Chorus], [Bridge], etc.)
- Verse/chorus contrast (different energy, specificity)
- V2 development (not twin of V1)
- Title/hook placement (first or last line of chorus)

**V2 Twin Test:**
- Does V2 say the same thing as V1 with different words?
- Does V2 develop the story or just repeat the message?

**Severity:**
- **Warning**: Missing section tags
- **Warning**: Twin verses (V2 = V1 reworded)
- **Warning**: Buried hook (title not prominent)
- **Info**: Could use stronger contrast

**Output format:**
```
### Structure Check
- [✓] Section tags: All present
- [✗] V2 is twin of V1 - both describe "the problem" without development
- [⚠] Hook buried mid-chorus, not first/last line
```

---

## 6. Flow Check

**What to scan:**
- Forced rhymes (word clearly chosen just because it rhymes)
- Inverted word order ("The truth to him was known")
- Awkward phrasing that no one would say
- Filler words/syllables
- Line length consistency between matching sections

**Conversational Test:**
- Would someone actually say this?
- Does it sound like song lyrics or a thesaurus explosion?

**Severity:**
- **Warning**: Clearly forced/awkward line
- **Info**: Slightly unnatural but not jarring

**Output format:**
```
### Flow Check
- [✗] V2:L4: "Upon the desk it lay" - inverted for rhyme
- [⚠] Bridge:L2: "Verily" - no one talks like this
- [✓] Choruses: Natural conversational flow
```

---

## 7. Documentary Check (Conditional)

**When to apply**: Only if RESEARCH.md exists in album directory

**What to scan:**
- Internal state claims ("she felt afraid", "he believed")
- Fabricated quotes (dialogue not from sources)
- Speculative actions ("she finally made the call")
- Negative factual claims ("nobody heard", "no one knew")
- Unsourced facts

**Reference**: Check lyrics against RESEARCH.md

**Severity:**
- **Critical**: Fabricated quote (legal risk)
- **Critical**: Internal state claim without testimony source
- **Warning**: Speculative action not in sources
- **Info**: Could attribute more clearly

**Output format:**
```
### Documentary Check
- [✗] CRITICAL: V2:L3 "she was afraid" - internal state, no testimony source
- [✗] CRITICAL: Bridge:L1 "'Help me,' she said" - fabricated quote
- [⚠] V1:L4: "waiting by the phone" - speculative action
- [✓] Dates and facts match RESEARCH.md
```

---

## 8. Factual Check (Conditional)

**When to apply**: Only if RESEARCH.md exists in album directory

**What to scan:**
- Names spelled correctly
- Dates match sources
- Numbers/amounts accurate
- Events in correct order
- Key facts verified

**How to check:**
- Cross-reference lyrics against RESEARCH.md

**Severity:**
- **Critical**: Wrong date/name/major fact
- **Warning**: Minor discrepancy
- **Info**: Could be clearer

**Output format:**
```
### Factual Check
- [✗] CRITICAL: V1 says "1943" but RESEARCH.md says "1942"
- [⚠] Bridge: "seventeen convicted" - actually 17 of 22, context unclear
- [✓] Names: All match sources
```

---

## 9. Length Check

**What to scan:**
- Total word count (count all lyrics excluding section tags)
- Number of verses
- Whether user explicitly requested extra verses

**Genre targets:**

| Genre | Target Words | Max Verses |
|-------|-------------|------------|
| Pop / Dance-Pop / Synth-Pop | 150–250 | 2 |
| Punk / Pop-Punk | 150–250 | 2 |
| Rock / Alt-Rock | 200–350 | 2–3 |
| Folk / Country / Americana | 200–350 | 2–3 |
| Hip-Hop / Rap | 300–500 | 2–3 |
| Ballad (any genre) | 200–300 | 2–3 |

**Severity:**
- **Critical**: Over 500 words (non-hip-hop) or over 700 words (hip-hop) — Suno will rush or skip content
- **Warning**: Over genre target range
- **Warning**: More than 3 verses without explicit user request
- **Info**: At upper end of range, could trim

**Output format:**
```
### Length Check
- [✗] CRITICAL: 720 words (pop) - far over 150-250 target, Suno will skip sections
- [✗] V1, V2, V3, V4 - 4 verses, user did not request extra
- [⚠] 360 words (rock) - slightly over 200-350 target
- [✓] 280 words (folk) - within 200-350 range
```

---

## 10. Section Length Check

**What to scan:**
- Count lines per section (verse, chorus, bridge, etc.)
- Compare against genre limits from lyric-writer Section Length Limits table

**Severity:**
- **Hard fail**: Any section exceeding its genre max must be flagged for trimming

**Output format:**
```
### Section Length Check
- [✗] V2: 10 lines (rock max = 8) - trim 2 lines
- [✓] Chorus: 4 lines (within limit)
```

---

## 11. Rhyme Scheme Check

**What to scan:**
- Verify rhyme scheme matches the genre (see lyric-writer Default Rhyme Schemes by Genre)
- No orphan lines (unrhymed lines in a rhyming section)
- No random scheme switches mid-verse

**Severity:**
- **Warning**: Inconsistent scheme within a section, orphan unrhymed line

**Output format:**
```
### Rhyme Scheme Check
- [✗] V1: ABAB expected (rock) but L3 doesn't rhyme with L1
- [⚠] Bridge: Orphan line L2 has no rhyme partner
- [✓] Chorus: AABB scheme consistent
```

---

## 12. Density/Pacing Check

**What to scan:**
- Verse line count vs genre README's `Density/pacing (Suno)` default
- Cross-reference BPM/mood from Musical Direction

**Severity:**
- **Hard fail**: Any verse exceeding the genre's max line count

**Output format:**
```
### Density/Pacing Check
- [✗] V2: 12 lines at 140 BPM - too dense, Suno will rush
- [✓] V1: 6 lines at 140 BPM - appropriate density
```

---

## 13. Verse-Chorus Echo Check

**What to scan:**
- Compare last 2 lines of every verse against first 2 lines of the following chorus
- Flag exact phrases, shared rhyme words, restated hooks, or shared signature imagery
- Check ALL verse-to-chorus and bridge-to-chorus transitions

**Severity:**
- **Warning**: Shared phrases or rhyme words bleeding across section boundaries

**Output format:**
```
### Verse-Chorus Echo Check
- [⚠] V1→Chorus: "burning down" appears in V1:L4 and Chorus:L1
- [⚠] V2→Chorus: V2:L4 rhyme word "night" echoes Chorus:L2 "light"
- [✓] Bridge→Chorus: No echo
```

---

## 14. Artist Name Check

**What to scan:**
- Scan lyrics AND style prompt for real artist/band names
- Cross-reference against `${CLAUDE_PLUGIN_ROOT}/reference/suno/artist-blocklist.md`

**Severity:**
- **Critical**: Any artist name in the style prompt will cause Suno to fail or produce unexpected results
- **Fix**: Replace with genre/style description from the blocklist's "Say Instead" column

**Output format:**
```
### Artist Name Check
- [✗] CRITICAL: "Nirvana" in Style Box - replace with "90s grunge, distorted guitars"
- [✓] Lyrics: No artist names found
```

---

## Severity Definitions Summary

| Level | Definition | Action Required |
|-------|------------|-----------------|
| **Critical** | Will cause Suno problems or legal risk | Must fix before generation |
| **Warning** | Quality issue, impacts song | Should fix, can proceed with caution |
| **Info** | Nitpick, optional improvement | Nice to have, not blocking |
