"""Persist and load ``ALBUM_SIGNATURE.yaml`` (#290 phase 4).

Pure-Python schema layer — no MCP coupling, no handler imports. Callers
supply a ready-made payload dict; this module wraps it with the schema
envelope (``schema_version`` + ``written_at`` + ``plugin_version``) and
handles atomic on-disk writes / strict on-disk reads.

Schema v1 layout (top-level keys required at read time):

.. code-block:: yaml

    schema_version: 1
    written_at: "2026-04-14T10:00:00Z"
    plugin_version: "0.91.0"
    album_slug: "my-album"
    anchor:
      index: 3
      filename: "03-track.wav"
      method: "composite"           # composite | override | tie_breaker
      score: 0.512                  # composite score (null for override)
      signature:                    # anchor's own pre-master signature
        stl_95: -14.8
        low_rms: -22.1
        vocal_rms: -17.6
        short_term_range: 8.4
        lufs: -14.0
        peak_db: -3.1
    album_median:                   # album-wide median across tracks
      lufs: -14.0
      stl_95: -14.5
      low_rms: -22.0
      vocal_rms: -17.8
      short_term_range: 8.2
    delivery_targets:               # what the album was actually shipped at
      target_lufs: -14.0
      tp_ceiling_db: -1.0
      lra_target_lu: 8.0
      output_bits: 24
      output_sample_rate: 96000
    tolerances:                     # coherence-correction tolerances in force
      coherence_stl_95_lu: 1.0
      coherence_lra_floor_lu: 6.0
      coherence_low_rms_db: 2.0
      coherence_vocal_rms_db: 1.5
    pipeline:                       # provenance, informational
      polish_subfolder: "polished"
      source_sample_rate: 44100
      upsampled_from_source: true
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path
from typing import Any

import yaml

# Allow ``handlers._atomic`` import when run as a pure-Python module
# (mastering tests don't boot the MCP server).
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "servers" / "bitwize-music-server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from handlers._atomic import atomic_write_text  # noqa: E402

SIGNATURE_FILENAME = "ALBUM_SIGNATURE.yaml"
SIGNATURE_SCHEMA_VERSION = 1

# Top-level keys that must be present when reading an existing file.
_REQUIRED_TOP_LEVEL_KEYS = (
    "schema_version",
    "written_at",
    "album_slug",
    "anchor",
    "album_median",
    "delivery_targets",
)


class SignaturePersistenceError(Exception):
    """Raised when ALBUM_SIGNATURE.yaml is corrupt, malformed, or on an
    unsupported schema version. Callers should treat this as "halt +
    escalate" for Released albums; for in-progress albums they may choose
    to overwrite (frozen-mode is not engaged)."""


def write_signature_file(
    audio_dir: Path,
    payload: dict[str, Any],
    *,
    plugin_version: str,
) -> Path:
    """Write ``ALBUM_SIGNATURE.yaml`` atomically to ``audio_dir``.

    Args:
        audio_dir: Directory that contains ``mastered/``, ``archival/``,
            etc. for this album. Signature lives alongside those.
        payload: Caller-built payload dict. Must contain ``album_slug``,
            ``anchor``, ``album_median``, ``delivery_targets``. May
            contain ``tolerances``, ``pipeline``, or other keys — those
            pass through verbatim. If the payload happens to contain
            any envelope-owned key (``schema_version``, ``written_at``,
            ``plugin_version``), the envelope value wins to preserve the
            schema contract.
        plugin_version: Plugin semver string (e.g. ``"0.91.0"``) for
            forward-compat debugging.

    Returns:
        Path to the written file.
    """
    envelope = {
        "schema_version": SIGNATURE_SCHEMA_VERSION,
        "written_at":     _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugin_version": plugin_version,
    }
    # Envelope keys (schema_version, written_at, plugin_version) are
    # authoritative — if a caller's payload contains any of them, the
    # envelope values win. This prevents accidental shadowing of the
    # schema contract. YAML preserves insertion order when
    # sort_keys=False, so envelope keys also emit first.
    combined: dict[str, Any] = {**payload, **envelope}

    path = audio_dir / SIGNATURE_FILENAME
    text = yaml.safe_dump(
        combined,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    atomic_write_text(path, text)
    return path


def read_signature_file(audio_dir: Path) -> dict[str, Any] | None:
    """Load and validate ``ALBUM_SIGNATURE.yaml`` from ``audio_dir``.

    Returns:
        The parsed dict, or ``None`` if the file is absent.

    Raises:
        SignaturePersistenceError: file is malformed, on an unsupported
            schema version, or missing a required top-level key.
    """
    path = audio_dir / SIGNATURE_FILENAME
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SignaturePersistenceError(f"{path}: parse error — {exc}") from exc
    if not isinstance(raw, dict):
        raise SignaturePersistenceError(f"{path}: expected YAML mapping, got {type(raw).__name__}")
    version = raw.get("schema_version")
    if version != SIGNATURE_SCHEMA_VERSION:
        raise SignaturePersistenceError(
            f"{path}: unsupported schema_version {version!r} "
            f"(this build expects {SIGNATURE_SCHEMA_VERSION})"
        )
    for key in _REQUIRED_TOP_LEVEL_KEYS:
        if key not in raw:
            raise SignaturePersistenceError(f"{path}: missing required key {key!r}")
    return raw
