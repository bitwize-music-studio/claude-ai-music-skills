"""Tests for tools/validate_help_completeness.py."""

import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.validate_help_completeness import (
    check_help_skill,
    check_router_ghosts,
    get_all_skills,
)


def make_repo(
    tmp_path: Path,
    skills: list[str],
    help_refs: list[str],
    rules_refs: list[str],
    arrow_refs: tuple[str, ...] = (),
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
    rules_lines = "\n".join(f"- use `/bitwize-music:{r}` here" for r in rules_refs)
    rules_lines += "\n" + "\n".join(f"- Do a thing → `{r}`" for r in arrow_refs)
    (tmp_path / "reference").mkdir(exist_ok=True)
    (tmp_path / "reference" / "plugin-rules.md").write_text(f"# Test\n{rules_lines}\n")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n\n@reference/plugin-rules.md\n")
    return tmp_path


def test_help_gap_detected(tmp_path):
    root = make_repo(tmp_path, ["alpha", "beta"], help_refs=["alpha", "help"], rules_refs=[])
    skills = get_all_skills(root)
    assert "beta" in check_help_skill(root, skills)


def test_help_complete_passes(tmp_path):
    root = make_repo(tmp_path, ["alpha", "beta"], help_refs=["alpha", "beta", "help"], rules_refs=[])
    skills = get_all_skills(root)
    assert check_help_skill(root, skills) == []


def test_rules_ghost_detected(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], rules_refs=["alpha", "no-such-skill"])
    skills = get_all_skills(root)
    assert check_router_ghosts(root, skills) == ["no-such-skill"]


def test_rules_curated_is_not_a_finding(tmp_path):
    root = make_repo(tmp_path, ["alpha", "beta"], help_refs=["alpha", "beta", "help"], rules_refs=["alpha"])
    skills = get_all_skills(root)
    assert check_router_ghosts(root, skills) == []


def test_discovery_ignores_dirs_without_skill_md(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], rules_refs=[])
    (root / "skills" / "not-a-skill").mkdir()
    assert "not-a-skill" not in get_all_skills(root)


def test_bare_arrow_ghost_detected(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], rules_refs=[], arrow_refs=("alpha", "gone"))
    assert check_router_ghosts(root, get_all_skills(root)) == ["gone"]


def test_mcp_tool_names_after_an_arrow_are_not_skills(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], rules_refs=[], arrow_refs=("list_skills",))
    assert check_router_ghosts(root, get_all_skills(root)) == []


def test_agents_md_is_scanned_too(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], rules_refs=["alpha"])
    (root / "AGENTS.md").write_text("Run `/bitwize-music:retired-skill` first.\n")
    assert check_router_ghosts(root, get_all_skills(root)) == ["retired-skill"]


def test_a_missing_rules_file_is_a_finding(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], rules_refs=[])
    (root / "reference" / "plugin-rules.md").unlink()
    assert check_router_ghosts(root, get_all_skills(root)) == ["<missing reference/plugin-rules.md>"]


def test_arrows_in_agents_md_prose_are_not_skill_references(tmp_path):
    root = make_repo(tmp_path, ["alpha"], help_refs=["alpha", "help"], rules_refs=["alpha"])
    (root / "AGENTS.md").write_text("Release: merge `develop` → `main`.\n")
    assert check_router_ghosts(root, get_all_skills(root)) == []


def test_the_real_repo_has_no_ghosts():
    assert check_router_ghosts(PROJECT_ROOT, get_all_skills(PROJECT_ROOT)) == []
