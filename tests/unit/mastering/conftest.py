"""Mastering-test fixtures.

Mirrors `tests/unit/mixing/conftest.py` (#553): every test in this package
is about what the shipped mastering presets do, or about how a user
override changes them, so none of them should be reading the overrides
the developer running the suite happens to have installed at
`~/.bitwize-music/overrides/mastering-presets.yaml` (#556). The autouse
fixture below resolves presets from the shipped files; tests that want an
override install one explicitly (which runs later and therefore wins).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.unit.mixing._presets import shipped_presets_only


@pytest.fixture(autouse=True)
def _hermetic_mastering_presets(monkeypatch: Any) -> None:
    shipped_presets_only(monkeypatch)
