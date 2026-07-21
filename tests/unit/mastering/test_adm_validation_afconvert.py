"""Unit coverage for the macOS ``afconvert`` path in adm_validation.py.

``_afconvert_encode_decode()`` is the product's only macOS-exclusive code path:
it probes for ``afconvert`` (by presence — ``shutil.which``), encodes WAV→AAC
with it, decodes via ffmpeg, and falls back to the ffmpeg ``aac`` encoder on
three distinct failure branches:

  1. afconvert is not installed (``shutil.which("afconvert") is None``);
  2. the ``afconvert`` encode step times out (subprocess.TimeoutExpired); or
  3. the ``afconvert`` encode step returns a non-zero rc.

The probe is a PRESENCE check, not ``afconvert --help``: on macOS
``afconvert --help`` exits 2 (usage convention), so the earlier ``check=True``
probe raised and the afconvert path was silently dead on every macOS machine.
These tests pin the corrected behaviour.

None of these run on Linux/Windows CI (no afconvert), so before this file the
whole path was invisible to the test suite (``grep -rn afconvert tests/`` → 0).
The tests drive every branch deterministically: ``shutil.which`` is
monkeypatched to say present/absent, and ``adm_validation.subprocess.run`` is
replaced with a dispatcher that records commands (a spy on which binary ran)
and writes a real decoded WAV for the ffmpeg ``pcm_f32le`` decode call so the
trailing ``sf.read`` returns a genuine array — no real ffmpeg/afconvert needed.

The real-``afconvert`` success path is proven separately, macOS-only, in
``tests/integration/test_afconvert_macos.py`` (the encoder cannot be faked into
producing a decodable m4a here).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Rate + sample count baked into the fake decoded WAV; tests assert on these so
# a broken decode/return would be caught, not just the encoder-name string.
_DECODED_RATE = 44100
_DECODED_SAMPLES = 256

_FAKE_AFCONVERT = "/usr/bin/afconvert"


def _set_afconvert_present(monkeypatch, present: bool) -> None:
    """Point the product's ``shutil.which`` at a present/absent afconvert."""
    import tools.mastering.adm_validation as adm

    if present:
        monkeypatch.setattr(
            adm.shutil, "which",
            lambda name: _FAKE_AFCONVERT if name == "afconvert" else None,
        )
    else:
        monkeypatch.setattr(adm.shutil, "which", lambda name: None)


class _FakeRunner:
    """A stand-in for ``subprocess.run`` that records calls and dispatches by
    program name, so a single object serves both the spy and the fake toolchain.

    ``encode`` controls the ``afconvert`` encode outcome. ffmpeg always
    "succeeds" and the ``pcm_f32le`` decode writes a real WAV so ``sf.read``
    returns a known array. (afconvert presence is decided by ``shutil.which``,
    not by any subprocess call, so there is no ``--help`` probe to fake.)
    """

    def __init__(self, *, encode: str = "ok") -> None:
        self.encode = encode
        self.calls: list[list[str]] = []

    # --- spy helpers -------------------------------------------------------
    @property
    def programs(self) -> list[str]:
        return [cmd[0] for cmd in self.calls]

    def ran_afconvert_encode(self) -> bool:
        return any(c[0] == "afconvert" for c in self.calls)

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
# Fallback branch 1: afconvert not installed → ffmpeg "aac"
# ---------------------------------------------------------------------------


def test_afconvert_absent_falls_back_to_ffmpeg(tmp_path, monkeypatch) -> None:
    """When shutil.which finds no afconvert, fall back to ffmpeg and report the
    ffmpeg encoder name, never "afconvert" — and never even attempt an afconvert
    subprocess."""
    import tools.mastering.adm_validation as adm

    _set_afconvert_present(monkeypatch, False)
    runner = _FakeRunner()
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    data, rate, encoder = adm._afconvert_encode_decode(wav)

    assert encoder == "aac"          # fell back, did NOT claim afconvert
    assert encoder != "afconvert"
    assert runner.ran_ffmpeg_aac_encode()      # the fallback path really ran
    assert not runner.ran_afconvert_encode()   # never invoked afconvert at all
    assert rate == _DECODED_RATE
    assert data.size > 0


def test_afconvert_help_nonzero_exit_does_not_block(tmp_path, monkeypatch) -> None:
    """Regression guard for the fixed bug: afconvert is present, so the path must
    proceed to the real encode. The old probe ran `afconvert --help` under
    check=True; on macOS that exits 2, which wrongly forced the fallback every
    time. Presence-based probing means a non-zero `--help` exit is irrelevant —
    prove no `--help` command is ever issued and the encoder is "afconvert"."""
    import tools.mastering.adm_validation as adm

    _set_afconvert_present(monkeypatch, True)
    runner = _FakeRunner(encode="ok")
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    data, rate, encoder = adm._afconvert_encode_decode(wav)

    assert encoder == "afconvert"
    # The bug was a `--help` probe; ensure it's gone for good.
    assert not any("--help" in c for c in runner.calls)
    assert rate == _DECODED_RATE
    assert data.size > 0


# ---------------------------------------------------------------------------
# Fallback branch 2: afconvert present, but the encode times out → ffmpeg "aac"
# ---------------------------------------------------------------------------


def test_afconvert_encode_timeout_falls_back(tmp_path, monkeypatch) -> None:
    """Present, then the afconvert encode raises TimeoutExpired → ffmpeg."""
    import tools.mastering.adm_validation as adm

    _set_afconvert_present(monkeypatch, True)
    runner = _FakeRunner(encode="timeout")
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
    """Present, then the afconvert encode returns rc!=0 → ffmpeg."""
    import tools.mastering.adm_validation as adm

    _set_afconvert_present(monkeypatch, True)
    runner = _FakeRunner(encode="nonzero")
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

    _set_afconvert_present(monkeypatch, True)
    runner = _FakeRunner(encode="ok")
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

    _set_afconvert_present(monkeypatch, False)
    runner = _FakeRunner()
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

    _set_afconvert_present(monkeypatch, True)
    runner = _FakeRunner(encode="ok")
    monkeypatch.setattr(adm.subprocess, "run", runner)
    wav = _write_input_wav(tmp_path)

    result = adm.check_aac_intersample_clips(wav, encoder="afconvert", ceiling_db=-1.0)

    assert result["encoder_used"] == "afconvert"
    assert result["filename"] == "in.wav"
    assert runner.ran_afconvert_encode()
    assert not runner.ran_ffmpeg_aac_encode()
