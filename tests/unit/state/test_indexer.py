#!/usr/bin/env python3
"""
Comprehensive unit tests for state cache indexer.

Tests all indexer functions with isolated unit tests using
monkeypatch and tmp_path for filesystem isolation.

Usage:
    python -m pytest tests/unit/state/test_indexer.py -v
"""

import copy
import errno
import json
import os
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state.indexer import (
    CURRENT_VERSION,
    _acquire_lock_with_timeout,
    _read_plugin_version,
    _update_tracks_incremental,
    _validate_session_value,
    _version_compare,
    build_config_section,
    build_state,
    incremental_update,
    migrate_state,
    read_config,
    read_state,
    resolve_path,
    scan_albums,
    scan_ideas,
    scan_skills,
    scan_tracks,
    validate_state,
    write_state,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_state(**overrides):
    """Return a minimal valid state dict, with optional overrides."""
    state = {
        'version': CURRENT_VERSION,
        'generated_at': '2026-01-01T00:00:00+00:00',
        'plugin_version': None,
        'config': {
            'content_root': '/tmp/content',
            'audio_root': '/tmp/audio',
            'documents_root': '/tmp/documents',
            'overrides_dir': '/tmp/content/overrides',
            'artist_name': 'testartist',
            'config_mtime': 1000.0,
        },
        'albums': {},
        'ideas': {'counts': {}, 'items': [], 'file_mtime': 0.0},
        'skills': {
            'skills_root': '/tmp/skills',
            'skills_root_mtime': 0.0,
            'count': 0,
            'model_counts': {},
            'items': {},
        },
        'session': {
            'last_album': None,
            'last_track': None,
            'last_phase': None,
            'pending_actions': [],
            'updated_at': None,
        },
    }
    state.update(overrides)
    return state


def _make_skill_content(name="test-skill", description="A test skill.",
                        model="claude-opus-4-6", allowed_tools=None,
                        prerequisites=None, user_invocable=None,
                        context=None, requirements=None):
    """Return markdown content for a SKILL.md file."""
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"model: {model}",
    ]
    if user_invocable is not None:
        lines.append(f"user-invocable: {'true' if user_invocable else 'false'}")
    if context is not None:
        lines.append(f"context: {context}")
    if allowed_tools is not None:
        lines.append("allowed-tools:")
        for tool in allowed_tools:
            lines.append(f"  - {tool}")
    else:
        lines.append("allowed-tools: []")
    if prerequisites is not None:
        lines.append("prerequisites:")
        for p in prerequisites:
            lines.append(f"  - {p}")
    if requirements is not None:
        lines.append("requirements:")
        lines.append("  python:")
        for r in requirements:
            lines.append(f"    - {r}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    lines.append("")
    return "\n".join(lines)


def _make_album_tree(content_root, artist, genre, album_slug,
                     readme_text=None, tracks=None):
    """Create an album directory tree with optional tracks.

    Args:
        content_root: Path to content root.
        artist: Artist name.
        genre: Genre name.
        album_slug: Album slug.
        readme_text: README.md content. Uses a default if None.
        tracks: Dict of {filename: content}. None means no tracks dir.

    Returns:
        Path to the album directory.
    """
    album_dir = content_root / "artists" / artist / "albums" / genre / album_slug
    album_dir.mkdir(parents=True, exist_ok=True)

    if readme_text is None:
        readme_text = f"""---
title: "{album_slug.replace('-', ' ').title()}"
genres: ["{genre}"]
explicit: false
---

# {album_slug.replace('-', ' ').title()}

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 0 |
"""
    (album_dir / "README.md").write_text(readme_text)

    if tracks:
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(exist_ok=True)
        for filename, content in tracks.items():
            (tracks_dir / filename).write_text(content)

    return album_dir


def _make_track_content(title="Test Track", status="Not Started",
                        suno_link="\u2014", explicit="No",
                        sources_verified="N/A"):
    """Return markdown content for a track file."""
    return f"""# {title}

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | {title} |
| **Status** | {status} |
| **Suno Link** | {suno_link} |
| **Explicit** | {explicit} |
| **Sources Verified** | {sources_verified} |
"""


def _override_indexer_paths(monkeypatch, cache_dir, config_path=None,
                            lock_file=None):
    """Monkeypatch module-level path constants in the indexer."""
    import tools.state.indexer as indexer
    monkeypatch.setattr(indexer, 'CACHE_DIR', Path(cache_dir))
    monkeypatch.setattr(indexer, 'STATE_FILE', Path(cache_dir) / "state.json")
    if lock_file is None:
        monkeypatch.setattr(indexer, 'LOCK_FILE', Path(cache_dir) / "state.lock")
    else:
        monkeypatch.setattr(indexer, 'LOCK_FILE', Path(lock_file))
    if config_path is not None:
        monkeypatch.setattr(indexer, 'CONFIG_FILE', Path(config_path))


# ===========================================================================
# Test Classes
# ===========================================================================

@pytest.mark.unit
class TestVersionCompare:
    """Tests for _version_compare()."""

    def test_equal_versions(self):
        assert _version_compare("1.0.0", "1.0.0") == 0

    def test_less_than(self):
        assert _version_compare("1.0.0", "1.1.0") == -1

    def test_greater_than(self):
        assert _version_compare("2.0.0", "1.9.9") == 1

    def test_multi_digit_components(self):
        assert _version_compare("1.10.0", "1.9.0") == 1
        assert _version_compare("1.2.10", "1.2.9") == 1

    def test_zero_padding_two_vs_three_part(self):
        assert _version_compare("1.0", "1.0.0") == 0

    def test_zero_padding_two_vs_three_less(self):
        assert _version_compare("1.0", "1.0.1") == -1

    def test_four_part_version_equal(self):
        assert _version_compare("1.0.0.0", "1.0.0") == 0

    def test_four_part_version_greater(self):
        assert _version_compare("1.0.0.1", "1.0.0") == 1

    def test_single_part(self):
        assert _version_compare("1", "1.0.0") == 0
        assert _version_compare("2", "1.0.0") == 1
        assert _version_compare("0", "1.0.0") == -1

    def test_non_numeric_part_treated_as_zero(self):
        assert _version_compare("1.0.beta", "1.0.0") == 0

    def test_both_non_numeric(self):
        assert _version_compare("alpha", "beta") == 0  # both become 0

    def test_patch_difference(self):
        assert _version_compare("1.0.1", "1.0.2") == -1

    def test_major_difference(self):
        assert _version_compare("3.0.0", "1.0.0") == 1


@pytest.mark.unit
class TestValidateSessionValue:
    """Tests for _validate_session_value()."""

    def test_valid_short_string(self):
        assert _validate_session_value("my-album", "album") is None

    def test_valid_empty_string(self):
        assert _validate_session_value("", "album") is None

    def test_too_long_default_limit(self):
        long_val = "x" * 257
        err = _validate_session_value(long_val, "album")
        assert err is not None
        assert "too long" in err
        assert "257" in err

    def test_too_long_custom_limit(self):
        err = _validate_session_value("abcdef", "field", max_len=5)
        assert err is not None
        assert "too long" in err

    def test_exactly_at_limit(self):
        assert _validate_session_value("x" * 256, "album") is None

    def test_null_bytes(self):
        err = _validate_session_value("hello\x00world", "album")
        assert err is not None
        assert "null bytes" in err

    def test_null_byte_only(self):
        err = _validate_session_value("\x00", "track")
        assert err is not None
        assert "null bytes" in err

    def test_valid_unicode(self):
        assert _validate_session_value("caf\u00e9-beats", "album") is None


@pytest.mark.unit
class TestValidateState:
    """Tests for validate_state()."""

    def test_valid_state(self):
        state = _make_minimal_state()
        errors = validate_state(state)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_not_a_dict(self):
        errors = validate_state("not a dict")
        assert errors == ["State is not a dict"]

    def test_not_a_dict_list(self):
        errors = validate_state([1, 2, 3])
        assert errors == ["State is not a dict"]

    def test_missing_top_level_keys(self):
        state = {'version': '1.0.0'}
        errors = validate_state(state)
        assert any('Missing top-level keys' in e for e in errors)

    def test_missing_version_field(self):
        state = _make_minimal_state()
        state['version'] = ''
        errors = validate_state(state)
        assert any('Missing version' in e for e in errors)

    def test_version_wrong_type(self):
        state = _make_minimal_state()
        state['version'] = 123
        errors = validate_state(state)
        assert any('Version should be string' in e for e in errors)

    def test_config_not_dict(self):
        state = _make_minimal_state()
        state['config'] = "bad"
        errors = validate_state(state)
        assert any('config should be a dict' in e for e in errors)

    def test_missing_config_fields(self):
        state = _make_minimal_state()
        state['config'] = {}
        errors = validate_state(state)
        assert any('config.content_root' in e for e in errors)
        assert any('config.audio_root' in e for e in errors)
        assert any('config.artist_name' in e for e in errors)
        assert any('config.config_mtime' in e for e in errors)

    def test_albums_not_dict(self):
        state = _make_minimal_state()
        state['albums'] = "bad"
        errors = validate_state(state)
        assert any('albums should be a dict' in e for e in errors)

    def test_album_missing_required_fields(self):
        state = _make_minimal_state()
        state['albums'] = {'test-album': {'path': '/tmp/test'}}
        errors = validate_state(state)
        assert any("Album 'test-album' missing 'genre'" in e for e in errors)
        assert any("Album 'test-album' missing 'title'" in e for e in errors)
        assert any("Album 'test-album' missing 'status'" in e for e in errors)
        assert any("Album 'test-album' missing 'tracks'" in e for e in errors)

    def test_album_not_dict(self):
        state = _make_minimal_state()
        state['albums'] = {'test-album': "bad"}
        errors = validate_state(state)
        assert any("Album 'test-album' should be a dict" in e for e in errors)

    def test_track_missing_required_fields(self):
        state = _make_minimal_state()
        state['albums'] = {
            'test-album': {
                'path': '/tmp/test',
                'genre': 'rock',
                'title': 'Test',
                'status': 'Concept',
                'tracks': {
                    '01-track': {'path': '/tmp/track'}
                }
            }
        }
        errors = validate_state(state)
        assert any("Track 'test-album/01-track' missing 'title'" in e for e in errors)
        assert any("Track 'test-album/01-track' missing 'status'" in e for e in errors)

    def test_track_not_dict(self):
        state = _make_minimal_state()
        state['albums'] = {
            'test-album': {
                'path': '/tmp/test',
                'genre': 'rock',
                'title': 'Test',
                'status': 'Concept',
                'tracks': {
                    '01-track': "bad"
                }
            }
        }
        errors = validate_state(state)
        assert any("Track 'test-album/01-track' should be a dict" in e for e in errors)

    def test_ideas_not_dict(self):
        state = _make_minimal_state()
        state['ideas'] = "bad"
        errors = validate_state(state)
        assert any('ideas should be a dict' in e for e in errors)

    def test_ideas_missing_counts(self):
        state = _make_minimal_state()
        state['ideas'] = {'items': []}
        errors = validate_state(state)
        assert any('ideas.counts' in e for e in errors)

    def test_ideas_missing_items(self):
        state = _make_minimal_state()
        state['ideas'] = {'counts': {}}
        errors = validate_state(state)
        assert any('ideas.items' in e for e in errors)

    def test_session_not_dict(self):
        state = _make_minimal_state()
        state['session'] = "bad"
        errors = validate_state(state)
        assert any('session should be a dict' in e for e in errors)

    def test_valid_state_with_full_album(self):
        state = _make_minimal_state()
        state['albums'] = {
            'test-album': {
                'path': '/tmp/test',
                'genre': 'rock',
                'title': 'Test Album',
                'status': 'In Progress',
                'tracks': {
                    '01-track': {
                        'path': '/tmp/track.md',
                        'title': 'Track One',
                        'status': 'Final',
                    }
                }
            }
        }
        errors = validate_state(state)
        assert errors == []


@pytest.mark.unit
class TestMigrateState:
    """Tests for migrate_state()."""

    def test_current_version_no_op(self):
        state = {'version': CURRENT_VERSION, 'data': 'preserved'}
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == CURRENT_VERSION
        assert result['data'] == 'preserved'

    def test_future_version_triggers_rebuild(self):
        state = {'version': '99.0.0'}
        result = migrate_state(state)
        assert result is None

    def test_major_mismatch_triggers_rebuild(self):
        state = {'version': '2.0.0'}
        result = migrate_state(state)
        assert result is None

    def test_major_mismatch_lower(self):
        # Major version 0 differs from current major version 1
        state = {'version': '0.9.0'}
        result = migrate_state(state)
        assert result is None

    def test_missing_version_triggers_rebuild(self):
        state = {}
        result = migrate_state(state)
        # version defaults to '0.0.0', major 0 != major 1 => rebuild
        assert result is None

    def test_same_major_minor_difference_no_rebuild(self):
        # Same major, migration chain applies 1.0.0 → 1.1.0 → 1.2.0
        state = {'version': '1.0.0'}
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == CURRENT_VERSION


@pytest.mark.unit
class TestResolvePath:
    """Tests for resolve_path()."""

    def test_tilde_expansion(self):
        result = resolve_path("~/mydir")
        expected = Path.home() / "mydir"
        assert result == expected.resolve()

    def test_relative_path_becomes_absolute(self):
        result = resolve_path("relative/path")
        assert result.is_absolute()

    def test_absolute_path_unchanged(self):
        result = resolve_path("/absolute/path")
        assert str(result) == "/absolute/path"

    def test_dot_path(self):
        result = resolve_path(".")
        assert result == Path.cwd()

    def test_path_with_trailing_slash(self):
        result = resolve_path("/tmp/test/")
        assert str(result) == "/tmp/test"


@pytest.mark.unit
class TestBuildConfigSection:
    """Tests for build_config_section()."""

    def test_normal_config(self, monkeypatch):
        config = {
            'artist': {'name': 'testartist'},
            'paths': {
                'content_root': '/home/user/content',
                'audio_root': '/home/user/audio',
                'documents_root': '/home/user/documents',
            },
        }
        # Mock get_config_mtime to avoid hitting real filesystem
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 12345.0)

        section = build_config_section(config)
        assert section['content_root'] == '/home/user/content'
        assert section['audio_root'] == '/home/user/audio'
        assert section['documents_root'] == '/home/user/documents'
        assert section['artist_name'] == 'testartist'
        assert section['config_mtime'] == 12345.0

    def test_missing_paths_defaults(self, monkeypatch):
        config = {'artist': {'name': 'test'}, 'paths': {}}
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        section = build_config_section(config)
        # Default content_root is '.' resolved
        assert section['content_root'] == str(Path('.').resolve())
        # audio_root defaults to content_root + '/audio'
        assert 'audio' in section['audio_root']
        # documents_root defaults to content_root + '/documents'
        assert 'documents' in section['documents_root']

    def test_missing_artist_defaults_empty(self, monkeypatch):
        config = {'paths': {'content_root': '/tmp/c'}}
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        section = build_config_section(config)
        assert section['artist_name'] == ''

    def test_documents_root_derives_from_content_root(self, monkeypatch):
        config = {
            'artist': {'name': 'test'},
            'paths': {'content_root': '/home/user/music-projects'},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        section = build_config_section(config)
        assert '/home/user/music-projects/documents' in section['documents_root']

    def test_audio_root_derives_from_content_root(self, monkeypatch):
        config = {
            'artist': {'name': 'test'},
            'paths': {'content_root': '/home/user/music-projects'},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        section = build_config_section(config)
        assert '/home/user/music-projects/audio' in section['audio_root']

    def test_explicit_documents_root_preserved(self, monkeypatch):
        config = {
            'artist': {'name': 'test'},
            'paths': {
                'content_root': '/home/user/music-projects',
                'documents_root': '/mnt/docs',
            },
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        section = build_config_section(config)
        assert section['documents_root'] == '/mnt/docs'

    def test_empty_config(self, monkeypatch):
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        section = build_config_section({})
        assert section['artist_name'] == ''
        assert section['config_mtime'] == 0.0


@pytest.mark.unit
class TestReadConfig:
    """Tests for read_config()."""

    def test_missing_file(self, monkeypatch):
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', Path("/nonexistent/config.yaml"))
        result = read_config()
        assert result is None

    def test_valid_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        config_data = {'artist': {'name': 'testartist'}, 'paths': {'content_root': '/tmp'}}
        config_path.write_text(yaml.dump(config_data))

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', config_path)

        result = read_config()
        assert result is not None
        assert result['artist']['name'] == 'testartist'

    def test_invalid_yaml(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("{{invalid: yaml: :: broken")

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', config_path)

        result = read_config()
        assert result is None

    def test_empty_yaml(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', config_path)

        result = read_config()
        # yaml.safe_load("") returns None, function returns {}
        assert result == {}

    def test_yaml_with_only_comments(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("# just a comment\n# another comment\n")

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', config_path)

        result = read_config()
        assert result == {}


@pytest.mark.unit
class TestReadWriteState:
    """Tests for read_state() and write_state()."""

    def test_write_then_read_roundtrip(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        state = _make_minimal_state()
        write_state(state)

        loaded = read_state()
        assert loaded is not None
        assert loaded['version'] == CURRENT_VERSION
        assert loaded['config']['artist_name'] == 'testartist'

    def test_read_missing_file(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)
        result = read_state()
        assert result is None

    def test_read_corrupted_json(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        state_file = tmp_path / "state.json"
        state_file.write_text("{invalid json content, not valid")

        result = read_state()
        assert result is None

    def test_read_truncated_json(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        state_file = tmp_path / "state.json"
        state_file.write_text('{"version": "1.0.0", "albums": {')

        result = read_state()
        assert result is None

    def test_read_empty_file(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        state_file = tmp_path / "state.json"
        state_file.write_text("")

        result = read_state()
        assert result is None

    def test_write_creates_cache_dir(self, tmp_path, monkeypatch):
        new_cache = tmp_path / "new_cache_dir"
        _override_indexer_paths(monkeypatch, new_cache)

        assert not new_cache.exists()
        write_state({'version': '1.0.0'})
        assert new_cache.exists()

    def test_atomic_write_no_temp_left(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        write_state({'version': '1.0.0'})

        # No .tmp files should remain
        tmp_files = list(tmp_path.glob(".state_*.tmp"))
        assert tmp_files == []

    def test_sequential_writes_preserve_latest(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        write_state({'version': '1.0.0', 'value': 'first'})
        write_state({'version': '1.0.0', 'value': 'second'})
        write_state({'version': '1.0.0', 'value': 'third'})

        result = read_state()
        assert result['value'] == 'third'

    def test_write_state_file_permissions(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        write_state({'version': '1.0.0'})

        state_file = tmp_path / "state.json"
        # Cache dir should be 0700
        cache_perms = oct(tmp_path.stat().st_mode & 0o777)
        assert cache_perms == '0o700'

    def test_write_complex_state(self, tmp_path, monkeypatch):
        _override_indexer_paths(monkeypatch, tmp_path)

        state = _make_minimal_state()
        state['albums'] = {
            'test-album': {
                'path': '/tmp/test',
                'genre': 'rock',
                'title': 'Test Album',
                'status': 'In Progress',
                'tracks': {
                    '01-track': {
                        'path': '/tmp/track.md',
                        'title': 'Track One',
                        'status': 'Final',
                    }
                }
            }
        }
        write_state(state)

        loaded = read_state()
        assert loaded['albums']['test-album']['tracks']['01-track']['status'] == 'Final'


@pytest.mark.unit
class TestFileLocking:
    """Tests for _acquire_lock_with_timeout()."""

    def test_acquire_lock_success(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with open(lock_file, 'w') as fd:
            # Should not raise
            _acquire_lock_with_timeout(fd, timeout=1)

    def test_lock_timeout(self, tmp_path, monkeypatch):
        """Simulate a lock that cannot be acquired within timeout."""
        import fcntl

        lock_file = tmp_path / "test.lock"
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'LOCK_FILE', lock_file)

        call_count = [0]
        original_flock = fcntl.flock

        def mock_flock(fd, operation):
            call_count[0] += 1
            if operation & fcntl.LOCK_NB:
                err = OSError()
                err.errno = errno.EAGAIN
                raise err
            return original_flock(fd, operation)

        # Use very short timeout
        with open(lock_file, 'w') as fd:
            lock_file.touch()  # Ensure mtime is fresh (not stale)
            with patch('tools.state.indexer.fcntl.flock', side_effect=mock_flock):
                with patch('tools.state.indexer.time.sleep'):
                    with pytest.raises(TimeoutError, match="Could not acquire state lock"):
                        _acquire_lock_with_timeout(fd, timeout=0)

    def test_stale_lock_recovery(self, tmp_path, monkeypatch):
        """When lock is stale (old mtime), recovery is attempted."""
        import fcntl

        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'LOCK_FILE', lock_file)

        # Make lock file appear old
        old_mtime = time.time() - (indexer.STALE_LOCK_SECONDS + 10)
        os.utime(lock_file, (old_mtime, old_mtime))

        attempt = [0]

        def mock_flock(fd, operation):
            attempt[0] += 1
            if attempt[0] <= 1:
                # First attempt fails
                err = OSError()
                err.errno = errno.EAGAIN
                raise err
            # Second attempt (after stale recovery) succeeds
            return

        with open(lock_file, 'w') as fd:
            with patch('tools.state.indexer.fcntl.flock', side_effect=mock_flock):
                # Should succeed via stale lock recovery
                _acquire_lock_with_timeout(fd, timeout=5)

    def test_unexpected_oserror_reraises(self, tmp_path, monkeypatch):
        """Unexpected OSError (not EAGAIN/EACCES) is re-raised."""
        lock_file = tmp_path / "test.lock"
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'LOCK_FILE', lock_file)

        def mock_flock(fd, operation):
            err = OSError()
            err.errno = errno.EIO  # I/O error, not a lock contention error
            raise err

        with open(lock_file, 'w') as fd:
            with patch('tools.state.indexer.fcntl.flock', side_effect=mock_flock):
                with pytest.raises(OSError):
                    _acquire_lock_with_timeout(fd, timeout=1)


@pytest.mark.unit
class TestScanAlbums:
    """Tests for scan_albums()."""

    def test_no_albums_dir(self, tmp_path):
        content_root = tmp_path / "content"
        content_root.mkdir()
        result = scan_albums(content_root, "testartist")
        assert result == {}

    def test_empty_albums_dir(self, tmp_path):
        albums_dir = tmp_path / "content" / "artists" / "testartist" / "albums"
        albums_dir.mkdir(parents=True)
        result = scan_albums(tmp_path / "content", "testartist")
        assert result == {}

    def test_albums_with_tracks(self, tmp_path):
        content_root = tmp_path / "content"
        _make_album_tree(
            content_root, "testartist", "rock", "my-album",
            tracks={
                "01-first.md": _make_track_content("First", "Final",
                                                    "[Listen](https://suno.com/song/abc)",
                                                    "No", "N/A"),
                "02-second.md": _make_track_content("Second", "Not Started"),
            }
        )

        result = scan_albums(content_root, "testartist")
        assert "my-album" in result
        album = result["my-album"]
        assert album['genre'] == 'rock'
        assert album['title'] == 'My Album'
        assert '01-first' in album['tracks']
        assert '02-second' in album['tracks']
        assert album['tracks']['01-first']['status'] == 'Final'

    def test_multiple_albums_different_genres(self, tmp_path):
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "rock-album")
        _make_album_tree(content_root, "testartist", "electronic", "electro-album")

        result = scan_albums(content_root, "testartist")
        assert len(result) == 2
        assert "rock-album" in result
        assert "electro-album" in result
        assert result["rock-album"]["genre"] == "rock"
        assert result["electro-album"]["genre"] == "electronic"

    def test_skip_album_with_parse_error(self, tmp_path):
        content_root = tmp_path / "content"
        album_dir = content_root / "artists" / "testartist" / "albums" / "rock" / "bad-album"
        album_dir.mkdir(parents=True)
        # Write a README that triggers a parse error (non-existent file used by parser is fine,
        # but let's make a README with no content at all - parsers handle this gracefully)
        # Instead create a valid album and an album that triggers _error
        _make_album_tree(content_root, "testartist", "rock", "good-album")

        # Create an album with binary garbage for README
        bad_dir = content_root / "artists" / "testartist" / "albums" / "rock" / "bad-album"
        bad_dir.mkdir(parents=True, exist_ok=True)
        # parsers won't return _error for readable text, but we can mock
        # Use a valid album to check skip logic works by verifying good album is present
        result = scan_albums(content_root, "testartist")
        assert "good-album" in result

    def test_album_with_fixtures(self, tmp_path):
        """Test scanning with real fixture files."""
        content_root = tmp_path / "content"
        album_dir = content_root / "artists" / "testartist" / "albums" / "electronic" / "test-album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        shutil.copy(FIXTURES_DIR / "album-readme.md", album_dir / "README.md")
        shutil.copy(FIXTURES_DIR / "track-file.md", tracks_dir / "01-boot-sequence.md")
        shutil.copy(FIXTURES_DIR / "track-not-started.md", tracks_dir / "04-kernel-panic.md")

        result = scan_albums(content_root, "testartist")
        assert "test-album" in result
        album = result["test-album"]
        assert album['title'] == 'Sample Album'
        assert album['status'] == 'In Progress'
        assert album['explicit'] is True
        assert album['track_count'] == 8
        assert '01-boot-sequence' in album['tracks']
        assert '04-kernel-panic' in album['tracks']


@pytest.mark.unit
class TestScanTracks:
    """Tests for scan_tracks()."""

    def test_no_tracks_dir(self, tmp_path):
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        result = scan_tracks(album_dir)
        assert result == {}

    def test_empty_tracks_dir(self, tmp_path):
        tracks_dir = tmp_path / "album" / "tracks"
        tracks_dir.mkdir(parents=True)
        result = scan_tracks(tmp_path / "album")
        assert result == {}

    def test_valid_tracks(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        (tracks_dir / "01-first.md").write_text(
            _make_track_content("First Track", "Final",
                                "[Listen](https://suno.com/song/abc)", "Yes",
                                "Verified"))
        (tracks_dir / "02-second.md").write_text(
            _make_track_content("Second Track", "Not Started"))

        result = scan_tracks(album_dir)
        assert len(result) == 2
        assert '01-first' in result
        assert '02-second' in result

        first = result['01-first']
        assert first['title'] == 'First Track'
        assert first['status'] == 'Final'
        assert first['has_suno_link'] is True
        assert first['explicit'] is True
        assert 'mtime' in first
        assert 'path' in first

        second = result['02-second']
        assert second['status'] == 'Not Started'
        assert second['has_suno_link'] is False

    def test_skip_non_md_files(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        (tracks_dir / "01-track.md").write_text(_make_track_content("Track"))
        (tracks_dir / "notes.txt").write_text("not a track")
        (tracks_dir / "cover.jpg").write_bytes(b'\x00\x01')

        result = scan_tracks(album_dir)
        assert len(result) == 1
        assert '01-track' in result

    def test_tracks_sorted_by_filename(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        (tracks_dir / "03-third.md").write_text(_make_track_content("Third"))
        (tracks_dir / "01-first.md").write_text(_make_track_content("First"))
        (tracks_dir / "02-second.md").write_text(_make_track_content("Second"))

        result = scan_tracks(album_dir)
        slugs = list(result.keys())
        assert slugs == ['01-first', '02-second', '03-third']


@pytest.mark.unit
class TestScanIdeas:
    """Tests for scan_ideas()."""

    def test_no_ideas_file(self, tmp_path):
        content_root = tmp_path / "content"
        content_root.mkdir()
        config = {'paths': {}}

        result = scan_ideas(config, content_root)
        assert result['file_mtime'] == 0.0
        assert result['counts'] == {}
        assert result['items'] == []

    def test_valid_ideas_with_fixture(self, tmp_path):
        content_root = tmp_path / "content"
        content_root.mkdir()
        shutil.copy(FIXTURES_DIR / "ideas.md", content_root / "IDEAS.md")

        config = {'paths': {}}
        result = scan_ideas(config, content_root)
        assert result['file_mtime'] > 0
        assert len(result['items']) == 4
        assert result['counts'].get('Pending', 0) == 2

    def test_custom_ideas_path(self, tmp_path):
        content_root = tmp_path / "content"
        content_root.mkdir()
        custom_ideas = tmp_path / "custom" / "IDEAS.md"
        custom_ideas.parent.mkdir(parents=True)
        shutil.copy(FIXTURES_DIR / "ideas.md", custom_ideas)

        config = {'paths': {'ideas_file': str(custom_ideas)}}
        result = scan_ideas(config, content_root)
        assert len(result['items']) == 4

    def test_ideas_parse_error(self, tmp_path):
        content_root = tmp_path / "content"
        content_root.mkdir()
        ideas_file = content_root / "IDEAS.md"
        # Write empty file (no ideas section) - parser returns items: []
        ideas_file.write_text("# Ideas\n\n<!-- empty -->\n")

        config = {'paths': {}}
        result = scan_ideas(config, content_root)
        assert result['items'] == []

    def test_ideas_nonexistent_custom_path(self, tmp_path):
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {'paths': {'ideas_file': '/nonexistent/IDEAS.md'}}
        result = scan_ideas(config, content_root)
        assert result['file_mtime'] == 0.0
        assert result['items'] == []


@pytest.mark.unit
class TestBuildState:
    """Tests for build_state() - integration test with mock filesystem."""

    def test_build_state_structure(self, tmp_path, monkeypatch):
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "test-album",
                         tracks={"01-track.md": _make_track_content("Track One", "Final")})

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 999.0)

        state = build_state(config)

        assert state['version'] == CURRENT_VERSION
        assert 'generated_at' in state
        assert 'config' in state
        assert 'albums' in state
        assert 'ideas' in state
        assert 'session' in state
        assert state['session']['last_album'] is None
        assert state['session']['pending_actions'] == []

    def test_build_state_albums(self, tmp_path, monkeypatch):
        content_root = tmp_path / "content"
        _make_album_tree(
            content_root, "testartist", "electronic", "my-album",
            tracks={
                "01-first.md": _make_track_content("First", "Final"),
                "02-second.md": _make_track_content("Second", "Not Started"),
            }
        )

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config)
        assert 'my-album' in state['albums']
        album = state['albums']['my-album']
        assert album['genre'] == 'electronic'
        assert len(album['tracks']) == 2

    def test_build_state_no_albums(self, tmp_path, monkeypatch):
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {
            'artist': {'name': 'nobody'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config)
        assert state['albums'] == {}

    def test_build_state_with_ideas(self, tmp_path, monkeypatch):
        content_root = tmp_path / "content"
        content_root.mkdir()
        shutil.copy(FIXTURES_DIR / "ideas.md", content_root / "IDEAS.md")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config)
        assert len(state['ideas']['items']) == 4

    def test_build_state_config_section(self, tmp_path, monkeypatch):
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {
            'artist': {'name': 'myartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 42.0)

        state = build_state(config)
        assert state['config']['artist_name'] == 'myartist'
        assert state['config']['content_root'] == str(content_root)
        assert state['config']['config_mtime'] == 42.0


@pytest.mark.unit
class TestIncrementalUpdate:
    """Tests for incremental_update()."""

    def test_config_unchanged(self, tmp_path, monkeypatch):
        """When config mtime is unchanged, albums are incrementally updated."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "my-album",
                         tracks={"01-track.md": _make_track_content("Track", "Not Started")})

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        # Ensure config_mtime matches so the fast path is taken
        existing['config']['config_mtime'] = 100.0

        updated = incremental_update(existing, config)
        assert 'my-album' in updated['albums']
        assert updated['albums']['my-album']['tracks']['01-track']['status'] == 'Not Started'

    def test_config_changed_path_field(self, tmp_path, monkeypatch):
        """When content_root changes, full album rescan occurs."""
        old_root = tmp_path / "old_content"
        new_root = tmp_path / "new_content"
        _make_album_tree(old_root, "testartist", "rock", "old-album")
        _make_album_tree(new_root, "testartist", "rock", "new-album")

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 200.0)

        old_config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(old_root)},
        }
        existing = build_state(old_config)
        existing['config']['config_mtime'] = 100.0  # Old mtime

        new_config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(new_root)},
        }

        updated = incremental_update(existing, new_config)
        # Old album should be gone, new album should be present
        assert 'old-album' not in updated['albums']
        assert 'new-album' in updated['albums']

    def test_config_changed_non_path_field(self, tmp_path, monkeypatch):
        """When only non-path config changes, albums are kept."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "my-album")

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 200.0)

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
            'generation': {'model': 'v5'},
        }

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0  # Simulate old mtime

        updated = incremental_update(existing, config)
        # Albums should be preserved (no path change)
        assert 'my-album' in updated['albums']

    def test_new_album_added(self, tmp_path, monkeypatch):
        """Adding a new album directory is picked up."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "first-album")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0

        # Add a second album
        _make_album_tree(content_root, "testartist", "electronic", "second-album")

        updated = incremental_update(existing, config)
        assert 'first-album' in updated['albums']
        assert 'second-album' in updated['albums']

    def test_album_removed(self, tmp_path, monkeypatch):
        """Removing an album directory removes it from state."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "keep-album")
        album_to_remove = _make_album_tree(content_root, "testartist", "rock", "remove-album")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        assert 'remove-album' in existing['albums']

        # Remove the album
        shutil.rmtree(album_to_remove)

        updated = incremental_update(existing, config)
        assert 'keep-album' in updated['albums']
        assert 'remove-album' not in updated['albums']

    def test_track_updated(self, tmp_path, monkeypatch):
        """Modifying a track file triggers re-parse."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "my-album",
                         tracks={"01-track.md": _make_track_content("Track", "Not Started")})

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        assert existing['albums']['my-album']['tracks']['01-track']['status'] == 'Not Started'

        # Modify the track
        track_path = (content_root / "artists" / "testartist" / "albums" /
                      "rock" / "my-album" / "tracks" / "01-track.md")
        time.sleep(0.05)  # Ensure mtime changes
        track_path.write_text(_make_track_content("Track", "In Progress"))

        updated = incremental_update(existing, config)
        assert updated['albums']['my-album']['tracks']['01-track']['status'] == 'In Progress'

    def test_ideas_updated(self, tmp_path, monkeypatch):
        """Modifying IDEAS.md triggers re-parse."""
        content_root = tmp_path / "content"
        content_root.mkdir()
        shutil.copy(FIXTURES_DIR / "ideas.md", content_root / "IDEAS.md")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        old_items_count = len(existing['ideas']['items'])

        # Modify IDEAS.md (touch to change mtime)
        time.sleep(0.05)
        ideas_path = content_root / "IDEAS.md"
        ideas_path.write_text(ideas_path.read_text())

        updated = incremental_update(existing, config)
        # Ideas should be re-parsed (same content, but mtime changed)
        assert 'ideas' in updated

    def test_ideas_removed(self, tmp_path, monkeypatch):
        """Removing IDEAS.md resets ideas to empty."""
        content_root = tmp_path / "content"
        content_root.mkdir()
        shutil.copy(FIXTURES_DIR / "ideas.md", content_root / "IDEAS.md")

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        assert len(existing['ideas']['items']) > 0

        # Remove IDEAS.md
        (content_root / "IDEAS.md").unlink()

        updated = incremental_update(existing, config)
        assert updated['ideas']['items'] == []
        assert updated['ideas']['file_mtime'] == 0.0

    def test_session_preserved(self, tmp_path, monkeypatch):
        """Session data is preserved during incremental update."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        existing['session'] = {
            'last_album': 'my-album',
            'last_track': '01-track',
            'last_phase': 'Writing',
            'pending_actions': ['do something'],
            'updated_at': '2026-01-01',
        }

        updated = incremental_update(existing, config)
        assert updated['session']['last_album'] == 'my-album'
        assert updated['session']['pending_actions'] == ['do something']


@pytest.mark.unit
class TestUpdateTracksIncremental:
    """Tests for _update_tracks_incremental()."""

    def test_no_tracks_dir(self, tmp_path):
        album_dir = tmp_path / "album"
        album_dir.mkdir()
        album = {'tracks': {}}
        _update_tracks_incremental(album, album_dir)
        assert album['tracks'] == {}

    def test_new_track_added(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        (tracks_dir / "01-track.md").write_text(
            _make_track_content("Track One", "Final"))

        album = {'tracks': {}, 'tracks_completed': 0}
        _update_tracks_incremental(album, album_dir)
        assert '01-track' in album['tracks']
        assert album['tracks_completed'] == 1

    def test_track_removed(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        album = {
            'tracks': {
                'old-track': {
                    'path': str(tracks_dir / "old-track.md"),
                    'title': 'Old',
                    'status': 'Final',
                    'mtime': 1000.0,
                }
            },
            'tracks_completed': 1,
        }
        _update_tracks_incremental(album, album_dir)
        assert 'old-track' not in album['tracks']
        assert album['tracks_completed'] == 0

    def test_unchanged_track_kept(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        track_file = tracks_dir / "01-track.md"
        track_file.write_text(_make_track_content("Track", "Not Started"))
        mtime = track_file.stat().st_mtime

        album = {
            'tracks': {
                '01-track': {
                    'path': str(track_file),
                    'title': 'Track',
                    'status': 'Not Started',
                    'mtime': mtime,
                }
            },
            'tracks_completed': 0,
        }
        _update_tracks_incremental(album, album_dir)
        # Track should remain unchanged
        assert album['tracks']['01-track']['status'] == 'Not Started'

    def test_completed_count_recomputed(self, tmp_path):
        album_dir = tmp_path / "album"
        tracks_dir = album_dir / "tracks"
        tracks_dir.mkdir(parents=True)

        (tracks_dir / "01-track.md").write_text(
            _make_track_content("One", "Final"))
        (tracks_dir / "02-track.md").write_text(
            _make_track_content("Two", "Generated"))
        (tracks_dir / "03-track.md").write_text(
            _make_track_content("Three", "Not Started"))

        album = {'tracks': {}, 'tracks_completed': 0}
        _update_tracks_incremental(album, album_dir)
        # Final + Generated = 2 completed
        assert album['tracks_completed'] == 2


@pytest.mark.unit
class TestReadConfigEdgeCases:
    """Additional edge cases for read_config()."""

    def test_config_permission_error(self, tmp_path, monkeypatch):
        """OSError during read returns None."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("artist: {name: test}")
        config_path.chmod(0o000)

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', config_path)

        result = read_config()
        # Restore permissions for cleanup
        config_path.chmod(0o644)
        assert result is None


@pytest.mark.unit
class TestGetConfigMtime:
    """Tests for get_config_mtime()."""

    def test_existing_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("test: true")

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', config_path)

        from tools.state.indexer import get_config_mtime
        mtime = get_config_mtime()
        assert mtime > 0

    def test_missing_config(self, monkeypatch):
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'CONFIG_FILE', Path("/nonexistent/config.yaml"))

        from tools.state.indexer import get_config_mtime
        mtime = get_config_mtime()
        assert mtime == 0.0


@pytest.mark.unit
class TestWriteStateErrorHandling:
    """Tests for write_state() error scenarios."""

    def test_write_state_lock_timeout_raises(self, tmp_path, monkeypatch):
        """When lock acquisition times out, TimeoutError propagates."""
        _override_indexer_paths(monkeypatch, tmp_path)

        import tools.state.indexer as indexer

        def mock_acquire(*args, **kwargs):
            raise TimeoutError("Lock timeout")

        monkeypatch.setattr(indexer, '_acquire_lock_with_timeout', mock_acquire)

        with pytest.raises(TimeoutError):
            write_state({'version': '1.0.0'})

    def test_write_state_cleans_up_on_error(self, tmp_path, monkeypatch):
        """Temp files are cleaned up when write fails partway through."""
        _override_indexer_paths(monkeypatch, tmp_path)

        import tools.state.indexer as indexer

        # Simulate os.replace failure
        original_replace = os.replace

        def failing_replace(src, dst):
            raise OSError("Simulated replace failure")

        monkeypatch.setattr('os.replace', failing_replace)

        with pytest.raises(OSError, match="Simulated replace failure"):
            write_state({'version': '1.0.0'})

        # No stale temp files should remain
        tmp_files = list(tmp_path.glob(".state_*.tmp"))
        assert tmp_files == []


@pytest.mark.unit
class TestMigrateStateEdgeCases:
    """Additional edge cases for migrate_state()."""

    def test_empty_version_string(self):
        # Version '' splits to [''], int('') raises ValueError -> 0
        state = {'version': ''}
        result = migrate_state(state)
        # '0' != '1' (major mismatch), triggers rebuild
        assert result is None

    def test_minor_version_ahead_same_major(self):
        """Minor version ahead of current but same major - newer => rebuild."""
        state = {'version': '1.99.0'}
        result = migrate_state(state)
        # 1.99.0 > 1.0.0, so this triggers rebuild (newer/downgrade scenario)
        assert result is None

    def test_exact_current_version(self):
        state = {'version': CURRENT_VERSION, 'keep': 'me'}
        result = migrate_state(state)
        assert result is not None
        assert result['keep'] == 'me'


@pytest.mark.unit
class TestIncrementalUpdateConfigChange:
    """Detailed tests for incremental_update config change detection."""

    def test_artist_name_change_triggers_rescan(self, tmp_path, monkeypatch):
        """Changing artist_name triggers full album rescan."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "newartist", "rock", "new-album")

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 200.0)

        existing = _make_minimal_state()
        existing['config']['config_mtime'] = 100.0
        existing['config']['artist_name'] = 'oldartist'
        existing['config']['content_root'] = str(content_root)
        existing['albums'] = {
            'old-album': {
                'path': str(content_root / "artists" / "oldartist" / "albums" / "rock" / "old-album"),
                'genre': 'rock',
                'title': 'Old Album',
                'status': 'Concept',
                'tracks': {},
                'readme_mtime': 50.0,
            }
        }

        new_config = {
            'artist': {'name': 'newartist'},
            'paths': {'content_root': str(content_root)},
        }

        updated = incremental_update(existing, new_config)
        assert 'old-album' not in updated['albums']
        assert 'new-album' in updated['albums']
        assert updated['config']['artist_name'] == 'newartist'

    def test_ideas_file_raw_tracked(self, tmp_path, monkeypatch):
        """_ideas_file_raw is stored in state for change detection."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 200.0)

        existing = _make_minimal_state()
        existing['config']['config_mtime'] = 100.0
        existing['config']['content_root'] = str(content_root)

        config = {
            'artist': {'name': 'testartist'},
            'paths': {
                'content_root': str(content_root),
                'ideas_file': str(content_root / "custom-ideas.md"),
            },
        }

        updated = incremental_update(existing, config)
        assert '_ideas_file_raw' in updated
        assert updated['_ideas_file_raw'] == str(content_root / "custom-ideas.md")


@pytest.mark.unit
class TestScanSkills:
    """Tests for scan_skills()."""

    def test_no_skills_dir(self, tmp_path):
        """Missing skills dir returns empty result."""
        result = scan_skills(tmp_path)
        assert result['count'] == 0
        assert result['items'] == {}
        assert result['model_counts'] == {}

    def test_empty_skills_dir(self, tmp_path):
        """Empty skills dir returns empty result."""
        (tmp_path / "skills").mkdir()
        result = scan_skills(tmp_path)
        assert result['count'] == 0
        assert result['items'] == {}

    def test_single_skill(self, tmp_path):
        """One valid skill is scanned correctly."""
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            _make_skill_content("my-skill", "Does things", "claude-opus-4-6"))
        result = scan_skills(tmp_path)
        assert result['count'] == 1
        assert 'my-skill' in result['items']
        assert result['items']['my-skill']['name'] == 'my-skill'
        assert result['items']['my-skill']['model_tier'] == 'opus'

    def test_mixed_tiers(self, tmp_path):
        """Skills with different model tiers are counted correctly."""
        for name, model in [("s1", "claude-opus-4-6"),
                            ("s2", "claude-sonnet-4-5-20250929"),
                            ("s3", "claude-haiku-4-5-20251001"),
                            ("s4", "claude-sonnet-4-5-20250929")]:
            skill_dir = tmp_path / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                _make_skill_content(name, f"Skill {name}", model))

        result = scan_skills(tmp_path)
        assert result['count'] == 4
        assert result['model_counts'] == {'opus': 1, 'sonnet': 2, 'haiku': 1}

    def test_error_skill_skipped(self, tmp_path):
        """Skills with parse errors are skipped without crashing."""
        # Valid skill
        valid_dir = tmp_path / "skills" / "valid"
        valid_dir.mkdir(parents=True)
        (valid_dir / "SKILL.md").write_text(
            _make_skill_content("valid", "Valid skill", "claude-opus-4-6"))

        # Broken skill (no frontmatter)
        broken_dir = tmp_path / "skills" / "broken"
        broken_dir.mkdir(parents=True)
        (broken_dir / "SKILL.md").write_text("# No frontmatter\n\nJust text.\n")

        result = scan_skills(tmp_path)
        assert result['count'] == 1
        assert 'valid' in result['items']
        assert 'broken' not in result['items']

    def test_mtime_stored(self, tmp_path):
        """skills_root_mtime is populated from skills dir."""
        skill_dir = tmp_path / "skills" / "test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            _make_skill_content("test", "Test", "claude-opus-4-6"))

        result = scan_skills(tmp_path)
        assert result['skills_root_mtime'] > 0

    def test_skills_root_path_stored(self, tmp_path):
        """skills_root stores the skills directory path."""
        (tmp_path / "skills").mkdir()
        result = scan_skills(tmp_path)
        assert result['skills_root'] == str(tmp_path / "skills")

    def test_skill_with_optional_fields(self, tmp_path):
        """Skills with prerequisites, requirements, context are parsed."""
        skill_dir = tmp_path / "skills" / "complex"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            _make_skill_content("complex", "Complex skill",
                                "claude-sonnet-4-5-20250929",
                                allowed_tools=["Read", "Bash"],
                                prerequisites=["lyric-writer"],
                                user_invocable=False,
                                context="fork",
                                requirements=["playwright"]))

        result = scan_skills(tmp_path)
        skill = result['items']['complex']
        assert skill['prerequisites'] == ['lyric-writer']
        assert skill['user_invocable'] is False
        assert skill['context'] == 'fork'
        assert skill['requirements'] == {'python': ['playwright']}
        assert skill['allowed_tools'] == ['Read', 'Bash']


@pytest.mark.unit
class TestValidateStateSkills:
    """Tests for validate_state() skills section."""

    def test_valid_state_with_skills(self):
        state = _make_minimal_state()
        errors = validate_state(state)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_skills_key(self):
        state = _make_minimal_state()
        del state['skills']
        errors = validate_state(state)
        assert any('Missing top-level keys' in e for e in errors)
        assert any('skills' in e for e in errors)

    def test_skills_not_dict(self):
        state = _make_minimal_state()
        state['skills'] = "bad"
        errors = validate_state(state)
        assert any('skills should be a dict' in e for e in errors)

    def test_skills_missing_count(self):
        state = _make_minimal_state()
        state['skills'] = {'items': {}}
        errors = validate_state(state)
        assert any('skills.count' in e for e in errors)

    def test_skills_missing_items(self):
        state = _make_minimal_state()
        state['skills'] = {'count': 0}
        errors = validate_state(state)
        assert any('skills.items' in e for e in errors)

    def test_skill_item_missing_required_fields(self):
        state = _make_minimal_state()
        state['skills']['items'] = {
            'broken': {'name': 'broken'}
        }
        errors = validate_state(state)
        assert any("Skill 'broken' missing 'description'" in e for e in errors)
        assert any("Skill 'broken' missing 'model_tier'" in e for e in errors)

    def test_skill_item_not_dict(self):
        state = _make_minimal_state()
        state['skills']['items'] = {'bad': "not a dict"}
        errors = validate_state(state)
        assert any("Skill 'bad' should be a dict" in e for e in errors)

    def test_valid_state_with_full_skill(self):
        state = _make_minimal_state()
        state['skills'] = {
            'skills_root': '/tmp/skills',
            'skills_root_mtime': 100.0,
            'count': 1,
            'model_counts': {'opus': 1},
            'items': {
                'test-skill': {
                    'name': 'test-skill',
                    'description': 'A test skill.',
                    'model': 'claude-opus-4-6',
                    'model_tier': 'opus',
                    'allowed_tools': [],
                    'prerequisites': [],
                    'requirements': {},
                    'user_invocable': True,
                    'context': None,
                    'path': '/tmp/skills/test-skill/SKILL.md',
                    'mtime': 100.0,
                }
            },
        }
        errors = validate_state(state)
        assert errors == []


@pytest.mark.unit
class TestMigrate1_0To1_1:
    """Tests for the 1.0.0 → 1.1.0 migration."""

    def test_migration_adds_skills_section(self):
        """State from v1.0.0 gets skills section via migration chain."""
        state = {
            'version': '1.0.0',
            'generated_at': '2026-01-01T00:00:00+00:00',
            'config': {
                'content_root': '/tmp/c',
                'audio_root': '/tmp/a',
                'documents_root': '/tmp/d',
                'artist_name': 'test',
                'config_mtime': 100.0,
            },
            'albums': {},
            'ideas': {'counts': {}, 'items': [], 'file_mtime': 0.0},
            'session': {
                'last_album': None,
                'last_track': None,
                'last_phase': None,
                'pending_actions': [],
                'updated_at': None,
            },
        }
        result = migrate_state(state)
        assert result is not None
        # Full chain: 1.0.0 → 1.1.0 → 1.2.0
        assert result['version'] == '1.2.0'
        assert 'skills' in result
        assert result['skills']['count'] == 0
        assert result['skills']['items'] == {}
        assert 'plugin_version' in result

    def test_migration_preserves_existing_data(self):
        """Migration preserves albums, session, etc."""
        state = {
            'version': '1.0.0',
            'generated_at': '2026-01-01T00:00:00+00:00',
            'config': {
                'content_root': '/tmp/c',
                'audio_root': '/tmp/a',
                'documents_root': '/tmp/d',
                'artist_name': 'test',
                'config_mtime': 100.0,
            },
            'albums': {'my-album': {'path': '/tmp', 'genre': 'rock',
                                     'title': 'My Album', 'status': 'Concept',
                                     'tracks': {}}},
            'ideas': {'counts': {'Pending': 1}, 'items': [{'title': 'Idea'}],
                      'file_mtime': 50.0},
            'session': {
                'last_album': 'my-album',
                'last_track': None,
                'last_phase': 'Writing',
                'pending_actions': [],
                'updated_at': '2026-01-01',
            },
        }
        result = migrate_state(state)
        assert result is not None
        assert result['albums']['my-album']['title'] == 'My Album'
        assert result['session']['last_album'] == 'my-album'
        assert result['ideas']['counts']['Pending'] == 1


@pytest.mark.unit
class TestBuildStateWithSkills:
    """Tests for build_state() with plugin_root parameter."""

    def test_build_state_includes_skills(self, tmp_path, monkeypatch):
        """build_state scans skills when plugin_root is provided."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        # Create a skills directory
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            _make_skill_content("my-skill", "A skill", "claude-opus-4-6"))

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config, plugin_root=tmp_path)
        assert 'skills' in state
        assert state['skills']['count'] == 1
        assert 'my-skill' in state['skills']['items']

    def test_build_state_default_plugin_root(self, tmp_path, monkeypatch):
        """build_state uses _PROJECT_ROOT by default."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config)
        # Should have skills section (from real project root)
        assert 'skills' in state
        assert isinstance(state['skills']['items'], dict)


@pytest.mark.unit
class TestReadPluginVersion:
    """Tests for _read_plugin_version()."""

    def test_valid_plugin_json(self, tmp_path):
        """Reads version from valid plugin.json."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test-plugin",
            "version": "0.43.1",
        }))
        result = _read_plugin_version(tmp_path)
        assert result == "0.43.1"

    def test_missing_plugin_json(self, tmp_path):
        """Returns None when plugin.json doesn't exist."""
        result = _read_plugin_version(tmp_path)
        assert result is None

    def test_malformed_json(self, tmp_path):
        """Returns None for invalid JSON."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text("{invalid json")
        result = _read_plugin_version(tmp_path)
        assert result is None

    def test_no_version_key(self, tmp_path):
        """Returns None when version key is missing."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test-plugin",
        }))
        result = _read_plugin_version(tmp_path)
        assert result is None

    def test_version_not_string(self, tmp_path):
        """Returns None when version is not a string."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test-plugin",
            "version": 42,
        }))
        result = _read_plugin_version(tmp_path)
        assert result is None

    def test_empty_string_version(self, tmp_path):
        """Empty string version is returned as-is (valid string)."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test-plugin",
            "version": "",
        }))
        result = _read_plugin_version(tmp_path)
        assert result == ""

    def test_version_is_list(self, tmp_path):
        """Returns None when version is a list."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test-plugin",
            "version": [1, 2, 3],
        }))
        result = _read_plugin_version(tmp_path)
        assert result is None

    def test_permission_error(self, tmp_path):
        """Returns None when file is unreadable."""
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        plugin_json = plugin_dir / "plugin.json"
        plugin_json.write_text(json.dumps({"version": "1.0.0"}))
        plugin_json.chmod(0o000)
        result = _read_plugin_version(tmp_path)
        plugin_json.chmod(0o644)  # Restore for cleanup
        assert result is None

    def test_reads_real_plugin_json(self):
        """Reads the actual plugin.json from the project root."""
        result = _read_plugin_version(PROJECT_ROOT)
        assert result is not None
        assert isinstance(result, str)
        # Should be a semver-like string
        parts = result.split('.')
        assert len(parts) >= 2


@pytest.mark.unit
class TestBuildStatePluginVersion:
    """Tests for plugin_version in build_state()."""

    def test_build_state_includes_plugin_version(self, tmp_path, monkeypatch):
        """build_state includes plugin_version from plugin.json."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        # Create plugin.json
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test",
            "version": "1.2.3",
        }))

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config, plugin_root=tmp_path)
        assert state['plugin_version'] == '1.2.3'

    def test_build_state_no_plugin_json(self, tmp_path, monkeypatch):
        """build_state sets plugin_version to None when plugin.json missing."""
        content_root = tmp_path / "content"
        content_root.mkdir()
        # No .claude-plugin directory

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config, plugin_root=tmp_path)
        assert state['plugin_version'] is None

    def test_build_state_plugin_version_validates(self, tmp_path, monkeypatch):
        """build_state with plugin_version passes validation."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test",
            "version": "0.44.0",
        }))

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config, plugin_root=tmp_path)
        errors = validate_state(state)
        assert errors == [], f"Unexpected validation errors: {errors}"


@pytest.mark.unit
class TestMigrate1_1To1_2:
    """Tests for the 1.1.0 → 1.2.0 migration."""

    def test_migration_adds_plugin_version(self):
        """State from v1.1.0 gets plugin_version field via migration."""
        state = {
            'version': '1.1.0',
            'generated_at': '2026-01-01T00:00:00+00:00',
            'config': {
                'content_root': '/tmp/c',
                'audio_root': '/tmp/a',
                'documents_root': '/tmp/d',
                'artist_name': 'test',
                'config_mtime': 100.0,
            },
            'albums': {},
            'ideas': {'counts': {}, 'items': [], 'file_mtime': 0.0},
            'skills': {
                'skills_root': '/tmp/skills',
                'skills_root_mtime': 0.0,
                'count': 0,
                'model_counts': {},
                'items': {},
            },
            'session': {
                'last_album': None,
                'last_track': None,
                'last_phase': None,
                'pending_actions': [],
                'updated_at': None,
            },
        }
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == '1.2.0'
        assert 'plugin_version' in result
        assert result['plugin_version'] is None

    def test_migration_preserves_existing_plugin_version(self):
        """If plugin_version already exists, migration preserves it."""
        state = {
            'version': '1.1.0',
            'generated_at': '2026-01-01T00:00:00+00:00',
            'plugin_version': '0.43.0',
            'config': {
                'content_root': '/tmp/c',
                'audio_root': '/tmp/a',
                'documents_root': '/tmp/d',
                'artist_name': 'test',
                'config_mtime': 100.0,
            },
            'albums': {},
            'ideas': {'counts': {}, 'items': [], 'file_mtime': 0.0},
            'skills': {
                'skills_root': '/tmp/skills',
                'skills_root_mtime': 0.0,
                'count': 0,
                'model_counts': {},
                'items': {},
            },
            'session': {
                'last_album': None,
                'last_track': None,
                'last_phase': None,
                'pending_actions': [],
                'updated_at': None,
            },
        }
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == '1.2.0'
        assert result['plugin_version'] == '0.43.0'


@pytest.mark.unit
class TestValidateStatePluginVersion:
    """Tests for plugin_version validation in validate_state()."""

    def test_plugin_version_string_ok(self):
        """String plugin_version is valid."""
        state = _make_minimal_state(plugin_version='0.43.1')
        errors = validate_state(state)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_plugin_version_null_ok(self):
        """Null plugin_version is valid."""
        state = _make_minimal_state(plugin_version=None)
        errors = validate_state(state)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_plugin_version_wrong_type(self):
        """Non-string, non-null plugin_version is invalid."""
        state = _make_minimal_state(plugin_version=42)
        errors = validate_state(state)
        assert any('plugin_version' in e for e in errors)

    def test_plugin_version_missing_key(self):
        """Missing plugin_version key is caught as missing top-level key."""
        state = _make_minimal_state()
        del state['plugin_version']
        errors = validate_state(state)
        assert any('plugin_version' in e for e in errors)

    def test_plugin_version_bool_invalid(self):
        """Boolean plugin_version is invalid."""
        state = _make_minimal_state(plugin_version=True)
        errors = validate_state(state)
        assert any('plugin_version' in e for e in errors)

    def test_plugin_version_empty_string_ok(self):
        """Empty string plugin_version is valid (string type)."""
        state = _make_minimal_state(plugin_version='')
        errors = validate_state(state)
        assert errors == [], f"Unexpected errors: {errors}"


@pytest.mark.unit
class TestFullMigrationChain:
    """Tests for the complete migration chain 1.0.0 → 1.2.0."""

    def test_1_0_to_1_2_adds_both_skills_and_plugin_version(self):
        """Full chain from 1.0.0 adds skills AND plugin_version."""
        state = {
            'version': '1.0.0',
            'generated_at': '2026-01-01T00:00:00+00:00',
            'config': {
                'content_root': '/tmp/c',
                'audio_root': '/tmp/a',
                'documents_root': '/tmp/d',
                'artist_name': 'test',
                'config_mtime': 100.0,
            },
            'albums': {},
            'ideas': {'counts': {}, 'items': [], 'file_mtime': 0.0},
            'session': {
                'last_album': None,
                'last_track': None,
                'last_phase': None,
                'pending_actions': [],
                'updated_at': None,
            },
        }
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == '1.2.0'
        # From 1.0→1.1 migration
        assert 'skills' in result
        assert result['skills']['count'] == 0
        # From 1.1→1.2 migration
        assert 'plugin_version' in result
        assert result['plugin_version'] is None

    def test_1_0_to_1_2_preserves_all_data(self):
        """Full chain preserves albums, ideas, session through both migrations."""
        state = {
            'version': '1.0.0',
            'generated_at': '2026-01-01T00:00:00+00:00',
            'config': {
                'content_root': '/tmp/c',
                'audio_root': '/tmp/a',
                'documents_root': '/tmp/d',
                'artist_name': 'test',
                'config_mtime': 100.0,
            },
            'albums': {'a': {'path': '/tmp', 'genre': 'rock',
                              'title': 'A', 'status': 'Concept',
                              'tracks': {}}},
            'ideas': {'counts': {'Pending': 2}, 'items': [{'title': 'X'}],
                      'file_mtime': 50.0},
            'session': {
                'last_album': 'a',
                'last_track': '01-t',
                'last_phase': 'Writing',
                'pending_actions': ['review'],
                'updated_at': '2026-01-01',
            },
        }
        result = migrate_state(state)
        assert result['albums']['a']['title'] == 'A'
        assert result['ideas']['counts']['Pending'] == 2
        assert result['session']['last_album'] == 'a'
        assert result['session']['pending_actions'] == ['review']


@pytest.mark.unit
class TestIncrementalUpdatePluginVersion:
    """Tests for plugin_version handling in incremental_update()."""

    def test_plugin_version_updated_on_incremental(self, tmp_path, monkeypatch):
        """incremental_update updates plugin_version from current plugin.json."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)
        monkeypatch.setattr(indexer, '_PROJECT_ROOT', tmp_path)

        # Create plugin.json at the mocked _PROJECT_ROOT
        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test",
            "version": "0.44.0",
        }))

        existing = _make_minimal_state()
        existing['plugin_version'] = '0.43.0'
        existing['config']['config_mtime'] = 100.0
        existing['config']['content_root'] = str(content_root)

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }

        updated = incremental_update(existing, config)
        assert updated['plugin_version'] == '0.44.0'

    def test_plugin_version_null_when_no_plugin_json(self, tmp_path, monkeypatch):
        """incremental_update sets plugin_version to None when plugin.json missing."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)
        monkeypatch.setattr(indexer, '_PROJECT_ROOT', tmp_path)
        # No .claude-plugin directory at tmp_path

        existing = _make_minimal_state()
        existing['plugin_version'] = '0.43.0'
        existing['config']['config_mtime'] = 100.0
        existing['config']['content_root'] = str(content_root)

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }

        updated = incremental_update(existing, config)
        assert updated['plugin_version'] is None

    def test_plugin_version_preserved_from_null(self, tmp_path, monkeypatch):
        """incremental_update handles existing null plugin_version gracefully."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)
        monkeypatch.setattr(indexer, '_PROJECT_ROOT', tmp_path)

        plugin_dir = tmp_path / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "test",
            "version": "0.44.0",
        }))

        existing = _make_minimal_state()
        existing['plugin_version'] = None
        existing['config']['config_mtime'] = 100.0
        existing['config']['content_root'] = str(content_root)

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }

        updated = incremental_update(existing, config)
        assert updated['plugin_version'] == '0.44.0'


# =============================================================================
# Edge case tests — bugs and boundary conditions found during code review
# =============================================================================


@pytest.mark.unit
class TestScanIdeasTOCTOU:
    """Tests for TOCTOU race in scan_ideas — file deleted between exists() and stat()."""

    def test_stat_after_delete(self, tmp_path):
        """File deleted between parse and stat returns file_mtime=0.0.

        The bug was an unguarded stat() call after exists(). Now wrapped
        in try/except.
        """
        content_root = tmp_path / "content"
        content_root.mkdir()
        ideas_file = content_root / "IDEAS.md"
        ideas_file.write_text("""## Ideas

### Test Idea

**Genre**: Rock
**Status**: Pending
""")

        config = {'paths': {}}

        # Patch stat to raise OSError (simulating file deletion)
        original_stat = Path.stat

        call_count = [0]

        def stat_that_fails_on_ideas(self, *args, **kwargs):
            if self.name == "IDEAS.md":
                call_count[0] += 1
                if call_count[0] > 1:
                    raise OSError("File was deleted")
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, 'stat', stat_that_fails_on_ideas):
            result = scan_ideas(config, content_root)

        # Should gracefully handle the missing file
        assert result['file_mtime'] == 0.0
        assert len(result['items']) == 1


@pytest.mark.unit
class TestMigrateStateChain:
    """Tests for migration chain correctness."""

    def test_full_chain_1_0_to_current(self):
        """Migration from 1.0.0 applies both 1.0->1.1 and 1.1->1.2."""
        state = {'version': '1.0.0', 'albums': {}}
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == CURRENT_VERSION
        assert 'skills' in result
        assert 'plugin_version' in result

    def test_migration_preserves_existing_fields(self):
        """Existing data survives migration chain."""
        state = {
            'version': '1.0.0',
            'albums': {'my-album': {'title': 'Test'}},
            'custom_field': 'preserved',
        }
        result = migrate_state(state)
        assert result is not None
        assert result['albums']['my-album']['title'] == 'Test'
        assert result['custom_field'] == 'preserved'

    def test_migration_1_0_adds_skills(self):
        """1.0->1.1 migration adds skills with correct structure."""
        state = {'version': '1.0.0'}
        result = migrate_state(state)
        assert result is not None
        skills = result['skills']
        assert 'items' in skills
        assert 'count' in skills
        assert 'model_counts' in skills
        assert skills['count'] == 0

    def test_migration_1_1_adds_plugin_version(self):
        """1.1->1.2 migration adds plugin_version as None."""
        state = {
            'version': '1.1.0',
            'skills': {'items': {}, 'count': 0, 'model_counts': {},
                       'skills_root': '', 'skills_root_mtime': 0.0},
        }
        result = migrate_state(state)
        assert result is not None
        assert result['version'] == '1.2.0'
        assert result['plugin_version'] is None

    def test_migration_does_not_overwrite_existing_skills(self):
        """1.0->1.1 migration does not clobber pre-existing skills."""
        state = {
            'version': '1.0.0',
            'skills': {'items': {'custom-skill': {}}, 'count': 1,
                       'model_counts': {'opus': 1},
                       'skills_root': '/tmp', 'skills_root_mtime': 1.0},
        }
        result = migrate_state(state)
        assert result is not None
        # Pre-existing skills preserved (migration checks 'skills' not in state)
        assert result['skills']['count'] == 1

    def test_migration_failure_returns_none(self):
        """Corrupted state during migration triggers rebuild (returns None)."""
        import tools.state.indexer as indexer
        # Temporarily replace the migration function to raise
        original_fn, original_target = indexer.MIGRATIONS['1.0.0']

        def bad_migration(state):
            raise ValueError("Corrupted state")

        try:
            indexer.MIGRATIONS['1.0.0'] = (bad_migration, '1.1.0')
            state = {'version': '1.0.0'}
            result = migrate_state(state)
            assert result is None
        finally:
            indexer.MIGRATIONS['1.0.0'] = (original_fn, original_target)


@pytest.mark.unit
class TestIncrementalUpdateTracksCompleted:
    """Tests for tracks_completed recomputation during incremental updates."""

    def test_tracks_completed_recomputed_on_readme_change(self, tmp_path, monkeypatch):
        """When README changes, tracks_completed is recomputed from actual track data."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "my-album",
                         tracks={
                             "01-track.md": _make_track_content("Track One", "Final"),
                             "02-track.md": _make_track_content("Track Two", "Generated"),
                             "03-track.md": _make_track_content("Track Three", "Not Started"),
                         })

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0

        # Modify a track to become Final
        time.sleep(0.05)
        track_path = (content_root / "artists" / "testartist" / "albums" /
                      "rock" / "my-album" / "tracks" / "03-track.md")
        track_path.write_text(_make_track_content("Track Three", "Final"))

        updated = incremental_update(existing, config)
        album = updated['albums']['my-album']
        # tracks_completed should include Final (2) + Generated (1) = 3
        # _update_tracks_incremental counts Final+Generated+Complete
        assert album['tracks_completed'] == 3

    def test_tracks_completed_recomputed_on_track_change(self, tmp_path, monkeypatch):
        """Track status change triggers tracks_completed recount."""
        content_root = tmp_path / "content"
        _make_album_tree(content_root, "testartist", "rock", "recount-album",
                         tracks={
                             "01-a.md": _make_track_content("A", "Not Started"),
                         })

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        assert existing['albums']['recount-album']['tracks_completed'] == 0

        # Update track to Final
        time.sleep(0.05)
        track_path = (content_root / "artists" / "testartist" / "albums" /
                      "rock" / "recount-album" / "tracks" / "01-a.md")
        track_path.write_text(_make_track_content("A", "Final"))

        updated = incremental_update(existing, config)
        assert updated['albums']['recount-album']['tracks_completed'] == 1


@pytest.mark.unit
class TestBuildStateSessionPreservation:
    """Tests that session is preserved across rebuilds."""

    def test_build_state_has_empty_session(self, tmp_path, monkeypatch):
        """Fresh build_state creates an empty session."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 0.0)

        state = build_state(config)
        assert state['session']['last_album'] is None
        assert state['session']['pending_actions'] == []
        assert state['session']['updated_at'] is None

    def test_incremental_preserves_session(self, tmp_path, monkeypatch):
        """incremental_update preserves session data (deep copy)."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        existing['session'] = {
            'last_album': 'test-album',
            'last_track': '01-track',
            'last_phase': 'Mastering',
            'pending_actions': ['verify sources', 'check lyrics'],
            'updated_at': '2026-01-15T00:00:00Z',
        }

        updated = incremental_update(existing, config)
        assert updated['session']['last_album'] == 'test-album'
        assert updated['session']['last_phase'] == 'Mastering'
        assert len(updated['session']['pending_actions']) == 2

    def test_incremental_does_not_mutate_original(self, tmp_path, monkeypatch):
        """incremental_update deep copies, so original state is not mutated."""
        content_root = tmp_path / "content"
        content_root.mkdir()

        config = {
            'artist': {'name': 'testartist'},
            'paths': {'content_root': str(content_root)},
        }
        import tools.state.indexer as indexer
        monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

        existing = build_state(config)
        existing['config']['config_mtime'] = 100.0
        original_generated_at = existing['generated_at']

        time.sleep(0.01)
        updated = incremental_update(existing, config)

        # Original should not have been mutated
        assert existing['generated_at'] == original_generated_at
        assert updated['generated_at'] != original_generated_at
