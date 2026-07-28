"""State ``genre`` is a path segment, so it must stay the parent directory name.

``reference/state-schema.md`` defines the album field as the parent directory
name, and ~7 handler sites interpolate it into
``{root}/artists/{artist}/albums/{genre}/{slug}`` — ``_resolve_audio_dir``,
``resolve_path``, ``update_album_status``'s release gate, ``rename_album``,
``migrate_audio_layout``, ``validate_album_structure``, ``db_sync_album``.

Meanwhile ``templates/album.md`` documents frontmatter ``genres:`` as musical
descriptors (``genres: []  # e.g., ["hip-hop", "documentary"]``), not filing
locations. The two are therefore allowed to disagree, and if the declared value
ever won, an album filed under ``electronic/`` that declared
``genres: ["synthwave"]`` would silently lose its audio, rename and release
gate — and a multi-word or cased entry could never match a directory at all.

``parse_album_readme`` does resolve ``genres:`` into its own ``genre`` key, so
nothing stops a future change from feeding it through. Both indexing paths must
keep ignoring it for this field; these two tests are what says so.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tools.state.indexer as indexer
from tools.state.indexer import build_state, incremental_update, scan_albums

# The album template's own shape: filed under one directory, declaring another
# genre in frontmatter.
_README = (
    '---\n'
    'title: "Neon Nights"\n'
    'genres: ["synthwave", "documentary"]\n'
    '---\n\n'
    '# Neon Nights\n'
)


def _make_album(content_root: Path) -> Path:
    album_dir = (
        content_root / "artists" / "bitwize" / "albums" / "electronic" / "neon-nights"
    )
    (album_dir / "tracks").mkdir(parents=True)
    (album_dir / "README.md").write_text(_README, encoding="utf-8")
    return album_dir


def test_scan_albums_keeps_the_directory_genre(tmp_path):
    """Full scan: the declared genre loses to the directory."""
    _make_album(tmp_path)

    album = scan_albums(tmp_path, "bitwize")["neon-nights"]

    assert album["genre"] == "electronic"


def test_incremental_update_keeps_the_directory_genre(tmp_path, monkeypatch):
    """Incremental README re-parse: same answer, via the other code path."""
    content_root = tmp_path / "content"
    album_dir = _make_album(content_root)
    config = {
        'artist': {'name': 'bitwize'},
        'paths': {'content_root': str(content_root)},
    }
    monkeypatch.setattr(indexer, 'get_config_mtime', lambda: 100.0)

    existing = build_state(config)
    existing['config']['config_mtime'] = 100.0
    assert existing['albums']['neon-nights']['genre'] == "electronic"

    # Touch the README so the incremental pass takes its re-parse branch —
    # the one that rebuilds the album dict, and so the one that could
    # reintroduce the declared genre.
    readme = album_dir / "README.md"
    st = readme.stat()
    os.utime(readme, (st.st_atime, st.st_mtime + 2))

    updated = incremental_update(existing, config)

    assert updated['albums']['neon-nights']['genre'] == "electronic"
