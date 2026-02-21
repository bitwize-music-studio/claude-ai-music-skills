"""Unit tests for the path resolver utility."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.shared.paths import resolve_overrides_dir, resolve_path, resolve_tracks_dir


@pytest.mark.unit
class TestResolvePath:
    """Tests for resolve_path()."""

    SAMPLE_CONFIG = {
        "artist": {"name": "test-artist"},
        "paths": {
            "content_root": "/tmp/test-content",
            "audio_root": "/tmp/test-audio",
            "documents_root": "/tmp/test-docs",
        },
    }

    def test_content_path(self):
        result = resolve_path(
            "content", "my-album", genre="rock", config=self.SAMPLE_CONFIG
        )
        expected = Path("/tmp/test-content").resolve() / "artists/test-artist/albums/rock/my-album"
        assert result == expected

    def test_audio_path(self):
        result = resolve_path("audio", "my-album", genre="rock", config=self.SAMPLE_CONFIG)
        expected = Path("/tmp/test-audio").resolve() / "artists/test-artist/albums/rock/my-album"
        assert result == expected

    def test_documents_path(self):
        result = resolve_path("documents", "my-album", genre="rock", config=self.SAMPLE_CONFIG)
        expected = Path("/tmp/test-docs").resolve() / "artists/test-artist/albums/rock/my-album"
        assert result == expected

    def test_genre_required(self):
        with pytest.raises(ValueError, match="Genre is required"):
            resolve_path("content", "my-album", config=self.SAMPLE_CONFIG)

    def test_audio_requires_genre(self):
        with pytest.raises(ValueError, match="Genre is required"):
            resolve_path("audio", "my-album", config=self.SAMPLE_CONFIG)

    def test_documents_requires_genre(self):
        with pytest.raises(ValueError, match="Genre is required"):
            resolve_path("documents", "my-album", config=self.SAMPLE_CONFIG)

    def test_invalid_path_type(self):
        with pytest.raises(ValueError, match="Invalid path_type"):
            resolve_path("invalid", "my-album", config=self.SAMPLE_CONFIG)

    def test_artist_override(self):
        result = resolve_path(
            "audio", "my-album", artist="other-artist", genre="rock", config=self.SAMPLE_CONFIG
        )
        expected = Path("/tmp/test-audio").resolve() / "artists/other-artist/albums/rock/my-album"
        assert result == expected

    def test_missing_artist_name(self):
        config = {"artist": {}, "paths": {"content_root": "/tmp"}}
        with pytest.raises(ValueError, match="Artist name is required"):
            resolve_path("audio", "my-album", genre="rock", config=config)

    def test_tilde_expansion(self):
        config = {
            "artist": {"name": "artist"},
            "paths": {"audio_root": "~/music"},
        }
        result = resolve_path("audio", "album", genre="rock", config=config)
        assert "~" not in str(result)
        assert result.is_absolute()


@pytest.mark.unit
class TestResolveTracksDir:
    """Tests for resolve_tracks_dir()."""

    SAMPLE_CONFIG = {
        "artist": {"name": "test-artist"},
        "paths": {
            "content_root": "/tmp/test-content",
            "audio_root": "/tmp/test-audio",
            "documents_root": "/tmp/test-docs",
        },
    }

    def test_tracks_dir(self):
        result = resolve_tracks_dir("my-album", "rock", config=self.SAMPLE_CONFIG)
        expected = Path("/tmp/test-content").resolve() / "artists/test-artist/albums/rock/my-album/tracks"
        assert result == expected


@pytest.mark.unit
class TestResolveOverridesDir:
    """Tests for resolve_overrides_dir()."""

    def test_explicit_overrides_path(self):
        config = {
            "paths": {
                "content_root": "/tmp/content",
                "overrides": "/tmp/my-overrides",
            }
        }
        result = resolve_overrides_dir(config=config)
        assert result == Path("/tmp/my-overrides").resolve()

    def test_default_overrides_path(self):
        config = {"paths": {"content_root": "/tmp/content"}}
        result = resolve_overrides_dir(config=config)
        assert result == Path("/tmp/content").resolve() / "overrides"

    def test_tilde_expansion(self):
        config = {"paths": {"content_root": "~/music"}}
        result = resolve_overrides_dir(config=config)
        assert "~" not in str(result)
