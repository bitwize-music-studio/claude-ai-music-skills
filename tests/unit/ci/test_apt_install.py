#!/usr/bin/env python3
"""Tests for .github/scripts/apt-install.sh, the CI apt fallback.

The script switches apt to archive.ubuntu.com when the runner's mirror fails
or stalls. It runs here for real, against a temporary /etc/apt (APT_ETC) and
stand-ins for sudo, timeout and apt-get on PATH.

The script runs only on Linux runners and relies on GNU sed and bash 4, so
these tests run on Linux only.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT = PROJECT_ROOT / ".github" / "scripts" / "apt-install.sh"

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(sys.platform != "linux", reason="the script runs on Linux runners only"),
]

AZURE = "http://azure.archive.ubuntu.com/ubuntu/"
INSTALL = "install -y --no-install-recommends ffmpeg"

SUDO = '#!/usr/bin/env bash\nexec "$@"\n'
# timeout --kill-after=30 <limit> CMD...: run CMD without a limit.
TIMEOUT = '#!/usr/bin/env bash\nwhile [[ "$1" == --* ]]; do shift; done\nshift\nexec "$@"\n'
# `update` fails while any file under $APT_ETC still names the runner's mirror.
APT_GET_MIRROR_DOWN = (
    "#!/usr/bin/env bash\n"
    'echo "$*" >> "$APT_LOG"\n'
    'if [[ " $* " == *" update "* ]] && grep -rqIF azure.archive.ubuntu.com "$APT_ETC"; then exit 100; fi\n'
    "exit 0\n"
)
# `update` fails the first time only, whatever the sources say.
APT_GET_FAILS_ONCE = (
    "#!/usr/bin/env bash\n"
    'echo "$*" >> "$APT_LOG"\n'
    'if [[ " $* " == *" update "* ]] && [ ! -e "$APT_LOG.failed" ]; then touch "$APT_LOG.failed"; exit 100; fi\n'
    "exit 0\n"
)


@pytest.fixture
def run_script(tmp_path):
    """Run the script against a fresh /etc/apt holding *files*."""
    def run(files: dict[str, str], apt_get: str = APT_GET_MIRROR_DOWN):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        for name, body in (("sudo", SUDO), ("timeout", TIMEOUT), ("apt-get", apt_get)):
            stub = bin_dir / name
            stub.write_text(body, encoding="utf-8")
            stub.chmod(0o755)
        etc = tmp_path / "etc" / "apt"
        (etc / "sources.list.d").mkdir(parents=True, exist_ok=True)
        for rel, text in files.items():
            (etc / rel).write_text(text, encoding="utf-8")
        log = tmp_path / "apt-get.log"
        env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                   APT_ETC=str(etc), APT_LOG=str(log), APT_FETCH_TIMEOUT="5", APT_OPTS="")
        result = subprocess.run(["bash", str(SCRIPT), "--no-install-recommends", "ffmpeg"],
                                capture_output=True, text=True, env=env, timeout=60, check=False)
        calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return result, etc, calls
    return run


def test_the_mirror_list_of_the_ubuntu_26_04_images_is_switched(run_script):
    """26.04 images name the mirror in apt-mirrors.txt, reached through mirror+file:."""
    result, etc, calls = run_script({
        "apt-mirrors.txt": f"{AZURE}\tpriority:1\n",
        "sources.list.d/ubuntu.sources": "Types: deb\nURIs: mirror+file:/etc/apt/apt-mirrors.txt\n",
    })
    assert result.returncode == 0, result.stdout + result.stderr
    mirrors = (etc / "apt-mirrors.txt").read_text(encoding="utf-8")
    assert mirrors == "http://archive.ubuntu.com/ubuntu/\tpriority:1\n"
    assert "apt-mirrors.txt" in result.stdout
    assert calls[-1] == INSTALL


def test_a_source_that_names_the_mirror_is_switched(run_script):
    """The layout of the older images: the mirror is in the sources themselves."""
    result, etc, calls = run_script({"sources.list": f"deb {AZURE} noble main\n"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert (etc / "sources.list").read_text(encoding="utf-8") == "deb http://archive.ubuntu.com/ubuntu/ noble main\n"
    assert calls[-1] == INSTALL


def test_when_nothing_names_the_mirror_it_says_so_and_retries(run_script):
    result, _etc, calls = run_script(
        {"sources.list": "deb http://example.invalid/ubuntu noble main\n"}, apt_get=APT_GET_FAILS_ONCE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No apt source or mirror list names azure.archive.ubuntu.com" in result.stdout
    assert calls.count("update") == 2 and calls[-1] == INSTALL
