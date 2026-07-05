"""_stage_layout must honor its 'Returns: None always, never halt' contract
even when a pre-existing LAYOUT.md contains invalid UTF-8 bytes.

Regression for issue #399: the read of a prior LAYOUT.md
(``layout_path.read_text(encoding="utf-8")``) ran OUTSIDE the stage's
protective try/except, which only caught ``(LayoutError, OSError)``. A corrupt
or binary LAYOUT.md raises ``UnicodeDecodeError`` (a ``ValueError`` subclass,
NOT an ``OSError``), so it escaped the guard and aborted the master_album
pipeline. A corrupt prior layout must instead be logged to warnings while the
stage degrades gracefully and still writes a fresh LAYOUT.md.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def _run_layout_stage(audio_dir: Path, mastered_names: list[str]):
    from handlers.processing._album_stages import MasterAlbumCtx, _stage_layout

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx = MasterAlbumCtx(
        album_slug="test", genre="pop", target_lufs=-14.0, ceiling_db=-1.0,
        cut_highmid=0.0, cut_highs=0.0, source_subfolder="",
        freeze_signature=False, new_anchor=False, loop=loop,
        audio_dir=audio_dir,
        mastered_files=[Path(name) for name in mastered_names],
    )
    try:
        result = loop.run_until_complete(_stage_layout(ctx))
    finally:
        loop.close()
    return ctx, result


def test_non_utf8_prior_layout_does_not_halt(tmp_path: Path) -> None:
    """A LAYOUT.md with invalid UTF-8 bytes must not raise out of the stage."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    # 0xFF/0xFE/0xC3-0x28 are invalid UTF-8 sequences → read_text(utf-8) raises
    # UnicodeDecodeError, which is a ValueError (not an OSError).
    (audio_dir / "LAYOUT.md").write_bytes(b"\xff\xfe\x00\x80 not utf-8 \xc3\x28")

    ctx, result = _run_layout_stage(audio_dir, ["01-a.wav", "02-b.wav"])

    # Contract: the stage returns None and never halts the pipeline.
    assert result is None
    # The corrupt prior LAYOUT.md is surfaced to the operator via warnings.
    assert any("LAYOUT" in str(w) for w in ctx.warnings)
    # A layout stage result is still recorded (structured result not discarded).
    assert "layout" in ctx.stages


def test_valid_prior_layout_still_parses(tmp_path: Path) -> None:
    """A well-formed prior LAYOUT.md is read and its hand-edits are preserved."""
    from tools.mastering.layout import (
        parse_layout_yaml,
        render_layout_markdown,
    )

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    prior = [
        {
            "from": "01-a.wav",
            "to": "02-b.wav",
            "mode": "gapless",
            "gap_ms": 0,
            "tail_fade_ms": 0,
            "head_fade_ms": 0,
        },
    ]
    (audio_dir / "LAYOUT.md").write_text(
        render_layout_markdown("test", prior), encoding="utf-8"
    )

    ctx, result = _run_layout_stage(audio_dir, ["01-a.wav", "02-b.wav"])

    assert result is None
    # No warnings for a clean, valid prior layout.
    assert not any("LAYOUT" in str(w) for w in ctx.warnings)
    # The hand-edited gapless transition survived the parse → compute → render
    # round-trip, proving the prior file was read and fed into the emitter.
    rewritten = parse_layout_yaml(
        (audio_dir / "LAYOUT.md").read_text(encoding="utf-8")
    )
    assert rewritten[0]["mode"] == "gapless"
