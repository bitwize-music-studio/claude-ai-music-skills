"""Tests for migration file format and consistency."""

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.plugin

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"

VALID_CATEGORIES = {
    'filesystem', 'templates', 'dependencies', 'config', 'workflow',
}

VALID_ACTION_TYPES = {'auto', 'action', 'info', 'manual'}


def _get_migration_files():
    """Get all migration markdown files (excluding README)."""
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(
        f for f in MIGRATIONS_DIR.glob("*.md")
        if f.name != "README.md"
    )


def _parse_migration(path: Path):
    """Parse a migration file, returning (frontmatter_dict, body_str)."""
    content = path.read_text()
    if not content.startswith('---'):
        return None, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return None, content

    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None, content

    return fm, parts[2].strip()


class TestMigrationDirectoryExists:
    """migrations/ directory must exist."""

    def test_migrations_dir_exists(self):
        assert MIGRATIONS_DIR.exists(), "migrations/ directory missing"

    def test_readme_exists(self):
        assert (MIGRATIONS_DIR / "README.md").exists(), "migrations/README.md missing"


class TestMigrationFileFormat:
    """Each migration file must have valid YAML frontmatter."""

    @pytest.fixture(params=_get_migration_files(),
                    ids=lambda f: f.name)
    def migration_file(self, request):
        return request.param

    def test_has_yaml_frontmatter(self, migration_file):
        content = migration_file.read_text()
        assert content.startswith('---'), f"{migration_file.name}: must start with ---"

    def test_valid_yaml(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None, f"{migration_file.name}: invalid YAML frontmatter"

    def test_version_matches_filename(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        expected_version = migration_file.stem  # e.g., "0.44.0"
        assert fm.get('version') == expected_version, (
            f"{migration_file.name}: version '{fm.get('version')}' "
            f"doesn't match filename '{expected_version}'"
        )

    def test_has_required_fields(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        for field in ('version', 'summary', 'categories', 'actions'):
            assert field in fm, f"{migration_file.name}: missing required field '{field}'"

    def test_summary_is_string(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        assert isinstance(fm['summary'], str), f"{migration_file.name}: summary must be string"

    def test_categories_valid(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        categories = fm.get('categories', [])
        assert isinstance(categories, list), f"{migration_file.name}: categories must be list"
        invalid = set(categories) - VALID_CATEGORIES
        assert not invalid, (
            f"{migration_file.name}: invalid categories: {invalid}. "
            f"Valid: {VALID_CATEGORIES}"
        )

    def test_actions_valid(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        actions = fm.get('actions', [])
        assert isinstance(actions, list), f"{migration_file.name}: actions must be list"
        for i, action in enumerate(actions):
            assert isinstance(action, dict), (
                f"{migration_file.name}: action {i} must be dict"
            )
            assert 'type' in action, (
                f"{migration_file.name}: action {i} missing 'type'"
            )
            assert action['type'] in VALID_ACTION_TYPES, (
                f"{migration_file.name}: action {i} invalid type '{action['type']}'. "
                f"Valid: {VALID_ACTION_TYPES}"
            )

    def test_auto_actions_have_check_and_command(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        for i, action in enumerate(fm.get('actions', [])):
            if action.get('type') == 'auto':
                assert 'check' in action, (
                    f"{migration_file.name}: auto action {i} missing 'check'"
                )
                assert 'command' in action, (
                    f"{migration_file.name}: auto action {i} missing 'command'"
                )

    def test_action_type_has_confirm(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        for i, action in enumerate(fm.get('actions', [])):
            if action.get('type') == 'action':
                assert action.get('confirm') is True, (
                    f"{migration_file.name}: action {i} (type=action) must have confirm: true"
                )

    def test_manual_actions_have_instruction(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        for i, action in enumerate(fm.get('actions', [])):
            if action.get('type') == 'manual':
                assert 'instruction' in action, (
                    f"{migration_file.name}: manual action {i} missing 'instruction'"
                )

    def test_has_markdown_body(self, migration_file):
        _, body = _parse_migration(migration_file)
        assert body.strip(), f"{migration_file.name}: must have markdown body after frontmatter"

    def test_version_is_semver(self, migration_file):
        fm, _ = _parse_migration(migration_file)
        assert fm is not None
        version = fm.get('version', '')
        assert re.match(r'^\d+\.\d+\.\d+$', version), (
            f"{migration_file.name}: version '{version}' is not valid semver"
        )
