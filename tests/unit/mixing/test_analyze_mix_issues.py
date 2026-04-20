"""Unit tests for analyze_mix_issues dark-track condition + threshold resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def test_resolve_analyzer_thresholds_defaults():
    """With no preset overrides, resolver returns (0.10, 0.25)."""
    from handlers.processing.mixing import _resolve_analyzer_thresholds
    dark, harsh = _resolve_analyzer_thresholds()
    assert dark == pytest.approx(0.10)
    assert harsh == pytest.approx(0.25)


def test_dark_condition_emits_high_tame_zero_and_already_dark_issue():
    """A track with high_mid_ratio < 0.10 gets recommendation high_tame_db=0.0."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = 0.3 * np.sin(2 * np.pi * 100 * t).astype(np.float64)
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="dark-track.wav", stem_name="synth", genre="electronic")

    assert "already_dark" in result["issues"], f"expected already_dark, got {result['issues']}"
    assert result["recommendations"]["high_tame_db"] == pytest.approx(0.0)
    assert result["high_mid_ratio"] < 0.10


def test_harsh_condition_still_fires_above_0_25():
    """A track with high_mid_ratio > 0.25 gets recommendation high_tame_db=-2.0 and harsh_highmids issue."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 3000 * t) + 0.3 * np.sin(2 * np.pi * 4000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="harsh-track.wav", stem_name="synth", genre="electronic")

    assert "harsh_highmids" in result["issues"], f"expected harsh_highmids, got {result['issues']}"
    assert result["recommendations"]["high_tame_db"] == pytest.approx(-2.0)


def test_middle_band_triggers_neither_condition():
    """high_mid_ratio in [0.10, 0.25] produces neither issue tag.

    Signal: 500 Hz at 0.8 + 3 kHz at 0.3 → high_mid_ratio ≈ 0.123, which
    sits between 0.10 and 0.25 so neither branch fires.
    """
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    # lo=0.8 @ 500 Hz + hi=0.3 @ 3 kHz → high_mid_ratio ≈ 0.123 (in-band)
    mono = (0.8 * np.sin(2 * np.pi * 500 * t) + 0.3 * np.sin(2 * np.pi * 3000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="middle-track.wav", stem_name="synth", genre="electronic")

    assert "already_dark" not in result["issues"]
    assert "harsh_highmids" not in result["issues"]
    assert "high_tame_db" not in result["recommendations"]
    assert result["high_mid_ratio"] > 0.10
    assert result["high_mid_ratio"] < 0.25


def test_preset_override_of_dark_threshold_changes_trigger():
    """Raising the dark threshold to 0.15 makes a ~0.138-ratio track fire already_dark.

    Signal: 500 Hz at 0.75 + 3 kHz at 0.3 → high_mid_ratio ≈ 0.138.
    Default threshold (0.10) does not fire; raised threshold (0.15) fires.
    """
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    # lo=0.75 @ 500 Hz + hi=0.3 @ 3 kHz → high_mid_ratio ≈ 0.138
    mono = (0.75 * np.sin(2 * np.pi * 500 * t) + 0.3 * np.sin(2 * np.pi * 3000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_default = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result_default = analyze_default(data, rate, filename="mid.wav", stem_name="synth", genre="electronic")
    assert "already_dark" not in result_default["issues"]
    assert result_default["high_mid_ratio"] > 0.10  # above default floor

    analyze_raised = _build_analyzer(dark_ratio=0.15, harsh_ratio=0.25)
    result_raised = analyze_raised(data, rate, filename="mid.wav", stem_name="synth", genre="electronic")
    assert "already_dark" in result_raised["issues"]
    assert result_raised["recommendations"]["high_tame_db"] == pytest.approx(0.0)
