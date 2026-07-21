"""Real-``afconvert`` integration test for the macOS ADM-validation path.

Exercises the FULL product path against the REAL macOS ``afconvert`` binary:

    a genuine WAV (ffmpeg lavfi sine)
      -> adm_validation._afconvert_encode_decode
           (subprocess: afconvert -f m4af -d aac ...  then  ffmpeg decode)
      -> a decoded float32 numpy array + encoder name "afconvert"

This is the ONE path the mocked unit tests
(``tests/unit/mastering/test_adm_validation_afconvert.py``) cannot prove: they
fake the toolchain, so they verify the three *fallback* branches but never that
real afconvert actually encodes a decodable m4a. A regression in the afconvert
argument order, the container/codec flags, the bitrate spelling, or the
ffmpeg-decode-after-afconvert handoff would fail HERE — and nowhere else.

Triple-gated so the normal suite and the 3-OS matrix collect-and-skip cleanly:

  * ``pytest.mark.integration`` + ``skipif(not BITWIZE_INTEGRATION)`` — the same
    double gate every integration module carries (only the CI integration job
    sets the env var); plus
  * ``skipif(shutil.which("afconvert") is None)`` — afconvert is a macOS-only
    system binary, so this cleanly skips on Linux/Windows *even when* the env
    gate is set (this box, and the ubuntu/windows matrix legs).

Guard choice: gating on ``shutil.which("afconvert")`` rather than
``sys.platform == "darwin"`` keys off the actual *capability* (is the binary
runnable?) instead of a platform proxy. It mirrors the repo's existing
``requires_ffmpeg`` idiom (``shutil.which("ffmpeg")``) and the MuseScore
integration test's binary-presence skip, and it degrades gracefully on the
(theoretical) macOS box without afconvert instead of erroring. ffmpeg presence
is guarded too, since both the WAV generation and the decode need it.

Nothing at import time loads the product module or shells out — the product is
imported inside the test, which only runs when NOT skipped, so collecting this
module on a dev box or the non-macOS matrix legs is inert.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("BITWIZE_INTEGRATION"),
        reason="integration services not available (set BITWIZE_INTEGRATION=1)",
    ),
    pytest.mark.skipif(
        shutil.which("afconvert") is None,
        reason="afconvert not available (macOS-only system binary)",
    ),
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="ffmpeg not available (needed to generate + decode the fixture)",
    ),
]

REPO_ROOT = Path(__file__).resolve().parents[2]

_FIXTURE_RATE = 44100


def _make_sine_wav(path: Path) -> Path:
    """Generate a tiny real stereo WAV via ffmpeg lavfi (as the toolchain does).

    A 0.5 s 440 Hz sine at 44.1 kHz, quietened to -6 dBFS so afconvert has clean
    headroom. ffmpeg is on the macOS runner (installed via brew in CI).
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration=0.5:sample_rate={_FIXTURE_RATE}",
        "-af", "volume=0.5",
        "-ac", "2",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=60)
    assert path.is_file() and path.stat().st_size > 0, "ffmpeg produced no WAV"
    return path


def test_afconvert_real_encode_decode(tmp_path) -> None:
    """The real afconvert path must encode+decode and report encoder 'afconvert'."""
    import numpy as np

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.mastering.adm_validation import _afconvert_encode_decode

    wav = _make_sine_wav(tmp_path / "sine.wav")

    data, rate, encoder = _afconvert_encode_decode(wav)

    # The whole point: real afconvert did the encoding, not the ffmpeg fallback.
    assert encoder == "afconvert", (
        f"expected real afconvert, got fallback encoder {encoder!r} — afconvert "
        "may be missing, timing out, or erroring on this runner"
    )
    assert isinstance(data, np.ndarray)
    assert data.size > 0, "decoded array is empty"
    assert data.dtype == np.float32
    assert rate == _FIXTURE_RATE, f"expected {_FIXTURE_RATE} Hz, got {rate}"


def test_afconvert_real_public_api(tmp_path) -> None:
    """Through the public API, encoder_used must be 'afconvert' on macOS."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.mastering.adm_validation import check_aac_intersample_clips

    wav = _make_sine_wav(tmp_path / "sine2.wav")

    result = check_aac_intersample_clips(wav, encoder="afconvert", ceiling_db=-1.0)

    assert result["encoder_used"] == "afconvert"
    assert result["filename"] == "sine2.wav"
    assert isinstance(result["clip_count"], int)
    assert isinstance(result["peak_db_decoded"], float)
