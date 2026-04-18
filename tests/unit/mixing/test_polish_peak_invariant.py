"""Per-stem polish must not increase peak amplitude (#323 follow-up).

Contract: for any stem + any genre preset, the post-processing peak must
not exceed the pre-processing peak. Reporter's case: percussion went
0.096 → 0.100 (+4%) and vocals 0.767 → 0.840 (+9.5%) after polish
because:

1. Saturation normalizes by the transfer-function peak rather than the
   actual processed-signal peak, under-correcting on dynamic content.
2. Per-stem `gain_db` from presets can be positive and compounds on top.
3. The 0.95 clipping guard is post-mix and reactive — it only engages
   on the summed bus, not on per-stem processing.

This test pins the invariant at the per-stem processor boundary. Content
is synthesized to exercise the saturation path specifically (dense
transients with a sustained tail) — sine waves don't trigger
under-normalization, so stem tests with pure sines passed before and
the bug slipped through.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mixing.mix_tracks import (  # noqa: E402
    STEM_NAMES, STEM_PROCESSORS, _get_stem_settings,
)


def _dynamic_stereo_content(
    duration_s: float = 2.0, rate: int = 44100, seed: int = 17,
) -> tuple[np.ndarray, int]:
    """Stereo content with varied envelope — triggers saturation boost.

    Dense transients overlaid on a sustained mid-tone. Unlike a pure
    sine, the RMS-to-peak ratio changes over time, so saturation's
    transfer-function normalization can't perfectly preserve peak.
    """
    rng = np.random.default_rng(seed)
    n = int(duration_s * rate)
    t = np.arange(n) / rate
    sustained = 0.35 * np.sin(2 * np.pi * 440.0 * t)
    transients = np.zeros(n)
    # 8 impulsive transients over the duration.
    for k in range(8):
        pos = int(n * (0.1 + 0.1 * k))
        if pos < n:
            env = np.exp(-np.linspace(0, 6, min(400, n - pos)))
            transients[pos:pos + len(env)] += 0.6 * env * rng.standard_normal(
                len(env)
            )
    mono = (sustained + transients).astype(np.float64)
    # Scale so pre-peak is comfortably below 1.0, leaving headroom for
    # the test to catch any boost without clipping the input itself.
    mono = mono * (0.75 / max(np.max(np.abs(mono)), 1e-9))
    stereo = np.column_stack([mono, mono]).astype(np.float64)
    return stereo, rate


# A representative genre sweep that exercises different preset overlays.
PEAK_INVARIANT_GENRES = ["electronic", "rock", "pop", "ambient", "hip-hop"]


@pytest.mark.parametrize("stem", STEM_NAMES)
@pytest.mark.parametrize("genre", PEAK_INVARIANT_GENRES)
def test_polish_does_not_increase_peak(stem: str, genre: str) -> None:
    """post_peak ≤ pre_peak after per-stem polish, for every (stem, genre).

    Uses dynamic synthesized content (transients over a sustained tone)
    so saturation's under-normalization is exercised. Pure-sine inputs
    slip the bug — don't use them.
    """
    data, rate = _dynamic_stereo_content()
    pre_peak = float(np.max(np.abs(data)))

    settings = _get_stem_settings(stem, genre)
    processor = STEM_PROCESSORS[stem]
    report: dict[str, object] = {"clicks_removed": 0}
    processed = processor(data.copy(), rate, settings, report=report)

    post_peak = float(np.max(np.abs(processed)))

    # Strict invariant — a per-stem polish stage must not boost peak.
    # Tiny float slop is acceptable, so allow a 0.001 tolerance for
    # floating-point round-off only (NOT an audio-domain allowance).
    assert post_peak <= pre_peak + 1e-3, (
        f"{stem}/{genre}: polish increased peak "
        f"{pre_peak:.4f} → {post_peak:.4f} "
        f"(+{(post_peak - pre_peak) / pre_peak * 100:.1f}%)"
    )


@pytest.mark.parametrize("genre", PEAK_INVARIANT_GENRES)
def test_full_mix_polish_does_not_increase_peak(
    genre: str, tmp_path: Path,
) -> None:
    """Full-mix fallback path must obey the same peak invariant as stems.

    `mix_track_full` runs its own inline processing chain (not
    dispatched through `STEM_PROCESSORS`), so `_with_peak_guard`
    doesn't cover it. Same saturation + character-effects stack, same
    under-normalization risk. Pin the contract here so the fallback
    path can't regress.
    """
    import soundfile as sf
    from tools.mixing.mix_tracks import mix_track_full

    data, rate = _dynamic_stereo_content()
    pre_peak = float(np.max(np.abs(data)))
    input_path = tmp_path / "input.wav"
    sf.write(str(input_path), data, rate, subtype="PCM_16")
    output_path = tmp_path / "polished.wav"

    result = mix_track_full(
        input_path=input_path, output_path=output_path, genre=genre,
    )
    post_peak = float(result.get("post_peak", 0.0))

    assert post_peak <= pre_peak + 1e-3, (
        f"full_mix/{genre}: polish increased peak "
        f"{pre_peak:.4f} → {post_peak:.4f} "
        f"(+{(post_peak - pre_peak) / pre_peak * 100:.1f}%)"
    )
