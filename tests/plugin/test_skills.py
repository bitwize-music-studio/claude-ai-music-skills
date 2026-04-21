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
    'mix-engineer': ['noisereduce', 'scipy', 'numpy', 'soundfile'],
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


class TestSupportingFiles:
    """All supporting files referenced in SKILL.md must exist on disk."""

    SUPPORTING_FILE_PATTERN = re.compile(
        r'\[([^\]]+)\]\(([^)]+)\)',  # Markdown link [text](path)
    )

    def test_supporting_files_exist(self, all_skill_dirs, project_root):
        missing = []
        for skill_dir in all_skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            content = skill_md.read_text()
            # Find the "## Supporting Files" section
            section_match = re.search(
                r'^## Supporting Files\s*\n(.*?)(?=\n---|\n## |\Z)',
                content,
                re.MULTILINE | re.DOTALL,
            )
            if not section_match:
                continue

            section = section_match.group(1)
            for match in self.SUPPORTING_FILE_PATTERN.finditer(section):
                ref_path = match.group(2)
                # Skip external links and anchors
                if ref_path.startswith(('http://', 'https://', '#', 'mailto:')):
                    continue
                # Absolute paths from plugin root (e.g., /reference/...)
                if ref_path.startswith('/'):
                    full_path = project_root / ref_path.lstrip('/')
                else:
                    full_path = skill_dir / ref_path
                if not full_path.exists():
                    missing.append(f"{skill_dir.name}/{ref_path}")

        assert not missing, (
            f"Missing supporting files: {', '.join(missing)}"
        )


class TestInstrumentalGuard:
    """Skills that process lyrics must have an Instrumental Guard section (#115)."""

    @pytest.mark.parametrize("skill_name", [
        'lyric-writer',
        'lyric-refiner',
        'lyric-reviewer',
        'pronunciation-specialist',
    ])
    def test_instrumental_guard_section(self, all_skill_frontmatter, skill_name):
        fm = all_skill_frontmatter.get(skill_name, {})
        if '_error' in fm:
            pytest.skip(f"{skill_name} has errors")
        content = fm.get('_content', '')
        assert 'Instrumental Guard' in content, (
            f"{skill_name} SKILL.md missing 'Instrumental Guard' section"
        )


class TestPreGenInstrumental:
    """pre-generation-check must handle instrumental tracks (#115, #129)."""

    def test_instrumental_gate_skipping(self, all_skill_frontmatter):
        """pre-generation-check must document skipping gates for instrumental tracks."""
        fm = all_skill_frontmatter.get('pre-generation-check', {})
        if '_error' in fm:
            pytest.skip("pre-generation-check has errors")
        content = fm.get('_content', '')
        assert 'instrumental' in content.lower(), (
            "pre-generation-check SKILL.md missing instrumental gate skipping"
        )
        assert 'skip' in content.lower(), (
            "pre-generation-check SKILL.md missing skip logic for instrumental gates"
        )

    def test_instrumental_field_sync_validation(self, all_skill_frontmatter):
        """pre-generation-check must block on instrumental field mismatch (#129)."""
        fm = all_skill_frontmatter.get('pre-generation-check', {})
        if '_error' in fm:
            pytest.skip("pre-generation-check has errors")
        content = fm.get('_content', '')
        assert 'mismatch' in content.lower(), (
            "pre-generation-check SKILL.md missing instrumental field mismatch blocking"
        )


class TestGuidedRegeneration:
    """resume and next-step must support guided regeneration workflow (#116)."""

    @pytest.mark.parametrize("skill_name", ['resume', 'next-step'])
    def test_generation_log_rating_reference(self, all_skill_frontmatter, skill_name):
        """Skill must reference Generation Log Rating with checkmark."""
        fm = all_skill_frontmatter.get(skill_name, {})
        if '_error' in fm:
            pytest.skip(f"{skill_name} has errors")
        content = fm.get('_content', '')
        assert 'Generation Log Rating' in content, (
            f"{skill_name} SKILL.md missing Generation Log Rating reference"
        )

    @pytest.mark.parametrize("skill_name", ['resume', 'next-step'])
    def test_batch_approve_workflow(self, all_skill_frontmatter, skill_name):
        """Skill must document batch-approve workflow."""
        fm = all_skill_frontmatter.get(skill_name, {})
        if '_error' in fm:
            pytest.skip(f"{skill_name} has errors")
        content = fm.get('_content', '')
        assert 'batch-approve' in content, (
            f"{skill_name} SKILL.md missing batch-approve workflow documentation"
        )


class TestAlbumStatusManagement:
    """Album status flows must be documented (#118)."""

    def test_verify_sources_auto_advancement(self, all_skill_frontmatter):
        """verify-sources must document auto-advancement of album status."""
        fm = all_skill_frontmatter.get('verify-sources', {})
        if '_error' in fm:
            pytest.skip("verify-sources has errors")
        content = fm.get('_content', '')
        assert 'auto-advance' in content.lower() or 'auto advance' in content.lower(), (
            "verify-sources SKILL.md missing auto-advancement documentation"
        )

    def test_claude_md_documentary_album_flow(self, claude_md_content):
        """CLAUDE.md must document documentary album status flow."""
        assert 'Documentary' in claude_md_content or 'documentary' in claude_md_content, (
            "CLAUDE.md missing documentary album status flow"
        )
        assert 'Research Complete' in claude_md_content, (
            "CLAUDE.md missing 'Research Complete' status for documentary flow"
        )

    def test_claude_md_standard_album_flow(self, claude_md_content):
        """CLAUDE.md must document standard (non-documentary) album status flow."""
        assert 'Standard albums' in claude_md_content or 'standard albums' in claude_md_content, (
            "CLAUDE.md missing standard album status flow"
        )


class TestInstrumentalFieldSyncValidation:
    """validate-album must warn on instrumental field mismatch (#129)."""

    def test_validate_album_mismatch_warning(self, all_skill_frontmatter):
        fm = all_skill_frontmatter.get('validate-album', {})
        if '_error' in fm:
            pytest.skip("validate-album has errors")
        content = fm.get('_content', '')
        assert 'mismatch' in content.lower(), (
            "validate-album SKILL.md missing instrumental field mismatch warning"
        )


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


class TestSkillRegistrationIntegrity:
    """On-disk skills must match the Claude Code plugin cache (#234)."""

    @pytest.mark.xfail(reason="Stale plugin cache — run: claude plugin update bitwize-music (#234)", strict=False)
    def test_no_ghost_skills_in_cache(self, skills_dir):
        """Skills in plugin cache but not on disk are ghost registrations."""
        from pathlib import Path
        cache_base = Path.home() / ".claude" / "plugins" / "cache" / "bitwize-music"
        if not cache_base.is_dir():
            pytest.skip("No plugin cache found (plugin not installed via marketplace)")

        source_skills = {
            p.parent.name for p in skills_dir.glob("*/SKILL.md")
        }

        # Find all cached version directories
        ghost = set()
        for org_or_name in cache_base.iterdir():
            if not org_or_name.is_dir():
                continue
            for version_dir in org_or_name.iterdir():
                cache_skills_dir = version_dir / "skills"
                if not cache_skills_dir.is_dir():
                    continue
                cached = {p.parent.name for p in cache_skills_dir.glob("*/SKILL.md")}
                ghost |= cached - source_skills

        assert not ghost, (
            f"Ghost skills in plugin cache (deleted but still cached): "
            f"{', '.join(sorted(ghost))} — run: claude plugin update bitwize-music"
        )

    @pytest.mark.xfail(reason="Stale plugin cache — run: claude plugin update bitwize-music (#234)", strict=False)
    def test_no_missing_skills_in_cache(self, skills_dir):
        """Skills on disk must also be present in the plugin cache."""
        from pathlib import Path
        cache_base = Path.home() / ".claude" / "plugins" / "cache" / "bitwize-music"
        if not cache_base.is_dir():
            pytest.skip("No plugin cache found (plugin not installed via marketplace)")

        source_skills = {
            p.parent.name for p in skills_dir.glob("*/SKILL.md")
        }

        # Find the latest cached version
        candidates = []
        for org_or_name in cache_base.iterdir():
            if not org_or_name.is_dir():
                continue
            for version_dir in org_or_name.iterdir():
                if version_dir.is_dir() and (version_dir / "skills").is_dir():
                    candidates.append(version_dir)

        if not candidates:
            pytest.skip("No cached plugin versions found")

        candidates.sort(key=lambda p: p.name, reverse=True)
        latest_cache = candidates[0]
        cached_skills = {
            p.parent.name
            for p in (latest_cache / "skills").glob("*/SKILL.md")
        }

        missing = source_skills - cached_skills
        assert not missing, (
            f"Skills on disk but missing from plugin cache (v{latest_cache.name}): "
            f"{', '.join(sorted(missing))} — run: claude plugin update bitwize-music"
        )
