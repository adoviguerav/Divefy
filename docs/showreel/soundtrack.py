"""Soundtrack for the Divefy showreel, synthesized from scratch (no samples).

120 BPM in A minor. The first 6 s play through a low-pass ("underwater"),
the filter opens on the logo drop at 6.0 s. Every SFX time mirrors the
timeline in showreel.html.

    uv run --with numpy --with scipy python soundtrack.py soundtrack.wav
"""

import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48_000
DUR = 24.5
N = int(SR * DUR)
BEAT = 0.5
rng = np.random.default_rng(11)

music = np.zeros((2, N))
sfx = np.zeros((2, N))


def add(bus, t0, sig, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N or i + len(sig) <= 0:
        return
    sig = sig[: N - i] * gain
    bus[0, i : i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    bus[1, i : i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def glide(f0, f1, dur, k=8.0):
    """Exponential pitch glide; returns the phase-integrated sine."""
    t = tt(dur)
    f = f1 + (f0 - f1) * np.exp(-k * t)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def env(dur, a=0.002, d=8.0):
    t = tt(dur)
    return np.minimum(1, t / a) * np.exp(-d * t)


def sweep_filter(x, f0, f1, q=0.7):
    """State-variable band-pass whose centre sweeps f0 -> f1 (exp)."""
    n = len(x)
    fc = f0 * (f1 / f0) ** (np.arange(n) / max(1, n - 1))
    g = np.tan(np.pi * np.minimum(fc, SR * 0.45) / SR)
    k = 1 / q
    y = np.zeros(n)
    s1 = s2 = 0.0
    for i in range(n):
        gi = g[i]
        hp_ = (x[i] - (k + gi) * s1 - s2) / (1 + k * gi + gi * gi)
        bp_ = gi * hp_ + s1
        s1 = gi * hp_ + bp_
        lp_ = gi * bp_ + s2
        s2 = gi * bp_ + lp_
        y[i] = bp_
    return y


# ------------------------------------------------------------------ instruments
def kick(gain=1.0):
    d = 0.45
    s = glide(170, 46, d, 28) * env(d, 0.001, 7.5)
    s[: int(0.004 * SR)] += noise(0.004) * 0.3
    return s * gain


def clap():
    d = 0.22
    x = bp(noise(d), 900, 3200) * env(d, 0.001, 22)
    for off in (0.011, 0.022):
        i = int(off * SR)
        x[i:] += bp(noise(d), 900, 3200)[: len(x) - i] * env(d, 0.001, 30)[: len(x) - i] * 0.7
    return x * 0.5


def hat(open_=False):
    d = 0.25 if open_ else 0.06
    return hp(noise(d), 7000) * env(d, 0.001, 14 if open_ else 60) * 0.35


def saw(freq, dur, detune_cents=(-7, 0, 7)):
    t = tt(dur)
    out = np.zeros(len(t))
    for c in detune_cents:
        f = freq * 2 ** (c / 1200)
        ph = rng.random()
        out += 2 * ((t * f + ph) % 1.0) - 1
    return out / len(detune_cents)


def pluck(freq, dur=0.3):
    t = tt(dur)
    out = np.zeros(len(t))
    for k in range(1, 8):
        out += np.sin(2 * np.pi * freq * k * t) / k * np.exp(-t * (9 + k * 7))
    return out * np.minimum(1, t / 0.002)


def bloop(f0, f1, dur=0.09, k=30):
    return glide(f0, f1, dur, k) * env(dur, 0.002, 30)


def ding(freq, dur=0.9, d=5.0):
    t = tt(dur)
    s = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d * r ** 0.5) for r, a in ((1, 1), (2.0, 0.35), (2.76, 0.25), (5.4, 0.1)))
    return s * np.minimum(1, t / 0.002)


def tick(bright=5000, d=0.006):
    return hp(noise(d), bright) * env(d, 0.0005, 400)


def blip(freq=1400, dur=0.05):
    t = tt(dur)
    return np.sign(np.sin(2 * np.pi * freq * t)) * env(dur, 0.001, 50) * 0.3


def whoosh(dur, f0, f1, q=0.9):
    x = noise(dur)
    shape = np.sin(np.pi * np.linspace(0, 1, len(x))) ** 1.5
    return sweep_filter(x, f0, f1, q) * shape


def boom(dur=1.6):
    s = glide(95, 30, dur, 3.5) * env(dur, 0.002, 2.6)
    crash = lp(hp(noise(dur), 3000), 12000) * env(dur, 0.001, 3.2) * 0.35
    return s + crash


def shimmer(dur=1.6, base=880.0):
    t = tt(dur)
    out = np.zeros(len(t))
    for r in (1, 1.5, 2, 2.5198, 3, 4):
        out += np.sin(2 * np.pi * base * r * t + rng.random() * 6.28) * (0.6 + 0.4 * np.sin(2 * np.pi * (5 + r) * t))
    return out / 6 * env(dur, 0.05, 2.2)


def boing(dur=0.32):
    t = tt(dur)
    f = 320 + 420 * t / dur + 60 * np.sin(2 * np.pi * 24 * t) * np.exp(-6 * t)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(dur, 0.003, 7)


def cork_pop():
    d = 0.12
    body = glide(900, 260, d, 45) * env(d, 0.0005, 40)
    snap = hp(noise(0.012), 2500) * env(0.012, 0.0003, 300)
    out = body
    out[: len(snap)] += snap * 0.9
    return out


# ------------------------------------------------------------------ harmony
NOTE = {"A1": 55.0, "F1": 43.65, "G1": 49.0, "C2": 65.41,
        "F3": 174.61, "G3": 196.0, "A3": 220.0, "B3": 246.94, "C4": 261.63, "D4": 293.66, "E4": 329.63, "B4": 493.88, "A4": 440.0}
CHORDS = [  # (start, end, bass, voicing)
    (0, 2, "A1", ("A3", "C4", "E4")), (2, 4, "F1", ("F3", "A3", "C4")), (4, 6, "G1", ("G3", "B3", "D4")),
    (6, 8, "A1", ("A3", "C4", "E4")), (8, 10, "F1", ("F3", "A3", "C4")), (10, 12, "C2", ("G3", "C4", "E4")),
    (12, 14, "G1", ("G3", "B3", "D4")), (14, 16, "A1", ("A3", "C4", "E4")), (16, 17, "F1", ("F3", "A3", "C4")),
    (17, 18.38, "G1", ("G3", "B3", "D4")), (18.38, 20, "A1", ("A3", "C4", "E4", "B4", "A4")),
    (20, 22, "F1", ("F3", "A3", "C4")), (22, 23, "G1", ("G3", "B3", "D4")), (23, 24.5, "A1", ("A3", "C4", "E4", "B4")),
]

pad = np.zeros(N)
bass = np.zeros(N)
arp = np.zeros(N)
for a, b, root, voicing in CHORDS:
    d = b - a + 0.25
    fade = np.minimum(1, tt(d) / 0.08) * np.minimum(1, (d - tt(d)) / 0.25)
    chord = sum(saw(NOTE[n], d) for n in voicing) / len(voicing)
    i = int(a * SR)
    seg_ = (chord * fade)[: N - i]
    pad[i : i + len(seg_)] += seg_
    f = NOTE[root]
    # bass: sub drone before the drop, off-beat eighths after it
    if a < 6:
        s = (np.sin(2 * np.pi * f * 2 * tt(d)) * 0.8 + saw(f * 2, d, (0,)) * 0.3) * fade * 0.45
        bass[i : i + len(s[: N - i])] += s[: N - i]
    else:
        t0 = a
        while t0 < min(b, 18.3 if b <= 20 else 24.0) - 1e-6:
            for off in (0.25,):
                nd = 0.22
                s = (np.sin(2 * np.pi * f * 2 * tt(nd)) + lp(saw(f * 2, nd, (-5, 5)), 900) * 0.6) * env(nd, 0.004, 9)
                j = int((t0 + off) * SR)
                bass[j : j + len(s)] += s[: max(0, N - j)]
            t0 += BEAT
        # 16th-note pluck arp over the groove (skips the stats + end card)
        if a < 16 or 20 <= a < 24:
            tones = [NOTE[voicing[0]] * 2, NOTE[voicing[1]] * 2, NOTE[voicing[2]] * 2, NOTE[voicing[1]] * 4]
            k = 0
            t0 = a
            while t0 < b - 1e-6:
                s = pluck(tones[k % 4], 0.3)
                j = int(t0 * SR)
                arp[j : j + len(s)] += s[: max(0, N - j)] * (1.0 if k % 4 == 0 else 0.7)
                k += 1
                t0 += BEAT / 4

pad = lp(pad, 2200)
music[0] += pad * 0.16
music[1] += pad * 0.16
add(music, 0, bass, 0.34)
add(music, 0, arp, 0.10, -0.25)
add(music, 0.0625, arp, 0.05, 0.4)  # dotted echo on the other side

# drums
kick_times = [i * BEAT for i in range(0, 12)]  # muffled intro kicks (0..5.5)
kick_times += [6.0 + i * BEAT for i in range(0, 25)]  # 6.0 .. 18.0
kick_times += [20.0 + i * BEAT for i in range(0, 8)]  # epilogue 20.0 .. 23.5
for k in kick_times:
    if 5.9 < k < 6.0:
        continue
    add(music, k, kick(), 0.95 if k >= 6 else 0.8)
for i in range(24):
    t0 = 6.5 + i * 1.0
    if t0 <= 18.0:
        add(music, t0, clap(), 0.55, 0.05)
for i in range(48):
    t0 = 6.25 + i * BEAT
    if t0 < 18.2:
        add(music, t0, hat(True), 0.45, 0.3)
for i in range(96):
    t0 = 6.0 + i * BEAT / 4
    if t0 < 18.2 and (i % 2 == 1):
        add(music, t0, hat(), 0.25, -0.3)
# epilogue groove
for i in range(4):
    add(music, 20.5 + i * 1.0, clap(), 0.5, 0.05)
for i in range(8):
    add(music, 20.25 + i * BEAT, hat(True), 0.4, 0.3)
# intro: shaker on off-beats from 2.5
for i in range(6):
    add(music, 2.75 + i * BEAT, hat(True), 0.3, 0.2)
# build: snare roll 5.0 -> 5.95 accelerating
t0, step = 4.95, 0.125
while t0 < 5.93:
    add(music, t0, clap(), 0.25 + 0.4 * (t0 - 4.95), 0.0)
    t0 += step
    step = max(0.03, step * 0.8)

# sidechain pump from the post-drop kicks
t = np.arange(N) / SR
duck = np.ones(N)
for k in kick_times:
    if k >= 6:
        m = t >= k
        duck[m] = np.minimum(duck[m], 1 - 0.55 * np.exp(-(t[m] - k) / 0.11))
music *= duck

# underwater: low-pass the whole music bus before the drop, silence the gap
intro = int(6.0 * SR)
for c in range(2):
    muffled = lp(music[c], 650, 4)
    music[c, :intro] = muffled[:intro] * 0.55
music[:, int(5.94 * SR) : intro] *= np.linspace(1, 0, intro - int(5.94 * SR))
# UI section: let the SFX breathe
gain = np.ones(N)
gain[int(8.6 * SR) : int(16.0 * SR)] = 0.72
music *= gain
# final fade
music[:, int(24.05 * SR) :] *= np.linspace(1, 0, N - int(24.05 * SR)) ** 1.5

# ------------------------------------------------------------------ SFX (mirrors showreel.html)
# on the boat: horn + sea, then a splash when the camera goes under
horn_t = tt(0.9)
horn = lp(saw(116.5, 0.9, (-6, 6)) + saw(146.8, 0.9, (-6, 6)) * 0.7, 900) * np.minimum(1, horn_t / 0.04) * np.minimum(1, (0.9 - horn_t) / 0.25)
add(sfx, 0.02, horn, 0.5, -0.3)
sea = lp(np.cumsum(noise(5.2)) * 0.02, 700)
sea -= lp(sea, 40)
swell = 0.55 + 0.45 * np.sin(2 * np.pi * 0.45 * tt(5.2)) ** 2
sea_fade = np.minimum(1, tt(5.2) / 0.3) * np.clip((4.98 - tt(5.2)) / 0.05, 0, 1)
add(sfx, 0.0, sea * swell * sea_fade / np.abs(sea).max(), 0.22, 0.2)
add(sfx, 1.07, glide(150, 55, 0.25, 22) * env(0.25, 0.002, 14), 0.7, 0.3)  # diver lands on deck
add(sfx, 4.95, lp(noise(0.6), 2500) * env(0.6, 0.005, 6), 0.55, 0)  # splash
for i in range(9):
    add(sfx, 5.0 + i * 0.035, bloop(250 + 90 * i, 700 + 60 * i, 0.07), 0.2, (-1) ** i * 0.5)
for i, t0 in enumerate((0.75, 0.9, 1.15)):
    add(sfx, t0, glide(120, 60, 0.15, 25) * env(0.15, 0.002, 20), 0.5)
add(sfx, 0.60, blip(1500), 0.25, 0.7)
add(sfx, 0.95, whoosh(0.4, 900, 5000, 2), 0.25, -0.2)
add(sfx, 1.40, bloop(500, 900, 0.06), 0.25, 0.4)
add(sfx, 1.47, bloop(600, 1000, 0.06), 0.25, 0.4)
add(sfx, 1.52, bloop(350, 800, 0.12), 0.45, 0.3)
add(sfx, 2.05, whoosh(0.7, 300, 3500, 0.8), 0.7, 0)
for i, t0 in enumerate((3.0, 3.5, 4.0, 4.5)):
    add(sfx, t0, bloop(280 + i * 60, 760 + i * 80, 0.1), 0.5, (-0.5, 0.5, -0.5, 0.5)[i])
add(sfx, 4.58, boing(), 0.35, 0)
add(sfx, 4.95, whoosh(0.9, 200, 6000, 1.2), 0.55, 0)
riser = np.sin(2 * np.pi * np.cumsum(180 * (1400 / 180) ** (tt(1.0) / 1.0)) / SR) * np.linspace(0, 1, SR) ** 2
add(sfx, 4.95, riser, 0.12, 0)
for t0 in (5.0, 5.25, 5.5):
    add(sfx, t0, blip(2200, 0.07), 0.18, 0.6)
add(sfx, 5.16, boom(0.5), 0.5, 0)
add(sfx, 5.16, clap(), 0.5, 0)
add(sfx, 5.52, cork_pop(), 0.9, 0)
add(sfx, 5.52, hp(noise(0.4), 4000) * env(0.4, 0.001, 9), 0.2, 0.3)  # fizz
add(sfx, 6.0, boom(1.8), 0.9, 0)
add(sfx, 6.02, shimmer(1.8, 880), 0.25, 0)
for t0, g in ((6.537, 0.5), (6.77, 0.22), (6.89, 0.1)):
    add(sfx, t0, bloop(1400, 700, 0.07, 45), g, -0.1)
add(sfx, 6.75, whoosh(0.45, 600, 4000, 1.5), 0.15, 0)
add(sfx, 7.2, whoosh(0.35, 1500, 7000, 2), 0.1, 0.2)
add(sfx, 7.35, bloop(400, 900, 0.09), 0.3, -0.4)
add(sfx, 7.47, bloop(450, 1000, 0.09), 0.3, 0.4)
add(sfx, 7.95, whoosh(0.65, 200, 5000, 1.0), 0.6, 0)
add(sfx, 8.55, bloop(900, 180, 0.2, 18), 0.6, 0)
add(sfx, 8.25, whoosh(0.6, 3000, 400, 0.9), 0.25, 0.2)
for i in range(22):
    add(sfx, 8.8 + i * 0.6 / 22, tick(3500), 0.35, 0.2)
add(sfx, 9.48, tick(1500, 0.015), 0.6, 0.2)
add(sfx, 9.48, whoosh(0.3, 800, 5000, 1.5), 0.22, 0.2)
add(sfx, 9.62, bloop(500, 850, 0.08), 0.3, -0.2)
for i in range(26):
    add(sfx, 9.92 + i * 1.2 / 26, tick(6000, 0.004), 0.12, -0.2)
for t0 in (9.55, 11.35, 12.8, 14.8):
    add(sfx, t0, bloop(700, 1100, 0.07), 0.25, 0)
add(sfx, 11.05, whoosh(0.55, 400, 3000, 1.0), 0.3, 0)
add(sfx, 11.2, whoosh(0.5, 2500, 500, 1.0), 0.25, 0.6)
for i, t0 in enumerate((11.55, 11.85, 12.15)):
    k = t0 - 0.3
    while k < t0 - 0.01:
        add(sfx, k, tick(4500, 0.004), 0.2, -0.2)
        k += 0.025
    add(sfx, t0, ding((1046.5, 1318.5, 1568.0)[i], 0.9), 0.3, 0.1)
add(sfx, 12.55, whoosh(0.6, 3000, 400, 1.0), 0.25, 0)
for i, t0 in enumerate((12.7, 12.78, 12.92)):
    add(sfx, t0, bloop(500 + i * 80, 900 + i * 80, 0.08), 0.25, -0.3)
add(sfx, 13.78, whoosh(0.55, 500, 2500, 1.0), 0.25, 0)
for i in range(27):
    add(sfx, 13.85 + i * 0.45 / 27, tick(3500), 0.3, 0.2)
add(sfx, 14.35, tick(1500, 0.015), 0.6, 0.2)
add(sfx, 14.35, whoosh(0.3, 800, 5000, 1.5), 0.22, 0.2)
add(sfx, 14.47, bloop(500, 850, 0.08), 0.3, -0.2)
add(sfx, 14.65, ding(659.25, 0.5, 7), 0.22, 0)
add(sfx, 14.8, ding(523.25, 0.7, 6), 0.2, 0)
add(sfx, 15.9, whoosh(0.55, 4000, 300, 1.0), 0.45, 0)
add(sfx, 16.42, bloop(1200, 300, 0.12, 30), 0.6, 0)
for t0 in (16.5, 17.0, 17.5):
    add(sfx, t0, boom(0.9), 0.75, 0)
    add(sfx, t0, clap(), 0.35, 0)
k = 17.5
while k < 17.74:
    add(sfx, k, tick(4500, 0.004), 0.22, 0.3)
    k += 0.03
add(sfx, 17.75, ding(1760, 1.0, 4), 0.35, 0.3)
add(sfx, 18.12, whoosh(0.5, 400, 4000, 1.0), 0.35, 0)
add(sfx, 18.38, boom(1.6), 0.8, 0)
add(sfx, 18.40, shimmer(1.6, 880), 0.3, 0)
add(sfx, 18.73, bloop(1400, 700, 0.07, 45), 0.45, -0.3)
add(sfx, 18.98, ding(1318.5, 0.9, 4), 0.2, 0.5)
add(sfx, 19.08, blip(1800, 0.04), 0.2, -0.2)

# epilogue: back on the boat
add(sfx, 19.98, whoosh(0.4, 300, 4000, 1.0), 0.5, 0)
add(sfx, 20.0, lp(noise(0.5), 3000) * env(0.5, 0.005, 7), 0.45, 0)  # surfacing splash
for i in range(6):
    add(sfx, 20.02 + i * 0.03, bloop(900 - 90 * i, 300, 0.06), 0.15, (-1) ** i * 0.5)
sea2 = lp(np.cumsum(noise(4.4)) * 0.02, 700)
sea2 -= lp(sea2, 40)
sea2 *= (0.55 + 0.45 * np.sin(2 * np.pi * 0.45 * tt(4.4)) ** 2) * np.minimum(1, tt(4.4) / 0.2) / np.abs(sea2).max()
add(sfx, 20.1, sea2, 0.18, 0.2)
add(sfx, 20.48, glide(150, 55, 0.25, 22) * env(0.25, 0.002, 14), 0.6, 0.3)  # diver lands
add(sfx, 20.5, whoosh(0.32, 300, 2500, 0.8), 0.35, -0.2)  # wave builds
add(sfx, 20.8, lp(noise(0.9), 2200) * env(0.9, 0.004, 4.5), 0.8, -0.1)  # crash
crackle = hp(noise(0.4), 3000) * (rng.random(int(0.4 * SR)) > 0.985) * 3
add(sfx, 20.86, crackle * env(0.4, 0.001, 5), 0.35, -0.2)
add(sfx, 20.9, glide(900, 60, 0.45, 7) * env(0.45, 0.002, 4), 0.3, -0.2)  # power down
add(sfx, 21.4, whoosh(0.35, 600, 4000, 1.2), 0.3, 0)
add(sfx, 21.55, glide(1600, 500, 0.22, 6) * env(0.22, 0.01, 4), 0.12, 0.3)  # falling
for t0, g in ((21.77, 0.8), (21.99, 0.35), (22.1, 0.15)):
    add(sfx, t0, glide(260, 110, 0.18, 30) * env(0.18, 0.001, 18) + np.pad(tick(2500, 0.01), (0, int(0.17 * SR))) * 0.6, g, 0.3)
add(sfx, 22.14, shimmer(0.9, 1318.5), 0.18, 0.4)
add(sfx, 22.85, whoosh(0.35, 600, 4000, 1.2), 0.3, 0)
add(sfx, 23.15, boom(0.5), 0.6, -0.1)
add(sfx, 23.15, clap(), 0.45, -0.1)
add(sfx, 23.35, ding(2093.0, 0.6, 6), 0.25, 0.2)  # ka-
add(sfx, 23.41, ding(2637.0, 0.8, 5), 0.25, 0.2)  # -ching
add(sfx, 23.6, bloop(700, 1100, 0.07), 0.2, 0)

# ------------------------------------------------------------------ space + master
ir_t = tt(1.4)
ir = rng.standard_normal((2, len(ir_t))) * np.exp(-ir_t * 4.2)
ir[:, : int(0.012 * SR)] = 0
ir /= np.sqrt((ir**2).sum(axis=1, keepdims=True))
wet_in = music * 0.5 + sfx
wet = np.stack([fftconvolve(wet_in[c], ir[c])[:N] for c in range(2)]) * 0.22
mix = music + sfx + wet
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix *= 0.93 / np.abs(mix).max()
mix[:, : int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))

out = sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix.T * 32767).astype("<i2").tobytes())
print("wrote", out)
