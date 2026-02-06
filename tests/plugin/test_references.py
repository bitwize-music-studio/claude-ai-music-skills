"""Tests for reference documentation: Suno refs, mastering docs, CLAUDE.md refs."""

import re

import pytest

pytestmark = pytest.mark.plugin

REQUIRED_SUNO_REFS = [
    'v5-best-practices.md',
    'pronunciation-guide.md',
    'tips-and-tricks.md',
    'structure-tags.md',
    'voice-tags.md',
    'instrumental-tags.md',
    'genre-list.md',
]


class TestSunoReferences:
    """Suno reference files must exist."""

    def test_suno_directory_exists(self, reference_dir):
        assert (reference_dir / "suno").exists(), "reference/suno/ directory missing"

    @pytest.mark.parametrize("ref_file", REQUIRED_SUNO_REFS)
    def test_suno_ref_exists(self, reference_dir, ref_file):
        suno_dir = reference_dir / "suno"
        if not suno_dir.exists():
            pytest.skip("reference/suno/ not found")
        assert (suno_dir / ref_file).exists(), f"Missing: reference/suno/{ref_file}"


class TestMasteringDocs:
    """Mastering workflow documentation must exist."""

    def test_mastering_workflow_exists(self, reference_dir):
        mastering_doc = reference_dir / "mastering" / "mastering-workflow.md"
        assert mastering_doc.exists(), "reference/mastering/mastering-workflow.md missing"


class TestClaudeMdRefs:
    """References mentioned in CLAUDE.md must exist."""

    def test_referenced_docs_exist(self, reference_dir, claude_md_content):
        ref_paths = re.findall(r'/reference/([a-zA-Z0-9_/-]+\.md)', claude_md_content)
        missing = [
            ref for ref in set(ref_paths)
            if not (reference_dir / ref).exists()
        ]
        assert not missing, f"Referenced in CLAUDE.md but missing: {missing}"
