"""End-to-end tests: analyzer recommends excitation_db on dark stems
(when the preset flag is on), which flows through _get_stem_settings
into the runtime settings, and the stem processor applies it."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import welch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mixing.mix_tracks import _get_stem_settings


class TestGetStemSettingsExcitation:
    def test_analyzer_rec_applied_when_dark(self):
        """When the analyzer's rec has excitation_db, _get_stem_settings
        honors it (whitelisted)."""
        settings = _get_stem_settings(
            "vocals",
            analyzer_rec={"excitation_db": 2.5, "high_tame_db": 0.0},
        )
        assert settings["excitation_db"] == 2.5

    def test_no_rec_keeps_zero_default(self):
        """Without an analyzer rec, excitation_db stays at preset
        default (0.0)."""
        settings = _get_stem_settings("vocals", analyzer_rec=None)
        assert settings["excitation_db"] == 0.0

    def test_unrelated_rec_ignored(self):
        """Recommendations for non-whitelisted keys are ignored."""
        settings = _get_stem_settings(
            "vocals",
            analyzer_rec={"some_nonsense_key": 999},
        )
        assert "some_nonsense_key" not in settings


class TestAnalyzerEmitsExcitationRec:
    def _call_analyze_one(
        self,
        data: np.ndarray,
        rate: int,
        stem_name: str,
        adm_aware: bool,
    ) -> dict:
        """Thin wrapper: build the analyzer the way the production caller
        does (via _build_analyzer), but with the adm_aware_excitation flag
        controlled by the test."""
        SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
        if str(SERVER_DIR) not in sys.path:
            sys.path.insert(0, str(SERVER_DIR))
        from handlers.processing.mixing import _build_analyzer  # type: ignore

        analyze_one = _build_analyzer(
            dark_ratio=0.10,
            harsh_ratio=0.25,
            adm_aware_excitation=adm_aware,
        )
        return analyze_one(
            data,
            rate,
            filename="test.wav",
            stem_name=stem_name,
            genre=None,
        )

    def _make_dark_stereo(self, seed: int = 0) -> tuple[np.ndarray, int]:
        """Low-passed noise — high_mid energy well below 10 %."""
        from scipy.signal import butter, sosfilt
        rng = np.random.default_rng(seed)
        rate = 48000
        n = int(2.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 500.0, btype="low", fs=rate, output="sos")
        dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
        dark /= np.max(np.abs(dark)) + 1e-9
        dark *= 0.1
        return dark, rate

    def _make_bright_stereo(self, seed: int = 2) -> tuple[np.ndarray, int]:
        """High-passed noise — high_mid energy well above 10 %."""
        from scipy.signal import butter, sosfilt
        rng = np.random.default_rng(seed)
        rate = 48000
        n = int(2.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 800.0, btype="high", fs=rate, output="sos")
        bright = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
        bright /= np.max(np.abs(bright)) + 1e-9
        bright *= 0.1
        return bright, rate

    def test_no_rec_when_flag_off(self):
        """Dark stem, adm_aware_excitation=False → no excitation_db
        recommendation emitted (existing behavior preserved)."""
        dark, rate = self._make_dark_stereo(seed=0)

        result = self._call_analyze_one(dark, rate, "vocals", adm_aware=False)
        assert "already_dark" in result["issues"], (
            "Fixture should be classified dark"
        )
        assert "excitation_db" not in result["recommendations"], (
            "Flag off → no excitation rec"
        )

    def test_rec_emitted_when_flag_on_and_dark(self):
        """Dark stem + flag on → excitation_db rec at stem's per-stem
        preset value (vocals = 2.5)."""
        dark, rate = self._make_dark_stereo(seed=1)

        result = self._call_analyze_one(dark, rate, "vocals", adm_aware=True)
        assert "already_dark" in result["issues"]
        assert result["recommendations"].get("excitation_db") == 2.5, (
            "Vocals preset's excitation_db_when_dark is 2.5"
        )

    def test_no_rec_on_bright_stem(self):
        """Bright stem + flag on → no excitation rec (only dark stems
        get excited)."""
        bright, rate = self._make_bright_stereo(seed=2)

        result = self._call_analyze_one(bright, rate, "vocals", adm_aware=True)
        assert "already_dark" not in result["issues"]
        assert "excitation_db" not in result["recommendations"]
