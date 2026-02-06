"""Tests for state cache tool files and structure."""

import re

import pytest

pytestmark = pytest.mark.plugin


class TestStateToolFiles:
    """State tool directory and files must exist."""

    def test_state_dir_exists(self, project_root):
        assert (project_root / "tools" / "state").exists(), "tools/state/ missing"

    @pytest.mark.parametrize("filename,desc", [
        ('__init__.py', 'Package init'),
        ('indexer.py', 'CLI indexer'),
        ('parsers.py', 'Markdown parsers'),
    ])
    def test_state_file_exists(self, project_root, filename, desc):
        filepath = project_root / "tools" / "state" / filename
        assert filepath.exists(), f"Missing: tools/state/{filename} ({desc})"


class TestSchemaVersion:
    """Schema version must be defined and valid."""

    def test_current_version_exists(self, project_root):
        indexer = project_root / "tools" / "state" / "indexer.py"
        if not indexer.exists():
            pytest.skip("indexer.py not found")
        content = indexer.read_text()
        assert 'CURRENT_VERSION' in content, "CURRENT_VERSION not found in indexer.py"

    def test_current_version_is_semver(self, project_root):
        indexer = project_root / "tools" / "state" / "indexer.py"
        if not indexer.exists():
            pytest.skip("indexer.py not found")
        content = indexer.read_text()
        match = re.search(r'CURRENT_VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\']', content)
        assert match, "CURRENT_VERSION should be a semver string like '1.0.0'"


class TestStateTestFiles:
    """State test files and fixtures must exist."""

    @pytest.mark.parametrize("test_file", ['test_parsers.py', 'test_indexer.py'])
    def test_state_test_exists(self, project_root, test_file):
        path = project_root / "tests" / "unit" / "state" / test_file
        assert path.exists(), f"Missing state test: {test_file}"

    @pytest.mark.parametrize("fixture", ['album-readme.md', 'track-file.md', 'ideas.md'])
    def test_fixture_exists(self, project_root, fixture):
        path = project_root / "tests" / "unit" / "state" / "fixtures" / fixture
        assert path.exists(), f"Missing test fixture: {fixture}"
