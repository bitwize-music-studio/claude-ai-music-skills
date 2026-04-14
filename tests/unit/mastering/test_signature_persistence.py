"""Tests for tools/mastering/signature_persistence.py (#290 phase 4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.signature_persistence import (  # noqa: E402
    SIGNATURE_FILENAME,
    SIGNATURE_SCHEMA_VERSION,
    SignaturePersistenceError,
    read_signature_file,
    write_signature_file,
)


def _sample_payload() -> dict:
    return {
        "album_slug": "test-album",
        "anchor": {
            "index": 2,
            "filename": "02-track.wav",
            "method": "composite",
            "score": 0.512,
            "signature": {
                "stl_95": -14.8,
                "low_rms": -22.1,
                "vocal_rms": -17.6,
                "short_term_range": 8.4,
                "lufs": -14.0,
                "peak_db": -3.1,
            },
        },
        "album_median": {
            "lufs": -14.0,
            "stl_95": -14.5,
            "low_rms": -22.0,
            "vocal_rms": -17.8,
            "short_term_range": 8.2,
        },
        "delivery_targets": {
            "target_lufs": -14.0,
            "tp_ceiling_db": -1.0,
            "lra_target_lu": 8.0,
            "output_bits": 24,
            "output_sample_rate": 96000,
        },
        "tolerances": {
            "coherence_stl_95_lu": 1.0,
            "coherence_lra_floor_lu": 6.0,
            "coherence_low_rms_db": 2.0,
            "coherence_vocal_rms_db": 1.5,
        },
        "pipeline": {
            "polish_subfolder": "polished",
            "source_sample_rate": 44100,
            "upsampled_from_source": True,
        },
    }


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    payload = _sample_payload()
    path = write_signature_file(tmp_path, payload, plugin_version="0.91.0")
    assert path == tmp_path / SIGNATURE_FILENAME
    assert path.exists()

    read = read_signature_file(tmp_path)
    assert read["album_slug"] == "test-album"
    assert read["anchor"]["index"] == 2
    assert read["delivery_targets"]["target_lufs"] == -14.0
    assert read["schema_version"] == SIGNATURE_SCHEMA_VERSION
    assert read["plugin_version"] == "0.91.0"
    assert "written_at" in read  # ISO-8601 timestamp was inserted


def test_read_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_signature_file(tmp_path) is None


def test_read_raises_on_unknown_schema_version(tmp_path: Path) -> None:
    bogus = {
        "schema_version": 999,
        "written_at": "2026-04-14T10:00:00Z",
        "album_slug": "x",
    }
    (tmp_path / SIGNATURE_FILENAME).write_text(yaml.safe_dump(bogus))
    with pytest.raises(SignaturePersistenceError, match="unsupported schema_version"):
        read_signature_file(tmp_path)


def test_read_raises_on_missing_required_key(tmp_path: Path) -> None:
    # Missing "anchor" block.
    (tmp_path / SIGNATURE_FILENAME).write_text(
        yaml.safe_dump({"schema_version": SIGNATURE_SCHEMA_VERSION, "album_slug": "x",
                        "written_at": "2026-04-14T10:00:00Z"})
    )
    with pytest.raises(SignaturePersistenceError, match="missing required key"):
        read_signature_file(tmp_path)


def test_read_raises_on_malformed_yaml(tmp_path: Path) -> None:
    (tmp_path / SIGNATURE_FILENAME).write_text(":::\nnot: valid: yaml:[")
    with pytest.raises(SignaturePersistenceError, match="parse error"):
        read_signature_file(tmp_path)


def test_write_is_atomic(tmp_path: Path) -> None:
    """Overwriting an existing signature must not leave the file empty at any
    observable point (relies on atomic_write_text's rename semantics)."""
    payload = _sample_payload()
    write_signature_file(tmp_path, payload, plugin_version="0.91.0")
    # Second write with slightly different payload.
    payload["anchor"]["index"] = 3
    write_signature_file(tmp_path, payload, plugin_version="0.91.0")
    read = read_signature_file(tmp_path)
    assert read["anchor"]["index"] == 3


def test_read_raises_on_non_mapping_yaml(tmp_path: Path) -> None:
    """Top-level YAML that parses to a list / scalar / null is rejected."""
    (tmp_path / SIGNATURE_FILENAME).write_text("- not\n- a\n- mapping\n")
    with pytest.raises(SignaturePersistenceError, match="expected YAML mapping"):
        read_signature_file(tmp_path)
