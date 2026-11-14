"""2 組のチャンネルの録音を、ずらしを探してから比べる（録り始めの位置が違うもの用）。
    py cmpshift.py <A> <B>
ch1 で、B を A に対して -6000..6000 サンプルずらした中から完全に一致する（または差が最小の）ずらしを探し、全チャンネルをその
ずらしの重なる区間で比べる。"""
import sys
import wave
from pathlib import Path

import numpy as np


def load(p):
    with wave.open(str(p), 'rb') as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.int64)
        if w.getnchannels() == 2:
            a = a[0::2]
    return a


A, B = Path(sys.argv[1]), Path(sys.argv[2])
ref_a, ref_b = load(A / 'ch1.wav'), load(B / 'ch1.wav')
best = None
for s in range(-6000, 6001):
    a = ref_a[max(0, s):]
    b = ref_b[max(0, -s):]
    n = min(len(a), len(b)) - 10
    if n < 5000:
        continue
    d = int(np.abs(a[:n] - b[:n]).sum())
    if best is None or d < best[1]:
        best = (s, d)
        if d == 0:
            break
s = best[0]
print(f'shift {s} (ch1 abs diff {best[1]})')
ok = True
for i in range(1, 16):
    a, b = load(A / f'ch{i}.wav'), load(B / f'ch{i}.wav')
    a = a[max(0, s):]
    b = b[max(0, -s):]
    n = min(len(a), len(b))
    d = np.abs(a[:n] - b[:n])
    peak = int(np.abs(a[:n]).max(initial=0))
    if d.max(initial=0) == 0:
        print(f'ch{i}: same over {n} samples (peak {peak})')
    else:
        ok = False
        print(f'ch{i}: DIFF max {int(d.max())}, {int((d > 0).sum())} of {n} samples (peak {peak})')
print('ALL SAME' if ok else 'SOME DIFFER')
