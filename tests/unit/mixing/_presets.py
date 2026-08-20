"""Preset-isolation helpers shared by the mixing unit tests (#553).

Resolving a stem's settings reads two user-override files out of the
developer's real ``~/.bitwize-music`` config:
``{overrides}/mix-presets.yaml`` (``load_mix_presets``) and, through
``_resolve_master_click_thresholds``, ``{overrides}/mastering-presets.yaml``
(``load_genre_presets``). A test that asserts what a *shipped* default is
— or that measures audio processed with the shipped chain — therefore
asserts what the machine running it happens to be configured for. These
helpers point both sources somewhere known.
"""

from __future__ import annotations

import copy
from typing import Any

_SHIPPED_PRESET_CACHE: dict[str, Any] = {}


def point_overrides_at(monkeypatch: Any, override_dir: Any) -> None:
    """Resolve BOTH preset override sources to `override_dir` (or None)."""
    import tools.mastering.master_tracks as mast
    import tools.mixing.mix_tracks as mt

    monkeypatch.setattr(mt, '_get_overrides_path', lambda: override_dir)
    monkeypatch.setattr(mt, 'MIX_PRESETS', mt.load_mix_presets())
    monkeypatch.setattr(mast, '_get_overrides_path', lambda: override_dir)
    monkeypatch.setattr(mast, 'GENRE_PRESETS', mast.load_genre_presets())


def shipped_presets_only(monkeypatch: Any) -> None:
    """Resolve presets from the files this repo ships, nothing else.

    The two YAML loads are cached across the session (they only ever read
    the same shipped files) and handed out as deep copies, so no test can
    mutate what the next one sees.
    """
    import tools.mastering.master_tracks as mast
    import tools.mixing.mix_tracks as mt

    monkeypatch.setattr(mt, '_get_overrides_path', lambda: None)
    monkeypatch.setattr(mast, '_get_overrides_path', lambda: None)
    if not _SHIPPED_PRESET_CACHE:
        _SHIPPED_PRESET_CACHE['mix'] = mt.load_mix_presets()
        _SHIPPED_PRESET_CACHE['mastering'] = mast.load_genre_presets()

    monkeypatch.setattr(mt, 'MIX_PRESETS', copy.deepcopy(_SHIPPED_PRESET_CACHE['mix']))
    monkeypatch.setattr(
        mast, 'GENRE_PRESETS', copy.deepcopy(_SHIPPED_PRESET_CACHE['mastering']),
    )


def install_override(tmp_path: Any, monkeypatch: Any, yaml_text: str) -> Any:
    """Write a user override file and reload the presets from it.

    Mirrors the real startup path: `load_mix_presets()` reads
    `{overrides}/mix-presets.yaml`, and the module-level `MIX_PRESETS`
    that `_get_stem_settings` consults is the result. The overrides dir
    is under `tmp_path` and the mastering overlay is pointed at it too,
    so the only overrides in play are the ones this call writes.
    """
    override_dir = tmp_path / "overrides"
    override_dir.mkdir(exist_ok=True)
    (override_dir / "mix-presets.yaml").write_text(yaml_text)
    point_overrides_at(monkeypatch, override_dir)
    return override_dir
