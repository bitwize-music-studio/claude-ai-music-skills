# Changelog

All notable changes to claude-ai-music-skills.

This project uses [Conventional Commits](https://conventionalcommits.org/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `fix_dynamic` iterates up to 3 times to reach target LUFS,
  returning `converged` and `iterations_run` in metrics.
- `_stage_verification` emits `VERIFICATION_WARNINGS.md` sidecar and
  downgrades to `status: "warn"` when auto-recovery exhausts
  iterations. Pipeline continues instead of halting.
- **`/bitwize-music:promote-idea` skill + `promote_idea` MCP tool (#328)**: One-shot conversion of a `Pending` idea from `IDEAS.md` into a full album project. Auto-derives the album slug from the idea title (lowercase, ASCII-only, diacritics stripped, apostrophes elided, non-alphanumeric → hyphen) or accepts an explicit override. Calls `create_album_structure` with the idea's genre, injects the idea's `**Concept**` text into the new album `README.md` under a `## Concept` section, advances idea status `Pending → In Progress`, and adds a `**Promoted To**: <slug>` back-link in `IDEAS.md`. Distinct errors for missing idea, already-promoted idea, missing/invalid genre, and duplicate album slug. `documentary=True` flag mirrors `new-album` behavior (creates `RESEARCH.md` + `SOURCES.md`). The state indexer now also extracts `concept` and `promoted_to` fields from `IDEAS.md` so downstream tools can read the concept without re-parsing the markdown.
- **Genre-aware silence QC thresholds**: new `silence_leading_max_s` / `silence_trailing_max_s` preset fields (`tools/mastering/genre-presets.yaml`). Defaults 0.5 / 3.0 s. `electronic` and `edm` override `silence_leading_max_s: 1.5` so filter-sweep / build intros don't FAIL the silence gate. (#323 comment)
- **Click removal on every stem polish chain**: `vocals`, `backing_vocals`, `bass`, `synth`, `guitar`, `keyboard`, `strings`, `brass`, `woodwinds`, `other` now run click removal as the first step (was drums / percussion only). Shared `_apply_click_removal` helper standardizes the detector across all chains — `click_peak_ratio: 15.0` default matches the analyzer in `analyze_mix_issues` so polish and analysis report the same events. Genre presets (e.g. `electronic: 10.0`) overlay the default per-genre. Drum / percussion chains kept `cubic` repair (better spectral reconstruction on isolated transients); harmonic stems use `linear` repair (safer on dense mix content and vocal consonants). `mix_track_stems` dispatch unified — every processor now accepts `report` and surfaces `clicks_removed`. (#323 comment)
- `ctx.track_ceilings`, `ctx.dark_tracks`, `ctx.remaster_filenames`
  on `MasterAlbumCtx` — per-track ADM tightening state.
- `is_dark` field on `analyze_track` output (`band_energy['high_mid']
  < 10 %`).
- `ADM_VALIDATION.md` sidecar now includes `dark_casualties`,
  `tightened_tracks`, and per-track final `track_ceilings` in the
  adm_validation stage output.

### Fixed
- Auto-recovery path now writes at `output_sample_rate` (was using
  source rate, so 48 kHz polished sources produced mastered files
  at 48 kHz while the rest of the album was 96 kHz).
- `master_album` halting at `verification` when track-level auto-recovery
  couldn't converge. The docstring promised warn-fallback; the
  implementation now delivers it.
- **`master_album` status_update stage no longer brittle on re-masters (#335)**: The stage previously only promoted tracks from `Generated → Final` and appended a "Skipped: expected Generated" error for any other starting status. Combined with a hardcoded `status: "pass"` report this silently no-op'd the entire stage on any re-master of an album whose tracks weren't pinned at exactly `Generated` (Not Started, Sources Pending, Sources Verified, In Progress, Released — all hit this). The stage now promotes any non-terminal status (`Not Started`, `Sources Pending`, `Sources Verified`, `In Progress`, `Generated`) to `Final` because the mastered WAV is real and status should follow. `Final` and `Released` are left alone as terminal states; `Released` specifically is never demoted back to `Final` on a re-master. Tracks with an empty `path` (cache-staleness, no disk file) are now silently skipped instead of appending an error. Stage outcome is now classified honestly: `pass` when clean or idempotent, `partial` when some updates succeeded and some errors exist, `skipped` when nothing updated AND errors exist (was always `pass` before, masking real failures).
- **`/bitwize-music:lyric-refiner` no longer blocks on instrumental-mixed albums (#311)**: The refiner's former guard clause — "Track status `Not Started` or `Sources Pending` → error" — fired on any non-ready vocal track and stopped the whole run, even when other tracks were refineable. Replaced with a three-bucket triage (instrumental / not-ready / refineable): non-refineable tracks are silently skipped with a one-line note (`Skipping {track} — instrumental` or `Skipping {track} — no lyrics yet ({status})`), and the refiner processes whatever is left. Zero-refineable is now a clean informational exit, not a guard-clause failure. Added explicit `### Instrumental Guard` section to match the convention shared with `lyric-writer` / `lyric-reviewer` / `pronunciation-specialist`, and extended the `TestInstrumentalGuard.test_instrumental_guard_section` parametrize to cover `lyric-refiner`. Report header now shows both skip counters: `X of Y (Z instrumental skipped, W Not Started skipped)`.
- **qc_audio silence check (#321)**: Trailing silence followed by a sub-threshold noise-floor blip no longer gets misclassified as an internal gap. The silence detector now classifies each silent region by position AND by the amount of non-silent content between the region and the file edge — a region ending within 1s of the file end (with <300ms of non-silent content after it) counts as trailing, not internal. Unblocks the `master_album` / `polish_album` pre-QC gate on tracks with natural fade-outs.
- **analyze_mix_issues click detection (#323)**: Replaced the sample-wise `|diff| > 6·σ(diff)` detector with a windowed peak-to-RMS check (matches `qc_tracks._check_clicks`) at `peak_ratio=15` over 10 ms windows. The old detector flagged tens of thousands of "clicks" on every clean vocal, bass, and synth stem (vocal consonants and synth attacks have high instantaneous derivatives but spread their energy across a window), emitting `click_removal: true` recommendations that the polish pipeline silently ignored. The analyzer now only recommends click removal when genuine single-sample discontinuities exist.

### Changed
- `master_album` docstring enumerates halt vs warn-fallback
  conditions explicitly.
- **Logger names standardized to `__name__` (#268)**: All 12 MCP server modules that used `logging.getLogger("bitwize-music-state")` now use `logging.getLogger(__name__)`, giving hierarchical logger names (e.g., `handlers.processing.audio`) so operators can filter logs by module/subpackage. Affected: `server.py`, `handlers/{core,database,gates,maintenance,text_analysis}.py`, `handlers/processing/{audio,video,mixing,sheet_music,_album_stages,_helpers}.py`. Six `caplog` assertions in the test suite updated to reference the new module-hierarchical logger names.
- **Dense-transient genre click QC thresholds bumped** to match `idm`'s calibration (`click_peak_ratio: 10.0`, `click_fail_count: 30`, was 8.0/15). Applies to `electronic`, `edm`, `techno`, `drum-and-bass`, `jungle`, `dubstep`, `hardstyle`, `breakbeat`, `metal`, `industrial`, `trap`, `drill`, `phonk`, `grime`, `shoegaze`, `dream-pop`. Prior values were flagging post-polish electronic drum transients as clicks (20+ clicks on a 3-min track → FAIL) even though the hits are musical, not digital pops. (#323 comment)
- **`polish_album` verify stage** now runs a pre-master check subset (`format, mono, phase, clipping, silence, spectral`) and defers `truepeak` / `clicks` to post-mastering QC. Polished audio is un-limited and dense-transient (the limiter is what enforces the ceiling), so failing those checks on pre-master files is a false gate. The stage surfaces `checks_run` and `checks_deferred_to_post_master` for transparency. (#323 comment)
- **`master_album` pre-QC stage** now forwards `genre` to `qc_track` (so genre-preset silence / click thresholds apply) and surfaces `checks_run` / `checks_deferred_to_post_master` in its status output. (#323 comment)
- ADM ceiling tightening is now per-track. A single clipping track
  no longer drags the album-wide ceiling down; clean tracks keep
  their original ceiling regardless of neighbor ADM failures.
- `_stage_mastering` honors `ctx.remaster_filenames` — on ADM retry
  cycles, only clipping non-dark tracks are re-mastered.
- Dark tracks (high_mid band_energy < 10 %) are excluded from ADM
  tightening; their ADM clips route to warn-fallback instead of
  forcing further ceiling reductions.

## [0.90.0] - 2026-04-15

### Added
- **opus_safe TP override (#290)**: `opus_safe: true` preset field applies -1.5 dBTP ceiling for dense-transient genres (EDM, trap, metal, dubstep, drum-and-bass, hardstyle, industrial, punk).
- **ADM validation stage (#290 step 9)**: `master_album` now runs `_stage_adm_validation` after ceiling guard — encodes each mastered WAV to AAC (ffmpeg native `aac` default; afconvert on macOS; `libfdk_aac` via config override), decodes back, checks for inter-sample peaks. Emits `ADM_VALIDATION.md` sidecar. Halts if clips found.
- **ID3v2.4 metadata embedding (#290)**: `master_album` embeds artist, album, title, copyright, and label into mastered WAV delivery files via `tools/mastering/metadata.py`. ISRC and UPC fields are supported by the tool but not yet sourced in the pipeline (follow-up).
- **polish_audio per-stem WAVs (#290)**: Stems mode now writes `polished/<track>/vocals.wav` (and other processed stems) alongside the full mix, activating stem-first vocal-RMS measurement in the mastering analysis.
- **Album-ceiling guard (#290 phase 5, step 8)**: `master_album` now gates
  mastered tracks against `album_median + 2 LU`. Small overshoots (≤0.5 LU)
  get a silent scalar pull-down; larger overshoots halt + escalate.
- **LAYOUT.md emitter (#290 phase 5, step 7)**: `master_album` writes
  `LAYOUT.md` next to `ALBUM_SIGNATURE.yaml` with one transition per
  adjacent track pair. Album-level override via
  `layout.default_transition: gapless` in README frontmatter.
- **Album coherence check + correct (issue #290 phase 3b)** — Two new MCP tools. `album_coherence_check` measures the mastered album, selects an anchor, and classifies every other track against per-genre tolerance bands: LUFS (±0.5 LU), STL-95 (`coherence_stl_95_lu`, default ±0.5 LU), LRA floor (`coherence_lra_floor_lu`, default 1.0 LU minimum), low-RMS (`coherence_low_rms_db`, default ±2.0 dB), vocal-RMS (`coherence_vocal_rms_db`, default ±2.0 dB). Read-only — returns per-track violation lists + a summary with outlier counts broken down by metric. `album_coherence_correct` takes the same check output and re-masters LUFS-outlier tracks from `polished/` into `mastered/` (atomic staging pattern, mirrors `master_album`) with the per-track `target_lufs` overridden to the anchor's **measured** LUFS — chasing real output rather than an idealized preset target guarantees convergence. Supports `dry_run=True` for CI preview. MVP scope: LUFS correction only; STL-95 / LRA / RMS outliers are reported but not auto-corrected (compression-ratio correction comes in a later phase). Four new tolerance fields added to the `defaults:` block in `genre-presets.yaml` (and `_PRESET_DEFAULTS` in `master_tracks.py`).
- **Album signature measurement (issue #290 phase 3a)** — New `measure_album_signature` MCP tool. Runs `analyze_track` on every WAV in an album's subfolder (default `mastered/`), then aggregates into per-track signature metrics (LUFS, peak, STL-95, short-term range, low-RMS, vocal-RMS, 7-band spectral energy) plus album-level aggregates (median, p95, min, max, range, eligible-count). When `genre` or `anchor_track` is supplied, also runs the phase-2 anchor selector and surfaces per-track deltas from the anchor. Read-only — no files written. Intended for tuning genre tolerance presets from reference albums and for feeding the phase-3b coherence check/correct tools. New pure-Python module `tools/mastering/album_signature.py` holds the aggregation + delta math (no I/O, no MCP coupling).
- **Mastering foundation — streaming-grade 24/96 delivery (issue #290 phase 1a, #304)** — New `mastering:` block in `config.example.yaml` documenting streaming-grade defaults (24-bit WAV at 96 kHz, -14 LUFS, -1 dBTP). `master_audio` and `master_album` now consume these defaults via a new `tools/mastering/config.py` loader (`load_mastering_config`, `resolve_mastering_targets`) with precedence: explicit handler arg > genre preset > user config > hardcoded default. Mastering report emits a runtime honesty notice when the resolved `delivery_sample_rate` exceeds the probed source rate ("upsampled from 44.1 kHz source — no additional audio information vs. source"). New opt-in archival output path writes 32-bit float pre-downconvert copies to `{audio_dir}/archival/` when `mastering.archival_enabled: true`; new `prune_archival` MCP tool keeps the N most-recent archival files per album. Optional new config keys `artist.copyright_holder`, `artist.label`, `mastering.adm_aac_encoder` (default `aac`) for downstream metadata embedding and ADM validation phases. `qc_tracks.py` format check expanded to accept 44.1/48/88.2/96/176.4/192 kHz (was 44.1/48 only). Companion issue #303 tracks the full-fidelity metadata embedding story.
- **Realistic audio test fixtures + integration tests** — Added `make_clicks_and_pops`, `make_silent_gaps`, and `make_phase_partial` generators to `tests/fixtures/audio/` for QC paths a sine wave can't exercise (injected DC pops, internal silent gaps, partial phase cancellation). Audio fixtures moved from an unscanned `tests/fixtures/audio/conftest.py` into `tests/conftest.py` so all tests auto-discover them. New `tests/unit/mastering/test_integration_realistic_audio.py` exercises sibilance/tinniness, partial-phase mono fold FAIL, click detection, internal-gap silence FAIL, and LUFS spread across dynamic content. Documented generator catalog and authoring conventions in `tests/fixtures/README.md` (#300)
- **Mastering samples — codec preview + mono fold-down QC artifacts** — `master_album` now writes operator-listening artifacts to a sibling `mastering_samples/` directory after verification, so `mastered/` stays byte-identical to the streaming upload. Each track gets a 128 kbps `.aac.m4a` AAC encode (Bluetooth-path audition), a `.mono.wav` mono fold sample (phone-speaker / Echo audition), and a `.MONO_FOLD.md` per-band delta report. A >6 dB band drop in the mono fold hard-fails the pipeline with the offending frequency surfaced (phase cancellation guard). New standalone tools `render_codec_preview` and `mono_fold_check` run the same checks independently. Thresholds and on/off flags configurable in `genre-presets.yaml` defaults; `reset_mastering` accepts `mastering_samples` (#296)
- **Mastering pipeline overhaul** — 30+ new configurable parameters across the full mastering chain:
  - DC offset removal (subsonic HPF)
  - Low shelf EQ with configurable Q factor
  - Linear-phase FIR EQ option (zero phase distortion)
  - Mid/side EQ for frequency-selective stereo management
  - De-essing with frequency, bandwidth, threshold, and ratio controls
  - Stereo width adjustment with bass mono fold
  - Parallel compression (wet/dry blend) with makeup gain
  - 3-band multiband compression with Linkwitz-Riley crossovers
  - Iterative LRA (Loudness Range) targeting per EBU R128
  - Look-ahead limiting with configurable release
  - Oversampled processing for nonlinear stages (2x/4x)
  - Sample rate conversion
  - 24-bit output support
  - Inter-track gap insertion
  - Album-level loudness consistency (two-pass mastering)
  - Extended loudness metering (short-term, momentary LUFS)
- **Mix pipeline enhancements** — saturation, sub-bass exciter, transient shaping wired into per-stem processing
- **Configurable mastering presets** — refactored from tuples to dicts; all parameters exposed via CLI and genre presets
- **Album signature persistence (#290 phase 4):** `master_album` now writes `ALBUM_SIGNATURE.yaml` alongside `mastered/` after every successful run, capturing the anchor, album medians, delivery targets (LUFS, TP ceiling, LRA), and coherence tolerances. Released albums automatically enter "frozen mode" on re-master — the shipped anchor + targets are reused so subsequent masters don't drift from what's on DSPs.
- **`freeze_signature` / `new_anchor` params on `master_album`** — force frozen or fresh routing regardless of album status. Mutually exclusive; enforced in pre-flight.
- **`is_album_released` helper** in `handlers/_shared.py` for cache-backed status checks.
- **`get_plugin_version` helper** in `handlers/_shared.py` — single source of truth for plugin version reads (DRYed from health.py and master_album's new stage).
- **`reference/streaming-mastering-specs.md`** — new authoritative reference for delivery targets, the signature contract, and re-mastering behavior.

### Changed
- **Stage extraction refactor (#290 D5)**: `master_album` is now a ~60-line orchestrator delegating to 14 standalone stage functions in `handlers/processing/_album_stages.py`. Zero behavior change; enables ADM validation (step 9) to land cleanly.
- **Default mastered output format** — `master_album` / `master_audio` / `polish_and_master_album` now produce **24-bit WAV at 96 kHz** by default (was 16-bit at source rate, typically 44.1 kHz). Existing user configs without a `mastering:` block pick up the new defaults on the next run. To preserve the legacy 16/44.1 output, set `mastering.delivery_bit_depth: 16` and `mastering.delivery_sample_rate: 44100` in `~/.bitwize-music/config.yaml`. Users with custom `{overrides}/mastering-presets.yaml` per-genre values continue to honor those overrides. Disk usage increases ~3x per track at the new defaults (~33 MB vs. ~10 MB for a 3-minute stereo track).

### Fixed
- **Notices on early-exit paths (A4 #290)**: Failure JSON from `master_album` now always includes the `notices` key, even when the pipeline halts before successful completion.
- LRA targeting now iteratively adjusts compression ratio (was measurement-only)
- Added missing `--deess-bandwidth` CLI arg
- Added missing CLI args for multiband ratios/thresholds and mid/side frequencies
- Wired `eq_low_q` through to `apply_low_shelf()` (was defined but unused)
- Look-ahead limiter now hits its target ceiling exactly (was overshooting by ~1 dB on transients). Gain at peak samples was being sampled from the release-relaxed envelope; replaced with a rolling minimum over the lookahead window (#283)
- QC click detector is now genre-aware: `click_peak_ratio` and `click_fail_count` are per-genre preset fields, tuned looser for genres with intentional sharp transients (electronic, IDM, breakcore, trap, metal, glitch, footwork, etc.) so musical transients no longer FAIL QC. `qc_tracks.py` accepts `--genre`, the `qc_audio` MCP tool accepts `genre`, and user `mastering-presets.yaml` overrides still apply (#285)
- Mastering chain now adds a final true-peak guard at the output rate after downsample and SRC. `scipy.signal.resample_poly`'s polyphase FIR has passband ripple that previously reintroduced 0.1–0.9 dB inter-sample peaks above the limiter ceiling; one reactive `limit_peaks()` pass closes that gap so `ceiling_db` is hit within ~0.05 dB without the prior headroom workaround (#286)
- Polish-stage declicker now reads `click_peak_ratio` / `click_fail_count` from
  the mastering genre preset so polish and QC click detection stay aligned.
  Stem passes (drums, percussion) use cubic-spline repair across ±1.5 ms of
  clean neighbors instead of two-sample linear interpolation; full-mix fallback
  keeps linear repair because dense mix content amplifies surgical artifacts.
  Polish results now surface `clicks_removed` per stem and on the full-mix
  result so operators can see whether polish acted (#289).
- `analyze_mix_issues` in stems mode now analyzes every stem per track and reports per-stem diagnostics under `tracks[].stems[stem_name]`, rather than sampling only the alphabetically first stem. Issues in specific stems (muddy bass, harsh vocals, etc.) are no longer missed, and per-track issue rollups are the union across stems (#272)
- **Archival stage now mirrors `mastered/` (#290 phase 4, PR #304 review A5):** orphans whose basename is no longer in `mastered/` are pruned before new files are written, so re-masters with fewer or renamed tracks don't retain stale archival entries. Records pruned names under `stages.archival.pruned`.

## [0.89.0] - 2026-04-10

### Added
- **Lyric-refiner skill** — multi-pass lyric refinement for post-writing polish
- **Tango genre** — Argentine-Uruguayan dance and song tradition covering Golden Age orquestas, tango canción, nuevo tango (Piazzolla), and electrotango; includes mastering presets for bandoneón-centric dynamics

### Fixed
- Updated Opus 4.5 references to Opus 4.6 in model-strategy.md
- Updated Sonnet 4.5 references to Sonnet 4.6 in model-strategy.md
- Fixed README skill count (51 → 52)
- Fixed lyric-refiner skill missing required section heading

## [0.88.0] - 2026-04-08

### Added
- **154 new genres** — massive genre library expansion from 197 to 351 genres, completing all remaining genre expansion issues (#176, #177, #179, #180, #181, #182, #183, #184, #185, #186, #187, #188, #189, #190, #192, #194, #195, #196, #197, #201, #203, #204, #206, #207)
  - Electronic Trance, Hardcore & experimental (13): Vocal Trance, Goa Trance, Psychedelic Trance, Happy Hardcore, Acid Jazz, Dark Ambient, Dub Techno, Glitch, Glitch Hop, Glitch Pop, Moombahton, Neurofunk, Witch House
  - Niche & modern Electronic (8): Chiptune, EBM, Darksynth, Future Funk, Folktronica, Deconstructed Club, Lo-fi House, Hardwave
  - Modern club & Hip-Hop production (8): Jersey Club, Footwork, Baile Funk, Italo Disco, Balearic, G-Funk, Chopped and Screwed, Bounce
  - British movements & UK dance (6): Britpop, Madchester, 2-Step Garage, Bassline, Speed Garage, Broken Beat
  - Jazz & Blues subgenres (12): Bebop, Cool Jazz, Hard Bop, Modal Jazz, Jazz Fusion, Ethio-Jazz, Gypsy Jazz, Nu Jazz, Smooth Jazz, Soul Jazz, Vocal Jazz, Delta Blues, Piano Blues
  - Rock movements & revival (10): Arena Rock, Hair Metal, Heartland Rock, NWOBHM, Jangle Pop, Noise Pop, Post-Britpop, Post-Punk Revival, Psychobilly, Rockabilly
  - Art rock & experimental (8): Canterbury Scene, Dance-Punk, Krautrock, No-Wave, Slowcore, Space Rock, Jam Band, Dark Jazz
  - Metal subgenres (6): Blackgaze, Crossover Thrash, Drone Metal, Melodic Death Metal, Post-Metal, Viking Metal
  - Modern Hip-Hop (7): Abstract Hip-Hop, Emo Rap, Horrorcore, Jazz Rap, Latin Trap, Plugg, Trap Metal
  - Soul, Funk & R&B deep cuts (8): Alternative R&B, Boogie, Doo-Wop, New Jack Swing, Northern Soul, P-Funk, Psychedelic Soul, Quiet Storm, Trap Soul
  - Vocal & A Cappella (4): A Cappella, Barbershop, Choir, Beatboxing
  - Vocal & Choral (2): Gregorian Chant, Vocaloid
  - World & Cultural music (6): Celtic, Klezmer, Polka, Throat Singing, Lounge, Spaghetti Western
  - African music (10): Afropop, Afro-House, Benga, Chimurenga, Gqom, Juju, Kwaito, Maskandi, Mbaqanga, Soukous
  - African deeper cuts (8): Bongo Flava, Champeta, Coupé-Décalé, Desert Blues, Fuji, Gengetone, Kuduro, Mbalax
  - Latin & Caribbean (8): Bachata, Bolero, Calypso, Mambo, Merengue, Soca, Son Cubano, Dembow
  - Caribbean & Latin niche (6): Chicha, Corridos Tumbados, Guaracha, Huayno, Punta, Vallenato
  - Latin American deep cuts (7): Axé, Forró, Kompa, Mento, MPB, Pagode, Banda
  - East & Southeast Asian (6): Anisong, Cantopop, Kayokyoku, Thai Pop, Trot, Visual Kei
  - South Asian & Middle Eastern (10): Carnatic, Dabke, Dangdut, Ghazal, Hindustani, Indian Classical, Laiko, Rai, Shaabi, Sufi
  - European folk & regional pop (10): Chutney, Isicathamiya, Kizomba, Manele, Morna, Norteno, Rebetiko, Sega, Semba, Sevdah, Taarab, Tejano, Turbo Folk, Turkish Pop
  - Remaining Electronic styles (7): Brostep, Cyberpunk, Dark Cabaret, Dark Electro, Deep Techno, Dungeon Synth, Post-Dubstep, Psybient, Rave, Space Disco, UK Funky, Vocal House
- Mastering presets for all 154 new genres in `genre-presets.yaml`
- New `skills/mastering-engineer/genre-presets.md` reference document

## [0.87.0] - 2026-04-07

### Added
- **16 new genres** — Punk & Hardcore deep cuts (6) and Electronic House & Disco variants (10)

### Fixed
- `analyze_mix_issues` now falls back to scanning `stems/` when no root WAVs exist, instead of erroring
- `polish_audio` auto-detects stems and gracefully degrades to full-mix mode instead of hard-failing
- Mix-engineer SKILL.md updated with explicit stems-first decision tree
- Removed unused type-ignore comment for numba import

### Changed
- Vectorized envelope follower in `gentle_compress` using numba JIT for faster audio processing

## [0.86.0] - 2026-04-06

### Added
- **44 new genres** — expanded genre library from 137 to 181 genres with full documentation, mastering presets, and INDEX integration
  - **Hip-Hop regional** (#178): East Coast Hip Hop, West Coast Rap, Southern Hip Hop, Gangsta Rap, Underground Hip Hop, Crunk, Mumble Rap, Pop Rap
  - **Country & Americana** (#202): Honky-Tonk, Bro-Country, Red Dirt, Bakersfield Sound, Western Swing, Cowpunk, Neotraditional Country
  - **Regional American** (#199): Cajun, Go-Go, Chicano Rap, Swamp Pop, Country Rap
  - **Electronic micro-genres** (#205): Nightcore, Breakcore, PC Music, Speedcore, Riddim, Wave, Complextro
  - **Historical & period** (#198): Ragtime, Sea Shanties, Medieval, Madrigal, Music Hall
  - **Jamaican & Reggae** (#191): Roots Reggae, Lovers Rock, Rocksteady, Ragga
  - **Pop subgenres** (#200): Dream Pop, Darkwave, Synth-Pop, Baroque Pop, Chamber Pop, Bubblegum Pop, Twee Pop, Sophisti-pop

## [0.85.0] - 2026-04-05

### Added
- **62 new genres** — expanded genre library from 74 to 136 genres with full documentation, mastering presets, and INDEX integration
  - **Rock/Punk**: Ska, Post-Punk, Noise Rock, Math Rock, Stoner Rock, Nu-Metal, Pop Punk, Screamo
  - **Metal**: Death Metal, Power Metal, Symphonic Metal, Folk Metal, Deathcore, Djent, Groove Metal, Sludge Metal, Progressive Metal, Speed Metal
  - **Electronic**: Jungle, UK Garage, Breakbeat, Downtempo, IDM, Electro, Hardstyle, Electroswing, Future Bass, Minimal Techno, Gabber
  - **Hip-Hop**: Boom Bap, Cloud Rap, Conscious Hip-Hop
  - **R&B/Soul**: Neo-Soul, Motown
  - **Country/Folk**: Outlaw Country, Zydeco
  - **Latin/Caribbean**: Cumbia, Samba, Reggaeton, Afro-Cuban, Boogaloo, Tropicália, Zouk
  - **African**: Highlife, Amapiano, Afroswing, Gnawa
  - **Asian**: J-Pop, City Pop, Mandopop, Enka, Qawwali, Bhangra
  - **Christian/Faith**: Contemporary Christian, Worship
  - **Other**: Dub, Flamenco, Fado, New Age, Spoken Word, Musical Comedy, Video Game Music, Cabaret

## [0.84.1] - 2026-04-05

### Removed
- **Ship skill** — internal release automation that didn't fit the plugin's music production scope; assumed a single-branch workflow incompatible with the develop → main release flow ([#145](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/145))

## [0.84.0] - 2026-04-05

### Added
- **Bollywood genre** — Hindi film music (filmi) with 10 subgenres, 15 artists, 14 reference tracks, Suno keywords, mukhda/antara lyric conventions, and mastering presets with differentiated LUFS targets ([#141](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/141), community contribution by [@markus-michalski](https://github.com/markus-michalski))
- **Diagnose MCP tool** — comprehensive health check tool for troubleshooting plugin, server, and environment issues ([#137](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/137))
- **Explicit flag consistency check** — release gate validates that frontmatter `explicit` flag matches actual lyric content ([#117](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/117))
- **Realistic audio fixtures** — WAV/MP3 test fixtures with proper headers, pipeline integration tests, and dev Makefile ([#132](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/132))
- **Tool tests and CI coverage threshold** — handler isolation tests for gates, album_ops, streaming, and server unit tests ([#119](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/119))

### Changed
- **Refactored processing.py** — split monolithic 2,752-line module into 4 focused submodules: audio, mixing, sheet_music, video ([#122](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/122))

### Fixed
- **Genre index count** — corrected stale count from 71 to 74 ([#143](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/143))

## [0.83.1] - 2026-04-04

### Changed
- **README** — added star history chart and circular contributor profile icons

## [0.83.0] - 2026-04-04

### Added
- **Instrumental field sync validation** — validate-album warns and pre-generation-check blocks when frontmatter `instrumental` and Track Details table disagree ([#129](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/129))
- **Guided regeneration workflow** — structured path for rejecting and regenerating tracks that don't meet quality standards ([#116](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/116))
  - CLAUDE.md: regeneration workflow documented in Status Tracking section
  - Resume: detects Generated tracks without approval (✓), offers style/lyrics/retry regeneration paths
  - Next-step: recommends review and regeneration for unapproved Generated tracks
  - SKILL_INDEX: new "Track Regeneration" workflow sequence and decision tree entries
- **Album status management improvements** — auto-advancement, batch operations, and documented status flows ([#118](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/118))
  - CLAUDE.md: documented non-documentary status flow (Concept → In Progress, skipping Research/Sources phases), auto-advancement rules, and batch-approve workflow
  - Verify-sources: auto-advances album from Research Complete → Sources Verified when all tracks verified, with partial verification progress reports
  - Resume: phase table covers both documentary and standard album flows, batch-approve path for Generated → Final
  - Next-step: batch-approve path for all-generated albums
  - SKILL_INDEX: batch-approve entry in Album Lifecycle table
- **Instrumental track support** — tracks can be marked `instrumental: true` in frontmatter to skip the lyrics workflow entirely ([#115](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/115))
  - Track template: new `instrumental` field in frontmatter and Track Details table
  - Pre-generation-check: Gates 2 (Lyrics), 3 (Pronunciation), 4 (Explicit) auto-skip for instrumental tracks
  - Lyric-writer, lyric-reviewer, pronunciation-specialist: instrumental guard stops execution with clear routing to suno-engineer
  - Resume & next-step: decision trees route instrumental tracks directly to `/suno-engineer`
  - Suno-engineer: expanded instrumental guidance (Style Box without vocals, section tags only, Instrumental: On)
  - Album-conceptualizer: Phase 4 asks vocal/instrumental split per track
  - SKILL_INDEX: explicit instrumental workflow path and mixed album (vocal + instrumental) sequence
  - New-album: tip about instrumental track support for OST/soundtrack albums

## [0.82.0] - 2026-04-03

### Added
- **Musicals genre** — integrated theatrical form from Golden Age Broadway (Rodgers & Hammerstein) to contemporary hip-hop musicals (Hamilton); 8 subgenres, 15 artists, 14 reference tracks, Suno keywords, lyric conventions, and mastering presets
- **Soundtrack genre** — vocal songs and curated compilations for film/TV, distinct from instrumental Cinematic scoring; covers Bond themes, disco soundtracks, needle drops, animated features, and power ballads; 8 subgenres, 15 artists, 14 reference tracks, Suno keywords, lyric conventions, and mastering presets
- **Database query pagination** — `db_list_tweets` and `db_search_tweets` support `limit`/`offset` parameters ([#114](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/114))
- **MCP payload pagination** — summary modes and top-N limiting for large-payload MCP tools ([#113](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/113))

## [0.81.2] - 2026-03-27

### Changed
- **boto3** bumped 1.42.76 → 1.42.77

## [0.81.1] - 2026-03-27

### Fixed
- **`[End]` tag misclassification** — `validate_section_structure` now recognizes `[End]` as a dedicated section type instead of defaulting to `verse` ([#111](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/111), closes [#108](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/108))

## [0.81.0] - 2026-03-26

### Added
- **mypy strict type checking** — full type annotations across all 51 source files (handlers, tools, server) with strict settings (`disallow_untyped_defs`, `disallow_any_generics`, `warn_unreachable`, etc.), integrated into CI lint job ([#110](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/110), closes [#102](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/102))
- **`types-PyYAML` stubs** — proper yaml typing, eliminated all `import-untyped` suppressions
- **Extended ruff rules** — added I (isort), UP (pyupgrade), B (bugbear), SIM (simplify), RUF rule sets; auto-fixed 216 import/syntax issues, manually fixed 44 remaining across tools/ and handlers/

### Fixed
- **Ambiguous variable names** — renamed `l` to `lightness`/`line` in media_utils and lyrics_analysis
- **Mutable default argument** — `reset_mastering` parameter annotated with noqa
- **Bare generic types** — all `dict`, `list`, `tuple`, `Pattern` given explicit type parameters

## [0.80.0] - 2026-03-26

### Added
- **Modularized MCP server** — broke monolithic `server.py` (10,260 lines, 76 tools) into 16 focused handler modules under `handlers/`, reducing `server.py` to ~480 lines of orchestration ([#85](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/85), closes [#81](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/81))
- **`_find_track_or_error` shared helper** — deduplicated track lookup boilerplate across 8 call sites in 5 handler modules
- **`StateCache.get_state_ref()`** — public API for in-place state mutation, replacing 3 direct `cache._state` accesses
- **Re-export completeness test** — catches missing re-exports when new tools are added to handler modules

### Changed
- **MCP server architecture** — 79 tools organized across 16 domain modules: core, content, text_analysis, lyrics_analysis, album_ops, gates, streaming, skills, status, promo, health, ideas, rename, processing, database, maintenance
- **`verify_streaming_urls` runs concurrently** — HTTP checks now use `asyncio.gather` (worst-case latency ~50s → ~10s)

### Fixed
- **State cache stale after `create_album_structure`** — new albums are now immediately available to subsequent tools like `create_track`
- **Shadowed `import re as _re`** in processing.py and _shared.py — now uses module-level `re`
- **19 unused imports** removed across handler modules (F401 lint violations from monolith extraction)
- **Duplicated constants** — `_STREAMING_PLACEHOLDER_MARKERS`, `_MARKDOWN_LINK_RE`, and `_CODE_BLOCK_SECTIONS` deduplicated into `_shared.py`
- **Dead code** — removed unused `_words_rhyme` function from lyrics_analysis.py

## [0.79.4] - 2026-03-25

### Fixed
- **Dynamic version badge** — README badge now reads from GitHub releases, never needs manual updating
- **Automated dev bump** — auto-release workflow bumps develop to next `-dev` version after each release
- **Version sync hook false positives** — hook now detects sequential edits and skips mid-pair checks
- **Dependabot grouping** — pip and GitHub Actions updates batched into single PRs instead of 10+ individual PRs

## [0.79.3] - 2026-03-25

### Changed
- **README reworked** — personal narrative opener, 77% shorter, architecture-focused; skills reference, troubleshooting, and configuration extracted to `docs/`

### Fixed
- **CI: version badge check skips `-dev` versions** — badge shows last release, dev branches no longer fail on mismatch
- **CI: removed test count and skills badge checks** — badges removed from README, corresponding CI validations removed

## [0.79.2] - 2026-03-25

### Changed
- **Batch dependency update** — 11 pip packages and 3 GitHub Actions bumped to latest versions

### Fixed
- **pypdf CVE-2026-33699** — bumped pypdf 6.9.1→6.9.2 to resolve security vulnerability

## [0.79.1] - 2026-03-25

### Added
- **Dependabot configuration** — automated weekly dependency update PRs for pip packages and GitHub Actions version pins

## [0.79.0] - 2026-03-25

### Added
- **Rilo Kiley artist deep-dive** — comprehensive artist reference for indie-rock genre covering discography, production techniques, and style characteristics

### Fixed
- **`line` style ignores `color_hex` and `glow` parameters** — was hardcoded to `colors=white` with no glow support; now uses custom color and glow like all other styles (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#84](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/84))
- **CI: ignore unfixed pygments CVE-2026-4539 in pip-audit** — added exclusion for upstream vulnerability with no available fix

## [0.78.1] - 2026-03-24

### Added
- **German pronunciation section in Suno pronunciation guide** — documents vowel length fixes (single → double vowel for long sounds, e.g. `juchhe` → `juchee`), umlaut handling, and German interjection pronunciation table (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#79](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/79))

## [0.78.0] - 2026-03-24

### Added
- **Children's Music genre** — comprehensive documentation covering nursery rhymes, educational music, Kinderlieder, lullabies, kids pop, singalong, musical storytelling, action/movement songs, animated/TV soundtrack, and family folk subgenres; 18 artists from Woody Guthrie (1947) to Cocomelon (2006+); mastering presets with lullaby variant (-16 LUFS) (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#78](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/78))

## [0.77.1] - 2026-03-23

### Fixed
- **Test skill uses venv Python and absolute paths** — `python3 -m pytest tests/` replaced with `~/.bitwize-music/venv/bin/python3 -m pytest ${CLAUDE_PLUGIN_ROOT}/tests/` across SKILL.md and test-definitions.md, fixing failures when invoked as a plugin skill (system Python missing deps, relative paths not resolving)

## [0.77.0] - 2026-03-23

### Added
- **76 new unit tests** for external tool mocking — boto3 cloud uploads (19 tests), ffmpeg/subprocess promo video generation (14 tests), album sampler pipeline (10 tests), reference mastering CLI (7 tests), media utilities (13 tests), fade-out and master_track pipeline (12 tests), bringing total from 2,406 to 2,482
- **PR target gate** — CI now blocks PRs to `main` unless source branch is `develop`
- **Dev version guard** — CI blocks `-dev` version suffixes from reaching `main`

### Changed
- **TODO.md audit** — marked Priority 6 items as complete (logging, progress, retry, concurrency, cache cleanup were all already implemented); added Future Improvements section for post-1.0 work

## [0.76.0] - 2026-03-23

### Added
- **`color_hex` parameter** for `generate_promo_videos` and `generate_album_sampler` — manually set wave color (e.g. `"#C9A96E"`) instead of auto-extracting from artwork (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#76](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/76))
- **`glow` parameter** for both tools — control glow intensity from 0.0 (none) to 1.0 (full), default 0.6; replaces hardcoded 3-layer screen blend (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#76](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/76))
- **`text_color` parameter** for both tools — override default white text color (e.g. `"#FFD700"` for gold) (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#76](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/76))
- **`style` parameter for `generate_album_sampler`** — same 9 visualization styles as promo videos (was hardcoded to "pulse") (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#76](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/76))

### Changed
- **Album sampler clip generation** refactored to delegate to `generate_waveform_video()` from promo video module, eliminating duplicated filter code and ensuring consistent rendering (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#76](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/76))

## [0.75.0] - 2026-03-23

### Added
- **Promo language selection** — New Step 4 in promo-writer workflow asks user which language(s) to generate copy in (English, German, French, Spanish, bilingual, or custom); skipped automatically when `## Language` is set in `promotion-preferences.md` override (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#75](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/75))
- **Bilingual promo mode** — Stacked primary + secondary language in one post (separated by `---` divider); Twitter exception uses separate tweets per language due to 280-char limit (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#75](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/75))
- **Language Adaptation section** in copy-formulas.md with bilingual post format example and language rules (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#75](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/75))
- **Campaign cross-reference links** — All 5 platform template files now link back to campaign.md (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#75](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/75))
- **Platform copy overview table** in campaign.md template with links to each platform file (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#75](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/75))

### Changed
- **Promo templates reformatted** — Cleaner heading structure, consistent `---` separators across all platform templates; Instagram hashtag sets as table; campaign.md includes Language field in overview (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#75](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/75))
- **Promo-writer workflow renumbered** — Steps 5-9 (was 4-8) to accommodate new Language Selection step (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#75](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/75))

## [0.74.0] - 2026-03-23

### Added
- **Multi-platform AI art prompts** — Album art director now asks which AI art platform to use (Midjourney, Leonardo.ai, DALL-E, Stable Diffusion) and generates platform-specific prompts with appropriate format, negative prompts, and model/preset recommendations (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#74](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/74))
- **Leonardo.ai support** — Natural language prompts with separate negative prompt field, model selection (Phoenix, Kino XL), and preset recommendations (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#74](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/74))
- **Platform comparison table** — Quick reference for choosing the right AI art generator (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#74](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/74))
- **Platform-specific tips** — Refinement keywords and best practices per platform (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#74](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/74))

## [0.73.0] - 2026-03-23

### Added
- **Chanson genre** — French chanson documentation covering réaliste, à texte, rive gauche, musette, nouvelle chanson and more (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#73](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/73))
- **Middle Eastern Pop genre** — Arabic, Israeli, and North African pop covering raï, Mizrahi, khaleeji, mahraganat, and Arabic-electronic fusion (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#73](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/73))
- **Mastering presets** — Added Schlager, Chanson, and Middle Eastern Pop (with aliases for arabic-pop, rai, mizrahi, mahraganat) to both `genre-presets.yaml` and `genre-presets.md` (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#73](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/73))
- **Genre-creator skill update** — Added step 9 to genre-creator workflow: update mastering preset files when creating new genres (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#73](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/73))

## [0.72.2] - 2026-03-22

### Fixed
- **genre-creator skill structure** — added required `## Your Task` and `## Important Notes` sections, fixed broken template link, added to SKILL_INDEX.md
- **README skill count** — updated 51 → 52 to reflect genre-creator addition
- **README version badge** — updated to 0.72.1

## [0.72.1] - 2026-03-22

### Fixed
- **pypdf CVE fix** — bumped 6.7.5 → 6.9.1 (CVE-2026-31826, CVE-2026-33123)
- **Test badge** — updated count 2348 → 2358

## [0.72.0] - 2026-03-22

### Added
- **Schlager genre** — 68th genre documentation covering German-language popular music from post-war ballads to modern EDM-infused party hits; full Overview, Characteristics, Lyric Conventions, Subgenres, Artists, Suno Keywords, and Reference Tracks sections (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#69](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/69))
- **`genre-creator` skill** — Standardizes creation of new genre documentation files with consistent section order, fact-checking via WebSearch, and automatic INDEX.md updates (contributed by [@markus-michalski](https://github.com/markus-michalski) in [#69](https://github.com/bitwize-music-studio/claude-ai-music-skills/pull/69))
- **Contributors section** — README now credits community contributors

## [0.71.0] - 2026-03-21

### Added
- **Exclude Styles field** — New `### Exclude Styles` section in track template for Suno V5 negative prompting (e.g., "no drums, no electric guitar"); documented in suno-engineer skill with max 2–4 items rule; MCP server supports extraction via `get_track_section` and includes in `suno` content type
- **Tampermonkey exclude styles support** — Suno auto-fill userscript (v1.2.0) now fills the "Exclude styles" input field from clipboard JSON
- **`/clipboard exclude` content type** — Copy just the Exclude Styles section to clipboard
- **Supporting files test** — New `TestSupportingFiles` plugin test validates all files referenced in skill `## Supporting Files` sections exist on disk

### Changed
- **`/clipboard style` auto-appends exclusions** — Style content type now combines Style Box + Exclude Styles into a single paste-ready string (no manual appending needed)
- **Clipboard skill docs** — Updated content type list and `suno` JSON output to reflect `exclude_styles` field
- **Override docs** — Updated `config/README.md` override directory listing to show all 12 override files with format convention note
- **Suno-engineer backfill rule** — Added instruction to backfill `### Exclude Styles` section into older track files when editing them

### Fixed
- **URL scheme validation** — `verify_streaming_urls` now rejects non-http/https URLs (prevents SSRF via file://, gopher://, etc.)
- **Path traversal hardening** — `load_override` and `get_reference` use `Path.relative_to()` instead of string `startswith()` for safer path containment checks
- **DB connection timeout** — Added `connect_timeout=5` to PostgreSQL connections to prevent indefinite blocking
- **Duplicate asyncio import** — Removed redundant `import asyncio` inside `verify_streaming_urls`
- **CodeQL alerts** — Rewrote URL substring checks in tests to use `startswith()`/exact match (resolves 4 "Incomplete URL substring sanitization" alerts)
- **Co-author line** — Updated from "Claude Opus 4.5" to "Claude Opus 4.6" in PR template and SECURITY.md

## [0.70.0] - 2026-03-20

### Added
- **Original Soundtrack (OST) album type** — 6th album type for music evoking fictional media (games, films, TV, anime); includes world/setting template sections, leitmotif planning, duration strategy, and cross-track referencing
- **`voice-checker` skill** — Reviews lyrics and prose for AI-written patterns (abstract noun stacking, over-explained metaphors, cliche escalation, missing idiosyncrasy, prose AI tells); advisory Warning/Info severity
- **Cross-track referencing** — lyric-writer supports callbacks, motifs, and character threads across tracks for concept/narrative albums; new Motifs & Threads and Cross-References template sections
- **Iterative refinement passes** — lyric-writer tighten/strengthen/flow refinement patterns added to craft-reference

### Fixed
- **Missing skill trigger phrases** — added trigger conditions to pre-generation-check, ship, and voice-checker skill descriptions
- **Domain correction** — `bitwize-music.com` → `bitwizemusic.com` in config example and tests
- **pypdf CVE fix** — bumped 6.7.1 → 6.7.5 (CVE-2026-27628, CVE-2026-27888, CVE-2026-28351, CVE-2026-28804)

## [0.69.0] - 2026-03-03

### Added
- **Target Duration planning system** — `Target Duration` field threaded through album planning (Phase 3), album/track templates, lyric-writer, suno-engineer, and lyric-reviewer; lookup chain: track → album → genre default
- **Duration-to-word-count mapping** — explicit table in craft-reference.md mapping duration ranges to word count targets for hip-hop and non-hip-hop genres
- **Duration-aware prompt construction** — suno-engineer adjusts structure recommendations based on target duration (under 3:00, 3:00–5:00, over 5:00)
- **Duration override example** — album-planning-guide override template includes duration preferences by format

## [0.68.0] - 2026-03-01

### Changed
- **Suno target duration guidance** — lyric-writer word count targets updated to produce 3:30–5:00 minute tracks (previous targets produced 2:00–2:30); genre-specific word counts, structure recommendations, and instrumental tag runtime estimates added to craft-reference.md
- **Length check updated** — quality check #8 now flags songs under 200 words as "likely too short for target duration" and lowers hard-fail thresholds to 400/600 words (non-hip-hop/hip-hop)

## [0.67.0] - 2026-02-23

### Added
- **Sheet music URL persistence** — `publish_sheet_music` now writes uploaded R2 URLs back to track and album frontmatter automatically (singles → `sheet_music.pdf`/`musicxml`/`midi` per track, songbook → `sheet_music.songbook` on album README)
- **`prepare_singles.py`** — replaces `fix_titles.py`; copies source files to `singles/` with clean consumer-ready titles, generates `.manifest.json` for track ordering
- **Songbook title page, TOC, and footers** — `create_songbook.py` enhanced with professional title page, table of contents, and configurable footer URL
- **`sheet_music` frontmatter** — new section in track template (`pdf`, `musicxml`, `midi`) and album template (`songbook`) for sheet music download URLs
- **`_update_frontmatter_block()` helper** — reusable function for adding/updating YAML frontmatter blocks in markdown files
- **`public_url` config field** — documented in R2 cloud config for custom CDN domain URLs
- **`enabled` and `footer_url` config fields** — new sheet_music config options for master switch and PDF footer customization
- **8 new tests** — 5 for frontmatter persistence in `TestPublishSheetMusic`, 3 for `TestUpdateFrontmatterBlock`

### Changed
- **`xml` → `musicxml`** — sheet music frontmatter key renamed for clarity
- **Relative R2 key fallback** — when no `public_url` configured, frontmatter is still populated with relative R2 keys instead of skipping entirely

### Removed
- **`fix_titles.py`** — replaced by `prepare_singles.py` with broader functionality

## [0.66.0] - 2026-02-22

### Added
- **12-stem pipeline** — expanded from 6 to 12 stem types matching Suno's full `split_stem` output: guitar, keyboard, strings, brass, woodwinds, and percussion now have dedicated processing chains instead of being dumped into the "other" catch-all
- **Instrument-name keywords** — flexible stem routing matches by instrument name (e.g. "Piano.wav" → keyboard, "Saxophone.wav" → woodwinds, "Trumpet.wav" → brass, "Violin.wav" → strings)
- **Genre overrides for new stems** — 20+ genre presets updated with per-stem settings for guitar, keyboard, strings, brass, woodwinds, and percussion
- **45 new tests** — 6 processor test classes, 12-stem integration test, 6 keyword routing regression tests

### Fixed
- **Percussion/drums separation** — "percussion" keyword no longer routes to "drums"; Suno separates kit drums (kick/snare/hi-hats) from percussion (congas/shakers/tambourine) and they need different processing chains

## [0.65.0] - 2026-02-22

### Reverted
- **`originals/` audio layout** — reverted `originals/` subdirectory layout and `migrate_audio_layout` MCP tool; WAV files remain in album audio root
- **Fade-out support** — reverted `apply_fade_out()` from mastering pipeline and `fade_out` field from track template/parser
- **Mix polish character effects** — reverted `apply_saturation()`, `apply_lowpass()`, `apply_stereo_width()` from mix pipeline and character effect settings from genre presets

These 0.61.0 audio pipeline changes degraded output quality. Infrastructure from 0.62.0–0.63.0 (develop branch model, venv health check, debug logging, `reset_mastering`, `cleanup_legacy_venvs`) is preserved.

## [0.64.0] - 2026-02-22

### Reverted
- **Mastering compression stage** — reverted dedicated compression stage (broke mastering pipeline); will revisit later
- **Stereo width in stems path** — reverted stems stereo width (coupled to compression changes)
- **Bus compression presets** — reverted mix-presets.yaml bus compression presets (dead config without code)

## [0.63.0] - 2026-02-21

### Added
- **Bus compression presets** — 16 genre presets in mix-presets.yaml for bus compression stage
- **Stereo width in stems path** — stereo width processing now applied during stems-based polish pipeline
- **Mastering compression stage** — dedicated compression stage added to mastering pipeline
- **Mastering genre confirmation** — mastering-engineer skill now asks to confirm the genre preset before mastering and checks if any tracks need different treatment
- **`check_venv_health` MCP tool** — compares installed package versions against `requirements.txt` pins; integrated into session start to warn about version drift after plugin upgrades
- **Configurable debug logging** — new `logging` section in config.yaml enables file-based debug logging with rotation; silent by default, opt-in for development/troubleshooting
- **`reset_mastering` MCP tool** — removes `mastered/` and/or `polished/` subfolders so the mastering pipeline can be re-run cleanly; dry-run safe by default, `originals/` and `stems/` are protected
- **`cleanup_legacy_venvs` MCP tool** — detects and removes stale per-tool venvs (`mastering-env`, `promotion-env`, `cloud-env`) left over from pre-0.40.0; dry-run safe by default
- **Dev mode docs** — CONTRIBUTING.md section explaining how to avoid cached plugin conflicts when using `--plugin-dir`

### Removed
- **Redundant requirements files** — removed `requirements-mastering.txt`, `requirements-mixing.txt`, `requirements-promo.txt`, `requirements-research.txt`, `requirements-sheet-music.txt`, and `tools/cloud/requirements.txt`; the unified `requirements.txt` covers all dependencies

### Fixed
- **Stale venv references** — updated `config/README.md`, `TESTING.md`, `reference/mastering/mastering-workflow.md`, and `skills/test/test-definitions.md` to reference unified `venv/` instead of legacy `mastering-env/`
- **Migration 0.40.0** — added missing `cloud-env` cleanup action
- **CI installs full dependencies** — `test.yml` now uses `requirements.txt` instead of the removed `requirements-mastering.txt`

## [0.62.0] - 2026-02-21

### Added
- **`develop` branch model** — two-branch workflow with `develop` for active work and `main` for stable releases; plugin distribution channels via branch-based marketplace
- **Plugin version in about skill** — `/bitwize-music:about` now reads and displays version from plugin.json dynamically

### Changed
- **CI targets Python 3.11 only** — dropped 3.9/3.10/3.12 matrix; not a library, runs in user's venv
- **CI triggers** — pushes run on `develop` only; `main` validated via PR gate
- **CONTRIBUTING.md** — updated for develop/main branch model, release process, co-author line

### Fixed
- **Test count badge** — corrected 2235 → 2238 (3 skipped tests collected by CI)

## [0.61.0] - 2026-02-21

### Added
- **`originals/` audio layout** — raw WAV files now stored in `originals/` subdirectory to keep album audio root clean; all tools (mastering, mixing, promotion, import-audio) updated with backward-compatible fallback to album root for legacy albums
- **`migrate_audio_layout` MCP tool** — migrates pre-existing albums from root-level WAVs to `originals/` layout (dry-run safe by default, single album or batch)
- **Fade-out support** — `apply_fade_out()` in mastering pipeline with exponential/linear curves; `fade_out` parameter in `master_track()`, track file parser, and track template (`| **Fade Out** | — |`)
- **Mix polish character effects** — `apply_saturation()` (tanh waveshaping), `apply_lowpass()` (Butterworth), `apply_stereo_width()` (mid-side processing) in mix_tracks.py; genre presets updated for 50+ genres with per-stem saturation, lowpass, and stereo width settings
- **29 new tests** — 6 for `migrate_audio_layout`, plus mastering and mixing coverage

### Changed
- **CLAUDE.md** — updated audio path structure documentation to reflect `originals/` layout
- **import-audio skill** — imports now target `originals/` subdirectory
- **mastering-engineer skill** — updated pre-flight check to look in `originals/` first
- **mix-engineer skill** — updated audio directory convention docs

## [0.60.0] - 2026-02-21

### Added
- **Suno stem discovery** — `discover_stems()` maps Suno's exported filenames (`0 Lead Vocals.wav`, `1 Backing Vocals.wav`) to polish pipeline stem roles via keyword-based matching + multi-file combining
- **Mastering auto-recovery** — `master_album` Stage 5 auto-detects recoverable dynamic range failures (LUFS too low + peak at ceiling) and applies `fix_dynamic()` from raw source files before re-verifying
- **`fix_dynamic()` reusable helper** — extracted core fix logic into a function that accepts pipeline settings (target LUFS, EQ, ceiling) instead of hardcoded values
- **12 new tests** — 7 unit tests for `fix_dynamic()`, 5 pipeline tests for auto-recovery scenarios

### Fixed
- **`fix_dynamic_track` MCP tool** — now uses shared `fix_dynamic()` instead of inline code

## [0.59.0] - 2026-02-20

### Added
- **`mix-engineer` skill** — automated per-stem audio polish pipeline for Suno output cleanup
- **`tools/mixing/mix_tracks.py`** — core DSP module: spectral gating noise reduction, Butterworth highpass, parametric EQ, high shelf, envelope-following compression, click detection/interpolation, mid-side stereo enhancement, stem remixing with per-stem gain
- **`tools/mixing/mix-presets.yaml`** — genre presets for 50+ genres with per-stem processing settings and deep-merge user override support
- **`polish_audio` MCP tool** — process stems or full mixes with genre presets
- **`analyze_mix_issues` MCP tool** — spectral analysis for noise floor, muddiness, harshness, clicks, sub-rumble
- **`polish_album` MCP tool** — 3-stage pipeline (analyze → polish → verify)
- **`source_subfolder` parameter on `master_audio`** — read WAVs from a subfolder (e.g., "polished") for polish → master chaining
- **89 unit tests** for mix_tracks.py — 16 test classes covering all DSP functions, pipeline modes, preset loading, numerical stability, and override merging
- **`requirements-mixing.txt`** — standalone dependency file for mixing tools

### Fixed
- **Python 3.9 compat** — replaced `str | None` union syntax with `Optional[str]` in server.py
- **Lint** — removed unused `reachable` variable in URL checking
- **README badges** — updated skills count (49→50), test count (1969→2183), added mix-engineer to workflow table and skills reference

## [0.58.0] - 2026-02-16

### Added
- **`ship` skill** — automates full code release pipeline (branch → commit → PR → CI → merge → version bump → release → cleanup)

### Fixed
- **Unused import** — removed `parse_frontmatter` from server.py imports (ruff F401)
- **Bandit false positives** — added `nosec` annotations for parameterized SQL and validated URL open in server.py
- **README version badge** — updated from 0.56.0 to match plugin.json 0.57.0

## [0.57.0] - 2026-02-16

### Added
- **PostgreSQL database integration** — 8 new MCP tools for social media post management (`db_init`, `db_list_tweets`, `db_create_tweet`, `db_update_tweet`, `db_delete_tweet`, `db_search_tweets`, `db_sync_album`, `db_get_tweet_stats`)
- **Database config section** — `database:` in config.yaml for PostgreSQL credentials with password masking in state
- **Portable schema** — `tools/database/schema.sql` with migrations directory for future changes
- **n8n workflow export** — `tools/n8n/n8n-auto-post-twitter.json` for automated Twitter/X posting (sanitized, no credentials)
- **`tools/database/`** — connection helper, schema, README with setup instructions
- **`tools/n8n/`** — workflow exports with setup docs, credential notes, and API cost info

## [0.56.0] - 2026-02-16

### Added
- **9 artist deep-dives** — production-level sonic profiles for trance (t.A.T.u., Cascada, ATB, Alice Deejay, Ian Van Dahl), pop (Ace of Base, Aqua, La Bouche), and electronic (Eiffel 65) with members, discography, musical analysis, Suno prompt keywords, and reference tracks
- **Trance artists INDEX.md** — quick-reference Suno keywords and reference tracks for all 5 trance artists
- **Pop/Electronic INDEX updates** — added new artists to existing genre INDEX files

### Fixed
- **Suno auto-fill SPA routing** — userscript now detects Next.js client-side navigation via History API monkey-patching (pushState/replaceState + popstate); button injects on `/create`, removes on other pages, never duplicates

## [0.55.0] - 2026-02-15

### Added
- **`count_syllables` MCP tool** — syllable counts per line with section tracking, consistency analysis (stdev > 3 = UNEVEN), and summary stats
- **`analyze_readability` MCP tool** — Flesch Reading Ease scoring, vocabulary richness, and grade level assessment for lyrics
- **`analyze_rhyme_scheme` MCP tool** — rhyme scheme detection (AABB/ABAB/XAXA) with section awareness, self-rhyme and repeated end word detection
- **`validate_section_structure` MCP tool** — section tag validation, balanced verse lengths (diff > 2 lines flagged), empty/duplicate/missing section detection, content-before-first-tag warning
- **`_count_syllables_word` helper** — vowel cluster heuristic for syllable counting (silent 'e', consonant-'le' endings, y-as-vowel)
- **`_get_rhyme_tail` / `_words_rhyme` helpers** — suffix-based rhyme detection from last vowel cluster to end of word, with silent-e handling and plural tolerance
- **85 unit tests** for lyrics analysis tools (`test_server_lyrics.py`) — 13 test classes covering all helpers and MCP tools with edge cases, boundary conditions, and bug-catching coverage

## [0.54.0] - 2026-02-14

### Added
- **`extract_distinctive_phrases` MCP tool** — extracts 4-7 word n-grams from lyrics with section awareness, filters ~75 common song cliches and stopword-only phrases, ranks by section priority (chorus/hook > verse), returns pre-formatted web search suggestions for plagiarism checking
- **`_COMMON_SONG_PHRASES` constant** — frozenset of ~75 ubiquitous lyric cliches filtered during phrase extraction (love/heartbreak, night/time, pain/struggle, fire/light, generic emotional)
- **`plagiarism-checker` skill** — scans lyrics for phrases that may match existing songs using web search and LLM knowledge; standalone quality check (not a pre-generation gate) with HIGH/MEDIUM/LOW risk findings and CLEAR/NEEDS REVIEW/REWRITE REQUIRED verdicts
- **~35 unit tests** for distinctive phrase extraction (`test_server_lyrics.py`) — covers `_tokenize_lyrics_with_sections` helper, `_extract_distinctive_ngrams` helper, and `extract_distinctive_phrases` MCP tool

## [0.53.0] - 2026-02-14

### Added
- **`check_cross_track_repetition` MCP tool** — scans all tracks in an album for words and phrases repeated across multiple tracks; tokenizes lyrics into words and 2-4 word n-grams, filters stopwords and common song vocabulary, flags items appearing in N+ tracks (configurable threshold)
- **70 unit tests** for cross-track repetition analysis (`test_server_lyrics.py`) — covers helpers (`_tokenize_lyrics_by_line`, `_ngrams_from_lines`), tool edge cases (slug normalization, unreadable files, stopword filtering, sort order, summary structure), and realistic multi-section lyrics

## [0.52.1] - 2026-02-14

### Fixed
- **Album sampler track titles** — `get_track_title()` now converts slug format to readable titles (e.g., "ocean-of-tears" → "Ocean Of Tears"), matching individual promo video behavior
- **Album sampler MCP title resolution** — `generate_album_sampler` MCP tool now pre-resolves proper titles from state cache (markdown metadata) and passes them to the sampler, so titles match exactly what's in track files

## [0.52.0] - 2026-02-14

### Added
- **`get_python_command` MCP tool** — returns venv Python path, plugin root, and ready-to-use command template; prevents skills from hitting system Python which lacks dependencies
- **4 new tests** for `get_python_command` (venv exists, venv missing, plugin root, usage template)

### Changed
- **Skills migrated from bare python3 to MCP tools** — mastering-engineer (12 refs), promo-director (2 refs), sheet-music-publisher (9 refs), session-start (1 ref) now use MCP tools instead of bash python3 commands
- **Skills without MCP equivalents use `get_python_command`** — cloud-uploader (4 refs), test-definitions (1 ref) now call `get_python_command()` first to get the venv path
- **CLAUDE.md** — indexer rebuild references updated to `rebuild_state()` MCP tool
- **genre-presets.md** — all python3 CLI examples replaced with MCP tool calls

## [0.51.0] - 2026-02-14

### Fixed
- **`resolve_path` mirrored structure** — audio and documents paths now use `{root}/artists/{artist}/albums/{genre}/{album}/` matching the content structure (was flat `{root}/{artist}/{album}/`)
- **Genre lookup for audio/documents** — `resolve_path` MCP tool and `paths.py` utility now look up genre from state cache for all path types (was only content/tracks)
- **`_resolve_audio_dir` genre support** — mastering/QC MCP tools now resolve genre from state cache instead of using flat paths
- **`validate_album_structure` wrong-location check** — detects old flat audio structure as misplaced files
- **`rename_album` path construction** — uses mirrored structure for audio and documents directories
- **`upload_to_cloud.py` path finder** — tries mirrored structure first with glob fallback
- **35 documentation files** — updated all path references from flat to mirrored structure

### Added
- **Per-track stems subfolders** — `import-audio` skill now extracts stems into `stems/{track-slug}/` subfolders preventing filename collisions across tracks
- **Stems file type detection** — `import-audio` skill detects zip files and routes to stems extraction workflow
- **Track slug derivation** — stems import infers track from zip filename, user argument, or prompts

## [0.50.0] - 2026-02-13

### Added
- `master_album` MCP tool — end-to-end mastering pipeline (analyze → QC → master → verify → QC → status update) in a single call
- Technical Audio QC tool (`qc_tracks.py`) with 7 checks: mono compatibility, phase correlation, clipping, click/pop detection, silence, format validation, spectral balance
- `qc_audio` MCP tool for running QC from skills
- QC gates integrated into mastering-engineer workflow (pre and post mastering)

## [0.49.0] - 2026-02-13

### Added
- **K-pop genre research** — 27 artist deep-dive files covering all major K-pop acts across 4 generations (BTS, BLACKPINK, Stray Kids, NewJeans, aespa, (G)I-DLE, ATEEZ, IVE, LE SSERAFIM, SEVENTEEN, EXO, Girls' Generation, Big Bang, SHINee, TWICE, Red Velvet, 2NE1, TVXQ, Dreamcatcher, ENHYPEN, TXT, ITZY, Epik High, IU, Zion.T, Crush, DEAN) with members, discography, musical analysis, Suno prompt keywords, and reference tracks
- **K-pop artist INDEX** — `genres/k-pop/artists/INDEX.md` quick-reference with Suno keywords and reference tracks for all 27 artists
- **K-pop artist blocklist** — 25 entries added to `reference/suno/artist-blocklist.md` with sonic description alternatives
- **K-pop Suno V5 tips** — comprehensive K-pop section in `reference/suno/v5-best-practices.md` covering style prompts, group vocal sound, Korean-English code-switching, switch-up technique, and common issues
- **Enhanced K-pop README** — expanded with entertainment company sounds (SM, YG, JYP, HYBE, ADOR, Cube, KQ), additional subgenres, industry terms glossary, and artist cross-references

## [0.48.0] - 2026-02-12

### Added
- **`/promo-writer` skill** — generates platform-specific social media copy (Twitter, Instagram, TikTok, Facebook, YouTube) from album themes, track concepts, and streaming lyrics; campaign strategy first, then native per-platform posts with character counts and hashtag compliance (Sonnet tier)
- **Social media best practices reference** — `reference/promotion/social-media-best-practices.md` with per-platform content strategy, algorithm notes, music discovery mechanics, hashtag strategies, indie artist tactics, and cross-platform release rollout templates
- **Copy formulas reference** — `skills/promo-writer/copy-formulas.md` with 6 hook formulas, CTA templates, post structure skeletons, hashtag recipes by genre/phase, and tone adaptation guide
- **Promotion preferences override** — `config/overrides.example/promotion-preferences.md` for customizing tone, platform priorities, messaging themes, hashtag preferences, and AI music positioning

### Fixed
- **Twitter hashtag count** — corrected from "2-3 per tweet" to "1-2 per tweet" in platform-rules.md and promo-reviewer SKILL.md (researched best practice)
- **Twitter hashtag rules** — added "never start with hashtag" (algorithm penalty), tag rotation (spam detection), and Tags to Avoid section (#MusicPromotion, #FollowBack, #Like4Like)
- **Release director promo references** — replaced "manual creative step" with promo-writer reference in QA item 9 and Distribution Prep item 6
- **Promo reviewer workflow** — updated diagram, When to Use, and empty-files message to reference promo-writer as option

## [0.47.0] - 2026-02-11

### Added
- **9 processing MCP tools** — `analyze_audio`, `master_audio`, `fix_dynamic_track`, `master_with_reference`, `transcribe_audio`, `fix_sheet_music_titles`, `create_songbook`, `generate_promo_videos`, `generate_album_sampler` — wrap Python processing scripts for direct MCP invocation with lazy dep checking and structured JSON responses
- **Suno auto-fill clipboard type** — `format_for_clipboard` now supports `"suno"` content type returning JSON with title, style, and lyrics for browser auto-fill
- **Tampermonkey userscript** — `tools/userscripts/suno-autofill.user.js` auto-fills Suno's create page from clipboard JSON with adaptive field detection and React-compatible input simulation
- **Album streaming block** — album template frontmatter now includes `streaming:` dict with soundcloud, spotify, apple_music, youtube_music, amazon_music keys for listen page generation

### Fixed
- **Pillow CVE-2026-25990** — bumped pillow 10.4.0 → 12.1.1
- **CI lint/security scope** — ruff and bandit now scan `servers/` in addition to `tools/`
- **Ruff warnings** — fixed pre-existing unused imports, variables, and f-string prefix issues in server.py

### Removed
- **Legacy URL fields** — removed `soundcloud_url` and `spotify_url` flat fields from album template (replaced by `streaming:` block)

## [0.46.0] - 2026-02-11

### Changed
- **Complete MCP migration** — migrated remaining 3 skills (`tutorial`, `validate-album`, `sheet-music-publisher`) to use MCP tools instead of manual file access; all 46 skills now use MCP tools where applicable
- **`tutorial`** — config reads → `get_config()`, album scanning → `list_albums()` + `get_album_progress()`
- **`validate-album`** — manual config + `find` command → `get_config()` + `find_album()` + `validate_album_structure()`
- **`sheet-music-publisher`** — config read + manual override loading → `get_config()` + `find_album()` + `resolve_path("audio")` + `load_override()`

## [0.45.0] - 2026-02-11

### Added
- **`/promo-reviewer` skill** — interactive post-by-post review of social media copy in album `promo/` files with approve/revise/shorten/punch-up/hashtag/tone actions, character limit enforcement, and write-back (Sonnet tier)
- **Platform rules reference** — `skills/promo-reviewer/platform-rules.md` with per-platform character limits, hashtag conventions, and tone guidelines

### Fixed
- **SKILL_INDEX alphabetical order** — `pre-generation-check` now correctly sorted before `promo-director`
- **model-strategy.md completeness** — added missing `verify-sources` (Sonnet) and `rename` (Haiku) subsections; counts now match actual skill inventory
- **SKILL_INDEX model sections** — added missing `/verify-sources` to Sonnet list and `/setup` to Haiku list
- **Cross-file count consistency** — all four count locations (SKILL_INDEX, model-strategy, distribution table, README) now agree: 6 Opus, 25 Sonnet, 15 Haiku = 46 total

### Changed
- **Skills count at 46** — up from 45 (added `/promo-reviewer`)

## [0.44.0] - 2026-02-10

### Added
- **Rename MCP tools** — `rename_album` and `rename_track` tools handle slug, title, and directory renames across all mirrored path trees (content, audio, documents) with state cache updates
- **`/rename` skill** — interactive wrapper for renaming albums or tracks with confirmation and error handling (Haiku tier)
- **Plugin migration system** — versioned `migrations/` directory with auto, action, info, and manual migration types; session-start checks for upgrades and processes migration actions
- **Promo templates** — 6 per-platform social media copy templates (`campaign.md`, `twitter.md`, `instagram.md`, `tiktok.md`, `facebook.md`, `youtube.md`) in new `templates/promo/` directory
- **Track template frontmatter** — YAML frontmatter with `title`, `track_number`, `explicit`, `suno_url` fields
- **Suno parenthetical warning** — track template now warns that Suno sings parenthetical directions literally
- **Migration tests** — validation suite for migration file format, YAML frontmatter, version matching, and action types
- **Promo template tests** — validates all 6 templates exist and contain required sections
- **32 rename tests** — `TestRenameAlbum` (15), `TestRenameTrack` (12), `TestDeriveTitleFromSlug` (5)

### Changed
- **Social media copy** moved from inline SOURCES.md sections to dedicated `promo/` directory in album content
- **Promo workflow reference** updated to reflect `promo/` directory separation from video files
- **Album art director** description broadened for use during planning, not just post-Final
- **Clipboard skill** heading detection updated to match new track template structure (`### Lyrics Box` / `### Style Box`)
- **Mastering engineer** now requires explicit path resolution step before mastering workflow
- **Test suite at 1585 tests** — up from 1553 in 0.43.1
- **Skills count at 45** — up from 44 (added `/rename`)

### Fixed
- **CONTRIBUTING.md** — added migration checklist item for PRs with filesystem/template/config changes

## [0.43.1] - 2026-02-06

### Added
- **Test count badge validation** — CI step in `test.yml` verifies README badge matches actual pytest count
- **Pre-commit hook check 11/11** — local badge sync validation before commit
- **Version-sync workflow** now triggers on `tests/**` changes and validates test badge presence

### Fixed
- **README model strategy** — updated Opus 4.5 → Opus 4.6, corrected skill counts (24 Sonnet, 14 Haiku)

## [0.43.0] - 2026-02-06

### Added
- **MCP server expanded to 30 tools** — 21 new tools across path resolution, content extraction, text analysis, validation, and album operations
- **3 content analysis tools** — `check_explicit_content`, `extract_links`, `get_lyrics_stats` for pre-generation checks
- **10 content/validation tools** — `extract_section`, `update_track_field`, `format_for_clipboard`, `validate_album_structure`, `get_album_full`, `search`, `check_pronunciation_enforcement`, `load_override`, `get_reference`, `create_album_structure`
- **8 path/query tools** — `resolve_path`, `resolve_track_file`, `list_track_files`, `list_tracks`, `get_album_progress`, `run_pre_generation_gates`, `scan_artist_names`, `check_homographs`
- **160 integration tests** — full end-to-end pipeline tests (real files → indexer → state.json → StateCache → MCP tool), 5+ per tool
- **309 MCP unit tests** — edge cases, error paths, word boundaries, path traversal protection

### Changed
- **MCP server renamed** — `state-server` → `bitwize-music-server` to reflect expanded scope
- **Test suite at 843 tests** — up from 494 in 0.42.0

## [0.42.0] - 2026-02-06

### Added
- **verify-sources skill** — new `/verify-sources` skill for human source verification workflow
- **State schema documentation** — formal `reference/state-schema.md` documenting state.json structure
- **Path resolver utility** — `tools/shared/paths.py` eliminates manual path construction
- **222 new unit tests** — indexer (121), MCP server (90), path resolver (11); suite now at 494
- **Coverage reporting** — pytest-cov with HTML artifact upload in CI
- **README badges** — version and skills count badges with CI sync validation
- **Badge sync in CI** — version-sync workflow now validates README badges match actual values

### Fixed
- **Resume skill** — merged next-step decision tree into resume (Step 8) for single-skill navigation
- **Lyric reviewer checklist** — heading corrected from 13-Point to 14-Point (matches actual items)
- **Lyric workflow test** — regex now matches writer's `Quality Check (N-Point)` format
- **README/CLAUDE.md alignment** — fixed trigger phrases, co-author line, status definitions
- **Import-audio** — added MP3 file handling guidance and supported formats list

### Changed
- **MCP server logging** — structured logging throughout StateCache for debugging
- **Config quick-start** — added 3-field quick-start block to config.example.yaml
- **Overrides docs** — consolidated to single source of truth in config/README.md
- **SKILL_INDEX** — updated navigation references, added verify-sources

## [0.41.6] - 2026-02-06

### Fixed
- **Tweet template DM issue** — moved @bitwizemusic after hashtags in tweet templates so tweets are public instead of becoming DMs

## [0.41.5] - 2026-02-06

### Fixed
- **MCP server config portability** — .mcp.json now uses `${HOME}` and `${CLAUDE_PLUGIN_ROOT}` environment variables instead of hardcoded absolute paths, making the config portable across different installations

## [0.41.4] - 2026-02-05

### Fixed
- **MCP server environment** — .mcp.json now explicitly passes CLAUDE_PLUGIN_ROOT env variable to server process, fixing "missing env variable" startup failures

## [0.41.3] - 2026-02-05

### Fixed
- **MCP server startup** — .mcp.json now uses venv Python (`~/.bitwize-music/venv/bin/python3`) instead of system Python, fixing server initialization failures

## [0.41.2] - 2026-02-05

### Changed
- **Setup skill simplified** — only recommends unified venv approach, removed confusing system-wide install options
- **Setup checks venv** — verifies ~/.bitwize-music/venv contents instead of system Python packages
- **No optional components** — all dependencies install together, clearer messaging

## [0.41.1] - 2026-02-05

### Fixed
- **Setup skill** — runs dependency checks sequentially to prevent sibling tool call cancellation, removes incorrect mcp.__version__ access
- **Pre-commit hook** — pip-audit check now correctly captures exit code and handles errors properly

## [0.41.0] - 2026-02-05

### Added
- **Pre-commit dependency security scan** — pip-audit automatically checks requirements.txt for known vulnerabilities before commit
- **Hook installation guide** — README and install script in hooks/ directory for easy setup

### Fixed
- **Security vulnerabilities** — updated mcp (1.2.0 → 1.23.0) and pypdf (4.3.1 → 6.6.2) to resolve 10 CVEs

## [0.40.0] - 2026-02-05

### Added
- **Unified venv for all plugin tools** — single `~/.bitwize-music/venv` for MCP server, mastering, cloud uploads, and document hunting. Automatic detection with fallback to system Python. Works on Linux, macOS, Windows, and WSL.
- **MCP server wrapper script** — `servers/state-server/run.py` handles platform-specific venv paths (Windows: `Scripts/python.exe`, Unix: `bin/python3`)
- **Single requirements.txt** — consolidated all dependencies into one file with clear sections for each feature

### Changed
- **MCP server environment variable convention** — server now checks `CLAUDE_PLUGIN_ROOT` first (standard), then `PLUGIN_ROOT` (legacy), then derives from file location
- **Installation simplified** — one venv setup installs everything: `python3 -m venv ~/.bitwize-music/venv && pip install -r requirements.txt`
- **MCP .mcp.json** — simplified configuration by removing redundant `PLUGIN_ROOT` env variable

### Removed
- **Separate requirements files** — removed `requirements-mcp.txt` and `requirements-cloud.txt` in favor of unified `requirements.txt`
- **Multiple venvs** — no longer need separate `mcp-env`, `cloud-env`, or `mastering-env` directories

## [0.39.0] - 2026-02-05

### Added
- **Setup skill** — `/bitwize-music:setup` detects Python environment, checks dependencies, and provides installation commands specific to your system (externally-managed vs user-managed Python)
- **Session start setup check** — automatic MCP dependency verification on session start with immediate setup guidance if missing

### Changed
- **MCP server naming** — renamed `bitwize-music-state` → `bitwize-music-mcp` to support future MCP tools beyond state cache
- **MCP error handling** — improved dependency error message with user-install, pipx, and venv instructions for externally-managed Python environments
- **MCP documentation** — added setup instructions to README and server README for Ubuntu/Debian systems

## [0.38.0] - 2026-02-05

### Added
- **MCP server: bitwize-music-state** — bundled MCP server exposing state cache as tools for instant structured responses. Wraps `tools/state/indexer.py` with 9 tools: `find_album`, `list_albums`, `get_track`, `get_session`, `update_session`, `rebuild_state`, `get_config`, `get_ideas`, `get_pending_verifications`. In-memory caching with lazy loading and staleness detection. Server auto-starts when plugin enabled via `.mcp.json`. Requires Python 3.10+, `mcp[cli]>=1.2.0`.
- **Plugin tests: SKILL.md structure validation** — checks all skills have required sections (task description, procedural content, closing guidance, agent title). Accepts common alternatives (## Workflow, ## Step 1, ## Commands, ## Domain Expertise, etc.). Runs as part of pre-commit check #11.
- **CI: plugin tests job** — runs full `run_tests.py` suite (449 tests) in CI, guarded against fork PRs
- **Suno: v5-best-practices.md updates** — Personas workflow, Song Editor, bar count targeting, Creative Sliders, prompt fatigue warning (4-7 descriptor sweet spot), token biases, WMG ownership/licensing, V4.5 comparison note
- **Suno: tips-and-tricks.md updates** — Personas+Covers combo, Song Editor reference, Creative Sliders, catalog protection warning
- **Suno: voice-tags.md updates** — V5 Voice Gender selector, sustained notes technique, emotion arc mapping
- **Suno: structure-tags.md updates** — bar count targeting syntax, performance cues rule, V5 reliability improvements
- **Suno: pronunciation-guide.md updates** — V5 context sensitivity note, IPA not supported, numbers guidance, multilingual track isolation
- **Suno: instrumental-tags.md updates** — Producer's Prompt narrative approach, tag soup warning

### Fixed
- **Plugin manifest: duplicate hooks reference** — removed explicit `hooks/hooks.json` reference from plugin.json since it's loaded automatically by Claude Code

## [0.37.1] - 2026-02-04

### Changed
- **CI: SHA-pinned action references** — all workflow `uses:` directives now reference exact commit SHAs instead of mutable version tags (checkout v4.3.1, setup-python v5.6.0)
- **CI: fork PR protection** — `test` and `lint` jobs skip for fork PRs to prevent untrusted code execution via modified requirements/test files
- **CI: security gates tests** — unit tests now depend on `security` job (pip-audit) completing first
- **CI: explicit read-only permissions** — all non-release workflows now declare `permissions: { contents: read }`
- **CI: GITHUB_OUTPUT delimiter syntax** — all output variables use heredoc delimiters to prevent injection via newlines
- **CI: dead code fix** — model-updater curl error message now reachable under `set -e`
- **CI: fixed-string grep** — auto-release uses `grep -qF` so semver dots aren't regex wildcards
- **CI: heredoc replaced with printf** — model-updater PR body uses `printf %s` instead of unquoted heredoc for variable expansion

## [0.37.0] - 2026-02-04

### Added
- **Security: temp file cleanup** — atexit handlers and `0o600` permissions on temp files in promo video generators
- **Security: path traversal validation** — `Path.relative_to()` containment checks in mastering tools
- **Security: state cache permissions** — `0o700` on cache directory, `0o600` on temp files in indexer
- **Security: album name validation** — character validation before `rglob` in cloud uploader prevents glob injection
- **Security: CI model-updater hardening** — character whitelist and length validation on fetched model IDs
- **Security: session input validation** — length limits, null byte checks, action count cap in state indexer
- **Mastering: pre-flight check** — new Step 1 verifies WAV files exist before mastering workflow
- **Album-conceptualizer: type decision criteria** — guidance for choosing between Documentary, Character Study, Thematic
- **Album-conceptualizer: energy mapping example** — concrete visual example and pacing problems checklist
- **Resume: Research Phase** — suggests `/researcher` and `/document-hunter` for documentary albums
- **Checkpoint scripts: required actions** — action checklists before each checkpoint message template
- **Source verification: human checklist** — 6 concrete items for verifying sources (URL, quotes, dates, context, etc.)
- **Pronunciation guide: enforcement workflow** — full table enforcement process, verification format, rules
- **Researcher: evidence chain format** — example documentation format for connecting sources

### Changed
- **Lyric-reviewer: homograph handling unified** — now verifies decisions from lyric-writer instead of independently re-determining pronunciation (fixes contradiction)
- **Lyric-reviewer: 13-point checklist** — added section length, rhyme scheme, density/pacing, verse-chorus echo checks (was 9)
- **Suno-engineer: parenthetical contradictions fixed** — removed instructions to use parentheticals in lyrics box (Suno sings them)
- **Suno-engineer: genre specificity guidance** — added 2-3 descriptor limit with "too much" anti-pattern example
- **Suno-engineer: album context lookup** — explicit instructions for finding album README from track path
- **Bass homograph standardized** — `bayss` (music) across lyric-writer, lyric-reviewer, pronunciation-specialist
- **New-album: documentary parsing** — documents both 2-arg and 3-arg formats, always asks about true-story status
- **Pronunciation-specialist: standard Override Support section** — restructured to match pattern used by other skills
- **Researcher: state cache + Glob approach** — replaced `find`/`cat` commands with state cache lookup per CLAUDE.md
- **Researcher: smart album detection** — checks for single in-progress album before asking user
- **Mastering-engineer: version-safe plugin detection** — `[0-9]*` pattern replaces `0.*` (works post-1.0)
- **Mastering-engineer: step renumbering** — 6 steps with new pre-flight check
- **Lyric-writer: trim strategy** — specific guidance on what to cut when sections exceed limits
- **Lyric-writer: pronunciation check split** — table enforcement elevated from parenthetical to explicit sub-item
- **Lyric-writer: twin verses example** — concrete before/after showing reworded vs developing V2
- **Track template: pronunciation enforcement note** — bold warning that table is mandatory checklist, not documentation
- **Track template: keeper marker documented** — explains ✓ in Generation Log Rating column
- **Album template: verification deduplication** — removed per-track table, points to track files as single source of truth
- **Album template: art filename convention** — documents expected filenames and locations for album art
- **Suno LUFS targets clarified** — renamed section, added note these are Suno outputs not mastering targets
- **Style Prompt terminology standardized** — consistent "Style Prompt" (content) vs "Style Box" (UI) across Suno docs
- **Test skill: section renumbering** — fixed duplicate section 9, renumbered 10-14
- **Resume: plugin root resolution** — explains how to find plugin directory when state cache needs rebuild
- **Clipboard: shell-safe example** — `printf '%s'` replaces `echo` for lyrics with special characters
- **Cross-references added** — release-procedures→distribution.md, error-recovery→mastering-workflow.md
- **Homograph drift prevention** — canonical source notes added to all 3 skills with homograph tables
- **Researcher sub-skills: override inheritance** — all 10 sub-skills now reference parent override preferences

## [0.36.0] - 2026-02-03

### Added
- **CI: CLAUDE.md size check** — validates CLAUDE.md stays under 40K characters (matches pre-commit hook)
- **CI: Skill frontmatter validation** — validates required fields (name, description, model) and model ID format pattern
- **Reference: status-tracking.md** — new reference doc for track/album status workflows (split from CLAUDE.md)

### Changed
- **CLAUDE.md trimmed** — reduced from 40.2K to 33.2K chars by moving skills table to SKILL_INDEX.md, lyrics checklist to lyric-writer SKILL.md, and status tracking to reference file
- **Model validation uses pattern** — skill frontmatter check now uses regex `^claude-(opus|sonnet|haiku)-\d+-\d+-\d{8}$` instead of hardcoded model IDs, allowing new model versions without updating checks
- **Plugin tests check SKILL_INDEX.md** — skill documentation test now checks SKILL_INDEX.md instead of CLAUDE.md (since skills table was moved there)

## [0.35.0] - 2026-02-03

### Added
- **`tools/shared/media_utils.py`** — shared module for color extraction, audio analysis, and ffmpeg helpers (extracted from promotion tools)
- **`tools/shared/text_utils.py`** — shared module for track naming utilities (extracted from sheet-music tools)

### Fixed
- **Bare `except:` clauses** — replaced 6 instances across sheet-music tools with specific exception types (`FileNotFoundError`, `subprocess.SubprocessError`, `TypeError`, etc.)
- **Unguarded `import yaml`** — added `try/except ImportError` with helpful message in `create_songbook.py` and `transcribe.py` to match project convention
- **Dead code** — removed unused `above_thresh`/`mask` duplication in `master_tracks.py:soft_clip()`, removed unused `BG_COLOR`/`WAVEFORM_COLOR` constants from promotion tools
- **Unused import** — removed `ProgressBar` import from `reference_master.py`
- **Resource leak** — `generate_album_sampler.py` now uses `Image.open()` as context manager
- **Broad exception handling** — narrowed `except Exception` to specific types in `create_songbook.py`

### Changed
- **Deduplicated promotion tools** — extracted 7 functions from `generate_promo_video.py` and `generate_album_sampler.py` into `tools/shared/media_utils.py` (-274 lines)
- **Deduplicated mastering tools** — `fix_dynamic_track.py` now imports `apply_eq` and `soft_clip` from `master_tracks.py` (gains safety guards: Nyquist, Q factor, stability checks)
- **Deduplicated sheet-music tools** — `strip_track_number` extracted to `tools/shared/text_utils.py`
- **PR template** — fixed Co-Authored-By from "Claude Sonnet 4.5" to "Claude Opus 4.5"
- **Skill counts** — fixed Sonnet (21→22) and Haiku (11→10) counts in `model-strategy.md` and `SKILL_INDEX.md`
- **README.md** — fixed stale `paths.yaml` reference to `~/.bitwize-music/config.yaml`, removed false `content_root` default claim
- **CONTRIBUTING.md** — added `SKILL_INDEX.md` and `model-strategy.md` to new skill checklist, clarified version bumps happen at release time

## [0.34.1] - 2026-02-03

### Fixed
- **Mastering summary crash** — `master_tracks.py` summary section crashed with `TypeError` when unpacking `(name, dict)` tuples as plain dicts
- **Album sampler crossfade offsets** — `concatenate_with_crossfade` hardcoded 12-second clip duration instead of using actual `--clip-duration` value, causing audio gaps/overlaps
- **ffprobe crash on failure** — `get_audio_duration` in promo video and album sampler tools now checks `returncode` before parsing output
- **CI expression injection** — moved all `${{ steps.*.outputs.* }}` interpolations in `auto-release.yml` and `model-updater.yml` into `env:` blocks to prevent shell injection via crafted inputs
- **Broad `git add -A` in model-updater** — replaced with targeted file additions to prevent accidental staging of temp files
- **`echo -e` portability** — replaced with `printf '%b'` in model-updater workflow
- **Release notes `echo` fragility** — replaced with `printf '%s\n'` in auto-release to avoid flag interpretation

## [0.34.0] - 2026-02-02

### Added
- **Python version matrix** — CI tests now run across Python 3.9, 3.10, 3.11, 3.12 with pip caching
- **Security scanning** — bandit static analysis in lint job, pip-audit dependency audit as new security job
- **Mastering tests in CI** — 47 mastering tests now run in the test pipeline alongside state/shared tests

### Fixed
- **Path traversal prevention** — upload_to_cloud.py and transcribe.py validate resolved paths stay within expected roots
- **Atomic state writes** — indexer.py uses tempfile + fsync to prevent corruption on crash
- **Python 3.9 compatibility** — `Path | None` → `Optional[Path]` in master_tracks.py
- **analyze_tracks divide-by-zero** — guard total_energy division in spectral analysis
- **Model updater safety** — validates model ID date format and skips downgrades

### Changed
- **Documentation sanitized** — replaced real album names with generic examples across 19 files

## [0.33.0] - 2026-02-01

### Added
- **Pronunciation Table Enforcement rule** — every entry in a track's Pronunciation Notes table must be applied as phonetic spelling in Suno lyrics. The table is a checklist of required substitutions, not documentation. Added full process, verification format, common failures, and anti-pattern examples to lyric-writer SKILL.md. Added to quality check #3 and pitfalls checklist.

## [0.32.0] - 2026-02-01

### Changed
- **CLAUDE.md deduplicated and trimmed to under 40KB** — consolidated 4 checkpoint sections into single table, slimmed Model Strategy to table with doc reference, condensed Lessons Learned, removed redundant sections (Quick Reference, Using Skills for Research, standalone Watch Your Rhymes, CORRECT APPROACH block). No information lost — all content consolidated or referenced elsewhere.

## [0.31.0] - 2026-02-01

### Changed
- **Verse-chorus echo check** replaces chorus lead-in rule — expanded from single-line check to full phrase deduplication. Now compares last 2 lines of every verse against first 2 lines of the chorus, flagging exact phrases, shared rhyme words, restated hooks, and shared signature imagery. Covers all verse-to-chorus and bridge-to-chorus transitions.

## [0.30.0] - 2026-02-01

### Added
- **No Invented Contractions rule** — Suno only handles standard pronoun/auxiliary contractions (they'd, wouldn't). Invented forms (signal'd, TV'd, network'd) will mispronounce or skip. Added to Pronunciation section, quality check #3, and pitfalls checklist.

## [0.29.0] - 2026-02-01

### Changed
- **Density/pacing reframed as Suno verse length limits** — replaced abstract syllable-density metrics with practical line counts per verse by genre and BPM. All 67 genre READMEs updated to `Density/pacing (Suno)` with default lines/verse, max safe limits, and BPM-aware guidance.
- **New BPM-aware fallback table** — universal verse length limits when genre README doesn't specify (4 lines at <80 BPM, 6 at 94-110, 6-8 at 110-140)
- **Default 4 lines/verse** unless genre and tempo justify more — shifted from permissive 8-line defaults to conservative 4-line baseline
- **Red flag: 8-line verse at BPM under 100** — now flagged as too dense for Suno
- **Streaming lyrics exception** documented — distributor text can have longer blocks but breaks must match Suno structure
- **Quality check #10 now hard fail** — trim or split any verse over the genre's Suno limit before presenting

## [0.28.0] - 2026-02-01

### Added
- **Genre-specific lyric density/pacing norms** — all 67 genre READMEs now include density character, syllables/line range, max topics/verse, typical BPM, and genre-specific pacing notes under Lyric Conventions
- **Chorus lead-in rule** — the line before a chorus must not duplicate the chorus hook, phrase, or rhyme word. Prevents flat chorus entries.
- **Quality checks expanded to 12** — #10 density/pacing (genre-aware), #11 chorus lead-in, #12 pitfalls checklist
- **4 new pitfalls checklist items** — verse too dense for BPM, too many proper nouns per verse, density mismatch with Musical Direction, chorus lead-in repeats chorus

### Changed
- **Lyric density architecture**: Genre READMEs now own density/pacing norms. SKILL.md keeps universal rules + quick-reference table by genre family.

## [0.27.0] - 2026-02-01

### Added
- **Lessons Learned Protocol** — 5-step process for turning production issues into preventive rules. When technical issues are discovered (pronunciation errors, rhyme violations, formatting problems), fix immediately, sweep the album, draft a rule, present to user, and log the lesson.

## [0.26.0] - 2026-02-01

### Added
- **Strict homograph handling for Suno pronunciation** — "context is clear" is never acceptable for homographs. Hard process: identify, ASK user (never guess), fix with phonetic spelling in Suno lyrics only, document in track pronunciation table.
- **Full homograph table** — live, read, lead, wound, close, bass, tear, wind with both pronunciations and phonetic spellings

## [0.25.0] - 2026-02-01

### Added
- **Genre-specific lyric conventions for all 67 genres** — research-backed rhyme schemes, verse structures, rhyme quality expectations, key rules, and anti-patterns added to every genre README under a new "Lyric Conventions" section
- **Genre-aware quality checks** — rhyme scheme check (#8) and flow check (#9) now verify conventions match the genre instead of enforcing hip-hop couplets universally
- **Quick-reference rhyme table in lyric-writer** — compact summary of all genre families' default schemes, replacing 190 lines of inlined genre tables with a pointer to genre READMEs

### Changed
- **Architecture**: Genre READMEs now own lyric conventions (rhyme, structure, rules). Lyric-writer SKILL.md keeps universal craft rules + quick-reference table.

## [0.24.0] - 2026-02-01

### Added
- **Section length guardrails by genre** — per-section line limits for 12 genre families (all 67 genres) to prevent Suno from rushing, compressing, or skipping lyrics. Covers Hip-Hop, Pop, Rock, Punk, Metal, Country/Folk, Electronic, Ambient, R&B, Jazz, Reggae, and Ballad.
- **Section length enforcement rules** — hard limits that must be trimmed before presenting drafts (hip-hop verse max 8 lines, any chorus max 6 lines, electronic verse max 6 lines, punk kept tight)
- **Section length added to quality checks** — now check #7 in both lyric-writer Automatic Quality Check and CLAUDE.md master workflow, plus added to Lyric Pitfalls Checklist

## [0.23.0] - 2026-01-31

### Added
- **Song length guidance for lyric writer** — word count targets by genre (150–250 pop, 200–350 rock/folk, 300–500 hip-hop), default structure (2 verses + chorus + bridge), and hard limits to prevent 800+ word songs that cause Suno to rush or skip sections
- **Length check added to lyric reviewer** — 9-point checklist (was 8-point) now includes word count validation with warning/critical severity levels
- **Suno best practices updated** — "Keep Lyrics Concise" note in Lyric Formatting section explaining shorter lyrics generate better results

## [0.22.0] - 2026-01-31

### Added
- **3 documentary/storytelling hip-hop deep-dives** — focused on narrative architecture, political documentary craft, and storytelling technique:
  - **Kendrick Lamar** — concept album mastery, vocal personas, jazz-funk-West Coast fusion, nonlinear timelines (GKMC, TPAB, DAMN., GNX)
  - **Run the Jewels** — El-P/Killer Mike dual-MC interplay, industrial political hip-hop, humor + protest balance (RTJ1-4)
  - **Immortal Technique** — politically charged documentary rap, "Dance with the Devil" narrative craft, fierce independence
- Hip-hop genre INDEX.md and README.md updated with all 3 artists

### Fixed
- **Removed artist/person names from Suno prompt keywords** in Ben Folds deep-dives — replaced "Ben Folds Five style", "Ben Folds solo style", "Ben Folds style", "Paul Buckmaster strings", "Nick Hornby storytelling", and "yMusic chamber rock" with descriptive style keywords (both deep-dive files and piano-rock INDEX.md)

## [0.21.1] - 2026-01-31

### Added
- **46 artist deep-dives** across 11 genres — comprehensive reference files (265-554 lines each) with overview, members, discography, musical analysis, Suno prompt keywords, and reference tracks:
  - **Punk** (8 new): Bad Religion, Blink-182, Descendents, Me First and the Gimme Gimmes, Mest, Propagandhi, Rancid, The Offspring
  - **Rock** (9): Fountains of Wayne, Hoobastank, Incubus, Jeff Buckley, Linkin Park, Phil Collins, Polaris, Toto, Weezer
  - **Country** (9): Alan Jackson, Dolly Parton, Garth Brooks, George Strait, Johnny Cash, Randy Travis, Sturgill Simpson, Tyler Childers, Willie Nelson
  - **Synthwave** (4): FM-84, GUNSHIP, The Midnight, Timecop1983
  - **Piano-Rock** (2): Billy Joel, Elton John
  - **Pop** (2): Carly Rae Jepsen, Taylor Swift
  - **Folk** (2): Israel Kamakawiwo'ole, Mumford & Sons
  - **Celtic-Punk** (1): Dropkick Murphys
  - **Electronic** (1): Daft Punk
  - **Hip-Hop** (1): Brock Berrigan
  - **Ambient** (1): Enya
- **11 genre INDEX.md files** — lightweight keyword indexes for all genres with deep-dives (rock, country, synthwave, electronic, folk, celtic-punk, hip-hop, ambient, pop); punk and piano-rock indexes expanded with new artists
- **Genre README updates** — Deep Dive and Keywords links added to artist tables across all 11 genres; Garth Brooks added to country README

## [0.21.0] - 2026-01-31

### Added
- **Artist reference indexes** — New `genres/[genre]/artists/INDEX.md` files for punk (127 lines) and piano-rock (84 lines) providing extracted Suno prompt keywords and reference tracks without loading full deep-dives (~2,900 lines across 6 files)
- **Lazy-loading guidance in CLAUDE.md** — New rule: read `artists/INDEX.md` first for Suno keywords; only read full deep-dive when detailed history/analysis is needed

### Changed
- **Genre README Artists tables** — Deep Dive column now includes `[Keywords]` shortcut links to INDEX.md alongside existing deep-dive links (punk, piano-rock)
- **CLAUDE.md directory structure** — Added `INDEX.md` to both plugin and content directory trees; updated deep-dive creation rule to require INDEX.md updates

## [0.20.2] - 2026-01-31

### Added
- **Genre overview files** — New genre READMEs for piano-rock, piano-pop, and singer-songwriter (67 genres total, up from 64)
- **Artist deep-dive references** — 6 comprehensive artist files in `genres/[genre]/artists/`:
  - `punk/artists/nofx.md` — Members, 15 albums, Fat Wreck Chords, farewell tour, Suno keywords
  - `punk/artists/lagwagon.md` — Members, 9 albums, Derrick Plourde, Tony Sly, Joey Cape solo work
  - `punk/artists/green-day.md` — Members, 14 albums, Gilman Street, American Idiot phenomenon
  - `punk/artists/masked-intruder.md` — Anonymous concept, 3 albums, gimmick analysis
  - `piano-rock/artists/ben-folds-five.md` — Members, 4 albums, Chapel Hill scene, production
  - `piano-rock/artists/ben-folds-solo.md` — 8 solo albums, orchestral work, collaborations

### Changed
- **Genre directory structure** — Artist deep-dives now live in `genres/[genre]/artists/` subdirectories instead of alongside genre READMEs
- **Genre README Artists tables** — Added "Deep Dive" column with links to artist reference files (punk, piano-rock)
- **CLAUDE.md** — Added `genres/` to plugin root directory tree, documented `artists/` subdirectory pattern, added deep-dive linking rule to Key Rules

## [0.20.1] - 2026-01-30

### Changed
- **README** — Added Claude Code Max plan ($200/month) recommendation callout for new users

## [0.20.0] - 2026-01-29

### Added
- **Python logging module** across all 15 tool files — `tools/shared/logging_config.py` with `ColorFormatter` (TTY-aware colored output via `Colors` class) and `setup_logging()`. Errors/warnings/status go to stderr via `logger`, formatted tables and data summaries stay as `print()`. `--verbose`/`--quiet` CLI flags added where argparse exists.
- **Progress indicators** — `tools/shared/progress.py` with `ProgressBar` class (TTY-aware █/░ bar). Added to 7 batch-processing tools: `master_tracks.py`, `analyze_tracks.py`, `reference_master.py`, `upload_to_cloud.py`, `generate_promo_video.py`, `generate_album_sampler.py`, `transcribe.py`.
- **Retry logic for cloud uploads** — `retry_upload()` in `upload_to_cloud.py` with exponential backoff (1s/2s/4s), `--retries` CLI arg (default: 3). Retries on `ClientError` (except 403/404), `ConnectionError`, `Timeout`.
- **Concurrent processing** — `-j`/`--jobs` CLI arg in 4 tools: `master_tracks.py` and `analyze_tracks.py` (`ProcessPoolExecutor`), `transcribe.py` and `generate_promo_video.py` (`ThreadPoolExecutor`). Default: 1 (sequential), 0 = auto (CPU count).
- **State cache cleanup command** — `python tools/state/indexer.py cleanup` removes albums from cache whose paths no longer exist on disk. Supports `--dry-run`.
- **New shared modules** — `tools/shared/logging_config.py`, `tools/shared/progress.py`, `tools/shared/__init__.py`
- **Test coverage improvements** — 180 tests (up from 137), 91% coverage. New test files: `test_logging_config.py` (13 tests), `test_progress.py` (14 tests). New test classes in `test_indexer.py`: `TestCmdCleanup`, `TestCmdRebuild`, `TestCmdValidate`, `TestCmdShow`, `TestCmdUpdate`. Edge case tests added to `test_parsers.py`.
- **Dev tooling** — `requirements-test.txt` (pytest, pyyaml, ruff, pytest-cov), `ruff.toml` config, CI workflow updated with test and lint jobs

## [0.19.3] - 2026-01-29

### Changed
- **Venv-first messaging** across all tools and skills — error messages in `upload_to_cloud.py` and `generate_promo_video.py` now show venv setup commands instead of bare `pip install`. Cloud-uploader and promo-director SKILL.md docs updated to present venv as the primary (not alternative) approach.

## [0.19.2] - 2026-01-29

### Fixed
- **Cloud upload album discovery** in `upload_to_cloud.py` — added recursive glob fallback when standard flat path (`{audio_root}/{artist}/{album}`) doesn't exist. Handles audio directories that mirror the content structure with genre folders (e.g., `artists/bitwize/albums/rock/shell-no/`). Reports all checked paths on failure.

## [0.19.1] - 2026-01-29

### Fixed
- **Cloud upload path resolution** in `upload_to_cloud.py` — when `--audio-root` override already includes the artist path, the script no longer doubles it (e.g., `.../bitwize/albums/rock/bitwize/shell-no`). Now tries standard path first, then falls back to direct `{override}/{album}` lookup.

## [0.19.0] - 2026-01-29

### Added
- **Per-feature requirements files** - Install only what you need:
  - `requirements-mastering.txt` - Audio mastering (matchering, pyloudnorm, scipy, numpy, soundfile)
  - `requirements-promo.txt` - Promo videos (pillow, librosa)
  - `requirements-sheet-music.txt` - Sheet music (pypdf, reportlab, pyyaml)
  - `requirements.txt` - Cloud uploads (boto3)
  - `requirements-research.txt` - Document hunting (playwright)
- **Model tier consistency test** in `run_tests.py` - Validates SKILL.md model assignments match model-strategy.md, reports tier distribution, detects `disable-model-invocation` flags
- **Cross-references** added to reference docs (v5-best-practices, distribution, pronunciation-guide, checkpoint-scripts) linking related skills and docs
- **Task-oriented guide table** in `reference/suno/README.md` - "When to Use Which Guide" quick lookup

### Fixed
- **Security: ffmpeg command injection** in `generate_promo_video.py` - Switched from `text=` (injectable via title/artist strings) to `textfile=` parameter with temp files
- **Silent audio crash** in `master_tracks.py` - Added guards for `-inf` LUFS from silent/near-silent audio, skips instead of crashing
- **Case-insensitive WAV discovery** in `master_tracks.py` - Now finds `.WAV` and `.wav` files
- **PIL file handle leak** in `generate_promo_video.py` - `Image.open()` now uses `with` block
- **Shallow copy bug** in `indexer.py` - `existing_state.copy()` replaced with `copy.deepcopy()` to prevent nested dict mutation
- **Race conditions** in `indexer.py` - Added `try/except OSError` around 4 `stat()` calls where files could be deleted between glob and stat
- **Whitespace in Suno Link parsing** in `parsers.py` - Added `.strip()` and en-dash to exclusion list
- **Sources Verified false positive** in `parsers.py` - Reordered matching to check "pending" before "verified", preventing "NOT verified" matching as verified
- **Model tier test substring matching** in `run_tests.py` - Used exact `### heading` regex instead of substring match (prevented "about" matching in prose, "researcher" matching "researchers-legal")

### Changed
- **SKILL_INDEX.md** realigned all 38 skills with model-strategy.md (added missing Opus/Sonnet skills, corrected tier assignments)
- **Album template** (`templates/album.md`) - Replaced hardcoded artist text with generic guidance, renamed distributor heading
- Removed `disable-model-invocation: true` from `release-director` and `skill-model-updater` skills
- Test runner timeout now configurable via `BITWIZE_TEST_TIMEOUT` env var (default: 60s)
- Removed redundant `import re` in `run_tests.py`

## [0.18.0] - 2026-01-29

### Added
- **State cache layer** (`tools/state/`) - JSON index of all project state for fast session startup
  - `parsers.py` - Markdown parsing functions for album READMEs, track files, IDEAS.md
  - `indexer.py` - CLI tool with `rebuild`, `update`, `validate`, `show`, `session` commands
  - State cached at `~/.bitwize-music/cache/state.json` (always rebuildable from markdown)
  - Schema versioning with migration chain for plugin upgrades
  - Atomic writes for crash safety
  - Incremental updates (only re-parse files with newer mtime)
- **`session` CLI command** for `indexer.py` - Update session context in state.json
  - `--album`, `--track`, `--phase` to set context
  - `--add-action` to append pending actions
  - `--clear` to reset session data
- **`__main__.py`** for `tools/state/` - Enables `python3 -m tools.state` invocation
- **State cache tests** - 57 tests across parsers and indexer
  - `test_parsers.py` - 29 unit tests including flexible column tracklist parsing
  - `test_indexer.py` - 28 integration tests for build, update, validate, migrate, session, script invocation
  - Test fixtures for album README, track files, and IDEAS.md
  - Regression tests: script invocation (`python3 tools/state/indexer.py --help`), module invocation, package invocation
- **State test category** in test runner (`/bitwize-music:test state`)
  - Validates state tool files exist
  - Checks schema version constant
  - Runs parser unit tests as subprocess

### Changed
- Session Start in CLAUDE.md now uses state cache instead of scanning markdown files
  - Reduces startup from 50-220 file reads to 2-3 file reads
  - Falls back to full rebuild if cache missing, corrupted, or schema changed
  - Shows last session context (album, phase, pending actions)
- Resume skill now reads from state cache instead of glob + individual file reads
  - Reduces per-invocation from 15-50 file reads to 1-2 file reads
  - Updates session context via `indexer.py session` command
  - Includes optional staleness check with incremental update
- CLAUDE.md "Finding Albums" section now references state cache as primary lookup before Glob fallback
- CLAUDE.md "Resuming Work" section updated to describe state cache workflow
- CLAUDE.md Session Start step 2 uses full `python3 {plugin_root}/tools/state/indexer.py` paths consistently

### Fixed
- **Critical**: `indexer.py` now runnable as `python3 tools/state/indexer.py` (was failing with `ModuleNotFoundError`)
  - Added `sys.path` fixup at top of file (same pattern as test files)
  - CLAUDE.md and resume SKILL.md both documented the broken form
- `documents_root` default now derives from `content_root` instead of CWD
  - `audio_root` default also derives from `content_root`
  - Prevents wrong paths when running from a different directory
- Tracklist parser now handles variable column counts (3+ columns)
  - Previously required exactly 5 columns; silently returned 0 tracks if template changed
  - Extracts track number (first col), title (second col), status (last col)
  - Emits warning if Tracklist section exists but no rows matched
- `state.session` was dead code — no write mechanism existed
  - Added `session` CLI command to `indexer.py`
  - Resume skill step 5 now calls `indexer.py session` to persist context

## [0.17.1] - 2026-01-28

### Changed
- Revised model assignments for 6 skills with comprehensive rationale for all 38 skills
  - Promoted to Opus: album-conceptualizer, lyric-reviewer
  - Promoted to Sonnet: pronunciation-specialist, explicit-checker
  - Moved to Haiku: skill-model-updater, test
- Simplified skill-model-updater to auto-detect tiers from existing model fields instead of maintaining a hardcoded tier list
- Updated model-strategy.md with per-skill rationale and decision framework

## [0.17.0] - 2026-01-28

### Added
- **Test automation runner** (`tools/tests/run_tests.py`) - Validates skills, templates, references, links, terminology, consistency
- **Genre INDEX.md** - Searchable, categorized guide to all 64 genres with quick reference tables
- **Quick-start guides** (`reference/quick-start/`) - first-album.md, true-story-album.md, bulk-releases.md
- **Override documentation** (`reference/overrides/`) - how-to-customize.md, override-index.md
- **Release documentation** (`reference/release/`) - platform-comparison.md, distributor-guide.md, metadata-by-platform.md, rights-and-claims.md
- **Cross-platform guides** (`reference/cross-platform/`) - wsl-setup-guide.md, tool-compatibility-matrix.md
- **Model strategy documentation** (`reference/model-strategy.md`) - Complete rationale for skill model assignments
- **Terminology glossary** (`reference/terminology.md`) - Standardized definitions for all key terms
- **Skill index** (`reference/SKILL_INDEX.md`) - Decision tree, prerequisites, skill sequences
- **Mastering reference docs** - genre-specific-presets.md, loudness-measurement.md, mastering-checklist.md
- **Sheet music reference docs** - genre-recommendations.md, troubleshooting.md
- **Workflow docs** - importing-audio.md
- **Skill supporting docs** for clipboard, album-ideas, configure, help, about
- **Researcher skill guides** for all 10 specialized researchers (legal, gov, journalism, security, financial, historical, biographical, tech, primary-source, verifier)

### Changed
- Expanded error-recovery.md from 52 to 316 lines with 12 detailed recovery scenarios
- Enhanced config.example.yaml with comprehensive inline documentation and platform examples
- Updated CLAUDE.md model strategy section to reference new documentation

## [0.16.0] - 2026-01-28

### Added
- Enhanced all 64 genre documentation files to Gold standard quality
  - 3+ paragraph overviews with historical context and scene development
  - 8+ subgenres with detailed descriptions and reference artists
  - 12+ artists with filled tables (no placeholder entries)
  - 12+ reference tracks with rich contextual descriptions
  - Comprehensive Suno prompt keywords for AI music generation
  - Coverage spans origins through modern revival movements

## [0.15.0] - 2026-01-28

### Added
- Example override files in `config/overrides.example/` for all 11 documented overrides
  - CLAUDE.md, pronunciation-guide.md, suno-preferences.md, lyric-writing-guide.md
  - explicit-words.md, mastering-presets.yaml, album-planning-guide.md
  - album-art-preferences.md, research-preferences.md, release-preferences.md
  - sheet-music-preferences.md
- `requirements:` field in skill frontmatter for skills with external dependencies
  - mastering-engineer, promo-director, document-hunter, cloud-uploader
- Test to verify skills with external deps have requirements field
- Root `requirements.txt` consolidating all Python dependencies by feature (mastering, promo videos, sheet music, cloud uploads, document hunting)
- Regression test for README skill count matching actual skill directory count
- Regression test to prevent accidental skill.json files (standard is SKILL.md)
- Genre validation test to catch mismatched genre references
- "What's New" section in README showing recent version highlights

### Changed
- Replaced emojis with text indicators in all logging output ([OK], [FAIL], [WARN])
  - Python tools: generate_promo_video.py, validate_help_completeness.py, transcribe.py, create_songbook.py
  - GitHub workflows: test.yml, model-updater.yml, auto-release.yml, version-sync.yml
- Standardized co-author line in CONTRIBUTING.md to use "Claude Opus 4.5" (was inconsistently using Sonnet)

### Fixed
- README.md skill count corrected from 32 to 38
- Removed accidental `skill.json` from resume skill (SKILL.md is the standard format)

## [0.14.3] - 2026-01-27

### Changed
- Promo video titles now use Title Case instead of ALL CAPS when derived from filenames
- Album sampler now saved in `promo_videos/` folder alongside track promos (was at album root)
- Cloud uploader puts all promos in same folder (`{artist}/{album}/promos/`)

### Fixed
- Cloud uploader documentation clarifies flat path structure (no genre folder in cloud paths)
- Config README updated with all current settings (promotion, sheet_music, cloud sections)

## [0.14.2] - 2026-01-27

### Fixed
- Promo videos now read track titles from markdown frontmatter when `--album` specified
  - Uses actual title from `{content_dir}/tracks/*.md` instead of filename
  - Falls back to uppercase filename conversion if markdown not found
- Improved special character escaping for ffmpeg drawtext filter
  - Handles apostrophes, quotes, backticks, colons, semicolons, brackets, ampersands
  - Prevents ffmpeg errors on tracks with special characters in titles

## [0.14.1] - 2026-01-27

### Fixed
- Add missing YAML frontmatter to `promo-director` and `resume` skills (skills weren't appearing in Claude Code)
- Add `--batch-artwork` and `--album` flags to promo video generator for better artwork discovery
  - `--batch-artwork /path/to/art.png` - explicit artwork path
  - `--album my-album` - checks content directory for artwork via config
  - Better error messages showing where artwork was searched

## [0.14.0] - 2026-01-27

### Added
- `/bitwize-music:cloud-uploader` skill for uploading promo videos to Cloudflare R2 or AWS S3
  - Uses boto3 S3-compatible API (works with both R2 and S3)
  - Dry-run mode for previewing uploads
  - Public/private upload options
  - Path organization: `{bucket}/{artist}/{album}/promos/`
  - Comprehensive setup guide in `/reference/cloud/setup-guide.md`
  - Config section added to `config/config.example.yaml`

## [0.13.0] - 2026-01-26

### Added
- **promo-director skill**: Generate professional promo videos for social media from mastered audio
  - Creates 15-second vertical videos (9:16, 1080x1920) optimized for Instagram Reels, Twitter, TikTok
  - 9 visualization styles: pulse, bars, line, mirror, mountains, colorwave, neon, dual, circular
  - Automatic color extraction from album artwork (dominant + complementary colors)
  - Intelligent audio segment selection using librosa (falls back to 20% into track)
  - Batch processing: individual track promos + album sampler video
  - Config integration: reads artist name from `~/.bitwize-music/config.yaml`
  - Robust artwork detection: finds album.png, album-art.png, artwork.png, cover.png, etc.
  - Multi-font path discovery (works on Linux/macOS)
  - Platform-optimized output: H.264, AAC, yuv420p, 30fps
  - Album sampler with crossfades (fits Twitter's 140s limit)
- **Promo video tools**: 3 Python scripts in `tools/promotion/`
  - `generate_promo_video.py` - Core video generator with 9 styles
  - `generate_album_sampler.py` - Multi-track sampler video
  - `generate_all_promos.py` - Batch wrapper for complete campaigns
- **Promo video documentation**:
  - `skills/promo-director/SKILL.md` - Complete skill workflow
  - `skills/promo-director/visualization-guide.md` - Style gallery with genre recommendations
  - `reference/promotion/promo-workflow.md` - End-to-end workflow guide
  - `reference/promotion/platform-specs.md` - Instagram, Twitter, TikTok, Facebook, YouTube specs
  - `reference/promotion/ffmpeg-reference.md` - Technical ffmpeg documentation
  - `reference/promotion/example-output.md` - Visual examples and benchmarks
  - `reference/promotion/promotion-preferences-override.md` - Override template
- **Config support for promo videos**: Added `promotion` section to `config/config.example.yaml`
  - `default_style` - Default visualization style (pulse, bars, etc.)
  - `duration` - Default video duration (15s, 30s, 60s)
  - `include_sampler` - Generate album sampler by default
  - `sampler_clip_duration` - Seconds per track in sampler (12s default)
- **Workflow integration**: Added promo videos as optional step 8 (between Master and Release)
  - Updated CLAUDE.md workflow: Concept → Research → Write → Generate → Master → **Promo Videos** → Release
  - Added to Album Completion Checklist
  - Added "Promo Videos (Optional)" section to CLAUDE.md
- **Plugin keywords**: Added promo-videos, social-media, video-generation to plugin.json
- **Skill documentation safeguards**: Added validation and documentation to prevent skills being forgotten
  - `tools/validate_help_completeness.py` - Cross-platform Python script that checks all skills are documented
  - Validates skills appear in CLAUDE.md skills table
  - Validates skills appear in skills/help/SKILL.md
  - Integrated into `/bitwize-music:test consistency` suite
  - Added "Adding a New Skill - Complete Checklist" to CONTRIBUTING.md with 15-item checklist
  - Lists all required files, recommended updates, testing steps, and common mistakes

### Changed
- **import-art compatibility**: All promo scripts now check for multiple artwork naming patterns
  - album.png, album.jpg (standard import-art output)
  - album-art.png, album-art.jpg (alternative from import-art content location)
  - artwork.png, artwork.jpg, cover.png, cover.jpg (fallbacks)
  - Scripts check both album directory and parent directory
  - Clear error messages when artwork not found

### Fixed

## [0.12.1] - 2026-01-26

### Fixed
- **Critical**: Fixed mastering-engineer skill to run scripts from plugin directory instead of copying them to audio folders
  - Scripts now use dynamic plugin path finding (version-independent)
  - Uses `find` command to locate latest plugin version automatically
  - Scripts invoked with audio path as argument instead of cd-ing to audio folder
  - Removed all instructions to copy scripts (cp command)
  - Added "Important: Script Location" section with CRITICAL warning
  - Added Common Mistakes section with 5 error patterns:
    - Don't copy scripts to audio folders
    - Don't hardcode plugin version number
    - Don't run scripts without path argument
    - Don't forget to activate venv
    - Don't use wrong path for mastered verification
  - Updated "Per-Album Session" workflow to use dynamic paths
  - Added regression test to prevent recurrence

**Root cause**: Previous documentation implied scripts lived in audio folder by saying "navigate to folder, run python3 analyze_tracks.py", causing Claude to copy scripts first. Plugin version numbers in cache path (0.12.0, 0.13.0, etc.) meant hardcoded paths would break after updates.

**Impact**: Audio folders now stay clean (only audio files), scripts always use latest version, plugin updates don't break mastering workflow.

## [0.12.0] - 2026-01-26

### Added
- **Quick Win #1**: Added `/bitwize-music:resume` skill to README.md Skills Reference table (Setup & Maintenance section)
- **Quick Win #2**: Comprehensive Troubleshooting section in README.md with 8 common issue categories
  - Config Not Found with setup instructions
  - Album Not Found When Resuming with debug steps
  - Path Resolution Issues with correct structure examples
  - Python Dependency Issues for mastering
  - Playwright Setup for document hunter
  - Plugin Updates Breaking Things
  - Skills Not Showing Up
  - Still Stuck? with GitHub issue link
- **Quick Win #3**: Getting Started Checklist in README.md with step-by-step setup instructions
  - Appears before Quick Start section for better onboarding flow
  - Includes all required steps: plugin install, config setup, optional dependencies
  - Each step has code examples and explanations
- **Quick Win #5**: Model Strategy section in README.md explaining Claude model usage
  - Table showing Opus 4.5 for critical creative outputs (lyrics, Suno prompts)
  - Sonnet 4.5 for most tasks (planning, research)
  - Haiku 4.5 for pattern matching (pronunciation scanning)
  - Rationale for model choices (quality vs cost optimization)
  - Reference to /skill-model-updater for checking models
- **Quick Win #6**: Visual workflow diagram in README.md "How It Works" section
  - ASCII box diagram showing full pipeline: Concept → Research → Write → Generate → Master → Release
  - Specific actions listed under each phase
  - Improves at-a-glance understanding of workflow
- **Quick Win #7**: Common Mistakes sections added to 4 path-handling skills
  - skills/new-album/SKILL.md: 5 mistake patterns (config reading, path construction, genre categories)
  - skills/import-audio/SKILL.md: 5 mistake patterns (artist in path, audio_root vs content_root)
  - skills/import-track/SKILL.md: 6 mistake patterns (tracks subdirectory, track number padding)
  - skills/import-art/SKILL.md: 6 mistake patterns (dual locations, filename conventions)
  - Each mistake includes Wrong/Right code examples and "Why it matters" explanation
  - 22 total mistake examples preventing most common path-related errors
- **Quick Win #9**: Enhanced config.example.yaml with inline examples throughout
  - Artist name examples ("bitwize", "my-band", "dj-shadow-clone")
  - Genre choice examples for each section
  - Path pattern examples (~/music-projects, ".", absolute paths)
  - Platform URL examples (Apple Music, Twitter added)
  - Notes about writability, file types, and use cases
  - All sections use "Examples:" or "Example:" format consistently
- **Quick Win #10**: Cross-references added to 4 key reference documentation files
  - reference/suno/pronunciation-guide.md: Related Skills and See Also sections
  - reference/suno/v5-best-practices.md: Related Skills and See Also sections
  - reference/suno/structure-tags.md: Related Skills and See Also sections
  - reference/mastering/mastering-workflow.md: Related Skills and See Also sections
  - Each cross-reference links to related skills and documentation for better navigation
- Test coverage: 15 new regression tests added to skills/test/SKILL.md
  - Tests for all 10 quick wins
  - Verifies README sections exist and have required content
  - Verifies template consistency
  - Verifies Common Mistakes sections in skills
  - Verifies config examples present
  - Verifies cross-references in reference docs

### Changed
- **Quick Win #4**: templates/ideas.md status values standardized from "Idea | Ready to Plan | In Progress" to "Pending | In Progress | Complete"
  - Now consistent with album-ideas skill documentation
  - Added status explanations (Pending: idea captured, In Progress: actively working, Complete: released or archived)

## [0.11.0] - 2026-01-26

### Added
- New `/bitwize-music:help` skill - comprehensive quick reference for all skills, workflows, and tips
  - Skills organized by category (Album Creation, Research, QC, Production, File Management, System)
  - Common workflow guides (new album, true-story albums, resuming work)
  - Quick tips reference (config, pronunciation, explicit content, mastering, status flows)
  - Key documentation paths
  - Getting help section with navigation tips
- Added help skill to CLAUDE.md skills table
- Added help skill to README.md Setup & Maintenance section

## [0.10.1] - 2026-01-26

### Fixed
- Removed reference to non-existent `/bitwize-music:help` skill in session startup productivity tips
- Updated tip to simply suggest asking "what should I do next?" for guidance

## [0.10.0] - 2026-01-26

### Added
- Session startup contextual tips system in CLAUDE.md
  - Smart, contextual one-liners based on detected user state
  - 6 conditional tip categories: tutorial (new users), album ideas, resume, overrides customization, overrides loaded confirmation, verification warning
  - 6 rotating general productivity tips for feature discovery
  - Tips show right feature at right time without overwhelming users
- Comprehensive test suite for session startup tips
  - Tests verify all 6 conditional tip categories are documented
  - Tests verify productivity tips reference actual skills
  - Tests verify correct skill command format
  - Tests verify path variables used instead of hardcoded paths

### Changed
- Session Start section in CLAUDE.md now shows contextual tips after status summary
- Session startup tips replace single static tip with comprehensive contextual guidance
- Final session startup prompt now asks "What would you like to work on?"

## [0.9.1] - 2026-01-26

### Changed
- Updated all documentation examples to use generic album names (my-album, demo-album) instead of "shell-no"
  - Changed examples in /resume skill documentation
  - Changed examples in CLAUDE.md "Finding Albums" section
  - Changed examples in "Resuming Work" section
  - Changed examples in "Creating a New Album" section

## [0.9.0] - 2026-01-26

### Added
- `/bitwize-music:resume` skill - Dedicated skill for resuming work on albums
  - Takes album name as argument
  - Reads config to get paths
  - Uses Glob to find album across all genre folders
  - Reads album README and track files to assess status
  - Determines current workflow phase (Planning, Writing, Generating, Mastering, etc.)
  - Reports detailed status: location, progress, what's done, next steps
  - Lists available albums if target album not found
  - Handles case-insensitive matching and album name variations
  - Usage: `/bitwize-music:resume shell-no`

### Changed
- CLAUDE.md "Finding Albums" section now recommends `/bitwize-music:resume` skill as the primary approach
- "Resuming Work on an Album" section updated to prioritize the resume skill
- Skills table: Added `/bitwize-music:resume` at the top
- Session Start tip now mentions `/bitwize-music:resume <album-name>` instead of tutorial resume

## [0.8.2] - 2026-01-26

### Added
- "Resuming Work on an Album" section in CLAUDE.md with explicit instructions for finding albums when user mentions them

### Changed
- Session Start step 4 now includes explicit instructions to use Glob tool to find album READMEs
- Clearer scanning instructions: find `{content_root}/artists/*/albums/*/*/README.md`, read each, report status

### Fixed
- Improved album discovery workflow - Claude now has clear step-by-step instructions for finding albums when user says "let's work on [album]"
  - Always read config first to get content_root and artist name
  - Use Glob to search for album README files
  - Read album and track files to assess current state
  - Report location, status, and next actions
  - Common mistakes highlighted (don't assume paths, don't guess genre folders, always search fresh)

## [0.8.1] - 2026-01-26

### Added
- `/clipboard` skill - Copy track content (lyrics, style prompts) to system clipboard
  - Cross-platform support: macOS (pbcopy), Linux (xclip/xsel), WSL (clip.exe)
  - Content types: lyrics, style, streaming-lyrics, all (combined Suno inputs)
  - Auto-detects platform and clipboard utility
  - Config-aware path resolution
  - Usage: `/clipboard <content-type> <album-name> <track-number>`
- Workflow reference documentation in `/reference/workflows/`
  - `checkpoint-scripts.md` - Detailed checkpoint message templates
  - `album-planning-phases.md` - The 7 Planning Phases detailed guide
  - `source-verification-handoff.md` - Human verification procedures
  - `error-recovery.md` - Edge case recovery procedures
  - `release-procedures.md` - Album art generation and release steps
- `/reference/distribution.md` - Streaming lyrics format and explicit content guidelines

### Changed
- **CLAUDE.md refactored for performance** - Reduced from 50,495 to 34,202 characters (32% reduction)
  - Compressed checkpoint sections - Kept triggers/actions, moved verbose messages to `/reference/workflows/checkpoint-scripts.md`
  - Condensed Audio Mastering section - Brief overview with reference to existing `/reference/mastering/mastering-workflow.md`
  - Condensed Sheet Music section - Summary with reference to `/reference/sheet-music/workflow.md`
  - Condensed Album Art Generation - Core workflow with reference to `/reference/workflows/release-procedures.md`
  - Condensed 7 Planning Phases - Summary with reference to `/reference/workflows/album-planning-phases.md`
  - Condensed Human Verification Handoff - Triggers with reference to `/reference/workflows/source-verification-handoff.md`
  - Condensed Error Recovery - Quick reference with link to `/reference/workflows/error-recovery.md`
  - Condensed Distribution Guidelines - Combined streaming lyrics and explicit content with reference to `/reference/distribution.md`
  - Simplified Creating Content sections - Condensed album creation and file import workflows
  - Simplified Suno Generation Workflow - Streamlined process description
  - Architecture: CLAUDE.md now focuses on workflow orchestration (WHEN/WHY), detailed procedures in reference docs (HOW)

## [0.8.0] - 2026-01-26

### Added
- **Complete override support for 10 skills** - All creative/stylistic skills now support user customization via `{overrides}` directory
  - `album-art-director` → `album-art-preferences.md` (visual style, color palettes, composition)
  - `researcher` → `research-preferences.md` (source priorities, verification standards, research depth)
  - `release-director` → `release-preferences.md` (QA checklist, platform priorities, metadata standards, timeline)
  - `sheet-music-publisher` → `sheet-music-preferences.md` (page layout, notation, songbook formatting)
  - Previously added (0.7.x): explicit-checker, lyric-writer, suno-engineer, mastering-engineer, album-conceptualizer, pronunciation-specialist
  - All skills follow unified override pattern: check `{overrides}/[skill-file]`, merge with base, fail silently if missing
  - Complete documentation in config/README.md with examples for all 10 override files
- `/album-ideas` skill - Track and manage album concepts before creating directories
  - Commands: list, add, remove, status, show, edit
  - Organize by status: Pending, In Progress, Complete
  - Config-based location: `paths.ideas_file` (defaults to `{content_root}/IDEAS.md`)
  - Creates template file automatically on first use
  - Integrated into session start workflow (step 3: check album ideas)

### Changed
- CLAUDE.md session start now checks album ideas file (step 3) and mentions `/album-ideas list` for details
- `/configure` skill now prompts for `paths.ideas_file` during setup
- config/README.md expanded with comprehensive override system documentation (10 skills, full examples)
- Skills table in CLAUDE.md now includes `/album-ideas` skill

### Fixed
- Tests updated to validate override support in all 10 skills and album-ideas commands

## [0.7.1] - 2026-01-26

### Changed
- **BREAKING**: Refactored customization system to use unified overrides directory
  - Replaced `paths.custom_instructions` with `paths.overrides`
  - Replaced `paths.custom_pronunciation` with `paths.overrides`
  - Single directory now contains all override files: `~/music-projects/overrides/`
  - Override files: `CLAUDE.md`, `pronunciation-guide.md`, `explicit-words.md` (future), etc.
  - Benefits: self-documenting, easy discovery, future-proof, convention over configuration
  - **Note**: Released immediately after 0.7.0 to fix design before user adoption

### Fixed
- Config design now scales for future overrides without new config fields

## [0.7.0] - 2026-01-26 **[DEPRECATED - Use 0.7.1]**

### Added
- Custom instructions support (`paths.custom_instructions` config field)
  - Load user's custom Claude workflow instructions at session start
  - Defaults to `{content_root}/CUSTOM_CLAUDE.md` if not set in config
  - Supplements (doesn't override) base CLAUDE.md
  - Optional - fails silently if file doesn't exist
  - Prevents plugin update conflicts for user workflow preferences
- Custom pronunciation guide support (`paths.custom_pronunciation` config field)
  - Load user's custom phonetic spellings at session start
  - Defaults to `{content_root}/CUSTOM_PRONUNCIATION.md` if not set in config
  - Merges with base pronunciation guide, custom entries take precedence
  - Optional - fails silently if file doesn't exist
  - pronunciation-specialist adds discoveries to custom guide, never edits base
  - Prevents conflicts when plugin updates base pronunciation guide
- Mandatory homograph auto-fix in lyric-reviewer
  - Automatically detects and fixes homographs based on context
  - Reference table of 8 common homographs with phonetic fixes
  - No longer asks user "Option A or B?" - applies fix immediately
  - Explicit anti-pattern warning in documentation

### Changed
- `/configure` skill now prompts for custom_instructions and custom_pronunciation paths during setup
- `/pronunciation-specialist` now loads and merges both base and custom pronunciation guides
- `/lyric-reviewer` pronunciation check now links to mandatory auto-fix section
- CLAUDE.md session start procedure now loads custom instructions and custom pronunciation files
- Self-updating skills documentation clarified: pronunciation-specialist updates custom guide only

### Fixed

## [0.6.1] - 2026-01-25

### Added

### Changed

### Fixed
- Auto-release workflow now extracts release notes from versioned section instead of [Unreleased]

## [0.6.0] - 2026-01-25

### Added

### Changed
- CHANGELOG.md is now manually maintained (no automated commits) for security and quality
- Auto-release workflow verifies CHANGELOG was updated instead of attempting to modify it

### Fixed

## [0.5.1] - 2026-01-25

### Added
- Automated release workflow - GitHub Actions automatically creates tags and releases when version files are updated on main
- `/sheet-music-publisher` skill - Convert audio to sheet music, create KDP-ready songbooks
  - AnthemScore CLI integration for automated transcription
  - MuseScore integration for polishing and PDF export
  - Cross-platform OS detection (macOS, Linux, Windows)
  - Config-aware path resolution
  - Automatic cover art detection for songbooks
  - Tools: transcribe.py, fix_titles.py, create_songbook.py
  - Comprehensive documentation (REQUIREMENTS.md, reference guides, publishing guide)
- `/validate-album` skill - Validates album structure, file locations, catches path issues
- `/test e2e` - End-to-end integration test that creates test album and exercises full workflow
- `/import-audio` skill - Moves audio files to correct `{audio_root}/{artist}/{album}/` location
- `/import-track` skill - Moves track .md files to correct album location with numbering
- `/import-art` skill - Places album art in both audio and content folders
- `/new-album` skill - Creates album directory structure with all templates
- `/about` skill - About bitwize and links to bitwizemusic.com
- `/configure` skill for interactive setup
- `/test` skill for automated plugin validation (13 test categories)
- GitHub issue templates (bug reports, feature requests)
- Suno Persona field in album template for consistent vocal style
- Comprehensive Suno V5 best practices guide
- Artist name → style description reference (200+ artists)
- Pronunciation guide with phonetic spellings
- Shared `tools_root` at `~/.bitwize-music/` for mastering venv
- `documents_root` config for PDF/primary source storage
- Core skills: lyric-writer, researcher, album-conceptualizer, suno-engineer
- Specialized researcher sub-skills (legal, gov, journalism, tech, security, financial, historical, biographical, primary-source, verifier)
- Album/track/artist templates
- Mastering workflow with Python tools
- Release director workflow
- Tutorial skill for guided album creation

### Changed
- Config lives at `~/.bitwize-music/config.yaml` (outside plugin dir)
- Audio/documents paths mirror content structure: `{root}/{artist}/{album}/`
- Mastering scripts accept path argument instead of being copied into audio folders
- Researcher skill saves RESEARCH.md/SOURCES.md to album directory, not working directory
- All path-sensitive operations read config first (enforced)
- Brand casing standardized to `bitwize-music` (lowercase)

### Fixed
- Audio files being saved to wrong location (missing artist folder)
- Research files being saved to working directory instead of album directory
- Mastering scripts mixing .py files with .wav files in audio folders
- User-provided names now preserve exact casing (no auto-capitalization)
- Skill references in docs now use full `/bitwize-music:` prefix (required for plugin skills)
- Researcher skill names aligned with folder names (colon → hyphen in frontmatter)
