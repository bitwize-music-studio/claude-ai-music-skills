"""Integration tests for signature persistence inside master_album (#290 phase 4)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from tools.mastering.signature_persistence import (  # noqa: E402
    SIGNATURE_FILENAME,
    read_signature_file,
)


def _write_sine_wav(path: Path, *, duration: float = 30.0, sample_rate: int = 44100,
                    freq: float = 220.0, amplitude: float = 0.3) -> Path:
    import soundfile as sf
    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, sample_rate, subtype="PCM_24")
    return path


def _install_album(monkeypatch, audio_path: Path, album_slug: str,
                   status: str = "In Progress") -> None:
    from handlers import _shared
    fake_state = {"albums": {album_slug: {
        "path": str(audio_path),
        "status": status,
        "tracks": {},
    }}}
    class _FakeCache:
        def get_state(self): return fake_state
        def get_state_ref(self): return fake_state
    monkeypatch.setattr(_shared, "cache", _FakeCache())


def test_master_album_writes_signature_on_success(tmp_path: Path, monkeypatch) -> None:
    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _write_sine_wav(tmp_path / "02-track.wav", amplitude=0.32, freq=330.0)
    _install_album(monkeypatch, tmp_path, album_slug="sig-album")

    # Force PLUGIN_ROOT=None so plugin_version falls back deterministically
    # (other tests may leave PLUGIN_ROOT populated).
    from handlers import _shared
    monkeypatch.setattr(_shared, "PLUGIN_ROOT", None)

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="sig-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, f"master_album failed: {result.get('failure_detail')}"
    assert "signature_persist" in result["stages"]
    assert result["stages"]["signature_persist"]["status"] == "pass"

    # File exists and round-trips.
    sig = read_signature_file(tmp_path)
    assert sig is not None
    assert sig["album_slug"] == "sig-album"
    assert sig["anchor"]["index"] in (1, 2)
    assert sig["delivery_targets"]["tp_ceiling_db"] == -1.0
    assert sig["delivery_targets"]["target_lufs"] == -14.0

    # Verify numpy coercion produced native Python floats.
    anchor_sig = sig["anchor"]["signature"]
    assert anchor_sig is not None
    assert isinstance(anchor_sig["peak_db"], float)
    assert isinstance(anchor_sig["lufs"], float)

    # Verify method, pipeline, album_median, and plugin version fallback.
    assert sig["anchor"]["method"] in ("composite", "tie_breaker", "override")
    assert sig["pipeline"]["source_sample_rate"] == 44100
    assert sig["album_median"]["lufs"] is not None
    assert sig["plugin_version"] == "unknown"  # PLUGIN_ROOT=None in tests


def test_master_album_does_not_write_signature_on_stage_failure(tmp_path: Path, monkeypatch) -> None:
    # No WAV files → pre_flight fails.
    _install_album(monkeypatch, tmp_path, album_slug="empty-album")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="empty-album"))

    result = json.loads(result_json)
    assert result["failed_stage"] == "pre_flight"
    assert not (tmp_path / SIGNATURE_FILENAME).exists()


def test_master_album_signature_write_failure_is_nonfatal(tmp_path: Path, monkeypatch) -> None:
    """Stage 7.5 warnings when signature write fails — master_album still succeeds."""
    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _install_album(monkeypatch, tmp_path, album_slug="warn-album")

    # Force PLUGIN_ROOT=None so plugin_version falls back deterministically
    # (other tests may leave PLUGIN_ROOT populated).
    from handlers import _shared
    monkeypatch.setattr(_shared, "PLUGIN_ROOT", None)

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    def _raising_write(*_args, **_kw):
        from tools.mastering.signature_persistence import SignaturePersistenceError
        raise SignaturePersistenceError("simulated failure")

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(audio_mod, "write_signature_file", _raising_write):
        result_json = asyncio.run(audio_mod.master_album(album_slug="warn-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None
    assert result["stages"]["signature_persist"]["status"] == "warn"
    assert "simulated failure" in result["stages"]["signature_persist"]["error"]


def test_released_album_with_signature_enters_frozen_mode(tmp_path: Path, monkeypatch) -> None:
    from tools.mastering.signature_persistence import write_signature_file

    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _write_sine_wav(tmp_path / "02-track.wav", amplitude=0.3, freq=330.0)
    _install_album(monkeypatch, tmp_path, "rel-album", status="Released")

    from handlers import _shared
    monkeypatch.setattr(_shared, "PLUGIN_ROOT", None)

    # Pre-seed the signature as if a prior master run wrote it.
    payload = {
        "album_slug": "rel-album",
        "anchor": {
            "index": 1,
            "filename": "01-track.wav",
            "method": "composite",
            "score": 0.5,
            "signature": {"lufs": -14.0, "peak_db": -3.0, "stl_95": -14.1,
                          "short_term_range": 8.0, "low_rms": -22.0, "vocal_rms": -17.5},
        },
        "album_median": {"lufs": -14.0, "stl_95": -14.1, "low_rms": -22.0,
                         "vocal_rms": -17.5, "short_term_range": 8.0},
        "delivery_targets": {"target_lufs": -14.0, "tp_ceiling_db": -1.0,
                             "lra_target_lu": 8.0, "output_bits": 24,
                             "output_sample_rate": 96000},
        "tolerances": {},
        "pipeline": {},
    }
    write_signature_file(tmp_path, payload, plugin_version="0.91.0")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="rel-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, result.get("failure_detail")
    assert result["stages"]["freeze_decision"]["mode"] == "frozen"
    # Anchor selection is skipped in frozen mode.
    assert result["stages"]["anchor_selection"]["method"] == "frozen_signature"
    assert result["stages"]["anchor_selection"]["selected_index"] == 1


def test_in_progress_album_uses_fresh_mode(tmp_path: Path, monkeypatch) -> None:
    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _write_sine_wav(tmp_path / "02-track.wav", amplitude=0.32, freq=330.0)
    _install_album(monkeypatch, tmp_path, "wip-album", status="In Progress")

    from handlers import _shared
    monkeypatch.setattr(_shared, "PLUGIN_ROOT", None)

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="wip-album"))

    result = json.loads(result_json)
    assert result["stages"]["freeze_decision"]["mode"] == "fresh"
    assert result["stages"]["anchor_selection"]["method"] in ("composite", "tie_breaker")


def test_new_anchor_forces_fresh_on_released(tmp_path: Path, monkeypatch) -> None:
    from tools.mastering.signature_persistence import write_signature_file

    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _install_album(monkeypatch, tmp_path, "relock-album", status="Released")
    from handlers import _shared
    monkeypatch.setattr(_shared, "PLUGIN_ROOT", None)
    # Signature present, but --new-anchor overrides the default frozen routing.
    write_signature_file(tmp_path, {
        "album_slug": "relock-album",
        "anchor": {"index": 1, "filename": "01-track.wav", "method": "composite",
                   "score": 0.5, "signature": {}},
        "album_median": {}, "delivery_targets": {}, "tolerances": {}, "pipeline": {},
    }, plugin_version="0.91.0")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(
            album_slug="relock-album", new_anchor=True,
        ))

    result = json.loads(result_json)
    assert result["stages"]["freeze_decision"]["mode"] == "fresh"
    assert result["stages"]["freeze_decision"]["reason"] == "new_anchor_override"


def test_frozen_mode_preserves_original_anchor_block(tmp_path: Path, monkeypatch) -> None:
    """Re-mastering a Released album keeps anchor.method from the shipped
    signature (e.g. "composite"), not "frozen_signature"."""
    import pytest
    from tools.mastering.signature_persistence import (
        read_signature_file, write_signature_file,
    )

    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _write_sine_wav(tmp_path / "02-track.wav", amplitude=0.3, freq=330.0)
    _install_album(monkeypatch, tmp_path, "pres-album", status="Released")

    from handlers import _shared
    monkeypatch.setattr(_shared, "PLUGIN_ROOT", None)

    original_anchor = {
        "index": 2,
        "filename": "02-track.wav",
        "method": "composite",
        "score": 0.612,
        "signature": {"lufs": -14.0, "peak_db": -3.0, "stl_95": -14.1,
                      "short_term_range": 8.0, "low_rms": -22.0, "vocal_rms": -17.5},
    }
    write_signature_file(tmp_path, {
        "album_slug": "pres-album",
        "anchor": original_anchor,
        "album_median": {}, "delivery_targets": {
            "target_lufs": -14.0, "tp_ceiling_db": -1.0,
            "lra_target_lu": 7.3,  # non-default value to detect drift
            "output_bits": 24, "output_sample_rate": 96000,
        },
        "tolerances": {
            "coherence_stl_95_lu": 0.75,   # non-default: default is 1.0
            "coherence_lra_floor_lu": 5.0, # non-default: default is 6.0
            "coherence_low_rms_db": 1.8,   # non-default: default is 2.0
            "coherence_vocal_rms_db": 1.2, # non-default: default is 1.5
        },
        "pipeline": {},
    }, plugin_version="0.91.0")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        asyncio.run(audio_mod.master_album(album_slug="pres-album"))

    after = read_signature_file(tmp_path)
    assert after is not None
    assert after["anchor"]["method"] == "composite"
    assert after["anchor"]["score"] == pytest.approx(0.612)
    assert after["anchor"]["filename"] == "02-track.wav"

    # Frozen mode must preserve tolerances and LRA target across re-masters.
    assert after["delivery_targets"]["lra_target_lu"] == pytest.approx(7.3)
    assert after["tolerances"]["coherence_stl_95_lu"] == pytest.approx(0.75)
    assert after["tolerances"]["coherence_lra_floor_lu"] == pytest.approx(5.0)
    assert after["tolerances"]["coherence_low_rms_db"] == pytest.approx(1.8)
    assert after["tolerances"]["coherence_vocal_rms_db"] == pytest.approx(1.2)


def test_frozen_mode_delivery_matches_frozen_target(tmp_path: Path, monkeypatch) -> None:
    """Phase-4 core guarantee: frozen re-master delivers at the frozen target,
    not at the genre default.

    Regression for the bug where Stage 2b mutated targets but the effective_*
    locals cached at Stage 1 were never refreshed, so Stage 4's mastering loop
    silently used the genre default (-14 LUFS) instead of the frozen target.
    """
    import soundfile as sf
    import pyloudnorm as pyln

    from tools.mastering.signature_persistence import write_signature_file

    # Wav amplitude chosen so genre-default mastering would drive it to ~-14 LUFS;
    # frozen target at -11 LUFS lets us detect the delta clearly.
    _write_sine_wav(tmp_path / "01-track.wav", amplitude=0.3)
    _install_album(monkeypatch, tmp_path, "drift-album", status="Released")

    from handlers import _shared
    monkeypatch.setattr(_shared, "PLUGIN_ROOT", None)

    frozen_target_lufs = -11.0
    write_signature_file(tmp_path, {
        "album_slug": "drift-album",
        "anchor": {
            "index": 1, "filename": "01-track.wav",
            "method": "composite", "score": 0.5,
            "signature": {"lufs": frozen_target_lufs, "peak_db": -3.0,
                          "stl_95": -11.1, "short_term_range": 8.0,
                          "low_rms": -22.0, "vocal_rms": -17.5},
        },
        "album_median": {},
        "delivery_targets": {
            "target_lufs": frozen_target_lufs,
            "tp_ceiling_db": -1.0,
            "lra_target_lu": 8.0,
            "output_bits": 24,
            "output_sample_rate": 96000,
        },
        "tolerances": {}, "pipeline": {},
    }, plugin_version="0.91.0")

    def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.master_album(album_slug="drift-album"))

    result = json.loads(result_json)
    assert result.get("failed_stage") is None, result.get("failure_detail")
    assert result["stages"]["freeze_decision"]["mode"] == "frozen"

    # Read the delivered WAV and compute integrated LUFS.
    mastered_path = tmp_path / "mastered" / "01-track.wav"
    assert mastered_path.exists(), "mastered file missing"
    data, sr = sf.read(str(mastered_path))
    meter = pyln.Meter(sr)
    delivered_lufs = meter.integrated_loudness(data)

    # Frozen mode must deliver within 0.5 LU of the frozen target.
    assert abs(delivered_lufs - frozen_target_lufs) < 0.5, (
        f"Frozen re-master drifted: delivered {delivered_lufs:.2f} LUFS vs "
        f"frozen target {frozen_target_lufs} LUFS "
        f"(delta {delivered_lufs - frozen_target_lufs:+.2f})"
    )
