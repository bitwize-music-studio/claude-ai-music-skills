"""Behavior tests for master_audio's cut_highmid/cut_highs None sentinel (#553).

Field evidence: master_audio(cut_highmid=0) could not disable a genre
preset's high-mid cut — 0.0 was also the parameter's default, so
build_effective_preset treated an explicit 0 exactly like "not supplied"
and the genre preset always won (a null test proved this: -91 dB residual
= dither only, meaning the EQ never ran). The returned settings block also
echoed the preset's value in both cases, hiding the bug from callers.

None now means "use the genre preset"; an explicit 0/0.0 means "disable
the cut" regardless of genre. Omitting the parameter must behave exactly
as before.
"""

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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers import _shared as shared_mod
from handlers.processing import _helpers as processing_helpers
from handlers.processing import audio as audio_mod

def _shipped_genre_preset(genre: str, key: str) -> float:
    """Read one value straight out of the genre presets this repo ships.

    Not out of `master_tracks.GENRE_PRESETS`: that is the shipped file
    deep-merged with the developer's `{overrides}/mastering-presets.yaml`,
    so reading it would compare the handler's output against the same
    override the handler used — an assertion that holds no matter what
    the code does. Reading the file makes the expected value a fact about
    this repo, and `_run_master_audio` patches the overrides path away so
    the handler resolves from the same file (#553).
    """
    import yaml

    presets_file = PROJECT_ROOT / "tools" / "mastering" / "genre-presets.yaml"
    with open(presets_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return float(data["genres"][genre][key])


POP_CUT_HIGHMID = _shipped_genre_preset("pop", "cut_highmid")
BLACK_METAL_CUT_HIGHS = _shipped_genre_preset("black-metal", "cut_highs")


class _MockCache:
    """Minimal stand-in for the server's state cache."""

    def get_state(self) -> dict:
        return {}


def _write_test_wav(path: Path, sr: int = 44100, duration: float = 2.0) -> None:
    """Write a test WAV with high-mid/high-frequency energy so an EQ cut is
    measurable (a pure low tone wouldn't show whether the cut applied)."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    data = 0.3 * np.sin(2 * np.pi * 440 * t) + 0.1 * np.sin(2 * np.pi * 6000 * t)
    stereo = np.column_stack([data, data])
    sf.write(str(path), stereo, sr, subtype="PCM_16")


@pytest.fixture
def one_track_audio_dir(tmp_path: Path) -> Path:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    _write_test_wav(audio_dir / "01-test.wav")
    return audio_dir


def _run_master_audio(**kwargs: object) -> dict:
    audio_dir = kwargs.pop("_audio_dir")  # type: ignore[assignment]

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, audio_dir

    # `build_effective_preset` calls `load_genre_presets()` fresh on every
    # run, which merges `{overrides}/mastering-presets.yaml` on top of the
    # shipped file. Point it at nothing so the run resolves from the
    # shipped presets the expected values above were read from (#553).
    import tools.mastering.master_tracks as master_tracks_mod

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
         patch.object(shared_mod, "cache", _MockCache()), \
         patch.object(master_tracks_mod, "_get_overrides_path", lambda: None):
        result_json = asyncio.run(audio_mod.master_audio(**kwargs))
    return json.loads(result_json)


class TestCutHighmidSentinel:
    def test_omitted_cut_highmid_applies_and_echoes_genre_preset(
        self, one_track_audio_dir: Path
    ) -> None:
        result = _run_master_audio(
            album_slug="test-album", genre="pop", _audio_dir=one_track_audio_dir
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highmid"] == POP_CUT_HIGHMID

    def test_explicit_zero_cut_highmid_disables_and_echoes_zero(
        self, one_track_audio_dir: Path
    ) -> None:
        result = _run_master_audio(
            album_slug="test-album",
            genre="pop",
            cut_highmid=0.0,
            _audio_dir=one_track_audio_dir,
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highmid"] == 0.0
        assert result["settings"]["cut_highmid"] != POP_CUT_HIGHMID

    def test_explicit_nonzero_cut_highmid_overrides_preset_and_echoes_value(
        self, one_track_audio_dir: Path
    ) -> None:
        result = _run_master_audio(
            album_slug="test-album",
            genre="pop",
            cut_highmid=-4.5,
            _audio_dir=one_track_audio_dir,
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highmid"] == -4.5


class TestCutHighsSentinel:
    def test_omitted_cut_highs_applies_and_echoes_genre_preset(
        self, one_track_audio_dir: Path
    ) -> None:
        result = _run_master_audio(
            album_slug="test-album",
            genre="black-metal",
            _audio_dir=one_track_audio_dir,
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highs"] == BLACK_METAL_CUT_HIGHS

    def test_explicit_zero_cut_highs_disables_and_echoes_zero(
        self, one_track_audio_dir: Path
    ) -> None:
        result = _run_master_audio(
            album_slug="test-album",
            genre="black-metal",
            cut_highs=0.0,
            _audio_dir=one_track_audio_dir,
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highs"] == 0.0
        assert result["settings"]["cut_highs"] != BLACK_METAL_CUT_HIGHS

    def test_explicit_nonzero_cut_highs_overrides_preset_and_echoes_value(
        self, one_track_audio_dir: Path
    ) -> None:
        result = _run_master_audio(
            album_slug="test-album",
            genre="black-metal",
            cut_highs=-2.25,
            _audio_dir=one_track_audio_dir,
        )
        assert "error" not in result, result
        assert result["settings"]["cut_highs"] == -2.25


class TestDisableActuallyChangesEffectivePreset:
    """Prove the disable isn't just a cosmetic settings-echo fix — the
    resolved preset fed to master_track (and therefore its EQ decision at
    ``if p['cut_highmid'] != 0``) must itself carry 0.0, not the genre's
    cut. Patches master_track to capture the preset it's actually called
    with, since master_track's own "apply EQ iff nonzero" branch already
    has thorough coverage in test_master_tracks.py — this test only needs
    to prove master_audio hands it the right number.
    """

    def test_explicit_zero_cut_highmid_reaches_master_track_as_zero(
        self, one_track_audio_dir: Path
    ) -> None:
        from tools.mastering import master_tracks as master_tracks_mod

        captured: dict = {}
        real_master_track = master_tracks_mod.master_track

        def _spy(*args: object, **kwargs: object) -> dict:
            captured["preset"] = kwargs.get("preset")
            return real_master_track(*args, **kwargs)

        def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
            return None, one_track_audio_dir

        with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve), \
             patch.object(shared_mod, "cache", _MockCache()), \
             patch.object(master_tracks_mod, "master_track", _spy):
            result_json = asyncio.run(audio_mod.master_audio(
                album_slug="test-album", genre="pop", cut_highmid=0.0,
            ))

        result = json.loads(result_json)
        assert "error" not in result, result
        assert captured["preset"]["cut_highmid"] == 0.0
