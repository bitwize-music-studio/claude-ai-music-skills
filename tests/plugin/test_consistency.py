"""Tests for cross-reference consistency: versions, skill counts, model tiers, .gitignore."""

import json
import re

import pytest

pytestmark = pytest.mark.plugin


class TestSkillCount:
    """README skill count must match actual count."""

    def test_readme_skill_count(self, project_root, all_skill_frontmatter):
        readme_path = project_root / "README.md"
        assert readme_path.exists(), "Required file missing: README.md"

        readme_content = readme_path.read_text()
        match = (
            re.search(r'\*\*(\d+)\s+specialized skills\*\*', readme_content)
            or re.search(r'Skill System\s*\((\d+)\s+Skills\)', readme_content)
        )
        assert match, (
            "README.md no longer advertises a skill count in a recognised form "
            "('**N specialized skills**' or 'Skill System (N Skills)') — the "
            "count can no longer be cross-checked. Update the README wording or "
            "this pattern, but do not leave the check silently disabled."
        )

        claimed = int(match.group(1))
        actual = len(all_skill_frontmatter)
        assert claimed == actual, (
            f"README claims {claimed} skills, actual is {actual}"
        )


class TestVersionSync:
    """plugin.json and marketplace.json versions must match."""

    def test_version_files_match(self, project_root):
        plugin_json = project_root / ".claude-plugin" / "plugin.json"
        marketplace_json = project_root / ".claude-plugin" / "marketplace.json"

        assert plugin_json.exists(), "Required file missing: .claude-plugin/plugin.json"
        assert marketplace_json.exists(), "Required file missing: .claude-plugin/marketplace.json"

        with open(plugin_json, encoding="utf-8") as f:
            plugin_version = json.load(f).get('version', 'unknown')
        with open(marketplace_json, encoding="utf-8") as f:
            marketplace_data = json.load(f)
            marketplace_version = marketplace_data.get('plugins', [{}])[0].get('version', 'unknown')

        assert plugin_version == marketplace_version, (
            f"plugin.json: {plugin_version}, marketplace.json: {marketplace_version}"
        )


class TestNoSkillJson:
    """No invalid skill.json files (standard is SKILL.md)."""

    def test_no_skill_json_files(self, skills_dir):
        skill_json_files = list(skills_dir.glob("*/skill.json"))
        assert not skill_json_files, (
            f"Found invalid skill.json files: {[str(f.relative_to(skills_dir)) for f in skill_json_files]}"
        )


class TestModelTierConsistency:
    """Model tiers in SKILL.md must match model-strategy.md."""

    def test_model_strategy_alignment(self, project_root, all_skill_frontmatter):
        strategy_path = project_root / "reference" / "model-strategy.md"
        assert strategy_path.exists(), "Required file missing: reference/model-strategy.md"

        strategy_content = strategy_path.read_text()

        tier_sections = {
            'opus': r'## Opus.*?(?=## Sonnet|## Haiku|## Decision|$)',
            'sonnet': r'## Sonnet.*?(?=## Haiku|## Decision|$)',
            'haiku': r'## Haiku.*?(?=## Decision|$)',
        }

        mismatches = []
        for skill_name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            model = fm.get('model', '')
            if not model:
                continue

            # Determine actual tier
            actual_tier = None
            for tier in ('opus', 'sonnet', 'haiku'):
                if tier in model:
                    actual_tier = tier
                    break
            if not actual_tier:
                continue

            # Find which section documents this skill
            skill_heading = re.compile(rf'^### {re.escape(skill_name)}$', re.MULTILINE)
            documented_tier = None
            for tier, pattern in tier_sections.items():
                section_match = re.search(pattern, strategy_content, re.DOTALL)
                if section_match and skill_heading.search(section_match.group()):
                    documented_tier = tier
                    break

            if documented_tier and documented_tier != actual_tier:
                mismatches.append(
                    f"{skill_name}: SKILL.md says {actual_tier}, model-strategy.md says {documented_tier}"
                )

        assert not mismatches, "Model tier mismatches:\n" + "\n".join(mismatches)


class TestNoDisableModelInvocation:
    """No skills should have disable-model-invocation flag."""

    def test_no_disable_flag(self, all_skill_frontmatter):
        flagged = [
            name for name, fm in all_skill_frontmatter.items()
            if '_error' not in fm and fm.get('disable-model-invocation')
        ]
        # No skill sets this flag today; setting it hides the skill from
        # model-driven invocation, which would silently break routing.
        assert not flagged, (
            "Skills must not set disable-model-invocation (it hides them from "
            f"model-driven routing): {', '.join(flagged)}"
        )


class TestHealthCheckCollisionDocs:
    """Skills documenting health_check must surface the collisions section (#392)."""

    def test_session_start_documents_collisions(self, skills_dir):
        skill_path = skills_dir / "session-start" / "SKILL.md"
        content = skill_path.read_text()

        step_15 = re.search(r'## Step 1\.5.*?(?=\n## Step 2)', content, re.DOTALL)
        assert step_15, "session-start SKILL.md missing Step 1.5 section"
        assert "collision" in step_15.group().lower(), (
            "session-start Step 1.5 does not handle the health_check "
            "collisions section — agents following it would drop the warning"
        )

        report = re.search(r'## Report Format.*?```.*?```', content, re.DOTALL)
        assert report, "session-start SKILL.md missing Report Format template"
        assert "collision" in report.group().lower(), (
            "session-start Report Format Health line omits collisions"
        )

    def test_health_check_documents_collisions(self, skills_dir):
        skill_path = skills_dir / "health-check" / "SKILL.md"
        content = skill_path.read_text()

        report = re.search(r'## Report Format.*?(?=\n## Remember|$)', content, re.DOTALL)
        assert report, "health-check SKILL.md missing Report Format section"
        assert "COLLISIONS" in report.group(), (
            "health-check Report Format has no COLLISIONS section slot "
            "alongside VENV/SKILLS"
        )


class TestGitignore:
    """Required .gitignore entries must be present."""

    REQUIRED_IGNORES = ['artists/', 'research/', '*.pdf', 'venv/']

    @pytest.mark.parametrize("entry", REQUIRED_IGNORES)
    def test_gitignore_entry(self, project_root, entry):
        gitignore_path = project_root / ".gitignore"
        assert gitignore_path.exists(), "Required file missing: .gitignore"

        content = gitignore_path.read_text()
        assert entry in content or entry.rstrip('/') in content, (
            f".gitignore missing recommended entry: {entry}"
        )
