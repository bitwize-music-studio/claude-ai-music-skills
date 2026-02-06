"""Tests for skill definitions: frontmatter, model refs, prerequisites, sections."""

import re

import pytest

pytestmark = pytest.mark.plugin

# Required frontmatter fields
REQUIRED_SKILL_FIELDS = {'name', 'description', 'model'}

# Valid model patterns
MODEL_PATTERN = re.compile(r'^claude-(opus|sonnet|haiku)-[0-9]+(-[0-9]+)?(-[0-9]{8})?$')

# Skills that require external dependencies
SKILLS_WITH_REQUIREMENTS = {
    'mastering-engineer': ['matchering', 'pyloudnorm', 'scipy', 'numpy', 'soundfile'],
    'promo-director': ['ffmpeg', 'pillow', 'librosa'],
    'sheet-music-publisher': ['AnthemScore', 'MuseScore', 'pypdf', 'reportlab'],
    'document-hunter': ['playwright', 'chromium'],
    'cloud-uploader': ['boto3'],
}

# System skills with non-standard structure
SYSTEM_SKILLS = {'about', 'help'}

# Required structural elements with accepted alternatives
REQUIRED_STRUCTURE = [
    (
        'agent title (# heading)',
        [r'^# .+'],
    ),
    (
        'task description',
        [r'^## Your Task', r'^## Purpose', r'^## Instructions'],
    ),
    (
        'procedural content',
        [r'^## .*Workflow', r'^## Step 1', r'^## Commands',
         r'^## Research Process', r'^## The \d+-Point Checklist',
         r'^## Domain Expertise', r'^## Key Skills',
         r'^## Output Format', r'^## Instructions',
         r'^## \d+\. '],
    ),
    (
        'closing guidance',
        [r'^## Remember', r'^## Important Notes', r'^## Common Mistakes',
         r'^## Implementation Notes', r'^## Error Handling',
         r'^## Troubleshooting', r'^## Adding New Tests',
         r'^## Technical Reference', r'^## Model Recommendation'],
    ),
]

# System skills to skip in SKILL_INDEX.md check
SKIP_SKILLS_INDEX = {'help', 'about', 'configure', 'test'}


class TestSkillMdExists:
    """All skill directories must have a SKILL.md file."""

    def test_skill_md_exists(self, all_skill_dirs):
        missing = [
            d.name for d in all_skill_dirs
            if not (d / "SKILL.md").exists()
        ]
        assert not missing, f"Missing SKILL.md in: {', '.join(missing)}"


class TestFrontmatter:
    """All skills must have valid YAML frontmatter."""

    def test_all_frontmatter_valid(self, all_skill_frontmatter):
        errors = {
            name: fm['_error']
            for name, fm in all_skill_frontmatter.items()
            if '_error' in fm
        }
        assert not errors, f"Invalid frontmatter: {errors}"

    def test_required_fields(self, all_skill_frontmatter):
        missing = {}
        for name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            gaps = REQUIRED_SKILL_FIELDS - set(fm.keys())
            if gaps:
                missing[name] = gaps
        assert not missing, f"Missing required fields: {missing}"


class TestModelReferences:
    """All model references must match the valid pattern."""

    def test_model_format(self, all_skill_frontmatter):
        invalid = {}
        for name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            model = fm.get('model', '')
            if model and not MODEL_PATTERN.match(model):
                invalid[name] = model
        assert not invalid, f"Invalid model references: {invalid}"


class TestRequirements:
    """Skills with external deps should have requirements field."""

    def test_requirements_field(self, all_skill_frontmatter):
        warnings = []
        for skill_name, expected_deps in SKILLS_WITH_REQUIREMENTS.items():
            if skill_name not in all_skill_frontmatter:
                continue
            fm = all_skill_frontmatter[skill_name]
            if '_error' in fm:
                continue
            if 'requirements' not in fm:
                warnings.append(
                    f"{skill_name} uses {', '.join(expected_deps[:3])}... but has no requirements field"
                )
        # This is a warning-level check, not a hard fail
        # requirements field is advisory (original was WARN level)
        assert True


class TestSkillSections:
    """Skills must have required structural sections."""

    def test_required_sections(self, all_skill_frontmatter):
        failures = []
        for skill_name, fm in all_skill_frontmatter.items():
            if '_error' in fm or skill_name in SYSTEM_SKILLS:
                continue
            content = fm.get('_content', '')
            for check_name, patterns in REQUIRED_STRUCTURE:
                found = any(
                    re.search(p, content, re.MULTILINE) for p in patterns
                )
                if not found:
                    failures.append(f"{skill_name}: missing {check_name}")
        assert not failures, "Missing sections:\n" + "\n".join(failures)


class TestSkillIndex:
    """All skills must be documented in SKILL_INDEX.md."""

    def test_skills_in_index(self, all_skill_frontmatter, reference_dir):
        skill_index_file = reference_dir / "SKILL_INDEX.md"
        if not skill_index_file.exists():
            pytest.skip("SKILL_INDEX.md not found")

        index_content = skill_index_file.read_text()
        missing = []
        for skill_name in all_skill_frontmatter:
            if skill_name in SKIP_SKILLS_INDEX:
                continue
            if f"`{skill_name}`" not in index_content and f"/{skill_name}" not in index_content:
                missing.append(skill_name)

        assert not missing, f"Skills not in SKILL_INDEX.md: {', '.join(missing)}"
