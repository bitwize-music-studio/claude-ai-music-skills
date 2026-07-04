"""Regression tests for find_album_path glob-injection guard ordering (#405).

The glob-metacharacter / path-separator validation must run BEFORE any
glob expansion. Previously the mirrored-structure branch interpolated
``album_name`` into a glob pattern (``albums/*/{album_name}``) and could
silently resolve a wildcard to an unintended in-tree album directory
before the explicit rejection ever executed.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock boto3 before importing the module so tests behave consistently
# regardless of whether boto3 is installed on this machine. Save originals and
# restore after import to prevent MagicMock pollution leaking into later tests.
_MOCK_DEPS = ["boto3", "botocore", "botocore.exceptions"]
_SAVED_DEPS = {dep: sys.modules.get(dep) for dep in _MOCK_DEPS}
for dep in _MOCK_DEPS:
    sys.modules[dep] = MagicMock()

from tools.cloud import upload_to_cloud as mod

# Restore original modules to avoid polluting later tests
for dep, original in _SAVED_DEPS.items():
    if original is None:
        sys.modules.pop(dep, None)
    else:
        sys.modules[dep] = original


@pytest.mark.unit
class TestFindAlbumPathGlobInjection:
    """album_name with glob metacharacters is rejected before glob expansion (#405)."""

    def _make_config(self, tmp_path):
        return {
            "paths": {"audio_root": str(tmp_path)},
            "artist": {"name": "testartist"},
        }

    def test_star_rejected_even_when_a_dir_matches(self, tmp_path):
        # A real album dir exists that the pattern albums/*/* would match.
        album_dir = tmp_path / "artists" / "testartist" / "albums" / "hip-hop" / "my-album"
        album_dir.mkdir(parents=True)
        # album_name "*" must be rejected outright, NOT resolved to album_dir.
        with pytest.raises(SystemExit):
            mod.find_album_path(self._make_config(tmp_path), "*")

    def test_question_mark_rejected_even_when_a_dir_matches(self, tmp_path):
        # "a?b" would glob-match this dir via albums/*/a?b if the guard is bypassed.
        matching_dir = tmp_path / "artists" / "testartist" / "albums" / "hip-hop" / "aXb"
        matching_dir.mkdir(parents=True)
        with pytest.raises(SystemExit):
            mod.find_album_path(self._make_config(tmp_path), "a?b")

    def test_bracket_rejected_even_when_a_dir_matches(self, tmp_path):
        # "[abc]" would glob-match a single-char dir via albums/*/[abc].
        matching_dir = tmp_path / "artists" / "testartist" / "albums" / "hip-hop" / "b"
        matching_dir.mkdir(parents=True)
        with pytest.raises(SystemExit):
            mod.find_album_path(self._make_config(tmp_path), "[abc]")

    def test_normal_album_name_still_resolves(self, tmp_path):
        album_dir = tmp_path / "artists" / "testartist" / "albums" / "hip-hop" / "my-album"
        album_dir.mkdir(parents=True)
        result = mod.find_album_path(self._make_config(tmp_path), "my-album")
        assert result == album_dir
