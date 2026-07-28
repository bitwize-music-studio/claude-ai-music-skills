"""Tests for the guarded album-path helpers in handlers/_shared.py.

These lock two things: that the helpers reproduce the inline construction they
replaced at fifteen call sites across six handler modules, and that they keep
the traversal guards ``core.py:resolve_path`` has always applied. #529 removed
an unguarded ``tools/shared/paths.py`` precisely because a helper without those
guards is the one a contributor reaches for.

The call sites' own contracts — which failure each reports, and how — are
covered in ``test_album_path_call_sites.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers._shared import (
    ALBUM_LAYOUT,
    PATH_ESCAPES_ROOT,
    _album_dir,
    _albums_dir,
    _genre_dir,
)


class TestAlbumDirShape:
    """The helper must reproduce the hand-built path it replaced, exactly."""

    def test_matches_the_inline_construction(self, tmp_path):
        assert _album_dir(
            tmp_path, artist="bitwize", genre="synthwave", album="neon",
        ) == tmp_path / "artists" / "bitwize" / "albums" / "synthwave" / "neon"

    def test_accepts_a_string_root(self, tmp_path):
        """Callers pass config values, which arrive as str."""
        assert _album_dir(
            str(tmp_path), artist="a", genre="g", album="al",
        ) == tmp_path / "artists" / "a" / "albums" / "g" / "al"

    def test_subdir_is_appended(self, tmp_path):
        """resolve_path's 'tracks' type appends a child directory."""
        assert _album_dir(
            tmp_path, artist="a", genre="g", album="al", subdir="tracks",
        ) == tmp_path / "artists" / "a" / "albums" / "g" / "al" / "tracks"

    def test_same_shape_under_every_root(self, tmp_path):
        """Content, audio and documents mirror one another — that is the point."""
        kwargs = {"artist": "a", "genre": "g", "album": "al"}
        content, audio = tmp_path / "content", tmp_path / "audio"
        assert (
            _album_dir(content, **kwargs).relative_to(content)
            == _album_dir(audio, **kwargs).relative_to(audio)
        )


class TestParents:
    """_genre_dir and _albums_dir are the layout truncated, not re-spelled."""

    def test_genre_dir_is_album_dir_parent(self, tmp_path):
        kwargs = {"artist": "a", "genre": "g"}
        assert _genre_dir(tmp_path, **kwargs) == _album_dir(
            tmp_path, album="al", **kwargs,
        ).parent

    def test_albums_dir_is_genre_dir_parent(self, tmp_path):
        assert _albums_dir(tmp_path, artist="a") == _genre_dir(
            tmp_path, artist="a", genre="g",
        ).parent

    def test_albums_dir_matches_the_inline_construction(self, tmp_path):
        assert _albums_dir(tmp_path, artist="bitwize") == (
            tmp_path / "artists" / "bitwize" / "albums"
        )


class TestGuards:
    """The guards #529 removed the unguarded helper for."""

    def test_normalizes_the_album_slug(self, tmp_path):
        """Callers need not pre-normalize; the helper does it."""
        assert _album_dir(
            tmp_path, artist="a", genre="g", album="My Album",
        ).name == "my-album"

    def test_normalizing_is_idempotent(self, tmp_path):
        """Most callers pass an already-normalized slug."""
        once = _album_dir(tmp_path, artist="a", genre="g", album="my-album")
        twice = _album_dir(tmp_path, artist="a", genre="g", album=once.name)
        assert once == twice

    @pytest.mark.parametrize("evil", [
        "../../../../../../tmp/pwned",
        "..",
        "a/b",
        "a\\b",
        "x\x00y",
    ])
    def test_rejects_traversal_and_separators(self, tmp_path, evil):
        """The exact class of input that escaped the deleted helper."""
        with pytest.raises(ValueError):
            _album_dir(tmp_path, artist="a", genre="g", album=evil)

    def test_result_stays_within_root(self, tmp_path):
        """Defense in depth: artist and genre are not slug-normalized."""
        with pytest.raises(ValueError, match=PATH_ESCAPES_ROOT):
            _album_dir(tmp_path, artist="../../..", genre="g", album="al")

    @pytest.mark.parametrize("absolute", ["/etc", "/", "\\windows"])
    def test_rejects_an_absolute_segment_rather_than_relativizing_it(
        self, tmp_path, absolute,
    ):
        """A confined-but-wrong path is a worse failure mode than an error.

        Joining segment by segment stops an absolute segment resetting the join
        to the filesystem root — but on its own that silently rewrites
        genre="/etc" into a relative "etc" and returns a path the caller never
        asked for. develop rejected this input; so does the helper, with the
        same message.
        """
        with pytest.raises(ValueError, match=PATH_ESCAPES_ROOT):
            _album_dir(tmp_path, artist="a", genre=absolute, album="al")

    def test_rejects_an_absolute_subdir(self, tmp_path):
        """subdir is joined last, so it is the other place an absolute lands."""
        with pytest.raises(ValueError, match=PATH_ESCAPES_ROOT):
            _album_dir(tmp_path, artist="a", genre="g", album="al", subdir="/etc")

    def test_escape_message_is_the_one_resolve_path_returns(self):
        """resolve_path surfaces str(exc) verbatim — keep the wording stable."""
        assert PATH_ESCAPES_ROOT == "Resolved path escapes root directory"

    @staticmethod
    def _symlinked_album(tmp_path):
        """An album directory that is a symlink pointing outside its root."""
        root = tmp_path / "audio-link"
        real = tmp_path / "elsewhere" / "test-album"
        real.mkdir(parents=True)
        linked = root / "artists" / "a" / "albums" / "g"
        linked.mkdir(parents=True)
        (linked / "test-album").symlink_to(real)
        return root, linked

    def test_symlink_escaping_root_is_rejected_under_confine(self, tmp_path):
        """confine=True is what resolve_path has always done, and must keep doing.

        The lexical pass cannot see this: every segment is a plain name, and the
        escape only exists once the symlink is followed.

        It is also the default, so a new caller who forgets fails closed and
        loudly rather than silently losing the check. Which value each *existing*
        site passes is decided by what that site did before centralisation, not
        by the default — see test_album_path_call_sites.py.
        """
        root, _ = self._symlinked_album(tmp_path)
        with pytest.raises(ValueError, match=PATH_ESCAPES_ROOT):
            _album_dir(root, artist="a", genre="g", album="test-album", confine=True)

    def test_symlinked_album_dir_allowed_with_confine_false(self, tmp_path):
        """The supported case, and it must be opted into explicitly.

        An album's audio directory may legitimately be a symlink pointing outside
        audio_root — see
        test_server.py::TestValidateAlbumStructure::test_symlinked_audio_dir_passes.
        Resolving rejects that layout, so every site that operates on an album
        directory which already exists passes confine=False. The lexical
        traversal guard still applies there.
        """
        root, linked = self._symlinked_album(tmp_path)
        resolved = _album_dir(
            root, artist="a", genre="g", album="test-album", confine=False,
        )
        assert resolved == linked / "test-album"
        assert resolved.is_dir()

    def test_lexical_guard_still_applies_when_confine_is_false(self, tmp_path):
        """Opting out of resolution must not opt out of traversal rejection."""
        with pytest.raises(ValueError):
            _album_dir(
                tmp_path, artist="../../..", genre="g", album="al", confine=False,
            )

    def test_empty_genre_collapses_as_path_always_did(self, tmp_path):
        """A missing genre is a caller bug, not a traversal — preserve behaviour."""
        assert _album_dir(tmp_path, artist="a", genre="", album="al") == (
            tmp_path / "artists" / "a" / "albums" / "al"
        )


def test_layout_constant_is_the_documented_shape():
    """Guards the constant the whole plugin's on-disk structure depends on."""
    assert ALBUM_LAYOUT == "artists/{artist}/albums/{genre}/{album}"
