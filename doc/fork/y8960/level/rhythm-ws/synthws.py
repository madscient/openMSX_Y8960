"""anaws.py の判別力を見るための合成の録音を作る。

    py synthws.py <出力先のディレクトリ>

none.wav     : BD と TT だけが波形で変わる（雑音のリズム音は変わらない）
all.wav      : すべての音が波形で変わる
mga_none.wav : none.wav に、MGA の電源投入（床の上昇、電源投入と初期化の音）を足したもの
mga_all.wav  : all.wav に同じものを足したもの

anaws.py は、none 系で SD・CY・HH を「掛かる」と出してはいけない。all 系ではすべて「掛かる」と出す。
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 48000
INSTR = ['BD', 'SD', 'TT', 'CY', 'HH']
WS_SEQ = [0, 1, 2, 3, 0]
rng = np.random.default_rng(1)


def shape(x, ws):
    if ws == 1:
        return np.where(x > 0, x, 0)
    if ws == 2:
        return np.abs(x)
    if ws == 3:
        return np.where(np.sin(2 * np.pi * 4 * np.arange(len(x)) / len(x)) > 0, np.abs(x), 0)
    return x


def hit(name, ws, affected):
    n = int(0.8 * RATE)
    t = np.arange(n) / RATE
    env = np.exp(-t / 0.15)
    if name in ('BD', 'TT'):
        f = 60 if name == 'BD' else 200
        x = np.sin(2 * np.pi * f * t + 2 * np.sin(2 * np.pi * f * t))
    else:
        x = rng.standard_normal(n)
        if name == 'HH':
            x = np.diff(x, prepend=0)
    if affected:
        x = shape(x, ws)
    return 0.3 * env * x


def make(path, affected_noise, mga):
    total = int((1.5 + 3.0 + 25 * 1.0 + 1.0) * RATE)
    y = rng.standard_normal(total) * 10 ** (-70 / 20)
    # 実機の録音で、最初の打の前に 5ms のクリックが 1 つ出たことがある
    c = int(2.26 * RATE)
    y[c:c + int(0.003 * RATE)] += 0.02
    if mga:
        # MGA の電源投入: 床が約 20dB 上がり、最初の打の約 1 秒前まで電源投入と初期化の音が出る
        p = int(2.0 * RATE)
        y[p:] += rng.standard_normal(total - p) * 10 ** (-66 / 20)
        for tp, lv, ln in ((2.0, -38, 0.035), (2.2, -18, 0.23), (2.6, -44, 0.03), (3.0, -40, 0.05), (3.4, -45, 0.03)):
            q = int(tp * RATE)
            y[q:q + int(ln * RATE)] += rng.standard_normal(int(ln * RATE)) * 10 ** (lv / 20)
    pos = int(4.5 * RATE)
    n = 0
    for ws in WS_SEQ:
        for name in INSTR:
            n += 1
            if n == 8:
                # 実機では、ときどき 1 歩が 1.3 秒ほどに延びる
                pos += int(0.33 * RATE)
            affected = name in ('BD', 'TT') or affected_noise
            h = hit(name, ws, affected)
            y[pos:pos + len(h)] += h
            # 実機では、レジスタの書き込みの分だけ 1 歩が 1000ms より延びる
            pos += int(1.022 * RATE)
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(s.tobytes())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / 'none.wav', False, False)
make(out / 'all.wav', True, False)
make(out / 'mga_none.wav', False, True)
make(out / 'mga_all.wav', True, True)
print('written')
