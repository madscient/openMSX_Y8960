"""analeak.py を確かめる合成の録音。電源投入の瞬間の音、区間の長さの揺れ（1.00〜1.045 秒）を入れる。

    py synthleak.py <出力先> [乱数の種]
  hh_sd.wav : HH と SD が鳴る（HH -16dBFS、SD -18dBFS）。TT・CY は鳴らない
  sd.wav    : SD だけが鳴る
  all4.wav  : 4 つとも同じ大きさで鳴る
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000
rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 3)


def make(path, levels):
    total = int(26 * RATE)
    y = rng.standard_normal(total) * 10 ** (-88 / 20)
    p0 = int(3.6 * RATE)
    y[p0:] += rng.standard_normal(total - p0) * 10 ** (-67 / 20)
    y[p0:p0 + int(0.25 * RATE)] += rng.standard_normal(int(0.25 * RATE)) * 10 ** (-18 / 20)
    t = 3.6 + 3.0 + 2 * 1.02
    on = dict(levels)
    order = ['HH', 'SD', 'TT', 'CY', 'all']
    steps = [t]
    for _ in order:
        steps.append(steps[-1] + sum(rng.uniform(1.0, 1.045) for _ in range(2)))
    end = steps[-1] + 1.0
    for k in range(len(steps)):
        a = int(steps[k] * RATE)
        b = int((steps[k + 1] if k + 1 < len(steps) else end) * RATE)
        if k > 0:
            name = order[k - 1]
            if name == 'all':
                on = {}
            else:
                on.pop(name, None)
        p = sum(10 ** (v / 10) for v in on.values())
        if p:
            y[a:b] += rng.standard_normal(b - a) * np.sqrt(p)
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as wv:
        wv.setnchannels(2)
        wv.setsampwidth(2)
        wv.setframerate(RATE)
        wv.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / 'hh_sd.wav', {'HH': -16, 'SD': -18})
make(out / 'sd.wav', {'SD': -14})
make(out / 'all4.wav', {'HH': -20, 'SD': -20, 'TT': -20, 'CY': -20})
print('written')
