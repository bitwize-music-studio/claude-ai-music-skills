#!/usr/bin/env python3
"""
Test Runner for claude-ai-music-skills plugin

Automated validation of plugin integrity including:
- SKILL.md frontmatter validation
- Cross-reference checks between docs and skills
- Template completeness verification
- Reference doc existence checks
- Broken internal link detection
- Terminology consistency

Usage:
    python tools/tests/run_tests.py              # Run all tests
    python tools/tests/run_tests.py skills       # Run only skills tests
    python tools/tests/run_tests.py --verbose    # Verbose output
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Try to import yaml, provide helpful error if missing
try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import logging

from tools.shared.colors import Colors
from tools.shared.logging_config import setup_logging
from tools.state.parsers import parse_frontmatter

logger = logging.getLogger(__name__)


class TestResult(Enum):
    OK = "OK"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class TestCase:
    """Single test result."""
    name: str
    result: TestResult
    message: str = ""
    file_path: str = ""
    line_number: int = 0
    fix_hint: str = ""


@dataclass
class TestCategory:
    """Collection of tests in a category."""
    name: str
    tests: List[TestCase] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.result == TestResult.OK)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if t.result == TestResult.FAIL)

    @property
    def warnings(self) -> int:
        return sum(1 for t in self.tests if t.result == TestResult.WARN)

    @property
    def skipped(self) -> int:
        return sum(1 for t in self.tests if t.result == TestResult.SKIP)


class PluginTestRunner:
    """Main test runner for plugin validation."""

    # Required frontmatter fields for SKILL.md files
    REQUIRED_SKILL_FIELDS = {'name', 'description', 'model'}

    # Valid model patterns
    MODEL_PATTERN = re.compile(r'^claude-(opus|sonnet|haiku)-[0-9]+-[0-9]+-[0-9]{8}$')

    # Skills that require external dependencies
    SKILLS_WITH_REQUIREMENTS = {
        'mastering-engineer': ['matchering', 'pyloudnorm', 'scipy', 'numpy', 'soundfile'],
        'promo-director': ['ffmpeg', 'pillow', 'librosa'],
        'sheet-music-publisher': ['AnthemScore', 'MuseScore', 'pypdf', 'reportlab'],
        'document-hunter': ['playwright', 'chromium'],
        'cloud-uploader': ['boto3'],
    }

    # Required templates
    REQUIRED_TEMPLATES = [
        'album.md',
        'track.md',
        'artist.md',
        'research.md',
        'sources.md',
    ]

    # Required Suno reference files
    REQUIRED_SUNO_REFS = [
        'v5-best-practices.md',
        'pronunciation-guide.md',
        'tips-and-tricks.md',
        'structure-tags.md',
        'voice-tags.md',
        'instrumental-tags.md',
        'genre-list.md',
    ]

    # Deprecated terminology that should not be used
    DEPRECATED_TERMS = {
        'media_root': 'Use audio_root instead',
        'paths.media_root': 'Use paths.audio_root instead',
        'config/paths.yaml': 'Config is now at ~/.bitwize-music/config.yaml',
        'config/artist.md': 'Config is now at ~/.bitwize-music/config.yaml',
    }

    def __init__(self, plugin_root: Path, verbose: bool = False):
        self.plugin_root = plugin_root
        self.verbose = verbose
        self.categories: List[TestCategory] = []
        self._skills_cache: Optional[Dict[str, Dict]] = None
        self._claude_md_cache: Optional[str] = None

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(f"  {Colors.CYAN}[DEBUG]{Colors.NC} {message}")

    def get_skills(self) -> Dict[str, Dict]:
        """Get all skills with their parsed frontmatter."""
        if self._skills_cache is not None:
            return self._skills_cache

        skills = {}
        skills_dir = self.plugin_root / "skills"

        if not skills_dir.exists():
            return skills

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                skills[skill_dir.name] = {'_error': 'Missing SKILL.md'}
                continue

            # Parse frontmatter
            content = skill_md.read_text()
            frontmatter = self._parse_frontmatter(content)
            frontmatter['_path'] = str(skill_md)
            frontmatter['_content'] = content
            skills[skill_dir.name] = frontmatter

        self._skills_cache = skills
        return skills

    def get_claude_md(self) -> str:
        """Get CLAUDE.md content."""
        if self._claude_md_cache is not None:
            return self._claude_md_cache

        claude_file = self.plugin_root / "CLAUDE.md"
        if claude_file.exists():
            self._claude_md_cache = claude_file.read_text()
        else:
            self._claude_md_cache = ""
        return self._claude_md_cache

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown content."""
        result = parse_frontmatter(content)
        # For test validation, missing frontmatter is an error
        if not result and not content.startswith('---'):
            return {'_error': 'No frontmatter (missing opening ---)'}
        if not result and content.startswith('---'):
            return {'_error': 'No frontmatter (missing closing ---)'}
        return result

    def run_all_tests(self, categories: Optional[List[str]] = None) -> int:
        """Run all test categories."""
        available_categories = {
            'skills': self.test_skills,
            'templates': self.test_templates,
            'references': self.test_references,
            'links': self.test_internal_links,
            'terminology': self.test_terminology,
            'consistency': self.test_consistency,
            'config': self.test_config,
            'state': self.test_state,
        }

        if categories:
            # Run only specified categories
            for cat in categories:
                if cat in available_categories:
                    available_categories[cat]()
                else:
                    logger.warning("Unknown category: %s", cat)
        else:
            # Run all categories
            for test_func in available_categories.values():
                test_func()

        return self._print_summary()

    def _add_test(self, category: TestCategory, name: str, result: TestResult,
                  message: str = "", file_path: str = "", line_number: int = 0,
                  fix_hint: str = ""):
        """Add a test result to a category."""
        category.tests.append(TestCase(
            name=name,
            result=result,
            message=message,
            file_path=file_path,
            line_number=line_number,
            fix_hint=fix_hint,
        ))

    def _print_category_header(self, name: str):
        """Print category header."""
        print()
        print(f"{Colors.BOLD}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BOLD}CATEGORY: {name}{Colors.NC}")
        print(f"{Colors.BOLD}{'=' * 60}{Colors.NC}")
        print()

    def _print_test_result(self, test: TestCase):
        """Print a single test result."""
        if test.result == TestResult.OK:
            print(f"{Colors.GREEN}[OK]{Colors.NC} {test.name}")
        elif test.result == TestResult.FAIL:
            print(f"{Colors.RED}[FAIL]{Colors.NC} {test.name}")
            if test.message:
                print(f"       -> Problem: {test.message}")
            if test.file_path:
                loc = test.file_path
                if test.line_number:
                    loc += f":{test.line_number}"
                print(f"       -> File: {loc}")
            if test.fix_hint:
                print(f"       -> Fix: {test.fix_hint}")
        elif test.result == TestResult.WARN:
            print(f"{Colors.YELLOW}[WARN]{Colors.NC} {test.name}")
            if test.message:
                print(f"       -> {test.message}")
        elif test.result == TestResult.SKIP:
            print(f"{Colors.BLUE}[SKIP]{Colors.NC} {test.name}")
            if test.message:
                print(f"       -> {test.message}")

    def _print_category_summary(self, category: TestCategory):
        """Print category summary."""
        print()
        print(f"{'-' * 40}")
        parts = [f"{category.passed} passed"]
        if category.failed:
            parts.append(f"{category.failed} failed")
        if category.warnings:
            parts.append(f"{category.warnings} warnings")
        if category.skipped:
            parts.append(f"{category.skipped} skipped")
        print(f"{category.name}: {', '.join(parts)}")
        print(f"{'-' * 40}")

    def _print_summary(self) -> int:
        """Print final summary and return exit code."""
        print()
        print(f"{Colors.BOLD}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BOLD}FINAL RESULTS{Colors.NC}")
        print(f"{Colors.BOLD}{'=' * 60}{Colors.NC}")

        total_passed = 0
        total_failed = 0
        total_warnings = 0
        total_skipped = 0

        for category in self.categories:
            status_parts = []
            status_parts.append(f"{category.passed} passed")
            if category.failed:
                status_parts.append(f"{Colors.RED}{category.failed} failed{Colors.NC}")
            if category.warnings:
                status_parts.append(f"{Colors.YELLOW}{category.warnings} warnings{Colors.NC}")

            print(f"{category.name:20} {', '.join(status_parts)}")

            total_passed += category.passed
            total_failed += category.failed
            total_warnings += category.warnings
            total_skipped += category.skipped

        print(f"{'-' * 40}")
        print(f"{'TOTAL':20} {total_passed} passed, {total_failed} failed, {total_warnings} warnings")
        print(f"{'=' * 60}")

        if total_failed > 0:
            print(f"\n{Colors.RED}Tests FAILED{Colors.NC}")
            return 1
        elif total_warnings > 0:
            print(f"\n{Colors.YELLOW}Tests passed with warnings{Colors.NC}")
            return 0
        else:
            print(f"\n{Colors.GREEN}All tests passed!{Colors.NC}")
            return 0

    # =========================================================================
    # TEST CATEGORIES
    # =========================================================================

    def test_skills(self):
        """Test skill definitions and documentation."""
        category = TestCategory(name="Skills")
        self._print_category_header("Skills")

        skills = self.get_skills()

        # Test: All skill directories have SKILL.md
        self.log("Checking SKILL.md existence...")
        skills_dir = self.plugin_root / "skills"
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                self._add_test(category, f"SKILL.md exists: {skill_dir.name}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"SKILL.md exists: {skill_dir.name}",
                    TestResult.FAIL,
                    "Missing SKILL.md file",
                    str(skill_dir),
                    fix_hint=f"Create {skill_dir}/SKILL.md with required frontmatter"
                )

        # Test: All skills have valid YAML frontmatter
        self.log("Validating YAML frontmatter...")
        for skill_name, frontmatter in skills.items():
            if '_error' in frontmatter:
                self._add_test(
                    category,
                    f"Valid frontmatter: {skill_name}",
                    TestResult.FAIL,
                    frontmatter['_error'],
                    frontmatter.get('_path', ''),
                    fix_hint="Ensure SKILL.md starts with --- and has valid YAML"
                )
            else:
                self._add_test(category, f"Valid frontmatter: {skill_name}", TestResult.OK)

        # Test: All skills have required frontmatter fields
        self.log("Checking required fields...")
        for skill_name, frontmatter in skills.items():
            if '_error' in frontmatter:
                continue

            missing_fields = self.REQUIRED_SKILL_FIELDS - set(frontmatter.keys())
            if missing_fields:
                self._add_test(
                    category,
                    f"Required fields: {skill_name}",
                    TestResult.FAIL,
                    f"Missing fields: {', '.join(missing_fields)}",
                    frontmatter.get('_path', ''),
                    fix_hint=f"Add {', '.join(missing_fields)} to frontmatter"
                )
            else:
                self._add_test(category, f"Required fields: {skill_name}", TestResult.OK)

        # Test: All model references are valid
        self.log("Validating model references...")
        for skill_name, frontmatter in skills.items():
            if '_error' in frontmatter:
                continue

            model = frontmatter.get('model', '')
            if not model:
                continue  # Already caught by required fields check

            if self.MODEL_PATTERN.match(model):
                self._add_test(category, f"Valid model reference: {skill_name}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Valid model reference: {skill_name}",
                    TestResult.FAIL,
                    f"Invalid model: {model}",
                    frontmatter.get('_path', ''),
                    fix_hint="Use format: claude-(opus|sonnet|haiku)-X-X-YYYYMMDD"
                )

        # Test: Skills with external deps have requirements field
        self.log("Checking requirements field for skills with dependencies...")
        for skill_name, expected_deps in self.SKILLS_WITH_REQUIREMENTS.items():
            if skill_name not in skills:
                continue
            frontmatter = skills[skill_name]
            if '_error' in frontmatter:
                continue

            if 'requirements' in frontmatter:
                self._add_test(category, f"Requirements field: {skill_name}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Requirements field: {skill_name}",
                    TestResult.WARN,
                    f"Skill uses external deps ({', '.join(expected_deps[:3])}...) but has no requirements field",
                    frontmatter.get('_path', ''),
                    fix_hint="Add requirements: section listing external dependencies"
                )

        # Test: All skills have required sections
        self.log("Checking SKILL.md required sections...")
        # System skills with non-standard structure (help text, not agent workflows)
        system_skills = {'about', 'help'}

        # Required structural elements with accepted alternatives
        # Each tuple: (check_name, description, list of regex patterns to match)
        required_structure = [
            (
                'agent title (# heading)',
                'Top-level heading identifying the agent',
                [r'^# .+'],
            ),
            (
                'task description',
                'Describes what the skill does (## Your Task, ## Purpose, ## Instructions)',
                [r'^## Your Task', r'^## Purpose', r'^## Instructions'],
            ),
            (
                'procedural content',
                'Step-by-step process or domain expertise sections',
                [r'^## .*Workflow', r'^## Step 1', r'^## Commands',
                 r'^## Research Process', r'^## The \d+-Point Checklist',
                 r'^## Domain Expertise', r'^## Key Skills',
                 r'^## Output Format', r'^## Instructions',
                 r'^## \d+\. '],  # numbered sections like "## 1. CONFIG TESTS"
            ),
            (
                'closing guidance',
                'Summary, rules, or reference sections',
                [r'^## Remember', r'^## Important Notes', r'^## Common Mistakes',
                 r'^## Implementation Notes', r'^## Error Handling',
                 r'^## Troubleshooting', r'^## Adding New Tests'],
            ),
        ]

        for skill_name, frontmatter in skills.items():
            if '_error' in frontmatter or skill_name in system_skills:
                continue
            content = frontmatter.get('_content', '')

            for check_name, desc, patterns in required_structure:
                found = any(
                    re.search(p, content, re.MULTILINE) for p in patterns
                )
                if found:
                    self._add_test(
                        category,
                        f"Has {check_name}: {skill_name}",
                        TestResult.OK
                    )
                else:
                    self._add_test(
                        category,
                        f"Has {check_name}: {skill_name}",
                        TestResult.FAIL,
                        f"Missing section ({desc})",
                        frontmatter.get('_path', ''),
                        fix_hint=f"Add one of the accepted headings for {check_name}"
                    )

        # Test: All skills documented in SKILL_INDEX.md
        self.log("Checking SKILL_INDEX.md skill documentation...")
        skill_index_file = self.plugin_root / "reference" / "SKILL_INDEX.md"
        skill_index_content = ""
        if skill_index_file.exists():
            skill_index_content = skill_index_file.read_text()
        skip_skills = {'help', 'about', 'configure', 'test'}  # System skills

        for skill_name in skills:
            if skill_name in skip_skills:
                continue
            # Check for skill in SKILL_INDEX.md (format: `skill-name` or /skill-name)
            if f"`{skill_name}`" in skill_index_content or f"/{skill_name}" in skill_index_content:
                self._add_test(category, f"Documented in SKILL_INDEX.md: {skill_name}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Documented in SKILL_INDEX.md: {skill_name}",
                    TestResult.FAIL,
                    "Skill not found in SKILL_INDEX.md",
                    "reference/SKILL_INDEX.md",
                    fix_hint=f"Add {skill_name} to the skill index in reference/SKILL_INDEX.md"
                )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)

    def test_templates(self):
        """Test template files."""
        category = TestCategory(name="Templates")
        self._print_category_header("Templates")

        templates_dir = self.plugin_root / "templates"

        # Test: All required templates exist
        self.log("Checking required templates...")
        for template in self.REQUIRED_TEMPLATES:
            template_path = templates_dir / template
            if template_path.exists():
                self._add_test(category, f"Template exists: {template}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Template exists: {template}",
                    TestResult.FAIL,
                    "Required template missing",
                    str(templates_dir),
                    fix_hint=f"Create {template_path}"
                )

        # Test: Templates referenced in CLAUDE.md exist
        self.log("Checking CLAUDE.md template references...")
        claude_content = self.get_claude_md()

        # Find /templates/ references
        template_refs = re.findall(r'/templates/([a-zA-Z0-9_-]+\.md)', claude_content)
        for ref in set(template_refs):
            template_path = templates_dir / ref
            if template_path.exists():
                self._add_test(category, f"Referenced template exists: {ref}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Referenced template exists: {ref}",
                    TestResult.FAIL,
                    "Template referenced in CLAUDE.md but missing",
                    "CLAUDE.md",
                    fix_hint=f"Create {template_path} or update reference in CLAUDE.md"
                )

        # Test: track.md has required sections
        self.log("Checking track.md structure...")
        track_template = templates_dir / "track.md"
        if track_template.exists():
            content = track_template.read_text()
            required_sections = ['Status', 'Suno Inputs', 'Generation Log']
            for section in required_sections:
                if section.lower() in content.lower():
                    self._add_test(category, f"track.md has section: {section}", TestResult.OK)
                else:
                    self._add_test(
                        category,
                        f"track.md has section: {section}",
                        TestResult.WARN,
                        f"Section '{section}' not found in template",
                        str(track_template)
                    )

        # Test: album.md has required sections
        self.log("Checking album.md structure...")
        album_template = templates_dir / "album.md"
        if album_template.exists():
            content = album_template.read_text()
            required_sections = ['Concept', 'Tracklist', 'Production Notes']
            for section in required_sections:
                if section.lower() in content.lower():
                    self._add_test(category, f"album.md has section: {section}", TestResult.OK)
                else:
                    self._add_test(
                        category,
                        f"album.md has section: {section}",
                        TestResult.WARN,
                        f"Section '{section}' not found in template",
                        str(album_template)
                    )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)

    def test_references(self):
        """Test reference documentation."""
        category = TestCategory(name="References")
        self._print_category_header("References")

        reference_dir = self.plugin_root / "reference"
        suno_dir = reference_dir / "suno"

        # Test: Suno reference directory exists
        self.log("Checking Suno reference directory...")
        if suno_dir.exists():
            self._add_test(category, "Suno reference directory exists", TestResult.OK)
        else:
            self._add_test(
                category,
                "Suno reference directory exists",
                TestResult.FAIL,
                "reference/suno/ directory missing",
                str(reference_dir),
                fix_hint="Create reference/suno/ directory"
            )
            # Skip remaining Suno tests
            for test in category.tests:
                self._print_test_result(test)
            self._print_category_summary(category)
            self.categories.append(category)
            return

        # Test: Required Suno reference files exist
        self.log("Checking required Suno reference files...")
        for ref_file in self.REQUIRED_SUNO_REFS:
            ref_path = suno_dir / ref_file
            if ref_path.exists():
                self._add_test(category, f"Suno reference exists: {ref_file}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Suno reference exists: {ref_file}",
                    TestResult.FAIL,
                    "Required reference file missing",
                    str(suno_dir),
                    fix_hint=f"Create {ref_path}"
                )

        # Test: Mastering workflow documentation exists
        self.log("Checking mastering documentation...")
        mastering_doc = reference_dir / "mastering" / "mastering-workflow.md"
        if mastering_doc.exists():
            self._add_test(category, "Mastering workflow doc exists", TestResult.OK)
        else:
            self._add_test(
                category,
                "Mastering workflow doc exists",
                TestResult.FAIL,
                "reference/mastering/mastering-workflow.md missing",
                str(reference_dir / "mastering")
            )

        # Test: References mentioned in CLAUDE.md exist
        self.log("Checking CLAUDE.md reference mentions...")
        claude_content = self.get_claude_md()

        # Find /reference/ paths
        ref_paths = re.findall(r'/reference/([a-zA-Z0-9_/-]+\.md)', claude_content)
        for ref_path in set(ref_paths):
            full_path = reference_dir / ref_path
            if full_path.exists():
                self._add_test(category, f"Referenced doc exists: {ref_path}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Referenced doc exists: {ref_path}",
                    TestResult.FAIL,
                    "Referenced in CLAUDE.md but missing",
                    "CLAUDE.md",
                    fix_hint=f"Create {full_path} or fix reference"
                )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)

    def test_internal_links(self):
        """Test for broken internal markdown links."""
        category = TestCategory(name="Internal Links")
        self._print_category_header("Internal Links")

        # Markdown link pattern: [text](path)
        link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

        files_to_check = [
            self.plugin_root / "CLAUDE.md",
            self.plugin_root / "README.md",
        ]

        # Add all SKILL.md files
        skills_dir = self.plugin_root / "skills"
        if skills_dir.exists():
            for skill_md in skills_dir.glob("*/SKILL.md"):
                files_to_check.append(skill_md)

        # Add template files
        templates_dir = self.plugin_root / "templates"
        if templates_dir.exists():
            for template in templates_dir.glob("*.md"):
                files_to_check.append(template)

        broken_links = []
        checked_count = 0

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            self.log(f"Checking links in: {file_path.name}")
            content = file_path.read_text()
            links = link_pattern.findall(content)

            for link_text, link_target in links:
                # Skip external links and anchors
                if link_target.startswith(('http://', 'https://', '#', 'mailto:')):
                    continue

                # Skip URL placeholders and template examples
                if link_target in ('url', 'URL', 'link', 'path'):
                    continue
                if 'suno.com' in link_target:
                    continue
                # Skip links with bracket placeholders like [artist], [genre]
                if '[' in link_target:
                    continue

                # Skip template placeholder paths (e.g., ../../../README.md, tracks/01-track-name.md)
                if '/templates/' in str(file_path):
                    # In templates, many links are placeholders for users to fill in
                    if link_target.startswith(('../', 'tracks/', '/genres/', 'albums/', 'artists/')):
                        continue
                    # Skip common placeholder names
                    if any(placeholder in link_target.lower() for placeholder in
                           ['album-name', 'artist-name', 'track-name', 'genre-name']):
                        continue

                checked_count += 1

                # Resolve relative links
                if link_target.startswith('/'):
                    # Absolute from repo root
                    target_path = self.plugin_root / link_target.lstrip('/')
                else:
                    # Relative to file
                    target_path = file_path.parent / link_target

                # Remove anchor from path
                if '#' in str(target_path):
                    target_path = Path(str(target_path).split('#')[0])

                if not target_path.exists():
                    broken_links.append({
                        'source': str(file_path.relative_to(self.plugin_root)),
                        'link': link_target,
                        'text': link_text,
                    })

        # Report results
        if not broken_links:
            self._add_test(category, f"All internal links valid ({checked_count} checked)", TestResult.OK)
        else:
            for link in broken_links:
                self._add_test(
                    category,
                    f"Broken link in {link['source']}",
                    TestResult.FAIL,
                    f"Link '{link['link']}' not found",
                    link['source'],
                    fix_hint=f"Fix or remove link: [{link['text']}]({link['link']})"
                )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)

    def test_terminology(self):
        """Test for consistent terminology across docs."""
        category = TestCategory(name="Terminology")
        self._print_category_header("Terminology")

        files_to_check = list(self.plugin_root.glob("*.md"))
        files_to_check.extend(self.plugin_root.glob("config/*.md"))
        files_to_check.extend(self.plugin_root.glob("config/*.yaml"))
        files_to_check.extend(self.plugin_root.glob("skills/*/*.md"))
        files_to_check.extend(self.plugin_root.glob("reference/**/*.md"))

        # Test: No deprecated terminology
        self.log("Checking for deprecated terminology...")
        # Exclude test skill (it documents deprecated terms for test purposes)
        excluded_files = {'skills/test/SKILL.md'}
        for term, replacement in self.DEPRECATED_TERMS.items():
            found_in = []
            for file_path in files_to_check:
                if not file_path.exists():
                    continue
                rel_path = str(file_path.relative_to(self.plugin_root))
                if rel_path in excluded_files:
                    continue
                content = file_path.read_text()
                if term in content:
                    found_in.append(rel_path)

            if not found_in:
                self._add_test(category, f"No deprecated term: {term}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"No deprecated term: {term}",
                    TestResult.FAIL,
                    f"Found in: {', '.join(found_in[:3])}{'...' if len(found_in) > 3 else ''}",
                    found_in[0] if found_in else "",
                    fix_hint=replacement
                )

        # Test: Path variables used consistently
        self.log("Checking path variable consistency...")
        expected_vars = ['{content_root}', '{audio_root}', '{documents_root}', '{plugin_root}']
        claude_content = self.get_claude_md()

        for var in expected_vars:
            if var in claude_content:
                self._add_test(category, f"Path variable documented: {var}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Path variable documented: {var}",
                    TestResult.WARN,
                    "Expected path variable not found in CLAUDE.md",
                    "CLAUDE.md"
                )

        # Test: No hardcoded user-specific paths (outside of examples)
        self.log("Checking for hardcoded paths...")
        hardcoded_patterns = [
            (r'/Users/[a-zA-Z]+/', 'Hardcoded macOS home path'),
            (r'/home/[a-zA-Z]+/', 'Hardcoded Linux home path'),
        ]

        for pattern, desc in hardcoded_patterns:
            regex = re.compile(pattern)
            found_in = []
            for file_path in files_to_check:
                if not file_path.exists():
                    continue
                content = file_path.read_text()
                # Skip if in a code block or example section
                if regex.search(content):
                    # Simple heuristic: skip examples, comments, and code blocks
                    lines = content.split('\n')
                    in_code_block = False
                    for i, line in enumerate(lines):
                        stripped = line.lstrip()
                        if stripped.startswith('```'):
                            in_code_block = not in_code_block
                            continue
                        if in_code_block:
                            continue
                        if regex.search(line) and 'example' not in line.lower():
                            # Skip YAML/code comments
                            if stripped.startswith('#') or stripped.startswith('//'):
                                continue
                            # Skip inline code (match is inside backticks)
                            line_no_code = re.sub(r'`[^`]+`', '', line)
                            if not regex.search(line_no_code):
                                continue
                            found_in.append(f"{file_path.relative_to(self.plugin_root)}:{i+1}")

            if not found_in:
                self._add_test(category, f"No hardcoded paths: {desc}", TestResult.OK)
            else:
                # This is a warning since examples might have these
                self._add_test(
                    category,
                    f"No hardcoded paths: {desc}",
                    TestResult.WARN,
                    f"Potential hardcoded path in: {found_in[0]}",
                    found_in[0] if found_in else "",
                    fix_hint="Replace with path variable or mark as example"
                )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)

    def test_consistency(self):
        """Test cross-reference consistency."""
        category = TestCategory(name="Consistency")
        self._print_category_header("Consistency")

        # Test: Skill count in README matches actual
        self.log("Checking skill count consistency...")
        skills = self.get_skills()
        actual_count = len(skills)

        readme_path = self.plugin_root / "README.md"
        if readme_path.exists():
            readme_content = readme_path.read_text()
            # Look for "XX specialized skills"
            match = re.search(r'\*\*(\d+)\s+specialized skills\*\*', readme_content)
            if match:
                claimed_count = int(match.group(1))
                if claimed_count == actual_count:
                    self._add_test(
                        category,
                        f"README skill count matches ({actual_count})",
                        TestResult.OK
                    )
                else:
                    self._add_test(
                        category,
                        "README skill count matches",
                        TestResult.FAIL,
                        f"README claims {claimed_count}, actual is {actual_count}",
                        "README.md",
                        fix_hint=f"Update README to show {actual_count} skills"
                    )
            else:
                self._add_test(
                    category,
                    "README skill count present",
                    TestResult.WARN,
                    "Could not find skill count pattern in README"
                )

        # Test: plugin.json and marketplace.json versions match
        self.log("Checking version consistency...")
        plugin_json = self.plugin_root / ".claude-plugin" / "plugin.json"
        marketplace_json = self.plugin_root / ".claude-plugin" / "marketplace.json"

        if plugin_json.exists() and marketplace_json.exists():
            import json
            with open(plugin_json) as f:
                plugin_version = json.load(f).get('version', 'unknown')
            with open(marketplace_json) as f:
                marketplace_data = json.load(f)
                marketplace_version = marketplace_data.get('plugins', [{}])[0].get('version', 'unknown')

            if plugin_version == marketplace_version:
                self._add_test(
                    category,
                    f"Version files match ({plugin_version})",
                    TestResult.OK
                )
            else:
                self._add_test(
                    category,
                    "Version files match",
                    TestResult.FAIL,
                    f"plugin.json: {plugin_version}, marketplace.json: {marketplace_version}",
                    ".claude-plugin/",
                    fix_hint="Update both files to the same version"
                )

        # Test: No skill.json files (standard is SKILL.md)
        self.log("Checking for invalid skill.json files...")
        skills_dir = self.plugin_root / "skills"
        skill_json_files = list(skills_dir.glob("*/skill.json"))
        if not skill_json_files:
            self._add_test(category, "No invalid skill.json files", TestResult.OK)
        else:
            for sjf in skill_json_files:
                self._add_test(
                    category,
                    "Invalid skill.json found",
                    TestResult.FAIL,
                    f"Found {sjf.relative_to(self.plugin_root)}",
                    str(sjf),
                    fix_hint="Remove skill.json - use SKILL.md format instead"
                )

        # Test: Model tiers are consistent across SKILL.md files
        self.log("Checking model tier consistency...")
        model_tiers: Dict[str, List[str]] = {}  # tier -> [skill_names]
        for skill_name, frontmatter in skills.items():
            if '_error' in frontmatter:
                continue
            model = frontmatter.get('model', '')
            if 'opus' in model:
                model_tiers.setdefault('opus', []).append(skill_name)
            elif 'sonnet' in model:
                model_tiers.setdefault('sonnet', []).append(skill_name)
            elif 'haiku' in model:
                model_tiers.setdefault('haiku', []).append(skill_name)

        # Check model-strategy.md lists match actual assignments
        strategy_path = self.plugin_root / "reference" / "model-strategy.md"
        if strategy_path.exists():
            strategy_content = strategy_path.read_text()

            for skill_name, frontmatter in skills.items():
                if '_error' in frontmatter:
                    continue
                model = frontmatter.get('model', '')
                if not model:
                    continue

                # Determine actual tier
                if 'opus' in model:
                    actual_tier = 'opus'
                elif 'sonnet' in model:
                    actual_tier = 'sonnet'
                elif 'haiku' in model:
                    actual_tier = 'haiku'
                else:
                    continue

                # Check if model-strategy.md lists this skill under the right section
                # Look for skill name in the section for a DIFFERENT tier
                tier_sections = {
                    'opus': r'## Opus.*?(?=## Sonnet|## Haiku|## Decision|$)',
                    'sonnet': r'## Sonnet.*?(?=## Haiku|## Decision|$)',
                    'haiku': r'## Haiku.*?(?=## Decision|$)',
                }

                # Find which section has a ### heading for this skill
                documented_tier = None
                skill_heading_pattern = re.compile(rf'^### {re.escape(skill_name)}$', re.MULTILINE)
                for tier, pattern in tier_sections.items():
                    section_match = re.search(pattern, strategy_content, re.DOTALL)
                    if section_match and skill_heading_pattern.search(section_match.group()):
                        documented_tier = tier
                        break

                if documented_tier is None:
                    self._add_test(
                        category,
                        f"Model strategy documents: {skill_name}",
                        TestResult.WARN,
                        f"Skill not found in model-strategy.md (actual: {actual_tier})",
                        "reference/model-strategy.md"
                    )
                elif documented_tier != actual_tier:
                    self._add_test(
                        category,
                        f"Model tier match: {skill_name}",
                        TestResult.FAIL,
                        f"SKILL.md says {actual_tier}, model-strategy.md says {documented_tier}",
                        frontmatter.get('_path', ''),
                        fix_hint="Align SKILL.md model with model-strategy.md"
                    )
                else:
                    self._add_test(
                        category,
                        f"Model tier match: {skill_name}",
                        TestResult.OK
                    )

            # Report tier distribution summary
            tier_counts = {t: len(s) for t, s in model_tiers.items()}
            self._add_test(
                category,
                f"Model distribution: opus={tier_counts.get('opus', 0)}, "
                f"sonnet={tier_counts.get('sonnet', 0)}, haiku={tier_counts.get('haiku', 0)}",
                TestResult.OK
            )
        else:
            self._add_test(
                category,
                "Model strategy document exists",
                TestResult.WARN,
                "reference/model-strategy.md not found, skipping tier consistency check"
            )

        # Test: No disable-model-invocation flags
        self.log("Checking for disable-model-invocation flags...")
        skills_with_flag = []
        for skill_name, frontmatter in skills.items():
            if '_error' in frontmatter:
                continue
            if frontmatter.get('disable-model-invocation'):
                skills_with_flag.append(skill_name)

        if not skills_with_flag:
            self._add_test(category, "No disable-model-invocation flags", TestResult.OK)
        else:
            self._add_test(
                category,
                "No disable-model-invocation flags",
                TestResult.WARN,
                f"Skills with flag: {', '.join(skills_with_flag)}",
                fix_hint="Remove disable-model-invocation unless intentional"
            )

        # Test: .gitignore has required entries
        self.log("Checking .gitignore entries...")
        gitignore_path = self.plugin_root / ".gitignore"
        required_ignores = ['artists/', 'research/', '*.pdf', 'mastering-env/']

        if gitignore_path.exists():
            gitignore_content = gitignore_path.read_text()
            for entry in required_ignores:
                # Check if entry or similar pattern exists
                if entry in gitignore_content or entry.rstrip('/') in gitignore_content:
                    self._add_test(category, f".gitignore has: {entry}", TestResult.OK)
                else:
                    self._add_test(
                        category,
                        f".gitignore has: {entry}",
                        TestResult.WARN,
                        "Recommended ignore entry missing",
                        ".gitignore",
                        fix_hint=f"Add '{entry}' to .gitignore"
                    )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)

    def test_config(self):
        """Test configuration files and documentation."""
        category = TestCategory(name="Config")
        self._print_category_header("Config")

        config_dir = self.plugin_root / "config"

        # Test: config.example.yaml exists
        self.log("Checking config.example.yaml...")
        config_example = config_dir / "config.example.yaml"
        if config_example.exists():
            self._add_test(category, "config.example.yaml exists", TestResult.OK)

            # Test: config.example.yaml is valid YAML
            try:
                with open(config_example) as f:
                    config_data = yaml.safe_load(f)
                self._add_test(category, "config.example.yaml is valid YAML", TestResult.OK)

                # Test: Required sections exist
                required_sections = ['artist', 'paths', 'generation']
                for section in required_sections:
                    if section in config_data:
                        self._add_test(category, f"Config has section: {section}", TestResult.OK)
                    else:
                        self._add_test(
                            category,
                            f"Config has section: {section}",
                            TestResult.FAIL,
                            f"Missing '{section}:' section",
                            str(config_example)
                        )

                # Test: Required fields exist
                required_fields = [
                    ('artist', 'name'),
                    ('paths', 'content_root'),
                    ('paths', 'audio_root'),
                ]
                for section, field in required_fields:
                    if section in config_data and field in config_data.get(section, {}):
                        self._add_test(category, f"Config has: {section}.{field}", TestResult.OK)
                    else:
                        self._add_test(
                            category,
                            f"Config has: {section}.{field}",
                            TestResult.FAIL,
                            f"Missing {section}.{field}",
                            str(config_example)
                        )

            except yaml.YAMLError as e:
                self._add_test(
                    category,
                    "config.example.yaml is valid YAML",
                    TestResult.FAIL,
                    str(e),
                    str(config_example)
                )
        else:
            self._add_test(
                category,
                "config.example.yaml exists",
                TestResult.FAIL,
                "Required config template missing",
                str(config_dir)
            )

        # Test: config/README.md exists
        self.log("Checking config documentation...")
        config_readme = config_dir / "README.md"
        if config_readme.exists():
            self._add_test(category, "config/README.md exists", TestResult.OK)
        else:
            self._add_test(
                category,
                "config/README.md exists",
                TestResult.WARN,
                "Config documentation missing",
                str(config_dir)
            )

        # Test: Config location documented consistently
        self.log("Checking config path documentation...")
        claude_content = self.get_claude_md()
        if '~/.bitwize-music/config.yaml' in claude_content:
            self._add_test(category, "Config path documented in CLAUDE.md", TestResult.OK)
        else:
            self._add_test(
                category,
                "Config path documented in CLAUDE.md",
                TestResult.FAIL,
                "Should reference ~/.bitwize-music/config.yaml",
                "CLAUDE.md"
            )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)


    def test_state(self):
        """Test state cache tool files and structure."""
        category = TestCategory(name="State Cache")
        self._print_category_header("State Cache")

        state_dir = self.plugin_root / "tools" / "state"

        # Test: tools/state/ directory exists
        self.log("Checking state tool directory...")
        if state_dir.exists():
            self._add_test(category, "State tool directory exists", TestResult.OK)
        else:
            self._add_test(
                category,
                "State tool directory exists",
                TestResult.FAIL,
                "tools/state/ directory missing",
                str(self.plugin_root / "tools"),
                fix_hint="Create tools/state/ directory"
            )
            for test in category.tests:
                self._print_test_result(test)
            self._print_category_summary(category)
            self.categories.append(category)
            return

        # Test: Required Python files exist
        required_files = [
            ('__init__.py', 'Package init'),
            ('indexer.py', 'CLI indexer'),
            ('parsers.py', 'Markdown parsers'),
        ]
        for filename, desc in required_files:
            filepath = state_dir / filename
            if filepath.exists():
                self._add_test(category, f"State file exists: {filename} ({desc})", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"State file exists: {filename} ({desc})",
                    TestResult.FAIL,
                    f"Missing {filename}",
                    str(state_dir),
                    fix_hint=f"Create tools/state/{filename}"
                )

        # Test: Schema version constant exists in indexer.py
        self.log("Checking schema version constant...")
        indexer_path = state_dir / "indexer.py"
        if indexer_path.exists():
            content = indexer_path.read_text()
            if 'CURRENT_VERSION' in content:
                self._add_test(category, "Schema version constant exists", TestResult.OK)

                # Check it's a valid semver string
                version_match = re.search(r'CURRENT_VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\']', content)
                if version_match:
                    self._add_test(
                        category,
                        f"Schema version is valid semver ({version_match.group(1)})",
                        TestResult.OK
                    )
                else:
                    self._add_test(
                        category,
                        "Schema version is valid semver",
                        TestResult.FAIL,
                        "CURRENT_VERSION should be a semver string like '1.0.0'",
                        str(indexer_path)
                    )
            else:
                self._add_test(
                    category,
                    "Schema version constant exists",
                    TestResult.FAIL,
                    "CURRENT_VERSION not found in indexer.py",
                    str(indexer_path)
                )

        # Test: Test directory and files exist
        self.log("Checking state test files...")
        test_dir = state_dir / "tests"
        test_files = [
            'test_parsers.py',
            'test_indexer.py',
        ]
        for test_file in test_files:
            test_path = test_dir / test_file
            if test_path.exists():
                self._add_test(category, f"State test exists: {test_file}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"State test exists: {test_file}",
                    TestResult.FAIL,
                    f"Missing {test_file}",
                    str(test_dir),
                    fix_hint=f"Create tools/state/tests/{test_file}"
                )

        # Test: Fixture files exist
        fixtures_dir = test_dir / "fixtures"
        fixture_files = ['album-readme.md', 'track-file.md', 'ideas.md']
        for fixture in fixture_files:
            fixture_path = fixtures_dir / fixture
            if fixture_path.exists():
                self._add_test(category, f"Test fixture exists: {fixture}", TestResult.OK)
            else:
                self._add_test(
                    category,
                    f"Test fixture exists: {fixture}",
                    TestResult.WARN,
                    f"Missing test fixture {fixture}",
                    str(fixtures_dir)
                )

        # Test: Run parser unit tests as subprocess
        self.log("Running state parser tests...")
        import subprocess
        try:
            test_timeout = int(os.environ.get('BITWIZE_TEST_TIMEOUT', '60'))
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tools/state/tests/test_parsers.py', '-q', '--tb=short'],
                capture_output=True, text=True, timeout=test_timeout,
                cwd=str(self.plugin_root)
            )
            if result.returncode == 0:
                # Extract test count from output
                lines = result.stdout.strip().split('\n')
                summary = lines[-1] if lines else 'passed'
                self._add_test(category, f"Parser unit tests pass ({summary.strip()})", TestResult.OK)
            else:
                self._add_test(
                    category,
                    "Parser unit tests pass",
                    TestResult.FAIL,
                    result.stdout.strip().split('\n')[-1] if result.stdout else result.stderr[:200],
                    "tools/state/tests/test_parsers.py"
                )
        except FileNotFoundError:
            self._add_test(
                category,
                "Parser unit tests pass",
                TestResult.SKIP,
                "pytest not installed"
            )
        except subprocess.TimeoutExpired:
            self._add_test(
                category,
                "Parser unit tests pass",
                TestResult.FAIL,
                f"Tests timed out after {test_timeout}s (set BITWIZE_TEST_TIMEOUT to increase)"
            )

        # Print results
        for test in category.tests:
            self._print_test_result(test)

        self._print_category_summary(category)
        self.categories.append(category)


def main():
    parser = argparse.ArgumentParser(
        description='Run plugin validation tests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_tests.py              # Run all tests
    python run_tests.py skills       # Run only skills tests
    python run_tests.py --verbose    # Verbose output
    python run_tests.py skills templates -v  # Multiple categories with verbose

Categories:
    skills       - Skill definitions and YAML frontmatter
    templates    - Template file validation
    references   - Reference documentation
    links        - Internal markdown links
    terminology  - Consistent language
    consistency  - Cross-reference checks
    config       - Configuration files
    state        - State cache tool validation
        """
    )
    parser.add_argument(
        'categories',
        nargs='*',
        help='Specific test categories to run (default: all)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    args = parser.parse_args()

    # Disable colors if requested or if not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    # Find plugin root (parent of tools/tests/)
    script_path = Path(__file__).resolve()
    plugin_root = script_path.parent.parent.parent

    setup_logging(__name__)

    # Verify we're in the right place
    if not (plugin_root / "CLAUDE.md").exists():
        logger.error("CLAUDE.md not found at %s", plugin_root)
        logger.error("Run this script from within the plugin directory.")
        sys.exit(1)

    print(f"{Colors.BOLD}Plugin Test Runner{Colors.NC}")
    print(f"Plugin root: {plugin_root}")
    print()

    runner = PluginTestRunner(plugin_root, verbose=args.verbose)
    exit_code = runner.run_all_tests(args.categories if args.categories else None)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
