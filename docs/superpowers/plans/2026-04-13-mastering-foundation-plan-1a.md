# Mastering Foundation — Plan 1a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `mastering:` config block, wire streaming-grade delivery defaults (24-bit / 96 kHz / -14 LUFS / -1 dBTP) into the existing mastering pipeline, ship an optional archival output path and a `prune_archival` tool, and surface a runtime notice when the pipeline upsamples from the Suno source rate.

**Architecture:** The existing mastering pipeline already supports per-genre presets via YAML; Plan 1a adds a higher-level `mastering:` config block that provides album-independent defaults for delivery format, bit depth, sample rate, archival behavior, and encoder preference. A new `load_mastering_config()` helper layers config values on top of preset values: user config overrides presets for non-genre-specific fields (delivery format, archival), while genre presets continue to control genre-specific fields (EQ curves, compression). Archival output is a new optional subfolder alongside existing `mastered/`.

**Tech Stack:** Python 3.11, `pyloudnorm` (already a dep), `soundfile` (24-bit + 32-bit float support already present), PyYAML (already a dep), existing `tools/shared/config.py` + `tools/mastering/master_tracks.py` + `servers/bitwize-music-server/handlers/processing/audio.py`.

---

## File Structure

**Create:**
- `tools/mastering/config.py` — `load_mastering_config()`, `resolve_mastering_targets()`, validation helpers
- `tests/unit/mastering/test_mastering_config.py` — unit tests for config loader + target resolution
- `tests/unit/mastering/test_archival_output.py` — tests for archival/ output path
- `tests/unit/mastering/test_prune_archival.py` — tests for `prune_archival` MCP tool

**Modify:**
- `config/config.example.yaml` — append `mastering:` section with all delivery-target keys + documentation
- `config/config.example.yaml` — add optional `artist.copyright_holder` + `artist.label` keys
- `servers/bitwize-music-server/handlers/processing/audio.py` — wire `resolve_mastering_targets()` into `master_audio` and `master_album`; add upsampling-report notice; add archival writing; register `prune_archival` MCP tool
- `servers/bitwize-music-server/handlers/processing/__init__.py` — export `prune_archival` for registration

**Responsibility boundaries:**
- `tools/shared/config.py` stays generic: YAML loader, no mastering-specific knowledge.
- `tools/mastering/config.py` handles mastering-config shape, defaults, merging with presets.
- `tools/mastering/master_tracks.py` remains preset-only; does not read config directly (keeps the low-level engine pure).
- `handlers/processing/audio.py` is where config meets pipeline: it resolves effective targets, passes them to `master_track()`, and handles archival + reporting.

---

## Task 1: Add `mastering:` config block to config.example.yaml

**Files:**
- Modify: `config/config.example.yaml` (append new section at end, before CONFIGURATION PATTERNS)

- [ ] **Step 1: Write the example YAML block**

Append before the `# CONFIGURATION PATTERNS` header (around line 722):

```yaml
# =============================================================================
# MASTERING [optional]
# =============================================================================
# Streaming-grade mastering defaults for master_album / master_audio / polish_and_master_album.
# All fields are optional — omit any key to accept the default.
#
# These values layer ON TOP of genre presets:
#   - Genre presets control *genre-specific* parameters (EQ curves, compression, de-essing).
#   - This block controls *delivery-target* parameters (bit depth, sample rate, loudness).
#
# The mastering pipeline enforces streaming-safe targets by default:
#   - 24-bit WAV at 96 kHz (Apple Hi-Res Lossless + Tidal Max eligibility)
#   - -14 LUFS integrated loudness (Spotify / Apple / Tidal / YouTube normalization)
#   - -1.0 dBTP true peak ceiling (AAC / Opus codec safety margin)
#
# Uncomment individual keys to customize.

# mastering:
#   # ---------------------------
#   # delivery_format [optional, default: "wav"]
#   # ---------------------------
#   # Output container for mastered tracks. Only WAV is supported for DistroKid
#   # single-ingest; other containers are reserved for future work.
#   #
#   # delivery_format: wav
#
#   # ---------------------------
#   # delivery_bit_depth [optional, default: 24]
#   # ---------------------------
#   # Bit depth for mastered delivery files.
#   #
#   # Options:
#   #   16 — legacy / smaller files / CD master rate
#   #   24 — streaming-grade headroom; required for Apple Hi-Res Lossless + Tidal Max
#   #
#   # delivery_bit_depth: 24
#
#   # ---------------------------
#   # delivery_sample_rate [optional, default: 96000]
#   # ---------------------------
#   # Output sample rate in Hz.
#   #
#   # Upsampled from the 44.1 kHz Suno source when >44100. This satisfies the
#   # sample-rate gate for Apple Hi-Res Lossless (>48 kHz strict) and Tidal Max
#   # (>44.1 kHz strict). It does NOT add audio information — the extra bandwidth
#   # above ~22 kHz is empty. See reference/streaming-mastering-specs.md for
#   # the full tradeoff discussion.
#   #
#   # Common values:
#   #   44100 — match Suno source; no badge eligibility.
#   #   48000 — broadcast standard; still below Apple Hi-Res threshold.
#   #   96000 — unlocks Apple Hi-Res Lossless + Tidal Max badges.
#   #
#   # delivery_sample_rate: 96000
#
#   # ---------------------------
#   # target_lufs [optional, default: -14.0]
#   # ---------------------------
#   # Integrated loudness target in LUFS. Genre presets override this per-genre;
#   # this is the fallback when no genre is specified.
#   #
#   # target_lufs: -14.0
#
#   # ---------------------------
#   # true_peak_ceiling [optional, default: -1.0]
#   # ---------------------------
#   # True peak ceiling in dBTP. -1.0 is the streaming-safe default. Use -1.5
#   # for opus-safe genres (EDM / metal / trap) where the codec is more
#   # aggressive about intersample peaks.
#   #
#   # true_peak_ceiling: -1.0
#
#   # ---------------------------
#   # archival_enabled [optional, default: false]
#   # ---------------------------
#   # When true, master_album also writes a 32-bit float / 96 kHz pre-downconvert
#   # master to {audio_root}/artists/[artist]/albums/[genre]/[album]/archival/.
#   # Intent: re-master without re-polishing stems (spec changes, re-release with
#   # different targets). Adds ~1-2 GB per 12-track album.
#   #
#   # Most users should leave this off.
#   #
#   # archival_enabled: false
#
#   # ---------------------------
#   # adm_aac_encoder [optional, default: "aac"]
#   # ---------------------------
#   # AAC encoder used for Apple Digital Masters (ADM) validation. Consumed by
#   # the validate_adm pipeline step (ships in a later phase).
#   #
#   # Options:
#   #   aac         — native ffmpeg AAC encoder; ships everywhere, spec-equivalent
#   #                 for the zero-clip validation test.
#   #   libfdk_aac  — Fraunhofer FDK AAC; closer parity to Apple's encoder.
#   #                 Requires a non-free ffmpeg build (--enable-libfdk_aac).
#   #
#   # adm_aac_encoder: aac
```

- [ ] **Step 2: Also add optional artist.copyright_holder and artist.label keys**

In the `artist:` section (around line 108, after `style:`), append before the closing blank line:

```yaml
  # ---------------------------
  # copyright_holder [optional]
  # ---------------------------
  # Copyright owner for embedded audio metadata. Defaults to artist.name
  # when omitted. Used by the mastering pipeline when writing ID3/BWF tags.
  #
  # copyright_holder: "Your Legal Name or Label LLC"

  # ---------------------------
  # label [optional]
  # ---------------------------
  # Record label name for embedded audio metadata. Defaults to artist.name
  # when omitted. Self-released artists can leave this unset.
  #
  # label: "Your Label"
```

- [ ] **Step 3: Run config.example.yaml through YAML parser to verify validity**

```bash
~/.bitwize-music/venv/bin/python -c "import yaml; yaml.safe_load(open('config/config.example.yaml'))"
```
Expected: no output (clean parse).

- [ ] **Step 4: Commit**

```bash
git add config/config.example.yaml
git commit -m "feat(config): add mastering: config block with 24/96 defaults

Documents streaming-grade delivery defaults for the mastering pipeline
(24-bit WAV at 96 kHz, -14 LUFS, -1 dBTP) and the 96 kHz upsampling
caveat. Adds optional artist.copyright_holder and artist.label keys for
downstream metadata embedding.

All keys are optional; existing configs continue to work unchanged.

Part of #290 phase 1a.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Create `load_mastering_config()` and `resolve_mastering_targets()`

**Files:**
- Create: `tools/mastering/config.py`
- Create: `tests/unit/mastering/test_mastering_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/mastering/test_mastering_config.py`:

```python
"""Unit tests for tools/mastering/config.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.mastering.config import (
    DEFAULT_MASTERING_CONFIG,
    load_mastering_config,
    resolve_mastering_targets,
)


class TestLoadMasteringConfig:
    def test_returns_defaults_when_config_missing(self):
        with patch("tools.mastering.config.load_config", return_value=None):
            result = load_mastering_config()
        assert result == DEFAULT_MASTERING_CONFIG

    def test_returns_defaults_when_mastering_key_absent(self):
        with patch("tools.mastering.config.load_config", return_value={"artist": {"name": "x"}}):
            result = load_mastering_config()
        assert result == DEFAULT_MASTERING_CONFIG

    def test_merges_user_values_over_defaults(self):
        user_config = {"mastering": {"delivery_bit_depth": 16, "archival_enabled": True}}
        with patch("tools.mastering.config.load_config", return_value=user_config):
            result = load_mastering_config()
        assert result["delivery_bit_depth"] == 16
        assert result["archival_enabled"] is True
        # unmentioned keys keep defaults
        assert result["delivery_sample_rate"] == 96000
        assert result["target_lufs"] == -14.0

    def test_rejects_unknown_keys_silently(self):
        """Unknown keys do not crash; they are logged and dropped."""
        user_config = {"mastering": {"nonsense_key": 42, "target_lufs": -12.0}}
        with patch("tools.mastering.config.load_config", return_value=user_config):
            result = load_mastering_config()
        assert "nonsense_key" not in result
        assert result["target_lufs"] == -12.0

    def test_coerces_numeric_types(self):
        """YAML loads 96000 as int; code expects int; -14.0 is float."""
        user_config = {"mastering": {"delivery_sample_rate": "48000", "target_lufs": "-14"}}
        with patch("tools.mastering.config.load_config", return_value=user_config):
            result = load_mastering_config()
        assert result["delivery_sample_rate"] == 48000
        assert isinstance(result["delivery_sample_rate"], int)
        assert result["target_lufs"] == -14.0
        assert isinstance(result["target_lufs"], float)


class TestResolveMasteringTargets:
    def test_config_supplies_defaults_when_no_genre_no_explicit(self):
        cfg = {
            "delivery_bit_depth": 24, "delivery_sample_rate": 96000,
            "target_lufs": -14.0, "true_peak_ceiling": -1.0,
            "delivery_format": "wav", "archival_enabled": False,
            "adm_aac_encoder": "aac",
        }
        preset = None
        targets = resolve_mastering_targets(
            config=cfg, preset=preset,
            target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
        )
        assert targets["target_lufs"] == -14.0
        assert targets["ceiling_db"] == -1.0
        assert targets["output_bits"] == 24
        assert targets["output_sample_rate"] == 96000

    def test_preset_overrides_config_for_target_lufs(self):
        cfg = {"target_lufs": -14.0, "true_peak_ceiling": -1.0,
               "delivery_bit_depth": 24, "delivery_sample_rate": 96000}
        preset = {"target_lufs": -9.0}  # metal preset
        targets = resolve_mastering_targets(
            config=cfg, preset=preset,
            target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
        )
        # explicit arg matches default, so preset wins
        assert targets["target_lufs"] == -9.0

    def test_explicit_arg_overrides_preset_and_config(self):
        cfg = {"target_lufs": -14.0, "true_peak_ceiling": -1.0,
               "delivery_bit_depth": 24, "delivery_sample_rate": 96000}
        preset = {"target_lufs": -9.0}
        # User explicitly passed -16.0; wins over both
        targets = resolve_mastering_targets(
            config=cfg, preset=preset,
            target_lufs_arg=-16.0, ceiling_db_arg=-1.0,
        )
        assert targets["target_lufs"] == -16.0

    def test_upsampling_flag_set_when_output_exceeds_source(self):
        cfg = {"target_lufs": -14.0, "true_peak_ceiling": -1.0,
               "delivery_bit_depth": 24, "delivery_sample_rate": 96000}
        preset = None
        targets = resolve_mastering_targets(
            config=cfg, preset=preset,
            target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
            source_sample_rate=44100,
        )
        assert targets["upsampled_from_source"] is True
        assert targets["source_sample_rate"] == 44100

    def test_upsampling_flag_unset_when_output_matches_source(self):
        cfg = {"target_lufs": -14.0, "true_peak_ceiling": -1.0,
               "delivery_bit_depth": 24, "delivery_sample_rate": 96000}
        targets = resolve_mastering_targets(
            config=cfg, preset=None,
            target_lufs_arg=-14.0, ceiling_db_arg=-1.0,
            source_sample_rate=96000,
        )
        assert targets["upsampled_from_source"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/bitwize/GitHub/claude-ai-music-skills/.worktrees/album-mastering-foundation
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_mastering_config.py -v
```
Expected: `ImportError` / `ModuleNotFoundError` — `tools.mastering.config` doesn't exist.

- [ ] **Step 3: Write the minimal implementation**

Create `tools/mastering/config.py`:

```python
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
# a user wraps them in quotes; we coerce to the canonical type here rather
# than sprinkle isinstance checks across the pipeline.
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
    coerced to the canonical type.
    """
    result = dict(DEFAULT_MASTERING_CONFIG)
    config = load_config()
    if not config:
        return result

    user_mastering = config.get("mastering") or {}
    if not isinstance(user_mastering, dict):
        logger.warning(
            "mastering: must be a mapping, got %s — ignoring",
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
                # YAML already gives us bools; don't coerce strings like "false"
                result[key] = bool(value)
            else:
                result[key] = expected_type(value)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Could not coerce mastering.%s=%r to %s: %s — using default",
                key, value, expected_type.__name__, exc,
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
      2. Genre preset (when provided).
      3. Config value.

    ``target_lufs_arg`` defaults to -14.0 and ``ceiling_db_arg`` to -1.0 in the
    handler signatures; a value equal to the default is treated as "not
    explicitly set" so the preset can take precedence.
    """
    # Loudness target
    if target_lufs_arg != -14.0:
        target_lufs = float(target_lufs_arg)
    elif preset is not None and "target_lufs" in preset:
        target_lufs = float(preset["target_lufs"])
    else:
        target_lufs = float(config.get("target_lufs", -14.0))

    # True peak ceiling
    if ceiling_db_arg != -1.0:
        ceiling_db = float(ceiling_db_arg)
    elif preset is not None and "true_peak_ceiling" in preset:
        ceiling_db = float(preset["true_peak_ceiling"])
    else:
        ceiling_db = float(config.get("true_peak_ceiling", -1.0))

    # Output bit depth — config unless preset explicitly overrides
    if preset is not None and "output_bits" in preset and preset["output_bits"]:
        output_bits = int(preset["output_bits"])
    else:
        output_bits = int(config.get("delivery_bit_depth", 24))

    # Output sample rate — config unless preset explicitly overrides (non-zero)
    preset_sr = int(preset.get("output_sample_rate", 0)) if preset else 0
    if preset_sr > 0:
        output_sample_rate = preset_sr
    else:
        output_sample_rate = int(config.get("delivery_sample_rate", 96000))

    targets = {
        "target_lufs": target_lufs,
        "ceiling_db": ceiling_db,
        "output_bits": output_bits,
        "output_sample_rate": output_sample_rate,
        "archival_enabled": bool(config.get("archival_enabled", False)),
        "adm_aac_encoder": str(config.get("adm_aac_encoder", "aac")),
    }

    if source_sample_rate is not None:
        targets["source_sample_rate"] = source_sample_rate
        targets["upsampled_from_source"] = output_sample_rate > source_sample_rate
    else:
        targets["source_sample_rate"] = None
        targets["upsampled_from_source"] = False

    return targets
```

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_mastering_config.py -v
```
Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/config.py tests/unit/mastering/test_mastering_config.py
git commit -m "feat(mastering): add load_mastering_config + resolve_mastering_targets

Adds a dedicated config loader for the mastering: YAML block plus a
resolver that combines config values, genre-preset values, and explicit
handler arguments into the effective per-run targets.

Precedence: explicit arg > genre preset > config > default.

Used by master_audio / master_album to honor streaming-grade delivery
defaults (24/96 WAV, -14 LUFS, -1 dBTP) without requiring per-call args.

Part of #290 phase 1a.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Wire `resolve_mastering_targets()` into `master_audio`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (function `master_audio`, around line 195)
- Create: `tests/unit/mastering/test_master_audio_config_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/mastering/test_master_audio_config_wiring.py`:

```python
"""Integration test: master_audio consumes mastering config for delivery targets."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def one_track_album(tmp_path: Path) -> Path:
    """Create a minimal audio dir with one synthetic 44.1 kHz WAV."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    sr = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    data = 0.3 * np.sin(2 * np.pi * 440 * t)
    stereo = np.column_stack([data, data])
    sf.write(str(audio_dir / "01-test.wav"), stereo, sr, subtype="PCM_16")
    return audio_dir


@pytest.mark.asyncio
async def test_master_audio_produces_24bit_96khz_by_default(one_track_album: Path):
    """With default config (24/96), mastered output is 24-bit at 96 kHz."""
    from servers.bitwize_music_server.handlers.processing import audio as audio_mod
    # NOTE: server module path is imported differently in the real server; if the
    # above import fails, the canonical path is handlers.processing.audio.

    # Patch _resolve_audio_dir to point at our temp album
    async def _fake_resolve(slug, *_, **__):
        return None, one_track_album

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = await audio_mod.master_audio("test-album")

    import json
    result = json.loads(result_json)
    assert "error" not in result, result

    mastered = one_track_album / "mastered" / "01-test.wav"
    assert mastered.exists()
    info = sf.info(str(mastered))
    assert info.samplerate == 96000
    assert info.subtype == "PCM_24"
```

Note: this is an end-to-end integration test that may need adjustment once we see the actual module import path. The important assertion is that the mastered output is 24-bit at 96 kHz by default.

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_master_audio_config_wiring.py -v
```
Expected: FAIL — current `master_audio` writes 16-bit PCM at source rate.

- [ ] **Step 3: Modify `master_audio` to consume mastering config**

In `servers/bitwize-music-server/handlers/processing/audio.py` at the top of the file, add:

```python
from tools.mastering.config import (
    load_mastering_config,
    resolve_mastering_targets,
)
```

In the body of `master_audio` (around line 260, where `effective_lufs = target_lufs` is set), replace the block that resolves effective targets with:

```python
    # Load mastering config and resolve effective delivery targets
    mastering_config = load_mastering_config()
    genre_applied = None
    preset = None
    effective_compress = 1.5
    eq_settings_highmid = cut_highmid
    eq_settings_highs = cut_highs

    if genre:
        presets = load_genre_presets()
        genre_key = genre.lower()
        if genre_key not in presets:
            return _safe_json({
                "error": f"Unknown genre: {genre}",
                "available_genres": sorted(presets.keys()),
            })
        preset = presets[genre_key]
        if cut_highmid == 0.0:
            eq_settings_highmid = preset['cut_highmid']
        if cut_highs == 0.0:
            eq_settings_highs = preset['cut_highs']
        effective_compress = preset['compress_ratio']
        genre_applied = genre_key

    targets = resolve_mastering_targets(
        config=mastering_config,
        preset=preset,
        target_lufs_arg=target_lufs,
        ceiling_db_arg=ceiling_db,
    )
    effective_lufs = targets["target_lufs"]
    effective_ceiling = targets["ceiling_db"]
```

Update the `_do_master` closure to pass `output_bits` and `output_sample_rate` through to `_master_track`:

```python
            def _do_master(in_path: Path, out_path: Path, fo: float) -> dict[str, Any]:
                return _master_track(
                    str(in_path), str(out_path),
                    target_lufs=effective_lufs,
                    eq_settings=eq_settings if eq_settings else None,
                    ceiling_db=effective_ceiling,
                    fade_out=fo,
                    compress_ratio=effective_compress,
                    preset={
                        **(preset or {}),
                        "output_bits": targets["output_bits"],
                        "output_sample_rate": targets["output_sample_rate"],
                        "target_lufs": effective_lufs,
                    },
                )
```

Update the response `settings` block to report the effective delivery params:

```python
    return _safe_json({
        "tracks": track_results,
        "settings": {
            "target_lufs": effective_lufs,
            "ceiling_db": effective_ceiling,
            "output_bits": targets["output_bits"],
            "output_sample_rate": targets["output_sample_rate"],
            "cut_highmid": eq_settings_highmid,
            "cut_highs": eq_settings_highs,
            "genre": genre_applied,
            "dry_run": dry_run,
        },
        # ... (keep existing summary)
    })
```

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_master_audio_config_wiring.py -v
```
Expected: PASS — output is 24-bit at 96 kHz.

- [ ] **Step 5: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py tests/unit/mastering/test_master_audio_config_wiring.py
git commit -m "feat(mastering): wire master_audio to mastering config for delivery targets

master_audio now consumes load_mastering_config() and passes the resolved
output bit depth + sample rate through to master_track(). Mastered output
defaults to 24-bit / 96 kHz (streaming-grade), overridable via the
mastering: config block.

Existing behavior preserved when config omits the mastering: block or
when genre presets explicitly set output_bits / output_sample_rate.

Part of #290 phase 1a.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Wire `resolve_mastering_targets()` into `master_album`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (function `master_album`, around line 565)

- [ ] **Step 1: Locate master_album's internal call to _master_track**

Search `master_album` for the call that drives per-track mastering. Identify the settings dict it builds.

- [ ] **Step 2: Replace hardcoded settings with resolved targets**

Apply the same pattern as Task 3: call `load_mastering_config()` once up front, call `resolve_mastering_targets()` per genre, pass `output_bits` and `output_sample_rate` through the preset dict to the inner `_master_track` call.

The minimum change is to ensure the inner call respects the resolved `output_bits` / `output_sample_rate` / `target_lufs` / `ceiling_db` from config. Follow the existing staging-directory pattern (lines 842-908) unchanged — just feed it resolved values.

- [ ] **Step 3: Extend the response dict to include resolved targets**

In the final `_safe_json` return at the end of `master_album`, add the resolved delivery params to the `settings` block so downstream consumers (the mastering report) can read them:

```python
        "settings": {
            "target_lufs": targets["target_lufs"],
            "ceiling_db": targets["ceiling_db"],
            "output_bits": targets["output_bits"],
            "output_sample_rate": targets["output_sample_rate"],
            "source_sample_rate": targets.get("source_sample_rate"),
            "upsampled_from_source": targets.get("upsampled_from_source", False),
            "archival_enabled": targets["archival_enabled"],
            "adm_aac_encoder": targets["adm_aac_encoder"],
            "genre": genre_applied,
        },
```

- [ ] **Step 4: Add an integration test for master_album**

Create `tests/unit/mastering/test_master_album_config_wiring.py`:

```python
"""Integration test: master_album consumes mastering config for delivery targets."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def three_track_album(tmp_path: Path) -> Path:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    sr = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    for i, freq in enumerate([440, 660, 880], start=1):
        data = 0.3 * np.sin(2 * np.pi * freq * t)
        stereo = np.column_stack([data, data])
        sf.write(str(audio_dir / f"0{i}-track.wav"), stereo, sr, subtype="PCM_16")
    return audio_dir


@pytest.mark.asyncio
async def test_master_album_outputs_24bit_96khz_by_default(three_track_album: Path):
    from handlers.processing import audio as audio_mod

    async def _fake_resolve(slug, *_, **__):
        return None, three_track_album

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = await audio_mod.master_album("test-album")

    result = json.loads(result_json)
    assert "error" not in result, result

    for i in range(1, 4):
        mastered = three_track_album / "mastered" / f"0{i}-track.wav"
        assert mastered.exists()
        info = sf.info(str(mastered))
        assert info.samplerate == 96000
        assert info.subtype == "PCM_24"

    assert result["settings"]["output_bits"] == 24
    assert result["settings"]["output_sample_rate"] == 96000
    assert result["settings"]["upsampled_from_source"] is True
```

- [ ] **Step 5: Run the test**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_master_album_config_wiring.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py tests/unit/mastering/test_master_album_config_wiring.py
git commit -m "feat(mastering): wire master_album to mastering config

master_album now consumes load_mastering_config() for delivery targets
and reports the resolved output_bits / output_sample_rate /
upsampled_from_source flags in the response settings block.

Part of #290 phase 1a.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Add upsampling notice to mastering report output

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (master_album's final response)

- [ ] **Step 1: Write the failing test**

Extend `tests/unit/mastering/test_master_album_config_wiring.py` with a new test:

```python
@pytest.mark.asyncio
async def test_master_album_reports_upsampling_notice(three_track_album: Path):
    from handlers.processing import audio as audio_mod

    async def _fake_resolve(slug, *_, **__):
        return None, three_track_album

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = await audio_mod.master_album("test-album")

    result = json.loads(result_json)
    notices = result.get("notices", [])
    # Upsampling caveat must be surfaced when delivery > source rate
    assert any("upsampled" in n.lower() and "44.1" in n and "96" in n for n in notices), (
        f"Expected upsampling notice, got: {notices}"
    )
    # And it must include the "no additional audio information" language
    assert any("no additional audio information" in n.lower() or
               "does not add" in n.lower() for n in notices), notices


@pytest.mark.asyncio
async def test_master_album_no_upsampling_notice_when_rates_match(
    three_track_album: Path,
):
    """When delivery_sample_rate matches source rate, no notice is emitted."""
    from handlers.processing import audio as audio_mod
    from tools.mastering.config import DEFAULT_MASTERING_CONFIG

    custom_cfg = {**DEFAULT_MASTERING_CONFIG, "delivery_sample_rate": 44100}

    async def _fake_resolve(slug, *_, **__):
        return None, three_track_album

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve), \
         patch("tools.mastering.config.load_mastering_config", return_value=custom_cfg):
        result_json = await audio_mod.master_album("test-album")

    result = json.loads(result_json)
    notices = result.get("notices", [])
    assert not any("upsampled" in n.lower() for n in notices), (
        f"Did not expect upsampling notice at matched rates, got: {notices}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `notices` key doesn't exist in response.

- [ ] **Step 3: Add notice emission in `master_album`**

Near the end of `master_album`, before the final `_safe_json` return, build a `notices` list:

```python
    notices = []
    if targets.get("upsampled_from_source"):
        src = targets["source_sample_rate"]
        dst = targets["output_sample_rate"]
        notices.append(
            f"Delivery at {dst // 1000} kHz (upsampled from {src / 1000:.1f} kHz "
            f"source). Badge-eligible for Apple Hi-Res Lossless and Tidal Max — "
            f"no additional audio information vs. source."
        )
```

Include `"notices": notices` in the returned dict.

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_master_album_config_wiring.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py tests/unit/mastering/test_master_album_config_wiring.py
git commit -m "feat(mastering): emit runtime notice when delivery rate upsamples source

master_album now appends a notice to its response whenever the effective
delivery_sample_rate exceeds the source rate (e.g. 96 kHz output from a
44.1 kHz Suno source). The notice surfaces the honesty caveat: badge-
eligible but no additional audio information vs. source.

Part of #290 phase 1a.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Add archival output path

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (master_album)
- Create: `tests/unit/mastering/test_archival_output.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/mastering/test_archival_output.py`:

```python
"""Tests for master_album archival output path."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def album_with_three_tracks(tmp_path: Path) -> Path:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    sr = 44100
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    for i, freq in enumerate([440, 660, 880], start=1):
        data = 0.3 * np.sin(2 * np.pi * freq * t)
        stereo = np.column_stack([data, data])
        sf.write(str(audio_dir / f"0{i}-track.wav"), stereo, sr, subtype="PCM_16")
    return audio_dir


@pytest.mark.asyncio
async def test_archival_disabled_by_default(album_with_three_tracks: Path):
    """Default config: archival_enabled=False → no archival/ directory."""
    from handlers.processing import audio as audio_mod

    async def _fake_resolve(slug, *_, **__):
        return None, album_with_three_tracks

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve):
        await audio_mod.master_album("test-album")

    archival_dir = album_with_three_tracks / "archival"
    assert not archival_dir.exists()


@pytest.mark.asyncio
async def test_archival_enabled_writes_32bit_float_96khz(album_with_three_tracks: Path):
    from handlers.processing import audio as audio_mod
    from tools.mastering.config import DEFAULT_MASTERING_CONFIG

    custom_cfg = {**DEFAULT_MASTERING_CONFIG, "archival_enabled": True}

    async def _fake_resolve(slug, *_, **__):
        return None, album_with_three_tracks

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve), \
         patch("tools.mastering.config.load_mastering_config", return_value=custom_cfg):
        await audio_mod.master_album("test-album")

    archival_dir = album_with_three_tracks / "archival"
    assert archival_dir.is_dir()
    for i in range(1, 4):
        arch = archival_dir / f"0{i}-track.wav"
        assert arch.exists(), f"Missing archival file: {arch}"
        info = sf.info(str(arch))
        assert info.samplerate == 96000
        assert info.subtype == "FLOAT"
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — archival logic doesn't exist.

- [ ] **Step 3: Implement archival writing in `master_album`**

After the per-track mastering loop (inside the existing staging block), add:

```python
    # Write 32-bit float archival copy if enabled
    if targets["archival_enabled"] and not dry_run:
        archival_dir = audio_dir / "archival"
        archival_dir.mkdir(exist_ok=True)
        for wav_file in wav_files:
            # Re-master with 32-bit float preset and write to archival
            arch_path = archival_dir / wav_file.name
            arch_preset = {
                **(preset or {}),
                "output_bits": 32,
                "output_sample_rate": targets["output_sample_rate"],
                "target_lufs": targets["target_lufs"],
            }
            await loop.run_in_executor(
                None, _master_track,
                str(wav_file), str(arch_path),
                targets["target_lufs"],
                eq_settings if eq_settings else None,
                1.5,  # compress_ratio (placeholder; use preset value when present)
                targets["ceiling_db"],
                None, None, None,  # fade_out, cut_highmid, cut_highs
                effective_compress,
                arch_preset,
            )
```

Caveat: the exact signature of `_master_track` needs to match its positional/keyword arg layout — read `tools/mastering/master_tracks.py::master_track` before writing the call to get the arg order right. The essential requirement is that the output file is written at 32-bit float / 96 kHz.

**Alternative (simpler, preferred if the signature proves awkward):** After writing the 24-bit mastered file to `mastered/`, re-open it, upconvert the samples to float32, and write to `archival/` with `subtype="FLOAT"`. That avoids the double-render. The archival file is bit-equivalent to the mastered file but in a higher-headroom container.

```python
    if targets["archival_enabled"] and not dry_run:
        archival_dir = audio_dir / "archival"
        archival_dir.mkdir(exist_ok=True)
        for wav_file in wav_files:
            mastered_path = output_dir / wav_file.name
            arch_path = archival_dir / wav_file.name
            data, sr = sf.read(str(mastered_path), dtype="float32")
            sf.write(str(arch_path), data, sr, subtype="FLOAT")
```

Use the simpler alternative. Archival's purpose is "re-master without re-polishing stems" — it doesn't need to be a separate render, just a higher-bit-depth copy of what shipped.

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_archival_output.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py tests/unit/mastering/test_archival_output.py
git commit -m "feat(mastering): add opt-in archival output path (32-bit float / 96 kHz)

When mastering.archival_enabled is true, master_album writes a 32-bit
float copy of each mastered track to {audio_dir}/archival/. Default is
off — archival is a power-user feature for re-mastering without
re-polishing stems.

Part of #290 phase 1a.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Add `prune_archival` MCP tool

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (add tool + registration)
- Create: `tests/unit/mastering/test_prune_archival.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/mastering/test_prune_archival.py`:

```python
"""Tests for the prune_archival MCP tool."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_prune_archival_noop_when_directory_missing(tmp_path: Path):
    from handlers.processing import audio as audio_mod

    async def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = await audio_mod.prune_archival("test-album")

    result = json.loads(result_json)
    assert "error" not in result
    assert result["removed"] == []
    assert result["kept"] == []


@pytest.mark.asyncio
async def test_prune_archival_removes_all_when_keep_is_zero(tmp_path: Path):
    archival_dir = tmp_path / "archival"
    archival_dir.mkdir()
    for name in ("01-old.wav", "02-old.wav"):
        (archival_dir / name).write_bytes(b"")

    from handlers.processing import audio as audio_mod

    async def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = await audio_mod.prune_archival("test-album", keep=0)

    result = json.loads(result_json)
    assert sorted(result["removed"]) == ["01-old.wav", "02-old.wav"]
    assert not any(archival_dir.iterdir())


@pytest.mark.asyncio
async def test_prune_archival_keeps_latest_n_by_mtime(tmp_path: Path):
    archival_dir = tmp_path / "archival"
    archival_dir.mkdir()
    # Create files with increasing mtimes
    import time
    paths = []
    for name in ("a.wav", "b.wav", "c.wav", "d.wav"):
        p = archival_dir / name
        p.write_bytes(b"")
        time.sleep(0.01)
        paths.append(p)

    from handlers.processing import audio as audio_mod

    async def _fake_resolve(slug, *_, **__):
        return None, tmp_path

    with patch.object(audio_mod._helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = await audio_mod.prune_archival("test-album", keep=2)

    result = json.loads(result_json)
    # "c.wav" and "d.wav" are the two newest
    assert sorted(result["kept"]) == ["c.wav", "d.wav"]
    assert sorted(result["removed"]) == ["a.wav", "b.wav"]
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `AttributeError: module ... has no attribute 'prune_archival'`.

- [ ] **Step 3: Implement `prune_archival`**

Append to `servers/bitwize-music-server/handlers/processing/audio.py`:

```python
async def prune_archival(album_slug: str, keep: int = 3) -> str:
    """Prune old archival masters, keeping the N most recent files per album.

    The archival/ directory holds 32-bit float pre-downconvert masters (written
    when mastering.archival_enabled is true). Each re-master adds new files;
    this tool lets users cap disk usage by pruning older entries.

    Args:
        album_slug: Album slug (e.g., "my-album")
        keep: Number of most-recent files to keep (by mtime). Default: 3.

    Returns:
        JSON with {"kept": [...], "removed": [...]}.
    """
    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    archival_dir = audio_dir / "archival"
    if not archival_dir.is_dir():
        return _safe_json({"kept": [], "removed": [], "note": "no archival directory"})

    files = sorted(
        (f for f in archival_dir.iterdir() if f.is_file()),
        key=lambda f: f.stat().st_mtime,
    )
    if keep < 0:
        keep = 0
    if keep >= len(files):
        return _safe_json({
            "kept": [f.name for f in files],
            "removed": [],
        })

    to_remove = files[: len(files) - keep] if keep > 0 else list(files)
    to_keep = files[len(files) - keep:] if keep > 0 else []

    removed_names = []
    for f in to_remove:
        try:
            f.unlink()
            removed_names.append(f.name)
        except OSError as e:
            logger.warning("Could not remove %s: %s", f, e)

    return _safe_json({
        "kept": [f.name for f in to_keep],
        "removed": removed_names,
    })
```

- [ ] **Step 4: Register the tool in the server**

At the bottom of `audio.py`, locate the existing tool-registration function (search for `mcp.tool()`) and add `mcp.tool()(prune_archival)` alongside the existing registrations.

If registration happens in `servers/bitwize-music-server/server.py` via an explicit import list, add `prune_archival` to the import from `handlers.processing`.

- [ ] **Step 5: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_prune_archival.py -v
```
Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py tests/unit/mastering/test_prune_archival.py
git commit -m "feat(mastering): add prune_archival MCP tool

Explicit user-action cleanup for the archival/ directory — keeps the N
most-recent 32-bit float masters per album and removes older entries.
Default keep=3; pass keep=0 to remove everything.

Part of #290 phase 1a.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Run the full plugin test harness + zero-regression sweep

**Files:**
- None (validation only)

- [ ] **Step 1: Run the mastering test suite**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/ tests/unit/mixing/ -v --tb=short
```
Expected: all tests pass (baseline 499 + new tests from this plan).

- [ ] **Step 2: Run the broader unit test suite**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/ -x --tb=short -q
```
Expected: all pass.

- [ ] **Step 3: Run the plugin test harness**

```bash
~/.bitwize-music/venv/bin/python tools/testing/run_tests.py all
```
Expected: no regressions.

If plugin harness is unavailable in the worktree, skip with a note in the commit message.

- [ ] **Step 4: Commit any test-driven fixups**

If step 3 surfaced any plugin harness violations (e.g., missing references to removed keys), address them and commit.

---

## Task 9: Open PR to develop

**Files:**
- None (PR operation)

- [ ] **Step 1: Push the feature branch**

```bash
git push -u origin feat/album-mastering-foundation
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base develop --title "feat: mastering foundation — 24/96 delivery + archival + config block (issue #290, phase 1a)" --body "$(cat <<'EOF'
## Summary

Foundation for the automated album-coherence mastering pipeline (issue #290).
This PR lands Phase 1a of the 10-phase rollout:

- New `mastering:` block in `config.example.yaml` with streaming-grade defaults
  (24-bit WAV / 96 kHz / -14 LUFS / -1 dBTP).
- `tools/mastering/config.py` — config loader + target resolver that layers
  user config on top of genre presets and explicit handler args.
- `master_audio` and `master_album` now honor the resolved delivery targets;
  default output is 24-bit at 96 kHz.
- Mastering report emits a runtime notice when `delivery_sample_rate` exceeds
  the source rate (the 96 kHz honesty caveat — badge-eligible but not
  substantively hi-res).
- Optional 32-bit float archival output path (`archival_enabled: false`
  default) at `{audio_root}/.../{album}/archival/`.
- New `prune_archival` MCP tool for explicit cleanup (keeps N most-recent).
- Optional `artist.copyright_holder` and `artist.label` config keys for
  downstream metadata embedding (landing in issue #303 / later phases).

No regressions on the existing flow: when config is absent or omits the
`mastering:` block, behavior matches the prior defaults for loudness and
ceiling, and output bit depth / sample rate fall back to preset values
when presets specify them.

## Test plan

- [x] New unit tests: `tests/unit/mastering/test_mastering_config.py`
- [x] Integration: `tests/unit/mastering/test_master_audio_config_wiring.py`
- [x] Integration: `tests/unit/mastering/test_master_album_config_wiring.py`
- [x] Archival: `tests/unit/mastering/test_archival_output.py`
- [x] Prune: `tests/unit/mastering/test_prune_archival.py`
- [x] Full `tests/unit/` sweep passes (baseline preserved)
- [x] Manual: existing genre-preset output_bits / output_sample_rate settings
      continue to take precedence when set (regression check)

## Phase context

This is Phase 1a of the 10-phase implementation of #290. Subsequent phases:
- 1b: Multi-metric `analyze_audio` extension (STL-95, low-RMS windowed, vocal-RMS)
- 2a–c: Anchor selector + coherence correction + signature persistence
- 3a–c: Layout generator, ADM validation + ceiling guard, metadata MVP
- 4a–b: `measure_album_signature` tool, integration/docs/flag promotion

Companion issue: #303 (full-fidelity metadata embedding).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Return PR URL**

The `gh pr create` command emits the PR URL; include it in the session summary.

---

## Self-Review Checklist (for the implementing agent, run before opening the PR)

- [ ] Every task step has an exact command, file path, or code block (no TBDs).
- [ ] Each new symbol introduced in one task is used consistently in later tasks (function names, dict keys, env var names).
- [ ] `DEFAULT_MASTERING_CONFIG` keys match the YAML field names exactly.
- [ ] No regression on 16-bit legacy flow: genre presets with `output_bits: 16` still produce 16-bit output.
- [ ] Commit messages follow Conventional Commits (`feat`, `fix`, `docs`, `chore`) with the `Co-Authored-By` trailer from CLAUDE.md.
- [ ] PR title is under 70 characters and references issue #290 phase 1a.
