#!/usr/bin/env python3
"""
Integration tests for state cache indexer.

Tests rebuild, update, validate, and schema versioning.

Usage:
    python -m pytest tools/state/tests/test_indexer.py -v
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import yaml
from tools.state.indexer import (
    CURRENT_VERSION,
    _version_compare,
    build_config_section,
    build_state,
    cmd_cleanup,
    cmd_rebuild,
    cmd_session,
    cmd_show,
    cmd_update,
    cmd_validate,
    incremental_update,
    migrate_state,
    read_state,
    validate_state,
    write_state,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with config and content."""
    tmpdir = tempfile.mkdtemp()
    # Resolve symlinks (macOS /var -> /private/var) so paths match resolve_path() output
    tmpdir = str(Path(tmpdir).resolve())
    content_root = Path(tmpdir) / "content"
    config_dir = Path(tmpdir) / "config"
    cache_dir = Path(tmpdir) / "cache"

    # Create directory structure
    album_dir = content_root / "artists" / "testartist" / "albums" / "electronic" / "test-album"
    tracks_dir = album_dir / "tracks"
    tracks_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    # Copy fixtures
    shutil.copy(FIXTURES_DIR / "album-readme.md", album_dir / "README.md")
    shutil.copy(FIXTURES_DIR / "track-file.md", tracks_dir / "01-boot-sequence.md")
    shutil.copy(FIXTURES_DIR / "track-not-started.md", tracks_dir / "04-kernel-panic.md")
    shutil.copy(FIXTURES_DIR / "ideas.md", content_root / "IDEAS.md")

    # Create config
    config_path = config_dir / "config.yaml"
    config = {
        'artist': {'name': 'testartist'},
        'paths': {
            'content_root': str(content_root),
            'audio_root': str(content_root / 'audio'),
            'documents_root': str(content_root / 'documents'),
        },
    }
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    # Override module-level paths so all tests use temp dirs
    import tools.state.indexer as _indexer
    _orig_cache_dir = _indexer.CACHE_DIR
    _orig_state_file = _indexer.STATE_FILE
    _orig_config_file = _indexer.CONFIG_FILE
    _orig_lock_file = _indexer.LOCK_FILE
    _indexer.CACHE_DIR = Path(cache_dir)
    _indexer.STATE_FILE = Path(cache_dir) / "state.json"
    _indexer.CONFIG_FILE = Path(config_path)
    _indexer.LOCK_FILE = Path(cache_dir) / "state.lock"

    yield {
        'tmpdir': tmpdir,
        'content_root': content_root,
        'config_path': config_path,
        'config': config,
        'cache_dir': cache_dir,
        'album_dir': album_dir,
        'tracks_dir': tracks_dir,
    }

    # Restore module-level paths
    _indexer.CACHE_DIR = _orig_cache_dir
    _indexer.STATE_FILE = _orig_state_file
    _indexer.CONFIG_FILE = _orig_config_file
    _indexer.LOCK_FILE = _orig_lock_file

    # Cleanup
    shutil.rmtree(tmpdir)


class TestBuildState:
    """Tests for build_state()."""

    def test_build_state_structure(self, temp_workspace):
        config = temp_workspace['config']
        state = build_state(config)

        assert 'version' in state
        assert state['version'] == CURRENT_VERSION
        assert 'generated_at' in state
        assert 'config' in state
        assert 'albums' in state
        assert 'ideas' in state
        assert 'session' in state

    def test_build_state_albums(self, temp_workspace):
        config = temp_workspace['config']
        state = build_state(config)

        albums = state['albums']
        assert 'test-album' in albums

        album = albums['test-album']
        assert album['title'] == 'Sample Album'
        assert album['status'] == 'In Progress'
        assert album['genre'] == 'electronic'
        assert album['explicit'] is True
        assert album['track_count'] == 8
        assert 'tracks' in album

    def test_build_state_tracks(self, temp_workspace):
        config = temp_workspace['config']
        state = build_state(config)

        tracks = state['albums']['test-album']['tracks']
        assert '01-boot-sequence' in tracks
        assert '04-kernel-panic' in tracks

        boot = tracks['01-boot-sequence']
        assert boot['status'] == 'Final'
        assert boot['has_suno_link'] is True
        assert boot['explicit'] is True

        kernel = tracks['04-kernel-panic']
        assert kernel['status'] == 'Not Started'
        assert kernel['has_suno_link'] is False

    def test_build_state_ideas(self, temp_workspace):
        config = temp_workspace['config']
        state = build_state(config)

        ideas = state['ideas']
        assert ideas['counts'].get('Pending', 0) == 2
        assert ideas['counts'].get('In Progress', 0) == 1
        assert len(ideas['items']) == 4

    def test_build_state_config_section(self, temp_workspace):
        config = temp_workspace['config']
        state = build_state(config)

        cfg = state['config']
        assert cfg['artist_name'] == 'testartist'
        assert cfg['content_root'] == str(temp_workspace['content_root'])

    def test_build_state_no_albums(self):
        """Build state when content root has no albums."""
        tmpdir = tempfile.mkdtemp()
        content_root = Path(tmpdir)
        config = {
            'artist': {'name': 'nobody'},
            'paths': {'content_root': str(content_root)},
        }
        state = build_state(config)
        assert state['albums'] == {}
        shutil.rmtree(tmpdir)


class TestIncrementalUpdate:
    """Tests for incremental_update()."""

    def test_unchanged_files(self, temp_workspace):
        """Incremental update with no changes returns same data."""
        config = temp_workspace['config']
        state = build_state(config)

        updated = incremental_update(state, config)

        assert len(updated['albums']) == len(state['albums'])
        assert updated['albums']['test-album']['status'] == 'In Progress'

    def test_modified_track(self, temp_workspace):
        """Modifying a track file triggers re-parse of that track."""
        config = temp_workspace['config']
        state = build_state(config)

        # Modify a track file
        track_path = temp_workspace['tracks_dir'] / "04-kernel-panic.md"
        content = track_path.read_text()
        content = content.replace('| **Status** | Not Started |', '| **Status** | In Progress |')
        # Ensure mtime changes
        import time
        time.sleep(0.05)
        track_path.write_text(content)

        updated = incremental_update(state, config)
        track = updated['albums']['test-album']['tracks']['04-kernel-panic']
        assert track['status'] == 'In Progress'

    def test_new_track_added(self, temp_workspace):
        """Adding a new track file is picked up."""
        config = temp_workspace['config']
        state = build_state(config)

        # Add a new track
        new_track = temp_workspace['tracks_dir'] / "02-fork-the-world.md"
        new_track.write_text("""# Fork the World

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Fork the World |
| **Status** | Generated |
| **Suno Link** | [Listen](https://suno.com/song/def456) |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")

        updated = incremental_update(state, config)
        assert '02-fork-the-world' in updated['albums']['test-album']['tracks']

    def test_deleted_track(self, temp_workspace):
        """Deleting a track file removes it from state."""
        config = temp_workspace['config']
        state = build_state(config)
        assert '04-kernel-panic' in state['albums']['test-album']['tracks']

        # Delete track
        (temp_workspace['tracks_dir'] / "04-kernel-panic.md").unlink()

        # Force README mtime change to trigger rescan
        readme = temp_workspace['album_dir'] / "README.md"
        import time
        time.sleep(0.05)
        readme.write_text(readme.read_text())

        updated = incremental_update(state, config)
        assert '04-kernel-panic' not in updated['albums']['test-album']['tracks']


class TestValidateState:
    """Tests for validate_state()."""

    def test_valid_state(self, temp_workspace):
        config = temp_workspace['config']
        state = build_state(config)
        errors = validate_state(state)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_top_level_keys(self):
        state = {'version': '1.0.0'}
        errors = validate_state(state)
        assert any('Missing top-level keys' in e for e in errors)

    def test_missing_config_fields(self):
        state = {
            'version': '1.0.0',
            'generated_at': '2026-01-01',
            'config': {},
            'albums': {},
            'ideas': {'counts': {}, 'items': []},
            'session': {},
        }
        errors = validate_state(state)
        assert any('config.content_root' in e for e in errors)

    def test_not_a_dict(self):
        errors = validate_state("not a dict")
        assert errors == ["State is not a dict"]


class TestMigrateState:
    """Tests for migrate_state()."""

    def test_current_version_no_migration(self):
        state = {'version': CURRENT_VERSION}
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == CURRENT_VERSION

    def test_newer_version_triggers_rebuild(self):
        state = {'version': '99.0.0'}
        result = migrate_state(state)
        assert result is None

    def test_missing_version_triggers_rebuild(self):
        state = {}
        result = migrate_state(state)
        # 0.0.0 major differs from 1.x, triggers rebuild
        assert result is None

    def test_major_version_change_triggers_rebuild(self):
        state = {'version': '2.0.0'}
        result = migrate_state(state)
        assert result is None


class TestWriteState:
    """Tests for write_state()."""

    def test_atomic_write(self, temp_workspace):
        """State file is written atomically."""
        import tools.state.indexer as indexer

        # Temporarily override cache paths
        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = {'version': '1.0.0', 'test': True}
            write_state(state)

            assert indexer.STATE_FILE.exists()
            with open(indexer.STATE_FILE) as f:
                loaded = json.load(f)
            assert loaded['test'] is True

            # No temp file left behind
            assert not indexer.STATE_FILE.with_suffix('.tmp').exists()
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file


class TestScriptInvocation:
    """Regression tests: indexer.py must be runnable as a script."""

    def test_script_help(self):
        """python3 tools/state/indexer.py --help must exit 0."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "state" / "indexer.py"), "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "rebuild" in result.stdout

    def test_module_help(self):
        """python3 -m tools.state.indexer --help must exit 0."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.state.indexer", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"Module failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "rebuild" in result.stdout

    def test_package_help(self):
        """python3 -m tools.state --help must exit 0."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.state", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"Package failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "rebuild" in result.stdout


class TestSessionCommand:
    """Tests for cmd_session()."""

    def test_session_set_album(self, temp_workspace):
        """Session command sets album in state."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            # Write initial state
            config = temp_workspace['config']
            state = build_state(config)
            write_state(state)

            # Run session command
            args = argparse.Namespace(
                album='test-album', track=None, phase='Writing',
                add_action=None, clear=False
            )
            result = cmd_session(args)
            assert result == 0

            # Verify
            updated = read_state()
            assert updated['session']['last_album'] == 'test-album'
            assert updated['session']['last_phase'] == 'Writing'
            assert updated['session']['updated_at'] is not None
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_session_add_action(self, temp_workspace):
        """Session command appends pending actions."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            write_state(state)

            args = argparse.Namespace(
                album='test-album', track=None, phase=None,
                add_action='Complete lyrics for track 05', clear=False
            )
            cmd_session(args)

            updated = read_state()
            assert 'Complete lyrics for track 05' in updated['session']['pending_actions']
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_session_clear(self, temp_workspace):
        """Session --clear resets all session data."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            state['session'] = {
                'last_album': 'old-album',
                'last_track': '01-old',
                'last_phase': 'Mastering',
                'pending_actions': ['something'],
                'updated_at': '2026-01-01',
            }
            write_state(state)

            args = argparse.Namespace(
                album=None, track=None, phase=None,
                add_action=None, clear=True
            )
            cmd_session(args)

            updated = read_state()
            assert updated['session']['last_album'] is None
            assert updated['session']['last_track'] is None
            assert updated['session']['pending_actions'] == []
            assert updated['session']['updated_at'] is not None  # updated_at always set
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file


class TestDocumentsRootDefault:
    """Tests for documents_root default derivation."""

    def test_documents_root_derives_from_content_root(self):
        """documents_root should derive from content_root, not CWD."""
        config = {
            'artist': {'name': 'test'},
            'paths': {
                'content_root': '/home/user/music-projects',
                # No documents_root specified
            },
        }
        section = build_config_section(config)
        assert '/home/user/music-projects/documents' in section['documents_root']

    def test_audio_root_derives_from_content_root(self):
        """audio_root should derive from content_root, not CWD."""
        config = {
            'artist': {'name': 'test'},
            'paths': {
                'content_root': '/home/user/music-projects',
                # No audio_root specified
            },
        }
        section = build_config_section(config)
        assert '/home/user/music-projects/audio' in section['audio_root']

    def test_explicit_documents_root_preserved(self):
        """Explicit documents_root should be used as-is."""
        config = {
            'artist': {'name': 'test'},
            'paths': {
                'content_root': '/home/user/music-projects',
                'documents_root': '/mnt/docs',
            },
        }
        section = build_config_section(config)
        assert section['documents_root'] == '/mnt/docs'


class TestVersionCompare:
    """Tests for _version_compare() with variable-length versions."""

    def test_equal_versions(self):
        assert _version_compare("1.0.0", "1.0.0") == 0

    def test_less_than(self):
        assert _version_compare("1.0.0", "1.1.0") == -1

    def test_greater_than(self):
        assert _version_compare("2.0.0", "1.9.9") == 1

    def test_two_part_vs_three_part_equal(self):
        assert _version_compare("1.0", "1.0.0") == 0

    def test_two_part_vs_three_part_less(self):
        assert _version_compare("1.0", "1.0.1") == -1

    def test_four_part_version(self):
        assert _version_compare("1.0.0.0", "1.0.0") == 0

    def test_four_part_version_greater(self):
        assert _version_compare("1.0.0.1", "1.0.0") == 1

    def test_non_numeric_part_treated_as_zero(self):
        assert _version_compare("1.0.beta", "1.0.0") == 0

    def test_single_part(self):
        assert _version_compare("1", "1.0.0") == 0
        assert _version_compare("2", "1.0.0") == 1


class TestCorruptedStateRecovery:
    """Tests for corrupted state.json recovery."""

    def test_read_state_corrupted_json(self, temp_workspace):
        """Corrupted JSON file returns None (triggers rebuild)."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            # Write corrupted JSON
            indexer.STATE_FILE.write_text("{invalid json content, not valid")

            result = read_state()
            assert result is None
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_read_state_truncated_json(self, temp_workspace):
        """Truncated JSON file returns None."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            # Write truncated JSON (simulates crash during write)
            indexer.STATE_FILE.write_text('{"version": "1.0.0", "albums": {')

            result = read_state()
            assert result is None
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_read_state_empty_file(self, temp_workspace):
        """Empty state file returns None."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            indexer.STATE_FILE.write_text("")

            result = read_state()
            assert result is None
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_read_state_missing_file(self, temp_workspace):
        """Missing state file returns None."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "nonexistent.json"

            result = read_state()
            assert result is None
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_read_state_valid_json_not_dict(self, temp_workspace):
        """Valid JSON that isn't a dict (e.g., a list) is still returned."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            # Valid JSON but wrong type - read_state returns it as-is
            indexer.STATE_FILE.write_text('[1, 2, 3]')

            result = read_state()
            # read_state doesn't validate shape, just parses JSON
            assert result == [1, 2, 3]
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_rebuild_after_corruption(self, temp_workspace):
        """Full rebuild produces valid state after corruption."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            # Write corrupted state
            indexer.STATE_FILE.write_text("not json at all")

            # Verify it's corrupted
            assert read_state() is None

            # Rebuild from scratch
            config = temp_workspace['config']
            state = build_state(config)
            write_state(state)

            # Verify recovery
            recovered = read_state()
            assert recovered is not None
            assert recovered['version'] == CURRENT_VERSION
            assert 'test-album' in recovered['albums']
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file


class TestConcurrentStateUpdates:
    """Tests for concurrent state update safety."""

    def test_write_state_creates_cache_dir(self):
        """write_state creates cache directory if missing."""
        import tools.state.indexer as indexer

        tmpdir = tempfile.mkdtemp()
        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE
        original_lock_file = indexer.LOCK_FILE

        try:
            new_cache = Path(tmpdir) / "new_cache_dir"
            indexer.CACHE_DIR = new_cache
            indexer.STATE_FILE = new_cache / "state.json"
            indexer.LOCK_FILE = new_cache / "state.lock"

            assert not new_cache.exists()
            write_state({'version': '1.0.0', 'test': True})
            assert new_cache.exists()
            assert indexer.STATE_FILE.exists()
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file
            indexer.LOCK_FILE = original_lock_file
            shutil.rmtree(tmpdir)

    def test_write_state_no_temp_file_left(self):
        """write_state cleans up temp file after successful write."""
        import tools.state.indexer as indexer

        tmpdir = tempfile.mkdtemp()
        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE
        original_lock_file = indexer.LOCK_FILE

        try:
            indexer.CACHE_DIR = Path(tmpdir)
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"
            indexer.LOCK_FILE = indexer.CACHE_DIR / "state.lock"

            write_state({'version': '1.0.0'})

            tmp_file = indexer.STATE_FILE.with_suffix('.tmp')
            assert not tmp_file.exists()
            assert indexer.STATE_FILE.exists()
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file
            indexer.LOCK_FILE = original_lock_file
            shutil.rmtree(tmpdir)

    def test_sequential_writes_preserve_latest(self):
        """Multiple sequential writes preserve the last written state."""
        import tools.state.indexer as indexer

        tmpdir = tempfile.mkdtemp()
        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE
        original_lock_file = indexer.LOCK_FILE

        try:
            indexer.CACHE_DIR = Path(tmpdir)
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"
            indexer.LOCK_FILE = indexer.CACHE_DIR / "state.lock"

            write_state({'version': '1.0.0', 'value': 'first'})
            write_state({'version': '1.0.0', 'value': 'second'})
            write_state({'version': '1.0.0', 'value': 'third'})

            result = read_state()
            assert result['value'] == 'third'
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file
            indexer.LOCK_FILE = original_lock_file
            shutil.rmtree(tmpdir)


class TestEdgeCaseAlbums:
    """Tests for edge-case album and track scenarios."""

    def test_unicode_album_title(self):
        """Album with unicode characters in title."""
        tmpdir = tempfile.mkdtemp()
        content_root = Path(tmpdir) / "content"
        album_dir = content_root / "artists" / "testartist" / "albums" / "electronic" / "caf\u00e9-beats"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        readme = album_dir / "README.md"
        readme.write_text("""---
title: "Caf\u00e9 Beats"
genres: ["electronic"]
explicit: false
---

# Caf\u00e9 Beats

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 5 |

## Tracklist

| # | Title | Status |
|---|-------|--------|
| 01 | \u00c9clat | Not Started |
| 02 | R\u00e9sum\u00e9 | Not Started |
""", encoding='utf-8')

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        state = build_state(config)
        assert 'caf\u00e9-beats' in state['albums']
        album = state['albums']['caf\u00e9-beats']
        assert album['title'] == 'Caf\u00e9 Beats'
        shutil.rmtree(tmpdir)

    def test_special_characters_in_track_name(self):
        """Track file with special characters."""
        tmpdir = tempfile.mkdtemp()
        content_root = Path(tmpdir) / "content"
        album_dir = content_root / "artists" / "testartist" / "albums" / "rock" / "test-album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        # Album README
        (album_dir / "README.md").write_text("""---
title: "Test Album"
genres: ["rock"]
explicit: false
---

# Test Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Tracks** | 1 |

## Tracklist

| # | Title | Status |
|---|-------|--------|
| 01 | Don't Stop & Won't Stop | In Progress |
""")

        # Track file with apostrophe and ampersand in name
        (tracks_dir / "01-dont-stop-and-wont-stop.md").write_text("""# Don't Stop & Won't Stop

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Don't Stop & Won't Stop |
| **Status** | In Progress |
| **Suno Link** | \u2014 |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        state = build_state(config)
        tracks = state['albums']['test-album']['tracks']
        assert '01-dont-stop-and-wont-stop' in tracks
        assert tracks['01-dont-stop-and-wont-stop']['title'] == "Don't Stop & Won't Stop"
        shutil.rmtree(tmpdir)

    def test_album_with_many_tracks(self):
        """Album with large number of tracks (20+)."""
        tmpdir = tempfile.mkdtemp()
        content_root = Path(tmpdir) / "content"
        album_dir = content_root / "artists" / "testartist" / "albums" / "electronic" / "big-album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        tracklist_rows = []
        for i in range(1, 26):
            num = str(i).zfill(2)
            tracklist_rows.append(f"| {num} | Track {num} | Not Started |")

            (tracks_dir / f"{num}-track-{num}.md").write_text(f"""# Track {num}

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Track {num} |
| **Status** | Not Started |
| **Suno Link** | \u2014 |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")

        tracklist_table = "\n".join(tracklist_rows)
        (album_dir / "README.md").write_text(f"""---
title: "Big Album"
genres: ["electronic"]
explicit: false
---

# Big Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 25 |

## Tracklist

| # | Title | Status |
|---|-------|--------|
{tracklist_table}
""")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        state = build_state(config)
        album = state['albums']['big-album']
        assert album['track_count'] == 25
        assert len(album['tracks']) == 25
        shutil.rmtree(tmpdir)

    def test_malformed_track_missing_table(self):
        """Track file with no details table still returns data."""
        tmpdir = tempfile.mkdtemp()
        track_path = Path(tmpdir) / "01-minimal.md"
        track_path.write_text("# Minimal Track\n\nJust a heading, no table.\n")

        from tools.state.parsers import parse_track_file
        result = parse_track_file(track_path)
        assert '_error' not in result
        assert result['title'] == 'Minimal Track'
        assert result['status'] == 'Unknown'
        shutil.rmtree(tmpdir)

    def test_album_with_empty_tracks_dir(self):
        """Album with tracks/ directory but no .md files."""
        tmpdir = tempfile.mkdtemp()
        content_root = Path(tmpdir) / "content"
        album_dir = content_root / "artists" / "testartist" / "albums" / "rock" / "empty-tracks"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        (album_dir / "README.md").write_text("""---
title: "Empty Tracks"
genres: ["rock"]
explicit: false
---

# Empty Tracks

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 0 |
""")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        state = build_state(config)
        album = state['albums']['empty-tracks']
        assert album['tracks'] == {}
        shutil.rmtree(tmpdir)

    def test_multiple_albums_different_genres(self):
        """Multiple albums across different genres are all found."""
        tmpdir = tempfile.mkdtemp()
        content_root = Path(tmpdir) / "content"

        genres = ['rock', 'electronic', 'hip-hop']
        for genre in genres:
            album_dir = content_root / "artists" / "testartist" / "albums" / genre / f"{genre}-album"
            album_dir.mkdir(parents=True)
            (album_dir / "README.md").write_text(f"""---
title: "{genre.title()} Album"
genres: ["{genre}"]
explicit: false
---

# {genre.title()} Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 3 |
""")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        state = build_state(config)
        assert len(state['albums']) == 3
        assert 'rock-album' in state['albums']
        assert 'electronic-album' in state['albums']
        assert 'hip-hop-album' in state['albums']

        assert state['albums']['rock-album']['genre'] == 'rock'
        assert state['albums']['electronic-album']['genre'] == 'electronic'
        assert state['albums']['hip-hop-album']['genre'] == 'hip-hop'
        shutil.rmtree(tmpdir)


class TestCmdCleanup:
    """Tests for cmd_cleanup() - remove stale albums from cache."""

    def test_cleanup_no_state_file(self, temp_workspace):
        """Returns error when no state file exists."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "nonexistent.json"

            args = argparse.Namespace(dry_run=False)
            result = cmd_cleanup(args)
            assert result == 1
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_cleanup_no_stale_albums(self, temp_workspace):
        """Returns 0 when all album paths exist."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            write_state(state)

            args = argparse.Namespace(dry_run=False)
            result = cmd_cleanup(args)
            assert result == 0

            # State unchanged
            after = read_state()
            assert len(after['albums']) == len(state['albums'])
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_cleanup_removes_stale_album(self, temp_workspace):
        """Removes albums whose paths no longer exist on disk."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            # Inject a fake album with a nonexistent path
            state['albums']['ghost-album'] = {
                'path': '/nonexistent/path/ghost-album',
                'genre': 'electronic',
                'status': 'In Progress',
                'tracks': {},
            }
            write_state(state)

            args = argparse.Namespace(dry_run=False)
            result = cmd_cleanup(args)
            assert result == 0

            after = read_state()
            assert 'ghost-album' not in after['albums']
            assert 'test-album' in after['albums']
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_cleanup_dry_run_preserves_state(self, temp_workspace):
        """Dry run reports but does not remove stale albums."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            state['albums']['ghost-album'] = {
                'path': '/nonexistent/path/ghost-album',
                'genre': 'electronic',
                'status': 'In Progress',
                'tracks': {},
            }
            write_state(state)

            args = argparse.Namespace(dry_run=True)
            result = cmd_cleanup(args)
            assert result == 0

            # State should still have the ghost album
            after = read_state()
            assert 'ghost-album' in after['albums']
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_cleanup_empty_albums(self, temp_workspace):
        """Returns 0 when state has no albums."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            state['albums'] = {}
            write_state(state)

            args = argparse.Namespace(dry_run=False)
            result = cmd_cleanup(args)
            assert result == 0
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file


class TestCmdRebuild:
    """Tests for cmd_rebuild()."""

    def test_rebuild_success(self, temp_workspace):
        """Rebuild creates valid state file."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE
        original_config = indexer.CONFIG_FILE
        original_lock = indexer.LOCK_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"
            indexer.CONFIG_FILE = Path(temp_workspace['config_path'])
            indexer.LOCK_FILE = indexer.CACHE_DIR / "state.lock"

            args = argparse.Namespace()
            result = cmd_rebuild(args)
            assert result in (None, 0)  # success

            state = read_state()
            assert state is not None
            assert 'test-album' in state['albums']
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file
            indexer.CONFIG_FILE = original_config
            indexer.LOCK_FILE = original_lock

    def test_rebuild_no_config(self, temp_workspace):
        """Rebuild returns error when config missing."""
        import tools.state.indexer as indexer

        original_config = indexer.CONFIG_FILE

        try:
            indexer.CONFIG_FILE = Path("/nonexistent/config.yaml")

            args = argparse.Namespace()
            result = cmd_rebuild(args)
            assert result == 1
        finally:
            indexer.CONFIG_FILE = original_config


class TestCmdValidate:
    """Tests for cmd_validate()."""

    def test_validate_valid_state(self, temp_workspace):
        """Validate passes on valid state."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            write_state(state)

            args = argparse.Namespace()
            result = cmd_validate(args)
            assert result == 0
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_validate_no_state(self, temp_workspace):
        """Validate returns error when no state file."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "nonexistent.json"

            args = argparse.Namespace()
            result = cmd_validate(args)
            assert result == 1
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_validate_invalid_state(self, temp_workspace):
        """Validate detects invalid state (missing keys)."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            # Write minimal invalid state
            write_state({'version': '1.0'})

            args = argparse.Namespace()
            result = cmd_validate(args)
            assert result == 1
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file


class TestCmdShow:
    """Tests for cmd_show()."""

    def test_show_valid_state(self, temp_workspace, capsys):
        """Show prints state summary."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            write_state(state)

            args = argparse.Namespace(verbose=False)
            result = cmd_show(args)
            assert result == 0

            captured = capsys.readouterr()
            assert 'Albums' in captured.out
            assert 'test-album' in captured.out
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_show_no_state(self, temp_workspace, capsys):
        """Show returns error when no state file."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "nonexistent.json"

            args = argparse.Namespace(verbose=False)
            result = cmd_show(args)
            assert result == 1
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file

    def test_show_verbose(self, temp_workspace, capsys):
        """Show verbose includes track details."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"

            state = build_state(temp_workspace['config'])
            write_state(state)

            args = argparse.Namespace(verbose=True)
            result = cmd_show(args)
            assert result == 0

            captured = capsys.readouterr()
            assert 'test-album' in captured.out
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file


class TestCmdUpdate:
    """Tests for cmd_update()."""

    def test_update_success(self, temp_workspace):
        """Update succeeds on existing state."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE
        original_config = indexer.CONFIG_FILE
        original_lock = indexer.LOCK_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"
            indexer.CONFIG_FILE = Path(temp_workspace['config_path'])
            indexer.LOCK_FILE = indexer.CACHE_DIR / "state.lock"

            # First build initial state
            state = build_state(temp_workspace['config'])
            write_state(state)

            args = argparse.Namespace()
            result = cmd_update(args)
            assert result in (None, 0)  # success

            updated = read_state()
            assert updated is not None
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file
            indexer.CONFIG_FILE = original_config
            indexer.LOCK_FILE = original_lock

    def test_update_no_config(self, temp_workspace):
        """Update returns error when config missing."""
        import tools.state.indexer as indexer

        original_config = indexer.CONFIG_FILE

        try:
            indexer.CONFIG_FILE = Path("/nonexistent/config.yaml")

            args = argparse.Namespace()
            result = cmd_update(args)
            assert result == 1
        finally:
            indexer.CONFIG_FILE = original_config

    def test_update_no_state_falls_back_to_rebuild(self, temp_workspace):
        """Update with no existing state does a full rebuild."""
        import tools.state.indexer as indexer

        original_cache_dir = indexer.CACHE_DIR
        original_state_file = indexer.STATE_FILE
        original_config = indexer.CONFIG_FILE
        original_lock = indexer.LOCK_FILE

        try:
            indexer.CACHE_DIR = Path(temp_workspace['cache_dir'])
            indexer.STATE_FILE = indexer.CACHE_DIR / "state.json"
            indexer.CONFIG_FILE = Path(temp_workspace['config_path'])
            indexer.LOCK_FILE = indexer.CACHE_DIR / "state.lock"

            # No pre-existing state
            args = argparse.Namespace()
            result = cmd_update(args)
            assert result in (None, 0)  # success

            state = read_state()
            assert state is not None
            assert 'test-album' in state['albums']
        finally:
            indexer.CACHE_DIR = original_cache_dir
            indexer.STATE_FILE = original_state_file
            indexer.CONFIG_FILE = original_config
            indexer.LOCK_FILE = original_lock
