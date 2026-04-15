"""Tests for per-stem polished WAV output from mix_track_stems (#290)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _write_stem(path: Path, amplitude: float = 0.1) -> Path:
    n = int(44100 * 1.0)
    data = (amplitude * np.sin(2 * np.pi * 440 * np.arange(n) / 44100)).astype(np.float32)
    sf.write(str(path), np.column_stack([data, data]), 44100, subtype="PCM_16")
    return path


def test_mix_track_stems_writes_vocals_to_stem_output_dir(tmp_path: Path) -> None:
    """When stem_output_dir is set, vocals.wav is written there."""
    from tools.mixing.mix_tracks import mix_track_stems

    stems_dir = tmp_path / "stems"
    stems_dir.mkdir()
    vocals_path = _write_stem(stems_dir / "vocals.wav")
    drums_path = _write_stem(stems_dir / "drums.wav")

    stem_output_dir = tmp_path / "polished" / "01-track"
    stem_output_dir.mkdir(parents=True)
    output_path = tmp_path / "polished" / "01-track.wav"

    result = mix_track_stems(
        {"vocals": str(vocals_path), "drums": str(drums_path)},
        output_path,
        stem_output_dir=stem_output_dir,
    )

    assert (stem_output_dir / "vocals.wav").exists()
    data, rate = sf.read(str(stem_output_dir / "vocals.wav"))
    assert data.size > 0


def test_mix_track_stems_no_stem_output_dir_unchanged(tmp_path: Path) -> None:
    """Without stem_output_dir, behavior is unchanged (no per-stem files written)."""
    from tools.mixing.mix_tracks import mix_track_stems

    stems_dir = tmp_path / "stems"
    stems_dir.mkdir()
    _write_stem(stems_dir / "vocals.wav")
    output_path = tmp_path / "polished" / "01-track.wav"
    output_path.parent.mkdir(parents=True)

    result = mix_track_stems(
        {"vocals": str(stems_dir / "vocals.wav")},
        output_path,
        # no stem_output_dir
    )

    # polished/ should only have the single output file, no subdirectory
    files = list((tmp_path / "polished").iterdir())
    assert len(files) == 1
    assert files[0].name == "01-track.wav"


def test_mix_track_stems_dry_run_does_not_write_stems(tmp_path: Path) -> None:
    """In dry_run mode, per-stem WAVs are not written even when dir is set."""
    from tools.mixing.mix_tracks import mix_track_stems

    stems_dir = tmp_path / "stems"
    stems_dir.mkdir()
    _write_stem(stems_dir / "vocals.wav")

    stem_output_dir = tmp_path / "polished" / "01-track"
    stem_output_dir.mkdir(parents=True)
    output_path = tmp_path / "polished" / "01-track.wav"

    mix_track_stems(
        {"vocals": str(stems_dir / "vocals.wav")},
        output_path,
        stem_output_dir=stem_output_dir,
        dry_run=True,
    )

    assert not (stem_output_dir / "vocals.wav").exists()
