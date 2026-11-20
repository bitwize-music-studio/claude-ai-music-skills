# Status Tracking

Track and album statuses indicate workflow progress.

---

## Track Statuses

| Status | Meaning |
|--------|---------|
| `Not Started` | Concept only |
| `Sources Pending` | Has sources, awaiting human verification |
| `Sources Verified` | Ready for production |
| `In Progress` | Lyrics being written or revised |
| `Generated` | Has acceptable output |
| `Final` | Complete, locked |

### Track Status Flow

```
Not Started → Sources Pending → Sources Verified → In Progress → Generated → Final
                    ↑                                              ↓
                    └──────────── (regenerate if needed) ──────────┘
```

---

## Album Statuses

| Status | Meaning |
|--------|---------|
| `Concept` | Planning phase |
| `Research Complete` | Sources gathered, awaiting verification |
| `Sources Verified` | All sources verified |
| `In Progress` | Tracks being created |
| `Complete` | All tracks Final |
| `Released` | Live on platforms (`release_date` set in frontmatter) |

### Album Status Flow

Documentary / true-story albums take the full flow:

```
Concept → Research Complete → Sources Verified → In Progress → Complete → Released
```

Standard (non-documentary) albums skip the research statuses:

```
Concept → In Progress → Complete → Released
```

---

## Generation Log

Every track file includes a generation log table:

| # | Date | Model | Result | Notes | Rating |
|---|------|-------|--------|-------|--------|
| 1 | 2025-12-03 | v6 | [Listen](url) | First attempt | — |
| 2 | 2025-12-03 | v6 | [Listen](url) | Boosted vocals | ✓ |

A track is `Generated` once it has takes. **When the user picks a keeper**, mark it ✓ in the Rating column and add its Suno Link; only then does the track advance to `Final`. Never pick the keeper for the user.

---

## Status Update Rules

1. **Track status changes require action**:
   - `Not Started` → `Sources Pending`: After adding sources
   - `Sources Pending` → `Sources Verified`: After human verification
   - `Sources Verified` → `In Progress`: When starting lyrics writing
   - `In Progress` → `Generated`: When keeper found
   - `Generated` → `Final`: After user approval

2. **Album status follows tracks**:
   - Album is `In Progress` when any track is being worked on
   - Album is `Complete` when ALL tracks are `Final`
   - Album is `Released` when uploaded to platforms

3. **Never skip statuses** - Each represents a workflow gate

4. **Transitions**: an album advances when ALL its tracks reach the corresponding level. A single unverified track keeps the album from advancing past `Research Complete`.

5. **Auto-advancement**: skills that complete a phase advance the album themselves:
   - `/bitwize-music:verify-sources` → when every track is verified, the album advances to `Sources Verified`
   - When the last track goes `Final`, `update_track_field` advances the album to `Complete` itself, and keeps the track's row in the README Tracklist current; `sync_album_tracklist` repairs the rest of that table from the track files

6. **Batch approval**: to mark all Generated tracks Final after QA, call `update_track_field(album_slug, track_slug, "status", "Final")` for each one, but only for tracks that have a ✓ keeper in their Generation Log.

---

## Regeneration Workflow

When the user rejects a generated take (wrong style, a pronunciation, the result):

1. **Log the rejection**: add a Generation Log row with the reason ("wrong tempo", "vocal too high", "mispronounced name").
2. **Decide the fix path**:
   - **Style** (genre, tempo, mood) → revise the Style Box via `/bitwize-music:suno-engineer`, then regenerate
   - **Lyrics** (wrong words, pronunciation) → fix them via `/bitwize-music:lyric-writer`, re-run `/bitwize-music:pronunciation-specialist`, then regenerate
   - **Suno's interpretation** (right prompt, wrong result) → regenerate with the same settings; Suno is non-deterministic
   - **One flaw in a take worth keeping** (a wrong or mispronounced word, a weak section, an unwanted instrument) → `/bitwize-music:edit-take` changes that part and keeps the rest. Past five changed places Suno re-sings the whole song, so regenerate instead
   - **A good take that stops early or goes wrong late** → `/bitwize-music:extend-take` keeps it up to the end of a line and generates the rest
3. **Regenerate**: `/bitwize-music:generate` again; it logs the new takes. On suno.com instead, generate and log the attempt by hand.
4. **When satisfied**: the user marks the keeper ✓ in the Rating column, and the track advances to `Final`.

The status stays `Generated` throughout; there is no backward transition, and the Generation Log keeps every attempt. `resume` and `next-step` detect Generated tracks without a ✓ and recommend the next regeneration step.

Detailed recovery procedures: [error-recovery.md](error-recovery.md). State cache schema: [../state-schema.md](../state-schema.md).
