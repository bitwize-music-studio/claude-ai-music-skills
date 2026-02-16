# State Cache Schema (v1.2.0)

The state cache at `~/.bitwize-music/cache/state.json` is a JSON file built from markdown source files. It is a **disposable cache** — markdown files remain the source of truth and state can always be rebuilt with `python3 tools/state/indexer.py rebuild`.

---

## Top-Level Structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (currently `"1.2.0"`) |
| `generated_at` | string | Yes | ISO 8601 UTC timestamp of last build/update |
| `plugin_version` | string\|null | Yes | Plugin version from `.claude-plugin/plugin.json`, or `null` if unreadable |
| `config` | object | Yes | Resolved configuration snapshot |
| `albums` | object | Yes | Map of album slug → album data |
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
| `model` | string | Full Claude model ID (e.g., `"claude-opus-4-6"`) |
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
