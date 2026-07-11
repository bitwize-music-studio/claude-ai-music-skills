# FAQ

Answers to the questions I get most — what this project is, what it costs to
run, why the workflow is shaped the way it is, and where I stand on
third-party integrations.

- [The project](#the-project)
- [Costs & requirements](#costs--requirements)
- [Workflow philosophy](#workflow-philosophy)
- [Integrations & third-party services](#integrations--third-party-services)

---

## The project

### What is this?

A Claude Code plugin that turns a conversation into a full album production
pipeline — concept, research, lyrics, Suno prompts, mastering, promo, and
release prep, with quality gates at every stage. The [README](README.md) has
the full tour and an example workflow.

### How do I get started?

Install from the marketplace, then run setup and configure:

```bash
/plugin marketplace add bitwize-music-studio/claude-ai-music-skills
/plugin install bitwize-music@bitwize-music
/bitwize-music:setup
/bitwize-music:configure
```

New to the workflow? `/bitwize-music:tutorial` walks you through your first
album end to end.

### How do I contribute?

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch and PR workflow. Genre
documentation is a great first contribution — `/bitwize-music:genre-creator`
scaffolds one for you.

## Costs & requirements

### What do I need to run this?

- **Claude Code** on Linux or macOS (Windows works via WSL).
- **Python 3.10+** for the MCP server and audio tools.
- **A Claude plan that can take the load.** This project pushes Claude Code
  hard — multi-agent research, sub-agent orchestration across model tiers.
  It works best on the Max plan; Pro will hit rate limits during multi-track
  sessions.
- **A Suno account** for generation (see the next question).

### Do I need a paid Suno subscription?

For anything you plan to release, yes. Beyond generation limits, the
important part is rights: Suno ties commercial use of generated audio to its
paid plans. If you intend to put tracks on streaming platforms, make sure the
plan you generate under actually grants commercial use — that grant is the
foundation of your chain of rights (more on why that matters
[below](#what-about-commercial-rights-this-is-the-part-that-worries-me)).

## Workflow philosophy

### Why do I generate on Suno manually instead of in-terminal?

Two reasons, in order:

1. **Suno has no official public API.** The day one exists, in-terminal
   generation goes on the roadmap — see
   [the integrations section](#integrations--third-party-services) for why I
   won't bridge the gap with third-party wrappers in the meantime.
2. **The listen-and-approve hop is a feature.** You hear every generation and
   decide what survives. The pipeline automates everything around your
   judgment, not instead of it.

### Why does the pipeline require human source verification?

Documentary albums name real people and make factual claims. Every source
gets captured as a clickable link and a human verifies it before generation
is unblocked — `/bitwize-music:pre-generation-check` enforces the gate. I
won't ship a workflow where an LLM's research goes straight to publication
without a human signing off.

## Integrations & third-party services

### Will you integrate with Suno's API or MCP server?

The moment an official one exists, yes — enthusiastically. Generate, review,
regenerate, as much of the loop as I can pull into the terminal. This is the
integration I want most, and it's blocked only by there being no official
API to build on.

### Why won't you integrate third-party Suno-wrapper APIs?

Suno doesn't offer a public API, so services selling "Suno generation over
REST" are accessing Suno programmatically without affiliation — some say so
outright in their own terms. Shipping such an integration — even opt-in and
disabled by default — would make this project a distribution channel for
access the platform hasn't sanctioned. That's a line I can't cross, however
clean the PR is. (This came to a head in
[#465](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/465)
if you want the long version.)

### What about commercial rights? (This is the part that worries me.)

Walk the chain of rights for a track generated through a wrapper:

1. Suno's commercial-use grant attaches to **its subscribers, generating
   through its platform**.
2. A wrapper generates on your behalf — through whose account? Under whose
   subscription? Wrapper terms typically add **no license of their own**
   ("rights flow from Suno's terms") and disclaim IP warranties.
3. Suno's terms **don't contemplate the wrapper existing**, so there is no
   written grant that clearly reaches you.

The result is audio with no clear chain of rights — and if it gets released
and a claim or takedown comes, that risk lands entirely on the person who
released it. People use this plugin to put real albums on real streaming
platforms. I'm not handing them that gap.

(Even generating on Suno directly: confirm your plan grants commercial use
before you release. This isn't legal advice — read the terms yourself.)

### Can you support other music generation services?

In principle, yes. A provider running **its own model** behind **its own
official API** is a completely different story from a wrapper. The
architecture would be a provider-neutral interface with pluggable adapters —
the templates already carry `<!-- SERVICE: suno -->` markers anticipating
exactly this. One honest caveat: I don't hold subscriptions with other
providers, so a contributed adapter needs contributor-maintained testing to
be viable.
