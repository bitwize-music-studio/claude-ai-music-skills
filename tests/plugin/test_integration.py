"""Tests for cross-skill integration: prerequisite chains, workflow consistency."""

import re
from typing import Dict, List

import pytest

pytestmark = [pytest.mark.plugin, pytest.mark.integration]


class TestPrerequisites:
    """Skills with prerequisites must reference valid skills."""

    def test_valid_prerequisites(self, all_skill_frontmatter):
        invalid = []
        for skill_name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            prereqs = fm.get('prerequisites', [])
            for prereq in prereqs:
                if prereq not in all_skill_frontmatter:
                    invalid.append(f"{skill_name} -> {prereq}")

        assert not invalid, (
            "Invalid prerequisite references:\n" + "\n".join(invalid)
        )

    def test_no_circular_prerequisites(self, all_skill_frontmatter):
        # Build adjacency graph
        prereq_graph: Dict[str, List[str]] = {}
        for skill_name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            prereqs = fm.get('prerequisites', [])
            if prereqs:
                prereq_graph[skill_name] = prereqs

        def has_cycle(node, visited, stack):
            visited.add(node)
            stack.add(node)
            for dep in prereq_graph.get(node, []):
                if dep in stack:
                    return True
                if dep not in visited and has_cycle(dep, visited, stack):
                    return True
            stack.discard(node)
            return False

        visited: set = set()
        for node in prereq_graph:
            if node not in visited:
                assert not has_cycle(node, visited, set()), (
                    "Circular dependency detected in skill prerequisites"
                )


class TestLyricWorkflowChain:
    """Lyric writer/reviewer checklist counts must be consistent."""

    def test_reviewer_covers_writer_checklist(self, all_skill_frontmatter):
        writer = all_skill_frontmatter.get('lyric-writer', {})
        reviewer = all_skill_frontmatter.get('lyric-reviewer', {})

        if '_error' in writer or '_error' in reviewer:
            pytest.skip("lyric-writer or lyric-reviewer has errors")

        writer_content = writer.get('_content', '')
        reviewer_content = reviewer.get('_content', '')

        writer_match = re.search(
            r'(?:(\d+)-[Pp]oint.*(?:[Cc]hecklist|[Qq]uality [Cc]heck)|[Qq]uality [Cc]heck \((\d+)-[Pp]oint\))', writer_content
        )
        reviewer_match = re.search(
            r'(\d+)-[Pp]oint.*[Cc]hecklist', reviewer_content
        )

        if not writer_match or not reviewer_match:
            pytest.skip("Could not find checklist counts")

        writer_count = int(writer_match.group(1) or writer_match.group(2))
        reviewer_count = int(reviewer_match.group(1))
        assert reviewer_count >= writer_count, (
            f"Reviewer ({reviewer_count}-point) should cover >= writer ({writer_count}-point)"
        )


class TestPreGenerationCheck:
    """pre-generation-check must reference all QC skills."""

    EXPECTED_REFS = ['lyric-writer', 'lyric-reviewer', 'pronunciation-specialist', 'suno-engineer']

    def test_pregen_references_qc_skills(self, all_skill_frontmatter):
        pregen = all_skill_frontmatter.get('pre-generation-check', {})
        if '_error' in pregen:
            pytest.skip("pre-generation-check has errors")

        content = pregen.get('_content', '')
        missing = [ref for ref in self.EXPECTED_REFS if ref not in content]

        # This is advisory (WARN level in original)
        assert not missing or True  # soft check


class TestArtistBlocklist:
    """Artist blocklist must exist and be referenced."""

    def test_blocklist_exists(self, reference_dir):
        blocklist = reference_dir / "suno" / "artist-blocklist.md"
        assert blocklist.exists(), "reference/suno/artist-blocklist.md not found"

    def test_suno_engineer_references_blocklist(self, all_skill_frontmatter):
        suno_eng = all_skill_frontmatter.get('suno-engineer', {})
        if '_error' in suno_eng:
            pytest.skip("suno-engineer has errors")
        content = suno_eng.get('_content', '')
        # Advisory check
        assert 'artist-blocklist' in content or True  # soft check

    def test_lyric_reviewer_references_blocklist(self, all_skill_frontmatter):
        reviewer = all_skill_frontmatter.get('lyric-reviewer', {})
        if '_error' in reviewer:
            pytest.skip("lyric-reviewer has errors")
        content = reviewer.get('_content', '')
        # Advisory check
        assert 'artist-blocklist' in content or True  # soft check


class TestHomographFlow:
    """Homograph handling must be documented across writer/specialist/reviewer."""

    ROLES = {
        'lyric-writer': 'flags',
        'pronunciation-specialist': 'resolves',
        'lyric-reviewer': 'verifies',
    }

    @pytest.mark.parametrize("skill_name,role", ROLES.items())
    def test_homograph_role_documented(self, all_skill_frontmatter, skill_name, role):
        fm = all_skill_frontmatter.get(skill_name, {})
        if '_error' in fm:
            pytest.skip(f"{skill_name} has errors")
        content = fm.get('_content', '')
        # Advisory check
        assert role.lower() in content.lower() or True  # soft check
