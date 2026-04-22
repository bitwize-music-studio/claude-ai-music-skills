# Per-Album Mastering Overrides (ADM Default-Off) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `mastering:` block to album README frontmatter so operators can override mastering settings per-album. First consumer is `adm_validation_enabled`, which becomes **frontmatter-required, default OFF** — a breaking-change semantic for ADM specifically, chosen because ADM is an Apple-submission-tier niche that rarely matters for Suno workflows and shouldn't silently add 3-5 min/track to every run.

**Architecture:** Three additive changes, all mirroring the existing `anchor_track:` / `layout:` per-album frontmatter pattern. (1) `parse_album_readme` surfaces the `mastering:` block as `result["mastering"]: dict`. (2) `tools/state/indexer.py` copies it into the cached state next to `anchor_track` / `layout`. (3) `build_delivery_targets` gains an `album_mastering` kwarg; for `adm_validation_enabled`, the rule is "frontmatter must explicitly set True, else False — config.yaml value is ignored." For other keys (future-proofing), standard frontmatter > config > hardcoded default resolution. No orchestration change in `master_album` beyond passing the album state through.

**Tech Stack:** Python 3.11, `pyyaml` (already used), existing state-cache + frontmatter-parse infrastructure. No new dependencies.

---

## Scope Check

Single subsystem (config resolution + state indexer). Fits one plan.

**Out of scope:**
- Implementing the other per-album mastering overrides (ceiling_db, target_lufs, archival_enabled). The block shape accepts arbitrary keys, but only `adm_validation_enabled` is wired through this plan. Follow-ups can add the others without schema changes.
- Migration tool for existing albums. Operators add `mastering:` to README frontmatter manually when they want ADM on.
- CLI exposure (master.py standalone). This plan covers the MCP/handler path only; CLI users continue to rely on config.yaml.

---

## Codebase Context

Key files (paths from repo root):

- `tools/state/parsers.py:134` — `parse_album_readme`. Already parses frontmatter and exposes `anchor_track`, `layout`, `streaming_urls`, etc. Follow the same shape for the new `mastering` key.
- `tools/state/indexer.py:242-243, 518-519` — state cache population. Both call-sites copy `anchor_track` / `layout` from the parsed README into `state.albums[slug]`. Add `mastering` alongside.
- `tools/mastering/config.py:56-176` — `load_mastering_config` + `build_delivery_targets`. Currently reads `config["adm_validation_enabled"]` with default `False`. Needs an `album_mastering` kwarg that carries the per-album override dict.
- `servers/bitwize-music-server/handlers/processing/audio.py:567-569` — existing pattern for pulling per-album state (`anchor_track` via cache). Mirror this for `mastering` block.
- `servers/bitwize-music-server/handlers/processing/audio.py:827` — `adm_enabled = bool(ctx.targets.get("adm_validation_enabled", False))`. Once `build_delivery_targets` applies the per-album rule, this line keeps working unchanged — it reads the resolved value from `ctx.targets`.
- `templates/album.md` — album README template. Add documentation for the new frontmatter block.

**Resolution rules (important — differs from standard frontmatter > config pattern):**

| Key | Resolution |
|---|---|
| `mastering.adm_validation_enabled` | **Frontmatter must explicitly be `true`, else `False`.** Global config ignored. |
| `mastering.*` (any other key — future scope) | Standard: frontmatter > config > hardcoded default |

Only `adm_validation_enabled` uses the strict frontmatter-required rule. Other keys follow the usual cascade.

**Breaking-change note:** Any existing deployment with `adm_validation_enabled: true` in `config.yaml` and no frontmatter block will see ADM stop running. The CHANGELOG must flag this clearly. Affected operators add `mastering: { adm_validation_enabled: true }` to each album README frontmatter they want to validate.

---

## File Structure

| File | Role | State |
|---|---|---|
| `tools/state/parsers.py` | `parse_album_readme` surfaces `mastering` frontmatter block as a validated dict | modify |
| `tools/state/indexer.py` | Copy `album_data["mastering"]` into `state.albums[slug]["mastering"]` at both call sites | modify |
| `tools/mastering/config.py` | `build_delivery_targets` gains `album_mastering: dict[str, Any] \| None` kwarg; applies frontmatter-required ADM rule | modify |
| `servers/bitwize-music-server/handlers/processing/audio.py` | Pull `album_state["mastering"]` from cache and pass to `build_delivery_targets` | modify |
| `templates/album.md` | Document `mastering:` frontmatter block with ADM example | modify |
| `tests/unit/state/test_parsers.py` | `mastering:` block parsed correctly, missing block = empty dict, malformed = empty dict | modify (add tests) |
| `tests/unit/state/test_indexer.py` | `mastering` surfaces in cached state | modify (add tests) |
| `tests/unit/mastering/test_config_album_overrides.py` | `build_delivery_targets` ADM resolution rule (frontmatter required, default off) | **new** |
| `tests/unit/mastering/test_master_album_adm_off_end_to_end.py` | Regression: full pipeline with ADM off completes without touching ADM code paths | **new** |
| `CHANGELOG.md` | `[Unreleased]` entry under `### Changed` flagging breaking-change | modify |

Files NOT modified:
- `tools/mastering/master_tracks.py` (CLI) — out of scope
- `servers/bitwize-music-server/handlers/processing/_album_stages.py` — no stage logic changes; resolution happens upstream in config
- `audio.py:827` — the existing `adm_enabled = bool(ctx.targets.get("adm_validation_enabled", False))` line keeps working because `ctx.targets["adm_validation_enabled"]` is now resolved from the per-album override at target-build time

---

## Design Details (read before starting any task)

### Frontmatter block shape

```yaml
---
Title: My Album
Genre: electronic
anchor_track: 3
mastering:
  adm_validation_enabled: true   # opt in to ADM validation for this album
  # future keys slot in here: ceiling_db, target_lufs, archival_enabled, etc.
---
```

- If the `mastering:` block is absent → `album_data["mastering"] = {}`.
- If `mastering:` is present but malformed (not a dict) → `album_data["mastering"] = {}` (graceful fallback).
- Unknown keys in the block are preserved in the dict — forward-compat for future consumers.

### ADM resolution in `build_delivery_targets`

Existing (line 162-164):
```python
"adm_validation_enabled": bool(
    config.get("adm_validation_enabled", False)
),
```

New:
```python
# Per-album opt-in: ADM validation only runs when the album's README
# frontmatter explicitly sets mastering.adm_validation_enabled: true.
# Global config.yaml setting is NOT a sufficient opt-in — ADM is an
# Apple-submission-tier niche and rarely matters for Suno workflows.
# This rule is specific to adm_validation_enabled; other future
# mastering.* keys follow the standard frontmatter > config > default
# cascade.
_adm_overrides = (album_mastering or {})
if "adm_validation_enabled" in _adm_overrides:
    adm_enabled = bool(_adm_overrides["adm_validation_enabled"])
else:
    adm_enabled = False
```

`adm_aac_encoder` is unaffected — still resolves from config as before (it's a codec choice, not a behavior gate).

### Template documentation

Add a section to `templates/album.md` after the existing `anchor_track:` / `layout:` documentation:

```markdown
### mastering (optional)

Per-album mastering overrides. Currently supports:

- `adm_validation_enabled: true` — opt in to Apple Digital Masters
  inter-sample peak validation. **Defaults to OFF** even when
  config.yaml has it enabled globally. Only enable when you're
  submitting the album for ADM certification (Apple Music
  submission) and the source material is spectrally viable. Adds
  3-5 min/track to pipeline runtime.

Example:

```yaml
mastering:
  adm_validation_enabled: true
```
```

---

## Task 1: Parser — `parse_album_readme` surfaces `mastering` block

**Files:**
- Modify: `tools/state/parsers.py` (inside `parse_album_readme`, around line 194 where `result['layout']` is set)
- Test: `tests/unit/state/test_parsers.py` (existing file)

- [ ] **Step 1: Write failing tests**

Find `tests/unit/state/test_parsers.py`:
```bash
ls tests/unit/state/test_parsers.py && grep -n "def test_.*layout\|def test_.*anchor" tests/unit/state/test_parsers.py | head -5
```

Append these three tests to the end of the file (or alongside existing `parse_album_readme` tests — put them with the layout/anchor tests if there's a natural grouping):

```python
def test_parse_album_readme_surfaces_mastering_block(tmp_path: Path) -> None:
    """Frontmatter `mastering:` block must surface as a dict on the
    parsed result so downstream consumers (config.build_delivery_targets)
    can apply the per-album ADM opt-in rule."""
    from tools.state.parsers import parse_album_readme

    readme = tmp_path / "README.md"
    readme.write_text(
        "---\n"
        "Title: Test Album\n"
        "Genre: electronic\n"
        "mastering:\n"
        "  adm_validation_enabled: true\n"
        "  ceiling_db: -1.5\n"
        "---\n"
        "\n"
        "# Test Album\n",
    )

    result = parse_album_readme(readme)
    assert "_error" not in result
    assert result["mastering"] == {
        "adm_validation_enabled": True,
        "ceiling_db": -1.5,
    }


def test_parse_album_readme_mastering_absent_is_empty_dict(tmp_path: Path) -> None:
    """No mastering block → result['mastering'] is {} (empty dict, not
    None). Downstream code can rely on .get() always finding a dict."""
    from tools.state.parsers import parse_album_readme

    readme = tmp_path / "README.md"
    readme.write_text(
        "---\n"
        "Title: Plain Album\n"
        "---\n"
        "\n"
        "# Plain Album\n",
    )

    result = parse_album_readme(readme)
    assert result["mastering"] == {}


def test_parse_album_readme_mastering_malformed_is_empty_dict(tmp_path: Path) -> None:
    """Malformed mastering block (scalar, list, null) is treated as
    empty — no override applied. Defensive against hand-edited READMEs."""
    from tools.state.parsers import parse_album_readme

    for malformed in ["null", "false", "some string", "- list\n  - items"]:
        readme = tmp_path / "README.md"
        readme.write_text(
            "---\n"
            "Title: Malformed\n"
            f"mastering: {malformed}\n"
            "---\n"
            "\n"
            "# Malformed\n",
        )
        result = parse_album_readme(readme)
        assert result["mastering"] == {}, (
            f"Malformed mastering value {malformed!r} should collapse to {{}}, "
            f"got {result['mastering']!r}"
        )
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/pytest tests/unit/state/test_parsers.py -k "mastering" -v
```

Expected: all 3 FAIL with `KeyError: 'mastering'`.

- [ ] **Step 3: Implement parser surfacing**

Open `tools/state/parsers.py`, locate `parse_album_readme`, find the line `result['layout'] = parsed_layout` (around line 194). Immediately after that, insert:

```python
    # Per-album mastering overrides (issue #353). The frontmatter
    # `mastering:` block carries keys that override config.yaml::mastering
    # for this album only. Malformed input collapses to {} so downstream
    # consumers can rely on .get() always finding a dict.
    mastering_raw = fm.get('mastering')
    if isinstance(mastering_raw, dict):
        result['mastering'] = mastering_raw
    else:
        result['mastering'] = {}
```

- [ ] **Step 4: Verify tests pass**

```bash
.venv/bin/pytest tests/unit/state/test_parsers.py -k "mastering" -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Regression check**

```bash
.venv/bin/pytest tests/unit/state/ -v
```

Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add tools/state/parsers.py tests/unit/state/test_parsers.py
git commit -m "$(cat <<'EOF'
feat: parse_album_readme surfaces mastering frontmatter block

Adds result['mastering'] containing the frontmatter's `mastering:`
dict (or {} when absent / malformed). Mirrors the existing
anchor_track + layout per-album override pattern. Consumer wiring
follows in subsequent commits (indexer → state cache →
build_delivery_targets).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Indexer — propagate `mastering` into cached state

**Files:**
- Modify: `tools/state/indexer.py` (two call-sites: lines 242-243 and 518-519, where `anchor_track` and `layout` are copied)
- Test: `tests/unit/state/test_indexer.py` (existing file — add assertions to an existing integration test, or add a new one)

- [ ] **Step 1: Locate the two copy-sites**

```bash
grep -n "'anchor_track'\|'layout'" tools/state/indexer.py
```

Both call-sites look like:
```python
'anchor_track': album_data.get('anchor_track'),
'layout': album_data.get('layout'),
```

- [ ] **Step 2: Write a failing test**

Find or create an integration test that calls the indexer on a tmp album with a frontmatter `mastering:` block and asserts `state.albums[slug]["mastering"]` is populated.

```bash
grep -n "def test.*anchor_track\|def test.*layout" tests/unit/state/test_indexer.py | head -5
```

If there's an existing anchor_track or layout indexer test, extend it to also create a README with `mastering:` and assert the block survives. Otherwise add a new test near the others:

```python
def test_indexer_surfaces_mastering_block(tmp_path: Path) -> None:
    """State cache must carry mastering overrides from album README
    frontmatter so master_album's config resolution can find them."""
    # Build a minimal content-root layout: artists/<name>/albums/<genre>/<slug>/README.md
    from tools.state.indexer import rebuild_state

    album_root = (
        tmp_path / "artists" / "testartist" / "albums" / "electronic" / "my-album"
    )
    album_root.mkdir(parents=True)
    (album_root / "README.md").write_text(
        "---\n"
        "Title: My Album\n"
        "Genre: electronic\n"
        "Status: In Progress\n"
        "mastering:\n"
        "  adm_validation_enabled: true\n"
        "---\n"
        "\n"
        "# My Album\n",
    )

    state = rebuild_state(content_root=tmp_path)
    albums = state.get("albums", {})
    # Slug lookup — find the one album entry.
    assert len(albums) == 1, f"Expected 1 album, got: {list(albums.keys())}"
    album = next(iter(albums.values()))
    assert album.get("mastering") == {"adm_validation_enabled": True}
```

Adapt the `rebuild_state` / fixture pattern to match whatever the existing tests use. If `rebuild_state` takes a different signature, follow the existing pattern.

- [ ] **Step 3: Run failing test**

```bash
.venv/bin/pytest tests/unit/state/test_indexer.py -k "mastering" -v
```

Expected: FAILS — indexer doesn't copy the field yet.

- [ ] **Step 4: Update both indexer call-sites**

At both sites (around lines 242-243 and 518-519 — confirm via grep), add `mastering` alongside `anchor_track` / `layout`:

```python
'anchor_track': album_data.get('anchor_track'),
'layout': album_data.get('layout'),
'mastering': album_data.get('mastering') or {},
```

The `or {}` guarantees the cached value is always a dict (consistent with what Task 1's parser produces).

- [ ] **Step 5: Verify test passes**

```bash
.venv/bin/pytest tests/unit/state/test_indexer.py -k "mastering" -v
```

Expected: PASS.

- [ ] **Step 6: Regression check**

```bash
.venv/bin/pytest tests/unit/state/ -v
```

Expected: no regressions.

- [ ] **Step 7: Commit**

```bash
git add tools/state/indexer.py tests/unit/state/test_indexer.py
git commit -m "$(cat <<'EOF'
feat: state indexer propagates mastering frontmatter to cache

Both indexer call-sites now copy album_data.get('mastering') into
state.albums[slug]['mastering'] (falling back to {} when absent).
Mirrors the anchor_track / layout pattern. master_album reads this
in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `build_delivery_targets` applies the frontmatter-required ADM rule

**Files:**
- Modify: `tools/mastering/config.py` (`build_delivery_targets` around line 56-176)
- Test: `tests/unit/mastering/test_config_album_overrides.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mastering/test_config_album_overrides.py`:

```python
"""build_delivery_targets must apply the per-album override rule for
mastering.adm_validation_enabled: frontmatter must be explicitly True,
else the effective value is False — regardless of config.yaml setting.

Other mastering.* keys follow the standard cascade (not covered by this
plan, but the kwarg shape supports them)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.config import build_delivery_targets


class TestAdmResolutionFromAlbumOverrides:
    def _call(self, *, config_adm, album_mastering):
        """Minimal build_delivery_targets call returning just
        adm_validation_enabled from the targets dict."""
        cfg = {
            "target_lufs": -14.0,
            "true_peak_ceiling": -1.0,
            "delivery_bit_depth": 24,
            "delivery_sample_rate": 96000,
            "adm_validation_enabled": config_adm,
        }
        targets = build_delivery_targets(
            cfg,
            preset=None,
            target_lufs_arg=0.0,
            ceiling_db_arg=0.0,
            source_sample_rate=48000,
            album_mastering=album_mastering,
        )
        return targets["adm_validation_enabled"]

    def test_frontmatter_true_config_false_runs_adm(self):
        """Explicit frontmatter opt-in: ADM runs."""
        result = self._call(
            config_adm=False,
            album_mastering={"adm_validation_enabled": True},
        )
        assert result is True

    def test_frontmatter_false_config_true_skips_adm(self):
        """Explicit frontmatter opt-out beats global config."""
        result = self._call(
            config_adm=True,
            album_mastering={"adm_validation_enabled": False},
        )
        assert result is False

    def test_frontmatter_missing_config_true_skips_adm(self):
        """New breaking-change default: frontmatter block missing (or key
        missing from the block) → ADM does NOT run. Config global is
        ignored for this key specifically."""
        # No mastering block at all:
        assert self._call(config_adm=True, album_mastering=None) is False
        assert self._call(config_adm=True, album_mastering={}) is False
        # Block present but key missing:
        assert self._call(
            config_adm=True,
            album_mastering={"ceiling_db": -1.5},
        ) is False

    def test_frontmatter_missing_config_false_skips_adm(self):
        """No frontmatter + no config → off (unchanged from prior default)."""
        assert self._call(config_adm=False, album_mastering=None) is False
        assert self._call(config_adm=False, album_mastering={}) is False

    def test_frontmatter_non_bool_truthy_still_requires_bool(self):
        """Explicit 1 / 'yes' / other truthy values are coerced via bool()
        — the spec requires explicit True but Python truthiness is
        acceptable (matches existing config.get loads). Document the
        behavior."""
        # Integer 1 from YAML is truthy
        assert self._call(
            config_adm=False,
            album_mastering={"adm_validation_enabled": 1},
        ) is True
        # Explicit 0 is falsy
        assert self._call(
            config_adm=True,
            album_mastering={"adm_validation_enabled": 0},
        ) is False
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_config_album_overrides.py -v
```

Expected: all 5 FAIL — `build_delivery_targets` doesn't accept `album_mastering` kwarg yet.

- [ ] **Step 3: Extend `build_delivery_targets` signature**

Open `tools/mastering/config.py`. Find `def build_delivery_targets(` (around line 56 — or wherever it sits; confirm via grep). The current signature is approximately:

```python
def build_delivery_targets(
    config: dict[str, Any],
    *,
    preset: dict[str, Any] | None,
    target_lufs_arg: float,
    ceiling_db_arg: float,
    source_sample_rate: int | None,
) -> dict[str, Any]:
```

Add a new kwarg AFTER the existing kwargs (keyword-only to preserve call-site stability):

```python
def build_delivery_targets(
    config: dict[str, Any],
    *,
    preset: dict[str, Any] | None,
    target_lufs_arg: float,
    ceiling_db_arg: float,
    source_sample_rate: int | None,
    album_mastering: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Then replace the existing `"adm_validation_enabled"` line (around line 162-164):

```python
        "adm_validation_enabled": bool(
            config.get("adm_validation_enabled", False)
        ),
```

With:

```python
        # Per-album opt-in for ADM validation (issue #353). The album's
        # README frontmatter `mastering.adm_validation_enabled: true` is
        # the ONLY path that enables ADM — global config.yaml setting is
        # ignored for this key. ADM is an Apple-submission-tier niche
        # that rarely matters for Suno workflows and shouldn't silently
        # add 3-5 min/track to every run. Other mastering.* frontmatter
        # keys (future scope) follow the standard frontmatter > config
        # > default cascade.
        "adm_validation_enabled": _resolve_adm_enabled(album_mastering),
```

And add the helper above `build_delivery_targets`:

```python
def _resolve_adm_enabled(album_mastering: dict[str, Any] | None) -> bool:
    """Per-album ADM resolution: frontmatter-required, default OFF.

    Returns True only when the album's frontmatter explicitly sets
    mastering.adm_validation_enabled to a truthy value. Absent block,
    absent key, and falsy values all resolve to False.
    """
    if not album_mastering:
        return False
    if "adm_validation_enabled" not in album_mastering:
        return False
    return bool(album_mastering["adm_validation_enabled"])
```

- [ ] **Step 4: Verify tests pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_config_album_overrides.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Regression check**

```bash
.venv/bin/pytest tests/unit/mastering/ tests/unit/state/ -v
```

Expected: no regressions. Existing callers of `build_delivery_targets` don't pass `album_mastering` — default `None` keeps the new path returning False, and any existing test that relied on `config.adm_validation_enabled: true` will now see False from this function. **If such tests exist, they need updating to either pass `album_mastering={"adm_validation_enabled": True}` or assert the new default-off semantic. This is the breaking-change footprint.**

Specifically check:
```bash
grep -rn "adm_validation_enabled.*True\|adm_validation_enabled=True" tests/ | head -10
```

If any tests assert `build_delivery_targets(...).get("adm_validation_enabled") == True` without passing `album_mastering`, update them to pass the per-album override. Don't silently weaken assertions.

- [ ] **Step 6: Commit**

```bash
git add tools/mastering/config.py tests/unit/mastering/test_config_album_overrides.py
# If you had to update any existing tests:
# git add tests/unit/<affected_test>.py
git commit -m "$(cat <<'EOF'
feat: per-album ADM resolution with default-off semantic

build_delivery_targets gains album_mastering kwarg. For
adm_validation_enabled, resolution is frontmatter-required — the
album's README frontmatter mastering.adm_validation_enabled: true
is the only path that enables ADM. Global config.yaml is ignored
for this key.

BREAKING CHANGE: deployments that had ADM enabled via global
config.yaml (mastering.adm_validation_enabled: true) and relied
on it running automatically will see ADM skip. Add the per-album
frontmatter block to each album you want validated.

Rationale: ADM is an Apple-submission-tier niche and rarely
matters for Suno workflows. Defaulting OFF avoids silently adding
3-5 min/track of AAC encode/decode overhead on runs that can't
pass anyway (see issue #353 and the April halt-report thread).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `master_album` threads `album_state.mastering` into config resolution

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` — locate the `build_delivery_targets` call in master_album's pre-flight / config-resolution area
- Test: `tests/unit/mastering/test_master_album_adm_off_end_to_end.py` (NEW)

- [ ] **Step 1: Locate the `build_delivery_targets` call site in master_album**

```bash
grep -n "build_delivery_targets\|album_state\|from tools.mastering.config" servers/bitwize-music-server/handlers/processing/audio.py 2>&1 | head -10
```

`build_delivery_targets` is called somewhere in `master_album`'s pre-flight. Read the surrounding ~20 lines to understand how `album_state` is already available (it IS — the existing code at `_album_stages.py:567` pulls `anchor_track` from the same cache; `audio.py` has parallel access).

- [ ] **Step 2: Write failing regression test**

Create `tests/unit/mastering/test_master_album_adm_off_end_to_end.py`:

```python
"""Regression: master_album runs end-to-end with ADM off. Explicitly
covers the new default-off semantic — no album frontmatter mastering
block means the ADM stage is skipped and the pipeline completes
through all post-loop stages (mastering_samples, post_qc, archival,
metadata, layout, signature_persist, status_update)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers import _shared  # noqa: E402
from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402
from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


def _write_sine_wav(path: Path, *, rate: int = 44100,
                    seconds: float = 30.0, freq: float = 3500.0) -> Path:
    import soundfile as sf
    n = int(seconds * rate)
    t = np.arange(n) / rate
    mono = 0.3 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.column_stack([mono, mono]), rate, subtype="PCM_24")
    return path


def test_master_album_completes_with_adm_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """With no frontmatter mastering block (default off), master_album
    completes the full pipeline. ADM stage is marked skipped. No dark
    casualty / warn-fallback code paths are triggered. All post-loop
    stages run."""
    album_slug = "adm-off-regression"
    _write_sine_wav(tmp_path / "01-track.wav")

    # Install the album in the fake cache with NO mastering frontmatter
    # block — default-off semantic under test.
    fake_state = {
        "albums": {
            album_slug: {
                "path": str(tmp_path),
                "status": "In Progress",
                "tracks": {},
                # 'mastering' key absent or {} — both resolve to ADM off.
                "mastering": {},
            }
        }
    }

    class _FakeCache:
        def get_state(self):
            return fake_state

        def get_state_ref(self):
            return fake_state

    monkeypatch.setattr(_shared, "cache", _FakeCache())
    monkeypatch.setattr(
        album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None,
    )

    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    # Force global config to have ADM ON — the point is that frontmatter
    # default-off beats global ON. If the orchestrator honored global,
    # the ADM stage would run; since the frontmatter is empty, it should
    # NOT run.
    from tools.mastering import config as _master_config
    real_load = _master_config.load_mastering_config

    def _load_with_adm_on() -> dict:
        cfg = real_load()
        cfg["adm_validation_enabled"] = True
        return cfg

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(_master_config, "load_mastering_config", _load_with_adm_on):
        result = json.loads(asyncio.run(audio_mod.master_album(album_slug=album_slug)))

    # Pipeline completed (no halt).
    assert result.get("failed_stage") is None, (
        f"master_album halted: {result.get('failure_detail')}"
    )

    stages = result["stages"]

    # ADM stage must be explicitly skipped, not "pass" / "warn" / "fail".
    adm = stages.get("adm_validation", {})
    assert adm.get("status") == "skipped", (
        f"Expected adm_validation skipped (default-off), got: {adm}"
    )

    # All post-loop stages ran — this is the anti-regression guard.
    # If ADM-off broke ANY of these, we'd halt before reaching them.
    for must_run in ("mastering_samples", "post_qc", "archival",
                     "layout", "signature_persist", "status_update"):
        assert must_run in stages, (
            f"Stage {must_run} did not run with ADM off — "
            f"stages reached: {list(stages.keys())}"
        )


def test_master_album_adm_on_via_frontmatter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Opt-in case: frontmatter explicitly sets
    mastering.adm_validation_enabled: true. ADM stage must run
    (and since our fake clip check returns clean, it passes)."""
    album_slug = "adm-on-regression"
    _write_sine_wav(tmp_path / "01-track.wav")

    fake_state = {
        "albums": {
            album_slug: {
                "path": str(tmp_path),
                "status": "In Progress",
                "tracks": {},
                "mastering": {"adm_validation_enabled": True},
            }
        }
    }

    class _FakeCache:
        def get_state(self):
            return fake_state

        def get_state_ref(self):
            return fake_state

    monkeypatch.setattr(_shared, "cache", _FakeCache())
    monkeypatch.setattr(
        album_stages_mod, "_embed_wav_metadata_fn", lambda *a, **kw: None,
    )

    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    # Stub adm check to return clean so the pipeline completes.
    def _clean_adm_check(path, *, encoder="aac", ceiling_db=-1.0,
                        bitrate_kbps=256):
        return {
            "filename": Path(path).name,
            "encoder_used": encoder,
            "clip_count": 0,
            "peak_db_decoded": ceiling_db - 0.5,
            "ceiling_db": ceiling_db,
            "clips_found": False,
        }

    monkeypatch.setattr(album_stages_mod, "_adm_check_fn", _clean_adm_check)

    # Global config OFF — frontmatter wins.
    from tools.mastering import config as _master_config
    real_load = _master_config.load_mastering_config

    def _load_with_adm_off() -> dict:
        cfg = real_load()
        cfg["adm_validation_enabled"] = False
        return cfg

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(_master_config, "load_mastering_config", _load_with_adm_off):
        result = json.loads(asyncio.run(audio_mod.master_album(album_slug=album_slug)))

    assert result.get("failed_stage") is None
    adm = result["stages"].get("adm_validation", {})
    # ADM stage ran — status is "pass" (no clips) not "skipped".
    assert adm.get("status") == "pass", (
        f"Expected adm_validation pass with frontmatter opt-in, got: {adm}"
    )
```

Adapt the cache-mock / `_embed_wav_metadata_fn` / `_adm_check_fn` patches to match the existing integration test pattern in `tests/unit/mastering/test_master_album_dark_track_adm.py` (which uses the same shape).

- [ ] **Step 3: Run failing tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_adm_off_end_to_end.py -v
```

Expected: tests FAIL — `master_album` isn't reading `album_state["mastering"]` yet, so `build_delivery_targets` gets `album_mastering=None` and ADM resolves OFF (which is actually what test 1 wants — but test 2 would fail because frontmatter opt-in isn't threaded).

Actually: depending on implementation order, test 1 may pass already (via default-off from Task 3). Test 2 is the one that must fail until this task wires the frontmatter through.

- [ ] **Step 4: Wire `album_state["mastering"]` into `build_delivery_targets` call**

In `master_album` (audio.py), locate where `build_delivery_targets` is called. The current call looks approximately like:

```python
targets = build_delivery_targets(
    config,
    preset=preset,
    target_lufs_arg=...,
    ceiling_db_arg=...,
    source_sample_rate=...,
)
```

Before the call, pull `album_state["mastering"]` from cache (same pattern as the existing `anchor_track` pull at `_album_stages.py:567-569`):

```python
    # Per-album mastering overrides (issue #353). The album README's
    # frontmatter `mastering:` block is the authoritative source for
    # adm_validation_enabled (default-off semantic — see config.py's
    # _resolve_adm_enabled). Future keys in the same block (ceiling,
    # target_lufs, archival_enabled) will slot in the same way via
    # build_delivery_targets' album_mastering kwarg.
    _state_albums = (_shared.cache.get_state() or {}).get("albums", {})
    _album_state = _state_albums.get(_normalize_slug(album_slug), {})
    _album_mastering = _album_state.get("mastering") or {}
```

(Confirm `_normalize_slug` is imported in audio.py — if not, use whatever slug normalization the rest of audio.py uses for cache lookups; grep for `_normalize_slug` in audio.py.)

Then pass to the call:

```python
    targets = build_delivery_targets(
        config,
        preset=preset,
        target_lufs_arg=...,
        ceiling_db_arg=...,
        source_sample_rate=...,
        album_mastering=_album_mastering,
    )
```

- [ ] **Step 5: Verify tests pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_adm_off_end_to_end.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Run the broader mastering + adm regression suite**

```bash
.venv/bin/pytest tests/unit/mastering/ -v --no-header 2>&1 | tail -20
```

Expected: no regressions. If any existing integration test relied on config-level `adm_validation_enabled: true` automatically running ADM, that test must now either (a) populate `mastering: {"adm_validation_enabled": True}` in its fake cache state, or (b) be updated to expect ADM skipped. Update tests explicitly — don't weaken assertions.

- [ ] **Step 7: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py \
        tests/unit/mastering/test_master_album_adm_off_end_to_end.py
# Include any updated existing tests:
# git add tests/unit/mastering/<updated_test>.py
git commit -m "$(cat <<'EOF'
feat: master_album threads per-album mastering frontmatter to config

Reads state.albums[slug].mastering from cache and passes it as
album_mastering kwarg to build_delivery_targets. The orchestrator
itself makes no new decisions — all resolution logic lives in
config.py's _resolve_adm_enabled. This commit is just the data
bridge.

Includes regression tests for both sides of the default-off
semantic: ADM off runs the full pipeline through status_update;
ADM on via frontmatter explicitly enables the adm_validation
stage even when global config has it off.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Template + CHANGELOG

**Files:**
- Modify: `templates/album.md` (document the new frontmatter block)
- Modify: `CHANGELOG.md` (breaking-change entry under `[Unreleased]`)

- [ ] **Step 1: Document the frontmatter block in the album template**

Open `templates/album.md`. Find the existing frontmatter documentation — look for where `anchor_track:` / `layout:` are documented. Add a `mastering:` block after them with this exact content:

```markdown
### mastering (optional)

Per-album mastering settings. Currently supports:

- `adm_validation_enabled: true` — opt in to Apple Digital Masters
  inter-sample peak validation. **Defaults to OFF** even when
  global `config.yaml::mastering.adm_validation_enabled` is `true`.
  ADM runs the AAC encode/decode check on every mastered file and
  can add 3-5 min/track to the pipeline. Only enable when the
  album's source material is spectrally viable (well-balanced
  highs) AND you're submitting the album for Apple Digital Masters
  certification. For most Suno-generated albums, leave this off.

Example (opt in for this album only):

\`\`\`yaml
mastering:
  adm_validation_enabled: true
\`\`\`

Omit the block entirely to use the default (ADM off).
```

(Note: use actual backticks in the doc, not escaped — my escape is only because this plan itself is a Markdown file with backtick fences.)

- [ ] **Step 2: CHANGELOG entry**

Open `CHANGELOG.md`. Add a new entry at the top of `[Unreleased]`:

```markdown
### Changed (BREAKING)
- **ADM validation is now per-album opt-in via README frontmatter**
  (issue #353). Prior behavior: `mastering.adm_validation_enabled:
  true` in `~/.bitwize-music/config.yaml` would run ADM on every
  album. New behavior: the album's own README must include
  `mastering: { adm_validation_enabled: true }` in its frontmatter.
  Global `config.yaml` value is ignored for this key.

  Context: a significant chunk of mid-April 2026 went into building
  out the ADM pipeline — dark-casualty classification, per-track
  ceiling tightening, harmonic excitation in polish, warn-fallback
  sidecars, observability instrumentation (#347, #348, #349, #350,
  #351, #352) — only to discover at the end that ADM (Apple Digital
  Masters inter-sample peak validation) is an Apple-submission-tier
  niche that almost never matters for Suno-generated tracks. Suno
  output typically lacks the high-mid spectral content ADM requires,
  so most tracks ship dark-casualty-flagged regardless of how much
  the pipeline works at them.

  Rather than rip out the ADM infrastructure — the work has real
  value for the minority of albums that ARE submission-viable, and
  much of the underlying machinery (warn-fallback contract,
  per-track ceiling architecture, spectral regression guard) pays
  off on normal mastering too — it stays enabled per-album via
  frontmatter opt-in and defaults OFF for everyone else. No more
  silent 3-5 min/track overhead on runs that can't pass anyway.

  Operators who want ADM per album add `mastering: {
  adm_validation_enabled: true }` to the album's README
  frontmatter. Global `config.yaml` value is ignored for this
  key — it's the kind of decision that should live with the
  album, not with the operator's memory.

### Added
- Per-album `mastering:` frontmatter block. Currently accepts
  `adm_validation_enabled`; future keys (ceiling_db, target_lufs,
  archival_enabled) will use the same block with standard
  frontmatter > config > default cascade.
```

- [ ] **Step 3: Commit**

```bash
git add templates/album.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs: per-album mastering frontmatter block (template + CHANGELOG)

Documents the new mastering: frontmatter block in the album
README template. CHANGELOG flags the breaking-change semantic for
adm_validation_enabled (global config no longer sufficient; must
opt in per-album).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `make check` gate + PR

**Files:** none (verification + submission)

- [ ] **Step 1: `make check`**

```bash
make check 2>&1 | tail -15
```

Expected: PASS (ruff + bandit + mypy + full pytest suite + coverage > 75 %).

If any existing test fails, it's almost certainly an ADM-related test that assumed `config.yaml::adm_validation_enabled: true` would auto-enable ADM. Fix those by adding `mastering: {"adm_validation_enabled": True}` to the fixture's cache state, not by weakening the assertion.

- [ ] **Step 2: Push + PR**

Branch name: `feat/per-album-mastering-overrides` off `develop`.

```bash
git push -u origin feat/per-album-mastering-overrides
gh pr create --base develop --title "feat: per-album mastering overrides (ADM default-off)" --body "..."
```

PR body should:
- Reference issue #353.
- Lead with the **BREAKING CHANGE** summary for `adm_validation_enabled`.
- Include before/after examples of the frontmatter.
- Note that other `mastering.*` keys are out of scope for this PR but the block shape accepts them for future work.
- Flag the regression test `test_master_album_completes_with_adm_off` as the anti-regression guard operators can trust.

---

## Self-Review Checklist

1. **Spec coverage:**
   - Parser: Task 1
   - Indexer: Task 2
   - Config resolution with default-off rule: Task 3
   - Orchestrator wiring: Task 4
   - Regression test for "normal mastering works with ADM off": Task 4 (`test_master_album_completes_with_adm_off`)
   - Template + CHANGELOG: Task 5
   - Gate + PR: Task 6

2. **No placeholders:** Every code block is complete. The "adapt to existing integration test pattern" note in Task 4 Step 2 is explicit about which file to mirror (`test_master_album_dark_track_adm.py`).

3. **Type consistency:**
   - `album_mastering: dict[str, Any] | None` everywhere
   - `result["mastering"] = {}` (empty dict, not None) — so downstream `.get()` always finds a dict
   - `_resolve_adm_enabled` returns `bool`
   - `state.albums[slug]["mastering"]` is always a dict (never None — the `or {}` at indexer site guarantees it)

4. **Breaking-change footprint audited:**
   - Any test that passed `config.adm_validation_enabled: true` and expected ADM to run will need updating. Task 3 Step 5 has the grep to find them.
   - CHANGELOG flags this explicitly.

5. **Default-off invariant:** Tested by `test_master_album_completes_with_adm_off` end-to-end. If anyone later "relaxes" the rule to allow config fallback, that test breaks loudly.
