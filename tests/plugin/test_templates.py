"""Tests for template files: existence, structure, references."""

import re
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state.parsers import parse_frontmatter

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


PROMO_TEMPLATES = [
    'campaign.md',
    'twitter.md',
    'instagram.md',
    'tiktok.md',
    'facebook.md',
    'youtube.md',
]

PROMO_REQUIRED_SECTIONS = {
    'campaign.md': ['Campaign Overview', 'Key Messages', 'Schedule'],
    'twitter.md': ['Album Announcement', 'Per-Track Posts'],
    'instagram.md': ['Album Announcement', 'Per-Track Captions', 'Hashtag'],
    'tiktok.md': ['Album Announcement', 'Per-Track Captions'],
    'facebook.md': ['Album Announcement', 'Per-Track Posts'],
    'youtube.md': ['Full Album Video Description', 'Per-Track Video Descriptions'],
}


class TestPromoTemplates:
    """Promo templates must exist with required sections."""

    @pytest.mark.parametrize("template", PROMO_TEMPLATES)
    def test_promo_template_exists(self, templates_dir, template):
        promo_dir = templates_dir / "promo"
        assert (promo_dir / template).exists(), f"Promo template missing: promo/{template}"

    @pytest.mark.parametrize("template", PROMO_TEMPLATES)
    def test_promo_template_not_empty(self, templates_dir, template):
        promo_file = templates_dir / "promo" / template
        if not promo_file.exists():
            pytest.skip(f"promo/{template} not found")
        content = promo_file.read_text()
        assert len(content.strip()) > 50, f"promo/{template} appears to be empty"

    @pytest.mark.parametrize(
        "template,sections",
        [(t, PROMO_REQUIRED_SECTIONS[t]) for t in PROMO_TEMPLATES],
        ids=PROMO_TEMPLATES,
    )
    def test_promo_template_sections(self, templates_dir, template, sections):
        promo_file = templates_dir / "promo" / template
        if not promo_file.exists():
            pytest.skip(f"promo/{template} not found")
        content = promo_file.read_text().lower()
        for section in sections:
            assert section.lower() in content, (
                f"promo/{template} missing section: {section}"
            )


class TestSourcesTemplatePromoPointer:
    """sources.md should reference promo/ directory."""

    def test_sources_references_promo_dir(self, templates_dir):
        sources = templates_dir / "sources.md"
        if not sources.exists():
            pytest.skip("sources.md not found")
        content = sources.read_text()
        assert 'promo/' in content, "sources.md should reference promo/ directory"


class TestTemplateFrontmatter:
    """Validates that album.md and track.md have parseable YAML frontmatter."""

    def test_album_has_frontmatter(self, templates_dir):
        album = templates_dir / "album.md"
        content = album.read_text()
        assert content.startswith('---'), "album.md must start with YAML frontmatter delimiter"
        fm = parse_frontmatter(content)
        assert isinstance(fm, dict), "album.md frontmatter must parse to a dict"
        assert '_error' not in fm, f"album.md frontmatter parse error: {fm.get('_error')}"

    def test_album_frontmatter_required_fields(self, templates_dir):
        album = templates_dir / "album.md"
        fm = parse_frontmatter(album.read_text())
        for field in ('title', 'explicit', 'genres'):
            assert field in fm, f"album.md frontmatter missing required field: {field}"

    def test_track_has_frontmatter(self, templates_dir):
        track = templates_dir / "track.md"
        content = track.read_text()
        assert content.startswith('---'), "track.md must start with YAML frontmatter delimiter"
        fm = parse_frontmatter(content)
        assert isinstance(fm, dict), "track.md frontmatter must parse to a dict"
        assert '_error' not in fm, f"track.md frontmatter parse error: {fm.get('_error')}"

    def test_track_frontmatter_required_fields(self, templates_dir):
        track = templates_dir / "track.md"
        fm = parse_frontmatter(track.read_text())
        for field in ('title', 'track_number', 'explicit'):
            assert field in fm, f"track.md frontmatter missing required field: {field}"


class TestTemplateTableFields:
    """Validates that required table fields exist in templates."""

    @pytest.mark.parametrize("field", ['Status', 'Tracks', 'Artist', 'Album'])
    def test_album_required_table_fields(self, templates_dir, field):
        album = templates_dir / "album.md"
        content = album.read_text()
        assert f'**{field}**' in content, f"album.md missing table field: {field}"

    @pytest.mark.parametrize("field", [
        'Status', 'Title', 'Track #', 'Suno Link', 'Explicit', 'Sources Verified',
    ])
    def test_track_required_table_fields(self, templates_dir, field):
        track = templates_dir / "track.md"
        content = track.read_text()
        assert f'**{field}**' in content, f"track.md missing table field: {field}"


class TestTrackTemplateLyricsWarning:
    """Validates the parentheses warning in the Lyrics Box."""

    def test_lyrics_box_has_parentheses_warning(self, templates_dir):
        track = templates_dir / "track.md"
        content = track.read_text()
        assert 'Suno sings EVERYTHING literally' in content, (
            "track.md Lyrics Box missing parentheses warning comment"
        )

    def test_no_parenthetical_directions_in_template(self, templates_dir):
        track = templates_dir / "track.md"
        content = track.read_text()
        # These should only appear inside the warning comment, not as actual directions
        bad_directions = ['(whispered)', '(softly)', '(screaming)', '(spoken)', '(laughing)']
        # Strip the warning comment before checking
        without_comment = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        for direction in bad_directions:
            assert direction.lower() not in without_comment.lower(), (
                f"track.md contains parenthetical direction '{direction}' outside warning comment"
            )


TRACK_REQUIRED_SECTIONS = [
    'Track Details',
    'Concept',
    'Musical Direction',
    'Suno Inputs',
    'Style Box',
    'Lyrics Box',
    'Streaming Lyrics',
    'Production Notes',
    'Pronunciation Notes',
    'Generation Log',
]


class TestTrackTemplateStructure:
    """Validates all expected sections exist in track.md."""

    @pytest.mark.parametrize("section", TRACK_REQUIRED_SECTIONS)
    def test_has_all_required_sections(self, templates_dir, section):
        track = templates_dir / "track.md"
        content = track.read_text()
        assert section.lower() in content.lower(), (
            f"track.md missing required section: {section}"
        )
