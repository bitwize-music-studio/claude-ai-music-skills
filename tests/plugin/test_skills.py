"""Tests for skill definitions: frontmatter, model refs, prerequisites, sections."""

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.plugin

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _plugin_version() -> str | None:
    """Version declared in .claude-plugin/plugin.json, or None if unreadable."""
    plugin_json = PROJECT_ROOT / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(plugin_json.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None

# Required frontmatter fields
REQUIRED_SKILL_FIELDS = {'name', 'description', 'model'}

# Valid model values: tier aliases (auto-track the frontier model of that tier) or
# the special values inherit/default. Pinned model IDs are intentionally rejected —
# skills must use an alias so new model releases need no file edits.
MODEL_PATTERN = re.compile(r'^(opus|sonnet|haiku|inherit|default)$')

# Valid values for the `effort:` frontmatter field. Availability is
# model-dependent (e.g. xhigh is unsupported on Sonnet 4.6); Claude Code falls
# back to the highest supported level at or below the one set.
VALID_EFFORT = {'low', 'medium', 'high', 'xhigh', 'max'}

# Model tiers that honor the `effort:` setting. Haiku does NOT support effort,
# so setting it there is a no-op and we keep it off those skills.
EFFORT_CAPABLE_TIERS = {'opus', 'sonnet'}


def _model_tier(model: str) -> str:
    """Derive tier (opus/sonnet/haiku) from a model alias or pinned ID."""
    lowered = (model or '').lower()
    for tier in ('opus', 'sonnet', 'haiku'):
        if tier in lowered:
            return tier
    return 'unknown'

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


def _skill_frontmatter(all_skill_frontmatter, skill_name: str) -> dict:
    """Return a named skill's parsed frontmatter, failing hard if unusable.

    A skill that is absent from skills/ or whose YAML frontmatter fails to
    parse is a broken plugin asset, not a reason to skip: skipping reports
    green for a shipped file that Claude Code cannot load. (On Windows a
    path/encoding failure surfaces here too, so a skip would hide an
    OS-specific breakage.)
    """
    fm = all_skill_frontmatter.get(skill_name)
    assert fm is not None, (
        f"Skill '{skill_name}' not found in skills/ — expected "
        f"skills/{skill_name}/SKILL.md"
    )
    assert '_error' not in fm, (
        f"skills/{skill_name}/SKILL.md frontmatter failed to parse: {fm['_error']}"
    )
    return fm


def _skill_content(all_skill_frontmatter, skill_name: str) -> str:
    """Return a named skill's SKILL.md body, failing hard if unusable."""
    return _skill_frontmatter(all_skill_frontmatter, skill_name).get('_content', '')


def _cache_dir_for_this_version() -> Path | None:
    """Plugin cache dir matching this checkout's version, or None if absent."""
    version = _plugin_version()
    if not version:
        return None
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "bitwize-music"
    if not cache_base.is_dir():
        return None
    for org_or_name in cache_base.iterdir():
        if not org_or_name.is_dir():
            continue
        candidate = org_or_name / version
        if (candidate / "skills").is_dir():
            return candidate
    return None


@pytest.fixture(scope="module")
def cached_skills() -> set:
    """Skill names registered in the plugin cache entry for this version.

    Skips when there is no cache entry for this exact version — the only
    honest "nothing to compare" state. See TestSkillRegistrationIntegrity.
    """
    cache_dir = _cache_dir_for_this_version()
    if cache_dir is None:
        pytest.skip(
            f"No plugin cache entry for v{_plugin_version()} "
            f"(plugin not installed from the marketplace at this version) "
            f"— nothing to compare against"
        )
    return {p.parent.name for p in (cache_dir / "skills").glob("*/SKILL.md")}


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


class TestEffortLevels:
    """The `effort:` field must be valid and present on effort-capable skills."""

    def test_effort_value_valid(self, all_skill_frontmatter):
        invalid = {}
        for name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            effort = fm.get('effort')
            if effort is not None and effort not in VALID_EFFORT:
                invalid[name] = effort
        assert not invalid, (
            f"Invalid effort values (allowed: {sorted(VALID_EFFORT)}): {invalid}"
        )

    def test_effort_present_on_capable_skills(self, all_skill_frontmatter):
        missing = {}
        for name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            tier = _model_tier(fm.get('model', ''))
            if tier in EFFORT_CAPABLE_TIERS and not fm.get('effort'):
                missing[name] = tier
        assert not missing, (
            f"Opus/Sonnet skills must set an effort level: {missing}"
        )

    def test_effort_absent_on_haiku_skills(self, all_skill_frontmatter):
        # Haiku does not support effort; setting it is a misleading no-op.
        present = {}
        for name, fm in all_skill_frontmatter.items():
            if '_error' in fm:
                continue
            if _model_tier(fm.get('model', '')) == 'haiku' and fm.get('effort'):
                present[name] = fm.get('effort')
        assert not present, (
            f"Haiku skills must not set effort (unsupported, no-op): {present}"
        )


class TestRequirements:
    """Skills with external deps should have requirements field."""

    def test_requirements_field(self, all_skill_frontmatter):
        """Skills with external dependencies must declare a `requirements` field.

        Every skill in SKILLS_WITH_REQUIREMENTS ships today with a requirements
        field, so this is a real, currently-satisfied invariant — not advisory.
        Dropping the field would leave `/bitwize-music:setup` unable to see the
        skill's dependencies.
        """
        missing = []
        for skill_name, expected_deps in SKILLS_WITH_REQUIREMENTS.items():
            fm = _skill_frontmatter(all_skill_frontmatter, skill_name)
            if 'requirements' not in fm:
                missing.append(
                    f"{skill_name} uses {', '.join(expected_deps[:3])}... "
                    f"but has no requirements field"
                )
        assert not missing, (
            "Skills with external dependencies missing a `requirements` field:\n"
            + "\n".join(missing)
        )


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
        content = _skill_content(all_skill_frontmatter, skill_name)
        assert 'Instrumental Guard' in content, (
            f"{skill_name} SKILL.md missing 'Instrumental Guard' section"
        )


class TestPreGenInstrumental:
    """pre-generation-check must handle instrumental tracks (#115, #129)."""

    def test_instrumental_gate_skipping(self, all_skill_frontmatter):
        """pre-generation-check must document skipping gates for instrumental tracks."""
        content = _skill_content(all_skill_frontmatter, 'pre-generation-check')
        assert 'instrumental' in content.lower(), (
            "pre-generation-check SKILL.md missing instrumental gate skipping"
        )
        assert 'skip' in content.lower(), (
            "pre-generation-check SKILL.md missing skip logic for instrumental gates"
        )

    def test_instrumental_field_sync_validation(self, all_skill_frontmatter):
        """pre-generation-check must block on instrumental field mismatch (#129)."""
        content = _skill_content(all_skill_frontmatter, 'pre-generation-check')
        assert 'mismatch' in content.lower(), (
            "pre-generation-check SKILL.md missing instrumental field mismatch blocking"
        )


class TestGuidedRegeneration:
    """resume and next-step must support guided regeneration workflow (#116)."""

    @pytest.mark.parametrize("skill_name", ['resume', 'next-step'])
    def test_generation_log_rating_reference(self, all_skill_frontmatter, skill_name):
        """Skill must reference Generation Log Rating with checkmark."""
        content = _skill_content(all_skill_frontmatter, skill_name)
        assert 'Generation Log Rating' in content, (
            f"{skill_name} SKILL.md missing Generation Log Rating reference"
        )

    @pytest.mark.parametrize("skill_name", ['resume', 'next-step'])
    def test_batch_approve_workflow(self, all_skill_frontmatter, skill_name):
        """Skill must document batch-approve workflow."""
        content = _skill_content(all_skill_frontmatter, skill_name)
        assert 'batch-approve' in content, (
            f"{skill_name} SKILL.md missing batch-approve workflow documentation"
        )


class TestAlbumStatusManagement:
    """Album status flows must be documented (#118)."""

    def test_verify_sources_auto_advancement(self, all_skill_frontmatter):
        """verify-sources must document auto-advancement of album status."""
        content = _skill_content(all_skill_frontmatter, 'verify-sources')
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
        content = _skill_content(all_skill_frontmatter, 'validate-album')
        assert 'mismatch' in content.lower(), (
            "validate-album SKILL.md missing instrumental field mismatch warning"
        )


class TestSkillIndex:
    """All skills must be documented in SKILL_INDEX.md."""

    def test_skills_in_index(self, all_skill_frontmatter, reference_dir):
        skill_index_file = reference_dir / "SKILL_INDEX.md"
        assert skill_index_file.exists(), (
            "reference/SKILL_INDEX.md missing — it is a required plugin asset "
            "(CLAUDE.md routes skill lookups through it)"
        )

        index_content = skill_index_file.read_text(encoding="utf-8")
        missing = []
        for skill_name in all_skill_frontmatter:
            if skill_name in SKIP_SKILLS_INDEX:
                continue
            if f"`{skill_name}`" not in index_content and f"/{skill_name}" not in index_content:
                missing.append(skill_name)

        assert not missing, f"Skills not in SKILL_INDEX.md: {', '.join(missing)}"


class TestSkillRegistrationIntegrity:
    """On-disk skills must match the Claude Code plugin cache (#234).

    The plugin cache is a *local developer artifact* — Claude Code populates
    ~/.claude/plugins/cache/ when the plugin is installed from the marketplace,
    and it is keyed by released version. There are exactly two honest states:

    * no cache entry for the version in this working tree — nothing to compare,
      so these tests skip (CI runners and any checkout whose version has not been
      released yet land here);
    * a cache entry for this exact version exists — the cached skill set must
      then match skills/ on disk, and a mismatch is a real defect that must fail.

    This replaces a blanket ``xfail(strict=False)``, which passed whether the
    assertion held or not and so guarded nothing. Anchoring to the working
    tree's own version also fixes a latent bug in the ghost check: it used to
    union *every* cached version, so a skill legitimately deleted three releases
    ago was reported as a ghost forever.
    """

    def test_no_ghost_skills_in_cache(self, skills_dir, cached_skills):
        """Skills in plugin cache but not on disk are ghost registrations."""
        source_skills = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
        assert source_skills, "No skills found on disk in skills/*/SKILL.md"

        ghost = cached_skills - source_skills
        assert not ghost, (
            f"Ghost skills in plugin cache v{_plugin_version()} (deleted from "
            f"skills/ but still registered): {', '.join(sorted(ghost))} "
            f"— run: claude plugin update bitwize-music"
        )

    def test_no_missing_skills_in_cache(self, skills_dir, cached_skills):
        """Skills on disk must also be present in the plugin cache."""
        source_skills = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
        assert source_skills, "No skills found on disk in skills/*/SKILL.md"

        missing = source_skills - cached_skills
        assert not missing, (
            f"Skills on disk but missing from plugin cache v{_plugin_version()}: "
            f"{', '.join(sorted(missing))} — run: claude plugin update bitwize-music"
        )
