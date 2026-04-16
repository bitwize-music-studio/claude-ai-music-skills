"""ADM (Apple Digital Masters) inter-sample clip validation (#290 step 9).

Encodes each mastered WAV to AAC and decodes back, then scans the decoded
PCM for samples exceeding the true-peak ceiling. Any excess indicates an
inter-sample peak introduced by the codec.

Encoder selection (adm_aac_encoder config key):
  - "aac"       → ffmpeg native AAC (default; works on Linux/CI/macOS)
  - "afconvert" → macOS afconvert preferred, falls back to ffmpeg if absent
  - "libfdk_aac"→ ffmpeg libfdk_aac (non-free ffmpeg build required)
"""

from __future__ import annotations

import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

# ffmpeg encode/decode of a typical ~5-minute master finishes in seconds; a
# 120s cap catches a hung subprocess without false-alarming on slow hosts.
_FFMPEG_TIMEOUT_SEC = 120


class ADMValidationError(RuntimeError):
    """Raised when ADM validation cannot proceed (missing file, ffmpeg error)."""


def _ffmpeg_encode_decode(
    input_path: Path,
    *,
    encoder: str,
    bitrate_kbps: int = 256,
) -> tuple[np.ndarray, int]:
    """Encode WAV→AAC via ffmpeg, decode back, return (float32 samples, rate)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        aac_path = Path(tmpdir) / "encoded.m4a"
        decoded_path = Path(tmpdir) / "decoded.wav"

        enc_cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-c:a", encoder, "-b:a", f"{bitrate_kbps}k",
            str(aac_path),
        ]
        try:
            enc = subprocess.run(
                enc_cmd, capture_output=True, text=True,
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
        except FileNotFoundError as exc:
            raise ADMValidationError(f"ffmpeg not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ADMValidationError(
                f"ffmpeg encode timed out after {_FFMPEG_TIMEOUT_SEC}s "
                f"for {input_path.name}"
            ) from exc
        if enc.returncode != 0:
            raise ADMValidationError(
                f"ffmpeg encode failed for {input_path.name}: {enc.stderr[-500:]}"
            )

        dec_cmd = [
            "ffmpeg", "-y", "-i", str(aac_path),
            "-c:a", "pcm_f32le", str(decoded_path),
        ]
        try:
            dec = subprocess.run(
                dec_cmd, capture_output=True, text=True,
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
        except FileNotFoundError as exc:
            raise ADMValidationError(f"ffmpeg not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ADMValidationError(
                f"ffmpeg decode timed out after {_FFMPEG_TIMEOUT_SEC}s "
                f"for {input_path.name}"
            ) from exc
        if dec.returncode != 0:
            raise ADMValidationError(
                f"ffmpeg decode failed for {input_path.name}: {dec.stderr[-500:]}"
            )

        data, rate = sf.read(str(decoded_path), dtype="float32")
        return data, int(rate)


def _afconvert_encode_decode(input_path: Path) -> tuple[np.ndarray, int, str]:
    """Encode WAV→AAC via afconvert (macOS), decode via ffmpeg, return (samples, rate, encoder_name).

    Returns ``"afconvert"`` as the encoder name when afconvert succeeds, or
    ``"aac"`` when it falls back to ffmpeg.
    """
    try:
        subprocess.run(
            ["afconvert", "--help"],
            capture_output=True, check=True,
            timeout=_FFMPEG_TIMEOUT_SEC,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # afconvert not available — fall back to ffmpeg
        data, rate = _ffmpeg_encode_decode(input_path, encoder="aac")
        return data, rate, "aac"

    with tempfile.TemporaryDirectory() as tmpdir:
        aac_path = Path(tmpdir) / "encoded.m4a"
        decoded_path = Path(tmpdir) / "decoded.wav"

        enc_cmd = [
            "afconvert",
            "-f", "m4af",
            "-d", "aac",
            "-b", "262144",  # 256 kbps in bits/s
            str(input_path),
            str(aac_path),
        ]
        try:
            enc = subprocess.run(
                enc_cmd, capture_output=True, text=True,
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            # afconvert hung — fall back to ffmpeg
            data, rate = _ffmpeg_encode_decode(input_path, encoder="aac")
            return data, rate, "aac"
        if enc.returncode != 0:
            # afconvert failed — fall back to ffmpeg
            data, rate = _ffmpeg_encode_decode(input_path, encoder="aac")
            return data, rate, "aac"

        dec_cmd = [
            "ffmpeg", "-y", "-i", str(aac_path),
            "-c:a", "pcm_f32le", str(decoded_path),
        ]
        try:
            dec = subprocess.run(
                dec_cmd, capture_output=True, text=True,
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as exc:
            raise ADMValidationError(
                f"ffmpeg decode after afconvert timed out after "
                f"{_FFMPEG_TIMEOUT_SEC}s"
            ) from exc
        if dec.returncode != 0:
            raise ADMValidationError(
                f"ffmpeg decode after afconvert failed: {dec.stderr[-500:]}"
            )

        data, rate = sf.read(str(decoded_path), dtype="float32")
        return data, int(rate), "afconvert"


def check_aac_intersample_clips(
    input_path: Path | str,
    *,
    encoder: str = "aac",
    ceiling_db: float = -1.0,
    bitrate_kbps: int = 256,
) -> dict[str, Any]:
    """Encode input WAV to AAC, decode, scan for inter-sample peaks.

    Args:
        input_path:   Path to a mastered WAV file.
        encoder:      AAC encoder to use ("aac", "afconvert", "libfdk_aac").
        ceiling_db:   True-peak ceiling in dBTP (default -1.0).
        bitrate_kbps: AAC bitrate in kbps (default 256).

    Returns:
        Dict with keys: filename, encoder_used, clip_count,
        peak_db_decoded, ceiling_db, clips_found.

    Raises:
        ADMValidationError: Input file missing or encode/decode fails.
    """
    input_path = Path(input_path)
    if not input_path.is_file():
        raise ADMValidationError(f"Input file not found: {input_path}")

    encoder_used = encoder
    if encoder == "afconvert":
        data, _rate, encoder_used = _afconvert_encode_decode(input_path)
    elif encoder in ("aac", "libfdk_aac"):
        data, _rate = _ffmpeg_encode_decode(
            input_path, encoder=encoder, bitrate_kbps=bitrate_kbps
        )
    else:
        # Unknown encoder — try as ffmpeg codec name
        data, _rate = _ffmpeg_encode_decode(
            input_path, encoder=encoder, bitrate_kbps=bitrate_kbps
        )

    ceiling_linear = 10.0 ** (ceiling_db / 20.0)
    peak_linear = float(np.max(np.abs(data)))
    # Clamp silent input to -120 dBTP — float("-inf") serializes as -Infinity
    # in Python's json.dumps, which strict JSON parsers reject.
    peak_db = float(20.0 * np.log10(peak_linear)) if peak_linear > 0 else -120.0
    clip_count = int(np.sum(np.abs(data) > ceiling_linear))

    return {
        "filename":        input_path.name,
        "encoder_used":    encoder_used,
        "clip_count":      clip_count,
        "peak_db_decoded": round(peak_db, 2),
        "ceiling_db":      ceiling_db,
        "clips_found":     clip_count > 0,
    }


def render_adm_validation_markdown(
    album_slug: str,
    results: list[dict[str, Any]],
    *,
    encoder_used: str,
    ceiling_db: float,
) -> str:
    """Render ADM_VALIDATION.md content for the mastered album."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    clips_total = sum(r.get("clip_count", 0) for r in results)
    overall = "PASS" if clips_total == 0 else "FAIL"

    lines = [
        f"# ADM Validation Report — {album_slug}",
        "",
        f"Generated: {now}  ",
        f"Encoder: `{encoder_used}`  ",
        f"Ceiling: {ceiling_db} dBTP  ",
        f"Overall: **{overall}**",
        "",
        "| Track | Peak (decoded) | Clips | Result |",
        "|-------|---------------|-------|--------|",
    ]
    for r in results:
        verdict = "FAIL ❌" if r.get("clips_found") else "PASS ✅"
        peak = f"{r['peak_db_decoded']:.2f} dBTP"
        lines.append(
            f"| {r['filename']} | {peak} | {r['clip_count']} | {verdict} |"
        )

    if clips_total > 0:
        lines += [
            "",
            f"> ⚠️ **{clips_total} inter-sample peak(s) detected** across "
            f"{sum(1 for r in results if r.get('clips_found'))} track(s). "
            f"Tighten true-peak ceiling by 0.5 dB and re-master.",
        ]
    return "\n".join(lines) + "\n"
