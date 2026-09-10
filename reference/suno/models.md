# Suno Model Catalog

One section per model you can pick in Suno's model picker (top-right of the Create form). Prompting mechanics that are the same on every model live in [best-practices.md](best-practices.md); this file holds what differs. When Suno ships a new model, add a section here and a migration file under [version-history/](version-history/) — nothing needs renaming.

> **Related skill**: `/bitwize-music:suno-engineer` (fills the track's Generation Settings table from this catalog)
> **Related docs**: [best-practices.md](best-practices.md), [creative-sliders.md](creative-sliders.md), [version-history/v6-changes.md](version-history/v6-changes.md)

---

## How to choose

| Situation | Model | Settings |
|---|---|---|
| Finished album track with engineered lyrics and Style Box (the default) | **v6** | Variety Off · Max Mode On if over ~2:00 · Duration Auto |
| Exploring a sound, or an "attitude" genre where v6 plays it safe (rock, metal, era-specific soul, anything drifting to a generic voice) | **v6-wild**, then Cover the keeper on v6 | Variety Off (its default) · listen to both takes |
| Album-wide brand or vocal consistency | **Custom Model** (or v6 + a Voice) | Max Mode On (Suno's recommendation for Voices) |
| Free account | **v6-mini** (only option) | downloads are trial-only and non-commercial — not releasable |
| Quick sketch, high-volume idea generation | **v6-mini** | Variety Normal is fine here |

Record the choice in the track file's `### Generation Settings` table; the Generation Log's Model column shows what each attempt actually ran on.

---

## v6

- **Suno's positioning**: "our flagship model … reliable, precise and consistently delivers polished music across every genre and style. When you know what you want, v6 helps you get there."
- **Tier**: Pro, Premier. Picker label "v6 · Pro" ("Powerful. Versatile. Refined. Our best model yet."). Selected by default.
- **Variety default**: Normal — set **Off** for an engineered Style Box.
- **Credits**: 10 per generation (two songs); 20 with Max Mode.
- **Max Mode**: supported; recommended over ~2:00, for covers, Voices and style transfer.
- **When to use**: every finished track. It follows the brief at least as well as v5.5 and adds fewer unrequested elements.
- **Known quirks** (reported, launch week): the same v5.5 prompt comes back slower, sparser and often longer on Duration Auto; rock/metal vocals drift to a generic post-grunge timbre; mixes reported going muffled after ~2:30 on standard mode **(unverified)**.
- Internal id (for reading payloads only): `chirp-hawk`.

## v6-wild

- **Suno's positioning**: "built for exploration … less predictable and more varied, producing unexpected, textured and ambitious results. It gives you new ideas to riff on, build from or bring back into v6 for further refinement." CEO: "maybe a verse, maybe even 5 seconds, V6 Wild makes incredible stuff … it's not going to be perfect for the whole song."
- **Tier**: Pro, Premier. Picker label "v6-wild · Pro" ("Best for experimental ideas.").
- **Variety default**: **Off** (the only model whose default is Off).
- **Credits**: 10 per generation; Max Mode supported.
- **When to use**: first pass on a sound you haven't pinned down, or on genres where v6 is too polite. Workflow: generate on v6-wild, pick the take with the character you want, **Cover it on v6** to polish. Two Generation Log rows.
- **Known quirks** (reported): less polish, sometimes short outputs (~50 s); drifts from the brief by design; a minority of testers could not tell it from v6. Built with outside producers and tuned less toward average user preference, so niche genres skew less "poppy".
- Internal id: `chirp-hawk-wild`.

## v6-mini

- **Suno's positioning**: "a faster, more efficient version available to everyone … better, faster results than any free model on any music creation platform."
- **Tier**: all plans, including Free. Picker label "v6-mini" ("A free, more efficient version of premium v6 models.").
- **Variety default**: Normal.
- **Credits**: 10 per generation; Max Mode supported in the app (plan-gated).
- **When to use**: sketches and high-volume idea generation; the only model on a Free account.
- **Known quirks** (reported): roughly v5.5-class in one A/B; The Verge found "simpler and often more artifacts". **Free-tier output is not releasable**: trial downloads (7 lifetime) are personal-use only and carry no commercial rights.
- Internal id: `chirp-goose`.

## Custom Models

- **What it is**: a private model fine-tuned on your own catalog. Upload **at least 6** original tracks ("Upload 24+ songs for best results"); **100 credits** to create; 2–5 minutes to build; up to **3 per account**; private, not shareable. Appears in the model picker as `Custom: <name>`.
- **v6 status**: models trained on v5.5 were automatically upgraded so v6 powers them — no rebuild.
- **Variety default**: Normal (treated as a v6 model) — set Off.
- **When to use**: album-wide consistency of voice and aesthetic; also the reported workaround for the rock "southern voice" drift. Can be stacked with a Voice.
- **Prompting**: drop generic production language; keep genre and section-level direction. See [best-practices.md § Custom Models](best-practices.md#custom-models-fine-tuning).

---

## Retired

Suno retired every pre-v6 model on **2026-09-09**. Existing songs stay playable and shareable; Extend, Cover and Remaster of them run on v6, so "results may sound different from the original generation" (Suno). Keep these names in mind when reading older Generation Logs.

| Model | Lifetime | Notes |
|---|---|---|
| **v5.5** | 2026-03-26 → 2026-09-09 | Added Voices, Custom Models, My Taste. Guide archived at [version-history/v5-best-practices.md](version-history/v5-best-practices.md). |
| **v5** | 2025-09-23 → 2026-09-09 | 8-minute generations, 12-stem separation. Migration notes: [version-history/v5-changes.md](version-history/v5-changes.md). |
| **v4.5 / v4.5+ / v4.5-all** | 2025-05 → 2026-09-09 | v4.5-all was the free-tier model before v6-mini. |

Third-party API resellers still list `V5_5` identifiers and no reseller exposes v6; there is no official Suno API. Do not write `V6` / `V6_WILD` / `V6_MINI` anywhere — those identifiers do not exist.

---

## Sources

- [Introducing v6 — Suno Blog](https://suno.com/blog/introducing-v6) · [v6 FAQ](https://help.suno.com/en/articles/13924481) · [Current Models: v6](https://help.suno.com/en/articles/13924737) · [What's new in v6?](https://help.suno.com/en/articles/13924801) · [How do I change models?](https://help.suno.com/en/articles/13924993)
- [Suno v6 Is Here — Suno (YouTube)](https://youtu.be/_lHvWn2SNC4) · [How to Transition Your Workflow — Suno (YouTube)](https://youtu.be/tkKGNBzkHwE)
- Launch-week hands-on: HookGenius, The AI Musicpreneur (27-generation A/B), The Verge, Busy Works Beats, Hit Songwriter Meets AI; r/SunoAI (first 24 h). See `CHANGELOG.md` § 2026-09-10 for the full list.
