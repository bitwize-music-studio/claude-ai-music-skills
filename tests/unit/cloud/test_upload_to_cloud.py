"""Tests for tools/cloud/upload_to_cloud.py utility functions."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock boto3 before importing the module so tests behave consistently
# regardless of whether boto3 is installed on this machine.
sys.modules["boto3"] = MagicMock()
sys.modules["botocore"] = MagicMock()
sys.modules["botocore.exceptions"] = MagicMock()

from tools.cloud import upload_to_cloud as mod


# ---------------------------------------------------------------------------
# _is_within
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestIsWithin:
    """Tests for path traversal prevention."""

    def test_child_inside_parent(self, tmp_path):
        child = tmp_path / "albums" / "my-album"
        child.mkdir(parents=True)
        assert mod._is_within(child, tmp_path) is True

    def test_child_outside_parent(self, tmp_path):
        outside = tmp_path.parent / "outside"
        outside.mkdir(exist_ok=True)
        assert mod._is_within(outside, tmp_path) is False

    def test_same_directory(self, tmp_path):
        assert mod._is_within(tmp_path, tmp_path) is True

    def test_traversal_attack(self, tmp_path):
        malicious = tmp_path / "albums" / ".." / ".." / "etc"
        assert mod._is_within(malicious, tmp_path) is False


# ---------------------------------------------------------------------------
# get_content_type
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetContentType:
    """Tests for MIME type lookup."""

    def test_mp4_file(self):
        assert mod.get_content_type(Path("video.mp4")) == "video/mp4"

    def test_png_file(self):
        assert mod.get_content_type(Path("image.png")) == "image/png"

    def test_wav_file(self):
        result = mod.get_content_type(Path("audio.wav"))
        assert "audio" in result

    def test_unknown_extension(self):
        assert mod.get_content_type(Path("file.xyz123")) == "application/octet-stream"

    def test_no_extension(self):
        assert mod.get_content_type(Path("README")) == "application/octet-stream"


# ---------------------------------------------------------------------------
# format_size
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFormatSize:
    """Tests for human-readable file size formatting."""

    def test_bytes(self):
        assert mod.format_size(500) == "500.0 B"

    def test_kilobytes(self):
        result = mod.format_size(2048)
        assert "KB" in result

    def test_megabytes(self):
        result = mod.format_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = mod.format_size(3 * 1024 ** 3)
        assert "GB" in result

    def test_terabytes(self):
        result = mod.format_size(2 * 1024 ** 4)
        assert "TB" in result

    def test_zero(self):
        assert mod.format_size(0) == "0.0 B"


# ---------------------------------------------------------------------------
# get_bucket_name
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetBucketName:
    """Tests for bucket name extraction from config."""

    def test_r2_bucket(self):
        config = {"cloud": {"provider": "r2", "r2": {"bucket": "my-bucket"}}}
        assert mod.get_bucket_name(config) == "my-bucket"

    def test_s3_bucket(self):
        config = {"cloud": {"provider": "s3", "s3": {"bucket": "s3-bucket"}}}
        assert mod.get_bucket_name(config) == "s3-bucket"

    def test_defaults_to_r2(self):
        config = {"cloud": {"r2": {"bucket": "default-bucket"}}}
        assert mod.get_bucket_name(config) == "default-bucket"

    def test_missing_bucket_exits(self):
        config = {"cloud": {"provider": "r2", "r2": {}}}
        with pytest.raises(SystemExit):
            mod.get_bucket_name(config)


# ---------------------------------------------------------------------------
# get_files_to_upload
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetFilesToUpload:
    """Tests for file discovery by upload type."""

    def test_promos_type(self, tmp_path):
        promo_dir = tmp_path / "promo_videos"
        promo_dir.mkdir()
        (promo_dir / "01-track.mp4").touch()
        (promo_dir / "02-track.mp4").touch()
        files = mod.get_files_to_upload(tmp_path, "promos")
        assert len(files) == 2

    def test_sampler_type(self, tmp_path):
        (tmp_path / "album_sampler.mp4").touch()
        files = mod.get_files_to_upload(tmp_path, "sampler")
        assert len(files) == 1
        assert files[0].name == "album_sampler.mp4"

    def test_all_type(self, tmp_path):
        promo_dir = tmp_path / "promo_videos"
        promo_dir.mkdir()
        (promo_dir / "01-track.mp4").touch()
        (tmp_path / "album_sampler.mp4").touch()
        files = mod.get_files_to_upload(tmp_path, "all")
        assert len(files) == 2

    def test_missing_promo_dir(self, tmp_path):
        files = mod.get_files_to_upload(tmp_path, "promos")
        assert files == []

    def test_missing_sampler(self, tmp_path):
        files = mod.get_files_to_upload(tmp_path, "sampler")
        assert files == []

    def test_non_mp4_ignored(self, tmp_path):
        promo_dir = tmp_path / "promo_videos"
        promo_dir.mkdir()
        (promo_dir / "thumbnail.png").touch()
        (promo_dir / "track.mp4").touch()
        files = mod.get_files_to_upload(tmp_path, "promos")
        assert len(files) == 1
