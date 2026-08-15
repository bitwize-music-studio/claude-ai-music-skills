#!/usr/bin/env python3
"""Dump every registered MCP tool's wire schema as canonical JSON.

Used two ways:

  * by ``test_tool_schema_parity.py``, which runs this in a clean subprocess and
    diffs the output against the committed golden file;
  * by a maintainer regenerating that golden after an intentional tool change::

        python3 tests/unit/state/_dump_tool_schemas.py > tests/fixtures/tool_schemas.json

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


def collect() -> list[dict[str, object]]:
    """Return each tool's name and generated schemas, sorted by name."""
    import server

    tools = asyncio.run(server.mcp.list_tools())
    dumped = [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]

    # `description` is deliberately excluded. It comes from the handler docstring,
    # so including it would turn every prose edit into a golden-file regeneration —
    # real friction for contributors, and not what this file guards. The generated
    # schemas are the SDK-dependent part (#537) and the part the error boundary
    # could silently change (#443).
    return sorted(
        (
            {
                "name": t["name"],
                "inputSchema": t.get("inputSchema"),
                "outputSchema": t.get("outputSchema"),
            }
            for t in dumped
        ),
        key=lambda t: str(t["name"]),
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _isolate_state_cache(Path(tmp))
        json.dump(collect(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
