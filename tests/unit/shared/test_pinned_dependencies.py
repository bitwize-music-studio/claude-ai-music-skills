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
