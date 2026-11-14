"""chrec.tcl の出力を mark の時刻から 10-410ms の窓で切り、全チャンネルの RMS と、全チャンネルの和の RMS を出す。
    py chwin.py <dir>"""
import sys
import wave
from pathlib import Path

import numpy as np

d = Path(sys.argv[1])
chs = {}
for i in range(1, 16):
    with wave.open(str(d / f'ch{i}.wav'), 'rb') as w:
        rate = w.getframerate()
        nch = w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float64) / 32768
    chs[i] = a.reshape(-1, nch)[:, 0]
n = min(len(v) for v in chs.values())
total = sum(v[:n] for v in chs.values())


def db(x):
    x = x - x.mean()
    return 10 * np.log10(max(np.mean(x * x), 1e-14))


for line in open(d / 'log.txt', encoding='utf-8'):
    parts = line.split()
    if len(parts) != 2:
        continue
    t, name = float(parts[0]), parts[1]
    s, e = int((t + 0.010) * rate), int((t + 0.410) * rate)
    loud = [(i, db(chs[i][s:e])) for i in chs if db(chs[i][s:e]) > -60]
    print(f'{name:6s} sum {db(total[s:e]):6.1f}  ' + '  '.join(f'ch{i} {v:6.1f}' for i, v in loud))
