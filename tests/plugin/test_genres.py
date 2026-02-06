"""Tests for genre directory structure vs INDEX.md and genre-list.md."""

import re

import pytest

pytestmark = pytest.mark.plugin


def _get_actual_genres(genres_dir):
    """Get genre directories that have a README.md."""
    if not genres_dir.exists():
        return set()
    return {
        entry.name for entry in sorted(genres_dir.iterdir())
        if entry.is_dir() and not entry.name.startswith('.') and (entry / "README.md").exists()
    }


class TestGenresDir:
    """Genre directory structure must be valid."""

    def test_genres_dir_exists(self, genres_dir):
        assert genres_dir.exists(), "genres/ directory missing"

    def test_genre_dirs_found(self, genres_dir):
        genres = _get_actual_genres(genres_dir)
        assert len(genres) > 0, "No genre directories found"


class TestGenreIndex:
    """INDEX.md must cross-reference all genre directories."""

    def test_index_exists(self, genres_dir):
        assert (genres_dir / "INDEX.md").exists(), "genres/INDEX.md missing"

    def test_all_genres_in_index(self, genres_dir):
        index_file = genres_dir / "INDEX.md"
        if not index_file.exists():
            pytest.skip("INDEX.md not found")

        index_content = index_file.read_text()
        index_refs = set(re.findall(r'\(([a-z0-9-]+)/README\.md\)', index_content))
        actual_genres = _get_actual_genres(genres_dir)

        missing = actual_genres - index_refs
        assert not missing, f"Genres not in INDEX.md: {', '.join(sorted(missing))}"

    def test_no_orphan_index_refs(self, genres_dir):
        index_file = genres_dir / "INDEX.md"
        if not index_file.exists():
            pytest.skip("INDEX.md not found")

        index_content = index_file.read_text()
        index_refs = set(re.findall(r'\(([a-z0-9-]+)/README\.md\)', index_content))
        actual_genres = _get_actual_genres(genres_dir)

        orphans = index_refs - actual_genres
        assert not orphans, f"INDEX.md references missing dirs: {', '.join(sorted(orphans))}"


class TestGenreListRef:
    """genre-list.md reference should exist."""

    def test_genre_list_exists(self, reference_dir):
        genre_list = reference_dir / "suno" / "genre-list.md"
        assert genre_list.exists(), "reference/suno/genre-list.md not found"


class TestGenreReadmeStructure:
    """Each genre README must have a top-level heading."""

    def test_genre_readmes_have_headings(self, genres_dir):
        actual_genres = _get_actual_genres(genres_dir)
        missing_headings = []
        for genre in sorted(actual_genres):
            readme = genres_dir / genre / "README.md"
            content = readme.read_text()
            if not re.search(r'^# .+', content, re.MULTILINE):
                missing_headings.append(genre)

        assert not missing_headings, (
            f"Genre READMEs missing headings: {', '.join(missing_headings)}"
        )
