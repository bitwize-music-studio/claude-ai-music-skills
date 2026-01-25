#!/usr/bin/env python3
"""
Reference-Based Mastering Script
Uses matchering to match your tracks to a professionally mastered reference.
"""

import sys
import argparse
from pathlib import Path

try:
    import matchering as mg
except ImportError:
    print("Error: matchering not installed")
    print("Run: pip install matchering")
    sys.exit(1)


def master_with_reference(target_path, reference_path, output_path):
    """Master a single track using a reference.

    Args:
        target_path: Path to your track (WAV)
        reference_path: Path to professionally mastered reference (WAV)
        output_path: Path for output file
    """
    print(f"  Target: {target_path}")
    print(f"  Reference: {reference_path}")
    print(f"  Output: {output_path}")

    mg.process(
        target=str(target_path),
        reference=str(reference_path),
        results=[
            mg.pcm16(str(output_path)),
        ],
    )
    print(f"  Done!")


def main():
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

    args = parser.parse_args()

    reference_path = Path(args.reference)
    if not reference_path.exists():
        print(f"Error: Reference file not found: {reference_path}")
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
            print(f"Error: Target file not found: {target_path}")
            sys.exit(1)

        output_path = output_dir / target_path.name
        print(f"Processing: {target_path.name}")
        master_with_reference(target_path, reference_path, output_path)
    else:
        # Batch mode - process all WAVs in current directory
        wav_files = sorted([f for f in Path('.').glob('*.wav')
                           if 'mastering-env' not in str(f)
                           and f != reference_path])

        if not wav_files:
            print("No WAV files found in current directory")
            sys.exit(1)

        print(f"Found {len(wav_files)} tracks to process")
        print()

        for i, wav_file in enumerate(wav_files, 1):
            print(f"[{i}/{len(wav_files)}] Processing: {wav_file.name}")
            output_path = output_dir / wav_file.name
            try:
                master_with_reference(wav_file, reference_path, output_path)
            except Exception as e:
                print(f"  Error: {e}")
            print()

    print("=" * 60)
    print(f"Mastered files written to: {output_dir.absolute()}/")
    print()
    print("Tip: Run analyze_tracks.py in the output folder to verify results")


if __name__ == '__main__':
    main()
