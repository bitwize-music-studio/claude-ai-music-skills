#!/usr/bin/env python3
"""Technical audio QC checks for pre/post mastering validation."""

import logging
import os
import sys
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.shared.logging_config import setup_logging
from tools.shared.progress import ProgressBar

logger = logging.getLogger(__name__)

# All available checks
ALL_CHECKS = ["format", "mono", "phase", "clipping", "clicks", "silence", "spectral"]


def _check_format(info):
    """Validate sample rate, bit depth, channels, and format."""
    rate = info.samplerate
    channels = info.channels
    subtype = info.subtype  # e.g. 'PCM_16', 'PCM_24', 'FLOAT'
    fmt = info.format  # e.g. 'WAV', 'FLAC'

    issues = []
    status = "PASS"

    # Format check
    if fmt != "WAV":
        issues.append(f"Format is {fmt}, expected WAV")
        status = "FAIL"

    # Sample rate
    if rate not in (44100, 48000):
        issues.append(f"Sample rate {rate} Hz, expected 44100 or 48000")
        status = "FAIL"

    # Bit depth
    valid_subtypes = {"PCM_16", "PCM_24", "FLOAT", "DOUBLE"}
    if subtype not in valid_subtypes:
        issues.append(f"Bit depth {subtype} not standard")
        status = "FAIL"

    # Channels
    if channels == 1:
        if status != "FAIL":
            status = "WARN"
        issues.append("Mono file (auto-fixable)")
    elif channels != 2:
        issues.append(f"{channels} channels, expected stereo")
        status = "FAIL"

    detail = "; ".join(issues) if issues else f"{subtype} {rate}Hz {channels}ch {fmt}"
    return {
        "status": status,
        "value": f"{subtype} {rate}Hz {channels}ch",
        "detail": detail,
    }


def _check_mono_compat(data):
    """Check mono compatibility by comparing summed L+R energy to stereo."""
    if data.shape[1] < 2:
        return {"status": "PASS", "value": "0.0 dB", "detail": "Mono file, N/A"}

    left = data[:, 0]
    right = data[:, 1]
    mono = left + right

    stereo_energy = np.sum(left**2) + np.sum(right**2)
    mono_energy = np.sum(mono**2)
    # Normalized: mono sum of stereo has 2x amplitude if perfectly correlated
    # Compare mono energy to expected 2x stereo energy
    if stereo_energy == 0:
        return {"status": "PASS", "value": "0.0 dB", "detail": "Silent file"}

    # Energy ratio: mono_energy / (2 * stereo_energy) should be ~1.0 for mono-safe
    ratio = mono_energy / (2 * stereo_energy)
    if ratio > 0:
        loss_db = abs(10 * np.log10(ratio))
    else:
        loss_db = 99.0

    if loss_db < 1.0:
        status = "PASS"
    elif loss_db < 3.0:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "status": status,
        "value": f"{loss_db:.1f} dB loss",
        "detail": f"Mono fold energy {'OK' if status == 'PASS' else f'loss of {loss_db:.1f} dB'}",
    }


def _check_phase(data, rate):
    """Check phase correlation between L and R channels."""
    if data.shape[1] < 2:
        return {"status": "PASS", "value": "1.00", "detail": "Mono file, N/A"}

    left = data[:, 0]
    right = data[:, 1]

    # Compute correlation in windows to get a stable average
    window_size = int(rate * 0.5)  # 500ms windows
    correlations = []

    for start in range(0, len(left) - window_size, window_size):
        chunk_l = left[start:start + window_size]
        chunk_r = right[start:start + window_size]
        # Skip silent windows
        if np.max(np.abs(chunk_l)) < 1e-6 or np.max(np.abs(chunk_r)) < 1e-6:
            continue
        corr = np.corrcoef(chunk_l, chunk_r)[0, 1]
        if not np.isnan(corr):
            correlations.append(corr)

    if not correlations:
        return {"status": "PASS", "value": "N/A", "detail": "No significant audio to measure"}

    mean_corr = float(np.mean(correlations))

    if mean_corr > 0.5:
        status = "PASS"
    elif mean_corr >= 0.0:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "status": status,
        "value": f"{mean_corr:.2f}",
        "detail": f"Phase correlation {'good' if status == 'PASS' else 'out of phase' if status == 'FAIL' else 'weak — may have mono issues'}",
    }


def _check_clipping(data):
    """Detect consecutive samples at ±0.99+ (clipping regions)."""
    clipped = np.any(np.abs(data) >= 0.99, axis=1) if data.ndim > 1 else np.abs(data) >= 0.99

    # Find runs of consecutive clipped samples (>= 3 consecutive = a region)
    regions = 0
    run_length = 0
    for val in clipped:
        if val:
            run_length += 1
        else:
            if run_length >= 3:
                regions += 1
            run_length = 0
    if run_length >= 3:
        regions += 1

    if regions == 0:
        status = "PASS"
    elif regions <= 3:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "status": status,
        "value": f"{regions} regions",
        "detail": f"{'No clipping detected' if regions == 0 else f'{regions} clipping region(s) found'}",
    }


def _check_clicks(data, rate):
    """Detect clicks/pops using sliding RMS window comparison."""
    # Work with mono sum for detection
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data

    # Sliding RMS window: 10ms
    window_samples = max(int(rate * 0.01), 1)
    hop = window_samples

    click_count = 0
    for start in range(0, len(mono) - window_samples, hop):
        window = mono[start:start + window_samples]
        rms = np.sqrt(np.mean(window**2))
        if rms < 1e-8:
            continue

        peak = np.max(np.abs(window))
        if peak > 6.0 * rms:
            click_count += 1

    if click_count == 0:
        status = "PASS"
    elif click_count <= 3:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "status": status,
        "value": f"{click_count} found",
        "detail": f"{'No clicks/pops' if click_count == 0 else f'{click_count} transient spike(s) detected'}",
    }


def _check_silence(data, rate):
    """Check for excessive leading, trailing, or internal silence."""
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data

    # Threshold: -60 dBFS
    threshold = 10 ** (-60 / 20)
    is_silent = np.abs(mono) < threshold

    total_samples = len(mono)
    issues = []
    status = "PASS"

    # Leading silence
    leading = 0
    for s in is_silent:
        if s:
            leading += 1
        else:
            break
    leading_sec = leading / rate
    if leading_sec > 0.5:
        status = "FAIL"
        issues.append(f"Leading silence: {leading_sec:.1f}s")

    # Trailing silence
    trailing = 0
    for s in reversed(is_silent):
        if s:
            trailing += 1
        else:
            break
    trailing_sec = trailing / rate
    if trailing_sec > 5.0:
        if status != "FAIL":
            status = "WARN"
        issues.append(f"Trailing silence: {trailing_sec:.1f}s")
    elif trailing_sec > 3.0:
        if status != "FAIL":
            status = "WARN"
        issues.append(f"Trailing silence: {trailing_sec:.1f}s")

    # Internal silence gaps (> 0.5s)
    gap_threshold = int(rate * 0.5)
    # Skip leading/trailing for internal gap detection
    content_start = leading
    content_end = total_samples - trailing
    if content_end > content_start:
        interior = is_silent[content_start:content_end]
        gap_length = 0
        gap_count = 0
        for s in interior:
            if s:
                gap_length += 1
            else:
                if gap_length >= gap_threshold:
                    gap_count += 1
                gap_length = 0
        if gap_length >= gap_threshold:
            gap_count += 1
        if gap_count > 0:
            status = "FAIL"
            issues.append(f"{gap_count} internal gap(s) > 0.5s")

    detail = "; ".join(issues) if issues else "No silence issues"
    value = f"L:{leading_sec:.1f}s T:{trailing_sec:.1f}s"

    return {"status": status, "value": value, "detail": detail}


def _check_spectral(data, rate):
    """Check spectral balance for missing bands or excessive energy."""
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data

    freqs, psd = signal.welch(mono, rate, nperseg=8192)
    total_energy = np.sum(psd)
    if total_energy == 0:
        return {"status": "WARN", "value": "silent", "detail": "No spectral energy"}

    bands = {
        "sub_bass": (20, 60),
        "bass": (60, 250),
        "low_mid": (250, 500),
        "mid": (500, 2000),
        "high_mid": (2000, 6000),
        "high": (6000, 12000),
        "air": (12000, 20000),
    }

    band_pct = {}
    for name, (low, high) in bands.items():
        mask = (freqs >= low) & (freqs < high)
        band_pct[name] = (np.sum(psd[mask]) / total_energy) * 100

    issues = []
    status = "PASS"

    # Check sub-bass presence
    if band_pct["sub_bass"] < 1.0:
        issues.append(f"Sub-bass very low ({band_pct['sub_bass']:.1f}%)")
        status = "WARN"

    # Check tinniness (high_mid to mid ratio)
    if band_pct["mid"] > 0:
        tinniness = band_pct["high_mid"] / band_pct["mid"]
        if tinniness > 0.8:
            issues.append(f"High-mid spike (tinniness ratio {tinniness:.2f})")
            status = "FAIL" if tinniness > 1.2 else "WARN"

    # Check highs presence
    highs_total = band_pct["high"] + band_pct["air"]
    if highs_total < 1.0:
        issues.append(f"No highs ({highs_total:.1f}%)")
        if status != "FAIL":
            status = "WARN"

    detail = "; ".join(issues) if issues else "Balanced spectrum"
    bass_total = band_pct["sub_bass"] + band_pct["bass"]
    mid_total = band_pct["low_mid"] + band_pct["mid"]

    return {
        "status": status,
        "value": f"B:{bass_total:.0f}% M:{mid_total:.0f}% H:{highs_total:.0f}%",
        "detail": detail,
    }


def qc_track(filepath, checks=None):
    """Run QC checks on a single audio track.

    Args:
        filepath: Path to WAV file.
        checks: List of check names to run (default: all).
            Options: format, mono, phase, clipping, clicks, silence, spectral

    Returns:
        Dict with filename, per-check results, and overall verdict.
    """
    filepath = str(filepath)
    basename = os.path.basename(filepath)
    active_checks = checks or ALL_CHECKS

    info = sf.info(filepath)
    data, rate = sf.read(filepath)

    # Handle mono files — expand to 2ch for stereo checks
    if len(data.shape) == 1:
        data = np.column_stack([data, data])

    results = {}

    if "format" in active_checks:
        results["format"] = _check_format(info)

    if "mono" in active_checks:
        results["mono"] = _check_mono_compat(data)

    if "phase" in active_checks:
        results["phase"] = _check_phase(data, rate)

    if "clipping" in active_checks:
        results["clipping"] = _check_clipping(data)

    if "clicks" in active_checks:
        results["clicks"] = _check_clicks(data, rate)

    if "silence" in active_checks:
        results["silence"] = _check_silence(data, rate)

    if "spectral" in active_checks:
        results["spectral"] = _check_spectral(data, rate)

    # Overall verdict: worst status across all checks
    statuses = [r["status"] for r in results.values()]
    if "FAIL" in statuses:
        verdict = "FAIL"
    elif "WARN" in statuses:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return {
        "filename": basename,
        "checks": results,
        "verdict": verdict,
    }


def main():
    parser = argparse.ArgumentParser(description="Technical audio QC checks.")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to directory containing WAV files (default: current directory)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Show only warnings and errors")
    parser.add_argument(
        "-j", "--jobs", type=int, default=1, help="Parallel jobs (0=auto, default: 1)"
    )
    parser.add_argument(
        "--checks",
        type=str,
        default="",
        help=f"Comma-separated checks to run (default: all). Options: {', '.join(ALL_CHECKS)}",
    )
    args = parser.parse_args()

    setup_logging(__name__, verbose=args.verbose, quiet=args.quiet)

    wav_dir = Path(args.path).expanduser().resolve()
    if not wav_dir.exists():
        logger.error("Directory not found: %s", wav_dir)
        sys.exit(1)

    wav_files = sorted(wav_dir.glob("*.wav"))
    filterable = [f for f in wav_files if "venv" not in str(f)]

    if not filterable:
        logger.error("No WAV files found in %s", wav_dir)
        sys.exit(1)

    active_checks = None
    if args.checks:
        active_checks = [c.strip() for c in args.checks.split(",")]
        invalid = [c for c in active_checks if c not in ALL_CHECKS]
        if invalid:
            logger.error("Unknown checks: %s. Valid: %s", ", ".join(invalid), ", ".join(ALL_CHECKS))
            sys.exit(1)

    print("=" * 90)
    print("AUDIO QC CHECKS")
    print("=" * 90)
    print()

    workers = args.jobs if args.jobs > 0 else os.cpu_count()
    progress = ProgressBar(len(filterable), prefix="QC scanning")

    if workers == 1:
        results = []
        for wav_file in filterable:
            progress.update(wav_file.name)
            result = qc_track(str(wav_file), checks=active_checks)
            results.append(result)
    else:
        logger.info("Using %d parallel workers", workers)
        ordered = {}
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(qc_track, str(wf), active_checks): i
                for i, wf in enumerate(filterable)
            }
            for future in as_completed(futures):
                idx = futures[future]
                progress.update(filterable[idx].name)
                ordered[idx] = future.result()
        results = [ordered[i] for i in sorted(ordered)]

    # Determine which checks were run
    display_checks = active_checks or ALL_CHECKS

    # Print table header
    print()
    col_width = 8
    header = f"{'Track':<30}"
    for check in display_checks:
        header += f" {check:>{col_width}}"
    header += f"  {'VERDICT':>8}"
    print(header)
    print("-" * len(header))

    # Print rows
    for r in results:
        name = r["filename"][:29]
        row = f"{name:<30}"
        for check in display_checks:
            if check in r["checks"]:
                status = r["checks"][check]["status"]
            else:
                status = "-"
            row += f" {status:>{col_width}}"
        row += f"  {r['verdict']:>8}"
        print(row)

    # Summary
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    warned = sum(1 for r in results if r["verdict"] == "WARN")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    total = len(results)

    print("-" * len(header))
    print(f"\nSummary: {total} tracks — {passed} PASS, {warned} WARN, {failed} FAIL")

    # Print details for non-PASS checks
    issues_found = False
    for r in results:
        track_issues = [
            (check, info)
            for check, info in r["checks"].items()
            if info["status"] != "PASS"
        ]
        if track_issues:
            if not issues_found:
                print()
                print("=" * 90)
                print("ISSUES")
                print("=" * 90)
                issues_found = True
            print(f"\n  {r['filename']}:")
            for check, info in track_issues:
                print(f"    [{info['status']}] {check}: {info['detail']}")

    print()


if __name__ == "__main__":
    main()
