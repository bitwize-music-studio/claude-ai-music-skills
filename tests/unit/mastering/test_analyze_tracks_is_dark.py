"""analyze_track must return is_dark=True when high_mid band energy is
below the 10 % threshold used by the mix analyzer's already_dark signal."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.analyze_tracks import analyze_track


def _write_dark(path: Path, seconds: float = 4.0, rate: int = 48000) -> None:
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(0)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    sos = butter(4, 400.0, btype="low", fs=rate, output="sos")
    dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
    dark /= np.max(np.abs(dark)) + 1e-9
    dark *= 0.1
    sf.write(str(path), dark, rate, subtype="PCM_24")


def _write_bright(path: Path, seconds: float = 4.0, rate: int = 48000) -> None:
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(1)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    # High-pass around 800 Hz — forces high_mid band to dominate.
    sos = butter(4, 800.0, btype="high", fs=rate, output="sos")
    bright = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
    bright /= np.max(np.abs(bright)) + 1e-9
    bright *= 0.1
    sf.write(str(path), bright, rate, subtype="PCM_24")


class TestAnalyzeTrackIsDark:
    def test_dark_track_reports_is_dark_true(self, tmp_path: Path) -> None:
        path = tmp_path / "dark.wav"
        _write_dark(path)
        result = analyze_track(str(path))
        assert result["band_energy"]["high_mid"] < 10.0
        assert result["is_dark"] is True

    def test_bright_track_reports_is_dark_false(self, tmp_path: Path) -> None:
        path = tmp_path / "bright.wav"
        _write_bright(path)
        result = analyze_track(str(path))
        assert result["band_energy"]["high_mid"] >= 10.0
        assert result["is_dark"] is False

    def test_is_dark_is_bool_not_numpy_bool(self, tmp_path: Path) -> None:
        path = tmp_path / "dark.wav"
        _write_dark(path)
        result = analyze_track(str(path))
        assert type(result["is_dark"]) is bool


def test_stage_analysis_populates_dark_tracks(tmp_path: Path) -> None:
    """_stage_analysis should set ctx.dark_tracks from analyze_track's
    is_dark field."""
    import asyncio

    SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
    if str(SERVER_DIR) not in sys.path:
        sys.path.insert(0, str(SERVER_DIR))

    from handlers.processing._album_stages import MasterAlbumCtx, _stage_analysis

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _write_dark(source_dir / "01-dark.wav")
    _write_bright(source_dir / "02-bright.wav")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ctx = MasterAlbumCtx(
        album_slug="test",
        genre="pop",
        target_lufs=-14.0,
        ceiling_db=-1.0,
        cut_highmid=0.0,
        cut_highs=0.0,
        source_subfolder="",
        freeze_signature=False,
        new_anchor=False,
        loop=loop,
        source_dir=source_dir,
        wav_files=sorted(source_dir.glob("*.wav")),
    )
    try:
        loop.run_until_complete(_stage_analysis(ctx))
    finally:
        loop.close()

    assert "01-dark.wav" in ctx.dark_tracks
    assert "02-bright.wav" not in ctx.dark_tracks
