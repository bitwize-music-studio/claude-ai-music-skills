# Test Fixtures

This directory holds shared test fixtures that aren't tied to a specific test module.

## `audio/` — procedural audio generators

`audio/__init__.py` defines deterministic, musically-realistic audio
generators authored from primitives (sines, filtered noise, envelopes). Each
generator returns a `(numpy.ndarray, sample_rate)` tuple.

The corresponding pytest fixtures live in [`tests/conftest.py`](../conftest.py)
so any test under `tests/` can use them by name (`vocal_wav`, `drums_wav`, etc.).

### Why on-the-fly generation, not committed FLAC files?

Generation cost is ~50–200 ms per fixture call — negligible across the suite.
Skipping the cache layer keeps the repo lean (no committed binary files), keeps
the generators as the single source of truth, and avoids drift between code
and fixture content. If runtime ever becomes a bottleneck, generators can be
wrapped in `@pytest.fixture(scope="session")` or pre-rendered to FLAC; nothing
in the integration tests assumes one strategy over the other.

### Generator catalog

| Generator | Pytest fixture | Contents | What it exercises |
|---|---|---|---|
| `make_vocal()` | `vocal_wav` | Formant-shaped (300–3500 Hz) noise + 4–8 kHz sibilant bursts every 0.5 s | De-essing, vocal EQ, vocal-band compression |
| `make_drums()` | `drums_wav` | 80 Hz kick + 5 kHz snap, exponential decay every 0.25 s | Click detection, transient shaping, declicker |
| `make_bass()` | `bass_wav` | 80 Hz fundamental + 160/240/320 Hz harmonics | High-pass filtering, low-end EQ |
| `make_full_mix()` | `full_mix_wav` | Layered vocal + drums + bass at ~−15 LUFS | Baseline mastering pipeline, spectral balance |
| `make_clipping()` | `clipping_wav` | Over-driven 300 Hz sine clipped to ±1.0 | Clipping detection, true-peak FAIL, fix_dynamic recovery |
| `make_phase_problem()` | `phase_problem_wav` | Perfect L = −R inversion at 440 Hz | Total mono cancellation FAIL (synthetic ceiling case) |
| `make_phase_partial()` | `phase_partial_wav` | 90° phase shift on R channel (sin/cos pair, 440 + 660 Hz) | Realistic mono fold-down loss (3–9 dB) |
| `make_bright()` | `bright_wav` | Weak lows + dominant 4 kHz + 10 kHz air | Tinniness/spectral WARN, high-shelf EQ correction |
| `make_noisy()` | `noisy_wav` | A4+C#5 chord + heavy gaussian noise floor | Noise reduction, silence detection edge cases |
| `make_clicks_and_pops()` | `clicks_and_pops_wav` | 220 Hz tonal bed + kick transients + 6 single-sample DC spikes | Click QC FAIL on injected pops, declicker peak_ratio |
| `make_silent_gaps()` | `silent_gaps_wav` | 2 s tone + 1 s silence + 2 s tone | Silence QC FAIL on internal-gap detection |
| `make_drums()` × 3 stems | `stem_dir` | Per-stem `vocals.wav`, `drums.wav`, `bass.wav` in a track directory | Stem-aware mixing, remix paths |

### Adding a new generator

1. **Write the generator** in `audio/__init__.py`. Use a fixed seed
   (`np.random.default_rng(seed=...)`) for any randomness. Compose from
   the existing primitives (`_bandpass`, `_to_stereo`) where you can.
2. **Add the pytest fixture** in `tests/conftest.py` following the existing
   pattern (`def my_thing_wav(tmp_path): ...`). Keep the fixture name
   suffixed with `_wav` for consistency.
3. **Probe the QC verdict** before writing tests against it — drop into a
   one-shot Python session and call the relevant `_check_*` from
   `tools.mastering.qc_tracks` so you know what status the fixture trips.
4. **Document the row** in the catalog table above.

### Adding integration tests against fixtures

Use `tests/unit/mastering/test_integration_realistic_audio.py` as the
template. Tests should:

- Assert on **measured properties** (status verdict, LUFS, peak dB), not
  byte-for-byte audio output.
- Use a wide-enough range in numeric assertions to survive parameter tuning
  (e.g. `1.0 < loss_db < 20.0`, not `loss_db == 3.0`).
- Pull fixtures from `tests/conftest.py` by name — no local re-definitions.
