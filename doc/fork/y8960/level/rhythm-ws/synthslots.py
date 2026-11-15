"""anaslots.py を確かめる合成の録音。終わりの合図（ch0 の鍵、F-Num 200h の 388Hz と 777Hz）を入れる。SPFM Light のように床が
-50dBFS のものと、MGA のように電源投入の音があるものを作る。

    py synthslots.py <出力先> [乱数の種]
  real.wav  : どれも静かで、BDh=20h の雑音も出ない（実チップの形）。床 -50dBFS、50Hz の倍音
  y8960.wav : 17 スロットが鳴る位置（ch8 の変調器以外）、BDh=20h の雑音あり。MGA の電源投入の音
  some.wav  : ch2 のキャリアと ch5 の変調器だけ。BDh=20h の雑音なし。床 -50dBFS
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000
F = 0x244 * 3579545 / 72 * 2 ** 3 / 2 ** 19
FM = 0x200 * 3579545 / 72 * 2 ** 3 / 2 ** 19
rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 21)


def make(path, loud, noise_marker, spfm):
    total = int(40 * RATE)
    t = np.arange(total) / RATE
    if spfm:
        y = rng.standard_normal(total) * 10 ** (-50 / 20)
        y += sum(10 ** ((-62 - 2 * k) / 20) * np.sin(2 * np.pi * 50 * k * t) for k in range(1, 20))
        start = 4.0
    else:
        y = rng.standard_normal(total) * 10 ** (-88 / 20)
        p0 = int(3.4 * RATE)
        y[p0:] += rng.standard_normal(total - p0) * 10 ** (-67 / 20)
        y[p0:p0 + int(0.25 * RATE)] += rng.standard_normal(int(0.25 * RATE)) * 10 ** (-18 / 20)
        start = 3.4
    edges = [start + 3.0 + 2 * 1.0]
    for _ in range(27):
        edges.append(edges[-1] + rng.uniform(1.0, 1.045))
    if noise_marker:
        a, b = int(edges[0] * RATE), int(edges[1] * RATE)
        y[a:b] += rng.standard_normal(b - a) * 10 ** (-14 / 20)
    for c in range(9):
        a, b = int(edges[3 + 2 * c] * RATE), int(edges[5 + 2 * c] * RATE)
        for name, mult in (('mod', 1), ('car', 2)):
            if (c, name) in loud:
                y[a:b] += 10 ** (-12 / 20) * np.sin(2 * np.pi * F * mult * t[a:b])
    a = int(edges[23] * RATE)
    n = int(0.8 * RATE)
    env = np.ones(n)
    env[-int(0.02 * RATE):] = np.linspace(1, 0, int(0.02 * RATE))
    y[a:a + n] += env * 10 ** (-12 / 20) * (np.sin(2 * np.pi * FM * t[a:a + n]) + np.sin(2 * np.pi * 2 * FM * t[a:a + n]))
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as wv:
        wv.setnchannels(2)
        wv.setsampwidth(2)
        wv.setframerate(RATE)
        wv.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / 'real.wav', set(), False, True)
make(out / 'y8960.wav', {(c, n) for c in range(9) for n in ('mod', 'car')} - {(8, 'mod')}, True, False)
make(out / 'some.wav', {(2, 'car'), (5, 'mod')}, False, True)
print('written')
