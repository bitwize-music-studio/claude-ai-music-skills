"""Tests for album-README layout frontmatter parsing (#290 phase 5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state.parsers import parse_album_readme  # noqa: E402


def _write_readme(tmp_path: Path, frontmatter: str, body: str = "# Album\n") -> Path:
    path = tmp_path / "README.md"
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path


def test_no_layout_frontmatter_returns_none(tmp_path: Path) -> None:
    path = _write_readme(tmp_path, 'title: "My Album"')
    result = parse_album_readme(path)
    assert result["layout"] is None


def test_layout_gap_default_transition(tmp_path: Path) -> None:
    path = _write_readme(tmp_path, 'layout:\n  default_transition: gap')
    result = parse_album_readme(path)
    assert result["layout"] == {"default_transition": "gap"}


def test_layout_gapless_default_transition(tmp_path: Path) -> None:
    path = _write_readme(tmp_path, 'layout:\n  default_transition: gapless')
    result = parse_album_readme(path)
    assert result["layout"] == {"default_transition": "gapless"}


def test_layout_unknown_value_drops_to_none(tmp_path: Path) -> None:
    path = _write_readme(tmp_path, 'layout:\n  default_transition: crossfade')
    result = parse_album_readme(path)
    assert result["layout"] is None


def test_layout_non_string_default_transition_drops_to_none(tmp_path: Path) -> None:
    path = _write_readme(tmp_path, 'layout:\n  default_transition: 42')
    result = parse_album_readme(path)
    assert result["layout"] is None


def test_layout_non_dict_value_drops_to_none(tmp_path: Path) -> None:
    path = _write_readme(tmp_path, 'layout: "gap"')
    result = parse_album_readme(path)
    assert result["layout"] is None


def test_layout_empty_dict_drops_to_none(tmp_path: Path) -> None:
    path = _write_readme(tmp_path, 'layout: {}')
    result = parse_album_readme(path)
    assert result["layout"] is None


def test_layout_case_insensitive_value(tmp_path: Path) -> None:
    # Accept "Gapless", "GAP" etc — normalize to lowercase.
    path = _write_readme(tmp_path, 'layout:\n  default_transition: Gapless')
    result = parse_album_readme(path)
    assert result["layout"] == {"default_transition": "gapless"}


def test_layout_extra_keys_ignored(tmp_path: Path) -> None:
    # Unknown keys inside the layout block don't break parsing.
    path = _write_readme(
        tmp_path,
        'layout:\n  default_transition: gap\n  reserved_future: true',
    )
    result = parse_album_readme(path)
    assert result["layout"] == {"default_transition": "gap"}
