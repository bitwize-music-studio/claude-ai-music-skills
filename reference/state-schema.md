# State Cache Schema (v1.3.0)

The state cache at `~/.bitwize-music/cache/state.json` is a JSON file built from markdown source files. It is a **disposable cache** — markdown files remain the source of truth and state can always be rebuilt with `python3 tools/state/indexer.py rebuild`.

---

## Top-Level Structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (currently `"1.4.0"`) |
| `generated_at` | string | Yes | ISO 8601 UTC timestamp of last build/update |
| `plugin_version` | string\|null | Yes | Installed plugin version from `.claude-plugin/plugin.json`, refreshed every build (display only), or `null` if unreadable |
| `last_migrated_version` | string\|null | No | Version through which migration notes have been processed. Only advances via `acknowledge_migrations`; preserved across rebuilds. `null`/absent = pre-tracking (surfaces the backlog once). Drives `get_pending_migrations`. See issue #320. |
| `config` | object | Yes | Resolved configuration snapshot |
| `albums` | object | Yes | Map of album slug → album data |
| `album_collisions` | array | Yes | Album slug collisions detected on disk (empty when none); see below |
| `ideas` | object | Yes | Album ideas from IDEAS.md |
| `skills` | object | Yes | Indexed skill metadata from SKILL.md files |
| `session` | object | Yes | Session context for resume/continuity |

---

## `config` Object

Snapshot of resolved paths and artist info from `~/.bitwize-music/config.yaml`.

| Field | Type | Description |
|-------|------|-------------|
| `content_root` | string | Resolved absolute path to content root |
| `audio_root` | string | Resolved absolute path to audio root |
| `documents_root` | string | Resolved absolute path to documents root |
| `overrides_dir` | string | Resolved absolute path to overrides directory |
| `artist_name` | string | Artist name from config |
| `config_mtime` | float | Last modification time of config.yaml (for staleness detection) |

---

## `albums` Object

Map of album slug (string) → album data object.

**Global uniqueness invariant**: album slugs are unique across genres — the map is keyed by bare slug, so the same slug under two genres cannot coexist. This is enforced at creation (`create_album_structure`) and rename (`rename_album`), both of which reject a slug that already exists under any other genre. Pre-existing on-disk collisions are detected at index time — the first genre (lexicographic order) whose README parses wins deterministically, and the shadowed album(s) are listed in `album_collisions`.

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
| `streaming_urls` | object | Map of platform → URL (only non-empty entries from frontmatter `streaming:` block) |
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

## `album_collisions` Array

Added in 1.3.0 (issue #392). Always present; a list of collision records, empty when no collisions exist. Populated by the indexer when the same album slug is found under multiple genres on disk. The winner (`kept`) is the first genre (lexicographic order) whose README parses — deterministic, and always the entry actually indexed into `albums`; all others are `shadowed` (sorted by genre, parseable or not; supports 2+ way collisions) and are **not** indexed into `albums`. If no candidate's README parses, no album entry and no collision record are emitted.

```json
"album_collisions": [
  {
    "slug": "midnight",
    "kept":     {"genre": "jazz", "path": "/abs/path/albums/jazz/midnight"},
    "shadowed": [{"genre": "rock", "path": "/abs/path/albums/rock/midnight"}]
  }
]
```

### Collision Record

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | The colliding album slug (bare directory name) |
| `kept` | object | The winning album: `{genre, path}` — this is the entry visible in `albums` |
| `shadowed` | array | The hidden album(s): `[{genre, path}, ...]`, sorted by genre |

**Fix**: rename one album with `/bitwize-music:rename`, or move the directory, then rebuild the state cache. Collisions are surfaced by `health_check`, `find_album`, `list_albums`, `rebuild_state`, and the indexer CLI (`rebuild`/`update`/`show`).

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

## `skills` Object

Indexed metadata from `skills/*/SKILL.md` files in the plugin directory. Queryable via `list_skills` and `get_skill` MCP tools.

| Field | Type | Description |
|-------|------|-------------|
| `skills_root` | string | Absolute path to the skills/ directory |
| `skills_root_mtime` | float | Last modification time of skills/ directory |
| `count` | integer | Total number of indexed skills |
| `model_counts` | object | Map of model tier → count (e.g., `{"opus": 6, "sonnet": 24, "haiku": 14}`) |
| `items` | object | Map of skill name → skill data |

### Skill Data

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Skill identifier (kebab-case, e.g., `"lyric-writer"`) |
| `description` | string | One-line description of the skill's purpose |
| `model` | string | Model from frontmatter — tier alias (e.g., `"opus"`) or a pinned ID (e.g., `"claude-opus-4-8"`) |
| `model_tier` | string | Derived tier: `"opus"`, `"sonnet"`, `"haiku"`, or `"unknown"` |
| `argument_hint` | string\|null | Expected input format hint |
| `allowed_tools` | array | List of tool names the skill can access |
| `prerequisites` | array | List of skill names that should run first |
| `requirements` | object | External dependencies (e.g., `{"python": ["playwright"]}`) |
| `user_invocable` | boolean | Whether the skill can be invoked directly by users (default: `true`) |
| `context` | string\|null | Execution context (e.g., `"fork"`) or `null` for default |
| `path` | string | Absolute path to the SKILL.md file |
| `mtime` | float | Last modification time of the SKILL.md file |

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

### Migration History

| From | To | Changes |
|------|-----|---------|
| 1.0.0 | 1.1.0 | Added `skills` top-level section with indexed skill metadata |
| 1.1.0 | 1.2.0 | Added `plugin_version` top-level field for upgrade path tracking |
| 1.2.0 | 1.3.0 | Added `album_collisions` top-level field (seeded to `[]`) for cross-genre slug collision detection (issue #392) |
| 1.3.0 | 1.4.0 | Re-coerced cached album/track `explicit` flags that pre-#388 parsers stored as raw truthy strings (e.g. `"false"`) to real booleans |

`last_migrated_version` was added as a **backward-compatible optional field** (no schema-version bump). Fresh builds include it (seeded to the installed version); states written earlier simply omit it and read as `null`, which `get_pending_migrations` treats as pre-tracking. Avoiding a version bump here is deliberate — bumping would force the live MCP path to auto-rebuild every existing state, erasing the very "behind" status migration detection depends on (issue #320).
