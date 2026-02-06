"""Tests for internal markdown link validation."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.plugin


def _collect_markdown_files(project_root):
    """Collect markdown files to check for broken links."""
    files = [
        project_root / "CLAUDE.md",
        project_root / "README.md",
    ]

    skills_dir = project_root / "skills"
    if skills_dir.exists():
        files.extend(skills_dir.glob("*/SKILL.md"))

    templates_dir = project_root / "templates"
    if templates_dir.exists():
        files.extend(templates_dir.glob("*.md"))

    return [f for f in files if f.exists()]


def _is_skippable_link(link_target, file_path):
    """Check if a link should be skipped from validation."""
    # External links and anchors
    if link_target.startswith(('http://', 'https://', '#', 'mailto:')):
        return True

    # URL placeholders
    if link_target in ('url', 'URL', 'link', 'path'):
        return True
    if 'suno.com' in link_target:
        return True

    # Bracket placeholders like [artist], [genre]
    if '[' in link_target:
        return True

    # Template placeholder paths
    if '/templates/' in str(file_path):
        if link_target.startswith(('../', 'tracks/', '/genres/', 'albums/', 'artists/')):
            return True
        if any(p in link_target.lower() for p in
               ['album-name', 'artist-name', 'track-name', 'genre-name']):
            return True

    return False


class TestInternalLinks:
    """All internal markdown links must resolve to existing files."""

    def test_no_broken_links(self, project_root):
        link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
        files_to_check = _collect_markdown_files(project_root)

        broken_links = []
        checked_count = 0

        for file_path in files_to_check:
            content = file_path.read_text()
            links = link_pattern.findall(content)

            for link_text, link_target in links:
                if _is_skippable_link(link_target, file_path):
                    continue

                checked_count += 1

                # Resolve path
                if link_target.startswith('/'):
                    target_path = project_root / link_target.lstrip('/')
                else:
                    target_path = file_path.parent / link_target

                # Remove anchor
                if '#' in str(target_path):
                    target_path = Path(str(target_path).split('#')[0])

                if not target_path.exists():
                    source = str(file_path.relative_to(project_root))
                    broken_links.append(f"{source}: [{link_text}]({link_target})")

        assert not broken_links, (
            f"Broken internal links ({len(broken_links)} of {checked_count} checked):\n"
            + "\n".join(broken_links)
        )
