"""Processing tools — audio mastering, sheet music, promo videos, mix polishing.

This package splits what was a single 2700-line module into focused submodules:
- audio.py      — mastering, analysis, QC, dynamic range fix
- sheet_music.py — transcription, singles, songbook, cloud publishing
- video.py      — promo video and album sampler generation
- mixing.py     — per-stem polish, mix issue analysis, polish pipeline
- _helpers.py   — shared dependency checks and importers
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Submodule imports — tools re-exported for backward compatibility.
# Tests and server.py import from `handlers.processing` directly.
# ---------------------------------------------------------------------------

# Audio mastering tools
from handlers.processing.audio import (  # noqa: F401
    analyze_audio,
    fix_dynamic_track,
    master_album,
    master_audio,
    master_with_reference,
    qc_audio,
)

# Sheet music tools
from handlers.processing.sheet_music import (  # noqa: F401
    create_songbook,
    prepare_singles,
    publish_sheet_music,
    transcribe_audio,
)

# Promo video tools
from handlers.processing.video import (  # noqa: F401
    generate_album_sampler,
    generate_promo_videos,
)

# Mix polish tools
from handlers.processing.mixing import (  # noqa: F401
    analyze_mix_issues,
    polish_album,
    polish_audio,
)

# Submodules with register functions
from handlers.processing import audio as _audio
from handlers.processing import mixing as _mixing
from handlers.processing import sheet_music as _sheet_music
from handlers.processing import video as _video

# Import _helpers module — submodules access helpers through this module object.
# Tests that patch _processing_mod._check_X use __getattr__/__setattr__ below
# to propagate patches to the _helpers module where submodules look them up.
from handlers.processing import _helpers


# ---------------------------------------------------------------------------
# Backward-compatible attribute access for test patching.
#
# Tests do: patch.object(_processing_mod, "_check_mastering_deps", ...)
# Submodules do: _helpers._check_mastering_deps()
#
# __getattr__ delegates reads of helper names to the _helpers module.
# __setattr__ (via patch.object) propagates writes to _helpers so submodule
# code sees the patched version.
# ---------------------------------------------------------------------------

_HELPER_NAMES = frozenset({
    "_build_title_map",
    "_check_anthemscore",
    "_check_cloud_enabled",
    "_check_ffmpeg",
    "_check_mastering_deps",
    "_check_matchering",
    "_check_mixing_deps",
    "_check_songbook_deps",
    "_extract_track_number_from_stem",
    "_import_cloud_module",
    "_import_sheet_music_module",
    "_resolve_audio_dir",
})


def __getattr__(name: str) -> Any:
    if name in _HELPER_NAMES:
        return getattr(_helpers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Hook for unittest.mock.patch.object — when a test patches a helper name
# on this package, propagate the patch to the _helpers module so submodule
# code (which accesses _helpers.X) sees the mock.
_original_setattr = object.__setattr__


class _PatchProxy:
    """Module-level __setattr__ isn't directly supported, so we use
    sys.modules replacement to intercept attribute writes from mock.patch."""
    pass


import sys as _sys  # noqa: E402
import types as _types  # noqa: E402

_this_module = _sys.modules[__name__]
_original_module_dict = _this_module.__dict__


class _ModuleProxy(_types.ModuleType):
    """Wrapper that intercepts setattr for helper names."""

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _HELPER_NAMES:
            setattr(_helpers, name, value)
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name in _HELPER_NAMES:
            # mock.patch restores by deleting then setting
            try:
                delattr(_helpers, name)
            except AttributeError:
                pass
        try:
            super().__delattr__(name)
        except AttributeError:
            pass


_proxy = _ModuleProxy(__name__)
_proxy.__dict__.update(_original_module_dict)
_proxy.__path__ = getattr(_this_module, "__path__", [])
_proxy.__file__ = _this_module.__file__
_proxy.__package__ = _this_module.__package__
_proxy.__spec__ = _this_module.__spec__
_sys.modules[__name__] = _proxy


def register(mcp: Any) -> None:
    """Register all processing tools with the MCP server."""
    _audio.register(mcp)
    _sheet_music.register(mcp)
    _video.register(mcp)
    _mixing.register(mcp)


# Attach register to proxy so it's accessible after module replacement
_proxy.register = register
