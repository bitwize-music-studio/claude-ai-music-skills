"""Sheet music transcription and publishing tools."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._shared import (
    _find_album_or_error,
    _find_wav_source_dir,
    _is_path_confined,
    _normalize_slug,
    # _resolve_audio_dir accessed via _helpers for patch compatibility
    _safe_json,
    _update_frontmatter_block,
)
from handlers.processing import _helpers

logger = logging.getLogger("bitwize-music-state")


async def transcribe_audio(
    album_slug: str,
    track_filename: str = "",
    formats: str = "pdf,xml,midi",
    dry_run: bool = False,
) -> str:
    """Convert WAV files to sheet music using AnthemScore.

    Creates symlinks with clean track titles (from state cache) so AnthemScore
    embeds proper titles in its output. Falls back to slug_to_title() when
    the state cache has no track data.

    Output goes to sheet-music/source/ with clean title filenames and a
    .manifest.json recording track ordering and slug mapping.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_filename: Optional single WAV filename (empty = all WAVs)
        formats: Comma-separated output formats: "pdf", "xml", "midi" (default: "pdf,xml")
        dry_run: If true, show what would be done without doing it

    Returns:
        JSON with per-track results and summary
    """
    import tempfile

    anthemscore_err = _helpers._check_anthemscore()
    if anthemscore_err:
        return _safe_json({"error": anthemscore_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    transcribe_mod = _helpers._import_sheet_music_module("transcribe")
    find_anthemscore = transcribe_mod.find_anthemscore
    transcribe_track = transcribe_mod.transcribe_track

    anthemscore_path = find_anthemscore()
    if not anthemscore_path:
        return _safe_json({
            "error": "AnthemScore not found on this system.",
            "suggestion": "Install from https://www.lunaverus.com/",
        })

    output_dir = audio_dir / "sheet-music" / "source"
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Parse formats
    fmt_list = [f.strip().lower() for f in formats.split(",")]

    # Build a namespace-like object for transcribe_track's args
    class Args:
        pass
    args = Args()
    args.pdf = "pdf" in fmt_list  # type: ignore[attr-defined]
    args.xml = "xml" in fmt_list  # type: ignore[attr-defined]
    args.midi = "midi" in fmt_list  # type: ignore[attr-defined]
    args.treble = False  # type: ignore[attr-defined]
    args.bass = False  # type: ignore[attr-defined]
    args.dry_run = dry_run  # type: ignore[attr-defined]

    if track_filename:
        if not _is_path_confined(audio_dir, track_filename):
            return _safe_json({
                "error": "Invalid track_filename: path must not escape the album directory",
                "track_filename": track_filename,
            })
        wav_files = [audio_dir / track_filename]
        if not wav_files[0].exists():
            wav_files = [_find_wav_source_dir(audio_dir) / track_filename]
        if not wav_files[0].exists():
            return _safe_json({
                "error": f"Track file not found: {track_filename}",
                "available_files": [f.name for f in _find_wav_source_dir(audio_dir).glob("*.wav")],
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)
        wav_files = sorted(source_dir.glob("*.wav"))
        wav_files = [f for f in wav_files if "venv" not in str(f)]

    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {audio_dir}"})

    # Build title map from state cache (falls back to slug_to_title)
    title_map = _helpers._build_title_map(album_slug, wav_files)

    # Dry run: just report the title mapping
    if dry_run:
        manifest_tracks = []
        for wav_file in wav_files:
            stem = wav_file.stem
            clean_title = title_map.get(stem, stem)
            track_num = _helpers._extract_track_number_from_stem(stem)
            manifest_tracks.append({
                "number": track_num,
                "source_slug": stem,
                "title": clean_title,
            })
        return _safe_json({
            "dry_run": True,
            "title_map": title_map,
            "manifest": {"tracks": manifest_tracks},
            "output_dir": str(output_dir),
            "formats": fmt_list,
        })

    # Create temp dir with clean-titled symlinks
    tmp_dir = None
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"{album_slug}-transcribe-"))

        # Disambiguate duplicate titles
        used_titles: dict[str, int] = {}
        symlink_map = {}  # clean_title -> (symlink_path, original_wav)
        for wav_file in wav_files:
            stem = wav_file.stem
            clean_title = title_map.get(stem, stem)
            # Handle duplicate titles
            if clean_title in used_titles:
                used_titles[clean_title] += 1
                clean_title = f"{clean_title} ({used_titles[clean_title]})"
            else:
                used_titles[clean_title] = 1

            symlink_path = tmp_dir / f"{clean_title}.wav"
            try:
                symlink_path.symlink_to(wav_file.resolve())
            except OSError:
                # Fallback: copy if symlinks fail (e.g., Windows)
                shutil.copy2(wav_file, symlink_path)
            symlink_map[clean_title] = (symlink_path, wav_file)

        # Transcribe from symlinked files
        loop = asyncio.get_running_loop()
        results = []
        manifest_tracks = []

        for clean_title, (symlink_path, original_wav) in symlink_map.items():
            stem = original_wav.stem
            track_num = _helpers._extract_track_number_from_stem(stem)

            success = await loop.run_in_executor(
                None, transcribe_track, anthemscore_path, symlink_path, output_dir, args
            )

            outputs = []
            if success:
                for fmt in fmt_list:
                    ext = {"pdf": ".pdf", "xml": ".xml", "midi": ".mid"}.get(fmt, "")
                    out_file = output_dir / f"{clean_title}{ext}"
                    if out_file.exists():
                        outputs.append(str(out_file))

            results.append({
                "filename": original_wav.name,
                "clean_title": clean_title,
                "success": success,
                "outputs": outputs,
            })
            manifest_tracks.append({
                "number": track_num,
                "source_slug": stem,
                "title": clean_title,
            })

        # Sort manifest by track number
        manifest_tracks.sort(key=lambda t: (t["number"] is None, t["number"] or 0))

        # Write .manifest.json to source/
        manifest = {"tracks": manifest_tracks}
        manifest_path = output_dir / ".manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        success_count = sum(1 for r in results if r["success"])
        return _safe_json({
            "tracks": results,
            "manifest": manifest,
            "summary": {
                "success": success_count,
                "failed": len(results) - success_count,
                "output_dir": str(output_dir),
                "formats": fmt_list,
            },
        })
    finally:
        # Clean up temp dir
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def prepare_singles(
    album_slug: str,
    dry_run: bool = False,
    xml_only: bool = False,
) -> str:
    """Prepare consumer-ready sheet music singles with clean titles.

    Reads source files from the album's sheet-music/source/ directory.
    If source/ has a .manifest.json (from transcribe_audio), files are
    already clean-titled. Otherwise falls back to numbered file discovery
    with slug_to_title derivation.

    Output files are numbered: "01 - First Pour.pdf", etc.
    Creates .manifest.json in singles/ with filename field for songbook.

    Args:
        album_slug: Album slug (e.g., "my-album")
        dry_run: If true, show changes without modifying files
        xml_only: If true, only process XML files (skip PDF/MIDI)

    Returns:
        JSON with per-track results and manifest
    """
    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Try new structure first, fall back to flat layout
    source_dir = audio_dir / "sheet-music" / "source"
    if not source_dir.is_dir():
        sheet_dir = audio_dir / "sheet-music"
        if sheet_dir.is_dir():
            source_dir = sheet_dir  # backward compat: flat layout
        else:
            return _safe_json({
                "error": f"Sheet music directory not found: {source_dir}",
                "suggestion": "Run transcribe_audio first to generate sheet music.",
            })

    singles_dir = audio_dir / "sheet-music" / "singles"

    prepare_mod = _helpers._import_sheet_music_module("prepare_singles")
    _prepare_singles = prepare_mod.prepare_singles

    musescore = None
    if not xml_only:
        musescore = prepare_mod.find_musescore()

    # Get artist, cover art, and footer URL for title pages
    songbook_mod = _helpers._import_sheet_music_module("create_songbook")
    auto_detect_cover_art = songbook_mod.auto_detect_cover_art
    get_footer_url_from_config = songbook_mod.get_footer_url_from_config

    state = _shared.cache.get_state()
    srv_config = state.get("config", {})
    artist = srv_config.get("artist_name", "Unknown Artist")
    cover_image = auto_detect_cover_art(str(source_dir))
    footer_url = get_footer_url_from_config()
    page_size_name = "letter"
    try:
        from tools.shared.config import load_config
        cfg = load_config()
        if cfg:
            page_size_name = cfg.get('sheet_music', {}).get('page_size', 'letter')
    except (ImportError, OSError, KeyError) as exc:
        logger.warning("Could not load sheet music config, using defaults: %s", exc)

    # Build title_map from state cache for legacy (no source manifest) fallback
    title_map = None
    albums = state.get("albums", {})
    album = albums.get(_normalize_slug(album_slug), {})
    cache_tracks = album.get("tracks", {})
    if cache_tracks:
        from tools.shared.text_utils import sanitize_filename
        from tools.shared.text_utils import slug_to_title as _s2t
        title_map = {}
        for slug, track in cache_tracks.items():
            title_map[slug] = sanitize_filename(track.get("title", _s2t(slug)))

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _prepare_singles(
            source_dir=source_dir,
            singles_dir=singles_dir,
            musescore=musescore,
            dry_run=dry_run,
            xml_only=xml_only,
            artist=artist,
            cover_image=cover_image,
            footer_url=footer_url,
            page_size_name=page_size_name,
            title_map=title_map,
        ),
    )

    if "error" in result:
        return _safe_json({"error": result["error"]})

    tracks = result.get("tracks", [])
    return _safe_json({
        "tracks": tracks,
        "singles_dir": str(singles_dir),
        "track_count": len(tracks),
        "manifest": result.get("manifest", {}),
    })


async def create_songbook(
    album_slug: str,
    title: str,
    page_size: str = "letter",
) -> str:
    """Combine sheet music PDFs into a distribution-ready songbook.

    Creates a complete songbook with title page, copyright page, table
    of contents, and all track sheet music. Reads from singles/ directory
    (falls back to flat sheet-music/ layout for backward compatibility).

    Args:
        album_slug: Album slug (e.g., "my-album")
        title: Songbook title (e.g., "My Album Songbook")
        page_size: Page size - "letter", "9x12", or "6x9" (default: "letter")

    Returns:
        JSON with output path and metadata
    """
    dep_err = _helpers._check_songbook_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Try new structure first (singles/), fall back to flat layout
    singles_dir = audio_dir / "sheet-music" / "singles"
    if singles_dir.is_dir():
        source_dir = singles_dir
    else:
        sheet_dir = audio_dir / "sheet-music"
        if sheet_dir.is_dir():
            source_dir = sheet_dir  # backward compat
        else:
            return _safe_json({
                "error": f"Sheet music directory not found: {singles_dir}",
                "suggestion": "Run transcribe_audio and prepare_singles first.",
            })

    songbook_mod = _helpers._import_sheet_music_module("create_songbook")
    _create_songbook = songbook_mod.create_songbook
    auto_detect_cover_art = songbook_mod.auto_detect_cover_art
    get_website_from_config = songbook_mod.get_website_from_config
    get_footer_url_from_config = songbook_mod.get_footer_url_from_config

    # Get artist from state
    state = _shared.cache.get_state()
    config = state.get("config", {})
    artist = config.get("artist_name", "Unknown Artist")

    # Auto-detect cover art, website, and footer URL
    cover = auto_detect_cover_art(str(source_dir))
    website = get_website_from_config()
    footer_url = get_footer_url_from_config()

    # Build output path in songbook/ subdirectory
    songbook_dir = audio_dir / "sheet-music" / "songbook"
    songbook_dir.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace(" ", "_").replace("/", "-").replace("..", "")
    if not safe_title or not _is_path_confined(songbook_dir, f"{safe_title}.pdf"):
        return _safe_json({
            "error": "Invalid title: produces a path that escapes the songbook directory",
            "title": title,
        })
    output_path = songbook_dir / f"{safe_title}.pdf"

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        lambda: _create_songbook(
            source_dir=str(source_dir),
            output_path=str(output_path),
            title=title,
            artist=artist,
            page_size_name=page_size,
            cover_image=cover,
            website=website,
            footer_url=footer_url,
        ),
    )

    if success:
        return _safe_json({
            "success": True,
            "output_path": str(output_path),
            "title": title,
            "artist": artist,
            "page_size": page_size,
        })
    else:
        return _safe_json({"error": "Songbook creation failed. Check sheet music directory."})


async def publish_sheet_music(
    album_slug: str,
    include_source: bool = False,
    dry_run: bool = False,
) -> str:
    """Upload sheet music files (PDFs, MusicXML, MIDI) to Cloudflare R2.

    Collects files from sheet-music/singles/ and sheet-music/songbook/,
    optionally including sheet-music/source/, and uploads them to R2
    for public download URLs.

    Args:
        album_slug: Album slug (e.g., "my-album")
        include_source: Include source/ transcription files (default: False)
        dry_run: List files and R2 keys without uploading (default: False)

    Returns:
        JSON with uploaded files, R2 keys, and summary
    """
    cloud_err = _helpers._check_cloud_enabled()
    if cloud_err:
        return _safe_json({"error": cloud_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    sheet_music_dir = audio_dir / "sheet-music"
    if not sheet_music_dir.is_dir():
        return _safe_json({
            "error": f"Sheet music directory not found: {sheet_music_dir}",
            "suggestion": (
                "Run transcribe_audio first to generate source files, "
                "then prepare_singles to create distribution-ready PDFs."
            ),
        })

    # Collect files from each subdirectory
    subdirs_to_scan = ["singles", "songbook"]
    if include_source:
        subdirs_to_scan.append("source")

    files_to_upload = []  # list of (local_path, r2_subdir, filename)
    for subdir in subdirs_to_scan:
        subdir_path = sheet_music_dir / subdir
        if not subdir_path.is_dir():
            continue
        for f in sorted(subdir_path.iterdir()):
            if not f.is_file():
                continue
            # Skip internal metadata files
            if f.name == ".manifest.json":
                continue
            files_to_upload.append((f, subdir, f.name))

    if not files_to_upload:
        return _safe_json({
            "error": "No sheet music files found to upload.",
            "checked_dirs": [
                str(sheet_music_dir / s) for s in subdirs_to_scan
            ],
            "suggestion": "Run prepare_singles and/or create_songbook first.",
        })

    # Get artist name from state
    state = _shared.cache.get_state()
    config_data = state.get("config", {})
    artist = config_data.get("artist_name", "Unknown Artist")
    normalized_slug = _normalize_slug(album_slug)

    # Build R2 keys
    upload_plan: list[dict[str, Any]] = []
    for local_path, subdir, filename in files_to_upload:
        r2_key = f"{artist}/{normalized_slug}/sheet-music/{subdir}/{filename}"
        upload_plan.append({
            "local_path": str(local_path),
            "r2_key": r2_key,
            "size_bytes": local_path.stat().st_size,
            "subdir": subdir,
            "filename": filename,
        })

    if dry_run:
        return _safe_json({
            "dry_run": True,
            "album_slug": normalized_slug,
            "artist": artist,
            "files": upload_plan,
            "summary": {
                "total": len(upload_plan),
                "by_subdir": {
                    s: len([f for f in upload_plan if f["subdir"] == s])
                    for s in subdirs_to_scan
                    if any(f["subdir"] == s for f in upload_plan)
                },
            },
        })

    # Import cloud module and upload
    try:
        cloud_mod = _helpers._import_cloud_module("upload_to_cloud")
    except Exception as e:
        return _safe_json({
            "error": f"Failed to import cloud module: {e}",
            "suggestion": "Ensure boto3 is installed: pip install boto3",
        })

    from tools.shared.config import load_config
    config = load_config()
    assert config is not None

    try:
        s3_client = cloud_mod.get_s3_client(config)
    except SystemExit:
        return _safe_json({
            "error": "Cloud credentials not configured.",
            "suggestion": "Configure cloud.r2 or cloud.s3 credentials in ~/.bitwize-music/config.yaml",
        })

    try:
        bucket = cloud_mod.get_bucket_name(config)
    except SystemExit:
        return _safe_json({
            "error": "Bucket name not configured.",
            "suggestion": "Set cloud.r2.bucket or cloud.s3.bucket in ~/.bitwize-music/config.yaml",
        })

    public_read = config.get("cloud", {}).get("public_read", False)

    uploaded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in upload_plan:
        local_path = Path(item["local_path"])
        r2_key = item["r2_key"]
        success = cloud_mod.retry_upload(
            s3_client, bucket, local_path, r2_key,
            public_read=public_read, dry_run=False,
        )
        if success:
            uploaded.append({
                "r2_key": r2_key,
                "filename": item["filename"],
                "subdir": item["subdir"],
            })
        else:
            failed.append({"r2_key": r2_key, "filename": item["filename"]})

    # Build public URLs if available
    cloud_config = config.get("cloud", {})
    provider = cloud_config.get("provider", "r2")
    base_url = None
    if public_read:
        if provider == "r2":
            custom_domain = cloud_config.get("r2", {}).get("public_url")
            if custom_domain:
                base_url = custom_domain.rstrip("/")
        elif provider == "s3":
            region = cloud_config.get("s3", {}).get("region", "us-east-1")
            base_url = f"https://{bucket}.s3.{region}.amazonaws.com"

    urls = {}
    if base_url:
        for item in uploaded:
            urls[item["filename"]] = f"{base_url}/{item['r2_key']}"
    else:
        # Use relative R2 keys when no public_url is configured
        for item in uploaded:
            urls[item["filename"]] = item["r2_key"]

    # --- Persist URLs to track/album frontmatter ---
    frontmatter_updated = False
    tracks_updated = []
    album_updated = False
    fm_reason = None

    if not urls:
        fm_reason = "No files uploaded successfully"
    else:
        # Find album content path
        _, album_data, album_err = _find_album_or_error(normalized_slug)
        if album_err:
            fm_reason = f"Album not found in state: {normalized_slug}"
        else:
            assert album_data is not None
            album_content_path = album_data.get("path", "")
            state_tracks = album_data.get("tracks", {})

            # Group single URLs by track number
            # Singles are named like "01 - The Mountain.pdf"
            track_urls: dict[int, dict[str, str]] = {}  # {1: {"pdf": url, "musicxml": url, "midi": url}, ...}
            songbook_urls: dict[str, str] = {}  # {"songbook": url}
            ext_to_key = {".pdf": "pdf", ".xml": "musicxml", ".mid": "midi", ".midi": "midi"}

            for item in uploaded:
                filename = item["filename"]
                url = urls.get(filename)
                if not url:
                    continue

                if item["subdir"] == "singles":
                    m = re.match(r"^(\d+)\s*-\s*", filename)
                    if m:
                        track_num = int(m.group(1))
                        suffix = Path(filename).suffix.lower()
                        file_key = ext_to_key.get(suffix)
                        if file_key:
                            track_urls.setdefault(track_num, {})[file_key] = url
                elif item["subdir"] == "songbook":
                    suffix = Path(filename).suffix.lower()
                    if suffix == ".pdf":
                        songbook_urls["songbook"] = url

            # Update each track file's frontmatter
            for track_num, sm_values in track_urls.items():
                prefix = f"{track_num:02d}-"
                for slug, tdata in state_tracks.items():
                    if slug.startswith(prefix):
                        track_path = Path(tdata.get("path", ""))
                        if track_path.is_file():
                            ok, err = _update_frontmatter_block(
                                track_path, "sheet_music", sm_values,
                            )
                            if ok:
                                tracks_updated.append(slug)
                        break

            # Update album README.md frontmatter
            if songbook_urls and album_content_path:
                readme_path = Path(album_content_path) / "README.md"
                if readme_path.is_file():
                    ok, err = _update_frontmatter_block(
                        readme_path, "sheet_music", songbook_urls,
                    )
                    if ok:
                        album_updated = True

            frontmatter_updated = bool(tracks_updated) or album_updated

    result = {
        "album_slug": normalized_slug,
        "artist": artist,
        "uploaded": uploaded,
        "failed": failed,
        "summary": {
            "total": len(upload_plan),
            "success": len(uploaded),
            "failed": len(failed),
        },
        "urls": urls,
        "frontmatter_updated": frontmatter_updated,
    }
    if tracks_updated:
        result["tracks_updated"] = tracks_updated
    if album_updated:
        result["album_updated"] = True
    if fm_reason:
        result["frontmatter_reason"] = fm_reason

    return _safe_json(result)


def register(mcp: Any) -> None:
    """Register sheet music tools."""
    mcp.tool()(transcribe_audio)
    mcp.tool()(prepare_singles)
    mcp.tool()(create_songbook)
    mcp.tool()(publish_sheet_music)
