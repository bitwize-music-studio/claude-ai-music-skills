"""Tests for consistent terminology: deprecated terms, path variables, hardcoded paths."""

import re

import pytest

pytestmark = pytest.mark.plugin

DEPRECATED_TERMS = {
    'media_root': 'Use audio_root instead',
    'paths.media_root': 'Use paths.audio_root instead',
    'config/paths.yaml': 'Config is now at ~/.bitwize-music/config.yaml',
    'config/artist.md': 'Config is now at ~/.bitwize-music/config.yaml',
}

# Files that intentionally document deprecated terms
EXCLUDED_FILES = {'skills/test/SKILL.md', 'skills/test/test-definitions.md'}

EXPECTED_PATH_VARS = ['{content_root}', '{audio_root}', '{documents_root}', '{plugin_root}']

HARDCODED_PATH_PATTERNS = [
    (re.compile(r'/Users/[a-zA-Z]+/'), 'Hardcoded macOS home path'),
    (re.compile(r'/home/[a-zA-Z]+/'), 'Hardcoded Linux home path'),
]


def _collect_doc_files(project_root):
    """Collect documentation files to check terminology."""
    files = list(project_root.glob("*.md"))
    files.extend(project_root.glob("config/*.md"))
    files.extend(project_root.glob("config/*.yaml"))
    files.extend(project_root.glob("skills/*/*.md"))
    files.extend(project_root.glob("reference/**/*.md"))
    return files


class TestDeprecatedTerms:
    """No deprecated terminology should be used in docs."""

    @pytest.mark.parametrize("term,replacement", DEPRECATED_TERMS.items())
    def test_no_deprecated_term(self, project_root, term, replacement):
        files = _collect_doc_files(project_root)
        found_in = []
        for file_path in files:
            if not file_path.exists():
                continue
            rel_path = str(file_path.relative_to(project_root))
            if rel_path in EXCLUDED_FILES:
                continue
            content = file_path.read_text()
            if term in content:
                found_in.append(rel_path)

        assert not found_in, (
            f"Deprecated term '{term}' found in: {', '.join(found_in[:5])}. {replacement}"
        )


class TestPathVariables:
    """Expected path variables should be documented in CLAUDE.md."""

    @pytest.mark.parametrize("var", EXPECTED_PATH_VARS)
    def test_path_variable_documented(self, claude_md_content, var):
        assert var in claude_md_content, f"Path variable {var} not found in CLAUDE.md"


class TestHardcodedPaths:
    """No hardcoded user-specific paths outside of examples."""

    @pytest.mark.parametrize("regex,desc", HARDCODED_PATH_PATTERNS)
    def test_no_hardcoded_paths(self, project_root, regex, desc):
        files = _collect_doc_files(project_root)
        found_in = []
        for file_path in files:
            if not file_path.exists():
                continue
            content = file_path.read_text()
            if not regex.search(content):
                continue

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
                    if stripped.startswith('#') or stripped.startswith('//'):
                        continue
                    line_no_code = re.sub(r'`[^`]+`', '', line)
                    if not regex.search(line_no_code):
                        continue
                    found_in.append(f"{file_path.relative_to(project_root)}:{i+1}")

        # Hardcoded paths are warnings, not failures (examples might have them)
        # But we still assert to track them
        assert not found_in, f"{desc} found: {found_in[0]}"
