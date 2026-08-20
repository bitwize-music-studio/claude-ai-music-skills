"""Mixing-test fixtures.

Every test in this package is about what the shipped mix presets do, or
about how a user override changes them — so none of them should be
reading the overrides the developer running the suite happens to have
installed (#553). The autouse fixture below resolves presets from the
shipped files; tests that want an override call `install_override`,
which runs later and therefore wins.
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
def _hermetic_mix_presets(monkeypatch: Any) -> None:
    shipped_presets_only(monkeypatch)
