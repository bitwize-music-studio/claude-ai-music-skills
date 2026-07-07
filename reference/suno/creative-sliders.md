# Suno Creative Sliders Reference

Deep-dive guide to Suno V5's three Creative Sliders — **Weirdness**, **Style Influence**, and **Audio Influence** — including per-slider behavior, genre starting points, interaction effects, and when to reach for a slider vs. rewrite the style prompt.

> **Related skills**: `/bitwize-music:suno-engineer` (constructs prompts and picks slider settings)
> **Related docs**: [v5-best-practices.md](v5-best-practices.md#creative-sliders) (this file expands the brief Creative Sliders table there), [tips-and-tricks.md](tips-and-tricks.md), [genre-list.md](genre-list.md)

---

## What the Sliders Do

The sliders live in the V5 generation interface and sit *on top of* your style prompt. They don't change **what** Suno makes — the prompt does that. They change **how hard Suno commits to the prompt** and **how far it's allowed to wander**.

- **Weirdness** — how experimental vs. predictable the result is.
- **Style Influence** — how tightly the output hugs your style prompt.
- **Audio Influence** — how much a piece of uploaded reference audio shapes the output (only appears when you provide reference audio).

Throughout this guide, slider positions are given on a **0.00–1.00 scale** — the same range the API exposes for `styleWeight` and `weirdnessConstraint` (see the [README API table](README.md#api-parameters)). If your interface shows a 0–100 scale instead, read `0.70` as `70`. **These bands are starting-point recommendations from this guide, not Suno-official defaults** — start at the defaults, generate once, then dial them in by ear.

---

## Weirdness

Controls how experimental and unexpected Suno's choices are — melody, harmony, arrangement quirks, structural surprises.

| Position | Behavior |
|----------|----------|
| **Low** (`0.00–0.30`) | Predictable, hooky, familiar. Strong, singable choices; conventional song shapes. The safe zone for radio-style results. |
| **Mid** (`0.30–0.55`) | Balanced. Mostly conventional with occasional pleasant surprises. |
| **High** (`0.55–1.00`) | Experimental and unexpected. Odd chord moves, unusual textures, less predictable structure. Rewarding for exploration, but drift and misfires increase. |

**Raise it** when the output is too safe or generic and you want the AI to surprise you. **Lower it** when you need a dependable hook and clean, conventional structure.

**Note**: High Weirdness increases variance between generations — expect to generate more takes and cherry-pick.

---

## Style Influence

Controls how tightly the output adheres to your style prompt — genre hallmarks, named instruments, mood words.

| Position | Behavior |
|----------|----------|
| **Low** (`0.00–0.40`) | Loose. Suno treats the prompt as a suggestion, blends influences freely, fills gaps its own way. Good for fusions and happy accidents. |
| **Mid** (`0.40–0.60`) | Balanced adherence. Honors the prompt while leaving room to breathe. |
| **High** (`0.60–1.00`) | Tight. Strong genre purity; the prompt's tags are enforced hard. Best when the genre must be unmistakable. |

**Raise it** for genre purity — when the result is drifting off-genre or ignoring your tags. **Lower it** when you want the AI to surprise you, blend styles, or when a dominant Persona is over-processing the mix (per [tips-and-tricks.md](tips-and-tricks.md#personas-for-vocal-consistency), lowering Style Influence can rebalance an overpowering Persona).

**Caution**: Very high Style Influence on a thin or contradictory prompt can produce a rigid, wooden result — the engine is enforcing tags that fight each other. If that happens, fix the prompt before pushing the slider higher (see [Sliders vs. Style Prompt](#sliders-vs-style-prompt)).

---

## Audio Influence

Controls how much a piece of **uploaded reference audio** shapes the output. This slider **appears only when audio is uploaded** — via Cover, Upload Audio, Sample to Song, or **Voices**. With no reference audio, it isn't shown.

| Position | Behavior |
|----------|----------|
| **Low** (`0.00–0.40`) | The upload is a loose seed. Your prompt and style lead; the reference just nudges. |
| **Mid** (`0.40–0.65`) | Balanced — the output carries the reference's character while following the prompt. |
| **High** (`0.65–1.00`) | The output hews closely to the uploaded audio's melody, feel, and arrangement. Safest for faithful covers and cross-track consistency. |

**Raise it** when a cover or reworked upload isn't resembling the source enough. **Lower it** when you want more transformation and less of the original bleeding through.

**With Voices (voice cloning):** keep Audio Influence **fairly high (~0.70–0.85)** so the result resembles the cloned voice — too low and Suno drifts toward a generic vocal. See [Voices & Custom Models](v5-best-practices.md#voices--custom-models).

---

## Recommended Starting Ranges by Genre

Starting points only — generate, listen, then adjust. Weirdness and Style Influence are always available; Audio Influence applies only to upload/cover workflows. See [Genre-Specific Tips](v5-best-practices.md#genre-specific-tips) for the matching prompt guidance.

| Genre category | Weirdness | Style Influence | Why |
|----------------|-----------|-----------------|-----|
| Pop / radio pop | `0.10–0.30` | `0.60–0.80` | Familiar hooks and clean structure win; keep it on-genre. |
| Hip-Hop / Rap | `0.20–0.40` | `0.50–0.70` | Protect the pocket and flow; a little room for beat character. |
| Rock / Punk | `0.20–0.45` | `0.55–0.75` | Genre hallmarks matter; punk stays tight and fast. |
| Folk / Acoustic | `0.10–0.30` | `0.60–0.80` | Intimacy and coherence over surprise. |
| Electronic / EDM | `0.30–0.55` | `0.45–0.65` | Sound design rewards some experimentation. |
| K-Pop | `0.20–0.40` | `0.65–0.85` | Maximalist but genre-precise — switch-ups come from the prompt, not the slider. |
| Cinematic / Orchestral | `0.15–0.40` | `0.55–0.75` | Mood and coherence carry the piece. |
| Jazz / Improv | `0.40–0.65` | `0.40–0.60` | An improvisational feel benefits from deviation. |
| Ambient / Experimental / IDM | `0.55–0.85` | `0.25–0.50` | The unexpected is the point; loosen the leash. |
| Metal / Heavy | `0.10–0.30` | `0.65–0.85` | Suno struggles with heavy genres — lock hard on-genre and minimize deviation (see [Known V5 Limitations](v5-best-practices.md#known-v5-limitations); consider testing V4.5). |
| Documentary / narrative | `0.10–0.30` | `0.55–0.75` | The story carries the track — favor clear vocals and predictable structure so the lyric lands. |

---

## Interaction Effects

The two always-on sliders combine into four broad regions:

| | **Low Style Influence** | **High Style Influence** |
|---|---|---|
| **High Weirdness** | **Wild card** — maximum surprise, genre may dissolve. Great for idea-mining; expect drift and many regenerations. | **Adventurous within the lane** — unexpected choices that still read as the genre. The sweet spot for keeping a familiar genre fresh (pair with a specific genre tag). |
| **Low Weirdness** | **Loose & smooth** — Suno fills gaps its own way but stays tame. Good for gentle fusions. | **Safe & on-genre** — faithful, predictable, release-ready. The default for pop, folk, and narrative work; the risk is a generic result. |

**Key takeaways:**
- **High Weirdness + a specific genre tag** is the reliable "interesting but not chaotic" combo — the genre tag anchors the surprises.
- **Low Style Influence when you want the AI to surprise you** — it's the fastest lever for happy accidents.
- Push **both sliders to their extremes** only deliberately: high Weirdness + low Style Influence is a genuine wild card, not a fine-tuning move.

**Audio Influence interactions** (upload/cover flows):

- **High Audio Influence + Low Weirdness** — output tracks the reference closely. Safest for faithful covers and consistency.
- **High Audio Influence + High Weirdness** — a tug-of-war: the upload pulls toward the source while Weirdness pushes away. This can yield striking reinterpretations, but also incoherent or muddy results. Move one slider at a time and audition carefully.
- **High Audio Influence + High Style Influence** — two "adherence" pulls competing. If the reference audio and the style prompt describe *different* things, they fight — decide which is your source of truth and relax the other.

---

## Sliders vs. Style Prompt

The single most useful habit: diagnose whether a bad result is a **prompt problem** or a **slider problem** before you touch anything.

- The **style prompt** decides *what* the track is — genre, instruments, mood, tempo, vocal identity. A slider can't add a banjo, fix a mispronunciation, or change the tempo.
- The **sliders** decide *how strictly* Suno commits to that prompt and *how far* it may wander. They're fine-tuning, not a rescue for a vague or wrong prompt.

**Change the prompt when** the output has the wrong genre, wrong instruments, wrong mood or tempo, a missing element, or the vocal character is off. No slider fixes content. (Keep the prompt focused — every descriptor doing distinct work; a bloated synonym-pile won't be rescued by sliders either; see [Keep It Simple](v5-best-practices.md#prompt-construction).)

**Adjust a slider when** the prompt is already right but the *interpretation* is off:

| Symptom | First move |
|---------|-----------|
| Output is generic / too safe | Raise Weirdness a little, **or** lower Style Influence a little (one at a time) |
| Output drifts off-genre / ignores tags | Raise Style Influence; if still off, sharpen the genre tag in the prompt |
| Output is chaotic / incoherent | Lower Weirdness; keep Style Influence mid–high |
| Result feels rigid / wooden | Lower Style Influence slightly, **or** simplify the prompt |
| Wrong instruments, mood, or tempo | Change the prompt — not a slider issue |
| Mispronunciation / wrong words | Fix lyrics + pronunciation — not a slider issue |
| Cover doesn't resemble the source | Raise Audio Influence |
| Cover too close, want more transformation | Lower Audio Influence and/or raise Weirdness |

**Golden rule — change one thing at a time.** Adjusting a slider *and* rewriting the prompt in the same pass makes it impossible to know which move helped (this mirrors the "adjust one element at a time" advice in [Iteration Tips](v5-best-practices.md#iteration-tips)).

---

## Quick Workflow

1. **Write a clear, focused prompt first** — genre + instruments + mood + vocal, every descriptor doing distinct work.
2. **Generate at the default slider positions.** Don't pre-adjust blind.
3. **Listen, then diagnose** — is this a prompt problem or a slider problem? (Use the table above.)
4. **If it's a slider problem, move ONE slider a small step** and regenerate.
5. **Log every attempt** — note the slider value and what changed, so you can reproduce the keeper.

---

## Related Skills

- **`/bitwize-music:suno-engineer`** — Technical Suno V5 prompting expert
  - Chooses slider settings alongside the style prompt
  - Diagnoses prompt-vs-slider issues on regeneration
  - Uses this guide as reference

- **`/bitwize-music:lyric-reviewer`** — Pre-generation QC gate
  - Confirms the prompt is ready before slider tuning matters

## See Also

- **`/reference/suno/v5-best-practices.md`** — Full V5 prompting guide; the [Creative Sliders](v5-best-practices.md#creative-sliders) section this file expands, plus [Genre-Specific Tips](v5-best-practices.md#genre-specific-tips) and [Known V5 Limitations](v5-best-practices.md#known-v5-limitations)
- **`/reference/suno/tips-and-tricks.md`** — Operational troubleshooting; Personas and Style Influence interaction
- **`/reference/suno/genre-list.md`** — 500+ genre tags to pin down the genre before tuning sliders
- **`/reference/suno/README.md`** — API parameter table (`styleWeight`, `weirdnessConstraint`)
