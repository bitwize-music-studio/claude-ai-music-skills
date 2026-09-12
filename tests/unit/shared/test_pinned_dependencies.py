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


# --- mcp SDK-line guardrails (#537) -------------------------------------------
#
# mcp 2.0.0 restructured `mcp.server.fastmcp` (FastMCP) into `mcp.server.mcpserver`
# (MCPServer) and shipped no compat shim. `server.py` imports whichever is present,
# preferring 2.x, so BOTH SDK lines boot — that is what keeps a plugin upgrade from
# breaking users whose hand-managed venv still has 1.x. These guards check the
# install is on one of the two supported lines, not on either one specifically.

# The two module paths `server.py` accepts, in the order it tries them.
SUPPORTED_MCP_SERVER_MODULES = ["mcp.server.mcpserver", "mcp.server.fastmcp"]


@pytest.mark.unit
def test_pinned_mcp_exposes_a_supported_server_module() -> None:
    """The installed mcp must expose one of the modules `server.py` imports.

    Bare `import mcp` succeeds on both lines — what moved is the submodule — so
    this asserts the submodules specifically.

    Deliberately a subprocess rather than `importlib.import_module`. The 24 test
    modules that exercise `server.py` install a fake `mcp.server.fastmcp` into
    ``sys.modules`` when the real one is absent, and pytest shares one process,
    so an in-process import would find that stub and pass on exactly the install
    this test exists to catch. A clean interpreter is also precisely what the
    documented readiness probe runs.
    """
    failures = []
    for module in SUPPORTED_MCP_SERVER_MODULES:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode == 0:
            return
        failures.append(f"  {module}: exit {result.returncode}\n{result.stderr.strip()}")

    pytest.fail(  # pragma: no cover - only on a real regression
        f"No supported MCP server module is importable under {sys.executable}:\n"
        + "\n".join(failures)
        + "\n\nservers/bitwize-music-server/server.py needs one of "
        f"{SUPPORTED_MCP_SERVER_MODULES} and exits 1 without them. Install "
        '`mcp[cli]>=1.28.1,<3`. See #537.'
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
def test_documented_mcp_install_is_capped_below_3(
    relative_path: str, project_root: Path
) -> None:
    """Install advice must carry a major-version ceiling.

    Two of these strings are printed by the ImportError handler itself, so an
    unbounded `>=` sends someone whose server will not start off to install
    whatever major ships next — which, on the evidence of 2.0.0, may well
    restructure the entry point again and land them back at the same message.
    A setup loop, shown precisely when the user is already stuck. 3.x is
    unreleased and unverified, so it stays outside the advice until someone
    checks it the way #537 checked 2.x.
    """
    text = (project_root / relative_path).read_text(encoding="utf-8")
    specs = _MCP_CLI_SPEC.findall(text)

    assert specs, (
        f"No `mcp[cli]` requirement found in {relative_path} — if the install "
        f"advice moved, update MCP_INSTALL_ADVICE_FILES."
    )
    for spec in specs:
        assert spec.startswith("==") or "<3" in spec, (
            f"{relative_path} advises `mcp[cli]{spec}`, which is unbounded above "
            f"the supported majors. server.py accepts 1.x and 2.x only (#537) — "
            f"bound it, e.g. `mcp[cli]>=1.28.1,<3`."
        )


# Every place that tells a session (or a user) how to check the SDK is healthy.
# This is the failure that actually reached people: bare `import mcp` succeeds
# whichever line is installed — and even when neither server module is present —
# so the gate CLAUDE.md says must halt the session reported ready on an install
# where the server was already dead.
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
def test_readiness_probe_checks_the_modules_the_server_imports(
    relative_path: str, project_root: Path
) -> None:
    """A readiness probe must import what `server.py` imports, not just `mcp`.

    Both module paths, not either one: `server.py` accepts 1.x and 2.x, so a probe
    naming only one reports a perfectly working install on the other line as broken.
    """
    text = (project_root / relative_path).read_text(encoding="utf-8")

    for module in SUPPORTED_MCP_SERVER_MODULES:
        assert f"import {module}" in text, (
            f"{relative_path} does not probe `{module}`. server.py boots on either "
            f"SDK line, so a probe naming only one calls a working install broken. "
            f"If the check moved, update PROBE_FILES. See #537."
        )
    assert not _BARE_MCP_PROBE.search(text), (
        f"{relative_path} probes readiness with a bare `-c \"import mcp\"`. That "
        f"succeeds even when neither `mcp.server.mcpserver` nor `mcp.server.fastmcp` "
        f"is present — so the probe reports healthy on an install the server cannot "
        f"boot on. Import the submodules instead. See #537."
    )


# `test_dependabot_ignores_mcp_majors` lived here and has been removed. It existed
# to keep an un-mergeable mcp major out of the `pip-all` group PR, and its own
# docstring set the condition for taking it out: "Remove this only together with
# the mcp 2.0 migration." That migration has landed — server.py boots on 1.x and
# 2.x alike — so the ignore is gone from .github/dependabot.yml and mcp majors flow
# again. A future major that breaks the entry point is caught by
# `test_pinned_mcp_exposes_a_supported_server_module` plus the boot jobs, which fail
# on the actual breakage rather than pre-emptively blocking every major (#537).
