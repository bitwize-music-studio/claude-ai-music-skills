"""Unit tests for tools/database/connection.py."""

from __future__ import annotations

import pytest


def _write_cfg(tmp_path, enabled_literal: str):
    p = tmp_path / "config.yaml"
    p.write_text(
        "database:\n"
        f"  enabled: {enabled_literal}\n"
        "  host: db.example\n"
        "  port: 5432\n"
        "  name: tweets\n"
        "  user: u\n"
        "  password: p\n",
        encoding="utf-8",
    )
    return p


class TestGetDbConfigBooleanGate:
    """database.enabled honors quoted boolean strings (#388)."""

    def test_quoted_false_disables(self, tmp_path, monkeypatch):
        import tools.database.connection as conn
        monkeypatch.setattr(conn, "CONFIG_PATH", _write_cfg(tmp_path, '"false"'))
        assert conn.get_db_config() is None

    def test_quoted_no_disables(self, tmp_path, monkeypatch):
        import tools.database.connection as conn
        monkeypatch.setattr(conn, "CONFIG_PATH", _write_cfg(tmp_path, '"no"'))
        assert conn.get_db_config() is None

    def test_quoted_true_enables(self, tmp_path, monkeypatch):
        import tools.database.connection as conn
        monkeypatch.setattr(conn, "CONFIG_PATH", _write_cfg(tmp_path, '"true"'))
        result = conn.get_db_config()
        assert result is not None
        assert result["host"] == "db.example"

    def test_unquoted_bools_unchanged(self, tmp_path, monkeypatch):
        import tools.database.connection as conn
        monkeypatch.setattr(conn, "CONFIG_PATH", _write_cfg(tmp_path, "true"))
        assert conn.get_db_config() is not None
        monkeypatch.setattr(conn, "CONFIG_PATH", _write_cfg(tmp_path, "false"))
        assert conn.get_db_config() is None

    def test_garbage_string_disables(self, tmp_path, monkeypatch):
        """Unparseable values fall back to the default (disabled)."""
        import tools.database.connection as conn
        monkeypatch.setattr(conn, "CONFIG_PATH", _write_cfg(tmp_path, '"maybe"'))
        assert conn.get_db_config() is None
