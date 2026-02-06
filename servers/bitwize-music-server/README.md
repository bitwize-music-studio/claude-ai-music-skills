# bitwize-music MCP Server

MCP (Model Context Protocol) server for the bitwize-music plugin.

## Overview

This server provides structured access to albums, tracks, sessions, config, paths, and track content. Instead of shelling out to Python, reading JSON files, or globbing for files, skills call these tools directly for instant structured responses.

The server is registered as `bitwize-music-mcp` in Claude Code. Future MCP tools can be added to this same server.

## Requirements

- Python 3.10+
- `mcp[cli]>=1.2.0`
- `pyyaml>=6.0`

## Installation

**Recommended: Virtual environment (all systems)**

```bash
# Create shared venv for all plugin tools
python3 -m venv ~/.bitwize-music/venv

# Install MCP server (required)
~/.bitwize-music/venv/bin/pip install -r requirements.txt

# Optional: Install additional tools
~/.bitwize-music/venv/bin/pip install -r requirements.txt          # Mastering
~/.bitwize-music/venv/bin/pip install -r requirements.txt    # Cloud uploads
~/.bitwize-music/venv/bin/pip install playwright                   # Document hunter
~/.bitwize-music/venv/bin/playwright install chromium
```

The MCP server automatically detects and uses `~/.bitwize-music/venv` if it exists. No manual configuration needed.

**Alternative: User install (externally-managed Python)**

```bash
pip install --user "mcp[cli]>=1.2.0" pyyaml
```

**Alternative: System install (user-managed Python)**

```bash
pip install -r requirements.txt
```

After installing, **restart Claude Code** to reload the plugin.

## Tools Available (30)

### Albums & Tracks
| Tool | Description |
|------|-------------|
| `find_album(name)` | Find album by name with fuzzy matching (auto-rebuilds if stale) |
| `list_albums(status_filter?)` | List all albums with summary info |
| `get_track(album_slug, track_slug)` | Get specific track details |
| `list_tracks(album_slug)` | List all tracks for an album |
| `get_album_progress(album_slug)` | Progress breakdown with phase detection |
| `get_album_full(album_slug, include_sections?)` | Combined album + track content query (eliminates N+1) |
| `get_pending_verifications()` | Get tracks needing source verification |
| `search(query, scope?)` | Full-text search across albums/tracks/ideas |

### Paths & Files
| Tool | Description |
|------|-------------|
| `resolve_path(path_type, album_slug, genre?)` | Resolve content/audio/documents/tracks/overrides path |
| `resolve_track_file(album_slug, track_slug)` | Find track file path with metadata |
| `list_track_files(album_slug, status_filter?)` | List tracks with file paths and status filtering |
| `extract_section(album_slug, track_slug, section)` | Extract section from track markdown (lyrics, style, etc.) |
| `update_track_field(album_slug, track_slug, field, value)` | Update metadata field in track file |
| `load_override(override_name)` | Load user override file by name from overrides directory |
| `get_reference(name, section?)` | Read plugin reference file with optional section extraction |
| `format_for_clipboard(album_slug, track_slug, content_type)` | Extract and format track content for clipboard |
| `extract_links(album_slug, file_name?)` | Extract markdown links from SOURCES.md, RESEARCH.md, or track files |

### Text Analysis
| Tool | Description |
|------|-------------|
| `check_homographs(text)` | Scan lyrics for homograph pronunciation risks |
| `scan_artist_names(text)` | Check text against artist name blocklist |
| `check_explicit_content(text)` | Scan lyrics for explicit/profane words with override support |
| `check_pronunciation_enforcement(album_slug, track_slug)` | Verify pronunciation notes applied in lyrics |
| `get_lyrics_stats(album_slug, track_slug?)` | Word/char counts with genre target comparison |

### Validation & Structure
| Tool | Description |
|------|-------------|
| `validate_album_structure(album_slug, checks?)` | Structural validation of album directories and files |
| `create_album_structure(album_slug, genre, documentary?)` | Create new album directory with templates |
| `run_pre_generation_gates(album_slug, track_slug?)` | Run all 6 pre-generation validation gates |

### Session & Config
| Tool | Description |
|------|-------------|
| `get_session()` | Get current session context |
| `update_session(album?, track?, phase?, action?, clear?)` | Update session context |
| `get_config()` | Get resolved configuration paths |
| `get_ideas(status_filter?)` | Get album ideas with counts |
| `rebuild_state()` | Force full rebuild from markdown files |

## Usage

The server starts automatically when the plugin is enabled. It uses stdio transport.

### Manual Testing

```bash
# From plugin root
python3 servers/bitwize-music-server/server.py
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
