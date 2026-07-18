"""Real-S3 integration test for the cloud-upload path, backed by SeaweedFS.

Exercises the product's actual upload code — ``upload_to_cloud.retry_upload``
-> ``upload_file`` -> boto3 ``upload_file`` (PutObject) — against a live
SeaweedFS S3 gateway, then verifies the object via boto3.

Why the client is injected rather than built by ``get_s3_client``: that helper
only supports AWS-native S3 (region-based) and Cloudflare R2 (a hardcoded
``*.r2.cloudflarestorage.com`` endpoint). It has no way to target an arbitrary
S3-compatible endpoint like SeaweedFS, so the config-driven path cannot reach
SeaweedFS without a product change (see task-D-report.md — an optional,
approval-gated ``cloud.s3.endpoint_url`` enhancement is proposed there). The
meaningful product code — content-type detection, ExtraArgs/ACL handling, the
PutObject call, error handling, and the retry wrapper — lives in
``upload_file``/``retry_upload``, which the injected client drives faithfully.

Gated behind the ``integration`` marker AND ``BITWIZE_INTEGRATION`` so the
normal suite / 3-OS matrix collect-and-skip (no SeaweedFS present).
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("BITWIZE_INTEGRATION"),
        reason="integration services not available (set BITWIZE_INTEGRATION=1)",
    ),
]


def test_upload_round_trip_against_seaweedfs(s3_client, s3_bucket, tmp_path):
    from tools.cloud import upload_to_cloud

    # A real (tiny) file with non-trivial bytes, named like a real promo asset
    # so the product's mimetype detection yields a meaningful content type.
    payload = b"bitwize integration promo payload \x00\x01\x02\xff"
    src = tmp_path / "album_sampler.mp4"
    src.write_bytes(payload)

    # Mirror the product's real key layout: {artist}/{album}/promos/{file}.
    key = "integration-artist/integration-album/promos/album_sampler.mp4"

    # Drive the PRODUCT upload path. max_retries=1 avoids the exponential
    # backoff sleep on a clean run; retry_upload still wraps upload_file.
    ok = upload_to_cloud.retry_upload(
        s3_client,
        s3_bucket,
        src,
        key,
        public_read=False,
        dry_run=False,
        max_retries=1,
    )
    assert ok is True, "product upload path returned failure against SeaweedFS"

    # Verify the object really landed with the correct key.
    listed = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=key)
    keys = [obj["Key"] for obj in listed.get("Contents", [])]
    assert key in keys, f"uploaded key not found; got {keys}"

    # Verify the bytes round-tripped exactly.
    obj = s3_client.get_object(Bucket=s3_bucket, Key=key)
    assert obj["Body"].read() == payload

    # Verify the product-set metadata (content type comes from upload_file's
    # mimetypes.guess_type -> ExtraArgs ContentType).
    head = s3_client.head_object(Bucket=s3_bucket, Key=key)
    assert head["ContentLength"] == len(payload)
    assert head["ContentType"] == "video/mp4"


def test_dry_run_uploads_nothing(s3_client, s3_bucket, tmp_path):
    """The product's --dry-run path must not touch the real bucket."""
    from tools.cloud import upload_to_cloud

    src = tmp_path / "promo.mp4"
    src.write_bytes(b"should-not-be-uploaded")
    key = "integration-artist/integration-album/promos/promo.mp4"

    ok = upload_to_cloud.retry_upload(
        s3_client, s3_bucket, src, key,
        public_read=False, dry_run=True, max_retries=1,
    )
    assert ok is True  # dry run reports success without uploading

    listed = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=key)
    assert listed.get("Contents", []) == [], "dry run must not create objects"
