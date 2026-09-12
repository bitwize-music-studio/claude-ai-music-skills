# Suno Model Catalog

One section per model you can pick in Suno's model picker (top-right of the Create form). Prompting mechanics that are the same on every model live in [best-practices.md](best-practices.md); this file holds what differs. The catalog covers whatever is selectable today. When Suno ships a new model, add a section here — nothing needs renaming, and older models keep their sections for as long as Suno keeps offering them. When Suno retires a model, delete its section and fold anything users still need (how to carry old songs, Voices or Custom Models forward) into the "Made before …" note at the end.

> **Related skill**: `/bitwize-music:suno-engineer` (fills the track's Generation Settings table from this catalog)
> **Related docs**: [best-practices.md](best-practices.md), [creative-sliders.md](creative-sliders.md)

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
- **When to use**: every finished track. It follows the brief closely and adds few unrequested elements, but output quality varies by genre — reported strong on pop, drum & bass and UK garage; weak on grunge, metal, alt-country and synth-pop.
- **Known quirks** (reported, launch week): on Duration Auto, outputs often run slower, sparser and longer than the prompt implies — state tempo and density explicitly; rock, metal, grunge and alt-country vocals drift to a generic or artifact-laden timbre (reported independently by several testers, including a professional mixer); the stereo image is narrower than testers expected (two independent reports); Covers hold the source melody and structure well with Variety Off, and drift with Variety on; mixes reported going muffled after ~2:30 on standard mode **(unverified)**.
- Internal id (for reading payloads only): `chirp-hawk`.

## v6-wild

- **Suno's positioning**: "built for exploration … less predictable and more varied, producing unexpected, textured and ambitious results. It gives you new ideas to riff on, build from or bring back into v6 for further refinement." CEO: "maybe a verse, maybe even 5 seconds, V6 Wild makes incredible stuff … it's not going to be perfect for the whole song."
- **Tier**: Pro, Premier. Picker label "v6-wild · Pro" ("Best for experimental ideas.").
- **Variety default**: **Off** (the only model whose default is Off).
- **Credits**: 10 per generation; Max Mode supported.
- **When to use**: first pass on a sound you haven't pinned down, or on genres where v6 is too polite. Workflow: generate on v6-wild, pick the take with the character you want, **Cover it on v6** to polish. Two Generation Log rows. Reported: one attempt at the Cover step did not clearly preserve wild's character, and nobody has published Cover settings that do — treat the second step as experimental.
- **Known quirks** (reported): less polish; output length is unpredictable (from ~50 s to ~7 min observed on similar prompts) — generate several takes before judging; drifts from the brief by design. In a seven-genre A/B, v6 won vocal fidelity and prompt adherence 7/7 while wild won on character in indie rock, R&B/soul and metal; one tester found it not always distinguishable from v6. Exclude Styles works on wild (one confirmation); Max Mode on wild and Variety above Off on wild are untested. Built with outside producers and tuned less toward average user preference, so niche genres skew less "poppy".
- Internal id: `chirp-hawk-wild`.

## v6-mini

- **Suno's positioning**: "a faster, more efficient version available to everyone … better, faster results than any free model on any music creation platform."
- **Tier**: all plans, including Free. Picker label "v6-mini" ("A free, more efficient version of premium v6 models.").
- **Variety default**: Normal.
- **Credits**: 10 per generation; Max Mode supported in the app (plan-gated).
- **When to use**: sketches and high-volume idea generation; the only model on a Free account.
- **Known quirks** (reported): The Verge found "simpler and often more artifacts". **Free-tier output is not releasable**: trial downloads (7 lifetime) are personal-use only and carry no commercial rights. The app contains a "keep one of two" flow ("Choose one to keep for free" / "Keep both for N credits"); when it triggers is unconfirmed. Advanced Mode controls, Voices and Custom Models on a Free account are reported available (single source, unconfirmed).
- Internal id: `chirp-goose`.

## Custom Models

- **What it is**: a private model fine-tuned on your own catalog. Upload **at least 6** original tracks ("Upload 24+ songs for best results"); **100 credits** to create; 2–5 minutes to build; up to **3 per account**; private, not shareable. Appears in the model picker as `Custom: <name>`.
- **Created before v6?** Upgraded automatically — nothing to rebuild.
- **Variety default**: Normal (treated as a v6 model) — set Off.
- **When to use**: album-wide consistency of voice and aesthetic; also the reported workaround for the rock "southern voice" drift. Can be stacked with a Voice.
- **Prompting**: drop generic production language; keep genre and section-level direction. See [best-practices.md § Custom Models](best-practices.md#custom-models-fine-tuning).

---

## Made before v6

Suno retired every earlier model on **2026-09-09**; nothing you generate today runs on anything but the v6 family. What that means for things already in your library:

- **Songs** stay playable and shareable. Extend, Cover and Remaster of them run on v6 — **Remaster** when you like the song and only want better audio, **Cover** when you want v6 to reinterpret it while following the melody. Suno warns the result "may sound different from the original generation."
- **Prompts** written for earlier generations do not transfer: expect different tempo, density and length. Re-prompt; don't rerun.
- **Voices** keep working and offer a one-click **Upgrade Voice to v6** for better consistency.
- **Custom Models** were upgraded automatically — nothing to rebuild.
- **Generation Logs** that name a model other than the four above refer to a retired model.

There is no official Suno API, and no third-party reseller exposes v6; do not write `V6` / `V6_WILD` / `V6_MINI` identifiers anywhere — they do not exist.

---

## Sources

- [Introducing v6 — Suno Blog](https://suno.com/blog/introducing-v6) · [v6 FAQ](https://help.suno.com/en/articles/13924481) · [Current Models: v6](https://help.suno.com/en/articles/13924737) · [What's new in v6?](https://help.suno.com/en/articles/13924801) · [How do I change models?](https://help.suno.com/en/articles/13924993)
- [Suno v6 Is Here — Suno (YouTube)](https://youtu.be/_lHvWn2SNC4) · [How to Transition Your Workflow — Suno (YouTube)](https://youtu.be/tkKGNBzkHwE)
- Launch-week hands-on: HookGenius, The AI Musicpreneur (27-generation A/B), The Verge, Busy Works Beats, Hit Songwriter Meets AI; r/SunoAI (first 24 h). Follow-up (Sep 10–11): Spasciz "V6 vs V6 WILD" (youtu.be/LR4af6Gr6Xg), Busy Works Beats "v6-Wild is Over Powered" (youtu.be/eMi7worlN0Y), Jeremiah The Stranger (youtu.be/8xNVN-KM77k), Music Tech Info issue videos (youtu.be/petSvYWvnIs, youtu.be/5SDKgk5QW5E, youtu.be/R3my_3sXk6A), The Mix University (youtu.be/7QLHGYEEwhw), Greg Kocis on Cover melody drift (youtu.be/gyQVxjkBoy8). See `CHANGELOG.md` § 2026-09-10 and § 2026-09-11 for the full list.
