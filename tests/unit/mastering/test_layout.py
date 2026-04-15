"""Tests for tools/mastering/layout.py (#290 phase 5, step 7)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.layout import (  # noqa: E402
    DEFAULT_TRANSITION,
    GAPLESS_TRANSITION,
    LayoutError,
    compute_transitions,
    render_layout_markdown,
)


def test_default_transition_constants_match_spec() -> None:
    assert DEFAULT_TRANSITION == {
        "mode": "gap",
        "gap_ms": 1500,
        "tail_fade_ms": 100,
        "head_fade_ms": 50,
    }
    assert GAPLESS_TRANSITION == {
        "mode": "gapless",
        "gap_ms": 0,
        "tail_fade_ms": 0,
        "head_fade_ms": 0,
    }


def test_compute_transitions_empty_list() -> None:
    assert compute_transitions([]) == []


def test_compute_transitions_single_track() -> None:
    # Single track has no adjacent pairs → empty transitions.
    assert compute_transitions(["01-only.wav"]) == []


def test_compute_transitions_default_gap_mode() -> None:
    result = compute_transitions(["01-a.wav", "02-b.wav", "03-c.wav"])
    assert len(result) == 2
    for t in result:
        assert t["mode"] == "gap"
        assert t["gap_ms"] == 1500
        assert t["tail_fade_ms"] == 100
        assert t["head_fade_ms"] == 50
    assert result[0]["from"] == "01-a.wav"
    assert result[0]["to"] == "02-b.wav"
    assert result[1]["from"] == "02-b.wav"
    assert result[1]["to"] == "03-c.wav"


def test_compute_transitions_gapless_override() -> None:
    result = compute_transitions(
        ["01-a.wav", "02-b.wav"], default_transition="gapless"
    )
    assert len(result) == 1
    assert result[0]["mode"] == "gapless"
    assert result[0]["gap_ms"] == 0
    assert result[0]["tail_fade_ms"] == 0
    assert result[0]["head_fade_ms"] == 0


def test_compute_transitions_unknown_mode_raises() -> None:
    with pytest.raises(LayoutError, match="Unknown transition mode"):
        compute_transitions(["01.wav", "02.wav"], default_transition="crossfade")


def test_render_layout_markdown_no_transitions_emits_note() -> None:
    md = render_layout_markdown("my-album", [])
    assert "# Album Layout" in md
    assert "my-album" in md
    assert "transitions: []" in md
    assert "Single-track" in md or "no transitions" in md.lower()


def test_render_layout_markdown_parseable_yaml_block() -> None:
    transitions = [
        {"from": "01-a.wav", "to": "02-b.wav", "mode": "gap",
         "gap_ms": 1500, "tail_fade_ms": 100, "head_fade_ms": 50},
        {"from": "02-b.wav", "to": "03-c.wav", "mode": "gap",
         "gap_ms": 1500, "tail_fade_ms": 100, "head_fade_ms": 50},
    ]
    md = render_layout_markdown("demo", transitions)
    assert "# Album Layout" in md
    # Extract the yaml fence and parse it.
    start = md.index("```yaml") + len("```yaml")
    end = md.index("```", start)
    parsed = yaml.safe_load(md[start:end])
    assert parsed == {"transitions": transitions}


def test_render_layout_markdown_gapless_round_trips() -> None:
    transitions = [
        {"from": "a.wav", "to": "b.wav", "mode": "gapless",
         "gap_ms": 0, "tail_fade_ms": 0, "head_fade_ms": 0},
    ]
    md = render_layout_markdown("demo", transitions)
    start = md.index("```yaml") + len("```yaml")
    end = md.index("```", start)
    parsed = yaml.safe_load(md[start:end])
    assert parsed["transitions"][0]["mode"] == "gapless"
    assert parsed["transitions"][0]["gap_ms"] == 0


def test_render_layout_markdown_includes_album_slug() -> None:
    md = render_layout_markdown("signal-chain", [])
    assert "signal-chain" in md
