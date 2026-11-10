"""The artwork settings are part of the config snapshot in state.json.

``get_config`` reads that snapshot, so the setting has to be in it for a
session to see which generator is chosen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state import indexer  # noqa: E402


class TestConfigSnapshot:
    def test_the_default_is_in_the_snapshot(self):
        section = indexer.build_config_section({"artist": {"name": "a"}})
        assert section["artwork"] == {"generator": "manual", "candidates": 1, "codex_path": ""}

    def test_a_chosen_generator_is_carried_through(self):
        section = indexer.build_config_section({"artwork": {"generator": "codex", "candidates": 2}})
        assert section["artwork"]["generator"] == "codex"
        assert section["artwork"]["candidates"] == 2

    @pytest.mark.parametrize("broken", [None, [], "codex", 7])
    def test_a_malformed_section_cannot_break_a_rebuild(self, broken):
        section = indexer.build_config_section({"artwork": broken})
        assert section["artwork"]["generator"] == "manual"


@pytest.fixture(scope="module")
def example() -> dict:
    """config/config.example.yaml, parsed once for the tests below.

    A module-level function, not a method: pytest 9.2 deprecates a
    class-scoped fixture written as an instance method.
    """
    text = (PROJECT_ROOT / "config" / "config.example.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


class TestTheShippedExample:
    """config/config.example.yaml is what a new user copies."""

    def test_it_has_the_section(self, example):
        assert isinstance(example.get("artwork"), dict)

    def test_it_ships_switched_off(self, example):
        """Nobody's image allowance is spent until they choose to."""
        assert example["artwork"]["generator"] == "manual"
        assert example["artwork"]["candidates"] == 1

    def test_the_readme_documents_every_key(self, example):
        readme = (PROJECT_ROOT / "config" / "README.md").read_text(encoding="utf-8")
        for key in ("generator", "candidates", "codex_path"):
            assert f"`artwork.{key}`" in readme, key
