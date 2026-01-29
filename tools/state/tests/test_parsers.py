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
