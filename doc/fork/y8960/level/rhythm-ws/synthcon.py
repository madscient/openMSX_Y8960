"""anacon.py の判別力を見るための合成の録音を作る。MGA の電源投入（床の上昇と電源投入の音）、ときどき延びる歩、
鍵を押している間の減衰を含む。

    py synthcon.py <出力先のディレクトリ>

con_gate.wav       : C7h=00h の HH が鳴らない（打 0 も鳴らない）
con_gate_hit0.wav  : C7h=00h の HH が鳴らない。打 0 だけ鳴る
con_none.wav       : HH はすべて鳴る
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000
rng = np.random.default_rng(7)
SEGS = ['HH0'] + ['TT', 'HH00', 'TT', 'HH01'] * 4 + ['TT']


def make(path, hh_on):
    total = int((8.0 + 19 * 1.05 + 2.0) * RATE)
    y = rng.standard_normal(total) * 10 ** (-86 / 20)
    p = int(2.0 * RATE)
    y[p:] += rng.standard_normal(total - p) * 10 ** (-66 / 20)
    for tp, lv, ln in ((2.0, -38, 0.035), (2.2, -18, 0.23), (2.6, -44, 0.03), (3.0, -40, 0.05), (3.4, -45, 0.03)):
        q = int(tp * RATE)
        y[q:q + int(ln * RATE)] += rng.standard_normal(int(ln * RATE)) * 10 ** (lv / 20)
    pos = int(6.5 * RATE)
    n_all = int(2.0 * RATE)
    t = np.arange(n_all) / RATE
    # リズム音は持続を持たないので、鍵を押している間も RR で減る
    rel = np.exp(-t * 9.0)
    for i, s in enumerate(SEGS):
        if i == 7:
            pos += int(0.35 * RATE)
        if s == 'TT':
            x = 0.2 * np.sin(2 * np.pi * 190 * t + 1.5 * np.sin(2 * np.pi * 190 * t)) * rel
        else:
            x = 0.1 * np.diff(rng.standard_normal(n_all), prepend=0) * rel * (1.0 if hh_on(s) else 0.0)
        end = min(total, pos + n_all)
        y[pos:end] += x[:end - pos]
        pos += int(1.03 * RATE)
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / 'con_gate.wav', lambda s: s == 'HH01')
make(out / 'con_gate_hit0.wav', lambda s: s in ('HH01', 'HH0'))
make(out / 'con_none.wav', lambda s: True)
print('written')
