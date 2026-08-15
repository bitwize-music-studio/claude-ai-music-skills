#!/usr/bin/env python3
"""Lock the generated MCP tool schemas against a committed golden file.

Two regressions this catches, both of which are invisible to every other test in
the suite because they change what *clients* see, not what handlers return:

1. **SDK drift (#537).** ``server.py`` boots on mcp 1.x (``FastMCP``) or 2.x
   (``MCPServer``). Both build a tool's input schema from the handler signature
   via ``inspect.signature(fn, eval_str=True)``, so the wire schemas are identical
   — verified across 1.28.1 and 2.0.0 when the compat import landed. The golden
   file is what keeps that true: CI on one line and a developer on the other must
   both reproduce it byte for byte.

2. **Error-boundary drift (#443).** ``_shared.install_error_boundary`` monkey-patches
   ``mcp.tool`` to wrap all 91 handlers. It relies on ``functools.wraps`` setting
   ``__wrapped__``, which ``inspect.signature`` follows, so the wrapper stays
   invisible to schema generation. Drop the ``@functools.wraps`` and every tool
   silently collapses to ``(*args, **kwargs)`` — handlers keep working, tests keep
   passing, and clients lose every parameter. That failure mode is exactly what a
   golden file catches and nothing else does.

Regenerate after an intentional tool change (new tool, renamed or retyped
parameter) and review the diff as part of the change::

    python3 tests/unit/state/_dump_tool_schemas.py > tests/fixtures/tool_schemas.json
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DUMP_SCRIPT = PROJECT_ROOT / "tests" / "unit" / "state" / "_dump_tool_schemas.py"
GOLDEN = PROJECT_ROOT / "tests" / "fixtures" / "tool_schemas.json"

REGENERATE = f"python3 {DUMP_SCRIPT.relative_to(PROJECT_ROOT)} > {GOLDEN.relative_to(PROJECT_ROOT)}"


def _dump_live_schemas() -> list[dict]:
    """Run the dump script in a clean interpreter and parse its JSON.

    Subprocess, not import: sibling test modules stub ``mcp.server.fastmcp`` into
    ``sys.modules`` when no SDK is installed, and pytest shares one process. An
    in-process dump could measure that stub instead of the real SDK — passing on
    precisely the install this test exists to check.
    """
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
        [sys.executable, str(DUMP_SCRIPT)],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "No module named 'mcp'" in stderr or "ModuleNotFoundError: No module named 'mcp" in stderr:
            pytest.skip("no real mcp SDK installed — schema parity needs one")
        pytest.fail(
            f"Could not dump tool schemas (exit {result.returncode}):\n{stderr}"
        )
    return json.loads(result.stdout)


@pytest.mark.unit
def test_tool_schemas_match_golden() -> None:
    """Every registered tool's generated schemas match the committed golden."""
    live = _dump_live_schemas()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    live_names = [t["name"] for t in live]
    golden_names = [t["name"] for t in golden]

    added = sorted(set(live_names) - set(golden_names))
    removed = sorted(set(golden_names) - set(live_names))
    assert not added and not removed, (
        f"Registered tools changed — added: {added or 'none'}, "
        f"removed: {removed or 'none'}.\nIf intentional, regenerate:\n  {REGENERATE}"
    )

    by_name = {t["name"]: t for t in golden}
    drifted = [t["name"] for t in live if t != by_name[t["name"]]]
    if drifted:
        first = drifted[0]
        pytest.fail(
            f"{len(drifted)} tool(s) have drifted schemas: {drifted[:10]}\n\n"
            f"--- golden: {first}\n{json.dumps(by_name[first], indent=2, sort_keys=True)}\n\n"
            f"--- live: {first}\n"
            f"{json.dumps(next(t for t in live if t['name'] == first), indent=2, sort_keys=True)}\n\n"
            f"An unintended change here means clients see different tool parameters "
            f"than they did before — check the error boundary still uses "
            f"@functools.wraps (#443) before assuming the SDK is at fault (#537).\n"
            f"If intentional, regenerate:\n  {REGENERATE}"
        )


@pytest.mark.unit
def test_golden_covers_every_tool_with_a_schema() -> None:
    """Guard the guard: a golden of empty schemas would pass the test above.

    If ``install_error_boundary`` ever erased signatures *and* someone regenerated
    the golden without reading the diff, every entry would go schema-less and the
    parity test would happily compare nothing to nothing. Assert the golden is
    substantive.
    """
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert len(golden) > 50, f"golden has only {len(golden)} tools — suspiciously few"

    schemaless = [t["name"] for t in golden if not t.get("inputSchema")]
    assert not schemaless, (
        f"{len(schemaless)} golden entries have no inputSchema: {schemaless[:10]}. "
        f"Every tool generates one from its handler signature, so an empty schema "
        f"means signature introspection broke — likely a lost @functools.wraps in "
        f"handlers/_shared.py's error boundary (#443)."
    )

    no_params = [
        t["name"]
        for t in golden
        if isinstance(t.get("inputSchema"), dict)
        and t["inputSchema"].get("type") == "object"
        and not t["inputSchema"].get("properties")
    ]
    # A handful of tools genuinely take no arguments; a *majority* taking none is
    # the collapse signature.
    assert len(no_params) < len(golden) / 2, (
        f"{len(no_params)} of {len(golden)} tools take no parameters. That is the "
        f"shape of collapsed (*args, **kwargs) introspection, not a real API."
    )
