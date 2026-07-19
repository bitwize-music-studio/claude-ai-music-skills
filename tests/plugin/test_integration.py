"""Tests for cross-skill integration: prerequisite chains, workflow consistency."""

import re

import pytest

from tests.plugin.test_skills import _skill_content

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
        prereq_graph: dict[str, list[str]] = {}
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
        writer_content = _skill_content(all_skill_frontmatter, 'lyric-writer')
        reviewer_content = _skill_content(all_skill_frontmatter, 'lyric-reviewer')

        writer_match = re.search(
            r'(?:(\d+)-[Pp]oint.*(?:[Cc]hecklist|[Qq]uality [Cc]heck)|[Qq]uality [Cc]heck \((\d+)-[Pp]oint\))', writer_content
        )
        reviewer_match = re.search(
            r'(\d+)-[Pp]oint.*[Cc]hecklist', reviewer_content
        )

        assert writer_match, (
            "lyric-writer SKILL.md no longer advertises an N-point quality "
            "checklist — the writer/reviewer coverage guarantee cannot be checked"
        )
        assert reviewer_match, (
            "lyric-reviewer SKILL.md no longer advertises an N-point checklist — "
            "the writer/reviewer coverage guarantee cannot be checked"
        )

        writer_count = int(writer_match.group(1) or writer_match.group(2))
        reviewer_count = int(reviewer_match.group(1))
        assert reviewer_count >= writer_count, (
            f"Reviewer ({reviewer_count}-point) should cover >= writer ({writer_count}-point)"
        )


class TestPreGenerationCheck:
    """pre-generation-check must reference all QC skills."""

    EXPECTED_REFS = ['lyric-writer', 'lyric-reviewer', 'pronunciation-specialist', 'suno-engineer']

    def test_pregen_references_qc_skills(self, all_skill_frontmatter):
        content = _skill_content(all_skill_frontmatter, 'pre-generation-check')
        missing = [ref for ref in self.EXPECTED_REFS if ref not in content]
        assert not missing, (
            "pre-generation-check SKILL.md must reference every QC skill it "
            f"gates on; missing: {', '.join(missing)}"
        )


class TestArtistBlocklist:
    """Artist blocklist must exist and be referenced."""

    def test_blocklist_exists(self, reference_dir):
        blocklist = reference_dir / "suno" / "artist-blocklist.md"
        assert blocklist.exists(), "reference/suno/artist-blocklist.md not found"

    # Skills may cite the blocklist by file name (artist-blocklist.md) or by
    # prose ("the artist blocklist"); both count as a reference.
    @pytest.mark.parametrize("skill_name", ['suno-engineer', 'lyric-reviewer'])
    def test_skill_references_blocklist(self, all_skill_frontmatter, skill_name):
        content = _skill_content(all_skill_frontmatter, skill_name).lower()
        assert 'artist-blocklist' in content or 'artist blocklist' in content, (
            f"{skill_name} SKILL.md no longer references the artist blocklist — "
            f"style prompts containing artist names would go unchecked"
        )


class TestHomographFlow:
    """Homograph handling must be documented across writer/specialist/reviewer."""

    ROLES = {
        'lyric-writer': 'flags',
        'pronunciation-specialist': 'resolves',
        'lyric-reviewer': 'verifies',
    }

    @pytest.mark.parametrize("skill_name,role", ROLES.items())
    def test_homograph_role_documented(self, all_skill_frontmatter, skill_name, role):
        content = _skill_content(all_skill_frontmatter, skill_name)
        assert role.lower() in content.lower(), (
            f"{skill_name} SKILL.md does not document its homograph role "
            f"('{role}') — the flag/resolve/verify handoff is broken"
        )


class TestInstrumentalRouting:
    """Instrumental tracks must route to suno-engineer, not lyric-writer (#115)."""

    @pytest.mark.parametrize("skill_name", ['resume', 'next-step'])
    def test_instrumental_routes_to_suno_engineer(self, all_skill_frontmatter, skill_name):
        """Decision tree must route instrumental tracks to suno-engineer."""
        content = _skill_content(all_skill_frontmatter, skill_name)
        # Must mention instrumental detection
        assert 'instrumental' in content.lower(), (
            f"{skill_name} SKILL.md missing instrumental track handling"
        )
        # Must route to suno-engineer for instrumental tracks
        assert 'suno-engineer' in content, (
            f"{skill_name} SKILL.md missing suno-engineer routing for instrumental tracks"
        )

    def test_resume_handles_mixed_albums(self, all_skill_frontmatter):
        """resume must handle albums with both vocal and instrumental tracks."""
        content = _skill_content(all_skill_frontmatter, 'resume')
        # Check for mixed album awareness (vocal + instrumental)
        has_mixed = (
            'vocal' in content.lower() and 'instrumental' in content.lower()
        )
        assert has_mixed, (
            "resume SKILL.md missing mixed vocal/instrumental album handling"
        )


class TestReviewAndApprovePhase:
    """resume must document the Review & Approve phase for all-Generated albums (#116)."""

    def test_resume_review_approve_phase(self, all_skill_frontmatter):
        """resume must show Review & Approve when all tracks are Generated."""
        content = _skill_content(all_skill_frontmatter, 'resume')
        assert 'Review & Approve' in content, (
            "resume SKILL.md missing 'Review & Approve' phase for all-Generated albums"
        )


class TestRegenerationPaths:
    """next-step must document regeneration paths for rejected tracks (#116)."""

    def test_next_step_regeneration_paths(self, all_skill_frontmatter):
        """next-step must document style issue and lyrics issue regeneration paths."""
        content = _skill_content(all_skill_frontmatter, 'next-step')
        has_style_path = 'style issue' in content.lower() or 'Style issue' in content
        has_lyrics_path = 'lyrics issue' in content.lower() or 'Lyrics issue' in content
        assert has_style_path, (
            "next-step SKILL.md missing style issue regeneration path"
        )
        assert has_lyrics_path, (
            "next-step SKILL.md missing lyrics issue regeneration path"
        )
