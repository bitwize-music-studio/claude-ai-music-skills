#!/usr/bin/env python3
"""
Reference-Based Mastering Script
Uses matchering to match your tracks to a professionally mastered reference.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging
from tools.shared.progress import ProgressBar

logger = logging.getLogger(__name__)

try:
    import matchering as mg
except ImportError:
    print("Error: matchering not installed")
    print("Run: pip install matchering")
    sys.exit(1)


def master_with_reference(target_path: Path | str, reference_path: Path | str,
                          output_path: Path | str, *,
                          output_bits: int | None = None,
                          output_sample_rate: int | None = None,
                          ceiling_db: float | None = None) -> dict[str, Any]:
    """Master a single track using a reference.

    matchering matches the target's EQ and loudness to the reference and
    renders at its internal 44.1 kHz. Its own limiter brickwalls at about
    -0.02 dBFS and its ``pcm16`` result is 16-bit, so it no longer writes
    the delivered file itself (#681): it renders an unlimited 32-bit float
    file, and the plugin's look-ahead limiter and delivery tail take it to
    the true-peak ceiling, the delivery sample rate and bit depth, exactly as
    ``master_album`` delivers.

    Args:
        target_path: Path to your track (WAV)
        reference_path: Path to professionally mastered reference (WAV)
        output_path: Path for output file
        output_bits: Delivery bit depth (16/24). None = config's
            ``mastering.delivery_bit_depth``.
        output_sample_rate: Delivery sample rate. None = config's
            ``mastering.delivery_sample_rate``.
        ceiling_db: True-peak ceiling in dBTP. None = config's
            ``mastering.true_peak_ceiling``.

    Returns:
        ``{"sample_rate", "output_bits", "final_peak_db", "final_lufs",
        "ceiling_db"}`` for the written file.
    """
    import numpy as np
    import pyloudnorm as pyln
    import soundfile as sf

    from tools.mastering.master_tracks import limit_peaks_lookahead, write_delivery

    if output_bits is None or output_sample_rate is None or ceiling_db is None:
        from tools.mastering.config import load_mastering_config
        cfg = load_mastering_config()
        if output_bits is None:
            output_bits = int(cfg["delivery_bit_depth"])
        if output_sample_rate is None:
            output_sample_rate = int(cfg["delivery_sample_rate"])
        if ceiling_db is None:
            ceiling_db = float(cfg["true_peak_ceiling"])

    logger.info("  Target: %s", target_path)
    logger.info("  Reference: %s", reference_path)
    logger.info("  Output: %s", output_path)

    output_path = Path(output_path)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".matchering_", suffix=".wav", dir=str(output_path.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        mg.process(
            target=str(target_path),
            reference=str(reference_path),
            results=[
                # Float, no limiter, no normalisation: the ceiling and the
                # delivery format are applied below.
                mg.Result(str(tmp_path), subtype="FLOAT",
                          use_limiter=False, normalize=False),
            ],
        )
        data, rate = sf.read(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    if data.ndim == 1:
        data = np.column_stack([data, data])
    data = limit_peaks_lookahead(data, ceiling_db, rate=rate)
    final_lufs = float(pyln.Meter(rate).integrated_loudness(data))
    written = write_delivery(
        data, rate, output_path,
        ceiling_db=ceiling_db,
        output_bits=output_bits,
        output_sample_rate=output_sample_rate,
    )
    logger.info("  Done! (%d-bit, %d Hz, %.2f dBTP)", written["output_bits"],
                written["sample_rate"], written["final_peak_db"])
    return {**written, "final_lufs": final_lufs, "ceiling_db": float(ceiling_db)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Master tracks using a reference track',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Master a single track
  python reference_master.py --reference pro_master.wav --target my_track.wav

  # Master all tracks in current directory
  python reference_master.py --reference pro_master.wav

  # Master with custom output directory
  python reference_master.py --reference pro_master.wav --output-dir matched/
        """
    )
    parser.add_argument('--reference', '-r', required=True,
                       help='Path to professionally mastered reference track (WAV)')
    parser.add_argument('--target', '-t',
                       help='Path to single target track (if omitted, processes all WAVs in current dir)')
    parser.add_argument('--output-dir', '-o', default='mastered',
                       help='Output directory (default: mastered)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show debug output')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Show only warnings and errors')

    args = parser.parse_args()

    setup_logging(__name__, verbose=args.verbose, quiet=args.quiet)

    reference_path = Path(args.reference)
    if not reference_path.exists():
        logger.error("Reference file not found: %s", reference_path)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("REFERENCE-BASED MASTERING")
    print("=" * 60)
    print(f"Reference: {reference_path.name}")
    print(f"Output: {output_dir}/")
    print("=" * 60)
    print()

    if args.target:
        # Single file mode
        target_path = Path(args.target)
        if not target_path.exists():
            logger.error("Target file not found: %s", target_path)
            sys.exit(1)

        output_path = output_dir / target_path.name
        logger.info("Processing: %s", target_path.name)
        master_with_reference(target_path, reference_path, output_path)
    else:
        # Batch mode - process all WAVs in current directory
        # Compare resolved paths so the reference is excluded regardless of
        # how --reference was supplied (absolute, './'-prefixed, or relative);
        # glob output is always relative to '.', so a lexical compare misses
        # an absolute --reference and re-masters it as its own target (#409).
        reference_resolved = reference_path.resolve()
        wav_files = sorted([f for f in Path('.').glob('*.wav')
                           if 'venv' not in str(f)
                           and f.resolve() != reference_resolved])

        if not wav_files:
            logger.error("No WAV files found in current directory")
            sys.exit(1)

        logger.info("Found %d tracks to process", len(wav_files))
        print()

        progress = ProgressBar(len(wav_files), prefix="Mastering")
        for i, wav_file in enumerate(wav_files, 1):
            progress.update(wav_file.name)
            logger.info("[%d/%d] Processing: %s", i, len(wav_files), wav_file.name)
            output_path = output_dir / wav_file.name
            try:
                master_with_reference(wav_file, reference_path, output_path)
            except Exception as e:
                logger.error("  Error: %s", e)
            print()

    print("=" * 60)
    print(f"Mastered files written to: {output_dir.absolute()}/")
    print()
    print("Tip: Run analyze_tracks.py in the output folder to verify results")


if __name__ == '__main__':
    main()
