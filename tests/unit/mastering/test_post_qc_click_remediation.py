"""Post-QC click failures must name the way out (#553).

Since #553 vocals, backing_vocals and the full-mix fallback default to
`click_removal: false` — the peak/RMS detector cannot tell a synthetic
consonant from a click, and repairing consonants damages them. The
trade-off is that a *genuine* click survives polish, and post-QC's click
check is a hard fail with no recovery path: the halt JSON said "3
transient spike(s) detected" and stopped. The failure now carries the
remediation, so the operator does not have to reverse-engineer which
knob turns declicking back on.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _album_stages as album_stages_mod  # noqa: E402


def _run_post_qc(tmp_path: Path, qc_result: dict) -> dict:
    wav = tmp_path / "01-track.wav"
    wav.touch()

    def _fake_qc(path, _preset=None, _genre=None):
        return {**qc_result, "filename": Path(path).name}

    with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
        async def _run():
            ctx = album_stages_mod.MasterAlbumCtx(
                album_slug="click-test", genre="", target_lufs=-14.0,
                ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
                source_subfolder="", freeze_signature=False, new_anchor=False,
                loop=asyncio.get_running_loop(),
            )
            ctx.mastered_files = [wav]
            return await album_stages_mod._stage_post_qc(ctx)

        result = asyncio.run(_run())
    assert result is not None, "expected a halt JSON"
    return json.loads(result)


def test_click_failure_names_the_remediation(tmp_path: Path) -> None:
    payload = _run_post_qc(tmp_path, {
        "verdict": "FAIL",
        "checks": {"clicks": {
            "status": "FAIL",
            "value": "12 found",
            "detail": "12 transient spike(s) detected",
        }},
    })

    assert payload["failed_stage"] == "post_qc"
    detail = payload["failure_detail"]["details"][0]
    assert detail["check"] == "clicks"
    remediation = detail["remediation"]
    assert "click_removal" in remediation
    assert "mix-presets.yaml" in remediation
    assert "polish" in remediation
    assert "master" in remediation


def test_non_click_failure_has_no_click_remediation(tmp_path: Path) -> None:
    payload = _run_post_qc(tmp_path, {
        "verdict": "FAIL",
        "checks": {"truepeak": {
            "status": "FAIL",
            "value": "-0.1 dBTP",
            "detail": "true peak above ceiling",
        }},
    })

    detail = payload["failure_detail"]["details"][0]
    assert detail["check"] == "truepeak"
    assert "remediation" not in detail
