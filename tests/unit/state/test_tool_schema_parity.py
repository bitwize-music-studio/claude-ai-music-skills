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

Tool *descriptions* are guarded differently — see the description tests at the
bottom of this file for why they are not in the golden.

Regenerate after an intentional tool change (new tool, renamed or retyped
parameter) and review the diff as part of the change::

    python3 tests/unit/state/_dump_tool_schemas.py --golden > tests/fixtures/tool_schemas.json
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DUMP_SCRIPT = PROJECT_ROOT / "tests" / "unit" / "state" / "_dump_tool_schemas.py"
GOLDEN = PROJECT_ROOT / "tests" / "fixtures" / "tool_schemas.json"

REGENERATE = (
    f"python3 {DUMP_SCRIPT.relative_to(PROJECT_ROOT)} --golden "
    f"> {GOLDEN.relative_to(PROJECT_ROOT)}"
)

# Fields the golden locks — kept in sync with _dump_tool_schemas.GOLDEN_FIELDS.
GOLDEN_FIELDS = ("name", "inputSchema", "outputSchema")


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
    live = [
        {field: tool.get(field) for field in GOLDEN_FIELDS}
        for tool in _dump_live_schemas()
    ]
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


# --- tool descriptions --------------------------------------------------------
#
# Descriptions are the highest-leverage field the server publishes: 81 of the 91
# carry their handler's full `Args:` block, ~50k characters in total, and that
# prose is what the model reads when choosing between 91 tools. A bad input schema
# fails loudly at call time; a degraded description just causes quiet wrong-tool
# selection that reads as the model being dim.
#
# They are still kept OUT of the golden file, because the two ways a description
# can change are not symmetric:
#
#   * A human edits a docstring — already visible in that file's own diff. Locking
#     it in the golden adds no information and costs a regeneration every few days.
#   * The SDK changes how it *derives* descriptions — starts at the summary line,
#     strips `Args:`, truncates, dedents differently. That silently rewrites all 91
#     with no diff anywhere in the repo, and nothing else in the suite would see it.
#
# Only the second is worth a guard, and it does not need the prose locked — just
# its shape asserted. That is what these tests do: SDK-drift coverage with zero
# churn on ordinary docstring edits.

# Parameterised tools whose docstring legitimately has no `Args:` block. Keep this
# list short — an entry is a tool whose parameters are undocumented to the model.
TOOLS_WITHOUT_ARGS_BLOCK = {"master_album"}


@pytest.mark.unit
def test_every_tool_has_a_description() -> None:
    """An empty description leaves the model picking a tool by name alone."""
    live = _dump_live_schemas()

    missing = [t["name"] for t in live if not (t.get("description") or "").strip()]
    assert not missing, (
        f"{len(missing)} tool(s) publish no description: {missing[:10]}. Either the "
        f"handler lost its docstring, or the SDK stopped deriving descriptions from "
        f"one — check `mcp.server.*`'s tool registration before assuming the former."
    )


@pytest.mark.unit
def test_parameterised_tools_document_their_arguments() -> None:
    """A tool's parameters must still reach the model, not just its summary line.

    This is the SDK-drift canary. If a future mcp version publishes only the
    docstring's first line — a plausible and entirely silent change — every
    parameterised tool keeps working while the model loses the text telling it what
    the parameters mean. Nothing else in the suite notices.
    """
    live = _dump_live_schemas()

    undocumented = sorted(
        t["name"]
        for t in live
        if (t.get("inputSchema") or {}).get("properties")
        and t["name"] not in TOOLS_WITHOUT_ARGS_BLOCK
        and "Args:" not in (t.get("description") or "")
    )
    assert not undocumented, (
        f"{len(undocumented)} parameterised tool(s) publish no `Args:` block: "
        f"{undocumented[:10]}.\n\nIf many tools regressed at once, suspect the SDK's "
        f"docstring handling rather than the handlers — that is the failure this "
        f"test exists for. If a single new tool is listed, give it an `Args:` block "
        f"or add it to TOOLS_WITHOUT_ARGS_BLOCK with a reason."
    )


@pytest.mark.unit
def test_descriptions_are_not_truncated() -> None:
    """Catch an SDK that starts capping description length.

    A cap would not empty any description, so the two tests above would both pass
    while the model silently lost the tail of every long one.
    """
    live = _dump_live_schemas()
    descriptions = {t["name"]: (t.get("description") or "") for t in live}

    elided = sorted(n for n, d in descriptions.items() if d.rstrip().endswith(("...", "…")))
    assert not elided, f"description(s) end in an ellipsis, i.e. truncated: {elided[:10]}"

    # The longest description is ~2.3k characters. If the maximum collapses to a
    # round-ish number, something upstream is capping it.
    longest = max(descriptions.values(), key=len)
    assert len(longest) > 1000, (
        f"the longest tool description is only {len(longest)} characters. These run "
        f"to ~2.3k, so a ceiling this low means something upstream is truncating them."
    )
