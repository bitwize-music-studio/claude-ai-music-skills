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

# For tests that assert specific permission bits (e.g. 0o700) rather than
# denial behavior: Windows never enforces POSIX modes (stat reports 0o777),
# but root still *sets* them correctly — so this is a Windows-only skip,
# distinct from requires_chmod_denial.
requires_posix_permissions = pytest.mark.skipif(
    IS_WINDOWS,
    reason="POSIX permission bits are not enforced on Windows",
)
