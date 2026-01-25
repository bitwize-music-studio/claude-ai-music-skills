# 8-Point Checklist Reference

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

## Severity Definitions Summary

| Level | Definition | Action Required |
|-------|------------|-----------------|
| **Critical** | Will cause Suno problems or legal risk | Must fix before generation |
| **Warning** | Quality issue, impacts song | Should fix, can proceed with caution |
| **Info** | Nitpick, optional improvement | Nice to have, not blocking |
