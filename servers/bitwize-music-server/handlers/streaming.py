"""Streaming URL management tools."""

import asyncio
import logging
from pathlib import Path

from handlers._shared import _safe_json, _find_album_or_error, _STREAMING_PLATFORMS
from handlers import _shared

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Streaming platform constants
# ---------------------------------------------------------------------------

# All 5 canonical platform keys (in display order)
_STREAMING_PLATFORM_KEYS = [
    "soundcloud", "spotify", "apple_music", "youtube_music", "amazon_music",
]

# Map from canonical platform key to DB column name
_PLATFORM_DB_COLUMNS = {
    "soundcloud": "soundcloud_url",
    "spotify": "spotify_url",
    "apple_music": "apple_music_url",
    "youtube_music": "youtube_url",
    "amazon_music": "amazon_music_url",
}


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


async def get_streaming_urls(album_slug: str) -> str:
    """Get streaming platform URLs for an album.

    Returns all 5 platform slots with their current value (empty string
    if not set), plus a count of filled/missing platforms.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with URLs per platform, filled_count, and missing list
    """
    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    # Get streaming URLs from state cache
    streaming = album.get("streaming_urls", {})

    # Build full response with all 5 slots
    urls = {}
    missing = []
    for key in _STREAMING_PLATFORM_KEYS:
        val = streaming.get(key, "")
        urls[key] = val
        if not val:
            missing.append(key)

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "urls": urls,
        "filled_count": len(_STREAMING_PLATFORM_KEYS) - len(missing),
        "total_platforms": len(_STREAMING_PLATFORM_KEYS),
        "missing": missing,
    })


async def update_streaming_url(album_slug: str, platform: str, url: str) -> str:
    """Set a streaming platform URL for an album.

    Updates the YAML frontmatter in the album's README.md and refreshes
    the state cache. If a database is configured, also syncs the URL
    there (best-effort).

    Args:
        album_slug: Album slug (e.g., "my-album")
        platform: Platform name. Accepts:
            "soundcloud", "spotify", "apple_music" (or "apple-music"),
            "youtube_music" (or "youtube-music"), "amazon_music" (or "amazon-music")
        url: The streaming URL (must start with http:// or https://).
            Pass empty string to clear.

    Returns:
        JSON with update result or error
    """
    import yaml

    # Validate platform
    canonical_platform = _STREAMING_PLATFORMS.get(platform.lower().replace(" ", "_"))
    if not canonical_platform:
        return _safe_json({
            "error": f"Unknown platform '{platform}'. Valid: "
                     f"{', '.join(_STREAMING_PLATFORM_KEYS)}",
        })

    # Validate URL (allow empty to clear)
    if url and not url.startswith(("http://", "https://")):
        return _safe_json({
            "error": f"Invalid URL: must start with http:// or https:// (got '{url[:50]}')",
        })

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    album_path = album.get("path", "")
    if not album_path:
        return _safe_json({"error": f"No path stored for album '{normalized}'"})

    readme_path = Path(album_path) / "README.md"
    if not readme_path.exists():
        return _safe_json({"error": f"README.md not found at {readme_path}"})

    # Read file
    try:
        text = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _safe_json({"error": f"Cannot read README.md: {e}"})

    # Parse and update frontmatter
    if not text.startswith("---"):
        return _safe_json({"error": "README.md has no YAML frontmatter"})

    lines = text.split("\n")
    end_index = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index == -1:
        return _safe_json({"error": "Cannot find closing --- in frontmatter"})

    frontmatter_text = "\n".join(lines[1:end_index])
    try:
        fm = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        return _safe_json({"error": f"Cannot parse frontmatter YAML: {e}"})

    # Update streaming URL using targeted regex replacement to preserve
    # YAML comments and formatting (yaml.dump would strip comments).
    fm_lines = lines[1:end_index]
    updated = False
    for idx, fm_line in enumerate(fm_lines):
        # Match lines like "  soundcloud: ..." or "  apple_music: ..."
        stripped = fm_line.lstrip()
        if stripped.startswith(f"{canonical_platform}:"):
            # Replace the value, preserving indent
            indent = fm_line[:len(fm_line) - len(stripped)]
            if url:
                fm_lines[idx] = f'{indent}{canonical_platform}: "{url}"'
            else:
                fm_lines[idx] = f"{indent}{canonical_platform}: \"\""
            updated = True
            break

    if not updated:
        # Platform key not found in frontmatter — need to add/create streaming block
        if "streaming" not in fm or not isinstance(fm.get("streaming"), dict):
            fm["streaming"] = {}
        fm["streaming"][canonical_platform] = url
        new_fm_text = yaml.dump(
            fm, default_flow_style=False, allow_unicode=True, sort_keys=False,
        ).rstrip("\n")
        fm_lines = new_fm_text.split("\n")

    # Reconstruct file: --- + frontmatter lines + --- + rest of file
    rest_of_file = "\n".join(lines[end_index + 1:])
    new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + rest_of_file

    # Write back
    try:
        readme_path.write_text(new_text, encoding="utf-8")
    except OSError as e:
        return _safe_json({"error": f"Cannot write README.md: {e}"})

    # Re-parse and update state cache
    from tools.state.parsers import parse_album_readme
    from tools.state.indexer import write_state

    album_data = parse_album_readme(readme_path)
    state = _shared.cache.get_state()
    if state and "albums" in state and normalized in state["albums"]:
        state["albums"][normalized]["streaming_urls"] = album_data.get(
            "streaming_urls", {}
        )
        write_state(state)

    # Best-effort DB sync
    db_synced = False
    try:
        from handlers.database import _check_db_deps, _get_db_connection

        dep_err = _check_db_deps()
        if not dep_err:
            conn, conn_err = _get_db_connection()
            if conn and not conn_err:
                db_col = _PLATFORM_DB_COLUMNS.get(canonical_platform)
                if db_col:
                    cur = conn.cursor()
                    cur.execute(
                        f"UPDATE albums SET {db_col} = %s, updated_at = now() "  # nosec B608 - db_col is from allowlist, not user input
                        f"WHERE slug = %s",
                        (url, normalized),
                    )
                    conn.commit()
                    db_synced = cur.rowcount > 0
                conn.close()
    except Exception as e:
        logger.warning("DB sync failed for streaming URL: %s", e)

    return _safe_json({
        "success": True,
        "album_slug": normalized,
        "platform": canonical_platform,
        "url": url,
        "db_synced": db_synced,
    })


async def verify_streaming_urls(album_slug: str) -> str:
    """Check if streaming URLs are live and reachable.

    For each non-empty streaming URL, performs an HTTP HEAD request to
    verify the link is reachable. Reports status per platform.

    Args:
        album_slug: Album slug (e.g., "my-album")

    Returns:
        JSON with per-platform reachability results
    """
    import urllib.request
    import urllib.error
    import urllib.parse

    normalized, album, error = _find_album_or_error(album_slug)
    if error:
        return error

    streaming = album.get("streaming_urls", {})

    def _check_url(url: str) -> dict:
        """Check a single URL (blocking). Run in executor to avoid blocking the event loop."""
        result_entry = {"url": url}
        # Validate URL scheme to prevent SSRF (file://, gopher://, etc.)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            result_entry["reachable"] = False
            result_entry["error"] = f"Unsupported URL scheme: {parsed.scheme!r}"
            return result_entry
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(
                    url, method=method,
                    headers={
                        "User-Agent": "bitwize-music-mcp/1.0 (link checker)",
                    },
                )
                with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 - URL scheme validated above
                    status_code = resp.getcode()
                    final_url = resp.geturl()
                    result_entry["reachable"] = True
                    result_entry["status_code"] = status_code
                    if final_url != url:
                        result_entry["redirect_url"] = final_url
                    break  # Success, no need to try GET
            except urllib.error.HTTPError as e:
                if method == "HEAD" and e.code in (405, 403):
                    continue  # HEAD rejected, try GET
                result_entry["reachable"] = False
                result_entry["status_code"] = e.code
                result_entry["error"] = str(e.reason)
                break
            except (urllib.error.URLError, OSError, ValueError) as e:
                if method == "HEAD":
                    continue  # Network issue on HEAD, try GET
                result_entry["reachable"] = False
                result_entry["error"] = str(e)
                break

        if "reachable" not in result_entry:
            result_entry["reachable"] = False
            result_entry["error"] = "Both HEAD and GET requests failed"

        return result_entry

    loop = asyncio.get_running_loop()

    results = {}
    reachable_count = 0
    unreachable_count = 0
    not_set_count = 0

    # First pass: separate not_set platforms from those needing HTTP checks
    keys_to_check = []
    for key in _STREAMING_PLATFORM_KEYS:
        url = streaming.get(key, "")
        if not url:
            results[key] = {"url": "", "reachable": None, "status": "not_set"}
            not_set_count += 1
        else:
            keys_to_check.append((key, url))

    # Run all URL checks concurrently in thread pool
    if keys_to_check:
        tasks = [
            loop.run_in_executor(None, _check_url, url)
            for _key, url in keys_to_check
        ]
        check_results = await asyncio.gather(*tasks)

        # Merge results back
        for (key, _url), result_entry in zip(keys_to_check, check_results):
            results[key] = result_entry
            if result_entry.get("reachable"):
                reachable_count += 1
            else:
                unreachable_count += 1

    all_reachable = reachable_count > 0 and unreachable_count == 0 and not_set_count == 0

    return _safe_json({
        "found": True,
        "album_slug": normalized,
        "results": results,
        "all_reachable": all_reachable,
        "reachable_count": reachable_count,
        "unreachable_count": unreachable_count,
        "not_set_count": not_set_count,
    })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp):
    """Register streaming URL tools with the MCP server."""
    mcp.tool()(get_streaming_urls)
    mcp.tool()(update_streaming_url)
    mcp.tool()(verify_streaming_urls)
