"""Regression tests for issue #411.

find_mastered_dir must skip candidate paths that exist as regular files
instead of crashing with NotADirectoryError when it calls iterdir() on them.
"""

import sys
from pathlib import Path

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.promotion import generate_all_promos as mod


@pytest.mark.unit
class TestFindMasteredDirFileCandidate:
    """A candidate path that exists as a FILE must not crash the search (#411)."""

    def test_mastered_file_candidate_is_skipped(self, tmp_path):
        """'mastered' existing as a file must be skipped, not iterdir()'d."""
        # album_dir itself has no audio, so the loop advances to sub-candidates.
        (tmp_path / "mastered").write_bytes(b"not a directory")

        # Before the fix this raised NotADirectoryError; now it falls back.
        result = mod.find_mastered_dir(tmp_path)
        assert result == tmp_path

    def test_wavs_file_candidate_is_skipped(self, tmp_path):
        """'wavs' existing as a file must be skipped, not iterdir()'d."""
        (tmp_path / "wavs").write_bytes(b"not a directory")

        result = mod.find_mastered_dir(tmp_path)
        assert result == tmp_path

    def test_file_candidate_skipped_and_real_dir_found(self, tmp_path):
        """A file candidate is skipped while a later real audio dir is still found."""
        # 'mastered' is a decoy file (probed before 'wavs' in candidate order).
        (tmp_path / "mastered").write_bytes(b"not a directory")
        # 'wavs' is a real directory holding audio.
        wavs = tmp_path / "wavs"
        wavs.mkdir()
        (wavs / "01-track.wav").write_bytes(b"audio")

        result = mod.find_mastered_dir(tmp_path)
        assert result == wavs
