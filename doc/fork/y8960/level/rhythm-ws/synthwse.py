"""anawse.py の判別力を見るための、HH だけの合成の録音を作る。MGA の電源投入（床の上昇と電源投入の音）を含む。

    py synthwse.py <出力先のディレクトリ>

wse_sil.wav  : 01h = 20h の打が鳴らない
wse_none.wav : 01h で変わらない

wse_sil.wav は、静かな打が 4 つ続く並びで位置合わせが崩れないかも見る。
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000
SEQ = [0x00] * 4 + [0x20] * 4 + [0x00] * 4 + [0x20] * 4
rng = np.random.default_rng(3)


def make(path, silenced):
    total = int((8.0 + 17 * 1.03 + 1.0) * RATE)
    y = rng.standard_normal(total) * 10 ** (-86 / 20)
    p = int(3.9 * RATE)
    y[p:] += rng.standard_normal(total - p) * 10 ** (-66 / 20)
    q = int(4.1 * RATE)
    y[q:q + int(0.23 * RATE)] += rng.standard_normal(int(0.23 * RATE)) * 10 ** (-18 / 20)
    pos = int(8.08 * RATE)
    n = int(0.8 * RATE)
    t = np.arange(n) / RATE
    for i, r in enumerate(SEQ):
        if i == 9:
            pos += int(0.3 * RATE)
        x = np.diff(rng.standard_normal(n), prepend=0) * np.exp(-t / 0.12)
        g = 0.0 if (silenced and r == 0x20) else 0.1
        y[pos:pos + n] += g * x
        pos += int(1.025 * RATE)
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / 'wse_sil.wav', True)
make(out / 'wse_none.wav', False)
