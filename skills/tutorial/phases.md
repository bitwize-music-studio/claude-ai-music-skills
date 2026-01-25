# The 7 Planning Phases

Reference for the tutorial skill. Work through these phases with the user before writing any lyrics.

---

## Phase 1: Foundation

**The basics that determine everything else.**

Questions to answer:
- Who is the artist? (Existing or new?)
- What genre(s)? (Primary category: hip-hop, electronic, country, folk, rock)
- What album type? (Documentary, Narrative, Thematic, Character Study, Collection)
- How many tracks? (Full album ~10-15, EP ~4-6, Single)
- Is this true-story/documentary? (Determines research requirements)

**Why it matters:** These answers shape the entire project. Genre determines folder structure. Album type determines workflow (documentary needs research). Track count sets scope.

**Tutorial tip:** Create album directory after this phase completes (once you know artist/genre/album name).

---

## Phase 2: Concept Deep Dive

**The heart of the album - what it's really about.**

Questions to answer:
- What's the central story/theme/message?
- Who are the key characters or subjects?
- What's the narrative arc or thematic journey?
- What's the emotional core?
- Why this story? (For artist, for audience)

**Why it matters:** This is the "why" behind the music. A clear concept makes every other decision easier. A fuzzy concept leads to a scattered album.

**Tutorial tip:** If user can't articulate the emotional core, dig deeper. "What do you want listeners to feel?" "What's the one thing this album needs to say?"

---

## Phase 3: Sonic Direction

**How should it sound?**

Questions to answer:
- What artists/albums inspire this sound?
- Production style? (Dark/bright, minimal/dense, organic/synthetic)
- Vocal approach? (Narrator, character voices, sung, rapped, mixed)
- Instrumentation palette?
- Mood/atmosphere?

**Why it matters:** This guides Suno prompts and ensures sonic coherence across tracks. Reference artists are shorthand for complex sonic ideas.

**Tutorial tip:** Don't get too detailed here - broad strokes. Detailed prompts come when writing tracks with `/suno-engineer`.

---

## Phase 4: Structure Planning

**The tracklist architecture.**

Questions to answer:
- Tracklist outline (titles or working titles)
- Track-by-track concepts (1-2 sentences each)
- Narrative/thematic flow across tracks
- Which tracks are pivotal?
- Pacing (building, episodic, consistent intensity)?

**Why it matters:** Track order can make or break an album. This is where the journey takes shape.

**Key positions:**
- Track 1: The opener - immediate impact, sets expectations
- Tracks 5-7: The heart - most important thematic statement
- Final track: The closer - emotional payoff, resolution

**Tutorial tip:** Working titles are fine. Help them identify the "heart" track and the closer. Use `/album-conceptualizer` for deep tracklist work.

---

## Phase 5: Album Art

**Visual concept (generation happens later).**

Questions to discuss:
- What imagery represents the album?
- Color palette?
- Mood/aesthetic?
- Any symbolic elements?

**Why it matters:** Album art is the visual first impression. It should match and reinforce the sonic/thematic concept.

**Tutorial tip:** Keep this brief during planning. Just capture the visual mood. Actual generation happens after tracks are written, using `/album-art-director`.

---

## Phase 6: Practical Details

**The logistics.**

Questions to confirm:
- Album title finalized?
- Track titles finalized (or willing to adjust)?
- Research needs? (Documentary albums: RESEARCH.md, SOURCES.md)
- Explicit content expected?
- Distributor genre categories?

**Why it matters:** These details affect files, metadata, and workflow. Better to know now than discover mid-project.

**Tutorial tip:** "Flexible" is a valid answer for titles. Flag explicit content early - it affects distributor choices and flags.

---

## Phase 7: Confirmation

**Final check before writing.**

Required steps:
- Present complete plan to user
- Get explicit go-ahead: "Ready to start writing?"
- Document all answers in album README

**Why it matters:** This is the checkpoint. User should understand and approve the plan before any lyrics get written.

**Tutorial tip:** Present a clean summary. If they hesitate, ask what needs adjustment. Once confirmed, create track files and begin.

---

## Planning Checklist

Before creating any track files:
- [ ] All 7 phases completed with explicit answers
- [ ] User confirmed: "Ready to start writing"
- [ ] Album README created with all planning details documented
- [ ] Research plan established (if true-story album)

**The rule:** No track writing until all phases complete and user confirms.

---

## Album Types Quick Reference

| Type | Definition | Key Considerations |
|------|------------|-------------------|
| **Documentary** | Real events, factual storytelling | Requires RESEARCH.md, SOURCES.md, source verification |
| **Narrative** | Fictional story across tracks | Protagonist, conflict, arc, resolution |
| **Thematic** | United by theme, not plot | Sub-themes, emotional journey, motifs |
| **Character Study** | Deep dive into a person | Aspects, time periods, through-line |
| **Collection** | Standalone songs, loose connection | Unifying element, flow, variety |
