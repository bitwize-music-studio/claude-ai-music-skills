# State Cache Indexer

Scans all markdown files and produces a JSON state cache at `~/.bitwize-music/cache/state.json`.

Markdown files remain the source of truth. State is a **cache** that can always be rebuilt.

## Why

Every session previously reconstructed all project state from scratch by scanning markdown files (50-220+ file reads). The state cache reduces this to 1-2 file reads.

## Commands

```bash
# Full rebuild from all markdown files
python -m tools.state.indexer rebuild

# Incremental update (only re-parse changed files)
python -m tools.state.indexer update

# Validate state.json against schema
python -m tools.state.indexer validate

# Pretty-print state summary
python -m tools.state.indexer show
python -m tools.state.indexer show -v    # Include track details
```

## Cache Location

Always at `~/.bitwize-music/cache/state.json` (not configurable).

## Schema

See `state.json` after running `rebuild` for the full structure. Key sections:

- **config** - Resolved paths and artist name from config
- **albums** - All albums with their tracks, statuses, and metadata
- **ideas** - IDEAS.md parsed into structured data with status counts
- **session** - Last working context (album, track, phase, pending actions)

## Schema Versioning

The `version` field uses semver. On plugin upgrades:

- **Patch bump** (1.0.0 → 1.0.1): Use as-is
- **Minor bump** (1.0.0 → 1.1.0): Auto-migrate (add new fields with defaults)
- **Major bump** (1.x → 2.0.0): Full rebuild from markdown files
- **Corrupted JSON**: Backup + full rebuild

## Tests

```bash
# Unit tests for parsers
python -m pytest tools/state/tests/test_parsers.py -v

# Integration tests for indexer
python -m pytest tools/state/tests/test_indexer.py -v

# All state tests
python -m pytest tools/state/tests/ -v
```

## Dependencies

- Python 3.8+
- PyYAML (`pip install pyyaml`)
- pytest (for tests only)
