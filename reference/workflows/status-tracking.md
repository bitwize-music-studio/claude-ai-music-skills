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

```
Concept → Research Complete → Sources Verified → In Progress → Complete → Released
```

---

## Generation Log

Every track file includes a generation log table:

| # | Date | Model | Result | Notes | Rating |
|---|------|-------|--------|-------|--------|
| 1 | 2025-12-03 | V5 | [Listen](url) | First attempt | — |
| 2 | 2025-12-03 | V5 | [Listen](url) | Boosted vocals | ✓ |

**When you find a keeper**: Set Status to `Generated`, add Suno Link.

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
