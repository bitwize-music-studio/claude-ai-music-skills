#!/usr/bin/env python3
"""Dump every registered MCP tool's wire schema as canonical JSON.

Used two ways:

  * by ``test_tool_schema_parity.py``, which runs this in a clean subprocess and
    diffs the output against the committed golden file;
  * by a maintainer regenerating that golden after an intentional tool change::

        python3 tests/unit/state/_dump_tool_schemas.py --golden > tests/fixtures/tool_schemas.json

Why a subprocess rather than an in-process import: the ~24 test modules that
exercise ``server.py`` install a fake ``mcp.server.fastmcp`` into ``sys.modules``
when no SDK is present, and pytest shares one process. An in-process dump could
pick up that stub — which registers tools but generates no schemas — and compare
nothing against nothing. A clean interpreter always measures the real SDK.

Output is the ``tools/list`` wire form (``by_alias=True``), so it is identical on
mcp 1.x (FastMCP) and 2.x (MCPServer) even though the two use different Python
field names internally — ``inputSchema`` vs ``input_schema``. That equivalence is
the property the parity test exists to hold (#537).
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"

for _path in (str(SERVER_DIR), str(PROJECT_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _isolate_state_cache(tmp: Path) -> None:
    """Point the indexer at a throwaway cache before ``server`` is imported.

    Importing ``server`` is read-only with respect to state, but the autouse
    conftest fixture that normally guarantees that does not reach a subprocess.
    Redirect explicitly rather than rely on the import staying read-only.
    """
    import tools.state.indexer as indexer

    indexer.CACHE_DIR = tmp
    indexer.STATE_FILE = tmp / "state.json"
    indexer.LOCK_FILE = tmp / "state.lock"


# The fields the committed golden file locks. `description` is deliberately NOT
# among them: it comes from the handler docstring, so locking it would turn every
# prose edit into a regeneration — roughly one every five days at this repo's rate
# of handler churn. A golden that moves weekly stops being read, which would cost
# the schema half of this file its whole point. Descriptions are still *dumped*,
# and guarded structurally instead — see test_tool_schema_parity.py.
GOLDEN_FIELDS = ("name", "inputSchema", "outputSchema")


def golden_projection(tool: dict[str, object]) -> dict[str, object]:
    """Narrow a dumped tool to the fields the golden file locks."""
    return {field: tool.get(field) for field in GOLDEN_FIELDS}


def collect() -> list[dict[str, object]]:
    """Return each tool's description and generated schemas, sorted by name."""
    import server

    tools = asyncio.run(server.mcp.list_tools())
    dumped = [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]

    return sorted(
        (
            {
                "name": t["name"],
                "description": t.get("description") or "",
                "inputSchema": t.get("inputSchema"),
                "outputSchema": t.get("outputSchema"),
            }
            for t in dumped
        ),
        key=lambda t: str(t["name"]),
    )


def main() -> None:
    """Dump all tools; ``--golden`` narrows output to the golden file's fields."""
    golden_only = "--golden" in sys.argv[1:]
    with tempfile.TemporaryDirectory() as tmp:
        _isolate_state_cache(Path(tmp))
        tools = collect()
        if golden_only:
            tools = [golden_projection(t) for t in tools]
        json.dump(tools, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
