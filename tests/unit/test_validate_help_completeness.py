"""Tests for tools/validate_help_completeness.py."""

import importlib.util
import sys
from pathlib import Path

# Import the standalone tools/ script via importlib (validate_help_completeness.py
# is a top-level tools/ script, not a member of a tools.* subpackage).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_MODULE_PATH = _PROJECT_ROOT / "tools" / "validate_help_completeness.py"
_spec = importlib.util.spec_from_file_location("validate_help_completeness", _MODULE_PATH)
vhc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vhc)


def make_repo(
    tmp_path: Path,
    skills: list[str],
    help_refs: list[str],
    claude_refs: list[str],
) -> Path:
    """Build a minimal fake plugin repo."""
    for name in skills:
        skill_dir = tmp_path / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\nbody\n")
    help_dir = tmp_path / "skills" / "help"
    help_dir.mkdir(parents=True, exist_ok=True)
    help_lines = "\n".join(f"- `/bitwize-music:{r}` - desc" for r in help_refs)
    (help_dir / "SKILL.md").write_text(f"---\nname: help\n---\n{help_lines}\n")
    claude_lines = "\n".join(f"- use `/bitwize-music:{r}` here" for r in claude_refs)
    (tmp_path / "CLAUDE.md").write_text(f"# Test\n{claude_lines}\n")
    return tmp_path


def test_help_gap_detected(tmp_path):
    root = make_repo(tmp_path, ["alpha", "beta"], help_refs=["alpha", "help"], claude_refs=[])
    skills = vhc.get_all_skills(root)
    assert "beta" in vhc.check_help_skill(root, skills)


def test_help_complete_passes(tmp_path):
    root = make_repo(tmp_path, ["alpha", "beta"], help_refs=["alpha", "beta", "help"], claude_refs=[])
    skills = vhc.get_all_skills(root)
    assert vhc.check_help_skill(root, skills) == []


def test_claude_ghost_detected(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], claude_refs=["alpha", "no-such-skill"])
    skills = vhc.get_all_skills(root)
    assert vhc.check_claude_md_ghosts(root, skills) == ["no-such-skill"]


def test_claude_curated_is_not_a_finding(tmp_path):
    root = make_repo(tmp_path, ["alpha", "beta"], help_refs=["alpha", "beta", "help"], claude_refs=["alpha"])
    skills = vhc.get_all_skills(root)
    assert vhc.check_claude_md_ghosts(root, skills) == []


def test_discovery_ignores_dirs_without_skill_md(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], claude_refs=[])
    (root / "skills" / "not-a-skill").mkdir()
    assert "not-a-skill" not in vhc.get_all_skills(root)
