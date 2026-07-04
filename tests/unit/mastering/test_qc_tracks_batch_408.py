#!/usr/bin/env python3
"""Regression tests for #408 — qc_tracks batch resilience to a bad file.

Both the serial and parallel QC batch paths in ``qc_tracks.main`` used to call
``qc_track`` / ``future.result()`` with no per-file guard, so a single corrupt
or unreadable WAV tore down the whole run: in serial mode the remaining files
were skipped, and in parallel mode the exception re-raised out of
``future.result()`` and aborted the pool after partial work.

The fix wraps each per-file call in a try/except that emits a per-track FAIL
row (matching qc_track's result shape) and keeps going, while still signalling
the failure through a non-zero exit.

Usage:
    python -m pytest tests/unit/mastering/test_qc_tracks_batch_408.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.qc_tracks import ALL_CHECKS
from tools.mastering.qc_tracks import main as qc_main


# ─── Helpers ──────────────────────────────────────────────────────────


def _pass_result(name: str) -> dict:
    """A well-formed all-PASS qc_track result for a good file."""
    return {
        "filename": name,
        "checks": {
            c: {"status": "PASS", "value": "ok", "detail": "ok"} for c in ALL_CHECKS
        },
        "verdict": "PASS",
    }


def _write_valid_wav(path: Path, rate: int = 44100, seconds: float = 0.2) -> None:
    """Write a small, well-formed stereo PCM_16 WAV that passes the format check."""
    n = int(rate * seconds)
    t = np.linspace(0, seconds, n, endpoint=False)
    mono = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float64)
    data = np.column_stack([mono, mono])
    sf.write(str(path), data, rate, subtype="PCM_16")


# ─── Tests ────────────────────────────────────────────────────────────


def test_serial_batch_continues_past_unreadable_file(tmp_path, monkeypatch, capsys):
    """Serial path: one file whose qc_track raises must not abort the batch.

    The good files on either side of the bad one still get results, the bad
    file gets a FAIL row surfacing the read error, and the run signals failure
    via a non-zero exit instead of dumping a traceback.
    """
    good1 = tmp_path / "01-good.wav"
    bad = tmp_path / "02-bad.wav"
    good2 = tmp_path / "03-good.wav"
    for p in (good1, bad, good2):
        p.touch()  # qc_track is mocked, so contents are irrelevant

    def mock_qc(filepath, checks=None, genre=None):
        if "bad" in Path(filepath).name:
            raise RuntimeError("corrupt WAV: could not read frames")
        return _pass_result(Path(filepath).name)

    monkeypatch.setattr("tools.mastering.qc_tracks.qc_track", mock_qc)
    monkeypatch.setattr(sys, "argv", ["qc_tracks", str(tmp_path), "-j", "1"])

    with pytest.raises(SystemExit) as excinfo:
        qc_main()

    assert excinfo.value.code == 1  # failure is signalled

    out = capsys.readouterr().out
    # Partial progress preserved — every file, including ones AFTER the bad one.
    assert "01-good.wav" in out
    assert "02-bad.wav" in out
    assert "03-good.wav" in out
    # The bad file renders as a FAIL row; good files as PASS.
    assert "3 tracks" in out
    assert "2 PASS" in out
    assert "1 FAIL" in out
    assert any("02-bad.wav" in line and "FAIL" in line for line in out.splitlines())
    # The read error is surfaced (not a raw traceback).
    assert "Could not read" in out


def test_parallel_batch_continues_past_corrupt_file(tmp_path, monkeypatch, capsys):
    """Parallel path: a genuinely corrupt WAV must not tear down the pool.

    Uses real files with -j 2 so ``future.result()`` re-raises soundfile's
    read error from the worker; the fix catches it per-future and keeps the
    other tracks' results.
    """
    _write_valid_wav(tmp_path / "01-good.wav")
    _write_valid_wav(tmp_path / "03-good.wav")
    # Garbage bytes with a .wav extension — libsndfile cannot parse it.
    (tmp_path / "02-bad.wav").write_bytes(b"this is definitely not audio \x00\xff" * 4)

    monkeypatch.setattr(
        sys, "argv", ["qc_tracks", str(tmp_path), "-j", "2", "--checks", "format"]
    )

    with pytest.raises(SystemExit) as excinfo:
        qc_main()

    assert excinfo.value.code == 1

    out = capsys.readouterr().out
    assert "01-good.wav" in out
    assert "02-bad.wav" in out
    assert "03-good.wav" in out
    assert "3 tracks" in out
    assert "2 PASS" in out
    assert "1 FAIL" in out
    assert any("02-bad.wav" in line and "FAIL" in line for line in out.splitlines())


def test_all_good_serial_completes_without_error_exit(tmp_path, monkeypatch, capsys):
    """Guard: when every file reads cleanly the run must NOT exit non-zero.

    Protects against the failure signal firing spuriously on a healthy batch.
    """
    for name in ("01-a.wav", "02-b.wav", "03-c.wav"):
        (tmp_path / name).touch()

    def mock_qc(filepath, checks=None, genre=None):
        return _pass_result(Path(filepath).name)

    monkeypatch.setattr("tools.mastering.qc_tracks.qc_track", mock_qc)
    monkeypatch.setattr(sys, "argv", ["qc_tracks", str(tmp_path), "-j", "1"])

    qc_main()  # must return normally — no SystemExit

    out = capsys.readouterr().out
    assert "3 tracks" in out
    assert "3 PASS" in out
    assert "1 FAIL" not in out
