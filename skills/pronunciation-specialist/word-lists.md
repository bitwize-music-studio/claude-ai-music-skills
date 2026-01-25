# Pronunciation Word Lists

Reference tables for pronunciation fixes in Suno lyrics.

---

## Category 1: Homographs (Critical)

Words spelled identically but pronounced differently based on meaning:

| Word | Meaning A | Meaning B | FIX |
|------|-----------|-----------|-----|
| live | LYVE (alive, verb) | LIV (performance, adj) | ALWAYS clarify |
| read | REED (present) | RED (past) | Use "red" for past |
| lead | LEED (guide) | LED (metal) | Use "led" for metal |
| wind | WIND (air) | WYNED (coil) | Use "wyned" for coil |
| close | KLOHS (near) | KLOHZ (shut) | Use "clohz" for shut |
| tear | TEER (cry) | TARE (rip) | Use "tare" for rip |
| bass | BAYSS (music) | BASS (fish) | Use "bass" for fish |
| wound | WOOND (injury) | WOWND (coiled) | Use "wownd" for coil |
| bow | BOH (ribbon) | BOW (bend) | Use "bow" for bend |
| minute | MIN-it (time) | my-NOOT (tiny) | Use "my-noot" for tiny |
| desert | DEZ-ert (sand) | dih-ZERT (abandon) | Use "dih-zert" for abandon |
| object | OB-ject (thing) | ob-JECT (protest) | Use "ob-ject" for protest |
| present | PREZ-ent (gift) | prih-ZENT (give) | Use "prih-zent" for give |
| record | REK-ord (disc) | rih-KORD (capture) | Use "rih-kord" for capture |
| refuse | REF-yoos (garbage) | rih-FYOOZ (decline) | Use "rih-fyooz" for decline |

---

## Category 2: Tech Terms

| Term | Wrong | Right | Phonetic |
|------|-------|-------|----------|
| Linux | "LINE-ucks" | "LIN-ucks" | Lin-ucks |
| SQL | "squeal" | "S-Q-L" or "sequel" | S-Q-L or sequel |
| GUI | "gooey" (usually correct) | "gooey" | gooey |
| API | "A-P-I" | "A-P-I" | A-P-I |
| CLI | "C-L-I" | "C-L-I" | C-L-I |
| IPv4/IPv6 | varies | "I-P-V-4" | I-P-V-4 |
| macOS | "mack-oh-ess" | "mack-oh-ess" | mack-oh-ess |
| iOS | "eye-oh-ess" | "eye-oh-ess" | eye-oh-ess |
| SSH | "S-S-H" | "S-S-H" | S-S-H |
| DNS | "D-N-S" | "D-N-S" | D-N-S |
| VPN | "V-P-N" | "V-P-N" | V-P-N |
| AI | "A-I" or "ay-eye" | User preference | A-I or ay-eye |
| GPU | "G-P-U" | "G-P-U" | G-P-U |
| CPU | "C-P-U" | "C-P-U" | C-P-U |
| RAM | "ram" | Clear | ram |
| ROM | "rom" | Clear | rom |
| USB | "U-S-B" | "U-S-B" | U-S-B |

---

## Category 3: Names & Proper Nouns

| Name | Common Error | Phonetic |
|------|--------------|----------|
| Ramos | "RAM-ohs" | Rah-mohs |
| Sinaloa | "sin-uh-LOW-uh" | Sin-ah-lo-ah |
| Kiev | "KEE-ev" vs "KYE-ev" | Kee-ev or Kye-ev |
| Qatar | "kuh-TAR" vs "KAT-ar" | Kuh-tar |
| Nguyen | "NEW-win" (wrong) | Win or Nwin |
| Zhang | "ZANG" (wrong) | Jahng |
| Jose | "joe-SAY" | Ho-zay |
| Maria | "muh-REE-uh" | Mah-ree-ah |
| Mikhail | "mih-KYLE" | Mee-kah-eel |
| Bjork | "bee-YORK" | Bee-york |

---

## Category 4: Acronyms & Initialisms

| Acronym | Say As | Phonetic |
|---------|--------|----------|
| FBI | Individual letters | F-B-I |
| CIA | Individual letters | C-I-A |
| NSA | Individual letters | N-S-A |
| NASA | Word | Nah-sah |
| SCUBA | Word | Scoo-bah |
| RICO | Word | Ree-koh |
| GPS | Individual letters | G-P-S |
| ATM | Individual letters | A-T-M |
| CEO | Individual letters | C-E-O |
| LLC | Individual letters | L-L-C |
| PhD | Individual letters | P-H-D |
| HTML | Individual letters | H-T-M-L |
| CSS | Individual letters | C-S-S |
| PDF | Individual letters | P-D-F |

**Rule**: 3 letters = spell out with hyphens, unless commonly pronounced as word (NASA, SCUBA).

---

## Category 5: Numbers

| Written | Suno Might Say | Better |
|---------|---------------|---------|
| 1993 | "one nine nine three" | "nineteen ninety-three" or "'93" |
| 2024 | "two zero two four" | "twenty twenty-four" |
| 63 | "six three" | "sixty-three" |
| 404 | "four zero four" | "four-oh-four" |
| 9/11 | "nine slash eleven" | "nine-eleven" or "September eleventh" |

---

## Category 6: Commonly Mispronounced Words

| Word | Wrong Stress | Right Stress | Fix |
|------|--------------|--------------|-----|
| legal | "leh-GAL" | LEE-gul | lee-gul |
| illegal | "ILL-ih-gul" | ill-EE-gul | ill-ee-gul |
| data | varies | User preference | day-tuh or dah-tuh |
| either | varies | User preference | ee-ther or eye-ther |
| neither | varies | User preference | nee-ther or nye-ther |
| route | varies | User preference | root or rowt |
| schedule | varies | User preference | sked-yool or shed-yool |

---

## Scanning Regex Patterns

```
High-risk patterns:
- \blive\b (homograph)
- \bread\b (homograph)
- \blead\b (homograph)
- \bSQL\b (tech term)
- \bLinux\b (tech term)
- [A-Z]{2,5} (potential acronyms)
- \d{4} (years like 1993, 2024)
- \d{2,3} (numbers like 63, 404)
```
