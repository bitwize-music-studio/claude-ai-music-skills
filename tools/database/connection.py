"""PostgreSQL database connection helper for bitwize-music tools."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".bitwize-music" / "config.yaml"


def check_db_deps() -> Optional[str]:
    """Return error message if database deps missing, else None."""
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        return (
            "Missing database dependency: psycopg2. "
            "Install: pip install psycopg2-binary"
        )
    return None


def get_db_config() -> Optional[Dict[str, Any]]:
    """Read database config from ~/.bitwize-music/config.yaml.

    Returns:
        Database config dict with host/port/name/user/password,
        or None if database is not configured or not enabled.
    """
    try:
        import yaml
    except ImportError:
        logger.error("pyyaml not installed")
        return None

    if not CONFIG_PATH.exists():
        return None

    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Cannot read config: %s", e)
        return None

    db_config = config.get("database", {})
    if not db_config or not db_config.get("enabled", False):
        return None

    return db_config


def get_connection(db_config: Dict[str, Any]):
    """Create a psycopg2 connection from config dict.

    Args:
        db_config: Dict with host, port, name, user, password keys.

    Returns:
        psycopg2 connection object.

    Raises:
        ImportError: If psycopg2 is not installed.
        psycopg2.Error: If connection fails.
    """
    import psycopg2
    import psycopg2.extensions

    conn = psycopg2.connect(
        host=db_config.get("host", "localhost"),
        port=db_config.get("port", 5432),
        dbname=db_config.get("name", ""),
        user=db_config.get("user", ""),
        password=db_config.get("password", ""),
    )
    conn.set_client_encoding('UTF8')
    return conn
