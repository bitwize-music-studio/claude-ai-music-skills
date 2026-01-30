#!/usr/bin/env python3
"""
Unit tests for state cache parsers.

Tests each parser function against fixture files.

Usage:
    python -m pytest tools/state/tests/test_parsers.py -v
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from tools.state.parsers import (
    _extract_bold_field,
    _extract_genre_from_path,
    _extract_table_value,
    _normalize_status,
    _parse_track_count,
    _parse_tracklist_table,
    parse_album_readme,
    parse_frontmatter,
    parse_ideas_file,
    parse_track_file,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseFrontmatter:
    """Tests for parse_frontmatter()."""

    def test_valid_frontmatter(self):
        text = '---\ntitle: "Test"\ngenres: ["rock"]\n---\n# Content'
        result = parse_frontmatter(text)
        assert result['title'] == 'Test'
        assert result['genres'] == ['rock']

    def test_no_frontmatter(self):
        text = '# Just a heading\nSome content.'
        result = parse_frontmatter(text)
        assert result == {}

    def test_unclosed_frontmatter(self):
        text = '---\ntitle: "Test"\nno closing delimiter'
        result = parse_frontmatter(text)
        assert result == {}

    def test_empty_frontmatter(self):
        text = '---\n---\n# Content'
        result = parse_frontmatter(text)
        assert result == {}

    def test_frontmatter_with_boolean(self):
        text = '---\nexplicit: true\n---\n'
        result = parse_frontmatter(text)
        assert result['explicit'] is True

    def test_frontmatter_with_empty_string(self):
        text = '---\nrelease_date: ""\n---\n'
        result = parse_frontmatter(text)
        assert result['release_date'] == ''


class TestParseAlbumReadme:
    """Tests for parse_album_readme()."""

    def test_full_album_readme(self):
        path = FIXTURES_DIR / "album-readme.md"
        result = parse_album_readme(path)

        assert '_error' not in result
        assert result['title'] == 'Shell No'
        assert result['status'] == 'In Progress'
        assert result['explicit'] is True
        assert result['track_count'] == 8
        assert result['release_date'] is None or result['release_date'] == ''

    def test_tracklist_parsing(self):
        path = FIXTURES_DIR / "album-readme.md"
        result = parse_album_readme(path)
        tracklist = result['tracklist']

        assert len(tracklist) == 8
        assert tracklist[0]['title'] == 'Boot Sequence'
        assert tracklist[0]['status'] == 'Final'
        assert tracklist[0]['number'] == '01'

        assert tracklist[1]['title'] == 'Fork the World'
        assert tracklist[1]['status'] == 'Generated'

        assert tracklist[2]['title'] == 'Merge Conflict'
        assert tracklist[2]['status'] == 'In Progress'

        assert tracklist[3]['status'] == 'Not Started'

    def test_tracks_completed_count(self):
        path = FIXTURES_DIR / "album-readme.md"
        result = parse_album_readme(path)
        # Final (1) + Generated (1) = 2 completed
        assert result['tracks_completed'] == 2

    def test_nonexistent_file(self):
        path = FIXTURES_DIR / "does-not-exist.md"
        result = parse_album_readme(path)
        assert '_error' in result

    def test_genre_from_frontmatter(self):
        path = FIXTURES_DIR / "album-readme.md"
        result = parse_album_readme(path)
        # First genre from frontmatter list
        assert result['genre'] == 'electronic'


class TestParseTrackFile:
    """Tests for parse_track_file()."""

    def test_final_track(self):
        path = FIXTURES_DIR / "track-file.md"
        result = parse_track_file(path)

        assert '_error' not in result
        assert result['title'] == 'Boot Sequence'
        assert result['status'] == 'Final'
        assert result['explicit'] is True
        assert result['has_suno_link'] is True
        assert result['sources_verified'] == 'Verified'

    def test_not_started_track(self):
        path = FIXTURES_DIR / "track-not-started.md"
        result = parse_track_file(path)

        assert '_error' not in result
        assert result['title'] == 'Kernel Panic'
        assert result['status'] == 'Not Started'
        assert result['explicit'] is False
        assert result['has_suno_link'] is False
        assert result['sources_verified'] == 'Pending'

    def test_nonexistent_file(self):
        path = FIXTURES_DIR / "does-not-exist.md"
        result = parse_track_file(path)
        assert '_error' in result


class TestParseIdeasFile:
    """Tests for parse_ideas_file()."""

    def test_full_ideas_file(self):
        path = FIXTURES_DIR / "ideas.md"
        result = parse_ideas_file(path)

        assert '_error' not in result
        assert len(result['items']) == 4

        # Check counts
        counts = result['counts']
        assert counts.get('Pending', 0) == 2
        assert counts.get('In Progress', 0) == 1
        assert counts.get('Complete', 0) == 1

    def test_idea_fields(self):
        path = FIXTURES_DIR / "ideas.md"
        result = parse_ideas_file(path)

        items = result['items']
        crypto = items[0]
        assert crypto['title'] == 'Crypto Wars'
        assert crypto['genre'] == 'hip-hop'
        assert crypto['type'] == 'Documentary'
        assert crypto['status'] == 'Pending'

        silicon = items[1]
        assert silicon['title'] == 'Silicon Ghosts'
        assert silicon['genre'] == 'electronic'
        assert silicon['status'] == 'In Progress'

    def test_nonexistent_file(self):
        path = FIXTURES_DIR / "does-not-exist.md"
        result = parse_ideas_file(path)
        assert '_error' in result

    def test_empty_ideas_section(self):
        """Test IDEAS.md with no actual ideas (just template)."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Album Ideas\n\n## Ideas\n\n<!-- No ideas yet -->\n")
            f.flush()
            result = parse_ideas_file(Path(f.name))
            assert result['items'] == []
            assert result['counts'] == {}
        os.unlink(f.name)


class TestEdgeCases:
    """Test edge cases and malformed input."""

    def test_album_with_no_tracklist(self):
        """Album README with no tracklist section."""
        import tempfile
        content = """---
title: "Minimal Album"
explicit: false
---

# Minimal Album

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 5 |
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_album_readme(Path(f.name))
            assert result['status'] == 'Concept'
            assert result['track_count'] == 5
            assert result['tracklist'] == []
        os.unlink(f.name)

    def test_track_with_na_sources(self):
        """Track where sources verified is N/A."""
        import tempfile
        content = """# Simple Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Simple Track |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | N/A |
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_track_file(Path(f.name))
            assert result['sources_verified'] == 'N/A'
            assert result['status'] == 'In Progress'
            assert result['has_suno_link'] is False
        os.unlink(f.name)

    def test_track_with_suno_link(self):
        """Track with a real suno link (not em-dash)."""
        import tempfile
        content = """# Linked Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Linked Track |
| **Status** | Generated |
| **Suno Link** | [Listen](https://suno.com/song/abc) |
| **Explicit** | Yes |
| **Sources Verified** | N/A |
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_track_file(Path(f.name))
            assert result['has_suno_link'] is True
            assert result['status'] == 'Generated'
            assert result['explicit'] is True
        os.unlink(f.name)


class TestTracklistFlexibleColumns:
    """Tests for _parse_tracklist_table with different column counts."""

    def test_5_columns(self):
        """Standard 5-column format: # | Title | POV | Concept | Status."""
        text = """## Tracklist

| # | Title | POV | Concept | Status |
|---|-------|-----|---------|--------|
| 01 | [Boot Sequence](tracks/01.md) | Narrator | Computing | Final |
| 02 | [Fork](tracks/02.md) | Narrator | Open source | Not Started |
"""
        tracks = _parse_tracklist_table(text)
        assert len(tracks) == 2
        assert tracks[0]['number'] == '01'
        assert tracks[0]['title'] == 'Boot Sequence'
        assert tracks[0]['status'] == 'Final'
        assert tracks[1]['status'] == 'Not Started'

    def test_3_columns(self):
        """Minimal 3-column format: # | Title | Status."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 01 | Boot Sequence | Final |
| 02 | Fork the World | In Progress |
"""
        tracks = _parse_tracklist_table(text)
        assert len(tracks) == 2
        assert tracks[0]['title'] == 'Boot Sequence'
        assert tracks[0]['status'] == 'Final'
        assert tracks[1]['title'] == 'Fork the World'
        assert tracks[1]['status'] == 'In Progress'

    def test_6_columns(self):
        """Extended 6-column format with Duration."""
        text = """## Tracklist

| # | Title | POV | Concept | Duration | Status |
|---|-------|-----|---------|----------|--------|
| 01 | [Boot](tracks/01.md) | Narrator | Computing | 3:45 | Final |
| 02 | [Fork](tracks/02.md) | Narrator | Open source | 4:12 | Generated |
"""
        tracks = _parse_tracklist_table(text)
        assert len(tracks) == 2
        assert tracks[0]['status'] == 'Final'
        assert tracks[1]['status'] == 'Generated'

    def test_no_tracklist_section(self):
        """No Tracklist heading returns empty list."""
        text = """## Album Details

Some content but no tracklist.
"""
        tracks = _parse_tracklist_table(text)
        assert tracks == []

    def test_tracklist_section_no_rows(self):
        """Tracklist heading exists but no data rows emits warning."""
        import warnings
        text = """## Tracklist

No table here, just text.
"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            tracks = _parse_tracklist_table(text)
            assert tracks == []
            assert len(w) == 1
            assert "no track rows matched" in str(w[0].message).lower()

    def test_title_with_markdown_link(self):
        """Title column with markdown link extracts display text."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 03 | [Merge Conflict](tracks/03-merge-conflict.md) | In Progress |
"""
        tracks = _parse_tracklist_table(text)
        assert tracks[0]['title'] == 'Merge Conflict'

    def test_title_without_link(self):
        """Title column without markdown link uses raw text."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 01 | Boot Sequence | Not Started |
"""
        tracks = _parse_tracklist_table(text)
        assert tracks[0]['title'] == 'Boot Sequence'

    def test_stops_at_next_section(self):
        """Parser stops at the next ## heading."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 01 | Boot | Final |

## Production Notes

| 01 | Not a track | Ignore |
"""
        tracks = _parse_tracklist_table(text)
        assert len(tracks) == 1


class TestNormalizeStatus:
    """Tests for _normalize_status()."""

    def test_canonical_statuses(self):
        from tools.state.parsers import _normalize_status
        assert _normalize_status('In Progress') == 'In Progress'
        assert _normalize_status('Final') == 'Final'
        assert _normalize_status('Not Started') == 'Not Started'
        assert _normalize_status('Generated') == 'Generated'
        assert _normalize_status('Complete') == 'Complete'
        assert _normalize_status('Released') == 'Released'
        assert _normalize_status('Concept') == 'Concept'

    def test_case_insensitive(self):
        from tools.state.parsers import _normalize_status
        assert _normalize_status('in progress') == 'In Progress'
        assert _normalize_status('IN PROGRESS') == 'In Progress'
        assert _normalize_status('final') == 'Final'
        assert _normalize_status('FINAL') == 'Final'

    def test_trailing_content(self):
        from tools.state.parsers import _normalize_status
        assert _normalize_status('In Progress (started 2026-01-01)') == 'In Progress'
        assert _normalize_status('Complete - all tracks done') == 'Complete'

    def test_empty_returns_unknown(self):
        from tools.state.parsers import _normalize_status
        assert _normalize_status('') == 'Unknown'
        assert _normalize_status(None) == 'Unknown'

    def test_unrecognized_returns_as_is(self):
        from tools.state.parsers import _normalize_status
        assert _normalize_status('SomeCustomStatus') == 'SomeCustomStatus'


class TestExtractTableValue:
    """Tests for _extract_table_value()."""

    def test_standard_extraction(self):
        from tools.state.parsers import _extract_table_value
        text = "| **Status** | In Progress |"
        assert _extract_table_value(text, 'Status') == 'In Progress'

    def test_extra_whitespace(self):
        from tools.state.parsers import _extract_table_value
        text = "|  **Status**  |   In Progress   |"
        assert _extract_table_value(text, 'Status') == 'In Progress'

    def test_key_not_found(self):
        from tools.state.parsers import _extract_table_value
        text = "| **Title** | My Track |"
        assert _extract_table_value(text, 'Status') is None

    def test_multiline_text(self):
        from tools.state.parsers import _extract_table_value
        text = """| **Title** | My Track |
| **Status** | Final |
| **Explicit** | No |"""
        assert _extract_table_value(text, 'Status') == 'Final'
        assert _extract_table_value(text, 'Title') == 'My Track'
        assert _extract_table_value(text, 'Explicit') == 'No'

    def test_value_with_special_characters(self):
        from tools.state.parsers import _extract_table_value
        text = '| **Suno Link** | [Listen](https://suno.com/song/abc) |'
        result = _extract_table_value(text, 'Suno Link')
        assert 'Listen' in result
        assert 'https://suno.com' in result


class TestExtractBoldField:
    """Tests for _extract_bold_field()."""

    def test_standard_extraction(self):
        from tools.state.parsers import _extract_bold_field
        text = "**Genre**: hip-hop"
        assert _extract_bold_field(text, 'Genre') == 'hip-hop'

    def test_case_insensitive(self):
        from tools.state.parsers import _extract_bold_field
        text = "**genre**: rock"
        assert _extract_bold_field(text, 'Genre') == 'rock'

    def test_field_not_found(self):
        from tools.state.parsers import _extract_bold_field
        text = "**Type**: Documentary"
        assert _extract_bold_field(text, 'Genre') is None

    def test_field_with_extra_spacing(self):
        from tools.state.parsers import _extract_bold_field
        text = "**Status**:   In Progress  "
        assert _extract_bold_field(text, 'Status') == 'In Progress'


class TestSourcesVerifiedParsing:
    """Tests for sources_verified field parsing edge cases."""

    def test_verified_with_date(self):
        import tempfile
        content = """# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Final |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | ✅ Verified (2026-01-15) |
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_track_file(Path(f.name))
            assert result['sources_verified'] == 'Verified'
        os.unlink(f.name)

    def test_pending_with_emoji(self):
        import tempfile
        content = """# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Not Started |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | ❌ Pending |
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_track_file(Path(f.name))
            assert result['sources_verified'] == 'Pending'
        os.unlink(f.name)

    def test_pending_verification_text(self):
        import tempfile
        content = """# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Not Started |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | Pending verification |
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_track_file(Path(f.name))
            assert result['sources_verified'] == 'Pending'
        os.unlink(f.name)

    def test_missing_sources_verified(self):
        import tempfile
        content = """# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_track_file(Path(f.name))
            assert result['sources_verified'] == 'N/A'
        os.unlink(f.name)


class TestFrontmatterEdgeCases:
    """Additional edge cases for frontmatter parsing."""

    def test_frontmatter_with_list(self):
        text = '---\ngenres:\n  - rock\n  - blues\n---\n'
        result = parse_frontmatter(text)
        assert result['genres'] == ['rock', 'blues']

    def test_frontmatter_with_nested_dict(self):
        text = '---\npaths:\n  content_root: /tmp\n  audio_root: /audio\n---\n'
        result = parse_frontmatter(text)
        assert result['paths']['content_root'] == '/tmp'

    def test_frontmatter_with_special_yaml_chars(self):
        text = '---\ntitle: "Album: The Sequel"\n---\n'
        result = parse_frontmatter(text)
        assert result['title'] == 'Album: The Sequel'

    def test_frontmatter_with_null_value(self):
        text = '---\nrelease_date: null\n---\n'
        result = parse_frontmatter(text)
        assert result['release_date'] is None

    def test_frontmatter_with_multiline_string(self):
        text = '---\ntitle: |\n  Multi\n  Line\n---\n'
        result = parse_frontmatter(text)
        assert 'Multi' in result['title']

    def test_frontmatter_yaml_error(self):
        """Invalid YAML in frontmatter returns _error key."""
        text = '---\n{{invalid: yaml: ::\n---\n'
        result = parse_frontmatter(text)
        assert '_error' in result
        assert 'Invalid YAML' in result['_error']

    def test_frontmatter_yaml_none(self):
        """When yaml module is None, returns _error."""
        import tools.state.parsers as parsers_mod
        original_yaml = parsers_mod.yaml
        try:
            parsers_mod.yaml = None
            text = '---\ntitle: Test\n---\n'
            result = parse_frontmatter(text)
            assert '_error' in result
            assert 'PyYAML' in result['_error']
        finally:
            parsers_mod.yaml = original_yaml


class TestAlbumReadmeEdgeCases:
    """Additional edge case tests for parse_album_readme."""

    def test_frontmatter_error_sets_warning(self, tmp_path):
        """Frontmatter parse error sets _warning on result."""
        readme = tmp_path / "README.md"
        readme.write_text('---\n{{bad yaml::\n---\n\n# Test Album\n\n## Album Details\n\n| Attribute | Detail |\n|-----------|--------|\n| **Status** | Concept |\n| **Tracks** | 5 |\n')
        result = parse_album_readme(readme)
        assert '_warning' in result
        assert result['status'] == 'Concept'

    def test_genre_from_path_no_albums_dir(self, tmp_path):
        """Genre extraction returns empty when path has no 'albums' dir."""
        result = _extract_genre_from_path(tmp_path / "some" / "other" / "README.md")
        assert result == ''

    def test_genre_from_path_with_albums_dir(self, tmp_path):
        """Genre extraction returns genre when path has 'albums' dir."""
        result = _extract_genre_from_path(tmp_path / "artists" / "test" / "albums" / "rock" / "my-album" / "README.md")
        assert result == 'rock'

    def test_track_count_no_digits(self):
        """Track count returns 0 for non-numeric string."""
        assert _parse_track_count('TBD') == 0
        assert _parse_track_count('[Number]') == 0

    def test_track_count_none(self):
        """Track count returns 0 for None input."""
        assert _parse_track_count(None) == 0
        assert _parse_track_count('') == 0

    def test_tracklist_row_too_few_columns(self):
        """Tracklist rows with fewer than 3 columns are skipped."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 1 | Good Track | Final |
| bad row |
| 2 | Another | In Progress |
"""
        result = _parse_tracklist_table(text)
        assert len(result) == 2
        assert result[0]['title'] == 'Good Track'
        assert result[1]['title'] == 'Another'


class TestTrackFileEdgeCases:
    """Additional edge case tests for parse_track_file."""

    def test_sources_verified_raw_passthrough(self, tmp_path):
        """Unknown sources_verified value passes through as-is."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Sources Verified** | Custom Value |
""")
        result = parse_track_file(track)
        assert result['sources_verified'] == 'Custom Value'


class TestIdeasEdgeCases:
    """Additional edge case tests for parse_ideas_file."""

    def test_idea_with_template_placeholder(self, tmp_path):
        """Template placeholders (starting with '[') are skipped."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""## Ideas

### [Placeholder Title]

**Genre**: Rock
**Status**: Pending

### Real Idea

**Genre**: Electronic
**Status**: Planning
""")
        result = parse_ideas_file(ideas)
        assert len(result['items']) == 1
        assert result['items'][0]['title'] == 'Real Idea'

    def test_idea_with_no_status_defaults_pending(self, tmp_path):
        """Ideas without a status field default to Pending."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""## Ideas

### No Status Idea

**Genre**: Folk
**Type**: Concept
""")
        result = parse_ideas_file(ideas)
        assert result['items'][0]['status'] == 'Pending'

    def test_idea_status_with_pipe_separator(self, tmp_path):
        """Status with pipe separator takes first value."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""## Ideas

### Piped Idea

**Genre**: Rock
**Status**: Planning | Research | Writing
""")
        result = parse_ideas_file(ideas)
        assert result['items'][0]['status'] == 'Planning'

    def test_empty_idea_blocks_skipped(self, tmp_path):
        """Empty idea blocks (no title) are skipped."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""## Ideas

###

### Valid Idea

**Genre**: Pop
**Status**: Planning
""")
        result = parse_ideas_file(ideas)
        assert len(result['items']) == 1
        assert result['items'][0]['title'] == 'Valid Idea'
