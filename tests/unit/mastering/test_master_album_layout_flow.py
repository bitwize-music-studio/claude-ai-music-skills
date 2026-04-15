"""Integration tests for Stage 6.7 (LAYOUT.md emitter) inside
master_album (#290 phase 5, step 7)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402


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
                   *, layout_frontmatter: dict | None = None,
                   status: str = "In Progress") -> None:
    from handlers import _shared
    album_entry = {
        "path": str(audio_path),
        "status": status,
        "tracks": {},
    }
    if layout_frontmatter is not None:
        album_entry["layout"] = layout_frontmatter
    fake_state = {"albums": {album_slug: album_entry}}
    class _FakeCache:
        def get_state(self): return fake_state
        def get_state_ref(self): return fake_state
    monkeypatch.setattr(_shared, "cache", _FakeCache())


def _run(tmp_path: Path, album_slug: str) -> dict:
    def _fake_resolve(slug, *_, **__):
        return None, tmp_path
    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        return json.loads(asyncio.run(
            audio_mod.master_album(album_slug=album_slug)
        ))


def _extract_yaml(layout_md: str) -> dict:
    start = layout_md.index("```yaml") + len("```yaml")
    end = layout_md.index("```", start)
    return yaml.safe_load(layout_md[start:end])


def test_layout_file_written_with_default_gap_mode(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sine_wav(tmp_path / "01-a.wav")
    _write_sine_wav(tmp_path / "02-b.wav", freq=330.0)
    _write_sine_wav(tmp_path / "03-c.wav", freq=440.0)
    _install_album(monkeypatch, tmp_path, "layout-album")

    result = _run(tmp_path, "layout-album")
    assert result.get("failed_stage") is None, result.get("failure_detail")
    assert result["stages"]["layout"]["status"] == "pass"

    layout_path = tmp_path / "LAYOUT.md"
    assert layout_path.is_file()

    parsed = _extract_yaml(layout_path.read_text(encoding="utf-8"))
    assert len(parsed["transitions"]) == 2
    for t in parsed["transitions"]:
        assert t["mode"] == "gap"
        assert t["gap_ms"] == 1500
        assert t["tail_fade_ms"] == 100
        assert t["head_fade_ms"] == 50


def test_layout_file_honors_gapless_frontmatter(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sine_wav(tmp_path / "01-a.wav")
    _write_sine_wav(tmp_path / "02-b.wav", freq=330.0)
    _install_album(
        monkeypatch, tmp_path, "gapless-album",
        layout_frontmatter={"default_transition": "gapless"},
    )

    result = _run(tmp_path, "gapless-album")
    assert result.get("failed_stage") is None

    layout_path = tmp_path / "LAYOUT.md"
    parsed = _extract_yaml(layout_path.read_text(encoding="utf-8"))
    assert len(parsed["transitions"]) == 1
    assert parsed["transitions"][0]["mode"] == "gapless"
    assert parsed["transitions"][0]["gap_ms"] == 0


def test_layout_single_track_album_emits_empty_transitions(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sine_wav(tmp_path / "01-solo.wav")
    _install_album(monkeypatch, tmp_path, "solo-album")

    result = _run(tmp_path, "solo-album")
    assert result.get("failed_stage") is None

    layout_path = tmp_path / "LAYOUT.md"
    assert layout_path.is_file()
    md = layout_path.read_text(encoding="utf-8")
    assert "transitions: []" in md
    assert "Single-track" in md


def test_layout_stage_reports_file_path(tmp_path: Path, monkeypatch) -> None:
    _write_sine_wav(tmp_path / "01-a.wav")
    _write_sine_wav(tmp_path / "02-b.wav", freq=330.0)
    _install_album(monkeypatch, tmp_path, "layout-album")

    result = _run(tmp_path, "layout-album")
    layout_stage = result["stages"]["layout"]
    assert layout_stage["path"] == str(tmp_path / "LAYOUT.md")
    assert layout_stage["default_transition"] == "gap"
    assert layout_stage["transition_count"] == 1


def test_layout_never_halts_pipeline_on_write_failure(
    tmp_path: Path, monkeypatch
) -> None:
    _write_sine_wav(tmp_path / "01-a.wav")
    _write_sine_wav(tmp_path / "02-b.wav", freq=330.0)
    _install_album(monkeypatch, tmp_path, "layout-album")

    # Force atomic_write_text to raise so we exercise the warn path.
    from handlers import _atomic

    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(_atomic, "atomic_write_text", _boom)
    # audio_mod imports atomic_write_text at call time through the layout
    # path, so patch both the re-export and the original.
    if hasattr(audio_mod, "atomic_write_text"):
        monkeypatch.setattr(audio_mod, "atomic_write_text", _boom)

    result = _run(tmp_path, "layout-album")
    # Pipeline still succeeds overall; layout stage records warn.
    assert result.get("failed_stage") is None
    assert result["stages"]["layout"]["status"] == "warn"
    assert any("layout" in str(w).lower() for w in result["warnings"])
