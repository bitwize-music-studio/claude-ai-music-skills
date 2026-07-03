"""Tests for tools/cloud/upload_to_cloud.py."""

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# Import the module under test
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Force-mock boto3 before importing the module so tests behave consistently
# regardless of whether boto3 is installed on this machine.
# Save originals and restore after import to prevent MagicMock pollution
# leaking into later test files.
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


# Real exception classes for testing except-clause handling.
# MagicMock can't be caught by except, so we need real classes.
class _MockClientError(Exception):
    pass


class _MockNoCredentialsError(Exception):
    pass


mod.ClientError = _MockClientError
mod.NoCredentialsError = _MockNoCredentialsError


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


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestUploadFile:
    """Tests for single file upload to S3/R2."""

    @pytest.fixture()
    def fake_video(self, tmp_path):
        f = tmp_path / "promo.mp4"
        f.write_bytes(b"fake video content")
        return f

    def test_happy_path(self, fake_video):
        client = MagicMock()
        result = mod.upload_file(client, "bucket", fake_video, "key/promo.mp4")
        assert result is True
        client.upload_file.assert_called_once()

    def test_dry_run_skips_upload(self, fake_video):
        client = MagicMock()
        result = mod.upload_file(client, "bucket", fake_video, "key/promo.mp4", dry_run=True)
        assert result is True
        client.upload_file.assert_not_called()

    def test_client_error_returns_false(self, fake_video):
        client = MagicMock()
        client.upload_file.side_effect = _MockClientError("403 Forbidden")
        result = mod.upload_file(client, "bucket", fake_video, "key/promo.mp4")
        assert result is False

    def test_no_credentials_returns_false(self, fake_video):
        client = MagicMock()
        client.upload_file.side_effect = _MockNoCredentialsError()
        result = mod.upload_file(client, "bucket", fake_video, "key/promo.mp4")
        assert result is False

    def test_public_read_sets_acl(self, fake_video):
        client = MagicMock()
        mod.upload_file(client, "bucket", fake_video, "key/promo.mp4", public_read=True)
        _, kwargs = client.upload_file.call_args
        assert kwargs["ExtraArgs"]["ACL"] == "public-read"

    def test_private_no_acl(self, fake_video):
        client = MagicMock()
        mod.upload_file(client, "bucket", fake_video, "key/promo.mp4", public_read=False)
        _, kwargs = client.upload_file.call_args
        assert "ACL" not in kwargs["ExtraArgs"]

    def test_content_type_passed(self, fake_video):
        client = MagicMock()
        mod.upload_file(client, "bucket", fake_video, "key/promo.mp4")
        _, kwargs = client.upload_file.call_args
        assert kwargs["ExtraArgs"]["ContentType"] == "video/mp4"


# ---------------------------------------------------------------------------
# retry_upload
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRetryUpload:
    """Tests for upload retry with exponential backoff."""

    @pytest.fixture()
    def fake_video(self, tmp_path):
        f = tmp_path / "promo.mp4"
        f.write_bytes(b"fake video content")
        return f

    @patch.object(time, "sleep")
    def test_success_first_attempt(self, mock_sleep, fake_video):
        client = MagicMock()
        result = mod.retry_upload(client, "bucket", fake_video, "key/f.mp4", max_retries=3)
        assert result is True
        mock_sleep.assert_not_called()

    @patch.object(time, "sleep")
    def test_success_on_second_attempt(self, mock_sleep, fake_video):
        client = MagicMock()
        client.upload_file.side_effect = [_MockClientError("500"), None]
        result = mod.retry_upload(client, "bucket", fake_video, "key/f.mp4", max_retries=3)
        assert result is True
        assert client.upload_file.call_count == 2

    @patch.object(time, "sleep")
    def test_all_retries_fail(self, mock_sleep, fake_video):
        client = MagicMock()
        client.upload_file.side_effect = _MockClientError("500")
        result = mod.retry_upload(client, "bucket", fake_video, "key/f.mp4", max_retries=3)
        assert result is False
        assert client.upload_file.call_count == 3

    def test_dry_run_no_retry(self, fake_video):
        result = mod.retry_upload(None, "bucket", fake_video, "key/f.mp4", dry_run=True)
        assert result is True


# ---------------------------------------------------------------------------
# get_s3_client
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetS3Client:
    """Tests for S3/R2 client creation."""

    @patch.object(mod, "boto3")
    def test_r2_provider(self, mock_boto3):
        config = {
            "cloud": {
                "provider": "r2",
                "r2": {
                    "account_id": "abc123",
                    "access_key_id": "key",
                    "secret_access_key": "secret",
                },
            }
        }
        mod.get_s3_client(config)
        mock_boto3.client.assert_called_once_with(
            "s3",
            endpoint_url="https://abc123.r2.cloudflarestorage.com",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
        )

    @patch.object(mod, "boto3")
    def test_s3_provider(self, mock_boto3):
        config = {
            "cloud": {
                "provider": "s3",
                "s3": {
                    "region": "eu-west-1",
                    "access_key_id": "key",
                    "secret_access_key": "secret",
                },
            }
        }
        mod.get_s3_client(config)
        mock_boto3.client.assert_called_once_with(
            "s3",
            region_name="eu-west-1",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
        )

    def test_missing_r2_credentials_exits(self):
        config = {"cloud": {"provider": "r2", "r2": {"account_id": "abc"}}}
        with pytest.raises(SystemExit):
            mod.get_s3_client(config)

    def test_unknown_provider_exits(self):
        config = {"cloud": {"provider": "azure"}}
        with pytest.raises(SystemExit):
            mod.get_s3_client(config)


# ---------------------------------------------------------------------------
# find_album_path
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFindAlbumPath:
    """Tests for album directory resolution."""

    def _make_config(self, tmp_path):
        return {
            "paths": {"audio_root": str(tmp_path)},
            "artist": {"name": "testartist"},
        }

    def test_mirrored_structure(self, tmp_path):
        album_dir = tmp_path / "artists" / "testartist" / "albums" / "hip-hop" / "my-album"
        album_dir.mkdir(parents=True)
        result = mod.find_album_path(self._make_config(tmp_path), "my-album")
        assert result == album_dir

    def test_direct_path(self, tmp_path):
        album_dir = tmp_path / "my-album"
        album_dir.mkdir()
        result = mod.find_album_path(self._make_config(tmp_path), "my-album")
        assert result == album_dir

    def test_audio_root_override(self, tmp_path):
        override_root = tmp_path / "custom"
        album_dir = override_root / "my-album"
        album_dir.mkdir(parents=True)
        config = self._make_config(tmp_path)
        result = mod.find_album_path(config, "my-album", audio_root_override=str(override_root))
        assert result == album_dir

    def test_not_found_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            mod.find_album_path(self._make_config(tmp_path), "nonexistent")

    def test_path_traversal_in_name_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            mod.find_album_path(self._make_config(tmp_path), "../../../etc")


class TestCloudEnabledGate:
    """cloud.enabled honors quoted boolean strings (#388)."""

    def test_quoted_false_exits(self, monkeypatch):
        monkeypatch.setattr(mod, "load_config", lambda *a, **k: {"cloud": {"enabled": "false"}})
        monkeypatch.setattr("sys.argv", ["upload_to_cloud.py", "some-album"])
        with pytest.raises(SystemExit):
            mod.main()

    def test_quoted_no_exits(self, monkeypatch):
        monkeypatch.setattr(mod, "load_config", lambda *a, **k: {"cloud": {"enabled": "no"}})
        monkeypatch.setattr("sys.argv", ["upload_to_cloud.py", "some-album"])
        with pytest.raises(SystemExit):
            mod.main()


class TestRetriesValidation:
    """--retries <= 0 must not silently skip every upload attempt (#385)."""

    @pytest.fixture()
    def fake_video(self, tmp_path):
        f = tmp_path / "promo.mp4"
        f.write_bytes(b"fake video content")
        return f

    def test_zero_retries_still_attempts_once(self, fake_video):
        client = MagicMock()
        result = mod.retry_upload(client, "bucket", fake_video, "key/f.mp4", max_retries=0)
        assert result is True
        assert client.upload_file.call_count == 1

    def test_negative_retries_still_attempts_once(self, fake_video):
        client = MagicMock()
        result = mod.retry_upload(client, "bucket", fake_video, "key/f.mp4", max_retries=-3)
        assert result is True
        assert client.upload_file.call_count == 1

    def test_cli_rejects_non_positive_retries(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["upload_to_cloud.py", "some-album", "--retries", "0"])
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        assert exc_info.value.code == 2  # argparse usage error, not silent failure
