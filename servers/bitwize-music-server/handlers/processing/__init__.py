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
    album_coherence_check,
    album_coherence_correct,
    analyze_audio,
    fix_dynamic_track,
    master_album,
    master_audio,
    master_with_reference,
    measure_album_signature,
    mono_fold_check,
    prune_archival,
    qc_audio,
    render_codec_preview,
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
    polish_and_master_album,
    polish_audio,
)

# Submodules with register functions
from handlers.processing import audio as _audio
from handlers.processing import mixing as _mixing
from handlers.processing import sheet_music as _sheet_music
from handlers.processing import video as _video


def register(mcp: Any) -> None:
    """Register all processing tools with the MCP server."""
    _audio.register(mcp)
    _sheet_music.register(mcp)
    _video.register(mcp)
    _mixing.register(mcp)
