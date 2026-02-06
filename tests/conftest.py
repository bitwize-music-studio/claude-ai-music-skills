"""Shared pytest fixtures for plugin and unit tests."""

import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state.parsers import parse_frontmatter


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Path to the repository root."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def skills_dir(project_root) -> Path:
    """Path to skills/ directory."""
    return project_root / "skills"


@pytest.fixture(scope="session")
def templates_dir(project_root) -> Path:
    """Path to templates/ directory."""
    return project_root / "templates"


@pytest.fixture(scope="session")
def reference_dir(project_root) -> Path:
    """Path to reference/ directory."""
    return project_root / "reference"


@pytest.fixture(scope="session")
def genres_dir(project_root) -> Path:
    """Path to genres/ directory."""
    return project_root / "genres"


@pytest.fixture(scope="session")
def config_dir(project_root) -> Path:
    """Path to config/ directory."""
    return project_root / "config"


@pytest.fixture(scope="session")
def all_skill_dirs(skills_dir) -> list:
    """List of all skill directory paths."""
    if not skills_dir.exists():
        return []
    return sorted(
        d for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    )


@pytest.fixture(scope="session")
def all_skill_frontmatter(all_skill_dirs) -> Dict[str, Dict[str, Any]]:
    """Dict of skill_name -> parsed frontmatter for all skills."""
    skills = {}
    for skill_dir in all_skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            skills[skill_dir.name] = {'_error': 'Missing SKILL.md'}
            continue

        content = skill_md.read_text()
        frontmatter = parse_frontmatter(content)

        if not frontmatter and not content.startswith('---'):
            frontmatter = {'_error': 'No frontmatter (missing opening ---)'}
        elif not frontmatter and content.startswith('---'):
            frontmatter = {'_error': 'No frontmatter (missing closing ---)'}

        frontmatter['_path'] = str(skill_md)
        frontmatter['_content'] = content
        skills[skill_dir.name] = frontmatter

    return skills


@pytest.fixture(scope="session")
def claude_md_content(project_root) -> str:
    """Contents of CLAUDE.md."""
    claude_file = project_root / "CLAUDE.md"
    if claude_file.exists():
        return claude_file.read_text()
    return ""
