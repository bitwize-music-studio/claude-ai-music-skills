# State Cache Schema (v1.0.0)

The state cache at `~/.bitwize-music/cache/state.json` is a JSON file built from markdown source files. It is a **disposable cache** — markdown files remain the source of truth and state can always be rebuilt with `python3 tools/state/indexer.py rebuild`.

---

## Top-Level Structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (currently `"1.0.0"`) |
| `generated_at` | string | Yes | ISO 8601 UTC timestamp of last build/update |
| `config` | object | Yes | Resolved configuration snapshot |
| `albums` | object | Yes | Map of album slug → album data |
| `ideas` | object | Yes | Album ideas from IDEAS.md |
| `session` | object | Yes | Session context for resume/continuity |

---

## `config` Object

Snapshot of resolved paths and artist info from `~/.bitwize-music/config.yaml`.

| Field | Type | Description |
|-------|------|-------------|
| `content_root` | string | Resolved absolute path to content root |
| `audio_root` | string | Resolved absolute path to audio root |
| `documents_root` | string | Resolved absolute path to documents root |
| `artist_name` | string | Artist name from config |
| `config_mtime` | float | Last modification time of config.yaml (for staleness detection) |

---

## `albums` Object

Map of album slug (string) → album data object.

### Album Data

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Absolute path to album directory |
| `genre` | string | Genre slug (parent directory name) |
| `title` | string | Album title from README frontmatter |
| `status` | string | Album status (see valid values below) |
| `explicit` | boolean | Whether album contains explicit content |
| `release_date` | string\|null | Release date or null if unreleased |
| `track_count` | integer | Total number of tracks |
| `tracks_completed` | integer | Number of tracks with completed status |
| `readme_mtime` | float | Last modification time of album README.md |
| `tracks` | object | Map of track slug → track data |

### Valid Album Statuses

- `Concept` — Initial planning phase
- `Research Complete` — Research done, sources gathered
- `Sources Verified` — Human verification of sources complete
- `In Progress` — Active writing/generation
- `Complete` — All tracks finished, ready for mastering/release
- `Released` — Album published to platforms

### Track Data

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Absolute path to track markdown file |
| `title` | string | Track title from frontmatter |
| `status` | string | Track status (see valid values below) |
| `explicit` | boolean | Whether track contains explicit content |
| `has_suno_link` | boolean | Whether a Suno generation link exists |
| `sources_verified` | string | Verification status: `"N/A"`, `"Pending"`, or `"Verified (DATE)"` |
| `mtime` | float | Last modification time of track file |

### Valid Track Statuses

- `Not Started` — No work begun
- `Sources Pending` — Sources gathered but not verified
- `Sources Verified` — Human verified all sources
- `In Progress` — Lyrics being written
- `Generated` — Track generated on Suno, audio exists
- `Final` — Approved, ready for mastering

---

## `ideas` Object

| Field | Type | Description |
|-------|------|-------------|
| `file_mtime` | float | Last modification time of IDEAS.md (0.0 if missing) |
| `counts` | object | Map of status string → count (e.g., `{"Pending": 3, "In Progress": 1}`) |
| `items` | array | List of idea objects |

### Idea Object

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Idea title/name |
| `genre` | string | Target genre |
| `status` | string | Idea status: `"Pending"`, `"In Progress"`, `"Complete"` |

---

## `session` Object

Tracks last working context for session continuity.

| Field | Type | Description |
|-------|------|-------------|
| `last_album` | string\|null | Last album slug worked on |
| `last_track` | string\|null | Last track slug worked on |
| `last_phase` | string\|null | Last workflow phase (e.g., `"Writing"`, `"Generating"`, `"Mastering"`) |
| `pending_actions` | array | List of pending action strings (max 100) |
| `updated_at` | string\|null | ISO 8601 UTC timestamp of last session update |

---

## Staleness Detection

The MCP server and indexer detect stale cache by comparing:
1. `state.json` file mtime vs cached mtime
2. `config.yaml` file mtime vs `config.config_mtime`

If either has changed, the cache is reloaded or rebuilt.

---

## Schema Migration

When `state.version` doesn't match the current version:
- Same major version → apply migration chain
- Different major version → full rebuild
- Newer than current → full rebuild (downgrade scenario)
- Migration failures → full rebuild

The migration chain is defined in `tools/state/indexer.py` as `MIGRATIONS` dict.
