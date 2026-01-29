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
    build_config_section,
    build_state,
    cmd_session,
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

    yield {
        'tmpdir': tmpdir,
        'content_root': content_root,
        'config_path': config_path,
        'config': config,
        'cache_dir': cache_dir,
        'album_dir': album_dir,
        'tracks_dir': tracks_dir,
    }

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
        assert album['title'] == 'Shell No'
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
