"""Shared platform-conditional test helpers."""

import os
import sys

import pytest

IS_WINDOWS = sys.platform == "win32"

# chmod(0o000) denies access only on POSIX and only when not running as root
# (root bypasses permission bits — see the note in test_indexer.py's chmod tests).
_chmod_denies = not IS_WINDOWS and os.geteuid() != 0

requires_chmod_denial = pytest.mark.skipif(
    not _chmod_denies,
    reason="chmod(0o000) does not deny access on Windows or when running as root",
)
