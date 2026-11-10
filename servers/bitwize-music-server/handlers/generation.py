"""Suno generation bridge — track file to API request, take logging, import planning.

Nothing in this module talks to Suno. A skill asks these tools what to send,
calls the Suno MCP server itself, then hands the resulting clip ids back for
logging. That keeps the Suno side swappable and this side testable offline.
See reference/suno/mcp-api-mapping.md for the mapping these tools implement.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any

from handlers import _shared
from handlers._atomic import atomic_write_text
from handlers._shared import (
    _album_dir,
    _extract_code_block,
    _extract_markdown_section,
    _find_album_or_error,
    _find_track_or_error,
    _lyrics_placeholder_in,
    _safe_json,
    _template_style_tokens_in,
)
from handlers.gates import _KNOWN_MODELS, _parse_duration_seconds
from tools.playback.player import find_track_audio
from tools.state.indexer import write_state
from tools.state.parsers import _extract_table_value, parse_frontmatter

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Limits from the Suno MCP `audio-create` schema.
_MAX_TITLE = 256
_MAX_LYRICS = 5000
_MAX_STYLE = 1000
_MAX_NEGATIVE_STYLE = 1000
_MIN_DURATION = 15
_MAX_DURATION = 360

# Request keys Suno only accepts on accounts with the `controls.advanced` feature.
# Request fields that need the plan's advanced-controls grant. Inside `controls` the
# sliders need it; `variety` does not (free for anyone signed in with Suno).
_NEEDS_ADVANCED_CONTROLS = ("negative_style", "vocal_gender")
_GRANT_FREE_CONTROLS = frozenset({"variety"})

# Generation Settings "Variety" -> controls.variety. Off means the Style Box is used
# as written; anything higher lets Suno reinterpret it.
_VARIETY_LEVELS = {
    "off": 0, "exact": 0, "exact style": 0, "0": 0,
    "normal": 1, "1": 1,
    "high": 2, "2": 2,
    "extra": 3, "3": 3,
    "max": 4, "4": 4,
}

# Table cells and code blocks that mean "nothing set".
_UNSET = frozenset({"", "—", "\u2013", "-", "n/a", "none", "(none)", "auto"})

# The Exclude Styles placeholder from templates/track.md — never worth sending
# to Suno. The Style Box and Lyrics Box placeholders are recognised by the
# helpers in _shared, the same ones the pre-generation gates use, so the gates
# and this request cannot disagree about what "not written yet" means.
_TEMPLATE_EXCLUDE = "[exclusions, if any]"

_SLIDER_RE = re.compile(r"(\d{1,3})\s*%?")
# Audio Influence is written as a percentage ("70", "70%") or as a fraction ("0.7").
_INFLUENCE_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(%?)")

# The four kinds of generation request, the Suno tool each is sent to, and what that
# tool cannot carry (read from the live tool definitions).
_KIND_TOOL = {
    "song": "audio-create",
    "cover": "audio-covers-create",
    "speech": "speech-create",
    "midi": "audio-create",
}
_KIND_LACKS: dict[str, frozenset[str]] = {
    "song": frozenset(),
    "cover": frozenset({"instrumental", "vocal_gender"}),
    "speech": frozenset({"model", "max_mode", "controls", "instrumental"}),
    "midi": frozenset({
        "lyrics", "negative_style", "model", "max_mode", "vocal_gender", "duration",
        "controls", "voice",
    }),
}
_WHY_NOT: dict[str, dict[str, str]] = {
    "cover": {"vocal_gender": "audio-covers-create takes no vocal gender"},
    "speech": {
        "model": "speech always uses Suno's default model",
        "max_mode": "speech-create has no Max Mode",
        "controls": "speech-create takes no controls, so Suno words the delivery tags its own way",
    },
    "midi": {
        "lyrics": "a song made from a score takes no lyrics",
        "negative_style": "a song made from a score takes no style to exclude from",
        "model": "a score plays only on v6-wild",
        "max_mode": "Max Mode needs lyrics or a style, and a score takes neither",
        "vocal_gender": "the sketch is instrumental",
        "duration": "the score sets the length",
        "controls": "a song made from a score takes no style for the sliders to steer",
        "voice": "the sketch is instrumental; the Voice sings when the sketch is covered",
    },
}
# A score plays only on v6-wild, in simple mode: a description, no lyrics and no style.
_MIDI_MODEL = "v6-wild"
_MIDI_DESCRIPTION = "An instrumental that plays my melody, in this style: "
_MIDI_UPLOAD_ID_RE = re.compile(r"[\w-]{8,64}")
# A template cell nobody filled in, such as "[Saved Voice name, or —]".
_PLACEHOLDER_CELL_RE = re.compile(r"\[[^\]]*\]")
_BRACKET_TAG_RE = re.compile(r"\[[^\]]*\]")

# Exclude Styles written before 0.102.0 read "no drums, no autotune". The field is
# already the negation, so the items go to Suno bare. "no wave" is a genre.
_NO_PREFIX_RE = re.compile(r"^no\s+", re.IGNORECASE)
_NO_PREFIX_KEEP = frozenset({"no wave"})

# Generation Log (templates/track.md § Generation Log)
_CLIP_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_GENERATION_LOG_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+Generation Log[ \t]*$")
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+\S")
_ROW_NUMBER_RE = re.compile(r"\|\s*(\d+)\s*\|")
_PLACEHOLDER_ROW_RE = re.compile(r"\|(?:\s*[—\u2013-]\s*\|){2,}")
_LOG_TABLE_HEADER = "| # | Date | Model | Result | Notes | Rating |"
_LOG_TABLE_SEPARATOR = "|---|------|-------|--------|-------|--------|"
_SONG_URL_RE = re.compile(
    r"https://suno\.com/song/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})"
)
_MARKDOWN_URL_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r"https?://[^\s|)]+")
_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")
_APPROVED_MARKS = ("✓", "✔", "✅")
# log_generation writes a take's Notes as "m:ss, ..., N credits".
_NOTE_DURATION_RE = re.compile(r"\s*(\d{1,3}):([0-5]\d)(?!\d)")
_NOTE_CREDITS_RE = re.compile(r"(\d+)\s+credits?\b", re.IGNORECASE)
# Notes that mark a row as a version of another take ("instrumental version of take 2"):
# audio kept beside the track, never the track's keeper. get_edit_request words the note.
VERSIONS = ("instrumental",)
_VERSION_NOTE_RE = re.compile(
    r"\b(" + "|".join(VERSIONS) + r") version of take (\d+)\b", re.IGNORECASE,
)

# Suno stem part (audio-stems-create, mode "twelve") -> filename. The names follow
# Suno's own stems zip, so tools/mixing/mix_tracks.discover_stems routes each to
# its processing bucket by keyword; "fx" has no keyword and lands in "other".
SUNO_STEM_FILENAMES: dict[str, str] = {
    "vocals": "0 Lead Vocals.wav",
    "backing_vocals": "1 Backing Vocals.wav",
    "drums": "2 Drums.wav",
    "bass": "3 Bass.wav",
    "guitar": "4 Guitar.wav",
    "keyboard": "5 Keyboard.wav",
    "percussion": "6 Percussion.wav",
    "strings": "7 Strings.wav",
    "synth": "8 Synth.wav",
    "fx": "9 FX.wav",
    "brass": "10 Brass.wav",
    "woodwinds": "11 Woodwinds.wav",
}


# =============================================================================
# Helpers
# =============================================================================


def _load_track(
    album_slug: str, track_slug: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a track through the state cache and read its file.

    Returns ``(context, None)`` or ``(None, error_json)``. The context carries
    ``album_slug``, ``album``, ``track_slug``, ``track`` (the cache entry, by
    reference), ``path`` and ``text``.
    """
    normalized_album, album, error = _find_album_or_error(album_slug)
    if error:
        return None, error
    assert album is not None

    matched_slug, track, error = _find_track_or_error(
        album.get("tracks", {}), track_slug, album_slug,
    )
    if error:
        return None, error
    assert track is not None

    track_path = track.get("path", "")
    if not track_path:
        return None, _safe_json({
            "found": False,
            "error": f"No path stored for track '{matched_slug}'",
        })

    path = Path(track_path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, _safe_json({"found": False, "error": f"Cannot read track file: {e}"})

    return {
        "album_slug": normalized_album,
        "album": album,
        "track_slug": matched_slug,
        "track": track,
        "path": path,
        "text": text,
    }, None


def _section_code(text: str, heading: str) -> str | None:
    """The first code block under *heading*, stripped; None when absent or empty."""
    section = _extract_markdown_section(text, heading)
    if section is None:
        return None
    code = _extract_code_block(section)
    if code is None or not code.strip():
        return None
    return code.strip()


def _problem(code: str, severity: str, detail: str) -> dict[str, str]:
    """A problem entry. *severity* is ``blocking`` or ``warning``."""
    return {"code": code, "severity": severity, "detail": detail}


def _instrumental_state(text: str) -> tuple[bool, dict[str, str] | None]:
    """Whether the track is instrumental, plus a problem if its two flags disagree.

    Frontmatter ``instrumental:`` and the Track Details ``Instrumental`` row are
    meant to match (the pre-generation check enforces it). Either one alone is
    accepted, so older track files without frontmatter still resolve.
    """
    frontmatter = parse_frontmatter(text)
    fm_value: bool | None = None
    if "_error" not in frontmatter and isinstance(frontmatter.get("instrumental"), bool):
        fm_value = frontmatter["instrumental"]

    table_raw = (_extract_table_value(text, "Instrumental") or "").strip().lower()
    table_value: bool | None = None
    if table_raw in ("yes", "true"):
        table_value = True
    elif table_raw in ("no", "false"):
        table_value = False

    if fm_value is not None and table_value is not None and fm_value != table_value:
        return False, _problem(
            "instrumental_mismatch", "blocking",
            f"Frontmatter says instrumental: {str(fm_value).lower()} but Track Details "
            f"says {'Yes' if table_value else 'No'} — make them match",
        )
    if fm_value is not None:
        return fm_value, None
    return bool(table_value), None


def _bare_exclusions(exclude: str) -> tuple[str, bool]:
    """Exclude Styles as bare, comma-separated elements.

    Returns the cleaned value and whether any leading "no " was removed.
    """
    items = [item.strip() for item in re.split(r"[,\n]", exclude) if item.strip()]
    cleaned = [
        item if item.lower() in _NO_PREFIX_KEEP else _NO_PREFIX_RE.sub("", item)
        for item in items
    ]
    return ", ".join(cleaned), cleaned != items


def _slider(
    settings: str, key: str, problems: list[dict[str, str]],
) -> float | None:
    """A 0-100 Generation Settings slider as the API's 0-1 fraction, or None if unset."""
    raw = (_extract_table_value(settings, key) or "").strip()
    if raw.lower() in _UNSET:
        return None
    slug = key.lower().replace(" ", "_")
    match = _SLIDER_RE.fullmatch(raw)
    if not match:
        problems.append(_problem(
            f"{slug}_unrecognized", "warning",
            f"{key} '{raw}' is not a number from 0 to 100 — left at Suno's default",
        ))
        return None
    value = int(match.group(1))
    if value > 100:
        problems.append(_problem(
            f"{slug}_clamped", "warning", f"{key} {value} is above 100 — sent as 100",
        ))
        value = 100
    return round(value / 100, 2)


def _setup_cell(section: str | None, key: str) -> str:
    """A Cover / Voice Setup table cell; "" when unset or still the template's placeholder."""
    if not section:
        return ""
    raw = (_extract_table_value(section, key) or "").strip()
    if raw.lower() in _UNSET or _PLACEHOLDER_CELL_RE.fullmatch(raw):
        return ""
    return raw


def _set_cells(settings: str, keys: tuple[str, ...]) -> list[str]:
    """``"Key value"`` for each Generation Settings row in *keys* that is set."""
    cells: list[str] = []
    for key in keys:
        raw = (_extract_table_value(settings, key) or "").strip()
        if raw.lower() not in _UNSET:
            cells.append(f"{key} {raw}")
    return cells


def _is_spoken(text: str) -> bool:
    """Whether the frontmatter marks the track as spoken word (``spoken: true``)."""
    frontmatter = parse_frontmatter(text)
    return "_error" not in frontmatter and frontmatter.get("spoken") is True


def _script(lyrics: str) -> str:
    """A Lyrics Box as a script to speak: section tags dropped, paragraphs kept."""
    out: list[str] = []
    for raw in lyrics.splitlines():
        stripped = raw.strip()
        if stripped and _BRACKET_TAG_RE.fullmatch(stripped):
            continue
        line = " ".join(_BRACKET_TAG_RE.sub(" ", stripped).split())
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def _cover_source(
    source_cell: str, cover_of: str,
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    """The song a cover reworks, from the Source audio cell: ``(cover, None)`` or
    ``(None, problem)``. Only a https://suno.com/song/<id> address names one."""
    url = _first_url(source_cell) if source_cell else None
    clip_id = clip_id_from_url(url) if url else None
    if clip_id:
        return {
            "source_clip_id": clip_id,
            "source_url": f"https://suno.com/song/{clip_id}",
        }, None
    if not source_cell:
        return None, _problem(
            "cover_source_missing", "blocking",
            f'Cover of names "{cover_of}" but Source audio is empty — paste the source\'s song '
            "address (https://suno.com/song/<id>), or clear Cover of to generate an original",
        )
    if url and "suno.com" in url.lower():
        return None, _problem(
            "cover_source_no_clip_id", "blocking",
            "Source audio is a share link, which carries no song id — open it and paste the "
            "address it lands on (https://suno.com/song/<id>)",
        )
    return None, _problem(
        "cover_source_not_on_suno", "blocking",
        f'Source audio is "{source_cell}", not a Suno song address. Through the MCP a cover '
        "needs the source's song page (https://suno.com/song/<id>): upload the audio on "
        "suno.com and paste its address, or make this cover on suno.com "
        "(/bitwize-music:clipboard)",
    )


def _audio_influence(raw: str, problems: list[dict[str, str]]) -> float | None:
    """Audio Influence as the API's 0-1 fraction: "70", "70%" and "0.7" all mean 0.7."""
    match = _INFLUENCE_RE.fullmatch(raw)
    if not match:
        problems.append(_problem(
            "audio_influence_unrecognized", "warning",
            f"Audio Influence '{raw}' is not a number from 0 to 100 — left at Suno's default",
        ))
        return None
    number, percent = match.group(1), match.group(2)
    value = float(number)
    if "." in number and not percent and value <= 1:
        return round(value, 2)
    if value > 100:
        problems.append(_problem(
            "audio_influence_clamped", "warning",
            f"Audio Influence {number} is above 100 — sent as 100",
        ))
        value = 100
    return round(value / 100, 2)


# =============================================================================
# get_generation_request
# =============================================================================


async def get_generation_request(
    album_slug: str, track_slug: str, midi_upload_id: str = "",
) -> str:
    """Build the Suno MCP request that generates a track, from its track file.

    Read-only, and it never calls Suno: the calling skill sends ``request`` to
    the Suno tool named in ``tool``. Maps the track's Suno Inputs — Style Box,
    Exclude Styles, Generation Settings and Lyrics Box — and its Cover / Voice
    Setup block to that tool's parameters. A track makes one of four kinds of
    request:

      - song: audio-create with the Style Box and the Lyrics Box.
      - cover: audio-covers-create, when Source audio (Cover / Voice Setup)
        holds a https://suno.com/song/<id> address. The Style Box is the new
        style and the Lyrics Box is what gets sung.
      - speech: speech-create, when the frontmatter says ``spoken: true``. The
        Lyrics Box is the script, spoken word for word (section tags dropped),
        and the Style Box holds the delivery tags.
      - midi: audio-create playing an uploaded MIDI score, when midi_upload_id
        is given. Suno takes no lyrics with a score, so this makes an
        instrumental sketch of the melody; cover the sketch to have the track's
        lyrics sung over it.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        midi_upload_id: The id midi-upload-complete returned, to make the track
            from a MIDI score (see get_midi_score_plan)

    Returns:
        JSON with:
            supported: False when a blocking problem means nothing should be sent
            kind: song, cover, speech or midi
            tool: the Suno tool to send request to
            request: that tool's arguments. A song carries title, style, lyrics,
                negative_style, model, instrumental, max_mode, vocal_gender,
                duration, controls and workspace_id; a cover adds id (the source
                song); speech carries script and backing_music instead of
                lyrics; a score carries midi_upload_id and description.
                controls always carries variety (0 Off, 1 Normal, 2 High,
                3 Extra, 4 Max; Off unless the track says otherwise, so the
                Style Box is used as written), the sliders the track sets, and
                audio_influence when a Voice or a cover source gives it meaning
            voice: {name} when the track names a saved Voice — find its id with
                voices-list and add it to request as voice_id — else null
            cover: {source_clip_id, source_url} for a cover, else null
            needs_grant: request keys that need the account's `controls.advanced`
                feature — drop them when account-usage does not list it. A dotted
                name such as "controls.weirdness" is a key inside controls;
                controls.variety never needs the grant
            ignored: [{setting, value, reason}] — settings the track file makes
                that this kind of request cannot carry
            problems: [{code, severity: blocking|warning, detail}]
            track_status: the track's current status
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]
    track: dict[str, Any] = ctx["track"]

    problems: list[dict[str, str]] = []
    ignored: list[dict[str, str]] = []
    request: dict[str, Any] = {}

    def leave_out(setting: str, value: str, reason: str) -> None:
        ignored.append({"setting": setting, "value": value, "reason": reason})

    title = str(track.get("title") or ctx["track_slug"]).strip()
    request["title"] = title
    if len(title) > _MAX_TITLE:
        problems.append(_problem(
            "title_too_long", "blocking",
            f"Title is {len(title)} characters; Suno accepts {_MAX_TITLE}",
        ))

    instrumental, mismatch = _instrumental_state(text)
    if mismatch:
        problems.append(mismatch)

    # --- which kind of request ------------------------------------------------------
    setup = _extract_markdown_section(text, "Cover / Voice Setup")
    source_cell = _setup_cell(setup, "Source audio")
    cover_of = _setup_cell(setup, "Cover of")
    voice_name = _setup_cell(setup, "Voice")
    influence_cell = _setup_cell(setup, "Audio Influence")
    midi_id = midi_upload_id.strip()

    kind = "song"
    cover: dict[str, str] | None = None
    if source_cell or cover_of:
        kind = "cover"
        cover, problem = _cover_source(source_cell, cover_of)
        if problem:
            problems.append(problem)
    if _is_spoken(text):
        if kind == "cover":
            problems.append(_problem(
                "spoken_cover", "blocking",
                "The track is spoken word and also names a cover source — a cover is sung; "
                "clear Source audio and Cover of, or remove spoken: true",
            ))
        if instrumental:
            problems.append(_problem(
                "spoken_instrumental", "blocking",
                "The track is marked both spoken and instrumental — speech is the voice; "
                "keep one of the two",
            ))
        kind = "speech"
    if midi_id:
        if kind == "cover":
            problems.append(_problem(
                "midi_and_cover", "blocking",
                "A score and a cover source cannot be combined — make the sketch from the "
                "score first (clear Source audio), then cover the sketch",
            ))
        elif kind == "speech":
            problems.append(_problem(
                "midi_spoken", "blocking", "A spoken-word track cannot play a score",
            ))
        if not _MIDI_UPLOAD_ID_RE.fullmatch(midi_id):
            problems.append(_problem(
                "midi_upload_id_invalid", "blocking",
                f"'{midi_id}' is not an upload id — pass the midi_upload_id that "
                "midi-upload-complete returned",
            ))
        kind = "midi"
    lacks = _KIND_LACKS[kind]
    why = _WHY_NOT.get(kind, {})

    if instrumental and kind == "song":
        request["instrumental"] = True

    style = _section_code(text, "Style Box")
    if style is None:
        problems.append(_problem(
            "style_missing", "blocking",
            "Style Box is empty — run /bitwize-music:suno-engineer",
        ))
    elif _template_style_tokens_in(style):
        problems.append(_problem(
            "style_placeholder", "blocking",
            "Style Box still holds the template placeholder — run /bitwize-music:suno-engineer",
        ))
    else:
        request["style"] = style
        if len(style) > _MAX_STYLE:
            problems.append(_problem(
                "style_too_long", "blocking",
                f"Style Box is {len(style)} characters; Suno accepts {_MAX_STYLE}",
            ))

    lyrics = _section_code(text, "Lyrics Box")
    placeholder = lyrics is not None and _lyrics_placeholder_in(lyrics) is not None
    if "lyrics" in lacks:
        if lyrics is not None and not placeholder:
            leave_out("Lyrics Box", f"{len(lyrics)} characters", why["lyrics"])
    elif placeholder:
        problems.append(_problem(
            "lyrics_placeholder", "blocking",
            "Lyrics Box still holds the template placeholder",
        ))
    elif lyrics is None:
        # An instrumental may omit lyrics; its section tags are optional structure.
        if not instrumental:
            problems.append(_problem(
                "lyrics_missing", "blocking",
                "Lyrics Box is empty — run /bitwize-music:lyric-writer",
            ))
    elif kind == "speech":
        script = _script(lyrics)
        if not script:
            problems.append(_problem(
                "script_empty", "blocking",
                "Lyrics Box has section tags but no words to speak",
            ))
        else:
            request["script"] = script
            if len(script) > _MAX_LYRICS:
                problems.append(_problem(
                    "script_too_long", "blocking",
                    f"The script is {len(script)} characters; Suno accepts {_MAX_LYRICS}",
                ))
    elif kind == "cover" and instrumental:
        # audio-covers-create has no instrumental flag: a cover is instrumental when it
        # is sent no lyrics, so an instrumental track's section tags stay behind.
        leave_out(
            "Lyrics Box", f"{len(lyrics)} characters",
            "a cover is instrumental only when no lyrics are sent",
        )
    else:
        request["lyrics"] = lyrics
        if len(lyrics) > _MAX_LYRICS:
            problems.append(_problem(
                "lyrics_too_long", "blocking",
                f"Lyrics Box is {len(lyrics)} characters; Suno accepts {_MAX_LYRICS}",
            ))

    exclude = _section_code(text, "Exclude Styles")
    if exclude is not None and exclude.lower() not in _UNSET and exclude != _TEMPLATE_EXCLUDE:
        negative_style, stripped = _bare_exclusions(exclude)
        if "negative_style" in lacks:
            leave_out("Exclude Styles", negative_style, why["negative_style"])
        else:
            request["negative_style"] = negative_style
            if stripped:
                problems.append(_problem(
                    "negative_style_no_prefix", "warning",
                    "Exclude Styles lists 'no ...' items, but the field is already the "
                    f"negation — sent as bare elements: {negative_style}. Fix the track file "
                    "(see migrations/0.102.0.md)",
                ))
            if len(negative_style) > _MAX_NEGATIVE_STYLE:
                problems.append(_problem(
                    "negative_style_too_long", "blocking",
                    f"Exclude Styles is {len(negative_style)} characters; "
                    f"Suno accepts {_MAX_NEGATIVE_STYLE}",
                ))

    # Variety Off unless the track asks for more: omitted, Suno applies the model's own
    # default, which is Normal on v6 and v6-mini and rewrites an engineered Style Box.
    controls: dict[str, float] = {"variety": 0}

    settings = _extract_markdown_section(text, "Generation Settings")
    if settings is None:
        if "controls" not in lacks:
            problems.append(_problem(
                "generation_settings_missing", "warning",
                "No Generation Settings section — Suno's defaults are used for model, sliders "
                "and duration, and Variety is sent as Off (add one from templates/track.md "
                "§ Generation Settings)",
            ))
    else:
        model_raw = (_extract_table_value(settings, "Model") or "").strip()
        model = model_raw.lower()
        if "model" in lacks:
            if model not in _UNSET and not (kind == "midi" and model == _MIDI_MODEL):
                leave_out("Model", model_raw, why["model"])
        elif model in _KNOWN_MODELS:
            request["model"] = model
        elif model.startswith("custom:"):
            problems.append(_problem(
                "custom_model_unsupported", "blocking",
                f"Model '{model_raw}' is a Custom Model, which the Suno MCP does not offer — "
                "generate this track on suno.com (use /bitwize-music:clipboard)",
            ))
        elif model in _UNSET:
            problems.append(_problem(
                "model_unset", "warning", "No model set — Suno's default model is used",
            ))
        else:
            problems.append(_problem(
                "model_unrecognized", "blocking",
                f"Model '{model_raw}' not recognized — use v6, v6-wild or v6-mini",
            ))

        if (_extract_table_value(settings, "Max Mode") or "").strip().lower() == "on":
            if "max_mode" in lacks:
                leave_out("Max Mode", "On", why["max_mode"])
            else:
                request["max_mode"] = True

        if "controls" in lacks:
            cells = _set_cells(settings, ("Variety", "Weirdness", "Style Influence"))
            if cells:
                leave_out("Variety and sliders", ", ".join(cells), why["controls"])
        else:
            variety = (_extract_table_value(settings, "Variety") or "").strip()
            if variety.lower() in _VARIETY_LEVELS:
                controls["variety"] = _VARIETY_LEVELS[variety.lower()]
            elif variety.lower() not in _UNSET:
                problems.append(_problem(
                    "variety_unrecognized", "warning",
                    f"Variety '{variety}' is not Off, Normal, High, Extra or Max — sent as Off",
                ))

        gender_cell = (_extract_table_value(settings, "Vocal Gender") or "").strip()
        gender = gender_cell.lower()
        if gender in ("male", "female"):
            if instrumental:
                pass  # nothing sings
            elif "vocal_gender" in lacks:
                leave_out("Vocal Gender", gender_cell, why["vocal_gender"])
            elif voice_name:
                leave_out("Vocal Gender", gender_cell, "the Voice carries its own gender")
            else:
                request["vocal_gender"] = gender
        elif gender not in _UNSET and "vocal_gender" not in lacks:
            problems.append(_problem(
                "vocal_gender_unrecognized", "warning",
                f"Vocal Gender '{gender}' is not Male or Female — left to Suno",
            ))

        duration_raw = (_extract_table_value(settings, "Duration") or "").strip()
        seconds = _parse_duration_seconds(duration_raw)
        if "duration" in lacks:
            if seconds is not None:
                leave_out("Duration", duration_raw, why["duration"])
        elif seconds is not None:
            clamped = min(max(seconds, _MIN_DURATION), _MAX_DURATION)
            if clamped != seconds:
                problems.append(_problem(
                    "duration_clamped", "warning",
                    f"Duration {duration_raw} is outside Suno's {_MIN_DURATION} to {_MAX_DURATION} s "
                    f"range — sent as {clamped} s",
                ))
            request["duration"] = clamped
        elif duration_raw.lower() not in _UNSET:
            problems.append(_problem(
                "duration_unrecognized", "warning",
                f"Duration '{duration_raw}' is not Auto or m:ss — left to Suno",
            ))

        if "controls" not in lacks:
            weirdness = _slider(settings, "Weirdness", problems)
            if weirdness is not None:
                controls["weirdness"] = weirdness
            style_influence = _slider(settings, "Style Influence", problems)
            if style_influence is not None:
                controls["style_influence"] = style_influence

    # --- the Voice, and how closely to follow the audio it or a cover source brings ----
    voice: dict[str, str] | None = None
    if voice_name:
        if "voice" in lacks:
            leave_out("Voice", voice_name, why["voice"])
        else:
            voice = {"name": voice_name}
            if instrumental:
                problems.append(_problem(
                    "voice_on_instrumental", "blocking",
                    f"Voice '{voice_name}' is set on an instrumental track — a Voice always "
                    "sings; clear the Voice or the instrumental flag",
                ))
    if influence_cell:
        if "controls" in lacks:
            leave_out("Audio Influence", influence_cell, why["controls"])
        elif kind == "cover" or voice:
            influence = _audio_influence(influence_cell, problems)
            if influence is not None:
                controls["audio_influence"] = influence
        else:
            leave_out(
                "Audio Influence", influence_cell,
                "there is no Voice or cover source for it to apply to",
            )

    # --- what only one kind carries -----------------------------------------------------
    if kind == "cover" and cover:
        request["id"] = cover["source_clip_id"]
    elif kind == "speech":
        backing = (_extract_table_value(settings or "", "Backing Music") or "").strip().lower()
        request["backing_music"] = backing == "on"
    elif kind == "midi":
        request["midi_upload_id"] = midi_id
        request["instrumental"] = True
        request["model"] = _MIDI_MODEL
        if "style" in request:
            request["description"] = _MIDI_DESCRIPTION + request.pop("style")
        if not instrumental:
            problems.append(_problem(
                "midi_makes_a_sketch", "warning",
                "Suno takes no lyrics with a score, so this makes an instrumental sketch of "
                "the melody. To have the track's lyrics sung over it, put the chosen sketch's "
                "song address in Source audio (Cover / Voice Setup) and generate again",
            ))

    if "controls" not in lacks:
        request["controls"] = controls

    # File the new takes in the album's Suno workspace when it has one.
    workspace = _album_workspace(ctx["album"])
    if workspace:
        request["workspace_id"] = workspace["id"]

    supported = not any(p["severity"] == "blocking" for p in problems)
    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "track_status": track.get("status", ""),
        "supported": supported,
        "kind": kind,
        "tool": _KIND_TOOL[kind],
        "request": request,
        "voice": voice,
        "cover": cover,
        "needs_grant": [
            f"controls.{key}" for key in request.get("controls", {})
            if key not in _GRANT_FREE_CONTROLS
        ] + [key for key in _NEEDS_ADVANCED_CONTROLS if key in request],
        "ignored": ignored,
        "problems": problems,
    })


# =============================================================================
# log_generation
# =============================================================================


def _today() -> str:
    """Today's date for a Generation Log row (a seam for tests)."""
    return datetime.date.today().isoformat()


def _cell(value: str) -> str:
    """Flatten a value so it cannot break out of a markdown table cell."""
    return re.sub(r"\s+", " ", value.replace("|", "/")).strip()


def _fmt_duration(seconds: float) -> str:
    """Seconds as m:ss."""
    total = round(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _generation_log_bounds(lines: list[str]) -> tuple[int, int] | None:
    """``(heading index, end index)`` of the Generation Log section, or None.

    The section runs to the next heading of the same or a higher level.
    """
    for i, line in enumerate(lines):
        heading = _GENERATION_LOG_HEADING_RE.match(line)
        if not heading:
            continue
        level = len(heading.group(1))
        for j in range(i + 1, len(lines)):
            other = _HEADING_RE.match(lines[j])
            if other and len(other.group(1)) <= level:
                return i, j
        return i, len(lines)
    return None


async def log_generation(
    album_slug: str,
    track_slug: str,
    model: str,
    clips: list[dict[str, Any]],
    notes: str = "",
) -> str:
    """Append Suno takes to a track's Generation Log, one row per clip.

    Each row links the take as https://suno.com/song/<clip_id>, so the clip id
    travels with the log. Rows are numbered on from the highest existing row; the
    template's placeholder row is replaced by the first real one. Rating is left
    as "—" — a human marks the keeper. This tool does not change the track's
    Status; call update_track_field(status, "Generated") for that.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        model: Model the takes were generated with (e.g., "v6")
        clips: One entry per take: {"clip_id": Suno clip UUID, "status":
            "complete" or "error", "duration_s": optional seconds,
            "error": optional reason for a failed take}
        notes: Text for the Notes column of every row (e.g., "via MCP, 10 credits")

    Returns:
        JSON with the rows written ({row, clip_id, url, status}) or an error
    """
    if not clips:
        return _safe_json({"error": "No clips to log"})

    cleaned: list[dict[str, Any]] = []
    for clip in clips:
        clip_id = str(clip.get("clip_id", "")).strip().lower()
        if not _CLIP_ID_RE.fullmatch(clip_id):
            return _safe_json({
                "error": f"Invalid clip id '{clip.get('clip_id', '')}' — expected a Suno clip UUID",
            })
        duration = clip.get("duration_s")
        cleaned.append({
            "clip_id": clip_id,
            "status": str(clip.get("status", "complete")).strip().lower() or "complete",
            "duration_s": (
                float(duration)
                if isinstance(duration, int | float) and not isinstance(duration, bool)
                else None
            ),
            "error": str(clip.get("error") or "").strip(),
        })

    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    path: Path = ctx["path"]

    lines = ctx["text"].split("\n")
    bounds = _generation_log_bounds(lines)
    if bounds is None:
        return _safe_json({
            "error": "Track file has no Generation Log section — add one "
                     "(see templates/track.md § Generation Log)",
            "track_slug": ctx["track_slug"],
        })
    start, end = bounds

    table_rows = [i for i in range(start + 1, end) if lines[i].lstrip().startswith("|")]
    numbers = [
        int(match.group(1))
        for i in table_rows
        if (match := _ROW_NUMBER_RE.match(lines[i].lstrip()))
    ]
    next_number = max(numbers, default=0) + 1

    today = _today()
    model_cell = _cell(model) or "—"
    new_rows: list[str] = []
    logged: list[dict[str, Any]] = []
    for offset, clip in enumerate(cleaned):
        number = next_number + offset
        failed = clip["status"] == "error"
        url = f"https://suno.com/song/{clip['clip_id']}"
        parts: list[str] = []
        if clip["duration_s"] is not None:
            parts.append(_fmt_duration(clip["duration_s"]))
        if notes.strip():
            parts.append(notes)
        if failed and clip["error"]:
            parts.append(f"error: {clip['error']}")
        result_cell = "Failed" if failed else f"[Listen]({url})"
        notes_cell = _cell(", ".join(parts)) or "—"
        new_rows.append(
            f"| {number} | {today} | {model_cell} | {result_cell} | {notes_cell} | — |"
        )
        logged.append({
            "row": number, "clip_id": clip["clip_id"], "url": url, "status": clip["status"],
        })

    placeholder = next(
        (i for i in table_rows if _PLACEHOLDER_ROW_RE.fullmatch(lines[i].strip())), None,
    )
    if placeholder is not None:
        lines[placeholder:placeholder + 1] = new_rows
    elif table_rows:
        insert_at = table_rows[-1] + 1
        lines[insert_at:insert_at] = new_rows
    else:
        # No table yet: add one at the end of the section, above its trailing blank lines.
        insert_at = end
        while insert_at > start + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines[insert_at:insert_at] = ["", _LOG_TABLE_HEADER, _LOG_TABLE_SEPARATOR, *new_rows]

    try:
        atomic_write_text(path, "\n".join(lines))
    except OSError as e:
        return _safe_json({"error": f"Cannot write track file: {e}"})

    logger.info(
        "Logged %d take(s) for %s.%s", len(logged), ctx["album_slug"], ctx["track_slug"],
    )

    # The file is written either way; a failed cache refresh self-heals on rebuild.
    try:
        ctx["track"]["mtime"] = path.stat().st_mtime
        write_state(_shared.cache.get_state())
    except Exception as e:
        logger.warning(
            "Generation Log written but cache update failed for %s.%s: %s",
            ctx["album_slug"], ctx["track_slug"], e,
        )

    return _safe_json({
        "success": True,
        "album_slug": ctx["album_slug"],
        "track_slug": ctx["track_slug"],
        "rows": logged,
    })


# =============================================================================
# Reading the Generation Log back
# =============================================================================


def _first_url(cell: str) -> str | None:
    """The first URL in a table cell — a markdown link's target, or a bare URL."""
    link = _MARKDOWN_URL_RE.search(cell)
    if link:
        return link.group(1)
    bare = _BARE_URL_RE.search(cell)
    return bare.group(0) if bare else None


def clip_id_from_url(url: str) -> str | None:
    """The Suno clip id in a ``https://suno.com/song/<uuid>`` URL, or None.

    Older logs hold ``https://suno.com/s/<short>`` share links, which carry no
    clip id.
    """
    match = _SONG_URL_RE.search(url)
    return match.group(1).lower() if match else None


def _split_row(line: str) -> list[str]:
    """Cells of a markdown table row (escaped pipes stay inside their cell)."""
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    return [cell.strip() for cell in _UNESCAPED_PIPE_RE.split(inner)]


def parse_generation_log(text: str) -> list[dict[str, Any]]:
    """The takes recorded in a track file's Generation Log, in table order.

    Each take: ``row``, ``date``, ``model``, ``url`` (None when the Result cell
    has no link), ``clip_id`` (None for a legacy share link), ``notes``,
    ``rating``, ``approved`` (the Rating cell carries a check mark), and
    ``duration_s`` and ``credits`` read from the Notes when log_generation
    wrote them ("3:14, via MCP, 10 credits"), else None. Handles the current
    six-column table and the older five-column one without Model.

    A row whose Notes say "instrumental version of take N" is a version of
    another take, not a take of the track: ``version`` names it (else ""),
    ``version_of`` is N, and a check mark sets ``version_keeper`` — the version
    to import — while ``approved`` stays False, so a version is never taken for
    the track's keeper.
    """
    lines = text.split("\n")
    bounds = _generation_log_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds

    takes: list[dict[str, Any]] = []
    for i in range(start + 1, end):
        stripped = lines[i].strip()
        if not stripped.startswith("|"):
            continue
        cells = _split_row(stripped)
        if len(cells) < 3 or not cells[0].isdigit():
            continue  # header, separator or the template's placeholder row
        url = next((found for found in map(_first_url, cells[1:]) if found), None)
        notes = cells[-2] if len(cells) >= 4 else ""
        length = _NOTE_DURATION_RE.match(notes)
        cost = _NOTE_CREDITS_RE.search(notes)
        version = _VERSION_NOTE_RE.search(notes)
        checked = any(mark in cells[-1] for mark in _APPROVED_MARKS)
        takes.append({
            "row": int(cells[0]),
            "date": cells[1],
            "model": cells[2] if len(cells) >= 6 else "",
            "url": url,
            "clip_id": clip_id_from_url(url) if url else None,
            "notes": notes,
            "rating": cells[-1],
            "approved": checked and not version,
            "duration_s": int(length.group(1)) * 60 + int(length.group(2)) if length else None,
            "credits": int(cost.group(1)) if cost else None,
            "version": version.group(1).lower() if version else "",
            "version_of": int(version.group(2)) if version else None,
            "version_keeper": checked and bool(version),
        })
    return takes


def album_audio_dir(
    album_slug: str, album: dict[str, Any],
) -> tuple[Path | None, str | None]:
    """An album's audio directory — it need not exist yet — or an error JSON."""
    config = _shared.cache.get_state().get("config", {})
    audio_root = config.get("audio_root", "")
    artist = config.get("artist_name", "")
    if not audio_root or not artist:
        return None, _safe_json({"error": "audio_root or artist_name not configured"})
    genre = album.get("genre", "")
    if not genre:
        return None, _safe_json({"error": f"Genre not found for album '{album_slug}'"})
    try:
        return _album_dir(
            audio_root, artist=artist, genre=genre, album=album_slug, confine=False,
        ), None
    except ValueError as exc:
        return None, _safe_json({"error": str(exc)})


# =============================================================================
# get_suno_import_plan
# =============================================================================


def keeper_clip(
    text: str,
) -> tuple[str | None, str | None, str | None, dict[str, str] | None]:
    """The approved take of a track file: ``(clip_id, source, link_url, problem)``.

    The Suno Link names the keeper; when it is unset, the one Generation Log
    row marked ✓ does. ``source`` is ``suno_link`` or ``generation_log``. When
    no clip id can be given, ``problem`` says why: ``legacy_link`` (a share link
    from before MCP generation), ``keeper_ambiguous`` or ``no_keeper``.
    """
    link_url = _first_url((_extract_table_value(text, "Suno Link") or "").strip())
    clip_id = clip_id_from_url(link_url) if link_url else None
    if clip_id:
        return clip_id, "suno_link", link_url, None
    if link_url is not None:
        return None, None, link_url, _problem(
            "legacy_link", "blocking",
            "The Suno Link is a share link from before MCP generation and carries no clip "
            "id — download the file on suno.com and import it with "
            "/bitwize-music:import-audio <file> <album>",
        )
    approved = [
        take for take in parse_generation_log(text) if take["approved"] and take["clip_id"]
    ]
    if len(approved) == 1:
        return approved[0]["clip_id"], "generation_log", None, None
    if approved:
        rows = ", ".join(str(take["row"]) for take in approved)
        return None, None, None, _problem(
            "keeper_ambiguous", "blocking",
            f"Generation Log rows {rows} are all marked as keepers — set the Suno "
            "Link to the one to import",
        )
    return None, None, None, _problem(
        "no_keeper", "blocking",
        "No approved take — mark the keeper ✓ in the Generation Log and set "
        "the Suno Link first",
    )


def _version_clip(
    text: str, version: str,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """The version of a track to import: ``(log row, None)`` or ``(None, problem)``.

    It is the one row of that version marked with a check mark.
    """
    if version not in VERSIONS:
        return None, _problem(
            "version_unknown", "blocking",
            f"'{version}' is not a version this tool imports — it knows: {', '.join(VERSIONS)}",
        )
    rows = [
        take for take in parse_generation_log(text)
        if take["version"] == version and take["clip_id"]
    ]
    if not rows:
        return None, _problem(
            "no_version_takes", "blocking",
            f"No {version} version has been made of this track — "
            f"/bitwize-music:edit-take <album> <track> {version}",
        )
    marked = [take for take in rows if take["version_keeper"]]
    if len(marked) == 1:
        return marked[0], None
    listed = ", ".join(str(take["row"]) for take in (marked or rows))
    if marked:
        return None, _problem(
            "version_keeper_ambiguous", "blocking",
            f"Generation Log rows {listed} are all marked as the {version} version to keep — "
            "leave the mark on one",
        )
    return None, _problem(
        "no_version_keeper", "blocking",
        f"Mark the {version} version to keep ✓ in the Generation Log (rows {listed})",
    )


async def get_suno_import_plan(album_slug: str, track_slug: str, version: str = "") -> str:
    """Say which Suno clip is a track's keeper and where its audio should be saved.

    Read-only, and it never calls Suno. The keeper is the clip in the track's
    Suno Link; with no link set, the one take marked with a check mark in the
    Generation Log. Paths follow the album's audio layout: the WAV goes to
    originals/ when that directory exists, else the album audio root; stems go
    to stems/<track-slug>/ under names the mix tools route by instrument.

    With version ("instrumental"), plans the import of that version of the
    track instead: the one Generation Log row of that version marked with a
    check mark, saved as versions/<track-slug>-<version>.wav — outside the
    folder the mastering tools read, so it is never mastered as a track.

    Args:
        album_slug: Album slug (e.g., "my-album")
        track_slug: Track slug or number (e.g., "01-track-name" or "01")
        version: "" for the track's keeper, or "instrumental" for its
            instrumental version (made with get_edit_request)

    Returns:
        JSON with:
            clip_id: the keeper's Suno clip id, or null (see problems)
            clip_source: "suno_link" or "generation_log"
            song_url: the keeper's suno.com page
            version: the version planned, "" for the keeper
            take: the Generation Log row of a version (versions only)
            wav: {path: where to save the WAV, existing: a file already
                imported for this track, or null}
            stems: {dir, exists, files: {suno part name: file path}}; null
                for a version
            problems: [{code, severity, detail}] — no_keeper, keeper_ambiguous
                or legacy_link when there is no clip id to import; for a
                version, version_unknown, no_version_takes, no_version_keeper
                or version_keeper_ambiguous
    """
    ctx, error = _load_track(album_slug, track_slug)
    if error:
        return error
    assert ctx is not None
    text: str = ctx["text"]
    track_slug_resolved: str = ctx["track_slug"]

    audio_dir, error = album_audio_dir(ctx["album_slug"], ctx["album"])
    if error:
        return error
    assert audio_dir is not None

    version = version.strip().lower()
    if version:
        row, problem = _version_clip(text, version)
        target = audio_dir / "versions" / f"{track_slug_resolved}-{version}.wav"
        return _safe_json({
            "found": True,
            "album_slug": ctx["album_slug"],
            "track_slug": track_slug_resolved,
            "clip_id": row["clip_id"] if row else None,
            "clip_source": "generation_log" if row else None,
            "song_url": row["url"] if row else None,
            "version": version,
            "take": row["row"] if row else None,
            "wav": {"path": str(target), "existing": str(target) if target.is_file() else None},
            "stems": None,
            "workspace": _album_workspace(ctx["album"]),
            "problems": [problem] if problem else [],
        })

    problems: list[dict[str, str]] = []
    clip_id, clip_source, link_url, problem = keeper_clip(text)
    if problem:
        problems.append(problem)

    originals = audio_dir / "originals"
    wav_dir = originals if originals.is_dir() else audio_dir
    existing = find_track_audio(wav_dir, track_slug_resolved)
    stems_dir = audio_dir / "stems" / track_slug_resolved

    return _safe_json({
        "found": True,
        "album_slug": ctx["album_slug"],
        "track_slug": track_slug_resolved,
        "clip_id": clip_id,
        "clip_source": clip_source,
        "song_url": f"https://suno.com/song/{clip_id}" if clip_id else link_url,
        "version": "",
        "wav": {
            "path": str(wav_dir / f"{track_slug_resolved}.wav"),
            "existing": str(existing) if existing else None,
        },
        "stems": {
            "dir": str(stems_dir),
            "exists": stems_dir.is_dir(),
            "files": {
                part: str(stems_dir / filename)
                for part, filename in SUNO_STEM_FILENAMES.items()
            },
        },
        "workspace": _album_workspace(ctx["album"]),
        "problems": problems,
    })


# =============================================================================
# Album workspaces
# =============================================================================

_WORKSPACE_ID_RE = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
_WORKSPACE_BATCH = 50  # workspaces-update-clips files at most 50 songs per call
_WORKSPACE_KEY = "suno_workspace"
_WORKSPACE_COMMENT = (
    "# Suno workspace that holds this album's takes; /bitwize-music:generate fills it in"
)
_TEMPLATE_ALBUM_TITLES = frozenset({"", "[Album Title]"})


def _album_workspace(album: dict[str, Any]) -> dict[str, str] | None:
    """The album's recorded Suno workspace, ``{"id", "name"}``, or None."""
    workspace = album.get(_WORKSPACE_KEY)
    if not isinstance(workspace, dict) or not workspace.get("id"):
        return None
    return {"id": str(workspace["id"]), "name": str(workspace.get("name") or "")}


def _album_clips(album: dict[str, Any]) -> list[dict[str, Any]]:
    """Every take with a clip id in the album's Generation Logs, in track and take order.

    Legacy share links carry no clip id and are left out.
    """
    clips: list[dict[str, Any]] = []
    for track_slug, track in sorted((album.get("tracks") or {}).items()):
        path = track.get("path") or ""
        if not path:
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Skipping %s while collecting clips: %s", path, e)
            continue
        for take in parse_generation_log(text):
            if take["clip_id"]:
                clips.append({
                    "track_slug": track_slug,
                    "take": take["row"],
                    "clip_id": take["clip_id"],
                    "keeper": take["approved"],
                })
    return clips


async def get_album_workspace(album_slug: str) -> str:
    """The Suno workspace an album's takes are filed in, and the takes it has so far.

    /bitwize-music:generate reads this before generating: a recorded workspace
    is passed to audio-create (see get_generation_request), and an album without
    one gets a workspace created and recorded with set_album_workspace. clips
    lists every take in the album's Generation Logs so earlier takes can be filed
    with workspaces-update-clips; batches splits their ids into groups of 50,
    which is that tool's limit.

    Args:
        album_slug: Album slug

    Returns:
        JSON with found, album_slug, album_title, workspace ({id, name} or null),
        suggested_name (the album title, or the slug while the title is still
        the template's placeholder), clips ([{track_slug, take, clip_id,
        keeper}]), batches ([[clip ids]]), and enabled (config
        generation.suno_workspaces, default true)
    """
    album_slug, album, error = _find_album_or_error(album_slug)
    if error:
        return error
    assert album is not None

    title = str(album.get("title") or "").strip()
    clips = _album_clips(album)
    ids = [clip["clip_id"] for clip in clips]
    generation = _shared.cache.get_state().get("config", {}).get("generation", {}) or {}
    return _safe_json({
        "found": True,
        "album_slug": album_slug,
        "album_title": title,
        "workspace": _album_workspace(album),
        "suggested_name": album_slug if title in _TEMPLATE_ALBUM_TITLES else title,
        "clips": clips,
        "batches": [ids[i:i + _WORKSPACE_BATCH] for i in range(0, len(ids), _WORKSPACE_BATCH)],
        "enabled": bool(generation.get("suno_workspaces", True)),
    })


def _frontmatter_bounds(lines: list[str]) -> int | None:
    """Index of the closing ``---`` of a file's frontmatter, or None."""
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i
    return None


def _write_frontmatter_block(
    text: str, key: str, comment: str, fields: dict[str, str],
) -> str | None:
    """*text* with the ``key:`` block of its frontmatter set, or None without frontmatter.

    Edits lines rather than re-dumping the YAML, so the comments in the album
    README survive. An existing block is replaced; otherwise one is added just
    before the closing ``---``. Values are written as double-quoted scalars.
    """
    lines = text.split("\n")
    end = _frontmatter_bounds(lines)
    if end is None:
        return None
    block = [f"{key}:  {comment}"] + [
        f"  {name}: {json.dumps(value, ensure_ascii=False)}" for name, value in fields.items()
    ]
    start = next((i for i in range(1, end) if lines[i].startswith(f"{key}:")), None)
    if start is None:
        return "\n".join(lines[:end] + block + lines[end:])
    stop = start + 1
    while stop < end and (lines[stop].startswith((" ", "\t")) or not lines[stop].strip()):
        stop += 1
    return "\n".join(lines[:start] + block + lines[stop:])


def record_album_ref(
    album_slug: str, ref_id: str, name: str, *, key: str, comment: str, noun: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Record a Suno ``{id, name}`` reference in an album README's frontmatter.

    The shared body of set_album_workspace and set_album_playlist: validates the
    id and name, writes the ``key:`` block (keeping the file's comments), checks
    that the result still parses, and refreshes the album's cache entry.

    Returns ``({"path", "ref": {"id", "name"}}, None)`` or ``(None, error_json)``.
    """
    album_slug, album, error = _find_album_or_error(album_slug)
    if error:
        return None, error
    assert album is not None

    ref_id = ref_id.strip().lower()
    name = name.strip()
    if not _WORKSPACE_ID_RE.match(ref_id):
        return None, _safe_json({"error": f"Not a Suno {noun} id: '{ref_id}'"})
    if not name:
        return None, _safe_json({"error": f"The {noun} needs a name"})

    readme = Path(album.get("path") or "") / "README.md"
    if not album.get("path") or not readme.is_file():
        return None, _safe_json({"error": f"README.md not found for album '{album_slug}'"})
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, _safe_json({"error": f"Cannot read {readme}: {e}"})

    updated = _write_frontmatter_block(text, key, comment, {"id": ref_id, "name": name})
    if updated is None:
        return None, _safe_json({"error": f"{readme} has no YAML frontmatter"})
    check = parse_frontmatter(updated)
    recorded = check.get(key) if isinstance(check, dict) else None
    if "_error" in check or not isinstance(recorded, dict) or recorded.get("id") != ref_id:
        return None, _safe_json({
            "error": "The frontmatter would not parse after the change; nothing written",
        })

    try:
        atomic_write_text(readme, updated)
    except OSError as e:
        return None, _safe_json({"error": f"Cannot write {readme}: {e}"})

    ref = {"id": ref_id, "name": name}
    # The file is written either way; a failed cache refresh self-heals on rebuild.
    try:
        album[key] = ref
        album["readme_mtime"] = readme.stat().st_mtime
        write_state(_shared.cache.get_state())
    except Exception as e:
        logger.warning("%s recorded for %s but cache update failed: %s", noun, album_slug, e)

    logger.info("Album %s: Suno %s %s (%s)", album_slug, noun, name, ref_id)
    return {"path": str(readme), "ref": ref}, None


async def set_album_workspace(album_slug: str, workspace_id: str, name: str) -> str:
    """Record the Suno workspace that holds an album's takes.

    Writes the suno_workspace block in the album README's frontmatter (keeping
    its comments) and refreshes the state cache. From then on
    get_generation_request carries the workspace id and get_suno_import_plan
    reports it. Call it right after workspaces-create, or to point the album
    at a workspace that already exists.

    Args:
        album_slug: Album slug
        workspace_id: The workspace's id from workspaces-create or workspaces-list
        name: The workspace's name, for people reading the README

    Returns:
        JSON with updated, path and workspace, or an error
    """
    recorded, error = record_album_ref(
        album_slug, workspace_id, name,
        key=_WORKSPACE_KEY, comment=_WORKSPACE_COMMENT, noun="workspace",
    )
    if error:
        return error
    assert recorded is not None
    return _safe_json({"updated": True, "path": recorded["path"], "workspace": recorded["ref"]})


def register(mcp: Any) -> None:
    """Register Suno generation bridge tools with the MCP server."""
    mcp.tool()(get_generation_request)
    mcp.tool()(log_generation)
    mcp.tool()(get_suno_import_plan)
    mcp.tool()(get_album_workspace)
    mcp.tool()(set_album_workspace)
