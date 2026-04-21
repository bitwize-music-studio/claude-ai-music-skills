"""Recovery path must write at ctx.targets['output_sample_rate'], not
the source rate. Regression for bug #1 — a 48 kHz source that triggers
auto-recovery used to be written back at 48 kHz while the rest of the
album was at 96 kHz."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx


def _write_pink_wav(path: Path, rate: int, seconds: float = 3.0) -> None:
    """Write a stereo pink-ish WAV at the given sample rate.

    The audio is normalised so the true peak is very close to -1.5 dBFS
    while the integrated LUFS stays well below -14 LUFS (quiet overall but
    already limited to the ceiling).  This makes the mastered copy land in
    the 'lufs_too_low AND peak_at_ceiling' bucket that _stage_verification
    recognises as auto-recoverable.
    """
    rng = np.random.default_rng(42)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    # First-order pink filter
    pink = np.zeros_like(white)
    alpha = 0.98
    for i in range(1, n):
        pink[i] = alpha * pink[i - 1] + (1 - alpha) * white[i]

    # Normalise to true peak = -1.5 dBFS so the mastered copy will have
    # peak_db ≈ -1.5 (at ceiling) but LUFS far below -14.
    peak_lin = np.max(np.abs(pink))
    target_peak_lin = 10 ** (-1.5 / 20)
    pink *= target_peak_lin / (peak_lin + 1e-9)
    sf.write(str(path), pink, rate, subtype="PCM_24")


def test_recovery_writes_at_delivery_sample_rate(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "mastered"
    source_dir.mkdir()
    output_dir.mkdir()

    source_rate = 48_000
    delivery_rate = 96_000
    target_lufs = -14.0
    target_ceiling = -1.5

    fname = "09-dark.wav"
    _write_pink_wav(source_dir / fname, source_rate)

    # Pre-populate the mastered dir with the same audio so the output file
    # exists before _stage_verification reads it back via analyze_track.
    import shutil
    shutil.copy(source_dir / fname, output_dir / fname)

    # Construct ctx with all required fields.
    loop = asyncio.new_event_loop()
    ctx = MasterAlbumCtx(
        album_slug="test-album",
        genre="",
        target_lufs=target_lufs,
        ceiling_db=target_ceiling,
        cut_highmid=0.0,
        cut_highs=0.0,
        source_subfolder="",
        freeze_signature=False,
        new_anchor=False,
        loop=loop,
    )
    ctx.source_dir = source_dir
    ctx.output_dir = output_dir
    ctx.audio_dir = source_dir  # fallback lookup dir
    ctx.wav_files = [source_dir / fname]
    ctx.mastered_files = [output_dir / fname]
    ctx.targets = {
        "output_sample_rate": delivery_rate,
        "output_bits": 24,
        "ceiling_db": target_ceiling,
    }
    ctx.effective_lufs = target_lufs
    ctx.effective_ceiling = target_ceiling
    ctx.effective_highmid = 0.0
    ctx.effective_highs = 0.0
    ctx.effective_compress = 2.5

    # Mock analyze_track to return values that put the mastered copy in the
    # auto-recoverable bucket:
    #   lufs_too_low   = True   (lufs < target - 0.5 → -22.0 < -14.5)
    #   peak_at_ceiling = True  (peak_db >= ceiling - 0.1 → -1.5 >= -1.6)
    #   has_peak_issue  = False (peak_db <= ceiling → -1.5 <= -1.5)
    def _fake_analyze(path: str) -> dict:
        return {
            "filename": Path(path).name,
            "lufs": -22.0,   # well below target → lufs_too_low
            "peak_db": -1.5, # exactly at ceiling → peak_at_ceiling, no peak issue
            "short_term_range": 6.0,
        }

    asyncio.set_event_loop(loop)
    try:
        # analyze_track is imported locally inside _stage_verification via
        #   from tools.mastering.analyze_tracks import analyze_track
        # so we patch the symbol on its source module; the local `from … import`
        # will pick up the patched version at call time.
        with patch(
            "tools.mastering.analyze_tracks.analyze_track",
            side_effect=_fake_analyze,
        ):
            result = loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        loop.close()

    # Recovery must have actually run — not halted before reaching it.
    if result is not None:
        import json
        payload = json.loads(result)
        warnings = payload.get("warnings", [])
        recovery_ran = any(w.get("type") == "auto_recovery" for w in warnings)
        assert recovery_ran, (
            f"stage halted before recovery ran: {payload}"
        )

    # The recovery path ran (result is None on pass-after-recovery or a
    # warn-fallback JSON — either way the file must have been rewritten).
    data, rate_written = sf.read(str(output_dir / fname))
    assert rate_written == delivery_rate, (
        f"recovery wrote at {rate_written} Hz but delivery target is "
        f"{delivery_rate} Hz (bug #1 regression)"
    )
