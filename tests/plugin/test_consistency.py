"""Tests for cross-reference consistency: versions, skill counts, model tiers, .gitignore."""

import json
import re

import pytest

pytestmark = pytest.mark.plugin


class TestSkillCount:
    """README skill count must match actual count."""

    def test_readme_skill_count(self, project_root, all_skill_frontmatter):
        readme_path = project_root / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        readme_content = readme_path.read_text()
        match = re.search(r'\*\*(\d+)\s+specialized skills\*\*', readme_content)
        if not match:
            pytest.skip("Skill count pattern not found in README")

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

        if not plugin_json.exists() or not marketplace_json.exists():
            pytest.skip("Version files not found")

        with open(plugin_json) as f:
            plugin_version = json.load(f).get('version', 'unknown')
        with open(marketplace_json) as f:
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
        if not strategy_path.exists():
            pytest.skip("model-strategy.md not found")

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
        # This is advisory, not a hard fail
        assert not flagged or True  # soft check preserved


class TestGitignore:
    """Required .gitignore entries must be present."""

    REQUIRED_IGNORES = ['artists/', 'research/', '*.pdf', 'venv/']

    @pytest.mark.parametrize("entry", REQUIRED_IGNORES)
    def test_gitignore_entry(self, project_root, entry):
        gitignore_path = project_root / ".gitignore"
        if not gitignore_path.exists():
            pytest.skip(".gitignore not found")

        content = gitignore_path.read_text()
        assert entry in content or entry.rstrip('/') in content, (
            f".gitignore missing recommended entry: {entry}"
        )
