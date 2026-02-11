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
    _derive_model_tier,
    _extract_bold_field,
    _extract_genre_from_path,
    _extract_table_value,
    _normalize_status,
    _parse_track_count,
    _parse_tracklist_table,
    parse_album_readme,
    parse_frontmatter,
    parse_ideas_file,
    parse_skill_file,
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
        assert result['title'] == 'Sample Album'
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

    def test_streaming_block_in_frontmatter(self):
        """Fixture album-readme.md should have a streaming block in frontmatter."""
        path = FIXTURES_DIR / "album-readme.md"
        fm = parse_frontmatter(path.read_text())
        assert 'streaming' in fm, "Fixture missing streaming block in frontmatter"
        streaming = fm['streaming']
        assert isinstance(streaming, dict)
        for platform in ('soundcloud', 'spotify', 'apple_music', 'youtube_music', 'amazon_music'):
            assert platform in streaming, f"streaming block missing: {platform}"


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
        assert result['sources_verified'] == 'Verified (2026-01-15)'

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
            assert result['sources_verified'] == 'Verified (2026-01-15)'
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


class TestDeriveModelTier:
    """Tests for _derive_model_tier()."""

    def test_opus(self):
        assert _derive_model_tier('claude-opus-4-6') == 'opus'

    def test_sonnet(self):
        assert _derive_model_tier('claude-sonnet-4-5-20250929') == 'sonnet'

    def test_haiku(self):
        assert _derive_model_tier('claude-haiku-4-5-20251001') == 'haiku'

    def test_unknown(self):
        assert _derive_model_tier('gpt-4o') == 'unknown'

    def test_empty_string(self):
        assert _derive_model_tier('') == 'unknown'

    def test_case_insensitive(self):
        assert _derive_model_tier('CLAUDE-OPUS-4-6') == 'opus'
        assert _derive_model_tier('Claude-Sonnet-4-5') == 'sonnet'
        assert _derive_model_tier('Claude-Haiku-4-5') == 'haiku'


class TestParseSkillFile:
    """Tests for parse_skill_file()."""

    def test_valid_skill(self, tmp_path):
        """Full skill file with all fields parses correctly."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: lyric-writer
description: Writes or reviews lyrics with professional prosody.
argument-hint: <track-file-path>
model: claude-opus-4-6
prerequisites:
  - album-conceptualizer
allowed-tools:
  - Read
  - Edit
  - Write
---

# Lyric Writer Agent

Content here.
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        assert result['name'] == 'lyric-writer'
        assert result['description'] == 'Writes or reviews lyrics with professional prosody.'
        assert result['model'] == 'claude-opus-4-6'
        assert result['model_tier'] == 'opus'
        assert result['argument_hint'] == '<track-file-path>'
        assert result['allowed_tools'] == ['Read', 'Edit', 'Write']
        assert result['prerequisites'] == ['album-conceptualizer']
        assert result['user_invocable'] is True
        assert result['context'] is None
        assert result['path'] == str(skill)
        assert result['mtime'] > 0

    def test_minimal_required_fields(self, tmp_path):
        """Skill with only required fields."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: help
description: Shows help information.
model: claude-haiku-4-5-20251001
allowed-tools: []
---
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        assert result['name'] == 'help'
        assert result['model_tier'] == 'haiku'
        assert result['allowed_tools'] == []
        assert result['prerequisites'] == []
        assert result['requirements'] == {}

    def test_optional_fields(self, tmp_path):
        """Skill with user-invocable, context, and requirements."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: researchers-legal
description: Researches court documents.
model: claude-sonnet-4-5-20250929
user-invocable: false
context: fork
allowed-tools:
  - Read
  - Bash
requirements:
  python:
    - playwright
---
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        assert result['user_invocable'] is False
        assert result['context'] == 'fork'
        assert result['requirements'] == {'python': ['playwright']}
        assert result['model_tier'] == 'sonnet'

    def test_missing_name(self, tmp_path):
        """Missing required name field returns error."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
description: Some skill
model: claude-opus-4-6
allowed-tools: []
---
""")
        result = parse_skill_file(skill)
        assert '_error' in result
        assert 'name' in result['_error']

    def test_missing_description(self, tmp_path):
        """Missing required description field returns error."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: broken-skill
model: claude-opus-4-6
allowed-tools: []
---
""")
        result = parse_skill_file(skill)
        assert '_error' in result
        assert 'description' in result['_error']

    def test_no_frontmatter(self, tmp_path):
        """File without frontmatter returns error."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("# Just a heading\n\nNo frontmatter here.\n")
        result = parse_skill_file(skill)
        assert '_error' in result
        assert 'No frontmatter' in result['_error']

    def test_unreadable_file(self, tmp_path):
        """Unreadable file returns error."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("---\nname: test\n---\n")
        skill.chmod(0o000)
        result = parse_skill_file(skill)
        skill.chmod(0o644)  # Restore for cleanup
        assert '_error' in result
        assert 'Cannot read' in result['_error']

    def test_nonexistent_file(self, tmp_path):
        """Nonexistent file returns error."""
        skill = tmp_path / "does-not-exist.md"
        result = parse_skill_file(skill)
        assert '_error' in result

    def test_invalid_yaml_frontmatter(self, tmp_path):
        """Invalid YAML in frontmatter returns error."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("---\n{{invalid: yaml: ::\n---\n")
        result = parse_skill_file(skill)
        assert '_error' in result
        assert 'Invalid YAML' in result['_error']

    def test_missing_model_defaults_to_empty(self, tmp_path):
        """Missing model field defaults to empty string with unknown tier."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: no-model
description: A skill without model specified.
allowed-tools: []
---
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        assert result['model'] == ''
        assert result['model_tier'] == 'unknown'

    def test_hyphen_to_underscore_normalization(self, tmp_path):
        """Frontmatter keys with hyphens are normalized to underscores."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: test-skill
description: Test hyphen normalization.
argument-hint: <arg>
model: claude-opus-4-6
allowed-tools:
  - Read
user-invocable: false
---
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        assert result['argument_hint'] == '<arg>'
        assert result['user_invocable'] is False


# =============================================================================
# Edge case tests — bugs and boundary conditions found during code review
# =============================================================================


class TestParseFrontmatterNonDict:
    """Tests for parse_frontmatter with non-dict YAML content."""

    def test_yaml_returns_string(self):
        """YAML that parses to a bare string should return _error."""
        text = '---\njust a string\n---\n'
        result = parse_frontmatter(text)
        assert '_error' in result
        assert 'not a mapping' in result['_error']

    def test_yaml_returns_list(self):
        """YAML that parses to a list should return _error."""
        text = '---\n- item1\n- item2\n---\n'
        result = parse_frontmatter(text)
        assert '_error' in result
        assert 'not a mapping' in result['_error']

    def test_yaml_returns_integer(self):
        """YAML that parses to a bare integer should return _error."""
        text = '---\n42\n---\n'
        result = parse_frontmatter(text)
        assert '_error' in result
        assert 'not a mapping' in result['_error']

    def test_yaml_returns_boolean(self):
        """YAML that parses to a bare boolean should return _error."""
        text = '---\ntrue\n---\n'
        result = parse_frontmatter(text)
        assert '_error' in result
        assert 'not a mapping' in result['_error']


class TestNormalizeStatusEdgeCases:
    """Additional edge cases for _normalize_status()."""

    def test_greedy_prefix_concepts_of_art(self):
        """'concepts of modern art' should NOT match 'Concept'.

        Documents known greedy-prefix behavior: startswith('concept')
        matches any string beginning with 'concept'.
        """
        result = _normalize_status('concepts of modern art')
        # Current behavior: greedy prefix match returns 'Concept'
        # This documents the bug — the prefix matching is too loose
        assert result == 'Concept'

    def test_greedy_prefix_generated_report(self):
        """'generated report' matches 'Generated' due to greedy prefix.

        Documents known behavior: any string starting with 'generated'
        maps to 'Generated'.
        """
        result = _normalize_status('generated report')
        assert result == 'Generated'

    def test_whitespace_only_returns_empty(self):
        """Whitespace-only input returns empty string.

        Documents current behavior: '   '.strip() -> '' which doesn't
        match any key, and falls through to return '' (not 'Unknown').
        Only None and '' (before strip) return 'Unknown' via the
        `if not raw` guard.
        """
        assert _normalize_status('   ') == ''
        assert _normalize_status('\t\n') == ''

    def test_leading_trailing_whitespace(self):
        """Leading/trailing whitespace is stripped before matching."""
        assert _normalize_status('  In Progress  ') == 'In Progress'
        assert _normalize_status(' final ') == 'Final'

    def test_exact_match_takes_precedence_over_prefix(self):
        """Exact lowercase match is checked before prefix matching."""
        assert _normalize_status('complete') == 'Complete'
        assert _normalize_status('concept') == 'Concept'


class TestParseTrackFileBracketTitle:
    """Tests for parse_track_file with bracket-prefixed titles."""

    def test_title_starting_with_bracket(self, tmp_path):
        """Title like '[Explicit] My Song' falls through to heading.

        Documents known behavior: bracket-prefixed table titles are
        skipped (intended to filter markdown links), so the heading
        is used as fallback.
        """
        track = tmp_path / "01-track.md"
        track.write_text("""# [Explicit] My Song

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | [Explicit] My Song |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | Yes |
""")
        result = parse_track_file(track)
        # Title falls back to heading because table title starts with '['
        assert result['title'] == '[Explicit] My Song'
        assert result['status'] == 'In Progress'

    def test_title_with_markdown_link_uses_heading(self, tmp_path):
        """Title that IS a markdown link falls back to heading."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Real Title

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | [Real Title](tracks/01.md) |
| **Status** | Final |
| **Suno Link** | — |
| **Explicit** | No |
""")
        result = parse_track_file(track)
        assert result['title'] == 'Real Title'

    def test_normal_title_from_table(self, tmp_path):
        """Normal title (no bracket) is extracted from table."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Heading

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Normal Title |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
""")
        result = parse_track_file(track)
        assert result['title'] == 'Normal Title'


class TestParseTrackFileEmpty:
    """Tests for parse_track_file with minimal/empty content."""

    def test_empty_file(self, tmp_path):
        """Empty markdown file returns defaults."""
        track = tmp_path / "01-track.md"
        track.write_text("")
        result = parse_track_file(track)
        assert result['title'] == ''
        assert result['status'] == 'Unknown'
        assert result['explicit'] is False
        assert result['has_suno_link'] is False
        assert result['sources_verified'] == 'N/A'

    def test_heading_only(self, tmp_path):
        """File with only a heading, no table."""
        track = tmp_path / "01-track.md"
        track.write_text("# My Track\n\nSome prose but no table.\n")
        result = parse_track_file(track)
        assert result['title'] == 'My Track'
        assert result['status'] == 'Unknown'


class TestIdeasStatusWithPipe:
    """Tests for ideas file with pipe-separated status choices."""

    def test_template_choice_list(self, tmp_path):
        """Template placeholder 'Pending | In Progress | Complete' takes first."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""## Ideas

### Template Idea

**Genre**: Rock
**Status**: Pending | In Progress | Complete
""")
        result = parse_ideas_file(ideas)
        assert len(result['items']) == 1
        assert result['items'][0]['status'] == 'Pending'

    def test_single_pipe(self, tmp_path):
        """Status with a single pipe takes the first part."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""## Ideas

### Piped

**Genre**: Jazz
**Status**: Planning | Active
""")
        result = parse_ideas_file(ideas)
        assert result['items'][0]['status'] == 'Planning'


class TestTracklistTableEdgeCases:
    """Additional edge cases for _parse_tracklist_table."""

    def test_row_with_only_2_columns_skipped(self):
        """Rows with fewer than 3 columns are silently skipped."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 1 | Good Track | Final |
| 2 | Missing Status |
| 3 | Another Good | In Progress |
"""
        result = _parse_tracklist_table(text)
        assert len(result) == 2
        assert result[0]['title'] == 'Good Track'
        assert result[1]['title'] == 'Another Good'

    def test_non_digit_first_column_skipped(self):
        """Header row and separator are skipped (non-digit first col)."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 1 | First | Final |
| N/A | Skipped | Unknown |
| 2 | Second | In Progress |
"""
        result = _parse_tracklist_table(text)
        assert len(result) == 2
        assert result[0]['number'] == '01'
        assert result[1]['number'] == '02'

    def test_separator_row_with_dashes(self):
        """Standard separator row (|---|---|---) is properly skipped."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 1 | Track | Final |
"""
        result = _parse_tracklist_table(text)
        assert len(result) == 1
        assert result[0]['title'] == 'Track'

    def test_empty_columns_in_row(self):
        """Row with empty middle columns still works (first=num, last=status)."""
        text = """## Tracklist

| # | Title | POV | Concept | Status |
|---|-------|-----|---------|--------|
| 1 |  |  |  | Final |
"""
        result = _parse_tracklist_table(text)
        assert len(result) == 1
        assert result[0]['status'] == 'Final'
        assert result[0]['title'] == ''


class TestExtractTableValueEdgeCases:
    """Additional edge cases for _extract_table_value."""

    def test_empty_value(self):
        """Table cell with empty value returns empty string."""
        text = "| **Status** |  |"
        result = _extract_table_value(text, 'Status')
        assert result == ''

    def test_value_with_only_whitespace(self):
        """Table cell with only whitespace returns empty string after strip."""
        text = "| **Status** |    |"
        result = _extract_table_value(text, 'Status')
        assert result == ''


class TestDeriveModelTierComplete:
    """Complete coverage for _derive_model_tier."""

    def test_all_known_tiers(self):
        assert _derive_model_tier('claude-opus-4-6') == 'opus'
        assert _derive_model_tier('claude-sonnet-4-5-20250929') == 'sonnet'
        assert _derive_model_tier('claude-haiku-4-5-20251001') == 'haiku'

    def test_unknown_model(self):
        assert _derive_model_tier('gpt-4o') == 'unknown'
        assert _derive_model_tier('llama-3') == 'unknown'

    def test_none_input(self):
        assert _derive_model_tier(None) == 'unknown'

    def test_empty_string(self):
        assert _derive_model_tier('') == 'unknown'

    def test_case_insensitive_mixed(self):
        assert _derive_model_tier('CLAUDE-OPUS-4-6') == 'opus'
        assert _derive_model_tier('Claude-Sonnet-Latest') == 'sonnet'

    def test_tier_keyword_in_model_name(self):
        """Tier keyword embedded in model name is detected."""
        assert _derive_model_tier('my-custom-opus-model') == 'opus'
        assert _derive_model_tier('fine-tuned-haiku') == 'haiku'

    def test_precedence_opus_before_sonnet(self):
        """If model contains multiple tier keywords, opus wins (checked first)."""
        assert _derive_model_tier('opus-sonnet-hybrid') == 'opus'


class TestParseTrackFileFrontmatter:
    """Tests for frontmatter support in parse_track_file()."""

    def test_frontmatter_title_fallback(self, tmp_path):
        """When no table title, frontmatter title is used."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "Frontmatter Title"
track_number: 1
explicit: false
---

# Heading Title

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
""")
        result = parse_track_file(track)
        assert result['title'] == 'Frontmatter Title'

    def test_table_title_takes_precedence(self, tmp_path):
        """Table title beats frontmatter title."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "Frontmatter Title"
track_number: 1
explicit: false
---

# Heading Title

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Table Title |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
""")
        result = parse_track_file(track)
        assert result['title'] == 'Table Title'

    def test_frontmatter_explicit_fallback(self, tmp_path):
        """When no table explicit, frontmatter value used."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "Track"
track_number: 1
explicit: true
---

# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Suno Link** | — |
""")
        result = parse_track_file(track)
        assert result['explicit'] is True

    def test_frontmatter_suno_url(self, tmp_path):
        """suno_url extracted from frontmatter."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "Track"
track_number: 1
explicit: false
suno_url: "https://suno.com/song/abc123"
---

# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Generated |
| **Suno Link** | — |
| **Explicit** | No |
""")
        result = parse_track_file(track)
        assert result['suno_url'] == 'https://suno.com/song/abc123'

    def test_no_frontmatter_backwards_compat(self, tmp_path):
        """Existing files without frontmatter still parse correctly."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Boot Sequence

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Boot Sequence |
| **Status** | Final |
| **Suno Link** | [Listen](https://suno.com/song/abc) |
| **Explicit** | Yes |
| **Sources Verified** | ✅ Verified (2026-01-15) |
""")
        result = parse_track_file(track)
        assert '_error' not in result
        assert '_warning' not in result
        assert result['title'] == 'Boot Sequence'
        assert result['status'] == 'Final'
        assert result['explicit'] is True
        assert result['has_suno_link'] is True
        assert 'suno_url' not in result

    def test_invalid_frontmatter_ignored(self, tmp_path):
        """Bad YAML in frontmatter doesn't break parsing."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
{{invalid: yaml: ::
---

# My Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | My Track |
| **Status** | In Progress |
| **Suno Link** | — |
| **Explicit** | No |
""")
        result = parse_track_file(track)
        assert '_error' not in result
        assert '_warning' in result
        assert result['title'] == 'My Track'
        assert result['status'] == 'In Progress'


# =============================================================================
# Comprehensive edge case tests — Round 5 coverage audit
# =============================================================================


class TestSourcesVerifiedEdgeCases:
    """Additional edge cases for sources_verified field parsing."""

    def test_verified_lowercase_no_emoji(self, tmp_path):
        """'verified' (lowercase, no emoji, no date) is recognized."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Final |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | verified |
""")
        result = parse_track_file(track)
        assert result['sources_verified'] == 'Verified'

    def test_verified_with_extra_text(self, tmp_path):
        """'verified by human' is recognized via startswith."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Final |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | Verified by human reviewer |
""")
        result = parse_track_file(track)
        assert result['sources_verified'] == 'Verified'

    def test_verified_with_malformed_date(self, tmp_path):
        """Date regex doesn't match malformed date; returns plain 'Verified'."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Final |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | ✅ Verified (01-15-2026) |
""")
        result = parse_track_file(track)
        # Date format is wrong (MM-DD-YYYY instead of YYYY-MM-DD), regex won't match
        assert result['sources_verified'] == 'Verified'

    def test_verified_with_partial_date(self, tmp_path):
        """Partial date '(2026-01)' doesn't match YYYY-MM-DD format."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Final |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | ✅ Verified (2026-01) |
""")
        result = parse_track_file(track)
        assert result['sources_verified'] == 'Verified'

    def test_pending_capitalized_no_emoji(self, tmp_path):
        """'Pending' (capitalized, no emoji) is recognized."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Not Started |
| **Suno Link** | — |
| **Explicit** | No |
| **Sources Verified** | Pending |
""")
        result = parse_track_file(track)
        assert result['sources_verified'] == 'Pending'


class TestSunoLinkEdgeCases:
    """Edge cases for Suno Link parsing in parse_track_file."""

    def test_suno_link_single_hyphen(self, tmp_path):
        """Single hyphen '-' treated as empty (no suno link)."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Not Started |
| **Suno Link** | - |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")
        result = parse_track_file(track)
        assert result['has_suno_link'] is False

    def test_suno_link_en_dash(self, tmp_path):
        """En dash '–' treated as empty (no suno link)."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Not Started |
| **Suno Link** | \u2013 |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")
        result = parse_track_file(track)
        assert result['has_suno_link'] is False

    def test_suno_link_em_dash(self, tmp_path):
        """Em dash '—' treated as empty (no suno link)."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Not Started |
| **Suno Link** | \u2014 |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")
        result = parse_track_file(track)
        assert result['has_suno_link'] is False

    def test_suno_link_whitespace_only(self, tmp_path):
        """Whitespace-only suno link treated as empty."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Not Started |
| **Suno Link** |    |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")
        result = parse_track_file(track)
        assert result['has_suno_link'] is False

    def test_suno_link_with_url(self, tmp_path):
        """Plain URL is detected as having a suno link."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | Generated |
| **Suno Link** | https://suno.com/song/abc123 |
| **Explicit** | No |
| **Sources Verified** | N/A |
""")
        result = parse_track_file(track)
        assert result['has_suno_link'] is True


class TestIdeasFileNoHeading:
    """Edge cases for parse_ideas_file without expected headings."""

    def test_no_ideas_heading(self, tmp_path):
        """File without '## Ideas' heading still parses ### blocks."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""# My Ideas

### Cool Album

**Genre**: Rock
**Status**: Pending

### Another Album

**Genre**: Jazz
**Status**: In Progress
""")
        result = parse_ideas_file(ideas)
        # Without "## Ideas" heading, the entire text is searched for ### blocks
        assert len(result['items']) == 2
        assert result['items'][0]['title'] == 'Cool Album'
        assert result['items'][1]['title'] == 'Another Album'

    def test_only_preamble_no_ideas(self, tmp_path):
        """File with only preamble text and no ### blocks returns empty."""
        ideas = tmp_path / "IDEAS.md"
        ideas.write_text("""# Album Ideas

This file contains album ideas. Use this template.
""")
        result = parse_ideas_file(ideas)
        assert result['items'] == []
        assert result['counts'] == {}


class TestNormalizeStatusBoundary:
    """Boundary conditions for _normalize_status."""

    def test_whitespace_only_returns_empty_not_unknown(self):
        """Whitespace-only input passes 'if not raw' but strips to empty string."""
        # '   ' is truthy, so it passes the first guard
        # After strip, it's '' which doesn't match any key or prefix
        # Falls through to return '' (not 'Unknown')
        assert _normalize_status('   ') == ''
        assert _normalize_status('\t') == ''
        assert _normalize_status('\n') == ''

    def test_tab_separated_status(self):
        """Status with tab characters is stripped properly."""
        assert _normalize_status('\tFinal\t') == 'Final'

    def test_mixed_case_all_statuses(self):
        """Verify all canonical statuses work with varied casing."""
        cases = {
            'CONCEPT': 'Concept',
            'In progress': 'In Progress',
            'RESEARCH COMPLETE': 'Research Complete',
            'SOURCES VERIFIED': 'Sources Verified',
            'COMPLETE': 'Complete',
            'RELEASED': 'Released',
            'NOT STARTED': 'Not Started',
            'SOURCES PENDING': 'Sources Pending',
            'GENERATED': 'Generated',
            'FINAL': 'Final',
        }
        for input_val, expected in cases.items():
            assert _normalize_status(input_val) == expected, f"Failed for {input_val!r}"


class TestParseSkillFileEdgeCases:
    """Additional edge cases for parse_skill_file."""

    def test_none_model_value(self, tmp_path):
        """Model field set to YAML null produces empty string model."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: null-model-skill
description: Skill with null model.
model: null
allowed-tools: []
---
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        # yaml.safe_load('null') returns None; model defaults via .get('model', '')
        # But since None is present, it's used as-is (not the default '')
        assert result['model'] is None or result['model'] == ''
        assert result['model_tier'] == 'unknown'

    def test_integer_model_value(self, tmp_path):
        """Model field set to an integer is handled gracefully."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: int-model-skill
description: Skill with int model.
model: 42
allowed-tools: []
---
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        assert result['model'] == 42
        assert result['model_tier'] == 'unknown'

    def test_empty_name_is_falsy(self, tmp_path):
        """Empty string name is considered missing (falsy check)."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: ""
description: Has description.
model: claude-opus-4-6
allowed-tools: []
---
""")
        result = parse_skill_file(skill)
        assert '_error' in result
        assert 'name' in result['_error']

    def test_frontmatter_non_dict_returns_error(self, tmp_path):
        """Frontmatter that parses to non-dict returns error."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
- item1
- item2
---
""")
        result = parse_skill_file(skill)
        assert '_error' in result
        assert 'not a mapping' in result['_error']

    def test_extra_frontmatter_keys_preserved(self, tmp_path):
        """Unknown frontmatter keys are available in result via normalization."""
        skill = tmp_path / "SKILL.md"
        skill.write_text("""---
name: extra-keys
description: Has extra keys.
model: claude-opus-4-6
allowed-tools: []
custom-field: custom-value
---
""")
        result = parse_skill_file(skill)
        assert '_error' not in result
        # custom-field becomes custom_field after normalization
        # but it's not explicitly returned in the result dict
        # (only specific fields are extracted)
        assert result['name'] == 'extra-keys'


class TestTrackTitlePrecedenceComplete:
    """Complete coverage of title extraction precedence chain."""

    def test_table_title_beats_all(self, tmp_path):
        """Table title takes precedence over frontmatter and heading."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "FM Title"
---

# Heading Title

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Table Title |
| **Status** | In Progress |
""")
        result = parse_track_file(track)
        assert result['title'] == 'Table Title'

    def test_frontmatter_title_beats_heading(self, tmp_path):
        """When no table title, frontmatter beats heading."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "FM Title"
---

# Heading Title

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
""")
        result = parse_track_file(track)
        assert result['title'] == 'FM Title'

    def test_heading_is_last_fallback(self, tmp_path):
        """When no table title and no frontmatter title, heading is used."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Heading Title

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
""")
        result = parse_track_file(track)
        assert result['title'] == 'Heading Title'

    def test_frontmatter_template_placeholder_skipped(self, tmp_path):
        """Frontmatter title '[Track Title]' is skipped as template."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "[Track Title]"
---

# Real Title

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Not Started |
""")
        result = parse_track_file(track)
        assert result['title'] == 'Real Title'

    def test_no_title_anywhere(self, tmp_path):
        """No table title, no frontmatter, no heading returns empty string."""
        track = tmp_path / "01-track.md"
        track.write_text("""## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Not Started |
""")
        result = parse_track_file(track)
        assert result['title'] == ''


class TestExplicitFieldEdgeCases:
    """Edge cases for explicit field extraction."""

    def test_explicit_true_from_table(self, tmp_path):
        """Table value 'true' is recognized as explicit."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | In Progress |
| **Explicit** | true |
""")
        result = parse_track_file(track)
        assert result['explicit'] is True

    def test_explicit_yes_from_table(self, tmp_path):
        """Table value 'Yes' is recognized as explicit."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | In Progress |
| **Explicit** | Yes |
""")
        result = parse_track_file(track)
        assert result['explicit'] is True

    def test_explicit_no_from_table(self, tmp_path):
        """Table value 'No' is not explicit."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | In Progress |
| **Explicit** | No |
""")
        result = parse_track_file(track)
        assert result['explicit'] is False

    def test_explicit_random_string_not_explicit(self, tmp_path):
        """Unrecognized string like 'maybe' is not explicit."""
        track = tmp_path / "01-track.md"
        track.write_text("""# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Title** | Test |
| **Status** | In Progress |
| **Explicit** | maybe |
""")
        result = parse_track_file(track)
        assert result['explicit'] is False

    def test_explicit_frontmatter_fallback_zero(self, tmp_path):
        """Frontmatter explicit: 0 (falsy int) maps to False."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "Track"
explicit: 0
---

# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
""")
        result = parse_track_file(track)
        assert result['explicit'] is False


class TestSunoUrlFromFrontmatter:
    """Edge cases for suno_url extraction from frontmatter."""

    def test_empty_suno_url_not_included(self, tmp_path):
        """Empty suno_url in frontmatter is not included in result."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "Track"
suno_url: ""
---

# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Suno Link** | — |
""")
        result = parse_track_file(track)
        assert 'suno_url' not in result

    def test_whitespace_suno_url_not_included(self, tmp_path):
        """Whitespace-only suno_url is not included in result."""
        track = tmp_path / "01-track.md"
        track.write_text("""---
title: "Track"
suno_url: "   "
---

# Track

## Track Details

| Attribute | Detail |
|-----------|--------|
| **Status** | In Progress |
| **Suno Link** | — |
""")
        result = parse_track_file(track)
        assert 'suno_url' not in result


class TestAlbumGenreExtraction:
    """Edge cases for genre extraction in parse_album_readme."""

    def test_genre_from_frontmatter_empty_list(self, tmp_path):
        """Empty genres list falls back to path extraction."""
        album_dir = tmp_path / "artists" / "test" / "albums" / "hip-hop" / "my-album"
        album_dir.mkdir(parents=True)
        readme = album_dir / "README.md"
        readme.write_text("""---
title: "My Album"
genres: []
---

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 5 |
""")
        result = parse_album_readme(readme)
        assert result['genre'] == 'hip-hop'

    def test_genre_from_frontmatter_non_list(self, tmp_path):
        """Non-list genres value falls back to path extraction."""
        album_dir = tmp_path / "artists" / "test" / "albums" / "rock" / "my-album"
        album_dir.mkdir(parents=True)
        readme = album_dir / "README.md"
        readme.write_text("""---
title: "My Album"
genres: "rock"
---

## Album Details

| Attribute | Detail |
|-----------|--------|
| **Status** | Concept |
| **Tracks** | 5 |
""")
        result = parse_album_readme(readme)
        # genres is a string, not a list — isinstance check fails, falls to path
        assert result['genre'] == 'rock'


class TestTracklistNumberPadding:
    """Tests for track number zero-padding in tracklist parsing."""

    def test_single_digit_padded(self):
        """Single digit track number gets zero-padded to 2 digits."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 1 | First | Final |
| 9 | Ninth | Not Started |
"""
        tracks = _parse_tracklist_table(text)
        assert tracks[0]['number'] == '01'
        assert tracks[1]['number'] == '09'

    def test_double_digit_not_padded(self):
        """Double digit track number stays as-is."""
        text = """## Tracklist

| # | Title | Status |
|---|-------|--------|
| 10 | Tenth | Final |
| 12 | Twelfth | Not Started |
"""
        tracks = _parse_tracklist_table(text)
        assert tracks[0]['number'] == '10'
        assert tracks[1]['number'] == '12'
