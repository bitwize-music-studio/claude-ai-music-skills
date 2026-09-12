#!/usr/bin/env python3
"""Unit tests for build_effective_preset (D1 refactor extraction)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.config import build_effective_preset


class TestBuildEffectivePreset:
    def test_pop_genre_happy_path(self):
        result = build_effective_preset(
            genre="pop",
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
            source_sample_rate=44100,
        )
        assert result["error"] is None
        assert result["genre_applied"] == "pop"
        assert result["preset_dict"] is not None
        # effective_preset must carry resolved delivery targets
        ep = result["effective_preset"]
        assert ep["target_lufs"] == -14.0
        assert ep["output_bits"] == 24
        assert ep["output_sample_rate"] == 96000
        # settings dict is JSON-ready
        s = result["settings"]
        assert s["genre"] == "pop"
        assert s["target_lufs"] == -14.0
        assert s["ceiling_db"] == -1.0
        # source_sample_rate threads through to both targets and settings
        assert result["targets"]["source_sample_rate"] == 44100
        assert result["targets"]["upsampled_from_source"] is True
        assert s["upsampled_from_source"] is True

    def test_empty_genre_no_preset(self):
        result = build_effective_preset(
            genre="",
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert result["error"] is None
        assert result["preset_dict"] is None
        assert result["genre_applied"] is None
        # Still returns a working effective_preset with delivery-target fields
        ep = result["effective_preset"]
        assert ep["target_lufs"] == -14.0
        assert ep["compress_ratio"] == 1.5
        assert ep["cut_highmid"] == 0.0

    def test_empty_genre_dither_follows_output_bits(self):
        """Regression for #373: a genreless master must dither at output_bits.

        _PRESET_DEFAULTS hardcodes dither_bits=16, and the genreless
        effective_preset previously omitted dither_bits, so master_track
        resolved output_bits=24 but dither_bits=16 — injecting a 16-bit noise
        floor into a 24-bit file. The effective_preset must carry a dither_bits
        that follows output_bits.
        """
        result = build_effective_preset(
            genre="",
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        ep = result["effective_preset"]
        assert "dither_bits" in ep, "genreless preset must set dither_bits explicitly"
        assert ep["dither_bits"] == ep["output_bits"], (
            f"dither_bits ({ep['dither_bits']}) must follow output_bits "
            f"({ep['output_bits']}) for a genreless master"
        )

    def test_genre_preset_dither_follows_output_bits(self):
        """A genre preset's effective_preset should also carry a dither_bits
        consistent with output_bits (genre-presets.yaml sets dither_bits=24)."""
        result = build_effective_preset(
            genre="pop",
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        ep = result["effective_preset"]
        assert ep["dither_bits"] == ep["output_bits"]

    def test_unknown_genre_returns_error(self):
        result = build_effective_preset(
            genre="not-a-real-genre",
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert result["error"] is not None
        assert "Unknown genre" in result["error"]["reason"]
        assert "available_genres" in result["error"]
        assert "pop" in result["error"]["available_genres"]

    def test_explicit_args_override_preset(self):
        result = build_effective_preset(
            genre="pop",
            cut_highmid_arg=-2.5,  # explicit override
            cut_highs_arg=-1.0,    # explicit override
            target_lufs_arg=-16.0, # explicit override
            ceiling_db_arg=-1.5,   # explicit override
        )
        assert result["error"] is None
        ep = result["effective_preset"]
        assert ep["cut_highmid"] == -2.5
        assert ep["cut_highs"] == -1.0
        assert ep["target_lufs"] == -16.0
        s = result["settings"]
        assert s["ceiling_db"] == -1.5


class TestCutEqNoneSentinel:
    """#556: None means "use the genre preset", an explicit 0 disables the cut.

    black-metal is the fixture genre because it ships a non-zero value for
    BOTH cuts, so "explicit 0 disables" is a real assertion either way.
    """

    @pytest.fixture(autouse=True)
    def _shipped_presets_only(self, monkeypatch):
        """Resolve from the presets this repo ships, not from the developer's
        ``{overrides}/mastering-presets.yaml`` — an override that zeroed
        black-metal's cuts would otherwise make these assertions vacuous."""
        from tools.mastering import master_tracks as master_tracks_mod
        monkeypatch.setattr(master_tracks_mod, "_get_overrides_path", lambda: None)

    def _preset(self) -> dict:
        from tools.mastering.master_tracks import load_genre_presets
        return load_genre_presets()["black-metal"]

    def test_omitted_uses_preset_cuts(self):
        preset = self._preset()
        result = build_effective_preset(
            genre="black-metal", target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
        )
        assert result["effective_preset"]["cut_highmid"] == preset["cut_highmid"]
        assert result["effective_preset"]["cut_highs"] == preset["cut_highs"]
        assert result["settings"]["cut_highmid"] == preset["cut_highmid"]
        assert result["settings"]["cut_highs"] == preset["cut_highs"]

    def test_explicit_none_matches_omitted(self):
        preset = self._preset()
        result = build_effective_preset(
            genre="black-metal", cut_highmid_arg=None, cut_highs_arg=None,
            target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
        )
        assert result["settings"]["cut_highmid"] == preset["cut_highmid"]
        assert result["settings"]["cut_highs"] == preset["cut_highs"]

    def test_explicit_zero_disables_and_is_echoed(self):
        preset = self._preset()
        assert preset["cut_highmid"] != 0, "fixture genre must ship a cut"
        result = build_effective_preset(
            genre="black-metal", cut_highmid_arg=0.0, cut_highs_arg=0.0,
            target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
        )
        assert result["effective_preset"]["cut_highmid"] == 0.0
        assert result["effective_preset"]["cut_highs"] == 0.0
        assert result["settings"]["cut_highmid"] == 0.0
        assert result["settings"]["cut_highs"] == 0.0

    def test_each_cut_resolves_independently(self):
        preset = self._preset()
        result = build_effective_preset(
            genre="black-metal", cut_highmid_arg=0.0,
            target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
        )
        assert result["settings"]["cut_highmid"] == 0.0
        assert result["settings"]["cut_highs"] == preset["cut_highs"]

    def test_genreless_omitted_still_resolves_to_no_cut(self):
        """Byte-identical to the pre-#556 float-only default of 0.0."""
        result = build_effective_preset(
            genre="", target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
        )
        assert result["effective_preset"]["cut_highmid"] == 0.0
        assert result["effective_preset"]["cut_highs"] == 0.0
