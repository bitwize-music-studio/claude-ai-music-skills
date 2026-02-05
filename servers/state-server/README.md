# bitwize-music-state MCP Server

MCP (Model Context Protocol) server providing direct access to the bitwize-music state cache.

## Overview

This server wraps the existing `tools/state/indexer.py` functionality, exposing it as MCP tools. Instead of shelling out to Python and reading JSON files, Claude can call these tools directly for instant structured responses.

## Requirements

- Python 3.10+
- `mcp[cli]>=1.2.0`
- `pyyaml>=6.0`

## Installation

```bash
pip install -r requirements-mcp.txt
```

Or install dependencies directly:

```bash
pip install "mcp[cli]>=1.2.0" pyyaml
```

## Tools Available

| Tool | Description |
|------|-------------|
| `find_album(name)` | Find album by name with fuzzy matching |
| `list_albums(status_filter?)` | List all albums with summary info |
| `get_track(album_slug, track_slug)` | Get specific track details |
| `get_session()` | Get current session context |
| `update_session(album?, track?, phase?, action?, clear?)` | Update session context |
| `rebuild_state()` | Force full rebuild from markdown files |
| `get_config()` | Get resolved configuration paths |
| `get_ideas(status_filter?)` | Get album ideas with counts |
| `get_pending_verifications()` | Get tracks needing source verification |

## Usage

The server starts automatically when the plugin is enabled. It uses stdio transport.

### Manual Testing

```bash
# From plugin root
python3 servers/state-server/server.py
```

The server reads JSON-RPC requests from stdin and writes responses to stdout.

## Architecture

```
Claude Code → MCP Protocol → server.py → StateCache → indexer.py → state.json
```

- **StateCache**: In-memory cache with lazy loading and staleness detection
- **Staleness**: Checks file mtimes; auto-refreshes when state.json or config changes
- **Persistence**: Session updates write through to disk via indexer's atomic write

## Development

The server imports from the plugin's existing tools:

- `tools/state/indexer.py` - Core state management functions
- `tools/state/parsers.py` - Markdown parsing (used by indexer)
- `tools/shared/config.py` - Config path resolution

All existing code is reused; the server only adds the MCP interface layer.
