"""anafbd.py の判別力を見るための合成の録音を作る。fbmodel.py の各仮説で 24 打を作り、平らでない周波数特性、
経路のひずみ、チップのクロックのずれ、MGA の電源投入、ときどき延びる歩を加える。

    py synthfbd.py <出力先のディレクトリ>

fbd_<仮説>.wav（real、y8960、pr16、wide10）。anafbd.py は、それぞれの仮説だけを「合う」とするはず
"""
import sys
import wave
from pathlib import Path

import numpy as np

import fbmodel
from mkfbd import SEQ

RATE = 48000
# 種と、チップのクロックのずれ [ppm] は引数で替えられる（既定 23、+30）
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 23
CHIP = fbmodel.FS * (1 + (float(sys.argv[3]) if len(sys.argv) > 3 else 30) * 1e-6)
rng = np.random.default_rng(SEED)


def response(f):
    f = np.maximum(f, 1.0)
    hp = (1j * f / 20) / (1 + 1j * f / 20)
    s = 1j * f / 9000
    lp = 1 / (1 + np.sqrt(2) * s + s * s)
    tilt = 10 ** (-1.5 * np.log2(np.maximum(f, 20) / 1000) / 20)
    return hp * lp * tilt


def make(path, hyp):
    total = int((8.0 + len(SEQ) * 1.05 + 2.0) * CHIP)
    y = np.zeros(total)
    pos = int(6.5 * CHIP)
    n = int(0.8 * CHIP)
    ramp = np.ones(n)
    ramp[-100:] = np.linspace(1, 0, 100)
    for i, (name, mult, fb, tl) in enumerate(SEQ):
        if i == 9:
            pos += int(0.35 * CHIP)
        y[pos:pos + n] += fbmodel.run(fb, tl, hyp, mult, n) * ramp * (0.25 / 4096)
        pos += int(1.03 * CHIP)
    sp = np.fft.rfft(y)
    nout = int(round(total * RATE / CHIP))
    sp2 = np.zeros(nout // 2 + 1, complex)
    k = min(len(sp), len(sp2))
    sp2[:k] = sp[:k]
    fr = np.fft.rfftfreq(nout, 1 / RATE)
    z = np.fft.irfft(sp2 * response(fr), nout) * (nout / total)
    z = z + 0.02 * z ** 2 + 0.05 * z ** 3
    z += rng.standard_normal(nout) * 10 ** (-86 / 20)
    p = int(2.0 * RATE)
    z[p:] += rng.standard_normal(nout - p) * 10 ** (-66 / 20)
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
for h in fbmodel.HYP:
    make(out / f'fbd_{h}.wav', h)
print('written')
