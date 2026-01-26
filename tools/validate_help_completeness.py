#!/usr/bin/env python3
"""
Validation script: Check that all skills are documented in help system

Cross-platform validation to ensure no skill is forgotten in documentation.
Run this before committing changes that add new skills.
"""

import sys
from pathlib import Path
from typing import List, Set

# ANSI colors for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

def get_all_skills(plugin_root: Path) -> List[str]:
    """Find all skills (directories under skills/ with SKILL.md)."""
    skills_dir = plugin_root / "skills"
    skills = []

    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                skills.append(skill_dir.name)

    return skills

def check_claude_md(plugin_root: Path, skills: List[str]) -> List[str]:
    """Check which skills are missing from CLAUDE.md."""
    claude_file = plugin_root / "CLAUDE.md"

    if not claude_file.exists():
        print(f"{RED}✗ CLAUDE.md not found!{NC}")
        return skills

    claude_content = claude_file.read_text()
    missing = []

    # Skip system/internal skills
    skip_skills = {'help', 'about', 'configure', 'test'}

    for skill in skills:
        if skill in skip_skills:
            continue

        # Check for skill reference
        skill_pattern = f"/bitwize-music:{skill}"
        if skill_pattern not in claude_content:
            missing.append(skill)

    return missing

def check_help_skill(plugin_root: Path, skills: List[str]) -> List[str]:
    """Check which skills are missing from skills/help/SKILL.md."""
    help_file = plugin_root / "skills" / "help" / "SKILL.md"

    if not help_file.exists():
        print(f"{RED}✗ skills/help/SKILL.md not found!{NC}")
        return skills

    help_content = help_file.read_text()
    missing = []

    # Skip the help skill itself
    for skill in skills:
        if skill == 'help':
            continue

        # Check for skill reference
        skill_pattern = f"/bitwize-music:{skill}"
        if skill_pattern not in help_content:
            missing.append(skill)

    return missing

def main():
    print("🔍 Validating skill documentation completeness...")
    print()

    # Get plugin root directory
    plugin_root = Path(__file__).parent.parent

    # Find all skills
    all_skills = get_all_skills(plugin_root)

    if not all_skills:
        print(f"{RED}✗ No skills found!{NC}")
        return 1

    print(f"Found {len(all_skills)} skills:")
    for skill in all_skills:
        print(f"  - {skill}")
    print()

    errors = 0

    # Check CLAUDE.md
    print("📋 Checking CLAUDE.md skills table...")
    missing_claude = check_claude_md(plugin_root, all_skills)

    if not missing_claude:
        print(f"{GREEN}✓ All skills documented in CLAUDE.md{NC}")
    else:
        print(f"{RED}✗ Skills missing from CLAUDE.md:{NC}")
        for skill in missing_claude:
            print(f"  - {skill}")
        errors += len(missing_claude)
    print()

    # Check help system
    print("📋 Checking skills/help/SKILL.md...")
    missing_help = check_help_skill(plugin_root, all_skills)

    if not missing_help:
        print(f"{GREEN}✓ All skills documented in help system{NC}")
    else:
        print(f"{RED}✗ Skills missing from help system:{NC}")
        for skill in missing_help:
            print(f"  - {skill}")
        errors += len(missing_help)
    print()

    # Summary
    print("━" * 40)
    if errors == 0:
        print(f"{GREEN}✓ All skills properly documented!{NC}")
        print()
        print("All skills are listed in:")
        print("  - CLAUDE.md (main skills table)")
        print("  - skills/help/SKILL.md (help system)")
        return 0
    else:
        print(f"{RED}✗ Found {errors} documentation issues{NC}")
        print()
        print("To fix:")
        print("  1. Add missing skills to CLAUDE.md skills table")
        print("  2. Add missing skills to skills/help/SKILL.md")
        print("  3. Update CHANGELOG.md with the changes")
        print()
        print("See CONTRIBUTING.md for complete checklist")
        return 1

if __name__ == '__main__':
    sys.exit(main())
