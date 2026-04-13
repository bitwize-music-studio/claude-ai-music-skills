#!/usr/bin/env python3
"""Unit tests for tools/mastering/codec_preview.py — AAC preview rendering."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.codec_preview import (
    CodecPreviewError,
    render_aac_preview,
)


def _write_test_wav(path: Path, freq: float = 440.0, duration: float = 1.5, rate: int = 44100) -> None:
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = 0.3 * np.sin(2 * np.pi * freq * t)
    stereo = np.column_stack([mono, mono]).astype(np.float32)
    sf.write(str(path), stereo, rate, subtype="PCM_16")


ffmpeg_available = shutil.which("ffmpeg") is not None
skip_if_no_ffmpeg = pytest.mark.skipif(
    not ffmpeg_available, reason="ffmpeg not installed"
)


class TestRenderAacPreview:
    @skip_if_no_ffmpeg
    def test_writes_m4a_at_output_path(self, tmp_path):
        in_wav = tmp_path / "in.wav"
        out_m4a = tmp_path / "out.aac.m4a"
        _write_test_wav(in_wav)

        result = render_aac_preview(in_wav, out_m4a, bitrate_kbps=128)

        assert out_m4a.exists()
        assert out_m4a.stat().st_size > 0
        assert result["output_path"] == str(out_m4a)
        assert result["bitrate_kbps"] == 128

    @skip_if_no_ffmpeg
    def test_output_is_valid_aac_container(self, tmp_path):
        in_wav = tmp_path / "in.wav"
        out_m4a = tmp_path / "out.aac.m4a"
        _write_test_wav(in_wav)
        render_aac_preview(in_wav, out_m4a, bitrate_kbps=128)

        # ffprobe should identify it as AAC audio in an MP4 container
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name",
             "-of", "default=noprint_wrappers=1:nokey=1", str(out_m4a)],
            capture_output=True, text=True,
        )
        assert probe.returncode == 0
        assert "aac" in probe.stdout.strip().lower()

    @skip_if_no_ffmpeg
    def test_custom_bitrate_honored(self, tmp_path):
        """Higher bitrate should produce a larger file for the same source."""
        in_wav = tmp_path / "in.wav"
        lo = tmp_path / "lo.aac.m4a"
        hi = tmp_path / "hi.aac.m4a"
        _write_test_wav(in_wav, duration=3.0)

        render_aac_preview(in_wav, lo, bitrate_kbps=64)
        render_aac_preview(in_wav, hi, bitrate_kbps=256)

        assert hi.stat().st_size > lo.stat().st_size

    def test_missing_input_raises(self, tmp_path):
        out = tmp_path / "out.aac.m4a"
        with pytest.raises(CodecPreviewError, match="does not exist"):
            render_aac_preview(tmp_path / "nope.wav", out)

    def test_creates_output_directory(self, tmp_path):
        in_wav = tmp_path / "in.wav"
        nested_out = tmp_path / "deep" / "nested" / "out.aac.m4a"
        _write_test_wav(in_wav)
        if not ffmpeg_available:
            pytest.skip("ffmpeg not installed")
        render_aac_preview(in_wav, nested_out, bitrate_kbps=128)
        assert nested_out.exists()
        assert nested_out.parent.is_dir()

    def test_rejects_invalid_bitrate(self, tmp_path):
        in_wav = tmp_path / "in.wav"
        out = tmp_path / "out.aac.m4a"
        _write_test_wav(in_wav)
        with pytest.raises(CodecPreviewError, match="bitrate"):
            render_aac_preview(in_wav, out, bitrate_kbps=0)
        with pytest.raises(CodecPreviewError, match="bitrate"):
            render_aac_preview(in_wav, out, bitrate_kbps=-64)
