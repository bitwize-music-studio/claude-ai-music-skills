"""Tests for genre directory structure vs INDEX.md and genre-list.md."""

import re
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


GENRE_README_REQUIRED_SECTIONS = [
    'Genre Overview',
    'Characteristics',
    'Lyric Conventions',
    'Subgenres',
    'Artists',
    'Suno Prompt Keywords',
    'Reference Tracks',
]


class TestGenreReadmeRequiredSections:
    """Each genre README must have all required sections (PR #73)."""

    @pytest.mark.parametrize("section", GENRE_README_REQUIRED_SECTIONS)
    def test_genre_readmes_have_required_sections(self, genres_dir, section):
        actual_genres = _get_actual_genres(genres_dir)
        missing = []
        for genre in sorted(actual_genres):
            readme = genres_dir / genre / "README.md"
            content = readme.read_text().lower()
            if section.lower() not in content:
                missing.append(genre)

        assert not missing, (
            f"Genre READMEs missing '{section}': {', '.join(missing)}"
        )


class TestGenrePresetsYaml:
    """genre-presets.yaml must be valid and have required fields (PR #73)."""

    def test_presets_file_exists(self, project_root):
        presets = project_root / "tools" / "mastering" / "genre-presets.yaml"
        assert presets.exists(), "tools/mastering/genre-presets.yaml missing"

    def test_presets_valid_yaml(self, project_root):
        import yaml
        presets_file = project_root / "tools" / "mastering" / "genre-presets.yaml"
        if not presets_file.exists():
            pytest.skip("genre-presets.yaml not found")
        data = yaml.safe_load(presets_file.read_text())
        assert isinstance(data, dict), "genre-presets.yaml must parse to a dict"
        assert 'genres' in data, "genre-presets.yaml missing 'genres' key"
        assert 'defaults' in data, "genre-presets.yaml missing 'defaults' key"

    def test_presets_have_required_fields(self, project_root):
        import yaml
        presets_file = project_root / "tools" / "mastering" / "genre-presets.yaml"
        if not presets_file.exists():
            pytest.skip("genre-presets.yaml not found")
        data = yaml.safe_load(presets_file.read_text())
        required_fields = {'target_lufs', 'cut_highmid', 'cut_highs'}

        invalid = []
        for genre, settings in data.get('genres', {}).items():
            missing = required_fields - set(settings.keys())
            if missing:
                invalid.append(f"{genre}: missing {', '.join(missing)}")

        assert not invalid, (
            "Genre presets with missing fields:\n" + "\n".join(invalid)
        )

    def test_defaults_have_required_fields(self, project_root):
        import yaml
        presets_file = project_root / "tools" / "mastering" / "genre-presets.yaml"
        if not presets_file.exists():
            pytest.skip("genre-presets.yaml not found")
        data = yaml.safe_load(presets_file.read_text())
        defaults = data.get('defaults', {})
        for field in ('target_lufs', 'cut_highmid', 'cut_highs'):
            assert field in defaults, f"defaults missing required field: {field}"

    def test_new_genres_have_presets(self, project_root):
        """Chanson, Middle Eastern Pop, and Schlager must have presets (PR #73)."""
        import yaml
        presets_file = project_root / "tools" / "mastering" / "genre-presets.yaml"
        if not presets_file.exists():
            pytest.skip("genre-presets.yaml not found")
        data = yaml.safe_load(presets_file.read_text())
        genres = data.get('genres', {})
        for expected in ('chanson', 'middle-eastern-pop', 'schlager'):
            assert expected in genres, (
                f"genre-presets.yaml missing preset for: {expected}"
            )
