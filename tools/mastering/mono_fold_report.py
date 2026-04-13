#!/usr/bin/env python3
"""Render a MONO_FOLD.md markdown report from mono_fold_metrics() output."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_BAND_ORDER = ("sub_bass", "bass", "low_mid", "mid", "high_mid", "high", "air")


def _verdict_badge(verdict: str) -> str:
    return {
        "PASS": "PASS",
        "WARN": "WARN",
        "FAIL": "FAIL",
    }.get(verdict, verdict)


def _fmt_db(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _band_status(delta_db: float | None, band_fail_db: float) -> str:
    if delta_db is None:
        return "—"
    if delta_db <= -band_fail_db:
        return "FAIL"
    if delta_db <= -(band_fail_db / 2.0):
        return "WARN"
    return "PASS"


def render_mono_fold_markdown(
    track_name: str,
    metrics: dict[str, Any],
    sample_filename: str | None,
) -> str:
    """Produce the MONO_FOLD.md content for a single track.

    Args:
        track_name: Stem/slug of the track (e.g., "01-opening").
        metrics: The dict returned by mono_fold_metrics().
        sample_filename: Filename of the `.mono.wav` sibling sample, or None
            if the audio sample was not written.

    Returns:
        Markdown string (no trailing newline guaranteed).
    """
    verdict = metrics.get("verdict", "PASS")
    badge = _verdict_badge(verdict)
    thresholds = metrics.get("thresholds", {})
    band_fail_db = float(thresholds.get("band_drop_fail_db", 6.0))
    lufs_warn = float(thresholds.get("lufs_warn_db", 3.0))
    vocal_warn = float(thresholds.get("vocal_warn_db", 2.0))
    corr_warn = float(thresholds.get("correlation_warn", 0.3))

    lufs = metrics.get("lufs", {})
    vocal = metrics.get("vocal_rms", {})
    corr = metrics.get("stereo_correlation")
    worst = metrics.get("worst_band", {}) or {}

    lines: list[str] = []
    lines.append(f"# Mono Fold-Down Report — {track_name}")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"**Source**: `mastered/{track_name}.wav`")
    lines.append(f"**Verdict**: {badge} ({verdict})")
    lines.append("")

    # Summary deltas
    lines.append("## Deltas (mono − stereo)")
    lines.append("")
    lines.append("| Metric | Stereo | Mono | Delta | Threshold | Status |")
    lines.append("|---|---|---|---|---|---|")

    lufs_delta = lufs.get("delta_db")
    lufs_status = (
        "PASS" if lufs_delta is None or abs(lufs_delta) <= lufs_warn else "WARN"
    )
    lines.append(
        f"| Integrated LUFS | {_fmt_db(lufs.get('stereo'))} LU | "
        f"{_fmt_db(lufs.get('mono'))} LU | {_fmt_db(lufs_delta)} dB | "
        f"warn ±{lufs_warn:.1f} dB | {lufs_status} |"
    )

    vocal_delta = vocal.get("delta_db")
    vocal_status = (
        "PASS" if vocal_delta is None or abs(vocal_delta) <= vocal_warn else "WARN"
    )
    lines.append(
        f"| Vocal RMS (1–4 kHz) | {_fmt_db(vocal.get('stereo_db'))} dB | "
        f"{_fmt_db(vocal.get('mono_db'))} dB | {_fmt_db(vocal_delta)} dB | "
        f"warn ±{vocal_warn:.1f} dB | {vocal_status} |"
    )

    corr_status = (
        "PASS" if corr is None or corr >= corr_warn else "WARN"
    )
    corr_str = _fmt_db(corr, digits=2) if corr is not None else "—"
    lines.append(
        f"| Stereo correlation | {corr_str} | — | — | warn <{corr_warn:.2f} | {corr_status} |"
    )
    lines.append("")

    # Per-band table
    lines.append("## Per-band deltas")
    lines.append("")
    lines.append(
        f"Threshold: any band drop > **{band_fail_db:.1f} dB** → hard FAIL."
    )
    lines.append("")
    lines.append("| Band | Hz range | Stereo dB | Mono dB | Delta dB | Status |")
    lines.append("|---|---|---|---|---|---|")
    band_deltas = metrics.get("band_deltas", {})
    for band in _BAND_ORDER:
        entry = band_deltas.get(band)
        if not entry:
            continue
        delta = entry.get("delta_db")
        status = _band_status(delta, band_fail_db)
        hz_low = entry.get("hz_low", 0.0)
        hz_high = entry.get("hz_high", 0.0)
        lines.append(
            f"| `{band}` | {hz_low:.0f}–{hz_high:.0f} | "
            f"{_fmt_db(entry.get('stereo_db'))} | {_fmt_db(entry.get('mono_db'))} | "
            f"{_fmt_db(delta)} | {status} |"
        )
    lines.append("")

    # Worst band / fail call-out
    if metrics.get("band_drop_fail"):
        worst_name = worst.get("name") or "unknown"
        worst_delta = worst.get("delta_db")
        worst_entry = band_deltas.get(worst_name, {})
        hz_low = worst_entry.get("hz_low", 0.0)
        hz_high = worst_entry.get("hz_high", 0.0)
        lines.append("## Phase cancellation detected")
        lines.append("")
        lines.append(
            f"Band `{worst_name}` ({hz_low:.0f}–{hz_high:.0f} Hz) dropped "
            f"{_fmt_db(worst_delta)} dB when folded to mono — above the "
            f"{band_fail_db:.1f} dB hard-fail threshold. Listen to the "
            f".mono sample on a phone speaker or Echo to confirm which "
            f"elements disappear."
        )
        lines.append("")

    # Notes
    lines.append("## Notes")
    lines.append("")
    if sample_filename:
        lines.append(f"- Audio sample: `{sample_filename}`")
    lines.append("- Audition on a phone speaker, single Echo, or a club mono sum.")
    lines.append("- This file is QC-only — not uploaded to streaming platforms.")

    return "\n".join(lines) + "\n"
