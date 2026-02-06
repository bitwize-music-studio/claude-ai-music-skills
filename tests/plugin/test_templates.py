"""Tests for template files: existence, structure, references."""

import re

import pytest

pytestmark = pytest.mark.plugin

REQUIRED_TEMPLATES = [
    'album.md',
    'track.md',
    'artist.md',
    'research.md',
    'sources.md',
]


class TestTemplateExistence:
    """Required template files must exist."""

    @pytest.mark.parametrize("template", REQUIRED_TEMPLATES)
    def test_required_template_exists(self, templates_dir, template):
        assert (templates_dir / template).exists(), f"Required template missing: {template}"

    def test_referenced_templates_exist(self, templates_dir, claude_md_content):
        template_refs = re.findall(r'/templates/([a-zA-Z0-9_-]+\.md)', claude_md_content)
        missing = [
            ref for ref in set(template_refs)
            if not (templates_dir / ref).exists()
        ]
        assert not missing, f"Templates referenced in CLAUDE.md but missing: {missing}"


class TestTrackTemplate:
    """track.md template must have required sections."""

    @pytest.mark.parametrize("section", ['Status', 'Suno Inputs', 'Generation Log'])
    def test_track_template_section(self, templates_dir, section):
        track_template = templates_dir / "track.md"
        if not track_template.exists():
            pytest.skip("track.md not found")
        content = track_template.read_text()
        assert section.lower() in content.lower(), f"track.md missing section: {section}"


class TestAlbumTemplate:
    """album.md template must have required sections."""

    @pytest.mark.parametrize("section", ['Concept', 'Tracklist', 'Production Notes'])
    def test_album_template_section(self, templates_dir, section):
        album_template = templates_dir / "album.md"
        if not album_template.exists():
            pytest.skip("album.md not found")
        content = album_template.read_text()
        assert section.lower() in content.lower(), f"album.md missing section: {section}"
