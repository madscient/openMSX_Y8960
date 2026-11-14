"""anaeg.py の判別力を見るための合成の録音を作る。egmodel.py の各仮説の速さで、EG の歩（階段）、鍵を離す時刻の揺れ、平らでない
周波数特性、経路のひずみ、MGA の電源投入、ときどき延びる歩を加える。

    py syntheg.py <出力先のディレクトリ> [乱数の種] [クロックのずれ ppm]

eg_<仮説>.wav（real、y8960、pr16）。anaeg.py は、それぞれの仮説だけを「合う」とするはず
"""
import sys
import wave
from pathlib import Path

import numpy as np

import egmodel
from mkeg import TESTS

RATE = 48000
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 5
PPM = float(sys.argv[3]) if len(sys.argv) > 3 else 30
rng = np.random.default_rng(SEED)


def response(f):
    f = np.maximum(f, 1.0)
    hp = (1j * f / 20) / (1 + 1j * f / 20)
    s = 1j * f / 9000
    return hp / (1 + np.sqrt(2) * s + s * s)


def env_db(t, speed, step):
    return -step * np.floor(np.maximum(t, 0) * speed / step)


def make(path, hyp):
    total = int((8.0 + len(TESTS) * 1.05 + 2.0) * RATE)
    y = np.zeros(total)
    pos = int(6.5 * RATE)
    n = int(1.0 * RATE)
    t = np.arange(n) / RATE
    for i, test in enumerate(TESTS):
        if i == 5:
            pos += int(0.35 * RATE)
        f = egmodel.FS * test['fnum'] * 2 ** test['block'] * test['mult'] / 2 ** 20 * (1 + PPM * 1e-6)
        rt, sp = egmodel.predict(test)[hyp]
        hi = rt >> 2
        step = 0.09375 if (hyp == 'pr16' and hi < 12) else 0.1875
        off = (0.8 if test['kind'] == 'D' else 0.3) + rng.uniform(-0.003, 0.003)
        if test['kind'] == 'D':
            # 鍵を離すと RR=15 で速く消える
            e = np.maximum(env_db(t, sp, step), -93.0)
            e = np.where(t >= off, np.minimum(e, env_db(t - off, 30000, 0.1875) + e[int(off * RATE)]), e)
        else:
            e = env_db(t - off, sp, step)
        y[pos:pos + n] += 0.3 * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * 10 ** (e / 20)
        pos += int(1.03 * RATE)
    fr = np.fft.rfftfreq(total, 1 / RATE)
    z = np.fft.irfft(np.fft.rfft(y) * response(fr), total)
    z = z + 0.02 * z ** 2 + 0.05 * z ** 3
    z += rng.standard_normal(total) * 10 ** (-86 / 20)
    p = int(2.0 * RATE)
    z[p:] += rng.standard_normal(total - p) * 10 ** (-66 / 20)
    for tp, lv, ln in ((2.0, -38, 0.035), (2.2, -18, 0.23), (2.6, -44, 0.03), (3.0, -40, 0.05), (3.4, -45, 0.03)):
        q = int(tp * RATE)
        z[q:q + int(ln * RATE)] += rng.standard_normal(int(ln * RATE)) * 10 ** (lv / 20)
    s = np.clip(np.round(np.stack([z, z], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for h in egmodel.HYPS:
    make(out / f'eg_{h}.wav', h)
print('written')
