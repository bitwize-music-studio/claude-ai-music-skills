# Suno AI Music Creation — 100 Words of Advice

A compilation of hard-won wisdom from artists, producers, sound designers, and video makers who work in Suno every day. Distilled into 100 tips, tricks, hacks, workflows, blueprints, and templates. For fun or for profit.

Companion to [v5-best-practices.md](v5-best-practices.md) (the how) and [tips-and-tricks.md](tips-and-tricks.md) (the troubleshooting). This doc is the *why* and the *craft*.

---

## I. Mindset & Workflow (1–10)

**1. Suno is a session musician, not a vending machine.** Brief it the way you'd brief a player: genre, feel, tempo, reference era, what to leave out. Vague briefs get generic takes.

**2. Generate in batches of 4–6, never 1.** Suno is non-deterministic. One generation tells you nothing about the prompt. Five tell you whether the prompt or the dice are the problem.

**3. Keep a prompt journal.** A plain text file with date, Style Box, sliders, and a one-line verdict. Every keeper prompt becomes a reusable template. Every failure becomes a lesson you don't repeat.

**4. Decide the song's job before you type.** Background for a video? Club banger? Lullaby? The job dictates length, dynamics, vocal density, and how much ear-candy you need.

**5. Write the hook first.** If you can't hum the chorus after writing it, Suno won't make it memorable either. The model amplifies what's there; it doesn't invent a hook you didn't write.

**6. Change one variable per iteration.** Style Box OR lyrics OR sliders. Change all three and you learn nothing from the result.

**7. Listen on three systems before you keep anything.** Phone speaker, earbuds, monitors or car. Suno mixes can sound huge on headphones and hollow on a phone.

**8. Name your files like a producer.** `songslug_v03_takeB_vocal-warm.mp3` beats `Untitled (14).mp3` when you're picking a keeper two weeks later.

**9. Set a kill limit.** If a concept isn't landing after 12–15 generations, the concept is wrong, not the luck. Rewrite the brief or bench the song.

**10. Finish songs.** A hundred 80-percent drafts teach less than ten released tracks. Shipping exposes what actually mattered.

---

## II. The Style Box — Prompt Craft (11–22)

**11. Lead with genre, then vocal, then mood, then production.** Suno weights early words more heavily. `Dark synthwave, female alto vocal, melancholic, analog warmth, 100 BPM` reads in the right priority order.

**12. Two or three genres max.** `Country trap jazz fusion` is a coin flip. Pick a primary genre and one modifier: `Country, trap-influenced drums`.

**13. Describe the sound, not the artist.** Named artists are blocked and get silently dropped, taking your intent with them. See [artist-blocklist.md](artist-blocklist.md). Say what they *sound like* instead (tip 41).

**14. Use production language.** `Tape saturation, wide stereo, dry vocal, punchy compressed drums` moves the needle more than `good quality, professional`.

**15. Specify tempo as a number.** `128 BPM` is unambiguous. `Fast` means something different in doom metal and drum and bass.

**16. Era anchors beat adjectives.** `1994 boom bap` or `late-70s AOR` conjures instrumentation, mix style, and vocal delivery in one stroke.

**17. Name the instruments you want to hear.** Suno defaults to genre clichés. `Fretless bass, Rhodes, brushed snare` steers away from them. See [instrumental-tags.md](instrumental-tags.md).

**18. Say what you don't want.** Use the negative/exclude field. `no autotune, no EDM drop, no rap verse` prevents the most common hijacks.

**19. Under 200 characters is a sweet spot.** Long Style Boxes dilute. If you need a paragraph, you're probably describing two songs.

**20. Punctuation is structure.** Commas separate descriptors. Periods signal a new thought. Avoid semicolons, slashes, and quotes, which the parser handles inconsistently.

**21. Keep a "house sound" suffix.** Ten to fifteen words you append to every prompt for a project: `warm analog mix, slight vinyl crackle, intimate vocal, no reverb wash`. This is how albums sound like albums.

**22. Test prompts as instrumentals first.** Toggle instrumental on. If the bed sounds right without vocals, you've validated the Style Box independently of lyric problems.

---

## III. Lyrics & Structure (23–36)

**23. Every section gets a structure tag.** `[Intro]`, `[Verse]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Outro]`. Untagged blocks get treated as verses. See [structure-tags.md](structure-tags.md).

**24. Chorus in the first 45 seconds.** Streaming skips happen before the minute mark. Intro of four bars, one short verse, chorus. Save the long intro for the album cut.

**25. Write to a syllable budget.** Roughly 8–12 syllables per line for mid-tempo pop, 12–16 for rap, 6–8 for ballads. Overstuffed lines get rushed or dropped.

**26. Make every verse different.** Twin verses (same shape, same images) are the number one sign of AI-written lyrics. Verse two should advance time, perspective, or stakes.

**27. Repeat the chorus verbatim.** Suno sings the exact text. Small variations between choruses produce different melodies, and the song loses its anchor.

**28. Use parentheses for backing vocals.** `Take me home (take me home)` produces a call-and-response layer. Overuse it and everything becomes a gang chant.

**29. Ellipses and line breaks control phrasing.** A line break is a breath. `...` is a held note or pause. Commas mid-line barely register.

**30. Stack short lines for urgency, long lines for reflection.** Line length shapes melody. Four-word lines feel punchy. Fourteen-word lines meander.

**31. End sections on strong stressed syllables.** Lines ending on `the`, `of`, `and` get swallowed. End on nouns and verbs.

**32. Put the title in the chorus at least twice.** Listeners remember what to search for. So does the algorithm.

**33. A bridge is a change of key, view, or truth.** If the bridge just says the chorus with different words, cut it and go to a final chorus with a lift.

**34. `[Instrumental Break]` beats `[Solo]`.** `[Solo]` often produces noodling. Name the instrument: `[Guitar Solo]`, `[Saxophone Break]`.

**35. Control the ending.** `[Outro]` plus `[Fade Out]` or `[End]` on the final line. Without it, Suno rambles or cuts mid-phrase.

**36. Read the lyrics aloud with a metronome.** If you stumble, Suno stumbles. Fix the prosody on paper before spending credits.

---

## IV. Vocals & Pronunciation (37–46)

**37. One vocal descriptor cluster, placed early.** `Breathy female mezzo, close-mic, slight rasp` in the Style Box. Piling on six adjectives produces mush. See [voice-tags.md](voice-tags.md).

**38. Age and grit need reinforcement.** `Mature` alone reads young. Combine `weathered, gravel, lived-in, 50s male baritone` and, if needed, escalate to inline metatags in the lyrics.

**39. Suno cannot read context for homographs.** `Live`, `read`, `wind`, `tear`, `bass`, `lead`. Respell phonetically in the Suno lyrics only: `wynd` for the noun, `reed` for the present tense. See [pronunciation-guide.md](pronunciation-guide.md).

**40. Spell brand names and acronyms as sounds.** `A.P.I.` becomes `ay pee eye`. `Kubernetes` becomes `koo-ber-NET-eez`. Keep clean spellings in your published lyric sheet.

**41. Hyphenate for stress.** `re-COR-ded` forces the emphasis you want. Use sparingly; it's a scalpel.

**42. All caps means shouted.** Suno reads capitalization as intensity. Use it for one line, not a verse.

**43. Duets need explicit handoffs.** `[Verse 1: Male vocal]` / `[Verse 2: Female vocal]` / `[Chorus: Both, harmony]`. Without labels you get one singer.

**44. Whisper and spoken tags work when paired with dynamics.** `[Whispered, intimate]` at the start of a verse, then `[Full voice]` at the pre-chorus. Contrast is what sells it.

**45. If the vocal disappears, the intro is too long.** Cut `[Intro]` instrumentation descriptors or add `[Vocals enter immediately]` as the first line.

**46. Ad-libs go in brackets at line end.** `Running out of time [yeah]`. Keep them to the second half of the song where energy peaks.

---

## V. Distilling an Artist's Sound (47–54)

**47. Reverse-engineer in five dimensions.** Instrumentation, vocal character, rhythm feel, production era, lyrical stance. Fill all five and you have a description that beats a name.

**48. Sound Blueprint template:**
```
[genre] + [subgenre modifier], [vocal: gender, range, texture, delivery],
[rhythm: tempo, feel, drum sound], [key instruments x3],
[production: era, mix width, effects], [mood: 2 words]
```
Example: `Indie folk, chamber-pop touches, soft male tenor with cracked falsetto, 78 BPM brushed kit, nylon guitar, upright piano, string quartet, 2008 lo-fi warmth, wide reverb, wistful and tender`.

**49. Borrow the drums, not the melody.** Rhythm section descriptions carry the most identity with the least legal and ethical baggage.

**50. Describe the room.** `Recorded in a wooden church`, `dead vocal booth`, `stadium echo`. Space is half of what makes a sound recognizable.

**51. Use the reference era's gear.** `Juno-106 pads, LinnDrum, gated reverb` says 1984 without saying a name.

**52. Vocal texture words are your strongest lever.** Nasal, chesty, airy, smoky, glassy, throaty, sibilant, boyish, matronly. Pick two.

**53. Build a Persona from your best take, then iterate around it.** Personas lock vocal identity across an album. Generate the definitive vocal first, save it, then write the other songs to it.

**54. Blend two blueprints for something new.** Take the rhythm block from one and the vocal block from another. That's where original sounds live and where you stop chasing imitation.

---

## VI. Sliders, Personas, Covers & the Editor (55–66)

**55. Style Influence high, Weirdness low for commercial work.** Start around 70/20. Push Weirdness up only when the results are boring, not when they're wrong.

**56. Weirdness above 60 is an experimental tool.** Expect tempo shifts, odd instrumentation, and structure drift. Great for noise and ambient. Terrible for a wedding song. See [creative-sliders.md](creative-sliders.md).

**57. Audio Influence works best between 30 and 60.** Below that, your upload is ignored. Above it, you get a near-copy with artifacts.

**58. Upload a hummed melody, not a full demo.** A clean vocal or a single instrument gives the model a spine without confusing it with your bad mix.

**59. Cover mode is a re-arrangement tool.** Generate the song once, then cover it into three genres. The one that surprises you is often the release.

**60. Extend from a specific timestamp, not the end.** Trim the tail to the last good bar, then extend. You avoid building on a weak ending.

**61. Crop before extend, extend before replace.** Get the skeleton right, then use Replace Section to surgically fix a bad line or a flubbed word.

**62. Replace Section with identical lyrics to fix pronunciation.** Keep the text, only respell the problem word. The surrounding audio stays intact.

**63. Personas need 4+ strong references.** Build one from several keeper generations with the same vocal, not from a single lucky take.

**64. Seed ideas with short generations.** A 30-second instrumental test costs less and tells you whether the palette is right before you commit to full lyrics.

**65. Regenerate the section, not the song.** When 90 percent is right, editing tools cost fewer credits and preserve the magic of the take you already love.

**66. Save keepers to a workspace immediately.** Liked tracks get buried under new generations within a day. See [workspace-management.md](workspace-management.md).

---

## VII. Spoken Word, Poetry & Experimental Noise (67–78)

**67. Tag spoken word explicitly.** `[Spoken word]` at the section head and `spoken word, no singing, poetry reading` in the Style Box. Otherwise the model tries to sing your poem.

**68. Give spoken word a bed.** `Sparse ambient piano, field recordings, distant traffic` keeps it from feeling like a phone memo.

**69. Punctuation is the performance.** Periods stop. Line breaks breathe. Em-dashes hold. Write the delivery into the layout.

**70. Keep spoken lines under ten words.** Long sentences get rushed. Break thoughts across lines like a poem, not a paragraph.

**71. Mix one sung refrain into a spoken piece.** A four-line sung chorus between spoken verses gives listeners an anchor and makes the piece playlist-friendly.

**72. For noise, describe textures and processes.** `Granular synthesis, feedback loops, contact mic on metal, bit-crushed, tape stop`. Genre names for noise are too broad.

**73. Push Weirdness to 80+ and Style Influence to 30 for noise.** You want the model off-balance. Low style adherence lets textures collide.

**74. Use sound-word lyrics for rhythmic noise.** Onomatopoeia like `tk tk tsss`, `brrrap`, `hush hush` produces percussive vocal textures the model treats as instruments.

**75. Structure tags still work in noise pieces.** `[Build]`, `[Collapse]`, `[Drone]`, `[Silence]`, `[Rupture]`. Custom tags in brackets steer dynamics even outside song form.

**76. Generate short, then stitch.** Noise and ambient benefit from generating 30–60 second cells and assembling them in a DAW. You get control the model won't give you.

**77. Field recordings via Audio Influence.** Upload rain, a train, a crowd. Set influence around 40. The model builds harmonic material on top of real-world texture.

**78. ASMR, meditation, and sleep tracks are a real market.** `Whispered, ASMR, no music, soft background hum, slow` with lyrics that are gentle instructions. Long-form, low competition, steady streams.

---

## VIII. Post-Production & Mastering (79–86)

**79. Suno output is not mastered.** Expect around -14 to -12 LUFS with a soft top end. Every release needs at least a limiter pass. See [v5-best-practices.md](v5-best-practices.md#suno-output-loudness-pre-mastering).

**80. Download WAV, not MP3.** Master from the highest quality source available. MP3 artifacts compound at every step.

**81. Stem-split before you polish.** Separate vocals, drums, bass, and other. Fix the vocal's harshness without dulling the cymbals.

**82. High-pass everything except bass and kick.** Suno mixes carry low-end mud below 80 Hz on pads and vocals. Cut it and the mix opens up.

**83. Tame the 2–5 kHz shelf on vocals.** Suno vocals often have a sizzle that fatigues at volume. A gentle dynamic EQ cut fixes it without losing presence.

**84. Check mono compatibility.** Wide Suno stereo can cancel on phone speakers. Fold to mono and confirm the vocal and kick survive.

**85. Target -14 LUFS for streaming, -9 to -8 for club and video.** Different destinations, different masters. Don't upload the club master to Spotify.

**86. Master the album as a set.** Match tonal balance and loudness across tracks so the listener isn't reaching for the volume knob. Reference-track matching to your best song works well.

---

## IX. The AI Music Video Process (87–94)

**87. Step 1: Lock the audio first.** Never storyboard to a draft. Video timing, lyric sync, and cuts all depend on the final master.

**88. Step 2: Write a shot list from the lyrics.** One visual idea per section. Verse one: a room. Chorus: the open road. Bridge: close-up hands. This is your prompt map for the image and video models.

**89. Step 3: Build a visual bible.** Three to five reference images, a color palette, a lens choice, a time of day. Every image prompt inherits this block, the same way a Style Box suffix keeps an album coherent.

**90. Step 4: Generate stills before motion.** Image models are cheaper and faster. Approve the look in stills, then animate only the winners with an image-to-video model.

**91. Step 5: Cut on the beat, but not every beat.** Cut on the downbeat of each new section and on chorus entrances. Cutting every bar reads as a slideshow.

**92. Step 6: Sync lyrics with a transcript.** Run the master through a transcription tool to get word timestamps, then place lyric overlays or lip-synced characters against them.

**93. Step 7: Motion loops for budget videos.** Four to six looping 5-second clips, alternated and speed-ramped, carry a three-minute song convincingly. Save the expensive generations for the chorus.

**94. Step 8: Export vertical and horizontal.** 9:16 for Shorts, Reels, TikTok. 16:9 for YouTube. Frame the visual bible with both crops in mind from step 3.

---

## X. Rights, Release & Profit (95–100)

**95. Know your plan's license.** Free-tier output is non-commercial. Paid plans grant commercial rights to what you generate on them. Check the current terms before releasing; they've changed more than once.

**96. Register your songs.** Writers of lyrics and arrangement decisions have a claim. Register with a PRO and use a distributor that accepts AI-assisted work and disclose per their policy.

**97. Disclose honestly.** Platforms and listeners are increasingly hostile to hidden AI. Owning it in your bio builds an audience; getting caught loses one.

**98. Build catalogs, not singles.** Ambient, lo-fi, sleep, focus, and workout playlists reward volume and consistency. Twenty coherent tracks under one project name beat one great song.

**99. Sync and stock are the quiet money.** Instrumental beds for creators, podcasts, and ads. Deliver stems, multiple lengths (15s, 30s, 60s, full), and clean loop points.

**100. Your taste is the product.** Anyone can prompt. What sells is knowing which of the six generations is the one, and why. Spend as much time listening critically as you spend generating.

---

## Templates

### Style Box starter
```
[Primary genre], [modifier], [vocal descriptor cluster], [BPM] BPM,
[3 key instruments], [production era + mix character], [2 mood words]
```

### Lyric skeleton (radio edit, ~3:00)
```
[Intro]
(4 bars, one spoken or sung line optional)

[Verse 1]
(4–8 lines, establish scene)

[Pre-Chorus]
(2–4 lines, build)

[Chorus]
(4 lines, title twice)

[Verse 2]
(4–8 lines, change time/perspective)

[Pre-Chorus]

[Chorus]

[Bridge]
(4 lines, new truth)

[Chorus]
(final, with lift)

[Outro]
[End]
```

### Prompt journal row
```
| date | slug | style box | sliders (SI/W/AI) | take | verdict |
```

### Music video shot list row
```
| section | timestamp | visual idea | image prompt | motion prompt | status |
```

---

## V6 Addendum (launched September 9, 2026)

Suno V6 shipped the day before this doc was written, so the community consensus is thin. What is confirmed from Suno's own launch notes and early coverage:

- **Three models, pick on purpose.** `v6` is the precise, reliable flagship (Pro and Premier). `v6-wild` is deliberately less predictable and more textured, built for exploration. `v6-mini` is the faster free-tier model. Draft in wild, then bring the idea back into v6 for the keeper.
- **Single-lyric edits are real now.** You can change one word or one line by natural-language prompt without regenerating the track. This replaces most Replace Section workarounds in tips 61 and 62.
- **Advanced Mode controls.** Vocal Gender, Duration (Custom or Auto), Max Mode on/off, and three sliders: Weirdness and Style Influence both default to 50, plus a new Variety slider defaulting to Normal. Treat Variety as your batch-diversity knob (tip 2).
- **Personas did not go away.** They moved into a larger identity system alongside Voices, Lyricist, Custom Models, and My Taste. Tips 53 and 63 still apply.
- **Photos, video, and voice memos as input.** V6 accepts media as a seed, which extends tip 58 beyond audio uploads.
- **Early community advice is the same as V5.5.** Shorter Style Box, concrete instrument names over adjectives, tempo as a number, one variable per iteration, and the Exclude field to stop unrequested guitar solos and EDM drops. The word `Duet` must appear in the Style Box itself for two-voice tracks.

Revisit this section after a few weeks of r/SunoAI threads. Model-specific quirks usually surface in the first month.

---

## See Also

- [v5-best-practices.md](v5-best-practices.md) — full prompting guide
- [tips-and-tricks.md](tips-and-tricks.md) — troubleshooting
- [creative-sliders.md](creative-sliders.md) — slider deep dive
- [pronunciation-guide.md](pronunciation-guide.md) — homographs and phonetic fixes
- [artist-blocklist.md](artist-blocklist.md) — why named artists fail
