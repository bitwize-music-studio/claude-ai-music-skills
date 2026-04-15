"""Tests for tools/mastering/metadata.py (#290 metadata embedding)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mutagen = pytest.importorskip("mutagen")


def _write_wav(path: Path, duration: float = 1.0, rate: int = 44100) -> Path:
    n = int(duration * rate)
    data = (0.1 * np.sin(2 * np.pi * 440 * np.arange(n) / rate)).astype(np.float32)
    sf.write(str(path), np.column_stack([data, data]), rate, subtype="PCM_24")
    return path


def test_embed_wav_metadata_basic(tmp_path: Path) -> None:
    """Embedding artist + album + title writes readable ID3v2.4 tags."""
    from tools.mastering.metadata import embed_wav_metadata
    from mutagen.wave import WAVE

    wav = _write_wav(tmp_path / "track.wav")
    embed_wav_metadata(
        wav,
        title="My Track",
        artist="bitwize",
        album="My Album",
    )
    tags = WAVE(str(wav)).tags
    assert tags is not None
    assert str(tags.get("TIT2")) == "My Track"
    assert str(tags.get("TPE1")) == "bitwize"
    assert str(tags.get("TALB")) == "My Album"


def test_embed_wav_metadata_copyright(tmp_path: Path) -> None:
    """Copyright tag (TCOP) and label (TPUB) are embedded."""
    from tools.mastering.metadata import embed_wav_metadata
    from mutagen.wave import WAVE

    wav = _write_wav(tmp_path / "track.wav")
    embed_wav_metadata(wav, copyright_text="2026 bitwize", label="bitwize records")
    tags = WAVE(str(wav)).tags
    assert tags is not None
    assert "2026 bitwize" in str(tags.get("TCOP"))
    assert "bitwize records" in str(tags.get("TPUB"))


def test_embed_wav_metadata_isrc(tmp_path: Path) -> None:
    """ISRC written as TSRC tag."""
    from tools.mastering.metadata import embed_wav_metadata
    from mutagen.wave import WAVE

    wav = _write_wav(tmp_path / "track.wav")
    embed_wav_metadata(wav, isrc="USXYZ2600001")
    tags = WAVE(str(wav)).tags
    assert tags is not None
    assert "USXYZ2600001" in str(tags.get("TSRC"))


def test_embed_wav_metadata_upc(tmp_path: Path) -> None:
    """UPC written as TXXX:UPC tag."""
    from tools.mastering.metadata import embed_wav_metadata
    from mutagen.wave import WAVE

    wav = _write_wav(tmp_path / "track.wav")
    embed_wav_metadata(wav, upc="012345678901")
    tags = WAVE(str(wav)).tags
    assert tags is not None
    txxx = tags.getall("TXXX")
    upc_tag = next((t for t in txxx if t.desc == "UPC"), None)
    assert upc_tag is not None
    assert "012345678901" in str(upc_tag)


def test_embed_wav_metadata_empty_fields_no_error(tmp_path: Path) -> None:
    """Calling with all-empty fields doesn't raise and file is still valid WAV."""
    from tools.mastering.metadata import embed_wav_metadata
    wav = _write_wav(tmp_path / "track.wav")
    embed_wav_metadata(wav)  # no fields set
    # File should still be readable as WAV
    data, rate = sf.read(str(wav))
    assert data.size > 0


def test_embed_wav_metadata_missing_file_raises(tmp_path: Path) -> None:
    """MetadataEmbedError raised for non-existent file."""
    from tools.mastering.metadata import MetadataEmbedError, embed_wav_metadata
    with pytest.raises(MetadataEmbedError, match="not found"):
        embed_wav_metadata(tmp_path / "missing.wav", title="x")
