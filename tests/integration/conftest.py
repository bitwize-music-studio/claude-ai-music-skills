"""Fixtures for the real-service integration tests (Postgres + SeaweedFS/S3).

These tests exercise the db_* MCP tools and the boto3 cloud-upload path against
REAL services. They are double-gated so the normal suite and the 3-OS matrix
collect-and-skip without any services present:

  * every test module carries ``pytestmark = [pytest.mark.integration,
    pytest.mark.skipif(not BITWIZE_INTEGRATION, ...)]``; and
  * the CI ``integration`` job is the only place ``BITWIZE_INTEGRATION`` is set.

Nothing here connects to a service or imports psycopg2/boto3 at import time —
all heavyweight imports happen inside fixtures, which only run for a test that
was NOT skipped. So collecting ``tests/integration`` on a dev box (or the
windows/macos/ubuntu matrix) is inert.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import Any

import pytest

# The db_* handlers live under the server source tree, imported as
# ``from handlers import database`` (same as the unit suite). Put it on the
# path once, at collection time — cheap and side-effect free.
REPO_ROOT = Path(__file__).resolve().parents[2]
_SERVER_DIR = REPO_ROOT / "servers" / "bitwize-music-server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))


def pg_env() -> dict[str, Any]:
    """Postgres connection params from the CI env (with local-friendly defaults)."""
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "name": os.getenv("PGDATABASE", "bitwize_test"),
        "user": os.getenv("PGUSER", "bitwize"),
        "password": os.getenv("PGPASSWORD", "bitwize"),
    }


# ---------------------------------------------------------------------------
# Postgres fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_config(tmp_path, monkeypatch):
    """Write a throwaway config.yaml with ``database.enabled`` and point the
    connection module at it.

    Drives the *real* config-reading path (``get_db_config`` ->
    ``coerce_yaml_bool`` -> psycopg2) while never touching the developer's
    real ``~/.bitwize-music/config.yaml`` — we monkeypatch the module-level
    ``CONFIG_PATH`` that ``get_db_config`` reads.
    """
    import yaml

    from tools.database import connection as db_conn

    config = {
        "artist": {"name": "integration-artist"},
        "database": {"enabled": True, **pg_env()},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(db_conn, "CONFIG_PATH", config_path)
    return config


@pytest.fixture
def plugin_root(monkeypatch):
    """``db_init`` resolves schema.sql / migrations via ``_shared.PLUGIN_ROOT``.

    In-process the server sets this before handlers run; the unit suite never
    exercised db_init, so we set it explicitly here.
    """
    from handlers import _shared

    monkeypatch.setattr(_shared, "PLUGIN_ROOT", REPO_ROOT)
    return REPO_ROOT


@pytest.fixture
def pg_direct():
    """A direct psycopg2 connection (autocommit) for seeding + assertions.

    Independent of the product code path so a product bug can't hide behind
    the test's own setup/verification.
    """
    import psycopg2

    env = pg_env()
    conn = psycopg2.connect(
        host=env["host"],
        port=env["port"],
        dbname=env["name"],
        user=env["user"],
        password=env["password"],
        connect_timeout=5,
    )
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def album_slug(pg_direct):
    """A dedicated album slug for the tweet lifecycle test.

    Cascade-deletes the album (and its tweets/tracks) on teardown so reruns are
    idempotent. Best-effort: the table always exists by teardown time because
    the test runs ``db_init`` first.
    """
    slug = "zzz-integration-album"
    yield slug
    # teardown is best-effort cleanup
    with contextlib.suppress(Exception), pg_direct.cursor() as cur:
        cur.execute("DELETE FROM albums WHERE slug = %s", (slug,))


# ---------------------------------------------------------------------------
# SeaweedFS / S3 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cloud_config():
    """A cloud config dict pointing the ``s3`` provider at SeaweedFS via the
    generic ``cloud.s3.endpoint_url`` support.

    This is the exact shape ``upload_to_cloud`` reads, so the test drives the
    real config -> ``get_s3_client`` / ``get_bucket_name`` construction path.
    """
    return {
        "artist": {"name": "integration-artist"},
        "cloud": {
            "enabled": True,
            "provider": "s3",
            "s3": {
                "endpoint_url": os.getenv("S3_ENDPOINT_URL", "http://localhost:8333"),
                "region": os.getenv("S3_REGION", "us-east-1"),
                "access_key_id": os.getenv("S3_ACCESS_KEY_ID", "bitwizekey"),
                "secret_access_key": os.getenv("S3_SECRET_ACCESS_KEY", "bitwizesecret"),
                "bucket": os.getenv("S3_BUCKET", "bitwize-integration"),
            },
        },
    }


@pytest.fixture
def s3_client(cloud_config):
    """The S3 client built by the PRODUCT's ``get_s3_client`` — this exercises
    the new generic-endpoint construction path (path-style + checksums), not a
    hand-built client.
    """
    from tools.cloud import upload_to_cloud

    return upload_to_cloud.get_s3_client(cloud_config)


@pytest.fixture
def s3_bucket(s3_client, cloud_config):
    """Bucket name via the product's ``get_bucket_name``; create it, then empty
    + remove it on teardown."""
    from botocore.exceptions import ClientError

    from tools.cloud import upload_to_cloud

    bucket = upload_to_cloud.get_bucket_name(cloud_config)
    with contextlib.suppress(ClientError):  # already exists — fine
        s3_client.create_bucket(Bucket=bucket)
    yield bucket
    with contextlib.suppress(ClientError):  # best-effort cleanup
        resp = s3_client.list_objects_v2(Bucket=bucket)
        for obj in resp.get("Contents", []):
            s3_client.delete_object(Bucket=bucket, Key=obj["Key"])
        s3_client.delete_bucket(Bucket=bucket)
