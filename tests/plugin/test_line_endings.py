"""Shell scripts keep LF line endings on every checkout (#628).

bash rejects a carriage return at the end of a line ("set: pipefail\\r:
invalid option name"). A Windows checkout with core.autocrlf adds one, which
broke the nightly WSL2 suite: it checks the repo out on Windows and runs the
tests inside WSL2. .gitattributes pins every shell script to LF.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SHEBANG_RE = re.compile(rb"^#!.*\b(?:ba|z|da)?sh\b")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout


def _in_git_checkout() -> bool:
    try:
        return _git("rev-parse", "--is-inside-work-tree").strip() == "true"
    except (OSError, subprocess.CalledProcessError):
        return False


def _shell_scripts() -> list[str]:
    """Tracked files a POSIX shell runs: *.sh, or a first line naming a shell."""
    scripts = []
    for name in _git("ls-files", "-z").split("\0"):
        if not name:
            continue
        if name.endswith(".sh"):
            scripts.append(name)
            continue
        try:
            with (PROJECT_ROOT / name).open("rb") as handle:
                first = handle.readline(200)
        except OSError:
            continue
        if _SHEBANG_RE.match(first):
            scripts.append(name)
    return scripts


@pytest.mark.skipif(not _in_git_checkout(), reason="needs a git checkout")
def test_every_shell_script_is_checked_out_with_lf():
    scripts = _shell_scripts()
    assert ".github/scripts/apt-install.sh" in scripts
    attributes = _git("check-attr", "eol", "--", *scripts).splitlines()
    not_lf = [line for line in attributes if not line.endswith(": eol: lf")]
    assert not not_lf, "shell scripts without eol=lf in .gitattributes:\n" + "\n".join(not_lf)
