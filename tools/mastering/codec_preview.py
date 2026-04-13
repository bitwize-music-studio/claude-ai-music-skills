#!/usr/bin/env python3
"""Render a 128 kbps (configurable) AAC preview from a mastered WAV.

The output `.aac.m4a` is for operator Bluetooth-path listening only — it is
never uploaded to DistroKid. See issue #296.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodecPreviewError(RuntimeError):
    """Raised when the codec preview cannot be produced."""


def render_aac_preview(
    input_wav: Path | str,
    output_m4a: Path | str,
    bitrate_kbps: int = 128,
) -> dict[str, Any]:
    """Encode a WAV to AAC/M4A at the given bitrate using ffmpeg.

    Args:
        input_wav: Path to a source WAV (typically from `mastered/`).
        output_m4a: Destination `.aac.m4a` path. Parent directory is created.
        bitrate_kbps: AAC bitrate in kbps. Must be > 0.

    Returns:
        Dict with output_path (str), bitrate_kbps (int), output_bytes (int).

    Raises:
        CodecPreviewError: on missing ffmpeg, missing input, invalid bitrate,
            or a failed ffmpeg invocation.
    """
    if bitrate_kbps <= 0:
        raise CodecPreviewError(f"Invalid bitrate {bitrate_kbps} — must be > 0 kbps")

    in_path = Path(input_wav)
    out_path = Path(output_m4a)

    if not in_path.exists():
        raise CodecPreviewError(f"Input WAV does not exist: {in_path}")

    if shutil.which("ffmpeg") is None:
        raise CodecPreviewError("ffmpeg not found on PATH — install it first")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(in_path),
        "-c:a", "aac",
        "-b:a", f"{bitrate_kbps}k",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out_path.exists():
        raise CodecPreviewError(
            f"ffmpeg failed encoding {in_path.name}: {result.stderr.strip()}"
        )

    return {
        "output_path": str(out_path),
        "bitrate_kbps": int(bitrate_kbps),
        "output_bytes": out_path.stat().st_size,
    }
