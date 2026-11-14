"""anafb.py の判別力を見るための合成の録音を作る。MGA の電源投入、ときどき延びる歩、リズム音の減衰、HH の打ごとの揺らぎを含む。

    py synthfb.py <出力先のディレクトリ>

fb_all.wav    : 対照・TT・HH のすべてが FB で変わる
fb_ctl.wav    : 対照だけが FB で変わる（TT と HH は変わらない）
fb_none.wav   : どれも変わらない（対照が効かないので、回は無効になるはず）
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000
rng = np.random.default_rng(11)
SEQ = [('CTL', 0), ('CTL', 7)] * 2 + [('TT', 0), ('TT', 7)] * 4 + [('HH', 0), ('HH', 7)] * 4


def tone(f, n, fb):
    t = np.arange(n) / RATE
    if fb:
        # FB は正弦波を鋸歯状に近づける。倍音を足してまねる
        return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, 9)) * 0.6
    return np.sin(2 * np.pi * f * t)


def hh(n, fb):
    x = np.diff(rng.standard_normal(n), prepend=0)
    sp = np.fft.rfft(x)
    fr = np.fft.rfftfreq(n, 1 / RATE)
    # 打ごとの揺らぎ: 帯域の形を ±1.5dB ほど散らす
    tilt = 10 ** (rng.normal(0, 1.5) * np.log2(np.maximum(fr, 50) / 3000) / 20 / 4)
    if fb:
        tilt = tilt * 10 ** (-6 * np.log2(np.maximum(fr, 50) / 3000) / 20)
    return np.fft.irfft(sp * tilt, n)


def make(path, changes):
    total = int((8.0 + 21 * 1.05 + 2.0) * RATE)
    y = rng.standard_normal(total) * 10 ** (-86 / 20)
    p = int(2.0 * RATE)
    y[p:] += rng.standard_normal(total - p) * 10 ** (-66 / 20)
    for tp, lv, ln in ((2.0, -38, 0.035), (2.2, -18, 0.23), (2.6, -44, 0.03), (3.0, -40, 0.05), (3.4, -45, 0.03)):
        q = int(tp * RATE)
        y[q:q + int(ln * RATE)] += rng.standard_normal(int(ln * RATE)) * 10 ** (lv / 20)
    pos = int(6.5 * RATE)
    n = int(0.8 * RATE)
    t = np.arange(n) / RATE
    for i, (name, fb) in enumerate(SEQ):
        if i == 9:
            pos += int(0.35 * RATE)
        eff = fb if name in changes else 0
        if name == 'CTL':
            x = 0.1 * tone(440, n, eff)
        elif name == 'TT':
            x = 0.2 * tone(190, n, eff) * np.exp(-t * 9.0)
        else:
            x = 0.1 * hh(n, eff) * np.exp(-t * 9.0)
        y[pos:pos + n] += x
        pos += int(1.03 * RATE)
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / 'fb_all.wav', {'CTL', 'TT', 'HH'})
make(out / 'fb_ctl.wav', {'CTL'})
make(out / 'fb_none.wav', set())
print('written')
