#!/usr/bin/env python3
"""Unit tests for plugin-migration version tracking (issue #320).

Covers the separation of "installed version" (``plugin_version``, refreshed
every build for display) from "last-migrated version"
(``last_migrated_version``, only advanced on explicit acknowledgment), plus
the pure helpers that compute and surface pending migrations.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state import indexer
from tools.state.indexer import (
    CURRENT_VERSION,
    build_state,
    carry_migration_tracking,
    get_pending_migrations,
    incremental_update,
    parse_migration_file,
    validate_state,
)


def _minimal_state(**overrides):
    state = {
        'version': CURRENT_VERSION,
        'generated_at': '2026-01-01T00:00:00+00:00',
        'plugin_version': "0.91.0",
        'config': {
            'content_root': '/tmp/content',
            'audio_root': '/tmp/audio',
            'overrides_dir': '/tmp/content/overrides',
            'artist_name': 'testartist',
            'config_mtime': 1000.0,
        },
        'albums': {},
        'ideas': {'counts': {}, 'items': [], 'file_mtime': 0.0},
        'skills': {'skills_root': '', 'skills_root_mtime': 0.0,
                   'count': 0, 'model_counts': {}, 'items': {}},
        'session': {'last_album': None, 'last_track': None, 'last_phase': None,
                    'pending_actions': [], 'updated_at': None},
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plugin_root(tmp_path, version, migration_versions):
    """Create a fake plugin root with plugin.json and migration files.

    Args:
        tmp_path: pytest tmp_path.
        version: version string for .claude-plugin/plugin.json.
        migration_versions: iterable of version strings; one migration
            file is written per version (named ``<version>.md``).

    Returns:
        Path to the fake plugin root.
    """
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "bitwize-music", "version": version})
    )
    mdir = root / "migrations"
    mdir.mkdir()
    # A README that must always be ignored by the scanner.
    (mdir / "README.md").write_text("# Migrations\n")
    for ver in migration_versions:
        (mdir / f"{ver}.md").write_text(
            f'---\n'
            f'version: "{ver}"\n'
            f'summary: "Changes for {ver}"\n'
            f'categories:\n'
            f'  - config\n'
            f'actions:\n'
            f'  - type: info\n'
            f'    description: "noop"\n'
            f'---\n\n'
            f'Body for {ver}.\n'
        )
    return root


def _make_content_root(tmp_path):
    """Create a minimal content root (no albums) and return a config dict."""
    content_root = tmp_path / "content"
    content_root.mkdir()
    return {
        'artist': {'name': 'testartist'},
        'paths': {'content_root': str(content_root)},
    }


# ---------------------------------------------------------------------------
# build_state / incremental_update field behavior
# ---------------------------------------------------------------------------

class TestBuildStateSeedsLastMigrated:
    """A fresh build seeds last_migrated_version to the installed version."""

    def test_build_state_seeds_last_migrated_to_installed(self, tmp_path, monkeypatch):
        config = _make_content_root(tmp_path)
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)
        monkeypatch.setattr(indexer, '_read_plugin_version', lambda root: "0.91.0")

        state = build_state(config)

        assert state['last_migrated_version'] == "0.91.0"
        assert state['plugin_version'] == "0.91.0"


class TestIncrementalUpdatePreservesLastMigrated:
    """Incremental update must NOT clobber last_migrated_version."""

    def test_incremental_update_preserves_last_migrated(self, tmp_path, monkeypatch):
        config = _make_content_root(tmp_path)
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)
        # Build at an "old" installed version, then simulate an upgrade.
        monkeypatch.setattr(indexer, '_read_plugin_version', lambda root: "0.50.0")
        existing = build_state(config)
        assert existing['last_migrated_version'] == "0.50.0"

        # Plugin upgraded to 0.91.0 — incremental update refreshes the
        # installed-version display field but leaves last_migrated alone.
        monkeypatch.setattr(indexer, '_read_plugin_version', lambda root: "0.91.0")
        updated = incremental_update(existing, config)

        assert updated['last_migrated_version'] == "0.50.0"
        assert updated['plugin_version'] == "0.91.0"

    def test_incremental_update_preserves_none(self, tmp_path, monkeypatch):
        config = _make_content_root(tmp_path)
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)
        monkeypatch.setattr(indexer, '_read_plugin_version', lambda root: "0.91.0")
        existing = build_state(config)
        # Simulate a legacy state written before the field existed.
        del existing['last_migrated_version']

        updated = incremental_update(existing, config)

        assert updated.get('last_migrated_version') is None


# ---------------------------------------------------------------------------
# carry_migration_tracking
# ---------------------------------------------------------------------------

class TestCarryMigrationTracking:
    """A full rebuild over an existing state must not silently acknowledge."""

    def test_no_existing_state_keeps_seed(self):
        new = {'last_migrated_version': "0.91.0"}
        result = carry_migration_tracking(new, None)
        assert result['last_migrated_version'] == "0.91.0"

    def test_existing_value_is_carried(self):
        new = {'last_migrated_version': "0.91.0"}  # build_state's installed seed
        existing = {'last_migrated_version': "0.59.0"}
        result = carry_migration_tracking(new, existing)
        assert result['last_migrated_version'] == "0.59.0"

    def test_existing_without_field_carries_none(self):
        # A pre-field legacy state must keep migrations visible, not be
        # silently marked current by a rebuild.
        new = {'last_migrated_version': "0.91.0"}
        existing = {'plugin_version': "0.91.0"}  # no last_migrated_version key
        result = carry_migration_tracking(new, existing)
        assert result['last_migrated_version'] is None


# ---------------------------------------------------------------------------
# parse_migration_file
# ---------------------------------------------------------------------------

class TestParseMigrationFile:
    def test_valid_file(self, tmp_path):
        root = _make_plugin_root(tmp_path, "0.91.0", ["0.90.0"])
        parsed = parse_migration_file(root / "migrations" / "0.90.0.md")
        assert parsed is not None
        assert parsed['version'] == "0.90.0"
        assert parsed['summary'] == "Changes for 0.90.0"
        assert parsed['categories'] == ["config"]
        assert parsed['actions'] == [{"type": "info", "description": "noop"}]
        assert "Body for 0.90.0" in parsed['body']

    def test_no_frontmatter_returns_none(self, tmp_path):
        f = tmp_path / "x.md"
        f.write_text("# Just a heading, no frontmatter\n")
        assert parse_migration_file(f) is None

    def test_malformed_yaml_returns_none(self, tmp_path):
        f = tmp_path / "x.md"
        f.write_text("---\nversion: : : broken\n  - bad\n---\nbody\n")
        assert parse_migration_file(f) is None

    def test_missing_version_falls_back_to_filename(self, tmp_path):
        f = tmp_path / "0.77.0.md"
        f.write_text('---\nsummary: "no version field"\n---\nbody\n')
        parsed = parse_migration_file(f)
        assert parsed is not None
        assert parsed['version'] == "0.77.0"


# ---------------------------------------------------------------------------
# get_pending_migrations
# ---------------------------------------------------------------------------

class TestGetPendingMigrations:
    def test_upgrade_surfaces_only_newer(self, tmp_path):
        # Issue #320's exact acceptance scenario.
        root = _make_plugin_root(tmp_path, "0.90.0", ["0.59.0", "0.90.0"])
        result = get_pending_migrations({'last_migrated_version': "0.89.0"}, root)
        versions = [m['version'] for m in result['pending']]
        assert versions == ["0.90.0"]
        assert result['reason'] == "upgrade"
        assert result['installed_version'] == "0.90.0"
        assert result['last_migrated_version'] == "0.89.0"

    def test_current_has_no_pending(self, tmp_path):
        root = _make_plugin_root(tmp_path, "0.90.0", ["0.59.0", "0.90.0"])
        result = get_pending_migrations({'last_migrated_version': "0.90.0"}, root)
        assert result['pending'] == []
        assert result['reason'] == "current"

    def test_null_surfaces_full_backlog_sorted(self, tmp_path):
        # Pre-tracking state (the reporter's case): surface everything once.
        root = _make_plugin_root(tmp_path, "0.91.0", ["0.91.0", "0.44.0", "0.59.0"])
        result = get_pending_migrations({'last_migrated_version': None}, root)
        versions = [m['version'] for m in result['pending']]
        assert versions == ["0.44.0", "0.59.0", "0.91.0"]  # ascending
        assert result['reason'] == "untracked"

    def test_absent_field_treated_as_null(self, tmp_path):
        root = _make_plugin_root(tmp_path, "0.91.0", ["0.91.0"])
        result = get_pending_migrations({}, root)
        assert [m['version'] for m in result['pending']] == ["0.91.0"]
        assert result['reason'] == "untracked"

    def test_migrations_newer_than_installed_excluded(self, tmp_path):
        # A migration file ahead of the installed version is never surfaced.
        root = _make_plugin_root(tmp_path, "0.90.0", ["0.90.0", "0.99.0"])
        result = get_pending_migrations({'last_migrated_version': "0.89.0"}, root)
        versions = [m['version'] for m in result['pending']]
        assert versions == ["0.90.0"]

    def test_installed_version_unreadable_returns_empty(self, tmp_path):
        # No plugin.json → cannot compare → no pending (and no crash).
        root = tmp_path / "plugin"
        (root / "migrations").mkdir(parents=True)
        result = get_pending_migrations({'last_migrated_version': None}, root)
        assert result['pending'] == []
        assert result['installed_version'] is None
        assert result['reason'] == 'unknown'


# ---------------------------------------------------------------------------
# validate_state
# ---------------------------------------------------------------------------

class TestValidateLastMigratedVersion:
    def test_valid_string_ok(self):
        assert validate_state(_minimal_state(last_migrated_version="0.91.0")) == []

    def test_null_ok(self):
        assert validate_state(_minimal_state(last_migrated_version=None)) == []

    def test_absent_ok(self):
        # Legacy states without the field must still validate.
        state = _minimal_state()
        state.pop('last_migrated_version', None)
        assert validate_state(state) == []

    def test_wrong_type_rejected(self):
        errors = validate_state(_minimal_state(last_migrated_version=123))
        assert any('last_migrated_version' in e for e in errors)
