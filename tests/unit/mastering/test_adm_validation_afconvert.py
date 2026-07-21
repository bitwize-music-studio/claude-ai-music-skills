"""Unit coverage for the macOS ``afconvert`` path in adm_validation.py.

``_afconvert_encode_decode()`` is the product's only macOS-exclusive code path:
it probes for ``afconvert``, encodes WAV→AAC with it, decodes via ffmpeg, and
falls back to the ffmpeg ``aac`` encoder on THREE distinct failure branches:

  1. the ``afconvert --help`` probe raises (afconvert absent → FileNotFoundError,
     or non-zero → CalledProcessError, or hung → TimeoutExpired);
  2. the ``afconvert`` encode step times out (subprocess.TimeoutExpired); or
  3. the ``afconvert`` encode step returns a non-zero rc.

None of these run on Linux/Windows CI (no afconvert), so before this file the
whole path was invisible to the test suite (``grep -rn afconvert tests/`` → 0).
These tests drive every branch deterministically by monkeypatching
``adm_validation.subprocess.run`` with a dispatcher that:

  * records every invoked command so a test can *spy* on which binary ran, and
  * writes a real decoded WAV for the ffmpeg ``pcm_f32le`` decode call so the
    trailing ``sf.read`` returns a genuine array — no real ffmpeg/afconvert
    needed, so this module runs everywhere (no ``@requires_ffmpeg`` gate).

The real-``afconvert`` success path is proven separately, macOS-only, in
``tests/integration/test_afconvert_macos.py`` (the encoder cannot be faked into
producing a decodable m4a here).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Rate + sample count baked into the fake decoded WAV; tests assert on these so
# a broken decode/return would be caught, not just the encoder-name string.
_DECODED_RATE = 44100
_DECODED_SAMPLES = 256


class _FakeRunner:
    """A stand-in for ``subprocess.run`` that records calls and dispatches by
    program name, so a single object serves both the spy and the fake toolchain.

    ``probe`` controls the ``afconvert --help`` probe outcome; ``encode``
    controls the ``afconvert`` encode outcome. ffmpeg always "succeeds" and the
    ``pcm_f32le`` decode writes a real WAV so ``sf.read`` returns a known array.
    """

    def __init__(self, *, probe: str = "ok", encode: str = "ok") -> None:
        self.probe = probe
        self.encode = encode
        self.calls: list[list[str]] = []

    # --- spy helpers -------------------------------------------------------
    @property
    def programs(self) -> list[str]:
        return [cmd[0] for cmd in self.calls]

    def ran_afconvert_encode(self) -> bool:
        return any(c[0] == "afconvert" and "--help" not in c for c in self.calls)

    def ran_ffmpeg_aac_encode(self) -> bool:
        """True iff the ffmpeg fallback ENCODE (``-c:a aac``) was invoked."""
        return any(
            c[0] == "ffmpeg" and "pcm_f32le" not in c and "aac" in c
            for c in self.calls
        )

    def ran_ffmpeg_decode(self) -> bool:
        return any(c[0] == "ffmpeg" and "pcm_f32le" in c for c in self.calls)

    # --- the fake subprocess.run ------------------------------------------
    def __call__(self, cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        cmd = list(cmd)
        self.calls.append(cmd)
        prog = cmd[0]

        if prog == "afconvert" and "--help" in cmd:
            if self.probe == "absent":
                raise FileNotFoundError(2, "No such file or directory: 'afconvert'")
            if self.probe == "nonzero":
                # subprocess.run(check=True) raises this on a non-zero rc.
                raise subprocess.CalledProcessError(1, cmd)
            if self.probe == "timeout":
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        if prog == "afconvert":  # the encode step
            if self.encode == "timeout":
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
            if self.encode == "nonzero":
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="afconvert boom")
            Path(cmd[-1]).write_bytes(b"\x00\x00")  # dummy m4a; decode is faked
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        if prog == "ffmpeg":
            out = Path(cmd[-1])
            if "pcm_f32le" in cmd:  # the decode → produce a real, readable WAV
                mono = np.linspace(-0.4, 0.4, _DECODED_SAMPLES, dtype=np.float32)
                stereo = np.column_stack([mono, mono])
                sf.write(str(out), stereo, _DECODED_RATE, subtype="FLOAT")
            else:  # the encode → any bytes, nothing reads them
                out.write_bytes(b"\x00\x00")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        raise AssertionError(f"unexpected subprocess command: {cmd}")


def _write_input_wav(tmp_path: Path) -> Path:
    """A small real WAV to feed the function (only the fake toolchain reads it)."""
    wav = tmp_path / "in.wav"
    mono = np.linspace(-0.3, 0.3, 512, dtype=np.float32)
    sf.write(str(wav), np.column_stack([mono, mono]), 44100, subtype="PCM_24")
    return wav


# ---------------------------------------------------------------------------
# Fallback branch 1: the afconvert --help probe fails → ffmpeg "aac"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("probe", ["absent", "nonzero", "timeout"])
def test_probe_failure_falls_back_to_ffmpeg(tmp_path, monkeypatch, probe) -> None:
    """Every probe failure mode (absent / non-zero rc / hang) falls back to
    ffmpeg and reports the ffmpeg encoder name, never "afconvert"."""
    import tools.mastering.adm_validation as adm

    runner = _FakeRunner(probe=probe)
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    data, rate, encoder = adm._afconvert_encode_decode(wav)

    assert encoder == "aac"          # fell back, did NOT claim afconvert
    assert encoder != "afconvert"
    assert runner.ran_ffmpeg_aac_encode()   # the fallback path really ran
    assert not runner.ran_afconvert_encode()  # never reached afconvert encode
    assert rate == _DECODED_RATE
    assert data.size > 0


# ---------------------------------------------------------------------------
# Fallback branch 2: afconvert present, but the encode times out → ffmpeg "aac"
# ---------------------------------------------------------------------------


def test_afconvert_encode_timeout_falls_back(tmp_path, monkeypatch) -> None:
    """Probe succeeds, then the afconvert encode raises TimeoutExpired → ffmpeg."""
    import tools.mastering.adm_validation as adm

    runner = _FakeRunner(probe="ok", encode="timeout")
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    data, rate, encoder = adm._afconvert_encode_decode(wav)

    assert encoder == "aac"
    assert runner.ran_afconvert_encode()     # the encode WAS attempted...
    assert runner.ran_ffmpeg_aac_encode()    # ...then it fell back to ffmpeg
    assert rate == _DECODED_RATE
    assert data.size > 0


# ---------------------------------------------------------------------------
# Fallback branch 3: afconvert present, encode returns non-zero rc → ffmpeg "aac"
# ---------------------------------------------------------------------------


def test_afconvert_encode_nonzero_falls_back(tmp_path, monkeypatch) -> None:
    """Probe succeeds, then the afconvert encode returns rc!=0 → ffmpeg."""
    import tools.mastering.adm_validation as adm

    runner = _FakeRunner(probe="ok", encode="nonzero")
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    data, rate, encoder = adm._afconvert_encode_decode(wav)

    assert encoder == "aac"
    assert runner.ran_afconvert_encode()
    assert runner.ran_ffmpeg_aac_encode()
    assert rate == _DECODED_RATE
    assert data.size > 0


# ---------------------------------------------------------------------------
# Success path: afconvert present, encode + decode succeed → "afconvert"
# ---------------------------------------------------------------------------


def test_afconvert_success_reports_afconvert(tmp_path, monkeypatch) -> None:
    """When afconvert encodes cleanly and ffmpeg decodes, the encoder name is
    "afconvert" and NO ffmpeg aac-encode (the fallback) ever ran.

    The encode is mocked to write a dummy m4a and the decode is mocked to write
    a real WAV, so the pure-mock success path is reachable without a real
    afconvert (that end-to-end proof lives in the macOS integration test)."""
    import tools.mastering.adm_validation as adm

    runner = _FakeRunner(probe="ok", encode="ok")
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    data, rate, encoder = adm._afconvert_encode_decode(wav)

    assert encoder == "afconvert"
    assert runner.ran_afconvert_encode()      # afconvert did the encoding
    assert runner.ran_ffmpeg_decode()         # ffmpeg did the decoding
    assert not runner.ran_ffmpeg_aac_encode()  # fallback encode NEVER ran
    assert rate == _DECODED_RATE
    assert data.size > 0
    assert data.dtype == np.float32


# ---------------------------------------------------------------------------
# Public API wiring: check_aac_intersample_clips(encoder="afconvert")
# ---------------------------------------------------------------------------


def test_public_api_afconvert_fallback_records_encoder(tmp_path, monkeypatch) -> None:
    """check_aac_intersample_clips(encoder="afconvert") must surface the
    fallback encoder name in ``encoder_used`` when afconvert is unavailable."""
    import tools.mastering.adm_validation as adm

    runner = _FakeRunner(probe="absent")
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    result = adm.check_aac_intersample_clips(wav, encoder="afconvert", ceiling_db=-1.0)

    assert result["encoder_used"] == "aac"    # fell back, and the dict says so
    assert result["filename"] == "in.wav"
    assert runner.ran_ffmpeg_aac_encode()


def test_public_api_afconvert_success_records_encoder(tmp_path, monkeypatch) -> None:
    """check_aac_intersample_clips(encoder="afconvert") reports ``afconvert`` in
    ``encoder_used`` when the afconvert path succeeds."""
    import tools.mastering.adm_validation as adm

    runner = _FakeRunner(probe="ok", encode="ok")
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    result = adm.check_aac_intersample_clips(wav, encoder="afconvert", ceiling_db=-1.0)

    assert result["encoder_used"] == "afconvert"
    assert result["filename"] == "in.wav"
    assert runner.ran_afconvert_encode()
    assert not runner.ran_ffmpeg_aac_encode()
