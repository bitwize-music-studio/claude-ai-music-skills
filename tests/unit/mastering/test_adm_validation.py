"""Tests for tools/mastering/adm_validation.py (#290 step 9)."""

from __future__ import annotations

import sys
import math
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import shutil

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_ffmpeg_available = shutil.which("ffmpeg") is not None
requires_ffmpeg = pytest.mark.skipif(
    not _ffmpeg_available,
    reason="ffmpeg not installed",
)


def _write_sine(path: Path, *, amplitude: float = 0.3,
                duration: float = 1.0, rate: int = 44100) -> Path:
    """Write a stereo 440 Hz sine to path. Returns path."""
    n = int(duration * rate)
    t = np.arange(n) / rate
    mono = amplitude * np.sin(2 * math.pi * 440.0 * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, rate, subtype="PCM_24")
    return path


@requires_ffmpeg
def test_check_aac_intersample_clips_clean_pass(tmp_path: Path) -> None:
    """Quiet sine (-12 dBTP) survives AAC encoding without clipping."""
    pytest.importorskip("subprocess")
    from tools.mastering.adm_validation import check_aac_intersample_clips
    wav = _write_sine(tmp_path / "clean.wav", amplitude=0.25)  # ~-12 dBTP
    result = check_aac_intersample_clips(wav, ceiling_db=-1.0)
    assert result["filename"] == "clean.wav"
    assert result["clips_found"] is False
    assert result["clip_count"] == 0
    assert "encoder_used" in result
    assert "peak_db_decoded" in result


@requires_ffmpeg
def test_check_aac_intersample_clips_result_keys(tmp_path: Path) -> None:
    """Result dict has all required keys."""
    from tools.mastering.adm_validation import check_aac_intersample_clips
    wav = _write_sine(tmp_path / "test.wav", amplitude=0.3)
    result = check_aac_intersample_clips(wav, ceiling_db=-1.0)
    expected_keys = {
        "filename", "encoder_used", "clip_count",
        "peak_db_decoded", "ceiling_db", "clips_found",
    }
    assert expected_keys <= result.keys()


def test_check_aac_intersample_clips_missing_file_raises(tmp_path: Path) -> None:
    """ADMValidationError raised when input file does not exist."""
    from tools.mastering.adm_validation import ADMValidationError, check_aac_intersample_clips
    with pytest.raises(ADMValidationError, match="not found"):
        check_aac_intersample_clips(tmp_path / "missing.wav", ceiling_db=-1.0)


@requires_ffmpeg
def test_check_aac_intersample_clips_encoder_recorded(tmp_path: Path) -> None:
    """encoder_used reflects the encoder argument."""
    from tools.mastering.adm_validation import check_aac_intersample_clips
    wav = _write_sine(tmp_path / "enc.wav", amplitude=0.2)
    result = check_aac_intersample_clips(wav, ceiling_db=-1.0, encoder="aac")
    assert isinstance(result["encoder_used"], str)
    assert len(result["encoder_used"]) > 0


def test_render_adm_validation_markdown_all_pass() -> None:
    """Markdown renders PASS rows correctly."""
    from tools.mastering.adm_validation import render_adm_validation_markdown
    results = [
        {"filename": "01.wav", "peak_db_decoded": -1.5, "clip_count": 0,
         "clips_found": False, "ceiling_db": -1.0, "encoder_used": "aac"},
        {"filename": "02.wav", "peak_db_decoded": -1.8, "clip_count": 0,
         "clips_found": False, "ceiling_db": -1.0, "encoder_used": "aac"},
    ]
    md = render_adm_validation_markdown("my-album", results, encoder_used="aac", ceiling_db=-1.0)
    assert "ADM Validation" in md
    assert "PASS" in md
    assert "FAIL" not in md
    assert "01.wav" in md


@requires_ffmpeg
def test_check_aac_intersample_clips_silent_audio(tmp_path: Path) -> None:
    """Silent audio (all zeros) produces peak_db_decoded of -inf, no clips."""
    import soundfile as sf
    from tools.mastering.adm_validation import check_aac_intersample_clips
    import math

    silent_wav = tmp_path / "silent.wav"
    sf.write(str(silent_wav), np.zeros((44100, 2), dtype=np.float32), 44100, subtype="PCM_16")
    result = check_aac_intersample_clips(silent_wav, ceiling_db=-1.0)
    assert result["clips_found"] is False
    assert result["clip_count"] == 0
    # Silent audio: peak_db should be -inf (or a very large negative after AAC decode introduces noise)
    # AAC encoding of silence may introduce tiny noise floor - just check no clips
    assert isinstance(result["peak_db_decoded"], float)


def test_render_adm_validation_markdown_clip_fail() -> None:
    """Markdown renders FAIL for tracks with clips."""
    from tools.mastering.adm_validation import render_adm_validation_markdown
    results = [
        {"filename": "01.wav", "peak_db_decoded": -0.2, "clip_count": 5,
         "clips_found": True, "ceiling_db": -1.0, "encoder_used": "aac"},
    ]
    md = render_adm_validation_markdown("my-album", results, encoder_used="aac", ceiling_db=-1.0)
    assert "FAIL" in md
    assert "5" in md
