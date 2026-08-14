"""Every hard-pinned runtime dependency must actually import on this platform.

Deliberately a hard assertion, not ``pytest.importorskip``. These are exact pins
in ``requirements.txt`` that CI installs on all three OS legs, so an ImportError
means a real problem — most likely a wheel that is unavailable or broken for
this platform/Python combination. ``importorskip`` would convert exactly that
regression into a green skip, which is how a dependency can silently stop
working on one OS while the suite stays green.

That matters most for the legs that exist to catch it: the nightly 3.12/3.13
runs prove wheel availability ahead of adopting a new floor or ceiling, and
several of these packages ship platform-specific binary wheels.

This is an availability check only — it says nothing about whether the library
works, just that the pinned version is installed and importable. For playwright
specifically, the browser itself is a separate concern (browsers are downloaded
out-of-band, not via pip); that is covered by the gated
``tests/integration/test_playwright_browser.py`` smoke test.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# (import name, distribution name as pinned in requirements.txt)
# Import name and distribution name are tracked separately because they are not
# required to match, and asserting on the wrong one gives a confusing failure.
PINNED_RUNTIME_DEPS = [
    ("playwright", "playwright"),   # document-hunter (skill-driven, no product code)
    ("pypdf", "pypdf"),             # songbook creation
    ("reportlab", "reportlab"),     # songbook creation
    ("mutagen", "mutagen"),         # mastering metadata
    ("noisereduce", "noisereduce"), # mixing polish
]


@pytest.mark.unit
@pytest.mark.parametrize(("module_name", "dist_name"), PINNED_RUNTIME_DEPS)
def test_pinned_dependency_imports(module_name: str, dist_name: str) -> None:
    """A pinned dependency that cannot be imported is a platform regression."""
    try:
        importlib.import_module(module_name)
    except ImportError as exc:  # pragma: no cover - only on a real regression
        pytest.fail(
            f"{dist_name} is pinned in requirements.txt but `import {module_name}` "
            f"failed on this platform: {exc}\n"
            "This usually means no wheel is available for this OS/Python "
            "combination. Do not silence it with importorskip — that would hide "
            "the regression this test exists to surface."
        )


# Tools whose output IS the pass/fail verdict of a CI gate. Unlike the test
# runner, these change their verdict on unchanged code — a new ruff rule or a
# widened mypy check reddens a build nobody touched, and a re-run of an old
# green commit no longer reproduces. Exact pins move those upgrades into a
# reviewable Dependabot PR with CI attached instead of landing silently
# mid-week (#532).
#
# Deliberately NOT covering pytest/pytest-cov/pytest-xdist/pyyaml/types-PyYAML:
# they change *what runs*, not *what counts as a violation*, so they stay on
# `>=` to keep Dependabot volume proportionate.
GATE_TOOLS = ["ruff", "mypy", "bandit"]


def _requirement_line(requirements_text: str, package: str) -> str | None:
    """Return the requirement line for *package*, ignoring comments."""
    pattern = re.compile(rf"^{re.escape(package)}\s*([<>=!~].*)$", re.MULTILINE)
    match = pattern.search(requirements_text)
    return match.group(1).strip() if match else None


@pytest.mark.unit
@pytest.mark.parametrize("package", GATE_TOOLS)
def test_gate_tool_is_exactly_pinned(package: str, project_root: Path) -> None:
    """ruff/mypy/bandit must use `==`, so a CI verdict is reproducible."""
    text = (project_root / "requirements-test.txt").read_text(encoding="utf-8")
    spec = _requirement_line(text, package)

    assert spec is not None, (
        f"{package} not found in requirements-test.txt — if it was removed, drop "
        f"it from GATE_TOOLS too."
    )
    assert spec.startswith("=="), (
        f"{package} is specified as `{package}{spec}` in requirements-test.txt. "
        f"Gate-deciding tools must be pinned exactly (`{package}==X.Y.Z`): with "
        f"`>=`, CI resolves whatever is newest at that moment, so a release by "
        f"{package} can fail a commit nobody touched and an old green build "
        f"stops reproducing. See #532."
    )


# --- mcp 2.x guardrails (#537) ------------------------------------------------
#
# mcp 2.0.0 restructured `mcp.server.fastmcp` (FastMCP) into `mcp.server.mcpserver`
# (MCPServer) and shipped no compat shim, so `server.py`'s single `from mcp` import
# raises and the server exits 1 at import time. Three separate things go wrong on a
# 2.x install, and each gets a guard here.


@pytest.mark.unit
def test_pinned_mcp_exposes_fastmcp() -> None:
    """The installed mcp must expose the module `server.py` imports.

    Bare `import mcp` succeeds on 2.x — the removed module is the submodule — so
    this asserts the submodule specifically.

    Deliberately a subprocess rather than `importlib.import_module`. The 24 test
    modules that exercise `server.py` install a fake `mcp.server.fastmcp` into
    ``sys.modules`` when the real one is absent, and pytest shares one process,
    so an in-process import would find that stub and pass on exactly the install
    this test exists to catch. A clean interpreter is also precisely what the
    documented readiness probe runs.
    """
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
        [sys.executable, "-c", "import mcp.server.fastmcp"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:  # pragma: no cover - only on a real regression
        pytest.fail(
            f"`{sys.executable} -c 'import mcp.server.fastmcp'` exited "
            f"{result.returncode}:\n{result.stderr.strip()}\n\n"
            "mcp 2.x removed this module (it is now mcp.server.mcpserver.MCPServer) "
            "with no compat shim, so servers/bitwize-music-server/server.py cannot "
            "boot. requirements.txt must stay on the 1.x line until that migration "
            "lands. See #537."
        )


# Files that tell a *user* how to install mcp. requirements.txt is excluded (it
# carries an exact `==` pin, which needs no ceiling) and so is CHANGELOG.md, whose
# `>=1.2.0` is a historical record of what the server required when the MCP server
# shipped — rewriting history to satisfy a test would be worse than the drift it
# prevents.
MCP_INSTALL_ADVICE_FILES = [
    "servers/bitwize-music-server/server.py",
    "servers/bitwize-music-server/README.md",
]

_MCP_CLI_SPEC = re.compile(r"mcp\[cli\]([<>=!~][^\"'\s`]*)")


@pytest.mark.unit
@pytest.mark.parametrize("relative_path", MCP_INSTALL_ADVICE_FILES)
def test_documented_mcp_install_is_capped_below_2(
    relative_path: str, project_root: Path
) -> None:
    """Install advice must exclude 2.x, or it tells users to install a broken server.

    Two of these strings are printed by the ImportError handler itself, so an
    unbounded `>=` sends someone whose server will not start off to install the
    exact version that will not start — and back to the same message. A setup
    loop, shown precisely when the user is already stuck.
    """
    text = (project_root / relative_path).read_text(encoding="utf-8")
    specs = _MCP_CLI_SPEC.findall(text)

    assert specs, (
        f"No `mcp[cli]` requirement found in {relative_path} — if the install "
        f"advice moved, update MCP_INSTALL_ADVICE_FILES."
    )
    for spec in specs:
        assert spec.startswith("==") or "<2" in spec, (
            f"{relative_path} advises `mcp[cli]{spec}`, which resolves to 2.x "
            f"today. mcp 2.x cannot run this server (#537) — bound it, e.g. "
            f"`mcp[cli]>=1.28.1,<2`."
        )


# Every place that tells a session (or a user) how to check the SDK is healthy.
# This is the failure that actually reached people: bare `import mcp` succeeds on
# 2.x, so the gate CLAUDE.md says must halt the session reported ready on an
# install where the server was already dead.
PROBE_FILES = [
    "CLAUDE.md",
    "skills/session-start/SKILL.md",
    "skills/setup/SKILL.md",
    "reference/workflows/error-recovery.md",
]

# `python3 -c "import mcp"` — the bare probe. Matches only when the import ends
# right there, so `-c "import mcp.server.fastmcp"` and prose mentions of
# `import mcp` in backticks are both left alone.
_BARE_MCP_PROBE = re.compile(r"""-c\s+(["'])import mcp\1""")


@pytest.mark.unit
@pytest.mark.parametrize("relative_path", PROBE_FILES)
def test_readiness_probe_checks_the_module_the_server_imports(
    relative_path: str, project_root: Path
) -> None:
    """A readiness probe must import what `server.py` imports, not just `mcp`."""
    text = (project_root / relative_path).read_text(encoding="utf-8")

    assert "import mcp.server.fastmcp" in text, (
        f"{relative_path} no longer probes `mcp.server.fastmcp` — if the check "
        f"moved, update PROBE_FILES."
    )
    assert not _BARE_MCP_PROBE.search(text), (
        f"{relative_path} probes readiness with a bare `-c \"import mcp\"`. That "
        f"succeeds on mcp 2.x, which dropped `mcp.server.fastmcp` — so the probe "
        f"reports healthy on an install the server cannot boot on. Import the "
        f"submodule instead. See #537."
    )


@pytest.mark.unit
def test_dependabot_ignores_mcp_majors(project_root: Path) -> None:
    """Without this ignore, one un-mergeable major takes the whole group PR down.

    `pip-all` groups every dependency with `patterns: ["*"]`, so each weekly PR
    that picks up mcp 2.x fails Tests and MCP Server Boot on all three runners
    and holds every unrelated bump in the group hostage with it.
    """
    config = yaml.safe_load(
        (project_root / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    pip_updates = [u for u in config["updates"] if u["package-ecosystem"] == "pip"]
    assert pip_updates, "No pip ecosystem entry in .github/dependabot.yml"

    ignored = [
        entry
        for update in pip_updates
        for entry in update.get("ignore", [])
        if entry.get("dependency-name") == "mcp"
    ]
    assert ignored, (
        "`.github/dependabot.yml` no longer ignores mcp major updates. mcp 2.x "
        "cannot boot this server (#537), and because pip-all groups everything, "
        "the resulting PR fails 6 jobs and blocks every other bump in the group. "
        "Remove this only together with the mcp 2.0 migration."
    )
    assert any(
        "version-update:semver-major" in entry.get("update-types", [])
        or any(v.startswith(">=2") for v in entry.get("versions", []))
        for entry in ignored
    ), (
        "The mcp ignore entry no longer blocks the 2.x major. See #537."
    )
