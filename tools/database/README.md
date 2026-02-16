# Database Tools

PostgreSQL integration for social media post management. The database complements the markdown-based workflow — markdown files remain the source of truth for album/track content, while the database stores social media posts and their publish state.

## Setup

### 1. Install dependencies

```bash
~/.bitwize-music/venv/bin/pip install psycopg2-binary
```

### 2. Create the database

```bash
createdb your-database
psql -d your-database -f tools/database/schema.sql
```

Or use the MCP tool (auto-creates tables if they don't exist):

```
db_init
```

### 3. Configure credentials

Add a `database:` section to `~/.bitwize-music/config.yaml`:

```yaml
database:
  enabled: true
  host: "localhost"
  port: 5432
  name: "your-database"
  user: "your-username"
  password: "your-password"
```

See `config/config.example.yaml` for full documentation.

## Schema

Three tables — see `schema.sql` for the complete DDL.

| Table | Purpose |
|-------|---------|
| `albums` | Album metadata (synced from plugin markdown state via `db_sync_album`) |
| `tracks` | Track metadata (synced from plugin markdown state via `db_sync_album`) |
| `tweets` | Social media posts linked to albums/tracks (multi-platform) |

## MCP Tools

| Tool | Description |
|------|-------------|
| `db_init` | Create tables and run migrations (idempotent) |
| `db_list_tweets` | List posts with album/status/platform filters |
| `db_create_tweet` | Insert a new post linked to an album/track |
| `db_update_tweet` | Update post fields (text, posted, enabled, media) |
| `db_delete_tweet` | Delete a post by ID |
| `db_search_tweets` | Full-text search across post content |
| `db_sync_album` | Upsert album + tracks from markdown state to DB |
| `db_get_tweet_stats` | Post counts by status, platform, and album |

## Migrations

Future schema changes go in `migrations/` as numbered SQL files (e.g., `002_add_hashtags.sql`). The `db_init` tool runs all migration files automatically. Use `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` patterns so migrations are safe to re-run.

## Files

| File | Purpose |
|------|---------|
| `schema.sql` | Complete schema for new installs |
| `connection.py` | Connection helper (reads creds from config) |
| `__init__.py` | Package init |
