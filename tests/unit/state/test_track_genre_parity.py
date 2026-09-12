"""Parity test: the full scan and the incremental path must agree on track genre.

#523 established the pattern: a field set by one indexing path and dropped by
the other flip-flops depending on which ran last. The per-track ``genre`` key
must survive ``_update_tracks_incremental``, which re-parses any track whose
mtime changed — i.e. every ordinary edit to a track file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state.indexer import _update_tracks_incremental, scan_albums


def test_track_genre_survives_incremental_update(tmp_path):
    album_dir = tmp_path / "artists" / "a" / "albums" / "pop" / "al"
    (album_dir / "tracks").mkdir(parents=True)
    (album_dir / "README.md").write_text(
        '---\ntitle: "Al"\n---\n\n# Al\n', encoding="utf-8",
    )
    track = album_dir / "tracks" / "01-t.md"
    track.write_text(
        '---\ntitle: "T"\ngenre: "hip-hop"\n---\n\n# T\n', encoding="utf-8",
    )

    album = scan_albums(tmp_path, "a")["al"]
    assert album["tracks"]["01-t"]["genre"] == "hip-hop"

    # Any ordinary edit: content changes, mtime moves forward
    track.write_text(
        track.read_text(encoding="utf-8") + "\n<!-- edited -->\n", encoding="utf-8",
    )
    st = track.stat()
    os.utime(track, (st.st_atime, st.st_mtime + 2))

    _update_tracks_incremental(album, album_dir)
    assert album["tracks"]["01-t"].get("genre") == "hip-hop"
