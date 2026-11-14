"""anahh.py の判別力を見るための、HH だけの合成の録音を作る。

    py synthhh.py <出力先のディレクトリ>

hh_none.wav : 波形で変わらない
hh_weak.wav : 波形 1 で負の半分が消える（変化は小さめ）

打ごとに大きさを 1.5dB ほど散らし、実機の HH の打ごとの揺らぎをまねる。
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000
SEQ = [0, 1, 2, 3] * 4 + [0] * 4
rng = np.random.default_rng(2)


def make(path, affected):
    total = int((4.5 + 21 * 1.022 + 1.0) * RATE)
    y = rng.standard_normal(total) * 10 ** (-70 / 20)
    pos = int(4.5 * RATE)
    n = int(0.8 * RATE)
    t = np.arange(n) / RATE
    for i, ws in enumerate(SEQ):
        if i == 7:
            # 実機では、ときどき 1 歩が 1.3 秒ほどに延びる
            pos += int(0.33 * RATE)
        x = np.diff(rng.standard_normal(n), prepend=0) * np.exp(-t / 0.12)
        if affected and ws == 1:
            x = np.where(x > 0, x, 0)
        g = 10 ** (rng.normal(0, 1.5) / 20)
        y[pos:pos + n] += 0.2 * g * x
        pos += int(1.022 * RATE)
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / 'hh_none.wav', False)
make(out / 'hh_weak.wav', True)
