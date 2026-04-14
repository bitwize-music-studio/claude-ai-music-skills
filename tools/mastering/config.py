"""Config loader for the mastering pipeline.

Layers a ``mastering:`` block from ``~/.bitwize-music/config.yaml`` on top of
hardcoded defaults. Kept separate from ``tools/shared/config.py`` so the
mastering-specific schema evolves without coupling to generic config helpers.

Genre-specific mastering behavior continues to live in
``tools/mastering/genre-presets.yaml`` (per-genre EQ, compression, etc.).
This module handles delivery-target fields (format, bit depth, sample rate,
loudness target, archival) that apply across genres.
"""

from __future__ import annotations

import logging
from typing import Any

from tools.shared.config import load_config

logger = logging.getLogger(__name__)

# Canonical default values for the ``mastering:`` config block.
DEFAULT_MASTERING_CONFIG: dict[str, Any] = {
    "delivery_format": "wav",
    "delivery_bit_depth": 24,
    "delivery_sample_rate": 96000,
    "target_lufs": -14.0,
    "true_peak_ceiling": -1.0,
    "archival_enabled": False,
    "adm_aac_encoder": "aac",
}

# Per-key type coercion. Values from YAML may come through as strings when
# a user quotes them; we coerce to the canonical type here rather than
# sprinkle isinstance checks across the pipeline.
_KEY_TYPES: dict[str, type] = {
    "delivery_format": str,
    "delivery_bit_depth": int,
    "delivery_sample_rate": int,
    "target_lufs": float,
    "true_peak_ceiling": float,
    "archival_enabled": bool,
    "adm_aac_encoder": str,
}


def load_mastering_config() -> dict[str, Any]:
    """Return the resolved mastering config dict (defaults + user overrides).

    Unknown keys in the user config are logged and dropped; known keys are
    coerced to the canonical type. A malformed ``mastering:`` value (non-
    mapping) falls back to defaults with a warning.
    """
    result = dict(DEFAULT_MASTERING_CONFIG)
    config = load_config()
    if not config:
        return result

    user_mastering = config.get("mastering")
    if user_mastering is None:
        return result
    if not isinstance(user_mastering, dict):
        logger.warning(
            "mastering: must be a mapping, got %s — using defaults",
            type(user_mastering).__name__,
        )
        return result

    for key, value in user_mastering.items():
        if key not in DEFAULT_MASTERING_CONFIG:
            logger.warning("Unknown mastering config key: %s (ignored)", key)
            continue
        expected_type = _KEY_TYPES[key]
        try:
            if expected_type is bool:
                # YAML already gives us bools; don't coerce arbitrary strings
                result[key] = bool(value)
            else:
                result[key] = expected_type(value)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Could not coerce mastering.%s=%r to %s: %s — using default",
                key,
                value,
                expected_type.__name__,
                exc,
            )

    return result


def resolve_mastering_targets(
    config: dict[str, Any],
    preset: dict[str, Any] | None,
    target_lufs_arg: float,
    ceiling_db_arg: float,
    source_sample_rate: int | None = None,
) -> dict[str, Any]:
    """Resolve effective mastering targets from config + preset + explicit args.

    Precedence (highest wins):
      1. Explicit arg (when it differs from the function's documented default).
      2. Genre preset (when provided and relevant field set).
      3. Config value.

    ``target_lufs_arg`` defaults to -14.0 and ``ceiling_db_arg`` to -1.0 in
    handler signatures; a value equal to the default is treated as "not
    explicitly set" so the preset can take precedence.
    """
    # Loudness target
    if target_lufs_arg != -14.0:
        target_lufs = float(target_lufs_arg)
    elif preset is not None and preset.get("target_lufs") is not None:
        target_lufs = float(preset["target_lufs"])
    else:
        target_lufs = float(config.get("target_lufs", -14.0))

    # True peak ceiling
    if ceiling_db_arg != -1.0:
        ceiling_db = float(ceiling_db_arg)
    elif preset is not None and preset.get("true_peak_ceiling") is not None:
        ceiling_db = float(preset["true_peak_ceiling"])
    else:
        ceiling_db = float(config.get("true_peak_ceiling", -1.0))

    # Output bit depth — preset wins whenever it sets a value (0 = "not set").
    # User-supplied overrides in {overrides}/mastering-presets.yaml can force
    # legacy 16-bit output per-genre even when mastering.delivery_bit_depth
    # is 24 globally.
    preset_bits = int(preset.get("output_bits", 0)) if preset else 0
    if preset_bits > 0:
        output_bits = preset_bits
    else:
        output_bits = int(config.get("delivery_bit_depth", 24))

    # Output sample rate — preset wins only when non-zero (0 = "preserve input")
    preset_sr = int(preset.get("output_sample_rate", 0)) if preset else 0
    if preset_sr > 0:
        output_sample_rate = preset_sr
    else:
        output_sample_rate = int(config.get("delivery_sample_rate", 96000))

    targets: dict[str, Any] = {
        "target_lufs": target_lufs,
        "ceiling_db": ceiling_db,
        "output_bits": output_bits,
        "output_sample_rate": output_sample_rate,
        "archival_enabled": bool(config.get("archival_enabled", False)),
        "adm_aac_encoder": str(config.get("adm_aac_encoder", "aac")),
    }

    if source_sample_rate is not None:
        targets["source_sample_rate"] = int(source_sample_rate)
        targets["upsampled_from_source"] = output_sample_rate > int(
            source_sample_rate
        )
    else:
        targets["source_sample_rate"] = None
        targets["upsampled_from_source"] = False

    return targets
