#!/usr/bin/env python3
"""Fix tracks with excessive dynamic range that won't reach target LUFS."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.mastering.master_tracks import apply_eq, soft_clip, write_delivery
from tools.shared.logging_config import setup_logging

logger = logging.getLogger(__name__)

# (threshold_db, ratio) schedule used by fix_dynamic's iterative loop.
# First iteration matches legacy single-pass behavior. Heavier passes trade
# crest factor for headroom — needed when the ceiling is tight relative to the
# material's K-weighted response (dark content). Exposed at module scope so
# callers can reason about the max iteration count without hardcoding 3.
_FIX_DYNAMIC_ITER_SCHEDULE: list[tuple[float, float]] = [
    (-12.0, 2.5),
    (-10.0, 3.5),
    (-8.0,  5.0),
]


def fix_dynamic(data: Any, rate: int, target_lufs: float = -14.0,
                eq_settings: list[tuple[float, float, float]] | None = None,
                ceiling_db: float = -1.0) -> tuple[Any, dict[str, Any]]:
    """Core dynamic range fix: EQ → (compress → normalize → limit)xN.

    Runs up to 3 iterations of compress→normalize→limit with progressively
    heavier compression, stopping as soon as integrated LUFS is within
    ±0.5 dB of ``target_lufs``. When no iteration converges, returns the
    attempt with the smallest LUFS error and sets ``converged=False`` so
    the caller can decide whether the track is salvageable.

    Args:
        data: Audio data (numpy array, stereo)
        rate: Sample rate
        target_lufs: Target LUFS (default: -14.0)
        eq_settings: List of (freq, gain_db, q) tuples. If None, applies
            default 3500 Hz cut (-2.0 dB, Q=1.5).
        ceiling_db: Peak ceiling in dB (default: -1.0)

    Returns:
        (processed_data, metrics) tuple where metrics has:
            original_lufs:   input integrated LUFS
            final_lufs:      best-attempt integrated LUFS
            final_peak_db:   best-attempt peak in dBTP
            converged:       True if final_lufs within ±0.5 dB of target
            iterations_run:  1, 2, or 3
    """
    meter = pyln.Meter(rate)
    original_lufs = meter.integrated_loudness(data)

    # EQ is input conditioning — applied once, not part of the dynamics loop.
    if eq_settings is None:
        eq_settings = [(3500, -2.0, 1.5)]
    eq_data = data
    for freq, gain_db, q in eq_settings:
        eq_data = apply_eq(eq_data, rate, freq, gain_db, q)

    ceiling = 10 ** (ceiling_db / 20)
    tolerance_db = 0.5

    best_data = eq_data
    best_lufs = float("-inf")
    best_diff = float("inf")
    converged = False
    iterations_run = 0

    for i, (thr, ratio) in enumerate(_FIX_DYNAMIC_ITER_SCHEDULE):
        iterations_run = i + 1

        iter_data = gentle_compress(
            eq_data, threshold_db=thr, ratio=ratio, rate=rate,
        )

        post_comp_lufs = meter.integrated_loudness(iter_data)
        if np.isfinite(post_comp_lufs):
            gain_db_val = target_lufs - post_comp_lufs
            iter_data = iter_data * (10 ** (gain_db_val / 20))

        peak = np.max(np.abs(iter_data))
        if peak > ceiling:
            iter_data = iter_data * (ceiling / peak)
        iter_data = soft_clip(iter_data, ceiling)

        iter_lufs = meter.integrated_loudness(iter_data)
        iter_diff = (
            abs(iter_lufs - target_lufs) if np.isfinite(iter_lufs) else float("inf")
        )

        if iter_diff < best_diff:
            best_data = iter_data
            best_lufs = iter_lufs
            best_diff = iter_diff

        if iter_diff <= tolerance_db:
            converged = True
            break

    peak_abs = np.max(np.abs(best_data))
    final_peak = 20 * np.log10(peak_abs) if peak_abs > 0 else float("-inf")

    metrics: dict[str, Any] = {
        "original_lufs":   float(original_lufs),
        "final_lufs":      float(best_lufs),
        "final_peak_db":   float(final_peak),
        "converged":       bool(converged),
        "iterations_run":  int(iterations_run),
    }

    return best_data, metrics


def fix_dynamic_to_file(
    src: Path | str,
    dst: Path | str,
    *,
    target_lufs: float,
    ceiling_db: float,
    output_bits: Any,
    output_sample_rate: Any,
    eq_settings: list[tuple[float, float, float]] | None = None,
    fade_out: float | None = None,
    archival_path: Path | str | None = None,
) -> dict[str, Any]:
    """Run ``fix_dynamic`` on ``src`` and write ``dst`` in the delivery format.

    The one path that writes a dynamic-range fix into ``mastered/`` (#681):
    ``master_album``'s auto-recovery and the ``fix_dynamic_track`` tool both
    use it, so a fixed track comes out at the album's bit depth, sample rate,
    loudness target and true-peak ceiling like every other master, instead of
    16-bit at the source rate and -14 LUFS.

    ``fade_out`` (seconds) is applied before the loudness work, as in
    ``master_track``. Returns ``fix_dynamic``'s metrics plus
    ``sample_rate``, ``output_bits`` and ``true_peak_db`` of the written file.
    """
    data, rate = sf.read(str(src))
    if len(data.shape) == 1:
        data = np.column_stack([data, data])
    if fade_out:
        # Looked up at call time, like the handlers always did, so a spy on
        # master_tracks.apply_fade_out sees the call.
        from tools.mastering import master_tracks as _master_tracks
        data = _master_tracks.apply_fade_out(data, rate, duration=fade_out)
    data, metrics = fix_dynamic(
        data, rate,
        target_lufs=target_lufs,
        eq_settings=eq_settings,
        ceiling_db=ceiling_db,
    )
    written = write_delivery(
        data, rate, dst,
        ceiling_db=ceiling_db,
        output_bits=output_bits,
        output_sample_rate=output_sample_rate,
        archival_path=archival_path,
    )
    metrics["sample_rate"] = written["sample_rate"]
    metrics["output_bits"] = written["output_bits"]
    metrics["true_peak_db"] = written["final_peak_db"]
    return metrics


def gentle_compress(data: Any, threshold_db: float = -10, ratio: float = 3.0,
                    attack_ms: float = 10, release_ms: float = 100,
                    rate: int = 44100) -> Any:
    """Apply gentle compression to reduce dynamic range."""
    threshold = 10 ** (threshold_db / 20)

    # Calculate envelope
    attack_samples = int(attack_ms * rate / 1000)
    release_samples = int(release_ms * rate / 1000)

    # Work with mono envelope for gain calculation
    if len(data.shape) > 1:
        mono = np.max(np.abs(data), axis=1)
    else:
        mono = np.abs(data)

    # Simple envelope follower
    envelope = np.zeros_like(mono)
    for i in range(1, len(mono)):
        if mono[i] > envelope[i-1]:
            coef = 1 - np.exp(-1 / attack_samples)
        else:
            coef = 1 - np.exp(-1 / release_samples)
        envelope[i] = envelope[i-1] + coef * (mono[i] - envelope[i-1])

    # Calculate gain reduction
    gain = np.ones_like(envelope)
    above_thresh = envelope > threshold
    gain[above_thresh] = threshold + (envelope[above_thresh] - threshold) / ratio
    gain[above_thresh] = gain[above_thresh] / envelope[above_thresh]

    # Apply gain
    if len(data.shape) > 1:
        return data * gain[:, np.newaxis]
    return data * gain

def main() -> None:
    setup_logging(__name__)

    if len(sys.argv) < 2:
        logger.error("Usage: python fix_dynamic_track.py <input.wav> [output.wav]")
        logger.error("  Fixes tracks with excessive dynamic range")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"mastered/{Path(input_file).name}"

    # Prevent path traversal: output must stay within input file's parent directory
    input_dir = Path(input_file).resolve().parent
    output_path = Path(output_file).resolve()
    try:
        output_path.relative_to(input_dir)
    except ValueError:
        logger.error("Output path must be within input directory")
        logger.error("  Output: %s", output_path)
        logger.error("  Input dir: %s", input_dir)
        sys.exit(1)

    logger.info("Processing %s...", input_file)

    # Ensure output directory exists
    Path(output_file).parent.mkdir(exist_ok=True)

    # Delivery targets from the mastering: block of config.yaml (#681) —
    # the same format, loudness and ceiling master_album writes.
    from tools.mastering.config import load_mastering_config
    delivery = load_mastering_config()

    metrics = fix_dynamic_to_file(
        input_file, output_file,
        target_lufs=float(delivery["target_lufs"]),
        ceiling_db=float(delivery["true_peak_ceiling"]),
        output_bits=delivery["delivery_bit_depth"],
        output_sample_rate=delivery["delivery_sample_rate"],
    )

    print(f"  Original LUFS: {metrics['original_lufs']:.1f}")
    print(f"  Final LUFS: {metrics['final_lufs']:.1f}")
    print(f"  Final Peak: {metrics['true_peak_db']:.1f} dBTP")
    logger.info("Written to: %s (%d-bit, %d Hz)", output_file,
                metrics["output_bits"], metrics["sample_rate"])

if __name__ == '__main__':
    main()
