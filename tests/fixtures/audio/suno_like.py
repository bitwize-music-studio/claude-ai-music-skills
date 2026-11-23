"""Suno-like masters, generated: loud, brickwalled, arranged in sections.

The other fixtures in this package are seconds-long test tones peaking well
below full scale. What Suno delivers is different (16-bit / 48 kHz stereo,
-9 to -7 LUFS for pop, sample peaks within ~1.5 dB of 0 dBFS, an
intro / verse / chorus / bridge arrangement and a fade), and several album
mastering decisions only go wrong on audio like that (#681). Everything is
deterministic and generated at test time; nothing is checked in.
"""

from __future__ import annotations

import numpy as np
import pyloudnorm as pyln
from scipy.signal import butter, sosfilt


def _bp(x: np.ndarray, rate: int, lo: float, hi: float, order: int = 2) -> np.ndarray:
    sos = butter(order, [lo / (rate / 2), hi / (rate / 2)], btype="band", output="sos")
    return np.asarray(sosfilt(sos, x))


def _lp(x: np.ndarray, rate: int, f: float, order: int = 2) -> np.ndarray:
    sos = butter(order, f / (rate / 2), btype="low", output="sos")
    return np.asarray(sosfilt(sos, x))


def make_suno_song(
    seconds: float = 60.0,
    rate: int = 48000,
    target_lufs: float = -9.0,
    seed: int = 1,
    key: int = 0,
    peak: float = 0.985,
    fade_s: float = 6.0,
) -> tuple[np.ndarray, int]:
    """A pop-shaped song mastered the way Suno masters.

    Kick, snare, panned hats, a bass line, a wide pad and a formant "vocal",
    in sections (quiet intro, verse, louder chorus, bridge dip, chorus, fade),
    loudness-normalised to ``target_lufs`` and soft-clipped to a sample peak
    of ``peak``. Section lengths scale with ``seconds``.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * rate)
    t = np.arange(n) / rate
    beat = 0.5  # 120 bpm
    bar = 4 * beat
    k = int(0.2 * rate)

    # Section envelope, proportioned like the 150 s original.
    sec = np.ones(n)
    for a, b, g in ((0, 8, 0.35), (8, 40, 0.6), (40, 70, 1.0), (70, 100, 0.6),
                    (100, 115, 0.45), (115, 150, 1.0)):
        s = seconds / 150.0
        sec[int(a * s * rate):int(min(b * s, seconds) * rate)] = g
    sec = np.convolve(sec, np.ones(k) / k, mode="same")
    intro = 8.0 * seconds / 150.0

    root = 110.0 * 2 ** (key / 12)
    prog = [0, -4, 3, -2]

    kick = np.zeros(n)
    snare = np.zeros(n)
    hat = np.zeros(n)
    klen, slen, hlen = int(0.25 * rate), int(0.2 * rate), int(0.05 * rate)
    kt, st, ht = np.arange(klen) / rate, np.arange(slen) / rate, np.arange(hlen) / rate
    kick_hit = np.sin(2 * np.pi * (50 + 80 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 12)
    snare_hit = (_bp(rng.standard_normal(slen), rate, 1500, 7000) * 2
                 + 0.5 * np.sin(2 * np.pi * 190 * st)) * np.exp(-st * 22)
    hat_hit = _bp(rng.standard_normal(hlen), rate, 7000, 16000, order=4) * np.exp(-ht * 80) * 3
    for b in range(int(seconds / beat)):
        s = int(b * beat * rate)
        if s / rate < intro:
            continue
        e = min(n, s + klen)
        kick[s:e] += kick_hit[:e - s]
        if b % 2 == 1:
            e = min(n, s + slen)
            snare[s:e] += snare_hit[:e - s] * (0.9 + 0.2 * rng.random())
        for h in (0.0, 0.5):
            hs = int((b + h) * beat * rate)
            he = min(n, hs + hlen)
            if hs < n:
                hat[hs:he] += hat_hit[:he - hs] * (0.6 + 0.4 * rng.random())

    bass = np.zeros(n)
    for i in range(int(seconds / (beat / 2))):
        s = int(i * beat / 2 * rate)
        e = min(n, s + int(beat / 2 * rate))
        if s >= n or s / rate < intro:
            continue
        f = root / 2 * 2 ** (prog[int(s / rate / bar) % 4] / 12)
        tt = np.arange(e - s) / rate
        bass[s:e] += (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 3)
    bass = _lp(bass, rate, 400)

    pad_l = np.zeros(n)
    pad_r = np.zeros(n)
    for barn in range(int(seconds / bar) + 1):
        s = int(barn * bar * rate)
        e = min(n, int((barn + 1) * bar * rate))
        if s >= n:
            break
        tt = np.arange(e - s) / rate
        r = root * 2 * 2 ** (prog[barn % 4] / 12)
        for iv in (0, 3, 7, 12):
            f = r * 2 ** (iv / 12)
            pad_l[s:e] += np.sin(2 * np.pi * f * 1.002 * tt + rng.random() * 6)
            pad_r[s:e] += np.sin(2 * np.pi * f * 0.998 * tt + rng.random() * 6)
    pad_env = 0.5 + 0.5 * np.sin(2 * np.pi * t / bar) ** 2

    f0 = root * 4 * 2 ** (np.array(prog)[(t / bar).astype(int) % 4] / 12)
    phase = 2 * np.pi * np.cumsum(f0 * (1 + 0.01 * np.sin(2 * np.pi * 5.5 * t))) / rate
    saw = 2 * ((phase / (2 * np.pi)) % 1) - 1
    voc = _bp(saw, rate, 300, 1200) + 0.7 * _bp(saw, rate, 1800, 3500)
    phrase = np.convolve(((t % (2 * bar)) < 1.6 * bar).astype(float), np.ones(k) / k, mode="same")
    voc *= phrase * (t >= intro)

    left = 2.2 * kick + 1.4 * snare + 0.35 * hat + 0.6 * bass + 0.06 * pad_l * pad_env + 0.45 * voc
    right = 2.2 * kick + 1.4 * snare + 0.19 * hat + 0.6 * bass + 0.06 * pad_r * pad_env + 0.45 * voc
    wet = 0.4 * snare + 0.3 * voc + 0.05 * (pad_l + pad_r)
    for d, g in ((0.031, 0.35), (0.047, 0.25), (0.083, 0.18)):
        dl, dr = int(d * rate), int(d * 1.37 * rate)
        left[dl:] += g * wet[:-dl]
        right[dr:] += g * wet[:-dr]
    left *= sec
    right *= sec
    fn = int(fade_s * rate)
    if fn > 0:
        fade = np.linspace(1, 0, fn) ** 2
        left[-fn:] *= fade
        right[-fn:] *= fade
    left += 1e-4 * rng.standard_normal(n)
    right += 1e-4 * rng.standard_normal(n)

    data = np.column_stack([left, right])
    meter = pyln.Meter(rate)
    knee = 0.7 * peak
    for _ in range(6):
        data = data * 10 ** ((target_lufs - meter.integrated_loudness(data)) / 20)
        a = np.abs(data)
        over = a > knee
        a[over] = knee + (peak - knee) * np.tanh((a[over] - knee) / (peak - knee))
        data = np.sign(data) * a
    return data, rate


def make_808(
    seconds: float = 8.0,
    rate: int = 48000,
    note_hz: float = 32.70,  # C1
    level: float = 0.8,
) -> tuple[np.ndarray, int]:
    """A trap 808 bass stem: one long tuned boom per beat at ``note_hz``.

    A short pitch drop into the note, a ~0.6 s decay and a little
    saturation, the way an 808 is programmed under trap. Its fundamental sits
    at ``note_hz``; there is nothing below it but the note's own skirt.
    """
    n = int(seconds * rate)
    out = np.zeros(n)
    hit_len = int(0.45 * rate)
    tt = np.arange(hit_len) / rate
    freq = note_hz * (1 + 1.5 * np.exp(-tt * 60))
    hit = np.sin(2 * np.pi * np.cumsum(freq) / rate) * np.exp(-tt * 3.0)
    hit = np.tanh(1.5 * hit) / np.tanh(1.5)
    for s in range(0, n, int(0.5 * rate)):
        e = min(n, s + hit_len)
        out[s:e] += hit[:e - s]
    out = level * out / max(1e-9, float(np.max(np.abs(out))))
    return np.column_stack([out, out]), rate


def make_rumble(
    seconds: float = 8.0,
    rate: int = 48000,
    lo_hz: float = 10.0,
    hi_hz: float = 20.0,
    level: float = 0.5,
) -> tuple[np.ndarray, int]:
    """Sub-sonic rumble (handling noise, HVAC, drift) between ``lo_hz`` and ``hi_hz``."""
    rng = np.random.default_rng(11)
    noise = _bp(rng.standard_normal(int(seconds * rate)), rate, lo_hz, hi_hz, order=4)
    noise = level * noise / max(1e-9, float(np.max(np.abs(noise))))
    return np.column_stack([noise, noise]), rate
