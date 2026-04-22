"""analyze_mix_issues must key per-stem analysis by canonical STEM_NAMES
category (matching discover_stems' output), not by the raw WAV filename
stem. Regression guard for the bridge bug between analyzer output and
mix_track_stems' analyzer_recs lookup — previously keys didn't match,
so overrides_applied was empty even when the analyzer emitted
recommendations."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _write_wav(path: Path, *, rate: int = 44100, seconds: float = 1.5) -> None:
    """Write a minimal stereo WAV (white-noise-ish)."""
    rng = np.random.default_rng(0)
    n = int(seconds * rate)
    data = (rng.standard_normal((n, 2)) * 0.05).astype(np.float64)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, rate, subtype="PCM_24")


def _install_album(monkeypatch: pytest.MonkeyPatch, audio_path: Path,
                   album_slug: str) -> None:
    from handlers import _shared
    fake_state = {
        "albums": {
            album_slug: {
                "path": str(audio_path), "status": "In Progress", "tracks": {},
            }
        }
    }

    class _FakeCache:
        def get_state(self):
            return fake_state

        def get_state_ref(self):
            return fake_state

    monkeypatch.setattr(_shared, "cache", _FakeCache())


def test_analyzer_keys_stems_by_canonical_category(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When stems are named like '01-Vocals.wav' / '02-Drums.wav',
    analyze_mix_issues must still key the stems dict by canonical
    STEM_NAMES categories ('vocals', 'drums'), not by the filename
    stem ('01-Vocals', '02-Drums'). Otherwise mix_track_stems'
    analyzer_recs lookup (which uses STEM_NAMES) finds nothing."""
    from handlers.processing import _helpers as processing_helpers
    from handlers.processing.mixing import analyze_mix_issues

    album_slug = "canonical-key-test"
    track_dir = tmp_path / "stems" / "01-mytrack"
    _write_wav(track_dir / "01-Vocals.wav")
    _write_wav(track_dir / "02-Drums.wav")
    _write_wav(track_dir / "03-Bass.wav")
    _write_wav(track_dir / "04-MysteryStem.wav")  # should route to "other"

    _install_album(monkeypatch, tmp_path, album_slug)

    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(analyze_mix_issues(album_slug))

    result = json.loads(result_json)
    assert "error" not in result, (
        f"Analyzer errored: {result.get('error')}"
    )
    tracks = result.get("tracks", [])
    assert len(tracks) == 1
    track = tracks[0]
    assert track["track"] == "01-mytrack"
    stems = track["stems"]
    # Keys MUST be canonical categories from STEM_NAMES, not filename stems.
    assert "vocals" in stems, (
        f"Expected 'vocals' canonical key, got stems: {list(stems.keys())}"
    )
    assert "drums" in stems
    assert "bass" in stems
    assert "other" in stems  # MysteryStem falls through to other
    # And the filename-based keys must NOT be present.
    assert "01-Vocals" not in stems
    assert "01-vocals" not in stems
    assert "02-Drums" not in stems
    assert "04-MysteryStem" not in stems


def test_analyzer_recs_match_polish_stem_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """End-to-end: recs from the analyzer must be lookup-able by
    mix_track_stems using STEM_NAMES. This is the full bridge regression."""
    from handlers.processing import _helpers as processing_helpers
    from handlers.processing.mixing import analyze_mix_issues
    from tools.mixing.mix_tracks import STEM_NAMES

    album_slug = "bridge-test"
    track_dir = tmp_path / "stems" / "01-track"
    _write_wav(track_dir / "lead_vocals.wav")
    _write_wav(track_dir / "kick_drum.wav")

    _install_album(monkeypatch, tmp_path, album_slug)

    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(analyze_mix_issues(album_slug))

    result = json.loads(result_json)
    tracks = result.get("tracks", [])
    assert len(tracks) == 1
    stems = tracks[0]["stems"]

    # Every key in stems dict must be in STEM_NAMES — that's the
    # contract polish relies on.
    for key in stems.keys():
        assert key in STEM_NAMES, (
            f"Analyzer stored stem under non-canonical key {key!r}; "
            f"polish won't find it. Valid keys: {STEM_NAMES}"
        )


def test_analyzer_multi_file_same_category_coalesces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Multiple files in the same category (e.g., drums_kick.wav +
    drums_snare.wav) land under a single 'drums' key. Analyzer should
    produce one result per category — polish later combines the files
    during processing."""
    from handlers.processing import _helpers as processing_helpers
    from handlers.processing.mixing import analyze_mix_issues

    album_slug = "multi-file-cat"
    track_dir = tmp_path / "stems" / "01-track"
    _write_wav(track_dir / "drums_kick.wav")
    _write_wav(track_dir / "drums_snare.wav")
    _write_wav(track_dir / "drums_hats.wav")

    _install_album(monkeypatch, tmp_path, album_slug)

    def _fake_resolve(slug, subfolder=""):
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(analyze_mix_issues(album_slug))

    result = json.loads(result_json)
    stems = result["tracks"][0]["stems"]
    # Only one "drums" entry; the three files all categorize to drums.
    assert "drums" in stems
    # No filename-stem keys leaked through.
    for fname_stem in ("drums_kick", "drums_snare", "drums_hats"):
        assert fname_stem not in stems
