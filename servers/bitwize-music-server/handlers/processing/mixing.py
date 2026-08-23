"""Mix polish tools — per-stem audio cleanup before mastering."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from handlers._shared import _find_wav_source_dir, _is_path_confined, _safe_json
from handlers.processing import _helpers

logger = logging.getLogger(__name__)


async def polish_audio(
    album_slug: str,
    genre: str = "",
    use_stems: bool = True,
    dry_run: bool = False,
    track_filename: str = "",
    analyzer_results: dict[str, Any] | None = None,
) -> str:
    """Polish audio tracks by processing stems or full mixes.

    When use_stems=True (default), looks for stem WAV files in a stems/
    subfolder with per-track directories (vocals.wav, drums.wav, bass.wav,
    other.wav). Processes each stem with targeted cleanup and remixes them.

    When use_stems=False, processes full mix WAV files directly.

    Writes polished output to a polished/ subfolder. Originals are preserved.

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset for stem-specific settings (e.g., "hip-hop").
            Defaults to the album's own genre (looked up from state) when
            omitted, so genre-scoped overrides apply without passing it
            explicitly; an explicit value always wins. An unrecognized
            EXPLICIT genre returns an error. An unrecognized DERIVED
            genre (the album's own state-recorded genre has no
            `tools/mixing/mix-presets.yaml` section) is NOT an error and
            is NOT dropped either — it's logged and used as-is, since
            settings resolution already tolerates a mix-unknown genre
            gracefully (shipped per-stem defaults, plus the
            mastering-preset click-threshold overlay, which may still
            recognize the genre). (#556)
        use_stems: If true, process per-stem WAVs; if false, process full mixes
        dry_run: If true, analyze only without writing files
        track_filename: If set, only process this one track (e.g.,
            "01-track-name.wav"). In stems mode, matches the stem track
            directory with the same stem name. In full-mix mode, matches
            the WAV filename directly. Empty = process whole album.
        analyzer_results: Optional pre-computed per-track/per-stem
            analyzer output from `analyze_mix_issues`. When None and
            `dry_run=False`, the analyzer is run internally so
            recommendations still flow through. When None and
            `dry_run=True`, the analyzer is skipped (dry-run is meant
            to be fast) and `summary.overrides_applied` will be empty.
            polish_album passes its existing analyze-stage output
            here to avoid a duplicate run. (#336)

    Returns:
        JSON with per-track results, settings, and summary
    """
    dep_err = _helpers._check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    from tools.mixing.mix_tracks import (
        discover_stems,
        load_mix_presets,
        mix_track_full,
        mix_track_stems,
    )

    # #556: default genre from the album's own genre (state cache) when
    # the caller didn't pass one explicitly, so genre-scoped mix
    # overrides apply on a plain polish_audio(album_slug) call. An
    # explicit genre always wins; a derivation failure (album missing
    # from state, no genre recorded) falls back to today's no-genre
    # behavior rather than erroring.
    genre_was_explicit = bool(genre)
    if not genre:
        genre = _helpers._derive_album_genre(album_slug)

    # Validate genre if specified
    if genre:
        presets = load_mix_presets()
        genre_key = genre.lower()
        if genre_key not in presets.get('genres', {}):
            # #556 round 3: "not in the MIX preset set" is not the same
            # as "not a genre". The two preset files are independent and
            # very differently sized — the mastering set carries ~407
            # genres, the mix set ~73, and ~334 real mastering genres
            # (idm, dark-cabaret, synth-pop, post-punk...) have no mix
            # section at all. Round 2 hard-errored an EXPLICIT genre on
            # mix-set membership alone, so naming an album's own genre
            # failed a call that succeeded when the argument was omitted
            # and the identical value was derived — while
            # `skills/mix-engineer/SKILL.md` tells Claude to pass it
            # explicitly. The error also listed only the 73 mix genres,
            # implying the genre was invalid project-wide.
            #
            # An explicit genre is now checked against the UNION of both
            # preset sets: unknown to both is a typo and still hard-fails
            # (with the union listed), while known to mastering but not
            # to mix takes the same informational path a derived genre
            # takes — the mix chain resolves it gracefully (shipped
            # per-stem defaults plus the mastering-preset click overlay,
            # which reads the set that DOES recognize it).
            if genre_was_explicit and not _helpers._genre_known_anywhere(genre):
                return _safe_json({
                    "error": f"Unknown genre: {genre}",
                    "available_genres": sorted(_helpers._all_known_genres()),
                })
            # #556 round 2: an unrecognized DERIVED genre is NOT blanked
            # — the album's own state-recorded genre can simply predate
            # or fall outside this preset's genre list (e.g. a niche
            # "dark-cabaret"), and `load_mix_presets()`-based settings
            # resolution already tolerates that gracefully (shipped
            # per-stem defaults, plus the mastering-preset click overlay,
            # which reads a SEPARATE preset set and may still recognize
            # the genre). Blanking here (round 1) threw that overlay
            # away and made this function's own analyzer-auto-run call
            # below (which shares this SAME `genre` variable) agree with
            # itself, but disagreed with a standalone `analyze_mix_issues`
            # call for the same album, which never blanked. Just inform;
            # `genre` keeps flowing through unchanged below. The hard
            # error above stays for a genre the caller actually typed.
            _helpers._note_unpresetted_mix_genre(genre, album_slug)

    output_dir = audio_dir / "polished"
    if not dry_run:
        output_dir.mkdir(exist_ok=True)

    # #336: polish consumes analyzer per-stem recommendations. Auto-run
    # the analyzer when the caller didn't provide results (so direct
    # polish_audio calls still see the coupling). polish_album skips
    # this by passing its existing analyze-stage output down.
    if analyzer_results is None and not dry_run:
        analyzer_json = await analyze_mix_issues(album_slug, genre)
        analyzer_parsed = json.loads(analyzer_json)
        if "error" in analyzer_parsed:
            # Analyzer failure is non-fatal for polish — proceed without recs,
            # but log the error so operators can see why overrides are empty.
            logger.warning(
                "polish_audio analyzer auto-run failed for album %r (genre=%r): %s",
                album_slug, genre, analyzer_parsed.get("error"),
            )
        else:
            analyzer_results = analyzer_parsed

    # Build per-track analyzer rec lookup: {track_basename: {stem: {...}}}
    per_track_recs: dict[str, dict[str, dict[str, Any]]] = {}
    if analyzer_results:
        for track_entry in analyzer_results.get("tracks", []):
            # Stems-mode entry shape: {"track": name, "stems": {stem: analysis}}
            if "stems" in track_entry and isinstance(track_entry["stems"], dict):
                per_track_recs[track_entry["track"]] = track_entry["stems"]

    loop = asyncio.get_running_loop()
    track_results = []

    # Auto-detect stems when use_stems=True (default): prefer stems if
    # available, fall back to full-mix mode gracefully instead of erroring.
    if use_stems:
        stems_dir = audio_dir / "stems"
        if not stems_dir.is_dir() or not any(stems_dir.iterdir()):
            # Graceful fallback — process full mixes instead of erroring
            use_stems = False

    if track_filename and not _is_path_confined(audio_dir, track_filename):
        return _safe_json({
            "error": "Invalid track_filename: path must not escape the album directory",
            "track_filename": track_filename,
        })

    if use_stems:
        # Stems mode: look for stems/ subdirectory with track folders
        stems_dir = audio_dir / "stems"

        track_dirs = sorted([d for d in stems_dir.iterdir() if d.is_dir()])
        if not track_dirs:
            return _safe_json({"error": f"No track directories in {stems_dir}"})

        if track_filename:
            wanted = Path(track_filename).stem
            track_dirs = [d for d in track_dirs if d.name == wanted]
            if not track_dirs:
                return _safe_json({
                    "error": f"Track not found in stems/: {track_filename}",
                    "available_tracks": sorted([d.name for d in stems_dir.iterdir() if d.is_dir()]),
                })

        for track_dir in track_dirs:
            stem_paths = discover_stems(track_dir)

            if not stem_paths:
                continue

            out_path = str(output_dir / f"{track_dir.name}.wav")

            _stem_output_dir = (output_dir / track_dir.name) if not dry_run else None

            track_recs = per_track_recs.get(track_dir.name) or None

            def _do_stems(
                sp: dict[str, str | list[str]], op: str, g: str | None,
                dr: bool, sd: Path | None, ar: dict[str, Any] | None,
            ) -> dict[str, Any]:
                return mix_track_stems(
                    sp, op, genre=g, dry_run=dr,
                    stem_output_dir=sd, analyzer_recs=ar,
                )

            result = await loop.run_in_executor(
                None, _do_stems, stem_paths, out_path,
                genre or None, dry_run, _stem_output_dir, track_recs,
            )

            if result:
                result["track_name"] = track_dir.name
                track_results.append(result)

    else:
        # Full-mix mode: process WAV files directly
        source_dir = _find_wav_source_dir(audio_dir)
        wav_files = sorted([
            f for f in source_dir.iterdir()
            if f.suffix.lower() == ".wav" and "venv" not in str(f)
        ])

        if not wav_files:
            return _safe_json({"error": f"No WAV files found in {audio_dir}"})

        if track_filename:
            wanted_name = Path(track_filename).name
            wav_files = [f for f in wav_files if f.name == wanted_name]
            if not wav_files:
                return _safe_json({
                    "error": f"Track file not found: {track_filename}",
                    "available_files": [f.name for f in source_dir.glob("*.wav")],
                })

        for wav_file in wav_files:
            out_path = str(output_dir / wav_file.name)

            def _do_full(ip: str, op: str, g: str | None, dr: bool) -> dict[str, Any]:
                return mix_track_full(ip, op, genre=g, dry_run=dr)

            result = await loop.run_in_executor(
                None, _do_full, str(wav_file), out_path,
                genre or None, dry_run,
            )

            if result:
                track_results.append(result)

    if not track_results:
        return _safe_json({"error": "No tracks were processed."})

    aggregated_overrides: list[dict[str, Any]] = []
    aggregated_blocked: list[dict[str, Any]] = []
    for tr in track_results:
        track_label = tr.get("track_name") or tr.get("filename") or ""
        for entry in tr.get("overrides_applied", []):
            # Explicit track label last so it can't be shadowed by an entry
            # that ever gains a "track" field (defensive — entries don't
            # currently carry one).
            aggregated_overrides.append({**entry, "track": track_label})
        # #553: recommendations the polish whitelist dropped. Surfaced
        # next to the applied ones so "the analyzer keeps recommending
        # this and polish never applies it" is visible to the operator.
        for entry in tr.get("blocked", []):
            aggregated_blocked.append({**entry, "track": track_label})

    return _safe_json({
        "tracks": track_results,
        "settings": {
            "genre": genre or None,
            "use_stems": use_stems,
            "dry_run": dry_run,
            "track_filename": track_filename or None,
        },
        "summary": {
            "tracks_processed": len(track_results),
            "mode": "stems" if use_stems else "full_mix",
            "output_dir": str(output_dir) if not dry_run else None,
            "overrides_applied": aggregated_overrides,
            "blocked_recommendations": aggregated_blocked,
        },
    })


_ANALYZER_DEFAULT_PEAK_RATIO = 15.0

# Per-stem issue tags that are NOT album-level mix problems, and so must
# not roll up into a track's `issues` or `album_summary.common_issues`.
# `none_detected` is the explicit all-clear. `skipped_empty` (#553) is a
# routing fact, not a defect: Suno's Auto Split returns every requested
# stem category, and the ones with no source content come back as a
# ~-55 dBFS noise floor — normal, and already reported on the stem
# itself. Rolling it up read as "every track has something wrong".
_NON_ISSUE_TAGS = frozenset({"none_detected", "skipped_empty"})


def _resolve_analyzer_peak_ratio(
    stem_name: str | None, genre: str | None,
) -> float:
    """Resolve the click detector `peak_ratio` for a (stem, genre) pair.

    Single source of truth shared with the processor side. The analyzer
    and the per-stem polish chain MUST agree on this threshold or users
    see "393 detected / 1748 removed" divergence between
    `analyze_mix_issues` output and polish output (#323 follow-up).

    The processor's `tools.mixing.mix_tracks._get_stem_settings` already
    merges `mix-presets.yaml` defaults → mix-preset genre overrides →
    mastering-preset `click_peak_ratio` overlay. This function delegates
    to it and pulls out the one field the analyzer cares about, so the
    two sides are identical by construction.

    Args:
        stem_name: Canonical stem name (e.g. ``"keyboard"``). When None
            or unknown, the full-mix resolver is used.
        genre: Lowercase genre slug. Empty or None means no genre
            overlay — defaults only.

    Returns:
        Effective `peak_ratio`. Falls back to
        ``_ANALYZER_DEFAULT_PEAK_RATIO`` when no preset provides one.
    """
    try:
        from tools.mixing.mix_tracks import (
            _get_full_mix_settings,
            _get_stem_settings,
            _setting_float,
        )
    except ImportError:
        return _ANALYZER_DEFAULT_PEAK_RATIO

    g = genre or None
    if stem_name:
        settings = _get_stem_settings(stem_name, g)
    else:
        settings = _get_full_mix_settings(g)
    # Read the key exactly as the de-clicker does (#553). A bare
    # `float(raw)` split the two sides apart on anything unparseable: a
    # quoted `click_peak_ratio: "20"` gave the analyzer 20.0 while polish
    # warned and fell back to 15.0, and a non-numeric string raised
    # ValueError out of the analyzer instead of warning. Same read, same
    # default, same warn-and-default contract.
    return _setting_float(settings, "click_peak_ratio", _ANALYZER_DEFAULT_PEAK_RATIO)


_ANALYZER_DEFAULT_EXCITATION_DB = 2.0


def _resolve_excitation_db_when_dark(
    stem_name: str | None, genre: str | None,
) -> float:
    """Resolve `excitation_db_when_dark` for a (stem, genre) pair (#556).

    Delegates to the processor-side resolvers for the same reason every
    sibling here does: so the analyzer cannot reach a different value
    than the merged presets say.

    Round 2 read this key straight out of
    ``MIX_PRESETS["defaults"][stem]`` with a bare ``float()``, which had
    two consequences. A genre-scoped override of it — ``genres.electronic.
    vocals.excitation_db_when_dark`` — could never take effect anywhere,
    since this is the key's only read in the codebase, making it the
    exact "override written correctly, silently ignored" defect class
    #553/#556 exist to remove. And an unreadable value (``"2.5 dB"``, a
    YAML null, a list) raised straight out of ``analyze_mix_issues``
    rather than warning and falling back.
    """
    try:
        from tools.mixing.mix_tracks import (
            _get_full_mix_settings,
            _get_stem_settings,
            _setting_float,
        )
    except ImportError:
        return _ANALYZER_DEFAULT_EXCITATION_DB

    g = genre or None
    if stem_name:
        settings = _get_stem_settings(stem_name, g)
    else:
        settings = _get_full_mix_settings(g)
    return _setting_float(
        settings, "excitation_db_when_dark", _ANALYZER_DEFAULT_EXCITATION_DB,
    )


def _resolve_silence_gate_dbfs(stem_name: str, genre: str | None) -> float:
    """Resolve the polish silence gate for a (stem, genre) pair.

    Delegates to the processor side so `analyze_mix_issues` and
    `mix_track_stems` cannot drift: both read `silence_gate_dbfs` out of
    the same merged presets, falling back to the same module constant
    (#553). Returns the constant's value when the mixing module is
    unavailable, matching `_resolve_analyzer_peak_ratio`'s posture.
    """
    try:
        from tools.mixing.mix_tracks import (
            SILENT_STEM_PEAK_DBFS,
            STEM_NAMES,
            _get_stem_settings,
            resolve_silence_gate_dbfs,
        )
    except ImportError:
        return -40.0

    if stem_name not in STEM_NAMES:
        return SILENT_STEM_PEAK_DBFS
    return resolve_silence_gate_dbfs(_get_stem_settings(stem_name, genre or None))


def _resolve_analyzer_thresholds() -> tuple[float, float, bool]:
    """Load (dark_high_mid_ratio, harsh_high_mid_ratio, adm_aware_excitation)
    from mix presets.

    Falls back to (0.10, 0.25, False) when the analyzer preset block is absent.
    Values are consumed by `_build_analyzer` for the dark-track and
    harsh-highmids branches respectively (#336), and by the new
    adm_aware_excitation path that emits an excitation_db recommendation
    for dark-classified stems when the flag is enabled.
    """
    try:
        from tools.mixing.mix_tracks import load_mix_presets
    except ImportError:
        return 0.10, 0.25, False
    from tools.shared.config import coerce_yaml_bool, coerce_yaml_float

    presets = load_mix_presets()
    analyzer = presets.get("defaults", {}).get("analyzer", {})
    # #556 round 3: these two were left on a bare `float()` when the
    # boolean on the line below was hardened, so `dark_high_mid_ratio:
    # low` (or a YAML null, or a list) raised out of `analyze_mix_issues`
    # — which this same change made polish_album stage 1 and
    # polish_audio's auto-run depend on — instead of warn-and-defaulting
    # like every sibling resolver already did.
    dark = coerce_yaml_float(
        analyzer.get("dark_high_mid_ratio", 0.10),
        default=0.10,
        context="analyzer.dark_high_mid_ratio",
    )
    harsh = coerce_yaml_float(
        analyzer.get("harsh_high_mid_ratio", 0.25),
        default=0.25,
        context="analyzer.harsh_high_mid_ratio",
    )
    # `bool(...)` treated any non-empty string as truthy, so a quoted
    # `adm_aware_excitation: "false"` silently enabled the flag it was
    # writing to disable (#556) — the same class of bug #388/#553 already
    # fixed for other boolean gates.
    adm_aware = coerce_yaml_bool(
        analyzer.get("adm_aware_excitation", False),
        default=False,
        context="adm_aware_excitation",
    )
    return dark, harsh, adm_aware


def _build_analyzer(
    dark_ratio: float = 0.10,
    harsh_ratio: float = 0.25,
    adm_aware_excitation: bool = False,
) -> Callable[..., dict[str, Any]]:
    """Return an `analyze_one` callable bound to the given thresholds.

    The returned callable takes raw numpy audio data and produces the
    per-file/per-stem analysis dict. Splitting it out of
    `analyze_mix_issues` lets tests exercise the logic without mounting
    an album directory.

    Args:
        dark_ratio: high_mid_ratio below which ``already_dark`` fires.
        harsh_ratio: high_mid_ratio above which ``harsh_highmids`` fires.
        adm_aware_excitation: When True, dark-classified stems receive an
            ``excitation_db`` recommendation sourced from the stem's
            ``excitation_db_when_dark`` preset field. Defaults to False so
            existing behavior is unchanged unless the preset opts in.

    Returns:
        Callable ``analyze_one(data, rate, *, filename, stem_name, genre)``
        producing a per-file analysis dict identical in shape to the
        original ``_analyze_one`` output.
    """
    import numpy as np
    from scipy import signal as sig

    def analyze_one(
        data: Any,
        rate: int,
        *,
        filename: str,
        stem_name: str | None = None,
        genre: str = "",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"filename": filename, "issues": [], "recommendations": {}}

        # #401: zero-length audio has no samples to reduce — np.max / np.mean
        # over an empty array raises ValueError, which would abort the whole
        # analyze/polish run with a raw traceback. Return a structured
        # per-file error so a single malformed WAV is skipped, not fatal.
        if len(data) == 0:
            result["issues"].append("empty_audio")
            result["error"] = "empty audio: WAV has 0 samples"
            return result

        # Overall metrics
        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data ** 2)))
        result["peak"] = peak
        result["rms"] = rms

        # #553: mirror the polish silence gate. `mix_track_stems` skips a
        # stem whose peak falls under `silence_gate_dbfs` — Suno Auto
        # Split returns every requested category, and the ones with no
        # source content come back as a ~-55 dBFS noise floor. Analyzing
        # that floor produced click counts and recommendations for a stem
        # polish would never touch (~600 false-positive "clicks" on one
        # silent percussion stem), so the two halves of the pipeline
        # disagreed about whether the stem existed at all. Same threshold
        # source, same verdict. Only the stems path is gated: the
        # full-mix fallback has no such skip.
        if stem_name and np.isfinite(peak):
            gate_dbfs = _resolve_silence_gate_dbfs(stem_name, genre)
            peak_dbfs = 20.0 * np.log10(peak) if peak > 0.0 else float("-inf")
            if peak_dbfs < gate_dbfs:
                result["skipped_empty"] = True
                result["peak_dbfs"] = round(peak_dbfs, 1)
                result["issues"] = ["skipped_empty"]
                return result

        # Noise floor estimate (quietest 10% of signal). #402: buffers
        # shorter than 10 samples make the //10 slice empty, and np.mean of
        # an empty slice is NaN (with a RuntimeWarning). Emit None as a
        # sentinel instead so the value computes cleanly and serializes to
        # JSON null rather than the invalid token NaN.
        abs_signal = np.abs(data[:, 0])
        sorted_abs = np.sort(abs_signal)
        quietest = sorted_abs[:len(sorted_abs) // 10]
        noise_floor = float(np.mean(quietest)) if quietest.size else None
        result["noise_floor"] = noise_floor
        if noise_floor is not None and noise_floor > 0.005:
            result["issues"].append("elevated_noise_floor")
            result["recommendations"]["noise_reduction"] = min(0.8, noise_floor * 100)

        # Spectral analysis
        freqs, psd = sig.welch(data[:, 0], rate, nperseg=min(4096, len(data)))

        # Low-mid energy (150-400 Hz) — muddiness indicator
        low_mid_mask = (freqs >= 150) & (freqs <= 400)
        total_energy = float(np.sum(psd))
        if total_energy > 0:
            low_mid_ratio = float(np.sum(psd[low_mid_mask])) / total_energy
            result["low_mid_ratio"] = low_mid_ratio
            if low_mid_ratio > 0.35:
                result["issues"].append("muddy_low_mids")
                result["recommendations"]["mud_cut_db"] = -3.0

        # High-mid energy (2-5 kHz) — harshness / darkness indicator
        high_mid_mask = (freqs >= 2000) & (freqs <= 5000)
        if total_energy > 0:
            high_mid_ratio = float(np.sum(psd[high_mid_mask])) / total_energy
            result["high_mid_ratio"] = high_mid_ratio
            if high_mid_ratio > harsh_ratio:
                result["issues"].append("harsh_highmids")
                result["recommendations"]["high_tame_db"] = -2.0
            elif high_mid_ratio < dark_ratio:
                # #336: already-dark track — emit sentinel 0.0 to override
                # genre-default high-shelf cuts (e.g. electronic's
                # synth/keyboard/other stems at -1.5 dB @ 9 kHz) that
                # would compound the darkness in polish.
                result["issues"].append("already_dark")
                result["recommendations"]["high_tame_db"] = 0.0
                if adm_aware_excitation:
                    # Pull the per-stem target through the shared
                    # resolver so `defaults:` AND `genres.<g>:` scopes
                    # both apply, and an unreadable value warns instead
                    # of raising (#556 round 3). Falls back to 2.0 dB as
                    # a safe mid-ground when no preset declares one.
                    # Drums and bass keep 0.0 (their
                    # excitation_db_when_dark preset field is 0.0).
                    preset_excitation = _resolve_excitation_db_when_dark(
                        stem_name, genre,
                    )
                    if preset_excitation > 0:
                        result["recommendations"]["excitation_db"] = preset_excitation

        # Click detection (sudden amplitude spikes).
        #
        # Count 10 ms windows whose peak-to-RMS ratio exceeds `peak_ratio`
        # — genuine digital clicks are single-sample discontinuities that
        # spike a short window's crest factor well above 10x, while
        # musical transients distribute energy across the window and stay
        # below. The previous sample-wise detector was replaced in #323.
        mono_col = data[:, 0]
        window = max(int(rate * 0.01), 1)
        n_windows = len(mono_col) // window
        if n_windows > 0:
            windows = mono_col[: n_windows * window].reshape(n_windows, window)
            win_rms = np.sqrt(np.mean(windows ** 2, axis=1))
            win_peak = np.max(np.abs(windows), axis=1)
            active = win_rms > 1e-8
            ratios = np.zeros(n_windows, dtype=np.float64)
            np.divide(win_peak, win_rms, out=ratios, where=active)
            peak_ratio = _resolve_analyzer_peak_ratio(stem_name, genre)
            click_count = int(np.sum(ratios > peak_ratio))
            result["click_count"] = click_count
            if click_count > 10:
                result["issues"].append("clicks_detected")
                result["recommendations"]["click_removal"] = True

        # Sub-bass rumble (< 30 Hz)
        sub_mask = freqs < 30
        if total_energy > 0:
            sub_ratio = float(np.sum(psd[sub_mask])) / total_energy
            result["sub_ratio"] = sub_ratio
            if sub_ratio > 0.15:
                result["issues"].append("sub_rumble")
                result["recommendations"]["highpass_cutoff"] = 35

        if not result["issues"]:
            result["issues"].append("none_detected")

        return result

    return analyze_one


async def analyze_mix_issues(
    album_slug: str,
    genre: str = "",
) -> str:
    """Analyze audio files for common mix issues and recommend settings.

    Scans WAV files for noise floor, muddiness (low-mid energy), harshness
    (high-mid energy), clicks, and stereo issues. Returns per-track diagnostics
    with recommended mix-engineer settings.

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Optional genre preset (e.g. "electronic"). Routed through
            the same resolver the polish processors use so click counts
            match what polish will actually remove (#323 follow-up).
            Defaults to the album's own genre (looked up from state) when
            omitted, so it agrees with what a same-genre polish_audio
            call would resolve; an explicit value always wins. (#556)

    Returns:
        JSON with per-track analysis, detected issues, and recommendations
    """
    dep_err = _helpers._check_mixing_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # #556: same genre defaulting as polish_audio — an omitted genre is
    # looked up from the album's state entry so the analyzer and polish
    # stages of one polish_album run cannot resolve different
    # genre-scoped settings. Explicit genre always wins; a derivation
    # failure leaves genre empty, matching today's no-genre behavior.
    genre_was_explicit = bool(genre)
    if not genre:
        genre = _helpers._derive_album_genre(album_slug)

    import numpy as np
    import soundfile as sf

    # Re-read `{overrides}/mix-presets.yaml` on the way in, exactly as
    # `mix_track_stems` / `mix_track_full` do (#553). Both per-stem
    # resolvers below (`_resolve_analyzer_peak_ratio`,
    # `_resolve_silence_gate_dbfs`) go through `_get_stem_settings`,
    # which reads the module-global snapshot — so without this a
    # mid-session override edit was visible to polish and invisible to
    # analyze, and the two halves of one `polish_album` run disagreed
    # about which stems are empty and what click threshold applies.
    from tools.mixing.mix_tracks import _refresh_mix_presets
    _refresh_mix_presets()

    loop = asyncio.get_running_loop()

    source_dir = _find_wav_source_dir(audio_dir)
    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])

    # If no root WAVs, check stems/ for per-track directories and analyze
    # every stem in each track (per-stem diagnostics).
    #
    # CRITICAL: key the per-stem analyses by the CANONICAL STEM_NAMES
    # category (vocals, drums, ...) — not by the raw WAV filename stem.
    # polish's `mix_track_stems` looks up `analyzer_recs[stem_name]` where
    # stem_name is the canonical category from `discover_stems`. If the
    # analyzer stored keys by filename stem (e.g. "01-Vocals"), polish
    # would never match the lookup and `overrides_applied` would be empty
    # even when the analyzer emitted recommendations (including the
    # excitation_db rec that fixes dark-material ADM casualties).
    stems_mode = False
    # Per-track categorized stem list: (track_name, [(category, path), ...])
    stem_track_map: list[tuple[str, list[tuple[str, Path]]]] = []
    if not wav_files:
        stems_dir = audio_dir / "stems"
        if stems_dir.is_dir():
            from tools.mixing.mix_tracks import discover_stems
            track_dirs = sorted([d for d in stems_dir.iterdir() if d.is_dir()])
            for td in track_dirs:
                categorized = discover_stems(td)
                if not categorized:
                    continue
                # Flatten: for each category, take the first file (multi-file
                # categories like multiple drum stems share one analysis —
                # polish combines them during processing).
                entries: list[tuple[str, Path]] = []
                for category, paths in categorized.items():
                    path_list = [paths] if isinstance(paths, str) else list(paths)
                    if path_list:
                        entries.append((category, Path(path_list[0])))
                if entries:
                    stem_track_map.append((td.name, entries))
            if stem_track_map:
                stems_mode = True

    if not wav_files and not stem_track_map:
        return _safe_json({"error": f"No WAV files found in {audio_dir}"})

    # Resolve analyzer thresholds once per run (preset-configurable, #336).
    dark_ratio, harsh_ratio, adm_aware = _resolve_analyzer_thresholds()
    analyze_core = _build_analyzer(
        dark_ratio=dark_ratio,
        harsh_ratio=harsh_ratio,
        adm_aware_excitation=adm_aware,
    )

    def _analyze_one(
        wav_path: Path, stem_name: str | None = None,
    ) -> dict[str, Any]:
        data, rate = sf.read(str(wav_path))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])
        return analyze_core(
            data, rate, filename=wav_path.name,
            stem_name=stem_name, genre=genre,
        )

    track_analyses: list[dict[str, Any]] = []
    if stems_mode:
        for track_name, stem_entries in stem_track_map:
            stems_result: dict[str, dict[str, Any]] = {}
            track_issues: set[str] = set()
            for category, stem_wav in stem_entries:
                # Pass the CATEGORY as stem_name so _analyze_one's
                # MIX_PRESETS["defaults"][stem_name] lookup finds the
                # per-stem config (e.g. vocals → excitation_db_when_dark
                # 2.5, drums → 0.0) instead of falling back to defaults.
                analysis = await loop.run_in_executor(
                    None, _analyze_one, stem_wav, category,
                )
                stems_result[category] = analysis
                track_issues.update(
                    i for i in analysis["issues"] if i not in _NON_ISSUE_TAGS
                )
            track_analyses.append({
                "track": track_name,
                "stems": stems_result,
                "issues": sorted(track_issues) if track_issues else ["none_detected"],
            })
    else:
        for wav_file in wav_files:
            analysis = await loop.run_in_executor(None, _analyze_one, wav_file)
            track_analyses.append(analysis)

    # Album-level summary
    all_issues: set[str] = set()
    for a in track_analyses:
        all_issues.update(i for i in a["issues"] if i not in _NON_ISSUE_TAGS)

    return _safe_json({
        "tracks": track_analyses,
        "album_summary": {
            "tracks_analyzed": len(track_analyses),
            "common_issues": sorted(all_issues),
            "audio_dir": str(audio_dir),
            "source_mode": "stems" if stems_mode else "full_mix",
            # #556 round 3: report the genre this run actually resolved.
            # Now that it can be derived rather than passed, the value
            # governing every threshold here was otherwise invisible to
            # the caller — and its only other signal is a log line the
            # process-global warn-once dedup suppresses on a second run.
            "genre": genre or None,
            "genre_source": (
                None if not genre
                else "explicit" if genre_was_explicit else "derived"
            ),
        },
    })


async def polish_album(
    album_slug: str,
    genre: str = "",
) -> str:
    """End-to-end mix polish pipeline: analyze, polish stems, verify.

    Runs 3 sequential stages:
        1. Analyze — scan for mix issues and recommend settings
        2. Polish — process stems (or full mixes) with appropriate settings
        3. Verify — run full qc_track suite (format, mono, phase, clipping,
           truepeak, clicks, silence, spectral) on polished output

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset for stem-specific settings. Defaults to the
            album's own genre (looked up from state) when omitted; an
            explicit value always wins. Analyze and polish always resolve
            the SAME effective genre — stage 1 uses it directly, and
            stage 2 either gets it directly or (for a DERIVED genre with
            no mix-preset section) gets forwarded "" so it re-derives and
            reaches the identical result via its own logic; either way
            the two stages cannot disagree. A DERIVED genre unrecognized
            by the mix presets is not an error and is not dropped — it's
            logged and used as-is (settings resolution already tolerates
            it). An EXPLICIT unrecognized genre still fails the polish
            stage. (#556)

    Returns:
        JSON with per-stage results, settings, and recommendations
    """
    dep_err = _helpers._check_mixing_deps()
    if dep_err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "failed_stage": "pre_flight",
            "failure_detail": {"reason": dep_err},
        })

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "failed_stage": "pre_flight",
            "failure_detail": json.loads(err),
        })
    assert audio_dir is not None

    stages: dict[str, Any] = {}

    # #556: resolve genre once, up front — an explicit genre always
    # wins; an omitted one is derived from the album's state entry (and,
    # since round 2, no longer validated/blanked here — see the stage-2
    # call below for why). `genre` is used as-is for stage 1 and for
    # stage 3's QC guard. A derivation failure leaves genre empty,
    # matching today's no-genre behavior.
    genre_was_explicit = bool(genre)
    if not genre:
        genre = _helpers._derive_album_genre(album_slug)

    # Determine mode: stems or full mix
    stems_dir = audio_dir / "stems"
    use_stems = stems_dir.is_dir() and any(stems_dir.iterdir())

    stages["pre_flight"] = {
        "status": "pass",
        "audio_dir": str(audio_dir),
        "mode": "stems" if use_stems else "full_mix",
        "stems_dir": str(stems_dir) if use_stems else None,
    }

    # --- Stage 1: Analysis ---
    # #556: forward genre so stage 1 resolves the same genre-scoped
    # analyzer settings (e.g. click_peak_ratio) that stage 2's polish
    # will use — previously this call dropped genre entirely, so the two
    # stages of one run could disagree.
    analysis_json = await analyze_mix_issues(album_slug, genre)
    analysis = json.loads(analysis_json)

    if "error" in analysis:
        stages["analysis"] = {"status": "fail", "detail": analysis["error"]}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "analysis",
            "stages": stages,
            "failed_stage": "analysis",
            "failure_detail": analysis,
        })

    stages["analysis"] = {
        "status": "pass",
        "tracks_analyzed": analysis["album_summary"]["tracks_analyzed"],
        "common_issues": analysis["album_summary"]["common_issues"],
    }

    # --- Stage 2: Polish ---
    # #336: pass the analysis-stage output into polish so analyzer
    # recommendations become per-track overrides (no duplicate analysis
    # run — polish_audio would otherwise re-invoke analyze_mix_issues).
    #
    # #556 round 2: an explicit genre is forwarded unchanged. A DERIVED
    # genre is forwarded unchanged too UNLESS it has no mix-preset
    # section — in that one case, "" is forwarded instead, so
    # polish_audio re-derives it internally (identical state, identical
    # result) and — critically — correctly resolves its OWN
    # genre_was_explicit to False, applying its informational (not
    # hard-error) treatment. polish_audio cannot otherwise tell a
    # derived-and-forwarded genre apart from one a caller actually
    # typed, since both arrive as the same plain non-empty argument;
    # forwarding the concrete value here would trip its hard "Unknown
    # genre" error over a fact about the album's own state entry.
    #
    # #556 round 3: the blanking condition narrowed. polish_audio now
    # hard-errors an explicit genre only when it is unknown to BOTH
    # preset sets, so a derived genre that merely lacks a mix section
    # survives being forwarded verbatim. Only a derived genre unknown to
    # both sets — an album whose recorded genre matches nothing at all —
    # still needs the "" hand-off to reach polish_audio's informational
    # path instead of its typo error.
    if genre_was_explicit:
        polish_stage_genre = genre
    else:
        polish_stage_genre = genre
        if genre and not _helpers._genre_known_anywhere(genre):
            polish_stage_genre = ""

    polish_json = await polish_audio(
        album_slug=album_slug,
        genre=polish_stage_genre,
        use_stems=use_stems,
        dry_run=False,
        analyzer_results=analysis,
    )
    polish = json.loads(polish_json)

    if "error" in polish:
        stages["polish"] = {"status": "fail", "detail": polish["error"]}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "polish",
            "stages": stages,
            "failed_stage": "polish",
            "failure_detail": polish,
        })

    stages["polish"] = {
        "status": "pass",
        "tracks_processed": polish["summary"]["tracks_processed"],
        "output_dir": polish["summary"]["output_dir"],
        "overrides_applied": polish["summary"].get("overrides_applied", []),
        # #556 round 3: surface the genre the polish stage actually used
        # (polish_audio echoes it in its own settings block, which this
        # cherry-pick used to discard).
        "genre": polish.get("settings", {}).get("genre"),
    }

    # --- Stage 3: Verify polished output (full QC suite) ---
    from tools.mastering.qc_tracks import qc_track

    polished_dir = audio_dir / "polished"
    if not polished_dir.is_dir():
        stages["verify"] = {"status": "fail", "detail": "polished/ directory not found"}
        return _safe_json({
            "album_slug": album_slug,
            "stage_reached": "verify",
            "stages": stages,
            "failed_stage": "verify",
        })

    polished_files = sorted([
        f for f in polished_dir.iterdir()
        if f.suffix.lower() == ".wav"
    ])

    loop = asyncio.get_running_loop()
    qc_genre = genre or None
    if qc_genre is not None:
        # #556: qc_track raises ValueError for a genre its own
        # mastering-preset set doesn't recognize — a derived (or
        # user-override-added mix-only) genre reaching this stage used
        # to crash verify mid-run instead of failing structurally. The
        # mix and mastering genre-preset sets are independent, so a
        # genre valid on the mix side is not guaranteed valid here; warn
        # and QC genre-less rather than let the exception propagate out
        # of run_in_executor.
        #
        # #556 round 2 checked `master_tracks.GENRE_PRESETS` — the
        # import-time snapshot — because a guard reading the fresh
        # loader could pass while the stale-reading code underneath
        # still raised. Round 3 removes the split at its source:
        # `qc_track` now calls `refresh_genre_presets()` at its entry, so
        # the snapshot it reads is the file as it is on disk now, and
        # the fresh loader is the correct thing to validate against.
        from tools.mastering.master_tracks import load_genre_presets
        if qc_genre.lower() not in load_genre_presets():
            # #556 round 3: report the genre's real origin. This guard is
            # reached by an EXPLICIT genre too — one the caller typed
            # that the mix set recognizes and the mastering set does not
            # — and round 2 logged every case as DERIVED, pointing the
            # reader at the album's state entry instead of the argument
            # they passed.
            _helpers._warn_unknown_genre_for_qc(
                qc_genre, album_slug,
                preset_kind="mastering",
                was_explicit=genre_was_explicit,
            )
            qc_genre = None
    verify_results = []

    # Pre-master verify skips `truepeak` and `clicks`. Polished audio is
    # un-limited so peaks legitimately sit above the streaming ceiling
    # until mastering applies its limiter; genre-dense-transient stems
    # (kicks, snares) legitimately trip the click detector until the
    # full mix is mastered. Those checks are gates at post-master QC,
    # not pre-master. (Matches `_stage_pre_qc` in `_album_stages.py`.)
    VERIFY_CHECKS = ["format", "mono", "phase", "clipping", "silence", "spectral"]
    for wav in polished_files:
        result = await loop.run_in_executor(
            None, qc_track, str(wav), VERIFY_CHECKS, qc_genre
        )
        verify_results.append(result)

    failed = [r["filename"] for r in verify_results if r["verdict"] == "FAIL"]
    warned = [r["filename"] for r in verify_results if r["verdict"] == "WARN"]

    qc_warnings: list[str] = []
    for r in verify_results:
        for check_name, check_info in r["checks"].items():
            if check_info["status"] in ("WARN", "FAIL"):
                qc_warnings.append(
                    f"{r['filename']}: {check_name} {check_info['status']} — {check_info['detail']}"
                )

    if failed:
        verify_status = "fail"
    elif warned:
        verify_status = "warn"
    else:
        verify_status = "pass"

    stages["verify"] = {
        "status": verify_status,
        "tracks_verified": len(verify_results),
        "checks_run": VERIFY_CHECKS,
        "checks_deferred_to_post_master": ["truepeak", "clicks"],
        "failed_tracks": failed,
        "warned_tracks": warned,
        "qc_issues": qc_warnings,
    }

    return _safe_json({
        "album_slug": album_slug,
        "stage_reached": "complete",
        "stages": stages,
        "analysis": analysis.get("tracks"),
        "polish": polish.get("tracks"),
        "next_step": f"master_audio('{album_slug}', source_subfolder='polished')",
    })


async def polish_and_master_album(
    album_slug: str,
    genre: str = "",
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float | None = None,
    cut_highs: float | None = None,
) -> str:
    """Combined polish + master pipeline in a single call.

    Runs polish_album() to clean up Suno audio, then master_album() with
    source_subfolder="polished" to produce streaming-ready masters. Stops
    on failure at either stage and returns the combined stage results.

    Use the individual tools when you need granular control (e.g., re-polish
    with different settings, re-master without re-polishing).

    Args:
        album_slug: Album slug (e.g., "my-album")
        genre: Genre preset for both polish and master stages. Defaults to
            the album's own genre (looked up from state) when omitted;
            resolved once here. The mix and mastering genre-preset sets
            are independent, so a DERIVED genre unrecognized by one
            preset set is handled per-phase: on the mix side it's kept
            and used as-is (logged, not an error — settings resolution
            already tolerates it); on the master side it's logged and
            that phase proceeds without a genre preset instead, since
            `master_album` validates strictly with no such tolerance.
            Either way both phases still apply it where it IS
            recognized. An explicit value always wins and is forwarded
            to both phases unchanged (#556); an explicit value
            unrecognized by either phase still fails that phase's
            existing validation.
        target_lufs: Mastering target integrated loudness (default: -14.0)
        ceiling_db: Mastering true peak ceiling in dB (default: -1.0)
        cut_highmid: High-mid EQ cut in dB at 3.5kHz (e.g., -2.0). Omit
            (None) to use the genre preset's cut; pass 0 or 0.0
            explicitly to disable the cut regardless of genre. Forwarded
            to `master_album` unchanged.
        cut_highs: High shelf cut in dB at 8kHz. Same omit-vs-explicit-0
            semantics as cut_highmid: None uses the genre preset, an
            explicit 0/0.0 disables it.

    Returns:
        JSON with combined polish and master stage results
    """
    from handlers.processing.audio import master_album

    # #556: resolve genre once, up front — explicit wins; otherwise
    # derive from the album's state entry. Each phase below validates it
    # against its OWN preset set independently: mix presets and
    # mastering presets are separate files with separate genre lists, so
    # a genre known to one and not the other is a real, expected case,
    # not a bug — see the "custom-genre" example in the #556 CHANGELOG
    # entry.
    genre_was_explicit = bool(genre)
    if not genre:
        genre = _helpers._derive_album_genre(album_slug)

    # #556 round 2: mirrors polish_album's own stage-2 forwarding logic
    # (see there for the full rationale) — an explicit genre is
    # forwarded unchanged; a DERIVED genre is forwarded unchanged too
    # UNLESS it has no mix-preset section, in which case "" is forwarded
    # instead so polish_album re-derives it internally and correctly
    # resolves its OWN genre_was_explicit to False. Forwarding the
    # concrete value here for a mix-unknown DERIVED genre would make
    # polish_album (and, inside it, polish_audio) treat it as if a
    # caller had typed it — round 1's actual bug, which blanked the
    # genre in a way that made analyze_mix_issues (never blanked) and
    # the real polish processing (blanked) disagree about a state genre
    # neither of them was told to distrust.
    #
    # #556 round 3: same narrowing as polish_album's stage-2 forwarding.
    # The "" hand-off is only needed for a derived genre unknown to BOTH
    # preset sets; one that merely lacks a mix section is forwarded
    # verbatim now that polish_audio no longer errors on it.
    if genre_was_explicit:
        polish_genre = genre
    else:
        polish_genre = genre
        if genre and not _helpers._genre_known_anywhere(genre):
            polish_genre = ""

    polish_json = await polish_album(album_slug=album_slug, genre=polish_genre)
    polish_result = json.loads(polish_json)

    if polish_result.get("failed_stage"):
        return _safe_json({
            "album_slug": album_slug,
            "phase": "polish",
            "phase_reached": "polish",
            "failed_phase": "polish",
            "polish": polish_result,
        })

    # #556 round 3: the master phase does NOT receive a derived genre.
    #
    # Round 2 forwarded the derived genre here, which quietly changed
    # what a plain `polish_and_master_album(album_slug)` call produces:
    # a genre preset sets `target_lufs` and EQ cuts, so an album filed
    # under e.g. `post-rock` went from -14.0 LUFS with no EQ to -16.0
    # LUFS with a -1.5 dB high-mid cut, purely from omitting an argument
    # that had never been required. Because `genre=""` is
    # indistinguishable from omission (`genre_was_explicit = bool(genre)`),
    # there was also no way left to ask for genre-less mastering at all.
    #
    # #556 §3 asked for inference on the POLISH side — so that
    # `genre_scoped` mix overrides apply without passing the argument on
    # every call. It did not ask for mastering LUFS/EQ to change. The
    # derived genre therefore stays scoped to polish; mastering keeps its
    # pre-#556 contract of "trust exactly what's given", and an explicit
    # genre still reaches it unchanged.
    #
    # This also removes the fresh-vs-stale preset hazard that the round-2
    # guard here carried: it validated against a fresh
    # `load_genre_presets()` while the code it protected (`qc_track` ->
    # `_resolve_click_thresholds`) reads the `GENRE_PRESETS` snapshot.
    # Nothing derived reaches the mastering side now, and the snapshot
    # itself is refreshed at the mastering entry points (see
    # `master_tracks.refresh_genre_presets`, #556 round 3).
    master_genre = genre if genre_was_explicit else ""

    master_json = await master_album(
        album_slug=album_slug,
        genre=master_genre,
        target_lufs=target_lufs,
        ceiling_db=ceiling_db,
        cut_highmid=cut_highmid,
        cut_highs=cut_highs,
        source_subfolder="polished",
    )
    master_result = json.loads(master_json)

    failed = bool(master_result.get("failed_stage"))
    return _safe_json({
        "album_slug": album_slug,
        "phase_reached": "master" if not failed else f"master:{master_result.get('failed_stage')}",
        "failed_phase": "master" if failed else None,
        "polish": polish_result,
        "master": master_result,
    })


def register(mcp: Any) -> None:
    """Register mix polish tools."""
    mcp.tool()(polish_audio)
    mcp.tool()(analyze_mix_issues)
    mcp.tool()(polish_album)
    mcp.tool()(polish_and_master_album)
