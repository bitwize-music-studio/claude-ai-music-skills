#!/usr/bin/env python3
"""Fix tracks with excessive dynamic range that won't reach target LUFS."""

import logging
import sys
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging
from tools.mastering.master_tracks import apply_eq, soft_clip

logger = logging.getLogger(__name__)

def gentle_compress(data, threshold_db=-10, ratio=3.0, attack_ms=10, release_ms=100, rate=44100):
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

def main():
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

    # Read
    data, rate = sf.read(input_file)
    if len(data.shape) == 1:
        data = np.column_stack([data, data])

    meter = pyln.Meter(rate)
    original_lufs = meter.integrated_loudness(data)
    print(f"  Original LUFS: {original_lufs:.1f}")

    # Step 1: Apply EQ (same as other tracks)
    data = apply_eq(data, rate, 3500, -2.0, 1.5)

    # Step 2: Apply gentle compression to tame transients
    data = gentle_compress(data, threshold_db=-12, ratio=2.5, rate=rate)

    post_comp_lufs = meter.integrated_loudness(data)
    print(f"  After compression: {post_comp_lufs:.1f} LUFS")

    # Step 3: Normalize to -14 LUFS
    target_lufs = -14.0
    gain_db = target_lufs - post_comp_lufs
    gain_linear = 10 ** (gain_db / 20)
    data = data * gain_linear

    # Step 4: Limit peaks
    ceiling = 10 ** (-1.0 / 20)  # -1 dBTP
    peak = np.max(np.abs(data))
    if peak > ceiling:
        data = data * (ceiling / peak)
    data = soft_clip(data, ceiling)

    # Verify
    final_lufs = meter.integrated_loudness(data)
    final_peak = 20 * np.log10(np.max(np.abs(data)))

    print(f"  Final LUFS: {final_lufs:.1f}")
    print(f"  Final Peak: {final_peak:.1f} dBTP")

    # Write
    sf.write(output_file, data, rate, subtype='PCM_16')
    logger.info("Written to: %s", output_file)

if __name__ == '__main__':
    main()
